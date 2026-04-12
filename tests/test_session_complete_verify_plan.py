"""Unit tests for the verify_plan gate in DriftSession.complete_task().

Covers POLICY §18 enforcement: tasks with a non-empty verify_plan require
explicit evidence (safe_to_commit=true from drift_nudge) before they can
be marked completed.
"""

from __future__ import annotations

import pytest

from drift.session import DriftSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AGENT = "agent-1"
_TASK_WITH_VP = "task-vp"
_TASK_NO_VP_EMPTY = "task-no-vp-empty"
_TASK_NO_VP_MISSING = "task-no-vp-missing"


def _make_session(tasks: list[dict]) -> DriftSession:
    s = DriftSession(session_id="test-session", repo_path="/tmp/repo", phase="fix")
    s.selected_tasks = tasks
    return s


def _claim(session: DriftSession, task_id: str) -> None:
    result = session.claim_task(agent_id=_AGENT, task_id=task_id)
    assert result is not None, f"Could not claim task {task_id!r}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVerifyPlanGate:
    """complete_task() enforces verify_plan evidence when verify_plan is set."""

    def test_a_task_with_verify_plan_no_evidence_is_rejected(self) -> None:
        """Task has verify_plan + no result → verify_plan_required."""
        session = _make_session(
            [{"id": _TASK_WITH_VP, "verify_plan": [{"tool": "drift_nudge"}]}]
        )
        _claim(session, _TASK_WITH_VP)

        outcome = session.complete_task(agent_id=_AGENT, task_id=_TASK_WITH_VP, result=None)

        assert outcome["status"] == "verify_plan_required"
        assert "verify_plan" in outcome["error"].lower()
        # Task must NOT be in completed list
        assert _TASK_WITH_VP not in session.completed_task_ids

    def test_b_task_with_verify_plan_safe_to_commit_false_is_rejected(self) -> None:
        """Task has verify_plan + safe_to_commit=False → verify_plan_required."""
        session = _make_session(
            [{"id": _TASK_WITH_VP, "verify_plan": [{"tool": "drift_nudge"}]}]
        )
        _claim(session, _TASK_WITH_VP)

        outcome = session.complete_task(
            agent_id=_AGENT,
            task_id=_TASK_WITH_VP,
            result={"verify_evidence": {"safe_to_commit": False}},
        )

        assert outcome["status"] == "verify_plan_required"
        assert _TASK_WITH_VP not in session.completed_task_ids

    def test_c_task_with_verify_plan_safe_to_commit_true_completes(self) -> None:
        """Task has verify_plan + safe_to_commit=True → completed."""
        session = _make_session(
            [{"id": _TASK_WITH_VP, "verify_plan": [{"tool": "drift_nudge"}]}]
        )
        _claim(session, _TASK_WITH_VP)

        outcome = session.complete_task(
            agent_id=_AGENT,
            task_id=_TASK_WITH_VP,
            result={"verify_evidence": {"safe_to_commit": True}},
        )

        assert outcome["status"] == "completed"
        assert _TASK_WITH_VP in session.completed_task_ids

    def test_d_task_with_empty_verify_plan_completes_without_evidence(self) -> None:
        """Task has verify_plan=[] + no evidence → completed (no gate)."""
        session = _make_session(
            [{"id": _TASK_NO_VP_EMPTY, "verify_plan": []}]
        )
        _claim(session, _TASK_NO_VP_EMPTY)

        outcome = session.complete_task(
            agent_id=_AGENT, task_id=_TASK_NO_VP_EMPTY, result=None
        )

        assert outcome["status"] == "completed"
        assert _TASK_NO_VP_EMPTY in session.completed_task_ids

    def test_e_task_without_verify_plan_field_completes_without_evidence(self) -> None:
        """Task dict has no verify_plan key at all + no evidence → completed."""
        session = _make_session(
            [{"id": _TASK_NO_VP_MISSING, "title": "fix foo"}]
        )
        _claim(session, _TASK_NO_VP_MISSING)

        outcome = session.complete_task(
            agent_id=_AGENT, task_id=_TASK_NO_VP_MISSING, result=None
        )

        assert outcome["status"] == "completed"
        assert _TASK_NO_VP_MISSING in session.completed_task_ids
