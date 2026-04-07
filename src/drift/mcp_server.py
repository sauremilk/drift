"""Drift MCP server — exposes drift analysis as MCP tools for VS Code / Copilot.

Requires the optional ``mcp`` extra: ``pip install drift-analyzer[mcp]``

The server uses stdio transport (no network listener) and is started via
``drift mcp --serve``.  VS Code discovers it through ``.vscode/mcp.json``.

Tool surface (v2):
    drift_scan       — Full repo analysis (concise/detailed)
    drift_diff       — Diff-based change detection
    drift_explain    — Signal/rule/error explanations
    drift_fix_plan   — Prioritised repair tasks with constraints
    drift_validate   — Preflight config & environment check
    drift_brief      — Pre-task structural briefing with guardrails
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import io
import json
import os
import re as _re
from pathlib import Path
from typing import Annotated, Any, cast

try:
    import anyio

    _ANYIO_AVAILABLE = True
except ImportError:
    anyio = None  # type: ignore[assignment]
    _ANYIO_AVAILABLE = False

MCPFastMCPImpl: Any


async def _run_sync_in_thread(
    fn: Any,
    *args: object,
    abandon_on_cancel: bool = False,
) -> Any:
    """Run sync callables in a worker thread with optional anyio support."""
    if _ANYIO_AVAILABLE and anyio is not None:
        return await anyio.to_thread.run_sync(fn, *args, abandon_on_cancel=abandon_on_cancel)
    return await asyncio.to_thread(fn, *args)


async def _run_sync_with_timeout(
    fn: Any,
    timeout_seconds: float,
    *args: object,
) -> Any:
    """Run a sync callable with timeout, even when anyio is unavailable."""
    if _ANYIO_AVAILABLE and anyio is not None:
        with anyio.fail_after(timeout_seconds):
            return await anyio.to_thread.run_sync(fn, *args, abandon_on_cancel=True)
    return await asyncio.wait_for(
        asyncio.to_thread(fn, *args),
        timeout=timeout_seconds,
    )

try:
    from mcp.server.fastmcp import FastMCP as _ImportedFastMCP
    from pydantic import Field

    _MCP_AVAILABLE = True
    MCPFastMCPImpl = _ImportedFastMCP
except ImportError:
    _MCP_AVAILABLE = False

    def Field(**_kwargs: object) -> Any:  # type: ignore[misc,no-redef]  # noqa: N802
        """No-op fallback when pydantic is unavailable."""
        return ...

    class _FallbackFastMCP:
        """Minimal fallback so helper functions stay importable without mcp extra."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def tool(self):
            def _decorator(func):
                return func

            return _decorator

        def run(self, **_kwargs: object) -> None:
            msg = "MCP server requires optional dependency 'mcp'."
            raise RuntimeError(msg)

    MCPFastMCPImpl = _FallbackFastMCP

# ---------------------------------------------------------------------------
# Dynamic instructions builder
# ---------------------------------------------------------------------------

