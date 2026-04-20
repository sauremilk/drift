"""Bounded-context router for architecture & policy MCP tool implementations.

Covers: steer, compile_policy, suggest_rules, generate_skills.
"""

from __future__ import annotations

from drift.mcp_enrichment import _enrich_response_with_session
from drift.mcp_orchestration import (
    _resolve_session,
    _session_defaults,
    _strict_guardrail_block_response,
)
from drift.mcp_utils import _run_api_tool


async def run_steer(
    *,
    path: str,
    target: str,
    max_abstractions: int,
    response_profile: str | None,
    session_id: str,
) -> str:
    from drift.api.steer import steer

    session = _resolve_session(session_id)
    blocked = _strict_guardrail_block_response("drift_steer", session)
    if blocked is not None:
        return blocked

    kwargs = _session_defaults(
        session,
        {"path": path, "target_path": None, "signals": None, "exclude_signals": None},
    )

    raw = await _run_api_tool(
        "drift_steer",
        steer,
        path=kwargs["path"],
        target=target,
        max_abstractions=max_abstractions,
        response_profile=response_profile,
    )
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_steer")


async def run_compile_policy(
    *,
    path: str,
    task: str,
    task_spec_path: str | None,
    diff_ref: str | None,
    max_rules: int,
    response_profile: str | None,
    session_id: str,
) -> str:
    from drift.api.compile_policy import compile_policy

    session = _resolve_session(session_id)
    blocked = _strict_guardrail_block_response("drift_compile_policy", session)
    if blocked is not None:
        return blocked

    kwargs = _session_defaults(
        session,
        {"path": path, "target_path": None, "signals": None, "exclude_signals": None},
    )

    raw = await _run_api_tool(
        "drift_compile_policy",
        compile_policy,
        path=kwargs["path"],
        task=task,
        task_spec_path=task_spec_path,
        diff_ref=diff_ref,
        max_rules=max_rules,
        response_profile=response_profile,
    )
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_compile_policy")


async def run_suggest_rules(
    *,
    path: str,
    min_occurrences: int,
    response_profile: str | None,
    session_id: str,
) -> str:
    from drift.api.suggest_rules import suggest_rules

    session = _resolve_session(session_id)
    blocked = _strict_guardrail_block_response("drift_suggest_rules", session)
    if blocked is not None:
        return blocked

    kwargs = _session_defaults(
        session,
        {"path": path, "target_path": None, "signals": None, "exclude_signals": None},
    )

    raw = await _run_api_tool(
        "drift_suggest_rules",
        suggest_rules,
        path=kwargs["path"],
        min_occurrences=min_occurrences,
        response_profile=response_profile,
    )
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_suggest_rules")


async def run_generate_skills(
    *,
    path: str,
    min_occurrences: int,
    min_confidence: float,
    response_profile: str | None,
    session_id: str,
) -> str:
    from drift.api.generate_skills import generate_skills

    session = _resolve_session(session_id)
    blocked = _strict_guardrail_block_response("drift_generate_skills", session)
    if blocked is not None:
        return blocked

    kwargs = _session_defaults(
        session,
        {"path": path, "target_path": None, "signals": None, "exclude_signals": None},
    )

    raw = await _run_api_tool(
        "drift_generate_skills",
        generate_skills,
        path=kwargs["path"],
        min_occurrences=min_occurrences,
        min_confidence=min_confidence,
        response_profile=response_profile,
    )
    if session:
        session.touch()
    return _enrich_response_with_session(raw, session, "drift_generate_skills")
