"""Machine-readable agent steering contracts (ADR-024) and error responses.

Defines the next-step contract vocabulary and structured error responses
used across all Drift API endpoints.
"""

from __future__ import annotations

from typing import Any

from drift.response_shaping import SCHEMA_VERSION

# ---------------------------------------------------------------------------
# Next-step contracts (ADR-024) — machine-readable agent steering
# ---------------------------------------------------------------------------

# Predicate constants for ``done_when`` — keep in sync across endpoints.
DONE_ACCEPT_CHANGE = "accept_change == true AND blocking_reasons is empty"
DONE_SAFE_TO_COMMIT = "safe_to_commit == true"
DONE_DIFF_ACCEPT = "drift_diff.accept_change == true"
DONE_TASKS_COMPLETE = "session.tasks_remaining == 0"
DONE_NO_FINDINGS = "drift_score == 0.0 OR findings_returned == 0"
DONE_STAGED_EXISTS = "staged files exist"
DONE_TASK_AND_NUDGE = "task completed AND drift_nudge.safe_to_commit == true"
DONE_NUDGE_SAFE = "drift_nudge.safe_to_commit == true"


def _tool_call(tool: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a single tool-call descriptor for next-step contracts."""
    return {"tool": tool, "params": params or {}}


def _next_step_contract(
    *,
    next_tool: str | None,
    next_params: dict[str, Any] | None = None,
    done_when: str,
    fallback_tool: str | None = None,
    fallback_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the machine-readable next-step contract block (ADR-024).

    Returns a dict with ``next_tool_call``, ``fallback_tool_call`` and
    ``done_when`` ready to be merged into any API response.
    """
    return {
        "next_tool_call": _tool_call(next_tool, next_params) if next_tool else None,
        "fallback_tool_call": (
            _tool_call(fallback_tool, fallback_params) if fallback_tool else None
        ),
        "done_when": done_when,
    }


def _error_response(
    error_code: str,
    message: str,
    *,
    invalid_fields: list[dict[str, Any]] | None = None,
    suggested_fix: dict[str, Any] | None = None,
    recoverable: bool = True,
    recovery_tool_call: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured error response (not an exception — for tool returns)."""
    from drift.errors import ERROR_REGISTRY

    info = ERROR_REGISTRY.get(error_code)
    resp: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "type": "error",
        "error_code": error_code,
        "category": info.category if info else "input",
        "message": message,
        "invalid_fields": invalid_fields or [],
        "suggested_fix": suggested_fix,
        "recoverable": recoverable,
    }
    if recovery_tool_call is not None:
        resp["recovery_tool_call"] = recovery_tool_call
    return resp
