"""Bounded-context router for fix-plan and verify MCP tool implementations."""

from __future__ import annotations

import contextlib
import json
from typing import Any

from drift.mcp_enrichment import _enrich_response_with_session
from drift.mcp_orchestration import (
    _resolve_session,
    _session_defaults,
    _strict_guardrail_block_response,
    _update_session_from_fix_plan,
)
from drift.mcp_utils import _parse_csv_ids, _run_api_tool


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
    """Return whether fix_plan can reuse the session queue without re-analysis.

    Eligible response profiles for the cache fast-path are ``None``, ``planner``,
    and ``coder``. Other profiles (for example ``verifier`` and
    ``merge_readiness``) require the full API call so their shaped payload stays
    consistent with profile-specific contracts.
    """
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
    return response_profile in (None, "planner", "coder")


def _session_fix_plan_fast_response(session: Any, *, max_tasks: int) -> dict[str, Any]:
    selected_tasks = list(session.selected_tasks or [])
    selected_by_id = {
        str(task.get("id", task.get("task_id", ""))): task
        for task in selected_tasks
    }

    pending_tasks: list[dict[str, Any]]
    queue_status = getattr(session, "queue_status", None)
    if callable(queue_status):
        queue = queue_status() or {}
        pending_entries = list(queue.get("pending_tasks") or [])
        pending_tasks = []
        for entry in pending_entries:
            task_id = str(entry.get("id", entry.get("task_id", "")))
            if task_id in selected_by_id:
                pending_tasks.append(selected_by_id[task_id])
            else:
                pending_tasks.append(entry)
    else:
        completed_ids = {
            str(task_id)
            for task_id in (session.completed_task_ids or [])
        }
        pending_tasks = [
            task for task in selected_tasks
            if str(task.get("id", task.get("task_id", ""))) not in completed_ids
        ]

    limit = max(0, int(max_tasks))
    limited = pending_tasks[:limit] if limit else []

    remaining_by_signal: dict[str, int] = {}
    for task in pending_tasks:
        signal = str(task.get("signal", "UNKNOWN"))
        remaining_by_signal[signal] = remaining_by_signal.get(signal, 0) + 1

    return {
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


async def run_fix_plan(
    *,
    path: str,
    signal: str | None,
    max_tasks: int,
    automation_fit_min: str | None,
    target_path: str | None,
    exclude_paths: str | None,
    include_deferred: bool,
    include_non_operational: bool,
    response_profile: str | None,
    session_id: str,
) -> str:
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

    kwargs = _session_defaults(
        session,
        {
            "path": path,
            "target_path": target_path,
            "signals": None,
            "exclude_signals": None,
        },
    )

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


async def run_verify(
    *,
    path: str,
    fail_on: str,
    scope_files: str | None,
    uncommitted: bool,
    response_profile: str | None,
    session_id: str,
) -> str:
    from drift.api.verify import verify

    session = _resolve_session(session_id)
    resolved_path = path
    if session and (not path or path == "."):
        resolved_path = session.repo_path

    raw = await _run_api_tool(
        "drift_verify",
        verify,
        path=resolved_path,
        fail_on=fail_on,
        scope_files=_parse_csv_ids(scope_files),
        uncommitted=uncommitted,
        response_profile=response_profile,
    )
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_verify")


async def run_fix_apply(
    *,
    path: str,
    signal: str | None,
    max_tasks: int,
    dry_run: bool,
    target_path: str | None,
    exclude_paths: str | None,
    session_id: str,
) -> str:
    from drift.api.fix_apply import fix_apply

    session = _resolve_session(session_id)
    blocked = _strict_guardrail_block_response("drift_fix_apply", session)
    if blocked is not None:
        return blocked

    parsed_exclude_paths = _parse_csv_ids(exclude_paths)

    kwargs = _session_defaults(
        session,
        {
            "path": path,
            "target_path": target_path,
            "signals": None,
            "exclude_signals": None,
        },
    )

    raw = await _run_api_tool(
        "drift_fix_apply",
        fix_apply,
        path=kwargs["path"],
        signal=signal,
        max_tasks=max_tasks,
        dry_run=dry_run,
        target_path=kwargs["target_path"],
        exclude_paths=parsed_exclude_paths,
    )
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_fix_apply")
