"""MCP response enrichment — session metadata injection and error helpers.

Extracted from ``mcp_server.py`` to separate response-transformation from
MCP tool registration.

Decision: ADR-022
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drift.mcp_orchestration import _pre_call_advisory


def _enrich_response_with_session(
    raw_json: str,
    session: Any,
    tool_name: str = "",
    trace_meta: dict[str, Any] | None = None,
) -> str:
    """Inject session metadata into a tool response JSON string."""
    if session is None:
        return raw_json

    # Record trace entry + pre-call advisory
    advisory = _pre_call_advisory(tool_name, session) if tool_name else ""
    if tool_name:
        session.record_trace(tool_name, advisory=advisory, metadata=trace_meta)
    try:
        result = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return raw_json

    if not isinstance(result, dict):
        return raw_json

    session_block: dict[str, Any] = {
        "session_id": session.session_id,
        "scope": session.scope_label(),
        "tasks_remaining": session.tasks_remaining(),
        "phase": session.phase,
        "score_delta_since_start": (
            round(session.last_scan_score - session.score_at_start, 2)
            if session.last_scan_score is not None
            and session.score_at_start is not None
            else None
        ),
    }

    if session.git_head_at_plan:
        try:
            from drift.pipeline import _current_git_head

            current_head = _current_git_head(Path(session.repo_path))
        except Exception:  # noqa: BLE001
            current_head = None

        if current_head and current_head != session.git_head_at_plan:
            session_block["plan_stale"] = True
            session_block["plan_stale_reason"] = (
                "Plan baseline head "
                f"{session.git_head_at_plan} differs from current head {current_head}."
            )

    # Quality-drift detection
    from drift.quality_gate import quality_drift_from_history

    qd = quality_drift_from_history(session.run_history)
    if qd is not None:
        session_block["quality_drift"] = {
            "direction": qd.direction,
            "score_delta": qd.score_delta,
            "finding_delta": qd.finding_delta,
            "advisory": qd.advisory,
        }

    # Progressive tool disclosure — recommend tools for current phase
    from drift.tool_metadata import tools_for_phase

    session_block["available_tools"] = tools_for_phase(session.phase)

    # Pre-call advisory (soft guidance)
    if advisory:
        session_block["advisory"] = advisory

    # Tool context hint for the current tool
    if tool_name:
        from drift.tool_metadata import TOOL_CATALOG

        tool_entry = TOOL_CATALOG.get(tool_name)
        if tool_entry:
            session_block["context_hint"] = {
                "when_to_use": tool_entry.context.when_to_use,
                "follow_up_tools": list(tool_entry.context.follow_up_tools),
            }

    result["session"] = session_block

    # Enrich agent_instruction with session hint
    hint = (
        f"Session {session.session_id[:8]} active"
        f" (phase={session.phase},"
        f" {session.tasks_remaining()} tasks remaining)."
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