_BASE_INSTRUCTIONS = (
    "Drift is a deterministic static analyzer that detects architectural "
    "erosion in Python codebases. Use these tools to analyze repositories "
    "for coherence problems like pattern fragmentation, layer violations, "
    "and near-duplicate code.\n\n"
    "Tool workflow:\n"
    "1. drift_validate — check config & environment before first analysis\n"
    "2. drift_brief — get a structural briefing BEFORE implementing a task "
    "(returns scope-aware guardrails as prompt constraints)\n"
    "3. drift_scan — assess overall architectural health\n"
    "4. drift_negative_context — get anti-patterns to avoid in new code\n"
    "5. drift_diff — detect regressions in a PR or after changes\n"
    "6. drift_fix_plan — get actionable repair tasks with constraints\n"
    "7. drift_explain — understand unfamiliar signals or findings\n"
    "8. drift_nudge — get directional feedback after each file change "
    "(do not batch)\n\n"
    "IMPORTANT: When asked to implement a feature, add functionality, or make "
    "structural changes, call drift_brief(task=\"<task description>\") FIRST "
    "before writing any code. Use the returned guardrails as constraints "
    "in your code generation. If the scope confidence is below 0.5, ask the "
    "user to specify a --scope path.\n\n"
    "After each file change, call drift_nudge for fast directional feedback. "
    "Use drift_diff for full regression analysis. Do not batch multiple file "
    "changes without checking drift impact. "
    "Every response includes an 'agent_instruction' field — follow it.\n\n"
    "FIX-LOOP PROTOCOL (when fixing multiple findings):\n"
    "0. BASELINE WARM-UP: Call drift_validate, then drift_scan once to "
    "establish the nudge baseline — this avoids a costly first-nudge "
    "delay later. Keep the scan result as your session snapshot.\n"
    "1. SESSION START: Call drift_fix_plan(max_tasks=20) to see full scope. "
    "Then run 'drift baseline save' to create a checkpoint.\n"
    "2. BATCH AWARENESS: Tasks with batch_eligible=true share a fix pattern. "
    "Apply the fix to ALL affected_files_for_pattern listed, not just the first.\n"
    "3. VERIFICATION: After batch fixes, call "
    "drift_diff(uncommitted=True, baseline_file='.drift-baseline.json') "
    "to verify resolution. Check resolved_count_by_rule for batch efficiency.\n"
    "4. SESSION RESUME: After interruption, call "
    "drift_diff(baseline_file='.drift-baseline.json') "
    "to see remaining work without re-scanning.\n"
    "5. COMPLETED: When drift_diff shows 0 new findings vs baseline, "
    "session is done.\n\n"
    "BATCH REPAIR MODE:\n"
    "When fixing drift findings, you may apply the same fix pattern across "
    "multiple files in one iteration for batch_eligible tasks.\n"
    "Rules: Only batch fixes where batch_eligible=true in fix_plan response. "
    "Apply the SAME fix template to ALL affected_files_for_pattern. "
    "Verify the batch with a single drift_diff call, not per-file. "
    "If any file in the batch fails verification, revert that file only."
)


def _load_negative_context_instructions() -> str:
    """Build MCP instructions, enriching with cached anti-patterns if available.

    Looks for ``.drift-negative-context.md`` in the working directory.
    If found, extracts the top anti-pattern summaries and appends them
    to the base instructions so agents receive them at server start.
    """
    ctx_file = Path(".drift-negative-context.md")
    if not ctx_file.is_file():
        return _BASE_INSTRUCTIONS

    try:
        content = ctx_file.read_text(encoding="utf-8")
    except OSError:
        return _BASE_INSTRUCTIONS

    # Extract anti-pattern bullet points (lines starting with "- " under markers)
    from drift.negative_context_export import MARKER_BEGIN, MARKER_END

    begin = content.find(MARKER_BEGIN)
    end = content.find(MARKER_END)
    if begin < 0 or end < 0:
        return _BASE_INSTRUCTIONS

    section = content[begin + len(MARKER_BEGIN):end].strip()
    if not section:
        return _BASE_INSTRUCTIONS

    # Extract DO NOT lines (compact summary)
    do_not_lines: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- **DO NOT:**"):
            do_not_lines.append(stripped.removeprefix("- **DO NOT:** "))

    if not do_not_lines:
        return _BASE_INSTRUCTIONS

    # Limit to top 10 for concise instructions
    top = do_not_lines[:10]
    suffix = (
        f"\n  ... and {len(do_not_lines) - 10} more"
        if len(do_not_lines) > 10
        else ""
    )

    anti_pattern_block = (
        "\n\nKNOWN ANTI-PATTERNS IN THIS REPOSITORY "
        "(from last drift export-context):\n"
        + "\n".join(f"- DO NOT: {line}" for line in top)
        + suffix
    )

    return _BASE_INSTRUCTIONS + anti_pattern_block


# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = MCPFastMCPImpl(
    "drift",
    instructions=_load_negative_context_instructions(),
)


# ---------------------------------------------------------------------------
# MCP Tools — v2 agent-native surface
# ---------------------------------------------------------------------------


@mcp.tool()
async def drift_scan(
    path: Annotated[str, Field(description="Repository path to analyze.")] = ".",
    target_path: Annotated[
        str | None,
        Field(description="Restrict analysis to this subdirectory (relative to repo root)."),
    ] = None,
    since_days: Annotated[
        int, Field(description="Days of git history to consider.")
    ] = 90,
    signals: Annotated[
        str | None,
        Field(description="Comma-separated signal IDs to include, e.g. 'PFS,AVS'. Omit for all."),
    ] = None,
    exclude_signals: Annotated[
        str | None,
        Field(description="Comma-separated signal IDs to exclude, e.g. 'MDS,DIA'."),
    ] = None,
    max_findings: Annotated[
        int, Field(description="Maximum number of findings to return.")
    ] = 10,
    max_per_signal: Annotated[
        int | None,
        Field(description="Optional cap of findings per signal in returned results."),
    ] = None,
    response_detail: Annotated[
        str,
        Field(description="Detail level: 'concise' (token-efficient) or 'detailed' (all fields)."),
    ] = "concise",
    include_non_operational: Annotated[
        bool,
        Field(
            description=(
                "Include findings from non-operational contexts"
                " (fixtures, generated code)."
            ),
        ),
    ] = False,
) -> str:
    """Analyze a repository for architectural drift.

    Returns drift score, severity, top signals, fix-first queue,
    and findings sorted by impact.  Use this to assess overall health.

    Args:
        path: Repository path (default: current directory).
        target_path: Restrict analysis to a subdirectory.
        since_days: Days of git history to consider (default: 90).
        signals: Comma-separated signal IDs to include (e.g. "PFS,AVS").
        exclude_signals: Comma-separated signal IDs to exclude.
        max_findings: Maximum findings to return (default: 10).
        max_per_signal: Optional cap of findings per signal in the returned list.
        response_detail: "concise" (token-sparing) or "detailed" (full fields).
        include_non_operational: Include non-operational contexts in fix_first ordering.
    """

    def _sync() -> str:
        from drift.api import scan

        try:
            signal_list = (
                [s.strip() for s in signals.split(",") if s.strip()]
                if signals
                else None
            )
            exclude_signal_list = (
                [s.strip() for s in exclude_signals.split(",") if s.strip()]
                if exclude_signals
                else None
            )
            with contextlib.redirect_stdout(io.StringIO()):
                result = scan(
                    path,
                    target_path=target_path,
                    since_days=since_days,
                    signals=signal_list,
                    exclude_signals=exclude_signal_list,
                    max_findings=max_findings,
                    max_per_signal=max_per_signal,
                    response_detail=response_detail,
                    include_non_operational=include_non_operational,
                )
            return json.dumps(result, default=str)
        except Exception as exc:
            from drift.api_helpers import _error_response

            error = _error_response("DRIFT-5001", str(exc), recoverable=True)
            error["tool"] = "drift_scan"
            return json.dumps(error, default=str)

    return cast(str, await _run_sync_in_thread(_sync))


