"""Tests for ADR-025 Phases E/F/G: Plan validation, task contracts, metrics.

Decision: ADR-025
"""

from __future__ import annotations

import time

import pytest

from drift.api_helpers import (
    PlanValidationResult,
    WorkflowPlan,
    _compute_plan_fingerprint,
    _derive_task_contract,
    validate_plan,
)
from drift.session import DriftSession, OrchestrationMetrics, SessionManager

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_manager():
    """Ensure a fresh SessionManager for every test."""
    SessionManager.reset_instance()
    yield
    SessionManager.reset_instance()


SAMPLE_TASKS = [
    {"id": "t1", "signal": "PFS", "title": "Fix fragmentation in api.py"},
    {"id": "t2", "signal": "AVS", "title": "Reduce coupling in models.py"},
    {"id": "t3", "signal": "BEM", "title": "Normalise error handling"},
]


def _make_session(
    tasks: list[dict] | None = None,
    ttl: int = 1800,
) -> DriftSession:
    s = DriftSession(
        session_id="test-session",
        repo_path="/tmp/repo",
        ttl_seconds=ttl,
    )
    if tasks is not None:
        s.selected_tasks = tasks
    return s


# ---------------------------------------------------------------------------
# OrchestrationMetrics
# ---------------------------------------------------------------------------


class TestOrchestrationMetrics:
    def test_defaults(self):
        m = OrchestrationMetrics()
        assert m.tasks_claimed == 0
        assert m.tasks_completed == 0
        assert m.tasks_failed == 0
        assert m.tasks_released == 0
        assert m.plans_created == 0
        assert m.first_claim_at is None

    def test_to_dict_computed_fields(self):
        m = OrchestrationMetrics()
        m.tasks_claimed = 5
        m.tasks_completed = 3
        m.tasks_failed = 1
        m.tasks_expired = 1
        d = m.to_dict()
        assert d["tasks_completed"] == 3
        assert d["tasks_failed"] == 1
        # discarded_work_ratio = (failed + expired) / claimed
        assert d["discarded_work_ratio"] == pytest.approx(2 / 5, abs=0.01)

    def test_to_dict_zero_denominator(self):
        m = OrchestrationMetrics()
        d = m.to_dict()
        assert d["discarded_work_ratio"] == 0.0
        assert d["plan_reuse_ratio"] == 0.0

    def test_roundtrip(self):
        m = OrchestrationMetrics()
        m.tasks_claimed = 5
        m.tasks_completed = 3
        m.first_claim_at = 1000.0
        d = m.to_dict()
        m2 = OrchestrationMetrics.from_dict(d)
        assert m2.tasks_claimed == 5
        assert m2.tasks_completed == 3
        assert m2.first_claim_at == 1000.0

    def test_from_dict_empty(self):
        m = OrchestrationMetrics.from_dict({})
        assert m.tasks_claimed == 0


# ---------------------------------------------------------------------------
# Claim-Guard
# ---------------------------------------------------------------------------


