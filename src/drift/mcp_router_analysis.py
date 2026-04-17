"""Bounded-context router for MCP analysis tools.

Covers: scan, diff, nudge, explain, validate, brief, shadow_verify, negative_context.
"""

from __future__ import annotations

import contextlib
import io
import json
from typing import Any, cast

from drift.mcp_enrichment import _enrich_response_with_session
from drift.mcp_orchestration import (
    _resolve_diagnostic_hypothesis_context,
    _resolve_session,
    _session_defaults,
    _strict_guardrail_block_response,
    _trace_meta_from_hypothesis_result,
    _update_session_from_brief,
    _update_session_from_diff,
    _update_session_from_scan,
)
from drift.mcp_utils import (
    _parse_csv_ids,
    _run_api_tool,
    _run_sync_in_thread,
    _run_sync_with_timeout,
)


async def run_scan(
    *,
    path: str,
    target_path: str | None,
    since_days: int,
    signals: str | None,
    exclude_signals: str | None,
    max_findings: int,
    max_per_signal: int | None,
    response_detail: str,
    include_non_operational: bool,
    response_profile: str | None,
    session_id: str,
) -> str:
    from drift.api import scan

    session = _resolve_session(session_id)
    kwargs = _session_defaults(
        session,
        {
            "path": path,
            "target_path": target_path,
            "signals": _parse_csv_ids(signals),
            "exclude_signals": _parse_csv_ids(exclude_signals),
        },
    )

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


async def run_diff(
    *,
    path: str,
    diff_ref: str,
    uncommitted: bool,
    staged_only: bool,
    baseline_file: str | None,
    max_findings: int,
    response_detail: str,
    signals: str | None,
    exclude_signals: str | None,
    response_profile: str | None,
    hypothesis_id: str | None,
    diagnostic_hypothesis: Any,
    session_id: str,
) -> str:
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
    kwargs = _session_defaults(
        session,
        {
            "path": path,
            "signals": _parse_csv_ids(signals),
            "exclude_signals": _parse_csv_ids(exclude_signals),
        },
    )
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


async def run_nudge(
    *,
    path: str,
    changed_files: str | None,
    uncommitted: bool,
    response_profile: str | None,
    hypothesis_id: str | None,
    diagnostic_hypothesis: Any,
    session_id: str,
    task_signal: str | None,
    task_edit_kind: str | None,
    task_context_class: str | None,
) -> str:
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
        task_signal=task_signal,
        task_edit_kind=task_edit_kind,
        task_context_class=task_context_class,
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


async def run_explain(
    *,
    topic: str,
    response_profile: str | None,
    session_id: str,
) -> str:
    from drift.api import explain

    session = _resolve_session(session_id)
    raw = await _run_api_tool(
        "drift_explain",
        explain,
        topic=topic,
        response_profile=response_profile,
    )
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_explain")


async def run_validate(
    *,
    path: str,
    config_file: str | None,
    response_profile: str | None,
    session_id: str,
) -> str:
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
                pass
    return _enrich_response_with_session(raw, session, "drift_validate")


async def run_brief(
    *,
    path: str,
    task: str,
    scope: str | None,
    max_guardrails: int,
    response_detail: str,
    response_profile: str | None,
    session_id: str,
) -> str:
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

    payload: str = cast(str, await _run_sync_in_thread(_sync, abandon_on_cancel=True))
    if session:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            _update_session_from_brief(session, json.loads(payload))
    return _enrich_response_with_session(payload, session, "drift_brief")


async def run_shadow_verify(
    *,
    path: str,
    scope_files: str | None,
    uncommitted: bool,
    response_profile: str | None,
    session_id: str,
) -> str:
    from drift.api.shadow_verify import shadow_verify

    session = _resolve_session(session_id)
    resolved_path = path
    if session and (not path or path == "."):
        resolved_path = session.repo_path

    raw = await _run_api_tool(
        "drift_shadow_verify",
        shadow_verify,
        path=resolved_path,
        scope_files=_parse_csv_ids(scope_files),
        uncommitted=uncommitted,
        response_profile=response_profile,
    )
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_shadow_verify")


async def run_negative_context(
    *,
    path: str,
    scope: str | None,
    target_file: str | None,
    max_items: int,
    response_profile: str | None,
    session_id: str,
    timeout_seconds: float,
) -> str:
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
        if response_profile is not None:
            kwargs["response_profile"] = response_profile
        with contextlib.redirect_stdout(io.StringIO()):
            result = negative_context(resolved_path, **kwargs)
        if not isinstance(result, dict):
            return json.dumps({
                "status": "error",
                "error_code": "DRIFT-2032",
                "message": "MCP tool returned no structured response.",
                "recoverable": True,
                "agent_instruction": "Retry the call once; if it repeats, run drift_validate.",
            }, default=str)
        return json.dumps(result, default=str)

    try:
        raw = cast(str, await _run_sync_with_timeout(_sync, timeout_seconds))
        if session:
            session.touch()
        return _enrich_response_with_session(raw, session, "drift_negative_context")
    except TimeoutError:
        return json.dumps({
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
        }, default=str)
    except Exception as exc:
        from drift.api_helpers import _error_response

        error = _error_response("DRIFT-5001", str(exc), recoverable=True)
        error["tool"] = "drift_negative_context"
        return json.dumps(error, default=str)
