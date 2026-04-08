"""Drift MCP server — exposes drift analysis as MCP tools for VS Code / Copilot.

Requires the optional ``mcp`` extra: ``pip install drift-analyzer[mcp]``

The server uses stdio transport (no network listener) and is started via
``drift mcp --serve``.  VS Code discovers it through ``.vscode/mcp.json``.

Tool surface (v3 — sessions):
    drift_scan            — Full repo analysis (concise/detailed)
    drift_diff            — Diff-based change detection
    drift_explain         — Signal/rule/error explanations
    drift_fix_plan        — Prioritised repair tasks with constraints
    drift_validate        — Preflight config & environment check
    drift_brief           — Pre-task structural briefing with guardrails
    drift_nudge           — Fast directional feedback after edits
    drift_negative_context — Anti-pattern warnings
    drift_session_start   — Create a stateful session (scope, baseline, tasks)
    drift_session_status  — Show current session state
    drift_session_update  — Modify session scope, mark tasks complete
    drift_session_end     — End session with summary

Decision: ADR-022
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


def _parse_csv_ids(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    values = [part.strip() for part in raw.split(",") if part.strip()]
    return values or None


async def _run_api_tool(tool_name: str, api_fn: Any, **kwargs: Any) -> str:
    def _sync() -> str:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = api_fn(**kwargs)
            return json.dumps(result, default=str)
        except Exception as exc:
            from drift.api_helpers import _error_response

            error = _error_response("DRIFT-5001", str(exc), recoverable=True)
            error["tool"] = tool_name
            return json.dumps(error, default=str)

    return cast(str, await _run_sync_in_thread(_sync))

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
    "5. drift_diff — detect regressions or verify completed batches\n"
    "6. drift_fix_plan — get actionable repair tasks with constraints\n"
    "7. drift_explain — understand unfamiliar signals or findings\n"
    "8. drift_nudge — fast directional feedback between edits "
    "(usable inside batches)\n\n"
    "IMPORTANT: When asked to implement a feature, add functionality, or make "
    "structural changes, call drift_brief(task=\"<task description>\") FIRST "
    "before writing any code. Use the returned guardrails as constraints "
    "in your code generation. If the scope confidence is below 0.5, ask the "
    "user to specify a --scope path.\n\n"
    "FEEDBACK LOOP ROLES:\n"
    "- drift_nudge = fast inner loop (use between edits, even inside a batch)\n"
    "- drift_diff  = full verification outer loop (use after completing a "
    "batch or before committing)\n"
    "Every response includes an 'agent_instruction' field — follow it.\n\n"
    "FIX-LOOP PROTOCOL (when fixing multiple findings):\n"
    "0. BASELINE WARM-UP: Call drift_validate, then drift_scan once to "
    "establish the nudge baseline — this avoids a costly first-nudge "
    "delay later. Keep the scan result as your session snapshot.\n"
    "1. SESSION START: Call drift_fix_plan(max_tasks=20) to see full scope. "
    "Then run 'drift baseline save' to create a checkpoint.\n"
    "2. BATCH AWARENESS: Tasks with batch_eligible=true share a fix pattern. "
    "Apply the fix to ALL affected_files_for_pattern listed, not just the "
    "first. Use drift_nudge between edits for quick direction checks.\n"
    "3. VERIFICATION: After completing a batch, call "
    "drift_diff(uncommitted=True, baseline_file='.drift-baseline.json') "
    "to verify resolution. Check resolved_count_by_rule for batch efficiency.\n"
    "4. SESSION RESUME: After interruption, call "
    "drift_diff(baseline_file='.drift-baseline.json') "
    "to see remaining work without re-scanning.\n"
    "5. COMPLETED: When drift_diff shows 0 new findings vs baseline, "
    "session is done.\n\n"
    "BATCH REPAIR MODE:\n"
    "When fixing drift findings, apply the same fix pattern across "
    "multiple files in one iteration for batch_eligible tasks.\n"
    "Rules: Only batch fixes where batch_eligible=true in fix_plan response. "
    "Apply the SAME fix template to ALL affected_files_for_pattern. "
    "Verify the batch with a single drift_diff call, not per-file. "
    "If any file in the batch fails verification, revert that file only.\n\n"
    "SESSION WORKFLOW (recommended for multi-step tasks):\n"
    "1. drift_session_start(path=\"/repo\") → session_id\n"
    "2. drift_scan(session_id=sid) → baseline warm-up (cached in session)\n"
    "3. drift_brief(session_id=sid, task=\"...\") → guardrails cached\n"
    "4. drift_fix_plan(session_id=sid) → tasks queued in session\n"
    "5. [batch fix loop with drift_nudge(session_id=sid)]\n"
    "6. drift_session_status(session_id=sid) → progress overview\n"
    "7. drift_diff(session_id=sid, uncommitted=True) → verify\n"
    "8. drift_session_end(session_id=sid) → summary + cleanup\n"
    "Benefits: scope defaults carry across calls, scan results feed into "
    "fix_plan, guardrails persist, progress is tracked automatically."
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
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'planner' (tasks/graph/phases),"
                " 'coder' (findings/actions), 'verifier' (deltas/criteria),"
                " 'merge_readiness' (score/blocking). Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start for stateful workflows."),
    ] = "",
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
        response_profile: Shape response fields for a specific agent role.
        session_id: Optional session ID for stateful workflows.
    """

    from drift.api import scan

    session = _resolve_session(session_id)
    kwargs = _session_defaults(session, {
        "path": path,
        "target_path": target_path,
        "signals": _parse_csv_ids(signals),
        "exclude_signals": _parse_csv_ids(exclude_signals),
    })

    try:
        raw = await _run_api_tool(
            "drift_scan",
            scan,
            path=kwargs["path"],
            target_path=kwargs["target_path"],
            since_days=since_days,
            signals=kwargs["signals"],
            exclude_signals=kwargs["exclude_signals"],
            max_findings=max_findings,
            max_per_signal=max_per_signal,
            response_detail=response_detail,
            include_non_operational=include_non_operational,
            response_profile=response_profile,
        )
        if session:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                _update_session_from_scan(session, json.loads(raw))
        return _enrich_response_with_session(raw, session)
    except Exception as exc:
        from drift.api_helpers import _error_response

        error = _error_response("DRIFT-5001", str(exc), recoverable=True)
        error["tool"] = "drift_scan"
        return json.dumps(error, default=str)


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
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'planner' (tasks/graph/phases),"
                " 'coder' (findings/actions), 'verifier' (deltas/criteria),"
                " 'merge_readiness' (score/blocking). Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start for stateful workflows."),
    ] = "",
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
        response_profile: Response profile (planner, coder, verifier, merge_readiness).
        session_id: Optional session ID for stateful workflows.
    """

    from drift.api import diff

    session = _resolve_session(session_id)
    kwargs = _session_defaults(session, {
        "path": path,
        "signals": _parse_csv_ids(signals),
        "exclude_signals": _parse_csv_ids(exclude_signals),
    })
    bl_file = baseline_file
    if bl_file is None and session and session.baseline_file:
        bl_file = session.baseline_file

    raw = await _run_api_tool(
        "drift_diff",
        diff,
        path=kwargs["path"],
        diff_ref=diff_ref,
        uncommitted=uncommitted,
        staged_only=staged_only,
        baseline_file=bl_file,
        max_findings=max_findings,
        response_detail=response_detail,
        signals=kwargs["signals"],
        exclude_signals=kwargs["exclude_signals"],
        response_profile=response_profile,
    )
    if session:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            _update_session_from_diff(session, json.loads(raw))
    return _enrich_response_with_session(raw, session)


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
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'planner' (tasks/graph/phases),"
                " 'coder' (findings/actions), 'verifier' (deltas/criteria),"
                " 'merge_readiness' (score/blocking). Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start for stateful workflows."),
    ] = "",
) -> str:
    """Explain a drift signal, rule, or error code.

    Use when you encounter an unfamiliar signal abbreviation (e.g. "PFS"),
    need to understand what a finding means, or want remediation guidance.

    Args:
        topic: Signal abbreviation ("PFS"), signal name
            ("pattern_fragmentation"), or error code ("DRIFT-1001").
        session_id: Optional session ID for stateful workflows.
    """

    from drift.api import explain

    session = _resolve_session(session_id)
    raw = await _run_api_tool(
        "drift_explain", explain,
        topic=topic, response_profile=response_profile,
    )
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session)


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
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'planner' (tasks/graph/phases),"
                " 'coder' (findings/actions), 'verifier' (deltas/criteria),"
                " 'merge_readiness' (score/blocking). Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start for stateful workflows."),
    ] = "",
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
        session_id: Optional session ID for stateful workflows.
    """

    from drift.api import fix_plan

    session = _resolve_session(session_id)
    kwargs = _session_defaults(session, {
        "path": path,
        "target_path": target_path,
        "signals": None,
        "exclude_signals": None,
    })

    raw = await _run_api_tool(
        "drift_fix_plan",
        fix_plan,
        path=kwargs["path"],
        signal=signal,
        max_tasks=max_tasks,
        automation_fit_min=automation_fit_min,
        target_path=kwargs["target_path"],
        exclude_paths=_parse_csv_ids(exclude_paths),
        include_deferred=include_deferred,
        include_non_operational=include_non_operational,
        response_profile=response_profile,
    )
    if session:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            _update_session_from_fix_plan(session, json.loads(raw))
    return _enrich_response_with_session(raw, session)


