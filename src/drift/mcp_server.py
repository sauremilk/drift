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
    drift_verify          — Binary pass/fail coherence check after edits (ADR-070)
    drift_shadow_verify   — Scope-bounded full re-scan for cross-file-risky edits
    drift_negative_context — Anti-pattern warnings
    drift_session_start   — Create a stateful session (scope, baseline, tasks)
    drift_session_status  — Show current session state
    drift_session_update  — Modify session scope, mark tasks complete
    drift_session_end     — End session with summary
    drift_session_trace   — Return chronological session trace
    drift_map             — Lightweight module/dependency architecture map
    drift_feedback        — Record TP/FP/FN feedback for calibration
    drift_calibrate       — Compute calibrated signal weights from feedback
    drift_task_claim      — (deprecated) Claim a task from the fix-plan queue
    drift_task_renew      — (deprecated) Extend an active task lease
    drift_task_release    — (deprecated) Release a claimed task
    drift_task_complete   — (deprecated) Mark a claimed task as completed
    drift_task_status     — (deprecated) Show full task queue status

Decision: ADR-022
Refactored: Issue #378 — business logic extracted to router modules
"""

from __future__ import annotations

from typing import Annotated, Any

from drift.mcp_catalog import get_tool_catalog  # noqa: F401

MCPFastMCPImpl: Any

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
# Negative-context timeout (env-configurable)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# MCP instructions builder — see src/drift/mcp_instructions.py (Issue #378)
# ---------------------------------------------------------------------------
from drift.mcp_instructions import (  # noqa: E402
    _BASE_INSTRUCTIONS,  # noqa: F401 — re-exported; tests may import from drift.mcp_server
    _NEGATIVE_CONTEXT_TIMEOUT_SECONDS,
    _load_negative_context_instructions,
    _load_negative_context_timeout_seconds,  # noqa: F401 — re-exported for backward compat
)

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = MCPFastMCPImpl(
    "drift",
    instructions=_load_negative_context_instructions(),
)

# ---------------------------------------------------------------------------
# Session orchestration, guardrails, enrichment — delegated to submodules
# ---------------------------------------------------------------------------
from drift.mcp_enrichment import (  # noqa: E402
    _enrich_response_with_session,  # noqa: F401
    _session_error_response,
)
from drift.mcp_orchestration import (  # noqa: E402
    _effective_profile,  # noqa: F401
    _pre_call_advisory,  # noqa: F401
    _resolve_session,  # noqa: F401
    _session_defaults,  # noqa: F401
    _strict_guardrail_block_response,  # noqa: F401
    _update_session_from_verification_result,  # noqa: F401
)
from drift.mcp_utils import (  # noqa: E402
    _AUTOMATION_FIT_MIN_VALUES,  # noqa: F401
    _FAIL_ON_VALUES,  # noqa: F401
    _RESPONSE_DETAIL_VALUES,  # noqa: F401
    _RESPONSE_PROFILE_VALUES,  # noqa: F401
    _run_sync_in_thread,  # noqa: F401
    _validate_enum_param,  # noqa: F401
)

# Keep legacy re-exports visible to static analyzers and test imports.
_MCP_SERVER_LEGACY_REEXPORTS = (
    _effective_profile,
    _update_session_from_verification_result,
)

# ---------------------------------------------------------------------------
# MCP Tools — Analysis (scan / diff / explain / validate / brief / nudge)
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
    """Analyze a repository for architectural drift."""
    import json

    for _field, _val, _vals in [
        ("response_detail", response_detail, _RESPONSE_DETAIL_VALUES),
        ("response_profile", response_profile, _RESPONSE_PROFILE_VALUES),
    ]:
        _err = _validate_enum_param(_field, _val, _vals, "drift_scan")
        if _err:
            _err["tool"] = "drift_scan"
            return json.dumps(_err)

    from drift.mcp_router_analysis import run_scan

    return await run_scan(
        path=path,
        target_path=target_path,
        since_days=since_days,
        signals=signals,
        exclude_signals=exclude_signals,
        max_findings=max_findings,
        max_per_signal=max_per_signal,
        response_detail=response_detail,
        include_non_operational=include_non_operational,
        response_profile=response_profile,
        session_id=session_id,
    )


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
    """Detect drift changes since a git ref or baseline."""
    import json

    for _field, _val, _vals in [
        ("response_detail", response_detail, _RESPONSE_DETAIL_VALUES),
        ("response_profile", response_profile, _RESPONSE_PROFILE_VALUES),
    ]:
        _err = _validate_enum_param(_field, _val, _vals, "drift_diff")
        if _err:
            _err["tool"] = "drift_diff"
            return json.dumps(_err)

    from drift.mcp_router_analysis import run_diff

    return await run_diff(
        path=path,
        diff_ref=diff_ref,
        uncommitted=uncommitted,
        staged_only=staged_only,
        baseline_file=baseline_file,
        max_findings=max_findings,
        response_detail=response_detail,
        signals=signals,
        exclude_signals=exclude_signals,
        response_profile=response_profile,
        hypothesis_id=hypothesis_id,
        diagnostic_hypothesis=diagnostic_hypothesis,
        session_id=session_id,
    )


@mcp.tool()
async def drift_explain(
    topic: Annotated[
        str,
        Field(
            description=(
                "Signal abbreviation ('PFS'), signal name"
                " ('pattern_fragmentation'), or error code ('DRIFT-1003')."
            ),
        ),
    ],
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'planner', 'coder', 'verifier',"
                " 'merge_readiness'. Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start."),
    ] = "",
) -> str:
    """Explain a drift signal, rule, or error code."""
    from drift.mcp_router_analysis import run_explain

    return await run_explain(
        topic=topic,
        response_profile=response_profile,
        session_id=session_id,
    )


@mcp.tool()
async def drift_fix_plan(
    path: Annotated[str, Field(description="Repository path to analyze.")] = ".",
    signal: Annotated[
        str | None,
        Field(description="Filter tasks by signal abbreviation (e.g. 'PFS'). Omit for all."),
    ] = None,
    max_tasks: Annotated[
        int, Field(description="Maximum number of repair tasks to return.")
    ] = 5,
    automation_fit_min: Annotated[
        str | None,
        Field(
            description=(
                "Minimum automation fit level: 'low', 'medium', or 'high'."
                " Omit to include all tasks."
            ),
        ),
    ] = None,
    target_path: Annotated[
        str | None,
        Field(description="Restrict tasks to this subpath (relative to repo root)."),
    ] = None,
    exclude_paths: Annotated[
        str | None,
        Field(description="Comma-separated paths to exclude from the fix plan."),
    ] = None,
    include_deferred: Annotated[
        bool,
        Field(description="Include tasks that have been deferred/dismissed."),
    ] = False,
    include_non_operational: Annotated[
        bool,
        Field(description="Include tasks from non-operational contexts (fixtures, tests)."),
    ] = False,
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'planner' (tasks/graph/phases),"
                " 'coder' (findings/actions). Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start for stateful workflows."),
    ] = "",
) -> str:
    """Get prioritised repair tasks with constraints."""
    import json

    for _field, _val, _vals in [
        ("automation_fit_min", automation_fit_min, _AUTOMATION_FIT_MIN_VALUES),
        ("response_profile", response_profile, _RESPONSE_PROFILE_VALUES),
    ]:
        _err = _validate_enum_param(_field, _val, _vals, "drift_fix_plan")
        if _err:
            _err["tool"] = "drift_fix_plan"
            return json.dumps(_err)

    from drift.mcp_router_repair import run_fix_plan

    return await run_fix_plan(
        path=path,
        signal=signal,
        max_tasks=max_tasks,
        automation_fit_min=automation_fit_min,
        target_path=target_path,
        exclude_paths=exclude_paths,
        include_deferred=include_deferred,
        include_non_operational=include_non_operational,
        response_profile=response_profile,
        session_id=session_id,
    )


@mcp.tool()
async def drift_validate(
    path: Annotated[str, Field(description="Repository path to validate.")] = ".",
    config_file: Annotated[
        str | None,
        Field(description="Path to a custom drift.yaml config file."),
    ] = None,
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'planner', 'coder', 'verifier',"
                " 'merge_readiness'. Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start."),
    ] = "",
) -> str:
    """Preflight config and environment check."""
    from drift.mcp_router_analysis import run_validate

    return await run_validate(
        path=path,
        config_file=config_file,
        response_profile=response_profile,
        session_id=session_id,
    )


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
    task_signal: Annotated[
        str | None,
        Field(
            description=(
                "Signal type of the repair task being verified (e.g. 'mutant_duplicate'). "
                "When set with task_edit_kind, the outcome is recorded in the "
                "repair template registry for template-confidence learning."
            ),
        ),
    ] = None,
    task_edit_kind: Annotated[
        str | None,
        Field(
            description=(
                "Edit kind applied in the repair (e.g. 'merge_function_body'). "
                "Must also set task_signal to trigger outcome recording."
            ),
        ),
    ] = None,
    task_context_class: Annotated[
        str | None,
        Field(
            description=(
                "Context class for registry lookup (e.g. 'production' or 'test'). "
                "Defaults to 'production' when task_signal and task_edit_kind are set."
            ),
        ),
    ] = None,
) -> str:
    """Get directional feedback after a file change (experimental).

    Args:
        task_signal: Optional signal ID for the repaired finding (for example
            `mutant_duplicate`). Accepts known signal names used by fix-plan tasks.
            Combined with `task_edit_kind`, this enables template outcome recording
            used to refine nudge template-confidence scoring.
        task_edit_kind: Optional edit pattern label (for example
            `merge_function_body`). Accepts registry edit-kind identifiers.
            Must be paired with `task_signal`; together they map this nudge result
            to the matching repair template confidence bucket.
        task_context_class: Optional context bucket (`production` or `test`).
            Accepts registry context classes and defaults to `production` when
            outcome recording is active. This scopes confidence updates to the
            correct context during nudge scoring feedback.
    """
    from drift.mcp_router_analysis import run_nudge

    return await run_nudge(
        path=path,
        changed_files=changed_files,
        uncommitted=uncommitted,
        response_profile=response_profile,
        hypothesis_id=hypothesis_id,
        diagnostic_hypothesis=diagnostic_hypothesis,
        session_id=session_id,
        task_signal=task_signal,
        task_edit_kind=task_edit_kind,
        task_context_class=task_context_class,
    )


@mcp.tool()
async def drift_shadow_verify(
    path: Annotated[str, Field(description="Repository path to analyze.")] = ".",
    scope_files: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated posix-relative file paths to include in the comparison. "
                "Use the shadow_verify_scope value from the task contract. "
                "When omitted, all findings are compared (full-repo shadow verify)."
            ),
        ),
    ] = None,
    uncommitted: Annotated[
        bool,
        Field(
            description=(
                "Passed through for baseline freshness context. "
                "The analysis always covers the current working-tree state."
            ),
        ),
    ] = True,
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'verifier' (deltas/criteria),"
                " 'merge_readiness' (score/blocking). Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start for stateful workflows."),
    ] = "",
) -> str:
    """Scope-bounded full re-scan for cross-file-risky edits (ADR-064)."""
    from drift.mcp_router_analysis import run_shadow_verify

    return await run_shadow_verify(
        path=path,
        scope_files=scope_files,
        uncommitted=uncommitted,
        response_profile=response_profile,
        session_id=session_id,
    )


@mcp.tool()
async def drift_verify(
    path: Annotated[str, Field(description="Repository path to analyze.")] = ".",
    fail_on: Annotated[
        str,
        Field(
            description=(
                "Severity threshold for FAIL verdict. "
                "One of: critical, high, medium, low, none. Default: high."
            ),
        ),
    ] = "high",
    scope_files: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated posix-relative file paths to restrict "
                "verification scope. When omitted, all findings are compared."
            ),
        ),
    ] = None,
    uncommitted: Annotated[
        bool,
        Field(
            description="Analyze working-tree changes vs HEAD (default: true).",
        ),
    ] = True,
    response_profile: Annotated[
        str | None,
        Field(
            description=(
                "Response profile: 'verifier' (deltas/criteria),"
                " 'merge_readiness' (score/blocking). Omit for full response."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start for stateful workflows."),
    ] = "",
) -> str:
    """Verify structural coherence after edits — binary pass/fail verdict (ADR-070)."""
    import json

    for _field, _val, _vals in [
        ("fail_on", fail_on, _FAIL_ON_VALUES),
        ("response_profile", response_profile, _RESPONSE_PROFILE_VALUES),
    ]:
        _err = _validate_enum_param(_field, _val, _vals, "drift_verify")
        if _err:
            _err["tool"] = "drift_verify"
            return json.dumps(_err)

    from drift.mcp_router_repair import run_verify

    return await run_verify(
        path=path,
        fail_on=fail_on,
        scope_files=scope_files,
        uncommitted=uncommitted,
        response_profile=response_profile,
        session_id=session_id,
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
    """Get a pre-task structural briefing before writing code."""
    from drift.mcp_router_analysis import run_brief

    return await run_brief(
        path=path,
        task=task,
        scope=scope,
        max_guardrails=max_guardrails,
        response_detail=response_detail,
        response_profile=response_profile,
        session_id=session_id,
    )


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
    """Get anti-pattern warnings derived from drift analysis."""
    from drift.mcp_router_analysis import run_negative_context

    return await run_negative_context(
        path=path,
        scope=scope,
        target_file=target_file,
        max_items=max_items,
        response_profile=response_profile,
        session_id=session_id,
        timeout_seconds=_NEGATIVE_CONTEXT_TIMEOUT_SECONDS,
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
    autopilot_payload: Annotated[
        str,
        Field(
            description=(
                "Autopilot payload mode: 'summary' (default, compact with previews) "
                "or 'full' (embedded validate/brief/scan/fix_plan)."
            ),
        ),
    ] = "summary",
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
    """Start a new stateful session for multi-step agent workflows."""
    from drift.mcp_router_session import run_session_start

    return await run_session_start(
        path=path,
        signals=signals,
        exclude_signals=exclude_signals,
        target_path=target_path,
        exclude_paths=exclude_paths,
        ttl_seconds=ttl_seconds,
        autopilot=autopilot,
        autopilot_payload=autopilot_payload,
        response_profile=response_profile,
    )


@mcp.tool()
async def drift_session_status(
    session_id: Annotated[
        str, Field(description="The session ID returned by drift_session_start.")
    ],
) -> str:
    """Show the current state of an active session."""
    from drift.mcp_router_session import run_session_status

    return await run_session_status(
        session_id=session_id,
        session_error_response=_session_error_response,
    )


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
    """Update session scope, mark tasks complete, or save to disk."""
    from drift.mcp_router_session import run_session_update

    return await run_session_update(
        session_id=session_id,
        signals=signals,
        exclude_signals=exclude_signals,
        target_path=target_path,
        mark_tasks_complete=mark_tasks_complete,
        save_to_disk=save_to_disk,
        session_error_response=_session_error_response,
    )


@mcp.tool()
async def drift_session_end(
    session_id: Annotated[
        str, Field(description="The session ID to end.")
    ],
) -> str:
    """End a session and return a final summary."""
    from drift.mcp_router_session import run_session_end

    return await run_session_end(
        session_id=session_id,
        session_error_response=_session_error_response,
    )


# ---------------------------------------------------------------------------
# MCP Tools — Task-queue leasing (multi-agent coordination)
# DEPRECATED: These tools will be removed in v3.0.
# ---------------------------------------------------------------------------


@mcp.tool()
async def drift_task_claim(
    session_id: Annotated[
        str, Field(description="The active session ID from drift_session_start.")
    ],
    agent_id: Annotated[
        str, Field(description="Unique identifier for the claiming agent instance.")
    ],
    task_id: Annotated[
        str | None,
        Field(description="Specific task ID to claim. Omit to claim next available."),
    ] = None,
    lease_ttl_seconds: Annotated[
        int,
        Field(description="Lease time-to-live in seconds (default: 300 = 5 min)."),
    ] = 300,
    max_reclaim: Annotated[
        int,
        Field(description="Maximum number of times a task can be reclaimed (default: 3)."),
    ] = 3,
) -> str:
    """(Deprecated) Claim a pending task from the session's fix-plan queue."""
    from drift.mcp_legacy import run_task_claim

    return await run_task_claim(
        session_id=session_id,
        agent_id=agent_id,
        task_id=task_id,
        lease_ttl_seconds=lease_ttl_seconds,
        max_reclaim=max_reclaim,
    )


