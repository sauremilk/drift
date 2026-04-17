"""Bounded-context router for MCP session lifecycle tools."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from drift.mcp_autopilot import AUTOPILOT_PAYLOAD_MODES, build_autopilot_summary
from drift.mcp_orchestration import _strict_guardrail_block_response
from drift.mcp_utils import _parse_csv_ids, _run_sync_in_thread


async def run_session_start(
    *,
    path: str,
    signals: str | None,
    exclude_signals: str | None,
    target_path: str | None,
    exclude_paths: str | None,
    ttl_seconds: int,
    autopilot: bool,
    autopilot_payload: str,
    response_profile: str | None,
) -> str:
    from drift.mcp_enrichment import _enrich_response_with_session
    from drift.session import SessionManager

    payload_mode = str(autopilot_payload).strip().lower()
    if payload_mode not in AUTOPILOT_PAYLOAD_MODES:
        from drift.api_helpers import _error_response

        error = _error_response(
            "DRIFT-1003",
            f"Invalid autopilot_payload '{autopilot_payload}'",
            invalid_fields=[{
                "field": "autopilot_payload",
                "value": autopilot_payload,
                "reason": "Expected one of: summary, full",
            }],
            suggested_fix={
                "action": "Use a supported autopilot payload mode.",
                "valid_values": ["summary", "full"],
                "example_call": {
                    "tool": "drift_session_start",
                    "params": {
                        "path": path,
                        "autopilot": True,
                        "autopilot_payload": "summary",
                    },
                },
            },
        )
        return json.dumps(error, default=str)

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
    result: dict[str, Any] = {
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

    if autopilot:
        from drift.analyzer import analyze_repo
        from drift.api import validate
        from drift.api._config import _load_config_cached, _warn_config_issues
        from drift.api.brief import brief_from_analysis
        from drift.api.fix_plan import _build_fix_plan_response_from_analysis
        from drift.api.scan import _format_scan_response
        from drift.api_helpers import (
            build_drift_score_scope,
            shape_for_profile,
            signal_scope_label,
        )
        from drift.config import apply_signal_filter, resolve_signal_names

        loop = asyncio.get_running_loop()
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

        def _autopilot_from_shared_analysis() -> tuple[
            dict[str, Any], dict[str, Any], dict[str, Any]
        ]:
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

            brief_result = brief_from_analysis(
                path=resolved,
                task="autopilot session start",
                analysis=analysis,
                cfg=cfg,
                scope_override=target_path,
                signals=sig_list,
                max_guardrails=10,
                include_non_operational=False,
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
                shape_for_profile(brief_result, response_profile),
                shape_for_profile(scan_result, response_profile),
                shape_for_profile(fix_plan_result, response_profile),
            )

        brief_result, scan_result, fp_result = await loop.run_in_executor(
            None,
            _autopilot_from_shared_analysis,
        )
        if payload_mode == "full":
            result["autopilot"] = {
                "validate": val_result,
                "brief": brief_result,
                "scan": scan_result,
                "fix_plan": fp_result,
            }
        else:
            result["autopilot"] = build_autopilot_summary(
                session_id=session_id,
                validate_result=val_result,
                brief_result=brief_result,
                scan_result=scan_result,
                fix_plan_result=fp_result,
            )
        result["agent_instruction"] = (
            "Autopilot ready. Next: drift_fix_plan(session_id)."
        )
        result["recommended_next_actions"] = [
            f"drift_fix_plan(session_id=\"{session_id}\", max_tasks=1)",
            f"drift_session_status(session_id=\"{session_id}\")",
        ]
        result["next_tool_call"] = {
            "tool": "drift_fix_plan",
            "params": {"session_id": session_id},
        }

    raw = json.dumps(result, default=str)
    return _enrich_response_with_session(raw, session, "drift_session_start")


async def run_session_status(
    *,
    session_id: str,
    session_error_response: Callable[[str, str, str], str],
) -> str:
    from drift.session import SessionManager

    session = SessionManager.instance().get(session_id)
    if session is None:
        return session_error_response(
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


async def run_session_update(
    *,
    session_id: str,
    signals: str | None,
    exclude_signals: str | None,
    target_path: str | None,
    mark_tasks_complete: str | None,
    save_to_disk: bool,
    session_error_response: Callable[[str, str, str], str],
) -> str:
    import warnings

    from drift.session import SessionManager

    warnings.warn(
        "drift_session_update is deprecated and will be removed in v3.0. "
        "Use drift_session_start(autopilot=true) for automatic session orchestration.",
        DeprecationWarning,
        stacklevel=1,
    )

    mgr = SessionManager.instance()
    session = mgr.get(session_id)
    if session is None:
        return session_error_response(
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


async def run_session_end(
    *,
    session_id: str,
    session_error_response: Callable[[str, str, str], str],
) -> str:
    from drift.session import SessionManager

    session = SessionManager.instance().get(session_id)
    if session is not None:
        blocked = _strict_guardrail_block_response("drift_session_end", session)
        if blocked is not None:
            return blocked

    summary = SessionManager.instance().destroy(session_id)
    if summary is None:
        return session_error_response(
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


async def run_session_trace(
    *,
    session_id: str,
    last_n: int,
    session_error_response: Callable[[str, str, str], str],
) -> str:
    from drift.session import SessionManager

    session = SessionManager.instance().get(session_id)
    if session is None:
        return session_error_response(
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


async def run_map(
    *,
    path: str,
    target_path: str | None,
    max_modules: int,
    session_id: str | None,
) -> str:
    from drift.api import drift_map as api_drift_map
    from drift.mcp_enrichment import _enrich_response_with_session
    from drift.mcp_orchestration import _resolve_session, _session_defaults

    session = _resolve_session(session_id)
    kwargs = _session_defaults(session, {"path": path, "target_path": target_path})

    try:
        result = await _run_sync_in_thread(
            lambda: api_drift_map(
                kwargs.get("path", path),
                target_path=kwargs.get("target_path"),
                max_modules=max_modules,
            ),
            abandon_on_cancel=True,
        )
        raw = json.dumps(result, default=str)
        if session is not None:
            raw = _enrich_response_with_session(raw, session, "drift_map")
        return raw
    except Exception as exc:  # noqa: BLE001
        from drift.api_helpers import _error_response

        error = _error_response("DRIFT-7001", str(exc), recoverable=True)
        # Keep MCP consumers compatible with both error discriminators.
        error["status"] = "error"
        error["tool"] = "drift_map"
        error["agent_instruction"] = (
            "Verify that the repository path exists and target_path points to a valid "
            "subdirectory. Retry drift_map with a corrected path."
        )
        return json.dumps(error, default=str)