@mcp.tool()
async def drift_validate(
    path: Annotated[str, Field(description="Repository path to validate.")] = ".",
    config_file: Annotated[
        str | None,
        Field(description="Explicit config file path (auto-discovered from repo root if omitted)."),
    ] = None,
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'planner' (tasks/graph/phases),"
                " 'coder' (findings/actions), 'verifier' (deltas/criteria),"
                " 'merge_readiness' (score/blocking). Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start for stateful workflows."),
    ] = "",
) -> str:
    """Validate configuration and environment before running analysis.

    Use before first drift_scan or after config changes to verify
    that git is available, config is valid, and files are discoverable.

    Args:
        path: Repository path (default: current directory).
        config_file: Explicit config file path (auto-discovered if omitted).
        session_id: Optional session ID for stateful workflows.
    """

    from drift.api import validate

    session = _resolve_session(session_id)
    resolved_path = path
    if session and (not path or path == "."):
        resolved_path = session.repo_path

    raw = await _run_api_tool(
        "drift_validate",
        validate,
        path=resolved_path,
        config_file=config_file,
        response_profile=response_profile,
    )
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session)


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
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'planner' (tasks/graph/phases),"
                " 'coder' (findings/actions), 'verifier' (deltas/criteria),"
                " 'merge_readiness' (score/blocking). Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start for stateful workflows."),
    ] = "",
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
        session_id: Optional session ID for stateful workflows.
    """

    from drift.api import nudge

    session = _resolve_session(session_id)
    resolved_path = path
    if session and (not path or path == "."):
        resolved_path = session.repo_path

    raw = await _run_api_tool(
        "drift_nudge",
        nudge,
        path=resolved_path,
        changed_files=_parse_csv_ids(changed_files),
        uncommitted=uncommitted,
        response_profile=response_profile,
    )
    if session:
        try:
            result = json.loads(raw)
            score = result.get("score")
            if score is not None:
                session.last_scan_score = score
        except (json.JSONDecodeError, TypeError):
            pass
        session.touch()
    return _enrich_response_with_session(raw, session)


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
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'planner' (tasks/graph/phases),"
                " 'coder' (findings/actions), 'verifier' (deltas/criteria),"
                " 'merge_readiness' (score/blocking). Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start for stateful workflows."),
    ] = "",
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
        session_id: Optional session ID for stateful workflows.
    """

    session = _resolve_session(session_id)
    resolved_path = path
    if session and (not path or path == "."):
        resolved_path = session.repo_path

    def _sync() -> str:
        from drift.api import brief

        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = brief(
                    resolved_path,
                    task=task,
                    scope_override=scope,
                    max_guardrails=max_guardrails,
                    response_profile=response_profile,
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
    if session:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            _update_session_from_brief(session, json.loads(payload))
    return _enrich_response_with_session(payload, session)


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
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'planner' (tasks/graph/phases),"
                " 'coder' (findings/actions), 'verifier' (deltas/criteria),"
                " 'merge_readiness' (score/blocking). Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start for stateful workflows."),
    ] = "",
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
        session_id: Optional session ID for stateful workflows.
    """

    session = _resolve_session(session_id)
    resolved_path = path
    if session and (not path or path == "."):
        resolved_path = session.repo_path

    def _sync() -> str:
        from drift.api import negative_context

        kwargs: dict[str, Any] = {
            "scope": scope,
            "target_file": target_file,
            "max_items": max_items,
            "disable_embeddings": True,
        }
        # Keep backward compatibility with monkeypatched callables/tests
        # that may not accept response_profile yet.
        if response_profile is not None:
            kwargs["response_profile"] = response_profile

        # Keep MCP stdio clean if dependencies emit accidental stdout lines.
        with contextlib.redirect_stdout(io.StringIO()):
            result = negative_context(resolved_path, **kwargs)

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
        raw = cast(
            str,
            await _run_sync_with_timeout(_sync, _NEGATIVE_CONTEXT_TIMEOUT_SECONDS),
        )
        if session:
            session.touch()
        return _enrich_response_with_session(raw, session)
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


# ---------------------------------------------------------------------------
# Session helpers — resolve session defaults and enrich responses
# ---------------------------------------------------------------------------


def _resolve_session(session_id: str | None) -> Any:
    """Look up an active session. Returns ``DriftSession`` or ``None``."""
    if not session_id:
        return None
    from drift.session import SessionManager

    return SessionManager.instance().get(session_id)


def _session_defaults(session: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Apply session scope defaults for params that the caller omitted."""
    if session is None:
        return kwargs
    out = dict(kwargs)
    if not out.get("path") or out["path"] == ".":
        out["path"] = session.repo_path
    if out.get("signals") is None and session.signals:
        out["signals"] = session.signals
    if out.get("exclude_signals") is None and session.exclude_signals:
        out["exclude_signals"] = session.exclude_signals
    if out.get("target_path") is None and session.target_path:
        out["target_path"] = session.target_path
    return out