class TestClaimGuard:
    def test_double_claim_blocked_and_counted(self):
        s = _make_session(list(SAMPLE_TASKS))
        result1 = s.claim_task("agent-a", task_id="t1")
        assert result1 is not None
        result2 = s.claim_task("agent-b", task_id="t1")
        assert result2 is None
        assert s.metrics.duplicate_claims_attempted == 1

    def test_claim_after_expire_allowed(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1", lease_ttl_seconds=1)
        # Manually expire
        lease = s.active_leases["t1"]
        lease["expires_at"] = time.time() - 1
        result = s.claim_task("agent-b", task_id="t1")
        # The Claim-Guard checks expires_at — expired lease lets through
        assert result is not None

    def test_claim_updates_metrics(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a")
        assert s.metrics.tasks_claimed == 1
        assert s.metrics.first_claim_at is not None

    def test_first_claim_at_not_overwritten(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a")
        first = s.metrics.first_claim_at
        s.claim_task("agent-b")
        assert s.metrics.first_claim_at == first


# ---------------------------------------------------------------------------
# Complete task: result storage
# ---------------------------------------------------------------------------


class TestCompleteResultStorage:
    def test_result_stored(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        result = s.complete_task("agent-a", "t1", result={"nudge": "safe"})
        assert result["result_stored"] is True
        assert s.completed_results["t1"] == {"nudge": "safe"}

    def test_result_none_not_stored(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        result = s.complete_task("agent-a", "t1", result=None)
        assert result["result_stored"] is False
        assert "t1" not in s.completed_results

    def test_complete_updates_metrics(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        s.complete_task("agent-a", "t1")
        assert s.metrics.tasks_completed == 1
        assert s.metrics.first_completion_at is not None
        assert s.metrics.last_completion_at is not None

    def test_complete_tracks_lease_duration(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1", lease_ttl_seconds=300)
        # Manually adjust acquired_at to simulate elapsed time
        s.active_leases["t1"]["acquired_at"] = time.time() - 10
        s.complete_task("agent-a", "t1")
        assert s.metrics.total_lease_time_seconds >= 9.5


# ---------------------------------------------------------------------------
# Release task: metrics
# ---------------------------------------------------------------------------


class TestReleaseMetrics:
    def test_release_increments_counter(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        s.release_task("agent-a", "t1")
        assert s.metrics.tasks_released == 1

    def test_release_tracks_lease_duration(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        s.active_leases["t1"]["acquired_at"] = time.time() - 5
        s.release_task("agent-a", "t1")
        assert s.metrics.total_lease_time_seconds >= 4.5

    def test_release_max_reclaim_marks_failed(self):
        s = _make_session(list(SAMPLE_TASKS))
        for _ in range(3):
            s.claim_task("agent-a", task_id="t1")
            s.release_task("agent-a", "t1")
        assert s.metrics.tasks_failed == 1
        assert s.metrics.tasks_released == 3


# ---------------------------------------------------------------------------
# Session serialisation with new fields
# ---------------------------------------------------------------------------


class TestSessionSerialisationExtended:
    def test_roundtrip_completed_results(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        s.complete_task("agent-a", "t1", result={"nudge": "safe"})
        d = s.to_dict()
        s2 = DriftSession.from_dict(d)
        assert s2.completed_results == {"t1": {"nudge": "safe"}}

    def test_roundtrip_metrics(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        s.complete_task("agent-a", "t1")
        d = s.to_dict()
        s2 = DriftSession.from_dict(d)
        assert s2.metrics.tasks_claimed == 1
        assert s2.metrics.tasks_completed == 1

    def test_roundtrip_legacy_no_metrics(self):
        """Legacy session dicts without 'metrics' key get fresh defaults."""
        s = _make_session(list(SAMPLE_TASKS))
        d = s.to_dict()
        del d["metrics"]
        s2 = DriftSession.from_dict(d)
        assert s2.metrics.tasks_claimed == 0

    def test_end_summary_includes_metrics(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        s.complete_task("agent-a", "t1")
        summary = s.end_summary()
        assert "orchestration_metrics" in summary
        assert summary["orchestration_metrics"]["tasks_completed"] == 1


# ---------------------------------------------------------------------------
# Plan fingerprint
# ---------------------------------------------------------------------------


class TestPlanFingerprint:
    def _make_plan(self, **overrides) -> WorkflowPlan:
        defaults: dict = {
            "steps": [],
            "success_criteria": "score < 50",
            "abort_criteria": "score > 80",
        }
        defaults.update(overrides)
        return WorkflowPlan(**defaults)

    def test_fingerprint_deterministic(self):
        p = self._make_plan()
        fp1 = _compute_plan_fingerprint(p)
        fp2 = _compute_plan_fingerprint(p)
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA-256 hex

    def test_fingerprint_changes_with_state(self):
        p1 = self._make_plan(depended_on_repo_state={"head_commit": "abc"})
        p2 = self._make_plan(depended_on_repo_state={"head_commit": "def"})
        assert _compute_plan_fingerprint(p1) != _compute_plan_fingerprint(p2)


# ---------------------------------------------------------------------------
# Plan validation
# ---------------------------------------------------------------------------


class TestPlanValidation:
    def test_invalidated_plan_returns_replan(self):
        p = WorkflowPlan(
            steps=[],
            success_criteria="",
            abort_criteria="",
            invalidated=True,
            invalidation_reason="manual",
        )
        result = validate_plan(p, "/nonexistent")
        assert not result.valid
        assert result.recommendation == "re_plan"
        assert "explicit_invalidation" in result.triggered

    def test_legacy_plan_without_state_passes(self):
        p = WorkflowPlan(
            steps=[],
            success_criteria="",
            abort_criteria="",
            depended_on_repo_state={},
        )
        result = validate_plan(p, "/nonexistent")
        assert result.valid
        assert result.reason == "legacy_plan_no_state"

    def test_validation_result_serialisation(self):
        r = PlanValidationResult(
            valid=False,
            reason="test",
            stale_files=["a.py"],
            recommendation="re_plan",
            triggered=["head_commit_changed"],
        )
        d = r.to_api_dict()
        assert d["valid"] is False
        assert d["stale_files"] == ["a.py"]
        assert d["recommendation"] == "re_plan"


# ---------------------------------------------------------------------------
# Task contracts
# ---------------------------------------------------------------------------


class TestTaskContracts:
    def test_contract_has_allowed_files(self):
        task = {
            "id": "t1", "signal": "PFS",
            "file": "src/api.py",
            "related_files": ["src/models.py"],
        }
        contract = _derive_task_contract(task)
        assert "src/api.py" in contract["allowed_files"]
        assert "src/models.py" in contract["allowed_files"]

    def test_contract_has_forbidden_files(self):
        task = {"id": "t1", "signal": "PFS", "file": "src/api.py"}
        contract = _derive_task_contract(task)
        assert "POLICY.md" in contract["forbidden_files"]
        assert "pyproject.toml" in contract["forbidden_files"]

    def test_contract_has_completion_evidence(self):
        task = {"id": "t1", "signal": "PFS", "file": "src/api.py"}
        contract = _derive_task_contract(task)
        assert contract["completion_evidence"]["type"] == "nudge_safe"
        assert contract["completion_evidence"]["tool"] == "drift_nudge"

    def test_contract_no_file_empty_allowed(self):
        task = {"id": "t1", "signal": "PFS"}
        contract = _derive_task_contract(task)
        assert contract["allowed_files"] == []

    def test_max_files_changed_minimum(self):
        task = {"id": "t1", "signal": "PFS"}
        contract = _derive_task_contract(task)
        assert contract["max_files_changed"] >= 3