@mcp.tool()
async def drift_task_renew(
    session_id: Annotated[
        str, Field(description="The active session ID from drift_session_start.")
    ],
    agent_id: Annotated[
        str, Field(description="Agent ID that holds the lease.")
    ],
    task_id: Annotated[
        str, Field(description="Task ID whose lease to extend.")
    ],
    extend_seconds: Annotated[
        int,
        Field(description="Seconds to extend the lease by (default: 300)."),
    ] = 300,
) -> str:
    """(Deprecated) Extend an active task lease to prevent it from expiring."""
    from drift.mcp_legacy import run_task_renew

    return await run_task_renew(
        session_id=session_id,
        agent_id=agent_id,
        task_id=task_id,
        extend_seconds=extend_seconds,
    )


@mcp.tool()
async def drift_task_release(
    session_id: Annotated[
        str, Field(description="The active session ID from drift_session_start.")
    ],
    agent_id: Annotated[
        str, Field(description="Agent ID that holds the lease.")
    ],
    task_id: Annotated[
        str, Field(description="Task ID to release back to the pending pool.")
    ],
    max_reclaim: Annotated[
        int,
        Field(description="Maximum number of times a task can be reclaimed (default: 3)."),
    ] = 3,
) -> str:
    """(Deprecated) Release a claimed task back to the pending pool."""
    from drift.mcp_legacy import run_task_release

    return await run_task_release(
        session_id=session_id,
        agent_id=agent_id,
        task_id=task_id,
        max_reclaim=max_reclaim,
    )