def _update_session_from_scan(session: Any, result: dict[str, Any]) -> None:
    """Push scan results into the session state."""
    if session is None:
        return
    session.last_scan_score = result.get("drift_score")
    session.last_scan_top_signals = result.get("top_signals")
    finding_count = result.get("finding_count")
    if finding_count is None:
        findings = result.get("findings")
        if isinstance(findings, list):
            finding_count = len(findings)
    session.last_scan_finding_count = finding_count
    if session.score_at_start is None:
        session.score_at_start = result.get("drift_score")
    session.touch()


def _update_session_from_fix_plan(session: Any, result: dict[str, Any]) -> None:
    """Push fix-plan tasks into the session state."""
    if session is None:
        return
    tasks = result.get("tasks")
    if tasks:
        session.selected_tasks = tasks
    session.touch()


def _update_session_from_brief(session: Any, result: dict[str, Any]) -> None:
    """Push brief guardrails into the session state."""
    if session is None:
        return
    session.guardrails = result.get("guardrails")
    session.guardrails_prompt_block = result.get("guardrails_prompt_block")
    session.touch()


def _update_session_from_diff(session: Any, result: dict[str, Any]) -> None:
    """Track score delta from diff results."""
    if session is None:
        return
    score_after = result.get("score_after")
    if score_after is not None:
        session.last_scan_score = score_after
    session.touch()


