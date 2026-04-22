"""Bounded-context router for MCP session lifecycle tools."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from drift.mcp_autopilot import AUTOPILOT_PAYLOAD_MODES, build_autopilot_summary
from drift.mcp_orchestration import _strict_guardrail_block_response
from drift.mcp_utils import _parse_csv_ids, _run_sync_in_thread

# ---------------------------------------------------------------------------
# ADR-081 Nachschärfung (Q2): plan-staleness threshold
# ---------------------------------------------------------------------------
# A queue log whose newest ``plan_created`` event is older than this many
# seconds is treated as stale: the session_start response still replays the
# plan so no work is lost, but ``resumed_plan_stale`` becomes True, the
# agent_instruction warns the agent, and ``next_tool_call`` is redirected to
# ``drift_fix_plan`` so prioritisation can happen against the current scan.
# Default 24 h matches the "next working day" heuristic; override via the
# ``DRIFT_QUEUE_STALE_SECONDS`` environment variable for tests or projects
# with very fast cadence.
_QUEUE_PLAN_STALE_SECONDS_DEFAULT: float = 86_400.0


def _queue_plan_stale_threshold() -> float:
    """Return the current staleness threshold in seconds.

    Reads ``DRIFT_QUEUE_STALE_SECONDS`` at call time so tests can override
    it via ``monkeypatch.setenv`` without reloading the module.  Invalid
    or non-positive values fall back to the default.
    """
    raw = os.environ.get("DRIFT_QUEUE_STALE_SECONDS")
    if not raw:
        return _QUEUE_PLAN_STALE_SECONDS_DEFAULT
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return _QUEUE_PLAN_STALE_SECONDS_DEFAULT
    if value <= 0.0:
        return _QUEUE_PLAN_STALE_SECONDS_DEFAULT
    return value


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
    fresh_start: bool = False,
) -> str:
    from drift.api_helpers import _error_response
    from drift.mcp_enrichment import _enrich_response_with_session
    from drift.session import SessionManager
    from drift.session_queue_log import reduce_events, replay_events

    payload_mode = str(autopilot_payload).strip().lower()
    if payload_mode not in AUTOPILOT_PAYLOAD_MODES:
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
    try:
        session_id = mgr.create(
            repo_path=str(Path(path).resolve()),
            signals=_parse_csv_ids(signals),
            exclude_signals=_parse_csv_ids(exclude_signals),
            target_path=target_path,
            exclude_paths=_parse_csv_ids(exclude_paths),
            ttl_seconds=ttl_seconds,
        )
    except RuntimeError as exc:
        if "DRIFT-4000" not in str(exc):
            raise
        error = _error_response(
            "DRIFT-4000",
            str(exc),
            invalid_fields=[
                {
                    "field": "session_pool",
                    "value": "exhausted",
                    "reason": "maximum number of active sessions reached",
                }
            ],
            suggested_fix={
                "action": "End inactive sessions or retry later.",
                "example_call": {
                    "tool": "drift_session_end",
                    "params": {"session_id": "<active-session-id>"},
                },
            },
            recoverable=True,
        )
        return json.dumps(error, default=str)

    session = mgr.get(session_id)

    # ADR-081 Nachschärfung (Q3): best-effort concurrent-writer detection.
    # Read any existing writer-advisory lock *before* we take ownership so
    # we can surface a live previous holder in the response.  ADR-081 keeps
    # the cooperative single-writer contract, so we do not hard-block.
    from drift.session_writer_lock import (
        acquire_writer_advisory,
        read_current_holder,
    )

    concurrent_writer: dict[str, object] | None = None
    concurrent_sessions_detected = False
    repo_for_lock: Path | str | None = None
    if session is not None:
        repo_candidate = getattr(session, "repo_path", None)
        if isinstance(repo_candidate, (str, Path)):
            repo_for_lock = repo_candidate
    if repo_for_lock is not None:
        try:
            holder = read_current_holder(repo_for_lock)
        except Exception as exc:  # noqa: BLE001 - best-effort advisory
            logging.getLogger("drift").debug(
                "concurrent-writer probe failed: %s", exc
            )
            holder = None
        if holder is not None and holder.session_id != session_id:
            concurrent_sessions_detected = True
            concurrent_writer = holder.to_dict()
        try:
            acquire_writer_advisory(repo_for_lock, session_id=session_id)
        except OSError as exc:
            logging.getLogger("drift").debug(
                "writer-advisory acquire failed: %s", exc
            )

    # Queue-log replay: rehydrate selected_tasks / completed / failed from a
    # previous session's append-only log so agent work survives MCP server
    # restarts and session TTL expiry.  ADR-081.
    resumed_from_log = False
    resumed_tasks = 0
    resumed_completed = 0
    resumed_failed = 0
    resumed_plan_created_at: float | None = None
    resumed_plan_age_seconds: float | None = None
    resumed_plan_stale = False
    resumed_older_plans_discarded = 0
    resumed_next_task_id: str | None = None
    if session is not None and not fresh_start:
        events = replay_events(session.repo_path)
        if events:
            state = reduce_events(events)
            # ADR-081 Nachschärfung (Q4): count any ``plan_created`` events
            # older than the one that wins the replay; purely informational
            # so reviewers can audit that replan semantics are intentional.
            if state.plan_created_at is not None:
                resumed_older_plans_discarded = sum(
                    1
                    for evt in events
                    if evt.type == "plan_created"
                    and float(evt.timestamp) < float(state.plan_created_at)
                )
            if state.selected_tasks:
                # Session was just created and is not yet exposed to other
                # tool calls, so direct field assignment is safe.
                session.selected_tasks = list(state.selected_tasks)
                for tid in state.completed_task_ids:
                    if tid not in session.completed_task_ids:
                        session.completed_task_ids.append(tid)
                for tid in state.failed_task_ids:
                    if tid not in session.failed_task_ids:
                        session.failed_task_ids.append(tid)
                resumed_from_log = True
                resumed_tasks = len(state.selected_tasks)
                resumed_completed = len(state.completed_task_ids)
                resumed_failed = len(state.failed_task_ids)
                # ADR-081 Nachschärfung (Q2): surface plan age so agents
                # can decide to re-plan rather than follow a stale queue.
                if state.plan_created_at is not None:
                    resumed_plan_created_at = float(state.plan_created_at)
                    age = max(0.0, time.time() - resumed_plan_created_at)
                    resumed_plan_age_seconds = age
                    if age > _queue_plan_stale_threshold():
                        resumed_plan_stale = True
                # ADR-081 Nachschärfung (Q5): pick the first pending task so
                # the response can route the agent straight to
                # ``drift_fix_apply`` instead of a generic ``drift_scan``.
                # Pending = in selected_tasks and not in completed/failed.
                # Order: ``priority_score`` DESC (from drift_fix_plan) with
                # original index as deterministic tiebreaker.
                completed_set = set(state.completed_task_ids)
                failed_set = set(state.failed_task_ids)
                pending: list[tuple[int, dict[str, Any]]] = []
                for idx, task in enumerate(state.selected_tasks):
                    candidate = task.get("id") or task.get("task_id")
                    if not isinstance(candidate, str) or not candidate:
                        continue
                    if candidate in completed_set or candidate in failed_set:
                        continue
                    pending.append((idx, task))

                def _score(entry: tuple[int, dict[str, Any]]) -> tuple[float, int]:
                    idx, task = entry
                    raw = task.get("priority_score")
                    try:
                        score = float(raw) if raw is not None else 0.0
                    except (TypeError, ValueError):
                        score = 0.0
                    # DESC on score, ASC on idx — invert score sign so the
                    # built-in ASC sort gives DESC on score.
                    return (-score, idx)

                pending.sort(key=_score)
                if pending:
                    first = pending[0][1]
                    first_tid = first.get("id") or first.get("task_id")
                    if isinstance(first_tid, str) and first_tid:
                        resumed_next_task_id = first_tid

    result: dict[str, Any] = {
        "status": "ok",
        "session_id": session_id,
        "repo_path": str(Path(path).resolve()),
        "scope": session.scope_label() if session else "all",
        "ttl_seconds": ttl_seconds,
        "created_at": session.created_at if session else None,
        "resumed_from_log": resumed_from_log,
        "resumed_tasks": resumed_tasks,
        "resumed_completed": resumed_completed,
        "resumed_failed": resumed_failed,
        "resumed_plan_created_at": resumed_plan_created_at,
        "resumed_plan_age_seconds": resumed_plan_age_seconds,
        "resumed_plan_stale": resumed_plan_stale,
        "resumed_older_plans_discarded": resumed_older_plans_discarded,
        "resumed_next_task_id": resumed_next_task_id,
        "concurrent_sessions_detected": concurrent_sessions_detected,
        "concurrent_writer": concurrent_writer,
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

    # ADR-081 Nachschärfung (Q2): when the replayed plan is older than the
    # staleness threshold, override agent_instruction and next_tool_call so
    # the agent re-prioritises against the current codebase instead of
    # following a zombie plan.
    if resumed_plan_stale and resumed_plan_age_seconds is not None:
        age_hours = resumed_plan_age_seconds / 3600.0
        result["agent_instruction"] = (
            f"Session {session_id[:8]} resumed a queued plan that is "
            f"{age_hours:.1f}h old ({resumed_tasks} pending tasks). "
            "Plan may be stale — run drift_fix_plan again to re-prioritise "
            "against the current scan before applying fixes."
        )
        result["next_tool_call"] = {
            "tool": "drift_fix_plan",
            "params": {"session_id": session_id},
        }
        result["fallback_tool_call"] = {
            "tool": "drift_scan",
            "params": {"session_id": session_id},
        }
    elif (
        resumed_from_log
        and resumed_next_task_id is not None
        and resumed_tasks > 0
    ):
        # ADR-081 Nachschärfung (Q5): fresh resume with pending work —
        # route the agent straight to ``drift_fix_apply`` so the queue is
        # worked off instead of re-scanning.  Only applies when the plan
        # is NOT stale (P2 override above wins otherwise) and fresh_start
        # is not in effect (resumed_from_log remains False then).
        result["agent_instruction"] = (
            f"Session {session_id[:8]} resumed with {resumed_tasks} pending "
            f"tasks. Address the queue with drift_fix_apply "
            f"(task_id={resumed_next_task_id!r}) before launching new scans."
        )
        result["next_tool_call"] = {
            "tool": "drift_fix_apply",
            "params": {
                "session_id": session_id,
                "task_id": resumed_next_task_id,
            },
        }
        result["fallback_tool_call"] = {
            "tool": "drift_fix_plan",
            "params": {"session_id": session_id},
        }

    # ADR-081 Nachschärfung (Q3): if a live previous writer was detected
    # (before replay), annotate the agent_instruction so the operator
    # knows to pause the other session.  Advisory only — ADR-081 stays
    # cooperative.
    if concurrent_sessions_detected and concurrent_writer is not None:
        holder_pid = concurrent_writer.get("pid")
        holder_sid = concurrent_writer.get("session_id", "unknown")
        existing = result.get("agent_instruction", "")
        result["agent_instruction"] = (
            f"{existing} Concurrent writer detected (pid={holder_pid}, "
            f"session={str(holder_sid)[:8]}) — pause the other session or "
            "queue writes may interleave."
        ).strip()

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

        # Intent capture hint for high-AI-attributed-ratio repositories (Issue 537)
        _ai_ratio = float(scan_result.get("ai_ratio", 0.0))
        if _ai_ratio > 0.7:
            result["intent_capture_hint"] = {
                "reason": "high_ai_attributed_ratio",
                "ai_attributed_ratio": round(_ai_ratio, 3),
                "threshold": 0.7,
                "suggested_tool": "drift_capture_intent",
                "suggested_command": "drift intent run",
                "message": (
                    f"AI-attributed commit ratio is {_ai_ratio:.0%} (>70%). "
                    "Consider capturing intent before making code changes: "
                    "drift_capture_intent(path='.')"
                ),
            }
            result["agent_instruction"] = (
                f"Autopilot ready. AI-attributed commit ratio is {_ai_ratio:.0%} (>70%) — "
                "run drift_capture_intent(path='.') before code changes. "
                "Next: drift_fix_plan(session_id)."
            )
            result["recommended_next_actions"] = [
                'drift_capture_intent(path=".")',
                f'drift_fix_plan(session_id="{session_id}", max_tasks=1)',
                f'drift_session_status(session_id="{session_id}")',
            ]

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
    force: bool = False,
    bypass_reason: str | None = None,
    session_md_path: str | None = None,
    evidence_path: str | None = None,
    adr_path: str | None = None,
) -> str:
    from drift.api_helpers import _error_response
    from drift.session import DriftSession, SessionManager
    from drift.session_handover import (
        MAX_HANDOVER_RETRIES,
        ChangeClass,
        classify_session,
        validate,
        validate_bypass_reason,
    )

    mgr = SessionManager.instance()
    session = mgr.get(session_id)
    if session is not None:
        blocked = _strict_guardrail_block_response("drift_session_end", session)
        if blocked is not None:
            return blocked

    # ADR-079: Handover-Artefakt-Gate.
    # Only run the gate for real DriftSession instances; test fakes bypass it.
    gate_payload: dict[str, Any] | None = None
    if isinstance(session, DriftSession):
        change_class = classify_session(session)
        empty_session = (
            not session.completed_task_ids
            and not session.selected_tasks
            and session.tool_calls < 3
            and change_class is ChangeClass.CHORE
        )
        retries = session.handover_retries
        if not empty_session and not force:
            overrides: dict[str, str] = {}
            if session_md_path:
                overrides["session_md"] = session_md_path
            if evidence_path:
                overrides["evidence"] = evidence_path
            if adr_path:
                overrides["adr"] = adr_path

            result = validate(
                session,
                change_class=change_class,
                path_overrides=overrides or None,
            )
            if not result.ok:
                session.handover_retries = retries + 1
                session.last_activity = session.last_activity  # keep alive
                session.record_trace(
                    tool="drift_session_end",
                    advisory="session_handover.blocked",
                    metadata={
                        "change_class": str(change_class.value),
                        "retry": session.handover_retries,
                        "missing": [a.kind for a in result.missing],
                        "shape_error_count": len(result.shape_errors),
                        "placeholder_count": len(result.placeholder_flags),
                    },
                )
                # Bounded retry: after the limit, agent must use force=true.
                if session.handover_retries > MAX_HANDOVER_RETRIES:
                    pass  # fall through to unblock via force instruction
                else:
                    error = _error_response(
                        "DRIFT-6100",
                        "Session handover artifacts are missing or invalid.",
                        recoverable=True,
                        suggested_fix={
                            "action": (
                                "Author the missing handover artifacts per "
                                "ADR-079 / docs/session_handover_template.md, "
                                "then retry drift_session_end."
                            ),
                            "max_retries": MAX_HANDOVER_RETRIES,
                            "remaining_retries": max(
                                MAX_HANDOVER_RETRIES - session.handover_retries, 0
                            ),
                        },
                    )
                    error["session_id"] = session_id
                    error["status"] = "blocked"
                    error.update(result.to_dict())
                    error["agent_instruction"] = (
                        f"Session {session_id[:8]} blocked by handover gate "
                        f"(change_class={change_class.value}). "
                        "Fill missing artifacts, then retry drift_session_end."
                    )
                    return json.dumps(error, default=str)
            gate_payload = result.to_dict()

        if force:
            reason_err = validate_bypass_reason(bypass_reason)
            if reason_err is not None:
                error = _error_response(
                    "DRIFT-6101",
                    f"force=true requires a valid bypass_reason: {reason_err}",
                    recoverable=True,
                    suggested_fix={
                        "action": (
                            "Provide bypass_reason with a human-meaningful "
                            "explanation of why the handover gate is being "
                            "bypassed. Do not use placeholder text."
                        ),
                    },
                )
                error["session_id"] = session_id
                error["status"] = "blocked"
                return json.dumps(error, default=str)
            logging.getLogger("drift").warning(
                "Session handover gate bypassed via force=true: "
                "session=%s reason=%s",
                session_id[:8],
                bypass_reason,
            )

    # ADR-081 Nachschärfung (Q3): release the writer-advisory lock so a
    # subsequent session on the same repo does not see us as a live holder.
    # Real DriftSessions always expose ``repo_path``; test fakes may not,
    # so we probe via ``getattr`` and skip the release cleanly.
    repo_for_release: Path | str | None = None
    if session is not None:
        repo_candidate = getattr(session, "repo_path", None)
        if isinstance(repo_candidate, (str, Path)):
            repo_for_release = repo_candidate

    summary = mgr.destroy(session_id)
    if summary is None:
        return session_error_response(
            "DRIFT-6001",
            f"Session {session_id[:8]} not found or already ended.",
            session_id,
        )

    if repo_for_release is not None:
        from drift.session_writer_lock import release_writer_advisory

        try:
            release_writer_advisory(repo_for_release, session_id=session_id)
        except OSError as exc:
            logging.getLogger("drift").debug(
                "writer-advisory release failed: %s", exc
            )

    summary["status"] = "ok"
    if gate_payload is not None:
        summary["handover_gate"] = gate_payload
    if force:
        summary["handover_bypass"] = {
            "forced": True,
            "reason": bypass_reason,
        }
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
