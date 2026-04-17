"""Bounded-context router for patch engine MCP tool implementations."""

from __future__ import annotations

import json
from typing import Any

from drift.mcp_enrichment import _enrich_response_with_session
from drift.mcp_orchestration import _resolve_session
from drift.mcp_utils import _parse_csv_ids, _run_api_tool


def _store_patch_intent(session: Any, task_id: str, raw: str) -> None:
    """Store the PatchIntent in session.active_patches if session exists."""
    if session is None or not hasattr(session, "active_patches"):
        return
    try:
        data = json.loads(raw)
        intent = data.get("intent")
        if intent:
            session.active_patches[task_id] = {"intent": intent}
    except (json.JSONDecodeError, TypeError):
        pass


def _store_patch_verdict(session: Any, task_id: str, raw: str) -> None:
    """Store the PatchVerdict in session.active_patches if session exists."""
    if session is None or not hasattr(session, "active_patches"):
        return
    try:
        data = json.loads(raw)
        verdict = data.get("verdict")
        if verdict and task_id in session.active_patches:
            session.active_patches[task_id]["verdict"] = verdict
    except (json.JSONDecodeError, TypeError):
        pass


def _finalize_patch(session: Any, task_id: str, raw: str) -> None:
    """Move completed patch from active_patches to patch_history."""
    if session is None or not hasattr(session, "active_patches"):
        return
    try:
        data = json.loads(raw)
        evidence = data.get("evidence")
        if evidence:
            if hasattr(session, "patch_history"):
                session.patch_history.append(evidence)
            session.active_patches.pop(task_id, None)
    except (json.JSONDecodeError, TypeError):
        pass


async def run_patch_begin(
    *,
    task_id: str,
    declared_files: str,
    expected_outcome: str,
    session_id: str,
    blast_radius: str,
    forbidden_paths: str | None,
    max_diff_lines: int | None,
) -> str:
    from drift.api.patch import patch_begin

    session = _resolve_session(session_id)

    raw = await _run_api_tool(
        "drift_patch_begin",
        patch_begin,
        task_id=task_id,
        declared_files=_parse_csv_ids(declared_files) or [],
        expected_outcome=expected_outcome,
        session_id=session_id or None,
        blast_radius=blast_radius,
        forbidden_paths=_parse_csv_ids(forbidden_paths),
        max_diff_lines=max_diff_lines,
    )
    if session:
        _store_patch_intent(session, task_id, raw)
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_patch_begin")


async def run_patch_check(
    *,
    task_id: str,
    declared_files: str,
    path: str,
    session_id: str,
    forbidden_paths: str | None,
    max_diff_lines: int | None,
) -> str:
    from drift.api.patch import patch_check

    session = _resolve_session(session_id)
    resolved_path = path
    if session and (not path or path == "."):
        resolved_path = session.repo_path

    raw = await _run_api_tool(
        "drift_patch_check",
        patch_check,
        task_id=task_id,
        declared_files=_parse_csv_ids(declared_files) or [],
        path=resolved_path,
        forbidden_paths=_parse_csv_ids(forbidden_paths),
        max_diff_lines=max_diff_lines,
    )
    if session:
        _store_patch_verdict(session, task_id, raw)
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_patch_check")


async def run_patch_commit(
    *,
    task_id: str,
    declared_files: str,
    expected_outcome: str,
    path: str,
    session_id: str,
) -> str:
    from drift.api.patch import patch_commit

    session = _resolve_session(session_id)
    resolved_path = path
    if session and (not path or path == "."):
        resolved_path = session.repo_path

    raw = await _run_api_tool(
        "drift_patch_commit",
        patch_commit,
        task_id=task_id,
        declared_files=_parse_csv_ids(declared_files) or [],
        expected_outcome=expected_outcome,
        path=resolved_path,
        session_id=session_id or None,
    )
    if session:
        _finalize_patch(session, task_id, raw)
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_patch_commit")