@mcp.tool()
async def drift_diff(
    path: Annotated[str, Field(description="Repository path to analyze.")] = ".",
    diff_ref: Annotated[
        str, Field(description="Git ref to diff against, e.g. 'HEAD~1', 'main', or a commit SHA.")
    ] = "HEAD~1",
    uncommitted: Annotated[
        bool, Field(description="Compare current working-tree changes against HEAD.")
    ] = False,
    staged_only: Annotated[
        bool, Field(description="Compare only staged (git add) changes.")
    ] = False,
    baseline_file: Annotated[
        str | None,
        Field(description="Path to .drift-baseline.json file for snapshot comparison."),
    ] = None,
    max_findings: Annotated[
        int, Field(description="Maximum number of findings to return.")
    ] = 10,
    response_detail: Annotated[
        str,
        Field(description="Detail level: 'concise' (token-efficient) or 'detailed' (all fields)."),
    ] = "concise",
    signals: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated signal abbreviations to include "
                "(e.g. 'PFS,BEM'). If omitted, all signals."
            ),
        ),
    ] = None,
    exclude_signals: Annotated[
        str | None,
        Field(description="Comma-separated signal abbreviations to exclude (e.g. 'MDS,DIA')."),
    ] = None,
) -> str:
    """Detect drift changes since a git ref or baseline.

    Use this for PR review, CI gating, or before/after comparison.
    Returns drift_detected flag, score delta, new and resolved findings.

    Args:
        path: Repository path (default: current directory).
        diff_ref: Git ref to diff against (default: HEAD~1).
        uncommitted: Compare current working-tree changes against HEAD.
        staged_only: Compare only staged changes.
        baseline_file: Path to .drift-baseline.json for comparison.
        max_findings: Maximum findings to return (default: 10).
        response_detail: "concise" or "detailed".
        signals: Comma-separated signal abbreviations to include.
        exclude_signals: Comma-separated signal abbreviations to exclude.
    """

    def _sync() -> str:
        from drift.api import diff

        signal_list = (
            [s.strip() for s in signals.split(",") if s.strip()]
            if signals
            else None
        )
        exclude_list = (
            [s.strip() for s in exclude_signals.split(",") if s.strip()]
            if exclude_signals
            else None
        )

        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = diff(
                    path,
                    diff_ref=diff_ref,
                    uncommitted=uncommitted,
                    staged_only=staged_only,
                    baseline_file=baseline_file,
                    max_findings=max_findings,
                    response_detail=response_detail,
                    signals=signal_list,
                    exclude_signals=exclude_list,
                )
            return json.dumps(result, default=str)
        except Exception as exc:
            from drift.api_helpers import _error_response

            error = _error_response("DRIFT-5001", str(exc), recoverable=True)
            error["tool"] = "drift_diff"
            return json.dumps(error, default=str)

    return cast(str, await _run_sync_in_thread(_sync))


@mcp.tool()
async def drift_explain(
    topic: Annotated[
        str,
        Field(
            description=(
                "Signal abbreviation ('PFS'), signal name"
                " ('pattern_fragmentation'), or error code ('DRIFT-1001')."
            ),
        ),
    ],
) -> str:
    """Explain a drift signal, rule, or error code.

    Use when you encounter an unfamiliar signal abbreviation (e.g. "PFS"),
    need to understand what a finding means, or want remediation guidance.

    Args:
        topic: Signal abbreviation ("PFS"), signal name
            ("pattern_fragmentation"), or error code ("DRIFT-1001").
    """

    def _sync() -> str:
        from drift.api import explain

        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = explain(topic)
            return json.dumps(result, default=str)
        except Exception as exc:
            from drift.api_helpers import _error_response

            error = _error_response("DRIFT-5001", str(exc), recoverable=True)
            error["tool"] = "drift_explain"
            return json.dumps(error, default=str)

    return cast(str, await _run_sync_in_thread(_sync))


