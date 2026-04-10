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
import io
import json
import os
from pathlib import Path
from typing import Annotated, Any, cast

from drift.mcp_catalog import get_tool_catalog  # noqa: F401

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


def _can_use_session_fix_plan_fast_path(
    *,
    session: Any,
    path: str,
    signal: str | None,
    automation_fit_min: str | None,
    target_path: str | None,
    exclude_paths: list[str] | None,
    include_deferred: bool,
    include_non_operational: bool,
    response_profile: str | None,
) -> bool:
    """Return True when drift_fix_plan can be served from session queue state."""
    if session is None or not session.selected_tasks:
        return False
    if path not in ("", "."):
        return False
    if signal is not None:
        return False
    if automation_fit_min is not None:
        return False
    if target_path is not None:
        return False
    if exclude_paths:
        return False
    if include_deferred:
        return False
    if include_non_operational:
        return False
    return response_profile is None


def _session_fix_plan_fast_response(session: Any, *, max_tasks: int) -> dict[str, Any]:
    """Build a fix-plan response directly from the session task queue."""
    queue = session.queue_status()
    pending_ids = [
        task.get("id")
        for task in queue.get("pending_tasks", [])
        if isinstance(task, dict) and task.get("id")
    ]

    selected_tasks = session.selected_tasks or []
    task_by_id = {
        str(task.get("id", task.get("task_id", ""))): task
        for task in selected_tasks
        if isinstance(task, dict)
    }
    pending_tasks = [
        task_by_id[str(task_id)]
        for task_id in pending_ids
        if str(task_id) in task_by_id
    ]

    limit = max(0, max_tasks)
    limited = pending_tasks[:limit]
    remaining = pending_tasks[len(limited):]

    remaining_by_signal: dict[str, int] = {}
    for task in remaining:
        signal = str(task.get("signal", "UNKNOWN"))
        remaining_by_signal[signal] = remaining_by_signal.get(signal, 0) + 1

    response = {
        "status": "ok",
        "drift_score": round(float(session.last_scan_score), 3)
        if session.last_scan_score is not None
        else None,
        "drift_score_scope": "context:fix-plan,signals:session,path:session-default",
        "tasks": limited,
        "task_count": len(limited),
        "total_available": len(pending_tasks),
        "remaining_by_signal": remaining_by_signal,
        "recommended_next_actions": [
            "drift_nudge after each fix for fast directional feedback",
            "drift_diff(uncommitted=True) before final accept/commit",
        ],
        "agent_instruction": (
            "Served fix-plan from session task queue cache (no full re-analysis). "
            "Call drift_nudge after applying the selected task, then request the next "
            "task with drift_fix_plan(max_tasks=1)."
        ),
        "next_tool_call": {
            "tool": "drift_nudge",
        },
        "fallback_tool_call": {
            "tool": "drift_diff",
            "params": {"uncommitted": True},
        },
        "done_when": "accept_change == true OR (drift_detected == false AND score_delta <= 0)",
        "cache": {
            "hit": True,
            "source": "session.fix_plan_queue",
        },
    }
    return response


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
    "0. SESSION START: Call drift_session_start(path=\".\", autopilot=true) "
    "— this single call runs validate → brief → scan → fix_plan and "
    "returns combined results, saving 4 round-trips.\n"
    "1. TASK LOOP: Take the first task from the fix_plan result. Fix it. "
    "Call drift_nudge(session_id=sid, changed_files=\"path/to/file.py\") "
    "for fast feedback (~0.2s). If direction=degrading, revert and retry.\n"
    "2. NEXT TASK: Call drift_fix_plan(session_id=sid, max_tasks=1) to get "
    "the next task. Repeat step 1.\n"
    "3. BATCH AWARENESS: Tasks with batch_eligible=true share a fix pattern. "
    "Apply the fix to ALL affected_files_for_pattern listed, not just the "
    "first. Use drift_nudge between edits for quick direction checks.\n"
    "4. VERIFICATION: After all tasks are done, call "
    "drift_diff(session_id=sid, uncommitted=True) once to verify.\n"
    "5. COMPLETED: When drift_diff shows 0 new findings, session is done.\n\n"
    "CRITICAL RULES:\n"
    "- Always use autopilot=true in session_start (saves 4 round-trips)\n"
    "- Always pass session_id to every tool call\n"
    "- In the fix loop, use max_tasks=1 for each subsequent task request. "
    "For the initial overview, follow the max_tasks value from the scan "
    "agent_instruction (autopilot handles this automatically).\n"
    "- Use drift_nudge (not drift_scan) after each file edit\n"
    "- Use drift_diff only once at the end, not after every edit\n"
    "- Follow agent_instruction and next_tool_call from every response\n\n"
    "BATCH REPAIR MODE:\n"
    "When fixing drift findings, apply the same fix pattern across "
    "multiple files in one iteration for batch_eligible tasks.\n"
    "Rules: Only batch fixes where batch_eligible=true in fix_plan response. "
    "Apply the SAME fix template to ALL affected_files_for_pattern. "
    "Verify the batch with a single drift_diff call, not per-file. "
    "If any file in the batch fails verification, revert that file only.\n\n"
    "SESSION WORKFLOW (recommended for multi-step tasks):\n"
    "1. drift_session_start(path=\".\", autopilot=true) → session_id "
    "(runs validate+brief+scan+fix_plan automatically)\n"
    "2. [fix loop: edit file → drift_nudge(session_id=sid) → check direction]\n"
    "3. drift_fix_plan(session_id=sid, max_tasks=1) → next task\n"
    "4. drift_diff(session_id=sid, uncommitted=True) → final verify\n"
    "5. drift_session_end(session_id=sid) → summary + cleanup\n"
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
        return _enrich_response_with_session(raw, session, "drift_scan")
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
    hypothesis_id: Annotated[
        str | None,
        Field(
            description=(
                "Diagnostic hypothesis ID to link this verification result "
                "to the underlying cause/change hypothesis."
            ),
        ),
    ] = None,
    diagnostic_hypothesis: Annotated[
        Any,
        Field(
            description=(
                "Optional full diagnostic hypothesis payload. Required in batch-fix "
                "context if no hypothesis_id is provided. Must include: "
                "affected_files, suspected_root_cause, minimal_intended_change, non_goals."
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
        hypothesis_id: Existing diagnostic hypothesis ID for trace linkage.
        diagnostic_hypothesis: Full hypothesis payload (cause/change/non-goals).
        session_id: Optional session ID for stateful workflows.
    """

    from drift.api import diff

    session = _resolve_session(session_id)
    blocked = _strict_guardrail_block_response("drift_diff", session)
    if blocked is not None:
        return blocked
    hypothesis_ctx = _resolve_diagnostic_hypothesis_context(
        tool_name="drift_diff",
        session=session,
        hypothesis_id=hypothesis_id,
        diagnostic_hypothesis=diagnostic_hypothesis,
    )
    if hypothesis_ctx.get("blocked_response"):
        return cast(str, hypothesis_ctx["blocked_response"])
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
    with contextlib.suppress(json.JSONDecodeError, TypeError):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            h_id = cast(str | None, hypothesis_ctx.get("hypothesis_id"))
            if h_id:
                parsed["hypothesis_id"] = h_id
                parsed["verification_evidence"] = {
                    "tool": "drift_diff",
                    "accept_change": parsed.get("accept_change"),
                    "blocking_reasons": parsed.get("blocking_reasons", []),
                }
                raw = json.dumps(parsed, default=str)
    return _enrich_response_with_session(
        raw,
        session,
        "drift_diff",
        trace_meta=_trace_meta_from_hypothesis_result("drift_diff", raw),
    )


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
        response_profile: Response profile ('planner', 'coder', 'verifier',
            'merge_readiness'). Omit for full response.
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
    return _enrich_response_with_session(raw, session, "drift_explain")


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
    blocked = _strict_guardrail_block_response("drift_fix_plan", session)
    if blocked is not None:
        return blocked
    parsed_exclude_paths = _parse_csv_ids(exclude_paths)

    if _can_use_session_fix_plan_fast_path(
        session=session,
        path=path,
        signal=signal,
        automation_fit_min=automation_fit_min,
        target_path=target_path,
        exclude_paths=parsed_exclude_paths,
        include_deferred=include_deferred,
        include_non_operational=include_non_operational,
        response_profile=response_profile,
    ):
        cached_result = _session_fix_plan_fast_response(session, max_tasks=max_tasks)
        _update_session_from_fix_plan(session, cached_result)
        return _enrich_response_with_session(
            json.dumps(cached_result, default=str),
            session,
            "drift_fix_plan",
        )

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
        exclude_paths=parsed_exclude_paths,
        include_deferred=include_deferred,
        include_non_operational=include_non_operational,
        response_profile=response_profile,
    )
    if session:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            _update_session_from_fix_plan(session, json.loads(raw))
    return _enrich_response_with_session(raw, session, "drift_fix_plan")


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
        # Inject session-based progress when score history is available
        if session.score_at_start is not None and session.last_scan_score is not None:
            try:
                parsed = json.loads(raw)
                parsed["session_progress"] = {
                    "score_at_start": session.score_at_start,
                    "last_scan_score": session.last_scan_score,
                    "score_delta": round(
                        session.last_scan_score - session.score_at_start, 2
                    ),
                    "tasks_total": len(session.selected_tasks or []),
                    "tasks_completed": len(session.completed_task_ids),
                    "tasks_remaining": session.tasks_remaining(),
                }
                raw = json.dumps(parsed, indent=2)
            except (json.JSONDecodeError, TypeError):
                pass  # non-JSON response, skip enrichment
    return _enrich_response_with_session(raw, session, "drift_validate")


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
    hypothesis_id: Annotated[
        str | None,
        Field(
            description=(
                "Diagnostic hypothesis ID to link this nudge result "
                "to the underlying cause/change hypothesis."
            ),
        ),
    ] = None,
    diagnostic_hypothesis: Annotated[
        Any,
        Field(
            description=(
                "Optional full diagnostic hypothesis payload. Required in batch-fix "
                "context if no hypothesis_id is provided. Must include: "
                "affected_files, suspected_root_cause, minimal_intended_change, non_goals."
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
        hypothesis_id: Existing diagnostic hypothesis ID for trace linkage.
        diagnostic_hypothesis: Full hypothesis payload (cause/change/non-goals).
        session_id: Optional session ID for stateful workflows.
    """

    from drift.api import nudge

    session = _resolve_session(session_id)
    blocked = _strict_guardrail_block_response("drift_nudge", session)
    if blocked is not None:
        return blocked
    hypothesis_ctx = _resolve_diagnostic_hypothesis_context(
        tool_name="drift_nudge",
        session=session,
        hypothesis_id=hypothesis_id,
        diagnostic_hypothesis=diagnostic_hypothesis,
    )
    if hypothesis_ctx.get("blocked_response"):
        return cast(str, hypothesis_ctx["blocked_response"])
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
    with contextlib.suppress(json.JSONDecodeError, TypeError):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            h_id = cast(str | None, hypothesis_ctx.get("hypothesis_id"))
            if h_id:
                parsed["hypothesis_id"] = h_id
                parsed["verification_evidence"] = {
                    "tool": "drift_nudge",
                    "safe_to_commit": parsed.get("safe_to_commit"),
                    "blocking_reasons": parsed.get("blocking_reasons", []),
                    "changed_files": parsed.get("changed_files", []),
                }
                raw = json.dumps(parsed, default=str)
    return _enrich_response_with_session(
        raw,
        session,
        "drift_nudge",
        trace_meta=_trace_meta_from_hypothesis_result("drift_nudge", raw),
    )


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
        return _enrich_response_with_session(raw, session, "drift_negative_context")
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
# Session orchestration, guardrails, enrichment — delegated to submodules
# ---------------------------------------------------------------------------
from drift.mcp_enrichment import (  # noqa: E402
    _enrich_response_with_session,
    _session_error_response,
)
from drift.mcp_orchestration import (  # noqa: E402
    _effective_profile,  # noqa: F401
    _pre_call_advisory,  # noqa: F401
    _resolve_diagnostic_hypothesis_context,
    _resolve_session,
    _session_defaults,
    _strict_guardrail_block_response,
    _trace_meta_from_hypothesis_result,
    _update_session_from_brief,
    _update_session_from_diff,
    _update_session_from_fix_plan,
    _update_session_from_scan,
    _update_session_from_verification_result,  # noqa: F401
)

# Keep legacy re-exports visible to static analyzers and test imports.
_MCP_SERVER_LEGACY_REEXPORTS = (
    _effective_profile,
    _update_session_from_verification_result,
)

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
        from drift.analyzer import analyze_repo
        from drift.api import brief, validate
        from drift.api._config import _load_config_cached, _warn_config_issues
        from drift.api.fix_plan import _build_fix_plan_response_from_analysis
        from drift.api.scan import _format_scan_response
        from drift.api_helpers import build_drift_score_scope, shape_for_profile, signal_scope_label
        from drift.config import apply_signal_filter, resolve_signal_names

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
        def _scan_and_fixplan_from_shared_analysis() -> tuple[dict[str, Any], dict[str, Any]]:
            repo_path = Path(resolved)
            cfg = _load_config_cached(repo_path)
            cfg_warnings = _warn_config_issues(cfg)

            warnings: list[str] = list(cfg_warnings)
            if target_path and not (repo_path / target_path).exists():
                warnings.append(
                    f"target_path '{target_path}' does not exist in repository"
                )

            active_signals: set[str] | None = None
            select_csv = ",".join(sig_list) if sig_list else None
            ignore_csv = ",".join(excl_sig_list) if excl_sig_list else None
            if select_csv or ignore_csv:
                apply_signal_filter(cfg, select_csv, ignore_csv)
                if select_csv:
                    active_signals = set(resolve_signal_names(select_csv))

            analysis = analyze_repo(
                repo_path,
                config=cfg,
                since_days=90,
                target_path=target_path,
                active_signals=active_signals,
            )

            scan_result = _format_scan_response(
                analysis,
                config=cfg,
                max_findings=10,
                max_per_signal=None,
                detail="concise",
                strategy="diverse",
                signal_filter=set(s.upper() for s in sig_list) if sig_list else None,
                include_non_operational=False,
                drift_score_scope=build_drift_score_scope(
                    context="repo",
                    path=target_path,
                    signal_scope=signal_scope_label(selected=sig_list),
                ),
            )
            if warnings:
                scan_result["warnings"] = list(warnings)

            fix_plan_result = _build_fix_plan_response_from_analysis(
                analysis=analysis,
                cfg=cfg,
                repo_path=repo_path,
                finding_id=None,
                signal=None,
                max_tasks=5,
                automation_fit_min=None,
                target_path=target_path,
                exclude_paths=excl_paths,
                include_deferred=False,
                include_non_operational=False,
                warnings=list(warnings),
            )
            return (
                shape_for_profile(scan_result, response_profile),
                shape_for_profile(fix_plan_result, response_profile),
            )

        scan_result, fp_result = await loop.run_in_executor(
            None,
            _scan_and_fixplan_from_shared_analysis,
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

    session = SessionManager.instance().get(session_id)
    if session is not None:
        blocked = _strict_guardrail_block_response("drift_session_end", session)
        if blocked is not None:
            return blocked

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


@mcp.tool()
async def drift_session_trace(
    session_id: Annotated[
        str, Field(description="Active session ID from drift_session_start.")
    ],
    last_n: Annotated[
        int, Field(description="Number of most recent trace entries to return.")
    ] = 20,
) -> str:
    """Return the session trace log — a chronological record of tool calls.

    Use this to review the sequence of actions taken during the session,
    including phase transitions, advisories, and timing.

    Args:
        session_id: Active session ID from drift_session_start.
        last_n: Number of recent entries (default: 20).
    """
    from drift.session import SessionManager

    session = SessionManager.instance().get(session_id)
    if session is None:
        return _session_error_response(
            "DRIFT-6001",
            f"Session {session_id[:8]} not found or expired.",
            session_id,
        )

    session_trace = getattr(session, "trace", [])
    session_phase = getattr(session, "phase", "unknown")
    entries = session_trace[-last_n:] if last_n > 0 else session_trace
    result: dict[str, Any] = {
        "session_id": session_id,
        "total_entries": len(session_trace),
        "returned_entries": len(entries),
        "trace": entries,
        "current_phase": session_phase,
        "agent_instruction": (
            f"Trace contains {len(session_trace)} entries."
            f" Session phase: {session_phase}."
        ),
    }
    return json.dumps(result, default=str)


@mcp.tool()
async def drift_map(
    path: Annotated[str, Field(description="Repository path to map.")] = ".",
    target_path: Annotated[
        str | None,
        Field(description="Optional subpath scope inside repository."),
    ] = None,
    max_modules: Annotated[
        int,
        Field(description="Maximum number of modules to return."),
    ] = 50,
    session_id: Annotated[
        str | None,
        Field(description="Optional session ID for context enrichment."),
    ] = None,
) -> str:
    """Return a lightweight module/dependency architecture map.

    Args:
        path: Repository path to map.
        target_path: Optional subpath scope inside repository.
        max_modules: Maximum number of modules to return.
        session_id: Optional session ID for context enrichment.
    """
    from drift.api import drift_map as api_drift_map

    session = _resolve_session(session_id)
    kwargs = _session_defaults(session, {"path": path, "target_path": target_path})

    try:
        result = await _run_sync_in_thread(
            lambda: api_drift_map(
                kwargs.get("path", path),
                target_path=kwargs.get("target_path"),
                max_modules=max_modules,
            )
        )
        raw = json.dumps(result, default=str)
        if session is not None:
            raw = _enrich_response_with_session(raw, session, "drift_map")
        return raw
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {
                "type": "error",
                "error_code": "DRIFT-7001",
                "message": str(exc),
                "recoverable": True,
            },
            default=str,
        )


# ---------------------------------------------------------------------------
# Calibration tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def drift_feedback(
    signal: Annotated[
        str,
        Field(description="Signal type or abbreviation (e.g. 'PFS', 'pattern_fragmentation')."),
    ],
    file_path: Annotated[
        str,
        Field(description="File path the finding relates to."),
    ],
    verdict: Annotated[
        str,
        Field(
            description=(
                "Feedback verdict: 'tp' (true positive),"
                " 'fp' (false positive), or 'fn' (false negative)."
            ),
        ),
    ],
    reason: Annotated[
        str,
        Field(description="Optional reason for the verdict."),
    ] = "",
    start_line: Annotated[
        int,
        Field(description="Start line of the finding for line-precise feedback (0 = not set)."),
    ] = 0,
    path: Annotated[
        str,
        Field(description="Repository path."),
    ] = ".",
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start."),
    ] = "",
) -> str:
    """Record TP/FP/FN feedback for a finding to improve signal calibration.

    Use when you or an agent determines that a drift finding was correct (tp),
    incorrect (fp), or missed (fn). Feedback accumulates and can be used by
    ``drift_calibrate`` to adjust signal weights per repository.

    Args:
        signal: Signal type or abbreviation (e.g. 'PFS').
        file_path: File path the finding relates to.
        verdict: 'tp', 'fp', or 'fn'.
        reason: Optional reason for the verdict.
        start_line: Start line of the finding (0 means not set).
        path: Repository path.
        session_id: Optional session ID for stateful workflows.
    """
    from pathlib import Path as _Path

    from drift.calibration.feedback import FeedbackEvent, record_feedback
    from drift.config import SIGNAL_ABBREV, DriftConfig

    session = _resolve_session(session_id)

    def _sync() -> str:
        repo = _Path(path).resolve()
        cfg = DriftConfig.load(repo)
        resolved = SIGNAL_ABBREV.get(signal.upper(), signal)
        v = verdict.lower().strip()
        if v not in ("tp", "fp", "fn"):
            return json.dumps({"error": f"Invalid verdict '{verdict}'. Use tp, fp, or fn."})
        event = FeedbackEvent(
            signal_type=resolved,
            file_path=file_path,
            verdict=v,  # type: ignore[arg-type]
            source="user",
            start_line=start_line if start_line > 0 else None,
            evidence={"reason": reason} if reason else {},
        )
        feedback_path = repo / cfg.calibration.feedback_path
        record_feedback(feedback_path, event)
        return json.dumps({
            "status": "recorded",
            "signal": resolved,
            "file": file_path,
            "verdict": v,
            "finding_id": event.finding_id,
        })

    raw = await _run_sync_in_thread(_sync)
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_feedback")


@mcp.tool()
async def drift_calibrate(
    path: Annotated[
        str,
        Field(description="Repository path to calibrate."),
    ] = ".",
    dry_run: Annotated[
        bool,
        Field(description="If true, show proposed changes without writing to config."),
    ] = True,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start."),
    ] = "",
) -> str:
    """Compute calibrated signal weights from accumulated feedback evidence.

    Reads all feedback (user verdicts, git correlation, GitHub issues) and
    computes a per-signal weight adjustment using Bayesian confidence weighting.
    In dry-run mode (default), only shows proposed changes.

    Args:
        path: Repository path to calibrate.
        dry_run: If true, show proposed changes without writing.
        session_id: Optional session ID for stateful workflows.
    """
    from pathlib import Path as _Path

    from drift.calibration.feedback import load_feedback
    from drift.calibration.profile_builder import build_profile
    from drift.config import DriftConfig, SignalWeights

    session = _resolve_session(session_id)

    def _sync() -> str:
        repo = _Path(path).resolve()
        cfg = DriftConfig.load(repo)
        feedback_path = repo / cfg.calibration.feedback_path
        events = load_feedback(feedback_path)

        if not events:
            return json.dumps({
                "status": "no_data",
                "message": "No feedback evidence found. Use drift_feedback to record evidence.",
                "agent_instruction": "Record TP/FP/FN feedback for findings before calibrating.",
            })

        result = build_profile(
            events, cfg.weights,
            min_samples=cfg.calibration.min_samples,
            fn_boost_factor=cfg.calibration.fn_boost_factor,
        )
        diff = result.weight_diff(SignalWeights())

        if not dry_run and diff:
            import yaml as _yaml  # type: ignore[import-untyped]

            config_path = DriftConfig._find_config_file(repo) or repo / "drift.yaml"
            if config_path.exists():
                data = _yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            else:
                data = {}
            default_dict = SignalWeights().as_dict()
            custom: dict[str, float] = {}
            for key, val in result.calibrated_weights.as_dict().items():
                if abs(val - default_dict.get(key, 0.0)) > 0.0001:
                    custom[key] = round(val, 6)
            if custom:
                data["weights"] = custom
            config_path.write_text(
                _yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

        return json.dumps({
            "status": "calibrated" if diff else "no_change",
            "total_events": result.total_events,
            "signals_with_data": result.signals_with_data,
            "weight_changes": diff,
            "dry_run": dry_run,
            "written": not dry_run and bool(diff),
            "agent_instruction": (
                "Review the weight changes. Use dry_run=false to apply, "
                "or record more feedback for higher confidence."
                if dry_run else "Weights written to drift.yaml."
            ),
        }, default=str)

    raw = await _run_sync_in_thread(_sync)
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_calibrate")


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
    drift_session_trace,
    drift_map,
    drift_feedback,
    drift_calibrate,
)



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
    from drift.plugins import load_all_plugins

    if not _MCP_AVAILABLE:
        msg = "MCP server requires optional dependency 'mcp'."
        raise RuntimeError(msg)

    # Ensure plugin signals are registered before API tools are exercised.
    load_all_plugins()
    _eager_imports()
    mcp.run(transport="stdio")
