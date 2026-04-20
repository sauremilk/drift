"""Bounded-context router for intent-loop MCP tool implementations.

Handles the business logic for ``drift_capture_intent``,
``drift_verify_intent``, and ``drift_feedback_for_agent`` tools, keeping
them out of the transport/registration layer in mcp_server.py.
"""

from __future__ import annotations

from drift.mcp_enrichment import _enrich_response_with_session
from drift.mcp_orchestration import _resolve_session
from drift.mcp_utils import _run_sync_in_thread


async def run_capture_intent(
    *,
    raw: str,
    path: str,
    session_id: str,
) -> str:
    """Extract and persist a structured intent from a raw user input string."""
    import json

    from drift.api.capture_intent import capture_intent

    session = _resolve_session(session_id)

    def _sync() -> str:
        result = capture_intent(raw=raw, path=path)
        return json.dumps(result)

    raw_resp = await _run_sync_in_thread(_sync, abandon_on_cancel=True)
    if session:
        session.touch()
    return _enrich_response_with_session(raw_resp, session, "drift_capture_intent")


async def run_verify_intent(
    *,
    intent_id: str,
    artifact_path: str,
    path: str,
    session_id: str,
) -> str:
    """Verify that a build artifact fulfils a previously captured intent."""
    import json

    from drift.api.verify_intent import verify_intent

    session = _resolve_session(session_id)

    def _sync() -> str:
        result = verify_intent(
            intent_id=intent_id,
            artifact_path=artifact_path,
            path=path,
        )
        return json.dumps(result)

    raw_resp = await _run_sync_in_thread(_sync, abandon_on_cancel=True)
    if session:
        session.touch()
    return _enrich_response_with_session(raw_resp, session, "drift_verify_intent")


async def run_feedback_for_agent(
    *,
    intent_id: str,
    path: str,
    artifact_path: str,
    session_id: str,
) -> str:
    """Return a prioritised action list based on the current verify state."""
    import json

    from drift.api.feedback_for_agent import feedback_for_agent

    session = _resolve_session(session_id)

    def _sync() -> str:
        result = feedback_for_agent(
            intent_id=intent_id,
            path=path,
            artifact_path=artifact_path,
        )
        return json.dumps(result)

    raw_resp = await _run_sync_in_thread(_sync, abandon_on_cancel=True)
    if session:
        session.touch()
    return _enrich_response_with_session(raw_resp, session, "drift_feedback_for_agent")