@mcp.tool()
async def drift_fix_plan(
    path: Annotated[str, Field(description="Repository path to analyze.")] = ".",
    signal: Annotated[
        str | None,
        Field(description="Filter to a specific signal ID, e.g. 'PFS', 'AVS', 'BEM'."),
    ] = None,
    max_tasks: Annotated[
        int, Field(description="Maximum number of repair tasks to return.")
    ] = 5,
    automation_fit_min: Annotated[
        str | None,
        Field(description="Minimum automation fitness level: 'low', 'medium', or 'high'."),
    ] = None,
    target_path: Annotated[
        str | None,
        Field(description="Restrict tasks to findings inside this subdirectory."),
    ] = None,
    exclude_paths: Annotated[
        str | None,
        Field(
            description=(
                "Exclude findings inside these subdirectories "
                "(comma-separated paths)."
            ),
        ),
    ] = None,
    include_deferred: Annotated[
        bool,
        Field(description="Include findings marked deferred in drift config."),
    ] = False,
    include_non_operational: Annotated[
        bool,
        Field(
            description=(
                "Include findings from non-operational contexts"
                " (fixtures, generated code)."
            ),
        ),
    ] = False,
) -> str:
    """Generate prioritised repair tasks with constraints and success criteria.

    Use this after drift_scan identifies findings you want to fix.
    Each task includes action steps, do-not-over-fix constraints,
    machine-verifiable success criteria, and automation fitness rating.

    Args:
        path: Repository path (default: current directory).
        signal: Filter to a specific signal ("PFS", "AVS", etc.).
        max_tasks: Maximum tasks to return (default: 5).
        automation_fit_min: Minimum automation fitness: "low", "medium", or "high".
        target_path: Restrict tasks to findings inside this subpath.
        exclude_paths: Exclude findings inside one or more subpaths.
        include_deferred: Include findings tagged deferred by config.
        include_non_operational: Include non-operational contexts in prioritized tasks.
    """

    def _sync() -> str:
        from drift.api import fix_plan

        try:
            with contextlib.redirect_stdout(io.StringIO()):
                exclude_paths_list = (
                    [p.strip() for p in exclude_paths.split(",") if p.strip()]
                    if exclude_paths
                    else None
                )
                result = fix_plan(
                    path,
                    signal=signal,
                    max_tasks=max_tasks,
                    automation_fit_min=automation_fit_min,
                    target_path=target_path,
                    exclude_paths=exclude_paths_list,
                    include_deferred=include_deferred,
                    include_non_operational=include_non_operational,
                )
            return json.dumps(result, default=str)
        except Exception as exc:
            from drift.api_helpers import _error_response

            error = _error_response("DRIFT-5001", str(exc), recoverable=True)
            error["tool"] = "drift_fix_plan"
            return json.dumps(error, default=str)

    return cast(str, await _run_sync_in_thread(_sync))


@mcp.tool()
async def drift_validate(
    path: Annotated[str, Field(description="Repository path to validate.")] = ".",
    config_file: Annotated[
        str | None,
        Field(description="Explicit config file path (auto-discovered from repo root if omitted)."),
    ] = None,
) -> str:
    """Validate configuration and environment before running analysis.

    Use before first drift_scan or after config changes to verify
    that git is available, config is valid, and files are discoverable.

    Args:
        path: Repository path (default: current directory).
        config_file: Explicit config file path (auto-discovered if omitted).
    """

    def _sync() -> str:
        from drift.api import validate

        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = validate(path, config_file=config_file)
            return json.dumps(result, default=str)
        except Exception as exc:
            from drift.api_helpers import _error_response

            error = _error_response("DRIFT-5001", str(exc), recoverable=True)
            error["tool"] = "drift_validate"
            return json.dumps(error, default=str)

    return cast(str, await _run_sync_in_thread(_sync))