def _enrich_response_with_session(
    raw_json: str, session: Any
) -> str:
    """Inject session metadata into a tool response JSON string."""
    if session is None:
        return raw_json
    try:
        result = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return raw_json

    if not isinstance(result, dict):
        return raw_json

    result["session"] = {
        "session_id": session.session_id,
        "scope": session.scope_label(),
        "tasks_remaining": session.tasks_remaining(),
        "score_delta_since_start": (
            round(session.last_scan_score - session.score_at_start, 2)
            if session.last_scan_score is not None
            and session.score_at_start is not None
            else None
        ),
    }

    # Enrich agent_instruction with session hint
    hint = (
        f"Session {session.session_id[:8]} active"
        f" ({session.tasks_remaining()} tasks remaining)."
        " Use drift_session_status for full state."
    )
    existing = result.get("agent_instruction", "")
    if existing:
        result["agent_instruction"] = f"{existing} {hint}"
    else:
        result["agent_instruction"] = hint

    # Inject session_id into next-step contracts (ADR-024)
    sid = session.session_id
    for key in ("next_tool_call", "fallback_tool_call"):
        tc = result.get(key)
        if isinstance(tc, dict) and isinstance(tc.get("params"), dict):
            tc["params"].setdefault("session_id", sid)

    return json.dumps(result, default=str)


def _session_error_response(
    code: str, message: str, session_id: str
) -> str:
    """Build a JSON error response for session-related failures."""
    from drift.api_helpers import _error_response

    error = _error_response(code, message, recoverable=True)
    error["session_id"] = session_id
    return json.dumps(error, default=str)


# ---------------------------------------------------------------------------
# MCP Tools — Session management (v3)
# ---------------------------------------------------------------------------