@mcp.tool()
async def drift_task_complete(
    session_id: Annotated[
        str, Field(description="The active session ID from drift_session_start.")
    ],
    agent_id: Annotated[
        str, Field(description="Agent ID that holds the lease.")
    ],
    task_id: Annotated[
        str, Field(description="Task ID to mark as completed.")
    ],
    verify_evidence: Annotated[
        Any,
        Field(
            description=(
                "Optional verification evidence (e.g. nudge result with"
                " safe_to_commit=true)."
            ),
        ),
    ] = None,
) -> str:
    """(Deprecated) Mark a claimed task as completed and release its lease."""
    from drift.mcp_legacy import run_task_complete

    return await run_task_complete(
        session_id=session_id,
        agent_id=agent_id,
        task_id=task_id,
        verify_evidence=verify_evidence,
    )


@mcp.tool()
async def drift_task_status(
    session_id: Annotated[
        str, Field(description="The active session ID from drift_session_start.")
    ],
) -> str:
    """(Deprecated) Return a full queue overview: pending, claimed, completed, failed tasks."""
    from drift.mcp_legacy import run_task_status

    return await run_task_status(
        session_id=session_id,
    )


@mcp.tool()
async def drift_session_trace(
    session_id: Annotated[
        str, Field(description="Active session ID from drift_session_start.")
    ],
    last_n: Annotated[
        int, Field(description="Number of most recent trace entries to return.")
    ] = 20,
) -> str:
    """Return the session trace log — a chronological record of tool calls."""
    from drift.mcp_router_session import run_session_trace

    return await run_session_trace(
        session_id=session_id,
        last_n=last_n,
        session_error_response=_session_error_response,
    )


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
    """Return a lightweight module/dependency architecture map."""
    from drift.mcp_router_session import run_map

    return await run_map(
        path=path,
        target_path=target_path,
        max_modules=max_modules,
        session_id=session_id,
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
    """Record TP/FP/FN feedback for a finding to improve signal calibration."""
    from drift.mcp_router_calibration import run_feedback

    return await run_feedback(
        signal=signal,
        file_path=file_path,
        verdict=verdict,
        reason=reason,
        start_line=start_line,
        path=path,
        session_id=session_id,
    )


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
    """Compute calibrated signal weights from accumulated feedback evidence."""
    from drift.mcp_router_calibration import run_calibrate

    return await run_calibrate(
        path=path,
        dry_run=dry_run,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Patch Engine tools (ADR-074)
# ---------------------------------------------------------------------------

_BLAST_RADIUS_VALUES = frozenset({"local", "module", "repo"})


@mcp.tool()
async def drift_patch_begin(
    task_id: Annotated[
        str,
        Field(description="Unique identifier for the agent task."),
    ],
    declared_files: Annotated[
        str,
        Field(
            description=(
                "Comma-separated posix-relative file paths the agent intends to edit."
            ),
        ),
    ],
    expected_outcome: Annotated[
        str,
        Field(description="Short description of what the edit should achieve."),
    ],
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start."),
    ] = "",
    blast_radius: Annotated[
        str,
        Field(
            description=(
                "Expected blast radius: 'local' (single file), 'module' (package), "
                "'repo' (cross-module). Default: local."
            ),
        ),
    ] = "local",
    forbidden_paths: Annotated[
        str | None,
        Field(
            description="Comma-separated paths the agent must NOT touch.",
        ),
    ] = None,
    max_diff_lines: Annotated[
        int | None,
        Field(description="Maximum total diff lines before review is required."),
    ] = None,
) -> str:
    """Declare patch intent before editing files (ADR-074 phase 1)."""
    import json

    _err = _validate_enum_param(
        "blast_radius", blast_radius, _BLAST_RADIUS_VALUES, "drift_patch_begin"
    )
    if _err:
        _err["tool"] = "drift_patch_begin"
        return json.dumps(_err)

    from drift.mcp_router_patch import run_patch_begin

    return await run_patch_begin(
        task_id=task_id,
        declared_files=declared_files,
        expected_outcome=expected_outcome,
        session_id=session_id,
        blast_radius=blast_radius,
        forbidden_paths=forbidden_paths,
        max_diff_lines=max_diff_lines,
    )


@mcp.tool()
async def drift_patch_check(
    task_id: Annotated[
        str,
        Field(description="Task ID matching a prior drift_patch_begin call."),
    ],
    declared_files: Annotated[
        str,
        Field(
            description="Comma-separated posix-relative file paths from the intent.",
        ),
    ],
    path: Annotated[str, Field(description="Repository path to analyze.")] = ".",
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start."),
    ] = "",
    forbidden_paths: Annotated[
        str | None,
        Field(description="Comma-separated paths the agent must NOT touch."),
    ] = None,
    max_diff_lines: Annotated[
        int | None,
        Field(description="Maximum total diff lines before review is required."),
    ] = None,
) -> str:
    """Validate scope compliance after editing (ADR-074 phase 2)."""
    from drift.mcp_router_patch import run_patch_check

    return await run_patch_check(
        task_id=task_id,
        declared_files=declared_files,
        path=path,
        session_id=session_id,
        forbidden_paths=forbidden_paths,
        max_diff_lines=max_diff_lines,
    )


@mcp.tool()
async def drift_patch_commit(
    task_id: Annotated[
        str,
        Field(description="Task ID matching a prior drift_patch_begin call."),
    ],
    declared_files: Annotated[
        str,
        Field(
            description="Comma-separated posix-relative file paths from the intent.",
        ),
    ],
    expected_outcome: Annotated[
        str,
        Field(description="Short description of what the edit should achieve."),
    ],
    path: Annotated[str, Field(description="Repository path to analyze.")] = ".",
    session_id: Annotated[
        str,
        Field(description="Optional session ID from drift_session_start."),
    ] = "",
) -> str:
    """Generate evidence record for a completed patch (ADR-074 phase 3)."""
    from drift.mcp_router_patch import run_patch_commit

    return await run_patch_commit(
        task_id=task_id,
        declared_files=declared_files,
        expected_outcome=expected_outcome,
        path=path,
        session_id=session_id,
    )


_EXPORTED_MCP_TOOLS = (
    drift_scan,
    drift_diff,
    drift_verify,
    drift_explain,
    drift_fix_plan,
    drift_validate,
    drift_nudge,
    drift_shadow_verify,
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
    drift_patch_begin,
    drift_patch_check,
    drift_patch_commit,
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