@mcp.tool()
async def drift_nudge(
    path: Annotated[str, Field(description="Repository path to analyze.")] = ".",
    changed_files: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated changed file paths"
                " (posix, relative to repo root)."
                " Auto-detected via git if omitted."
            ),
        ),
    ] = None,
    uncommitted: Annotated[
        bool,
        Field(
            description=(
                "When auto-detecting changes, use uncommitted"
                " working-tree changes (True) vs staged-only (False)."
            ),
        ),
    ] = True,
) -> str:
    """Get directional feedback after a file change (experimental).

    Returns direction (improving/stable/degrading), safe_to_commit flag,
    and confidence per signal — without running a full scan.  Call this
    after every file edit instead of drift_diff for faster feedback.

    First call on a repository triggers a full baseline scan.  Subsequent
    calls only re-analyze changed files for file-local signals and carry
    forward cross-file results with estimated confidence.

    Args:
        path: Repository path (default: current directory).
        changed_files: Comma-separated list of changed file paths
            (posix, relative to repo root).  Auto-detected via git if omitted.
        uncommitted: When auto-detecting, use uncommitted working-tree
            changes (default) vs. staged-only.
    """

    def _sync() -> str:
        from drift.api import nudge

        try:
            file_list: list[str] | None = None
            if changed_files is not None:
                file_list = [f.strip() for f in changed_files.split(",") if f.strip()]

            with contextlib.redirect_stdout(io.StringIO()):
                result = nudge(
                    path,
                    changed_files=file_list,
                    uncommitted=uncommitted,
                )
            return json.dumps(result, default=str)
        except Exception as exc:
            from drift.api_helpers import _error_response

            error = _error_response("DRIFT-5001", str(exc), recoverable=True)
            error["tool"] = "drift_nudge"
            return json.dumps(error, default=str)

    return cast(str, await _run_sync_in_thread(_sync))


@mcp.tool()
async def drift_brief(
    path: Annotated[str, Field(description="Repository path to analyze.")] = ".",
    task: Annotated[
        str,
        Field(
            description=(
                "Natural-language task description, e.g."
                " 'add payment integration to checkout'."
            ),
        ),
    ] = "",
    scope: Annotated[
        str | None,
        Field(
            description=(
                "Manual scope override (path, e.g. 'src/checkout/')."
                " Auto-resolved from task if omitted."
            ),
        ),
    ] = None,
    max_guardrails: Annotated[
        int, Field(description="Maximum number of guardrails to return.")
    ] = 10,
    response_detail: Annotated[
        str,
        Field(
            description=(
                "Detail level: 'concise' (guardrails + risk only)"
                " or 'detailed' (full landscape)."
            ),
        ),
    ] = "concise",
) -> str:
    """Get a pre-task structural briefing before writing code.

    Resolves the task scope from the task description, assesses structural
    risk in that scope, and returns copy-pastable guardrails (prompt
    constraints) that prevent common architectural erosion patterns.

    Call this BEFORE starting any feature implementation or refactoring.
    Use the returned guardrails as constraints in your code generation.

    Args:
        path: Repository path (default: current directory).
        task: Natural-language description of the planned work.
        scope: Manual scope override path. Auto-resolved from task if omitted.
        max_guardrails: Maximum guardrails to return (default: 10).
        response_detail: "concise" (token-sparing) or "detailed" (full fields).
    """

    def _sync() -> str:
        from drift.api import brief

        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = brief(
                    path,
                    task=task,
                    scope_override=scope,
                    max_guardrails=max_guardrails,
                )

            if response_detail == "concise":
                # Strip verbose landscape fields for token efficiency
                result.pop("landscape", None)
                result.pop("meta", None)

            return json.dumps(result, default=str)
        except Exception as exc:
            from drift.api_helpers import _error_response

            error = _error_response("DRIFT-5010", str(exc), recoverable=True)
            error["tool"] = "drift_brief"
            error["agent_instruction"] = (
                "Check that the repository path exists and the task string is not empty. "
                "If the error persists, try passing an explicit --scope."
            )
            return json.dumps(error, default=str)

    payload: str = await asyncio.to_thread(_sync)
    return payload