@mcp.tool()
async def drift_session_start(
    path: Annotated[str, Field(description="Repository path for the session.")] = ".",
    signals: Annotated[
        str | None,
        Field(description="Comma-separated default signal filter for this session."),
    ] = None,
    exclude_signals: Annotated[
        str | None,
        Field(description="Comma-separated signals to exclude by default."),
    ] = None,
    target_path: Annotated[
        str | None,
        Field(description="Default target subdirectory for all session tools."),
    ] = None,
    exclude_paths: Annotated[
        str | None,
        Field(description="Comma-separated paths to exclude by default."),
    ] = None,
    ttl_seconds: Annotated[
        int,
        Field(description="Session time-to-live in seconds (default: 1800 = 30 min)."),
    ] = 1800,
    autopilot: Annotated[
        bool,
        Field(
            description=(
                "When true, automatically runs validate → brief → scan → fix_plan "
                "after session creation and returns combined results."
            ),
        ),
    ] = False,
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'planner', 'coder', 'verifier', "
                "'merge_readiness', or null for full response."
            ),
        ),
    ] = None,
) -> str:
    """Start a new stateful session for multi-step agent workflows.

    Creates a session that persists scope defaults, scan results,
    fix-plan tasks, and guardrails across subsequent tool calls.
    Pass the returned session_id to other drift tools.

    When autopilot=true, automatically runs validate → brief → scan →
    fix_plan after session creation. The combined results are returned
    in a single response, saving 4 round-trips.

    Args:
        path: Repository path (default: current directory).
        signals: Comma-separated default signal filter.
        exclude_signals: Comma-separated signals to exclude.
        target_path: Default target subdirectory.
        exclude_paths: Comma-separated paths to exclude.
        ttl_seconds: Session TTL in seconds (default: 1800).
        autopilot: Run validate → brief → scan → fix_plan automatically.
        response_profile: Shape sub-results for a specific agent role.
    """
    from drift.session import SessionManager

    mgr = SessionManager.instance()
    session_id = mgr.create(
        repo_path=str(Path(path).resolve()),
        signals=_parse_csv_ids(signals),
        exclude_signals=_parse_csv_ids(exclude_signals),
        target_path=target_path,
        exclude_paths=_parse_csv_ids(exclude_paths),
        ttl_seconds=ttl_seconds,
    )
    session = mgr.get(session_id)
    result = {
        "status": "ok",
        "session_id": session_id,
        "repo_path": str(Path(path).resolve()),
        "scope": session.scope_label() if session else "all",
        "ttl_seconds": ttl_seconds,
        "created_at": session.created_at if session else None,
        "agent_instruction": (
            f"Session {session_id[:8]} created. Pass session_id=\"{session_id}\" "
            "to subsequent drift tools to use session defaults and track state. "
            "Recommended next: drift_validate, then drift_scan with this session_id."
        ),
        "recommended_next_actions": [
            f"drift_validate(session_id=\"{session_id}\")",
            f"drift_scan(session_id=\"{session_id}\")",
        ],
        "next_tool_call": {
            "tool": "drift_scan",
            "params": {"session_id": session_id},
        },
        "fallback_tool_call": {
            "tool": "drift_validate",
            "params": {"session_id": session_id},
        },
        "done_when": "session.tasks_remaining == 0",
    }

    # ADR-025 Phase D: Session autopilot
    if autopilot:
        from drift.api import brief, fix_plan, scan, validate

        loop = asyncio.get_event_loop()
        resolved = str(Path(path).resolve())
        sig_list = _parse_csv_ids(signals) or None
        excl_sig_list = _parse_csv_ids(exclude_signals) or None
        excl_paths = _parse_csv_ids(exclude_paths) or None

        val_result = await loop.run_in_executor(
            None,
            lambda: validate(
                path=resolved,
                response_profile=response_profile,
            ),
        )
        brief_result = await loop.run_in_executor(
            None,
            lambda: brief(
                path=resolved,
                task="autopilot session start",
                signals=sig_list,
                response_profile=response_profile,
            ),
        )
        scan_result = await loop.run_in_executor(
            None,
            lambda: scan(
                path=resolved,
                signals=sig_list,
                exclude_signals=excl_sig_list,
                target_path=target_path,
                response_profile=response_profile,
            ),
        )
        fp_result = await loop.run_in_executor(
            None,
            lambda: fix_plan(
                path=resolved,
                target_path=target_path,
                exclude_paths=excl_paths,
                response_profile=response_profile,
            ),
        )
        result["autopilot"] = {
            "validate": val_result,
            "brief": brief_result,
            "scan": scan_result,
            "fix_plan": fp_result,
        }
        result["agent_instruction"] = (
            f"Session {session_id[:8]} created with autopilot. "
            "Validate, brief, scan, and fix_plan already executed — "
            "results included in autopilot field. Proceed to fix tasks."
        )
        result["next_tool_call"] = {
            "tool": "drift_fix_plan",
            "params": {"session_id": session_id},
        }

    return json.dumps(result, default=str)


