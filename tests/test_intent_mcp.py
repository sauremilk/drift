"""Tests verifying MCP tool registration in a2a_router."""
from __future__ import annotations


def test_capture_intent_registered() -> None:
    from drift.serve.a2a_router import _SKILL_DISPATCH, _ensure_dispatch_table

    _SKILL_DISPATCH.clear()
    table = _ensure_dispatch_table()
    assert "capture_intent" in table


def test_verify_intent_registered() -> None:
    from drift.serve.a2a_router import _SKILL_DISPATCH, _ensure_dispatch_table

    _SKILL_DISPATCH.clear()
    table = _ensure_dispatch_table()
    assert "verify_intent" in table


def test_feedback_for_agent_registered() -> None:
    from drift.serve.a2a_router import _SKILL_DISPATCH, _ensure_dispatch_table

    _SKILL_DISPATCH.clear()
    table = _ensure_dispatch_table()
    assert "feedback_for_agent" in table