@mcp.tool()
async def drift_negative_context(
    path: Annotated[str, Field(description="Repository path to analyze.")] = ".",
    scope: Annotated[
        str | None,
        Field(description="Filter by scope: 'file', 'module', or 'repo'. Omit for all scopes."),
    ] = None,
    target_file: Annotated[
        str | None,
        Field(
            description=(
                "Restrict to anti-patterns affecting this file path"
                " (posix, relative to repo root)."
            ),
        ),
    ] = None,
    max_items: Annotated[
        int, Field(description="Maximum number of anti-pattern items to return.")
    ] = 10,
) -> str:
    """Get anti-pattern warnings derived from drift analysis.

    Returns known bad patterns in this repository that coding agents should
    NOT reproduce.  Each item includes the forbidden pattern, a canonical
    alternative, affected files, and a rationale.

    Call this BEFORE generating code to learn what patterns to avoid.
    After generating code, call drift_nudge to verify compliance.

    Args:
        path: Repository path (default: current directory).
        scope: Filter by scope: "file", "module", or "repo" (default: all).
        target_file: Restrict to items affecting a specific file path.
        max_items: Maximum items to return (default: 10).
    """

    def _sync() -> str:
        from drift.api import negative_context

        # Keep MCP stdio clean if dependencies emit accidental stdout lines.
        with contextlib.redirect_stdout(io.StringIO()):
            result = negative_context(
                path,
                scope=scope,
                target_file=target_file,
                max_items=max_items,
                disable_embeddings=True,
            )

        if not isinstance(result, dict):
            fallback = {
                "status": "error",
                "error_code": "DRIFT-2032",
                "message": "MCP tool returned no structured response.",
                "recoverable": True,
                "agent_instruction": (
                    "Retry the call once; if it repeats, run drift_validate."
                ),
            }
            return json.dumps(fallback, default=str)

        return json.dumps(result, default=str)

    try:
        return cast(
            str,
            await _run_sync_with_timeout(_sync, _NEGATIVE_CONTEXT_TIMEOUT_SECONDS),
        )
    except TimeoutError:
        timeout_response = _negative_context_timeout_response(
            path=path,
            scope=scope,
            target_file=target_file,
            max_items=max_items,
            timeout_seconds=_NEGATIVE_CONTEXT_TIMEOUT_SECONDS,
        )
        return json.dumps(timeout_response, default=str)
    except Exception as exc:
        from drift.api_helpers import _error_response

        error = _error_response("DRIFT-5001", str(exc), recoverable=True)
        error["tool"] = "drift_negative_context"
        return json.dumps(error, default=str)


def _load_negative_context_timeout_seconds() -> float:
    """Resolve MCP timeout for drift_negative_context from environment."""
    raw = os.getenv("DRIFT_MCP_NEGATIVE_CONTEXT_TIMEOUT_SECONDS", "20")
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return 20.0


_NEGATIVE_CONTEXT_TIMEOUT_SECONDS = _load_negative_context_timeout_seconds()