@mcp.tool()
async def drift_session_status(
    session_id: Annotated[
        str, Field(description="The session ID returned by drift_session_start.")
    ],
) -> str:
    """Show the current state of an active session.

    Returns scope, last scan results, task queue progress, active
    guardrails, and TTL information.

    Args:
        session_id: The session ID to query.
    """
    from drift.session import SessionManager

    session = SessionManager.instance().get(session_id)
    if session is None:
        return _session_error_response(
            "DRIFT-6001",
            f"Session {session_id[:8]} not found or expired.",
            session_id,
        )

    result = session.summary()
    result["status"] = "ok"
    result["agent_instruction"] = (
        f"Session {session_id[:8]} is active"
        f" with {session.tasks_remaining()} tasks remaining."
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def drift_session_update(
    session_id: Annotated[
        str, Field(description="The session ID to update.")
    ],
    signals: Annotated[
        str | None,
        Field(description="New signal filter (replaces current). Omit to keep."),
    ] = None,
    exclude_signals: Annotated[
        str | None,
        Field(description="New exclude filter (replaces current). Omit to keep."),
    ] = None,
    target_path: Annotated[
        str | None,
        Field(description="New target path. Omit to keep current."),
    ] = None,
    mark_tasks_complete: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated task IDs to mark as completed"
                " in the session's fix-plan queue."
            ),
        ),
    ] = None,
    save_to_disk: Annotated[
        bool, Field(description="Persist session to .drift-session-{id}.json.")
    ] = False,
) -> str:
    """Update session scope, mark tasks complete, or save to disk.

    Args:
        session_id: The session ID to update.
        signals: New signal filter (replaces current).
        exclude_signals: New exclude filter (replaces current).
        target_path: New target path.
        mark_tasks_complete: Comma-separated task IDs to mark complete.
        save_to_disk: Persist session to a JSON file.
    """
    from drift.session import SessionManager

    mgr = SessionManager.instance()
    session = mgr.get(session_id)
    if session is None:
        return _session_error_response(
            "DRIFT-6001",
            f"Session {session_id[:8]} not found or expired.",
            session_id,
        )

    updates: dict[str, Any] = {}
    if signals is not None:
        updates["signals"] = _parse_csv_ids(signals)
    if exclude_signals is not None:
        updates["exclude_signals"] = _parse_csv_ids(exclude_signals)
    if target_path is not None:
        updates["target_path"] = target_path

    if mark_tasks_complete:
        task_ids = _parse_csv_ids(mark_tasks_complete) or []
        existing = list(session.completed_task_ids)
        existing.extend(tid for tid in task_ids if tid not in existing)
        updates["completed_task_ids"] = existing

    if updates:
        mgr.update(session_id, **updates)

    saved_path: str | None = None
    if save_to_disk:
        disk_path = mgr.save_to_disk(session_id)
        saved_path = str(disk_path) if disk_path else None

    result = session.summary()
    result["status"] = "ok"
    if saved_path:
        result["saved_to"] = saved_path
    result["agent_instruction"] = (
        f"Session {session_id[:8]} updated. Scope: {session.scope_label()}."
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def drift_session_end(
    session_id: Annotated[
        str, Field(description="The session ID to end.")
    ],
) -> str:
    """End a session and return a final summary.

    Destroys the session and returns duration, score delta, and
    task completion statistics.

    Args:
        session_id: The session ID to end.
    """
    from drift.session import SessionManager

    summary = SessionManager.instance().destroy(session_id)
    if summary is None:
        return _session_error_response(
            "DRIFT-6001",
            f"Session {session_id[:8]} not found or already ended.",
            session_id,
        )

    summary["status"] = "ok"
    summary["agent_instruction"] = (
        f"Session {session_id[:8]} ended. "
        f"Duration: {summary.get('duration_seconds', 0)}s, "
        f"tool calls: {summary.get('tool_calls', 0)}."
    )
    return json.dumps(summary, default=str)


# ---------------------------------------------------------------------------
# MCP Tools — Task-queue leasing (multi-agent coordination)
# ---------------------------------------------------------------------------


@mcp.tool()
async def drift_task_claim(
    session_id: Annotated[
        str, Field(description="Active session ID from drift_session_start.")
    ],
    agent_id: Annotated[
        str,
        Field(
            description=(
                "Unique identifier for the calling agent or role"
                " (e.g. 'agent-a', 'fixer')."
            )
        ),
    ],
    task_id: Annotated[
        str | None,
        Field(
            description=(
                "Specific task ID to claim. If omitted, the next FIFO"
                " pending task is claimed."
            ),
        ),
    ] = None,
    lease_ttl_seconds: Annotated[
        int,
        Field(
            description=(
                "Lease lifetime in seconds before the task reverts to pending"
                " (default: 300)."
            )
        ),
    ] = 300,
    max_reclaim: Annotated[
        int,
        Field(
            description=(
                "Maximum times a task may be reclaimed before being marked"
                " failed (default: 3)."
            )
        ),
    ] = 3,
) -> str:
    """Claim a pending task from the session's fix-plan queue.

    Atomically acquires a lease on the next pending task (FIFO) or a
    specific task by ID.  While a task is claimed, other agents cannot
    claim the same task.  The lease expires after ``lease_ttl_seconds``;
    use drift_task_renew to extend it before expiry.

    Requires an active session with tasks loaded via drift_fix_plan.

    Args:
        session_id: Active session ID from drift_session_start.
        agent_id: Unique identifier for the calling agent or role.
        task_id: Specific task ID to claim (FIFO if omitted).
        lease_ttl_seconds: Lease lifetime before task reverts (default: 300s).
        max_reclaim: Max reclaims before task is marked failed (default: 3).
    """
    from drift.session import SessionManager

    session = SessionManager.instance().get(session_id)
    if session is None:
        return _session_error_response(
            "DRIFT-6001",
            f"Session {session_id[:8]} not found or expired.",
            session_id,
        )

    claim = session.claim_task(
        agent_id=agent_id,
        task_id=task_id or None,
        lease_ttl_seconds=lease_ttl_seconds,
        max_reclaim=max_reclaim,
    )
    if claim is None:
        q = session.queue_status()
        result: dict[str, Any] = {
            "status": "no_tasks_available",
            "session_id": session_id,
            "pending_count": q["pending_count"],
            "claimed_count": q["claimed_count"],
            "completed_count": q["completed_count"],
            "failed_count": q["failed_count"],
            "agent_instruction": (
                "No pending tasks available in this session."
                " All tasks may be claimed, completed, or failed."
                " Call drift_task_status for a full queue overview."
            ),
        }
        return json.dumps(result, default=str)

    task_dict = claim["task"]
    lease_dict = claim["lease"]
    result = {
        "status": "claimed",
        "session_id": session_id,
        "task": task_dict,
        "lease": lease_dict,
        "agent_instruction": (
            f"Task {lease_dict['task_id']} claimed by {agent_id}."
            f" Lease expires in {lease_ttl_seconds}s."
            " Call drift_task_renew before expiry if more time is needed."
            " Call drift_task_complete when done, or drift_task_release to"
            " return the task to the pending pool."
        ),
    }
    return json.dumps(result, default=str)


@mcp.tool()
async def drift_task_renew(
    session_id: Annotated[
        str, Field(description="Active session ID from drift_session_start.")
    ],
    agent_id: Annotated[
        str, Field(description="Agent ID that holds the current lease.")
    ],
    task_id: Annotated[
        str, Field(description="Task ID to extend the lease for.")
    ],
    extend_seconds: Annotated[
        int,
        Field(description="Seconds to add to the current lease deadline (default: 300)."),
    ] = 300,
) -> str:
    """Extend an active task lease to prevent it from expiring.

    Call this while still working on a claimed task if the original
    ``lease_ttl_seconds`` is about to expire.  Only the agent that holds
    the lease can renew it.

    Args:
        session_id: Active session ID from drift_session_start.
        agent_id: Agent ID that holds the current lease.
        task_id: Task ID whose lease should be extended.
        extend_seconds: Seconds to add to the current deadline (default: 300s).
    """
    from drift.session import SessionManager

    session = SessionManager.instance().get(session_id)
    if session is None:
        return _session_error_response(
            "DRIFT-6001",
            f"Session {session_id[:8]} not found or expired.",
            session_id,
        )

    outcome = session.renew_lease(
        agent_id=agent_id,
        task_id=task_id,
        extend_seconds=extend_seconds,
    )
    status = outcome.get("status", "not_found")
    if status == "renewed":
        outcome["session_id"] = session_id
        outcome["agent_instruction"] = (
            f"Lease for task {task_id} extended by {extend_seconds}s."
        )
    else:
        outcome["session_id"] = session_id
        outcome["agent_instruction"] = (
            outcome.get("error", "Renewal failed.")
            + " Call drift_task_status for current queue state."
        )
    return json.dumps(outcome, default=str)


@mcp.tool()
async def drift_task_release(
    session_id: Annotated[
        str, Field(description="Active session ID from drift_session_start.")
    ],
    agent_id: Annotated[
        str, Field(description="Agent ID that holds the current lease.")
    ],
    task_id: Annotated[
        str, Field(description="Task ID to release back to the pending pool.")
    ],
    max_reclaim: Annotated[
        int,
        Field(
            description=(
                "Maximum reclaim count before the task is marked failed"
                " (default: 3)."
            )
        ),
    ] = 3,
) -> str:
    """Release a claimed task back to the pending pool.

    Use this when a task cannot be completed (e.g. blocked, out of scope).
    The task's reclaim count is incremented; after ``max_reclaim`` releases
    the task is marked as failed instead of re-queued.

    Args:
        session_id: Active session ID from drift_session_start.
        agent_id: Agent ID that holds the current lease.
        task_id: Task ID to release.
        max_reclaim: Max releases before marking failed (default: 3).
    """
    from drift.session import SessionManager

    session = SessionManager.instance().get(session_id)
    if session is None:
        return _session_error_response(
            "DRIFT-6001",
            f"Session {session_id[:8]} not found or expired.",
            session_id,
        )

    outcome = session.release_task(
        agent_id=agent_id,
        task_id=task_id,
        max_reclaim=max_reclaim,
    )
    state = outcome.get("status", "released")
    if state == "released":
        agent_instruction = (
            f"Task {task_id} released back to the pending pool"
            f" (reclaim count: {outcome.get('reclaim_count', 0)})."
            " Another agent can now claim it."
        )
    elif state == "failed":
        agent_instruction = (
            f"Task {task_id} has reached max_reclaim={max_reclaim}"
            " and is now marked as failed. It will not be re-queued."
        )
    else:
        agent_instruction = (
            outcome.get("error", "Release failed.")
            + " Call drift_task_status for current queue state."
        )
    outcome["session_id"] = session_id
    outcome["agent_instruction"] = agent_instruction
    return json.dumps(outcome, default=str)


@mcp.tool()
async def drift_task_complete(
    session_id: Annotated[
        str, Field(description="Active session ID from drift_session_start.")
    ],
    agent_id: Annotated[
        str, Field(description="Agent ID that holds the lease for this task.")
    ],
    task_id: Annotated[
        str, Field(description="Task ID to mark as completed.")
    ],
) -> str:
    """Mark a claimed task as completed and release its lease.

    Only the agent holding the active lease can complete the task.
    Completed tasks are excluded from future drift_task_claim calls.

    Args:
        session_id: Active session ID from drift_session_start.
        agent_id: Agent ID that holds the lease.
        task_id: Task ID to mark as completed.
    """
    from drift.session import SessionManager

    session = SessionManager.instance().get(session_id)
    if session is None:
        return _session_error_response(
            "DRIFT-6001",
            f"Session {session_id[:8]} not found or expired.",
            session_id,
        )

    outcome = session.complete_task(agent_id=agent_id, task_id=task_id)
    state = outcome.get("status", "completed")
    if state == "completed":
        remaining = session.tasks_remaining()
        agent_instruction = (
            f"Task {task_id} completed. {remaining} task(s) remaining."
        )
        if remaining == 0:
            agent_instruction += (
                " All tasks done — call drift_session_end for final summary."
            )
    elif state == "already_completed":
        agent_instruction = f"Task {task_id} was already completed."
    else:
        agent_instruction = (
            outcome.get("error", "Completion failed.")
            + " Call drift_task_status for current queue state."
        )
    outcome["session_id"] = session_id
    outcome["tasks_remaining"] = session.tasks_remaining()
    outcome["agent_instruction"] = agent_instruction
    return json.dumps(outcome, default=str)


@mcp.tool()
async def drift_task_status(
    session_id: Annotated[
        str, Field(description="Active session ID from drift_session_start.")
    ],
) -> str:
    """Return a full queue overview: pending, claimed, completed, failed tasks.

    Use this to understand the current distribution of work across agents
    and to decide which tasks still need attention.

    Args:
        session_id: Active session ID from drift_session_start.
    """
    from drift.session import SessionManager

    session = SessionManager.instance().get(session_id)
    if session is None:
        return _session_error_response(
            "DRIFT-6001",
            f"Session {session_id[:8]} not found or expired.",
            session_id,
        )

    status = session.queue_status()
    status["session_id"] = session_id
    status["tasks_remaining"] = session.tasks_remaining()
    pending = status.get("pending_count", 0)
    claimed = status.get("claimed_count", 0)
    completed = status.get("completed_count", 0)
    failed = status.get("failed_count", 0)
    status["agent_instruction"] = (
        f"Queue: {pending} pending, {claimed} claimed,"
        f" {completed} completed, {failed} failed."
        + (
            " All tasks done — call drift_session_end."
            if pending == 0 and claimed == 0 and completed > 0
            else ""
        )
    )
    return json.dumps(status, default=str)


_EXPORTED_MCP_TOOLS = (
    drift_scan,
    drift_diff,
    drift_explain,
    drift_fix_plan,
    drift_validate,
    drift_nudge,
    drift_brief,
    drift_negative_context,
    drift_session_start,
    drift_session_status,
    drift_session_update,
    drift_session_end,
    drift_task_claim,
    drift_task_renew,
    drift_task_release,
    drift_task_complete,
    drift_task_status,
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


def _field_description_from_annotation(annotation: Any) -> str | None:
    """Extract Field(description=...) from typing.Annotated metadata when present."""
    import typing

    if typing.get_origin(annotation) is not typing.Annotated:
        return None

    args = typing.get_args(annotation)
    for meta in args[1:]:
        description = getattr(meta, "description", None)
        if isinstance(description, str) and description.strip():
            return description.strip()
    return None


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
            else:
                field_desc = _field_description_from_annotation(annotation)
                if field_desc:
                    parameter_info["description"] = field_desc
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