def _negative_context_timeout_response(
    *,
    path: str,
    scope: str | None,
    target_file: str | None,
    max_items: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Build a structured timeout response for MCP tool callers."""
    return {
        "status": "error",
        "error_code": "DRIFT-2031",
        "message": (
            "MCP tool 'drift_negative_context' timed out before producing a "
            "response. This guard prevents silent chat hangs."
        ),
        "recoverable": True,
        "timeout_seconds": timeout_seconds,
        "path": path,
        "scope": scope,
        "target_file": target_file,
        "max_items": max_items,
        "agent_instruction": (
            "Retry with a narrower target_file or lower max_items. "
            "If timeout persists, run drift export-context offline and use the "
            "cached .drift-negative-context.md."
        ),
    }


_EXPORTED_MCP_TOOLS = (
    drift_scan,
    drift_diff,
    drift_explain,
    drift_fix_plan,
    drift_validate,
    drift_nudge,
    drift_brief,
    drift_negative_context,
)


def _extract_param_descriptions(doc: str) -> dict[str, str]:
    """Extract parameter descriptions from Google-style Args: docstring section."""
    result: dict[str, str] = {}
    in_args = False
    current_param: str | None = None
    current_parts: list[str] = []
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped == "Args:":
            in_args = True
            continue
        if not in_args:
            continue
        if not stripped:
            continue
        # Non-indented non-empty line = section ended
        if not line.startswith("    ") and not line.startswith("\t"):
            break
        # New param: "name: description" at first indent level
        m = _re.match(r"^(\w+):\s*(.*)", stripped)
        if m:
            if current_param:
                result[current_param] = " ".join(current_parts).strip()
            current_param = m.group(1)
            current_parts = [m.group(2)] if m.group(2) else []
        elif current_param:
            current_parts.append(stripped)
    if current_param:
        result[current_param] = " ".join(current_parts).strip()
    return result


def _annotation_to_string(annotation: Any) -> str:
    """Resolve a Python type annotation to a JSON Schema type string.

    Properly unwraps ``Annotated[T, ...]`` and maps Python primitives to
    their JSON Schema equivalents.
    """
    import types as _bt
    import typing

    if annotation is inspect.Signature.empty:
        return "Any"
    if isinstance(annotation, str):
        return annotation

    # Unwrap Annotated[T, ...] → T
    origin = typing.get_origin(annotation)
    if origin is typing.Annotated:
        args = typing.get_args(annotation)
        if args:
            return _annotation_to_string(args[0])

    # Handle Union / Optional (T | None)
    if origin is _bt.UnionType or origin is typing.Union:
        args = typing.get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _annotation_to_string(non_none[0])

    # Map Python primitives to JSON Schema types
    json_type_map: dict[type, str] = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }
    if isinstance(annotation, type) and annotation in json_type_map:
        return json_type_map[annotation]

    name = getattr(annotation, "__name__", None)
    if isinstance(name, str):
        return name
    return str(annotation).replace("typing.", "")


def get_tool_catalog() -> list[dict[str, Any]]:
    """Return MCP tool metadata for local inspection via CLI."""
    import typing

    catalog: list[dict[str, Any]] = []

    for tool in _EXPORTED_MCP_TOOLS:
        signature = inspect.signature(tool)
        doc = inspect.getdoc(tool) or ""
        summary = doc.splitlines()[0] if doc else ""
        param_descs = _extract_param_descriptions(doc)

        # Resolve string annotations (from __future__ annotations) to real types
        try:
            resolved_hints = typing.get_type_hints(tool, include_extras=True)
        except Exception:
            resolved_hints = {}

        parameters: list[dict[str, Any]] = []
        for parameter in signature.parameters.values():
            if parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            annotation = resolved_hints.get(parameter.name, parameter.annotation)
            required = parameter.default is inspect.Signature.empty
            parameter_info: dict[str, Any] = {
                "name": parameter.name,
                "type": _annotation_to_string(annotation),
                "required": required,
            }
            if not required:
                parameter_info["default"] = parameter.default
            if parameter.name in param_descs:
                parameter_info["description"] = param_descs[parameter.name]
            parameters.append(parameter_info)

        catalog.append(
            {
                "name": tool.__name__,
                "description": summary,
                "parameters": parameters,
            }
        )

    return catalog


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _eager_imports() -> None:
    """Pre-import heavy modules before the event loop starts.

    On Windows the IOCP proactor holds handles that conflict with the
    OS DLL-loader lock.  If a worker thread triggers a first-time import
    of C-extension modules (numpy, torch, faiss …) while the event loop
    owns an IOCP handle, a deadlock occurs.  Importing everything that
    the tool functions need *before* ``mcp.run()`` avoids this entirely.
    """
    import drift.analyzer  # noqa: F401 — pulls in signals, pipeline, scoring
    import drift.api  # noqa: F401 — registers public surface
    import drift.pipeline  # noqa: F401 — pulls in embeddings (numpy/torch)


def main() -> None:
    """Run the drift MCP server on stdio transport."""
    if not _MCP_AVAILABLE:
        msg = "MCP server requires optional dependency 'mcp'."
        raise RuntimeError(msg)
    _eager_imports()
    mcp.run(transport="stdio")
