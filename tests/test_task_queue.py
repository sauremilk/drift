"""Unit tests for task-queue leasing in DriftSession.

Tests cover claim/renew/release/complete lifecycle, FIFO ordering,
lease expiry with reclaim counting, and serialisation round-trips.

Decision: ADR-025
"""

from __future__ import annotations

import time

import pytest

from drift.session import DriftSession, SessionManager

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_manager():
    """Ensure a fresh SessionManager for every test."""
    SessionManager.reset_instance()
    yield
    SessionManager.reset_instance()


def _make_session(
    tasks: list[dict] | None = None,
    ttl: int = 1800,
) -> DriftSession:
    """Create a session pre-loaded with selected_tasks."""
    s = DriftSession(
        session_id="test-session",
        repo_path="/tmp/repo",
        ttl_seconds=ttl,
    )
    if tasks is not None:
        s.selected_tasks = tasks
    return s


SAMPLE_TASKS = [
    {"id": "t1", "signal": "PFS", "title": "Fix fragmentation in api.py"},
    {"id": "t2", "signal": "AVS", "title": "Reduce coupling in models.py"},
    {"id": "t3", "signal": "BEM", "title": "Normalise error handling"},
]


# ---------------------------------------------------------------------------
# TestTaskQueueClaim
# ---------------------------------------------------------------------------


class TestTaskQueueClaim:
    def test_claim_returns_first_pending_fifo(self):
        s = _make_session(list(SAMPLE_TASKS))
        result = s.claim_task("agent-a")
        assert result is not None
        assert result["task"]["id"] == "t1"
        assert result["lease"]["agent_id"] == "agent-a"
        assert result["lease"]["task_id"] == "t1"

    def test_claim_specific_task_id(self):
        s = _make_session(list(SAMPLE_TASKS))
        result = s.claim_task("agent-a", task_id="t2")
        assert result is not None
        assert result["task"]["id"] == "t2"

    def test_double_claim_same_task_returns_none(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        result = s.claim_task("agent-b", task_id="t1")
        assert result is None

    def test_claim_completed_task_returns_none(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.completed_task_ids.append("t1")
        result = s.claim_task("agent-a", task_id="t1")
        assert result is None

    def test_claim_no_selected_tasks_returns_none(self):
        s = _make_session(tasks=None)
        result = s.claim_task("agent-a")
        assert result is None

    def test_claim_all_completed_returns_none(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.completed_task_ids.extend(["t1", "t2", "t3"])
        result = s.claim_task("agent-a")
        assert result is None

    def test_fifo_skips_claimed_tasks(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        result = s.claim_task("agent-b")
        assert result is not None
        assert result["task"]["id"] == "t2"

    def test_claim_failed_task_returns_none(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.failed_task_ids.append("t1")
        result = s.claim_task("agent-a", task_id="t1")
        assert result is None

    def test_claim_sets_lease_fields(self):
        s = _make_session(list(SAMPLE_TASKS))
        result = s.claim_task("agent-a", lease_ttl_seconds=120)
        assert result is not None
        lease = result["lease"]
        assert lease["lease_ttl_seconds"] == 120
        assert lease["expires_at"] > time.time()
        assert lease["expires_at"] <= time.time() + 121


# ---------------------------------------------------------------------------
# TestLeaseLifecycle
# ---------------------------------------------------------------------------


class TestLeaseLifecycle:
    def test_renew_extends_expiry(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1", lease_ttl_seconds=60)
        before = s.active_leases["t1"]["expires_at"]
        outcome = s.renew_lease("agent-a", "t1", extend_seconds=120)
        assert outcome["status"] == "renewed"
        assert outcome["expires_at"] == pytest.approx(before + 120, abs=1)
        assert outcome["renew_count"] == 1

    def test_renew_wrong_agent_fails(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        outcome = s.renew_lease("agent-b", "t1")
        assert outcome["status"] == "wrong_agent"

    def test_renew_after_expiry_fails(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1", lease_ttl_seconds=1)
        # Force expiry
        s.active_leases["t1"]["expires_at"] = time.time() - 1
        outcome = s.renew_lease("agent-a", "t1")
        assert outcome["status"] == "expired"

    def test_renew_nonexistent_task(self):
        s = _make_session(list(SAMPLE_TASKS))
        outcome = s.renew_lease("agent-a", "t-nonexistent")
        assert outcome["status"] == "not_found"

    def test_expired_lease_becomes_reclaimable(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1", lease_ttl_seconds=1)
        # Force expiry
        s.active_leases["t1"]["expires_at"] = time.time() - 1
        # Now another agent should be able to claim it (reap triggers on claim)
        result = s.claim_task("agent-b", task_id="t1")
        assert result is not None
        assert result["lease"]["agent_id"] == "agent-b"

    def test_max_reclaim_marks_task_failed(self):
        s = _make_session(list(SAMPLE_TASKS))
        for i in range(3):
            claim = s.claim_task(f"agent-{i}", task_id="t1", max_reclaim=3)
            assert claim is not None, f"Claim {i} should succeed"
            # Force expiry to simulate timeout
            s.active_leases["t1"]["expires_at"] = time.time() - 1
        # 3 expired leases → reap marks as failed
        result = s.claim_task("agent-x", task_id="t1", max_reclaim=3)
        assert result is None
        assert "t1" in s.failed_task_ids

    def test_release_increments_reclaim_count(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        outcome = s.release_task("agent-a", "t1")
        assert outcome["status"] == "released"
        assert outcome["reclaim_count"] == 1
        assert s.task_reclaim_counts["t1"] == 1

    def test_release_max_reclaim_marks_failed(self):
        s = _make_session(list(SAMPLE_TASKS))
        for i in range(3):
            s.claim_task(f"agent-{i}", task_id="t1", max_reclaim=3)
            outcome = s.release_task(f"agent-{i}", "t1", max_reclaim=3)
            if i < 2:
                assert outcome["status"] == "released"
            else:
                assert outcome["status"] == "failed"
        assert "t1" in s.failed_task_ids

    def test_release_wrong_agent_fails(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        outcome = s.release_task("agent-b", "t1")
        assert outcome["status"] == "wrong_agent"

    def test_release_nonexistent_lease(self):
        s = _make_session(list(SAMPLE_TASKS))
        outcome = s.release_task("agent-a", "t1")
        assert outcome["status"] == "not_found"


# ---------------------------------------------------------------------------
# TestCompleteTask
# ---------------------------------------------------------------------------


class TestCompleteTask:
    def test_complete_removes_lease_and_marks_completed(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        assert "t1" in s.active_leases
        outcome = s.complete_task("agent-a", "t1")
        assert outcome["status"] == "completed"
        assert "t1" not in s.active_leases
        assert "t1" in s.completed_task_ids

    def test_complete_wrong_agent_fails(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        outcome = s.complete_task("agent-b", "t1")
        assert outcome["status"] == "wrong_agent"
        assert "t1" in s.active_leases  # Lease unchanged

    def test_complete_already_completed_idempotent(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.completed_task_ids.append("t1")
        outcome = s.complete_task("agent-a", "t1")
        assert outcome["status"] == "already_completed"

    def test_complete_without_lease_fails(self):
        s = _make_session(list(SAMPLE_TASKS))
        outcome = s.complete_task("agent-a", "t1")
        assert outcome["status"] == "not_found"
        assert "must be claimed" in outcome.get("error", "").lower()

    def test_complete_unknown_task_fails(self):
        s = _make_session(list(SAMPLE_TASKS))
        outcome = s.complete_task("agent-a", "nonexistent")
        assert outcome["status"] == "not_found"

    def test_complete_with_result_flag(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        outcome = s.complete_task("agent-a", "t1", result={"fixed": True})
        assert outcome["status"] == "completed"
        assert outcome["result_stored"] is True


# ---------------------------------------------------------------------------
# TestQueueStatus
# ---------------------------------------------------------------------------


class TestQueueStatus:
    def test_queue_status_empty(self):
        s = _make_session(tasks=None)
        status = s.queue_status()
        assert status["total"] == 0
        assert status["pending_count"] == 0
        assert status["claimed_count"] == 0

    def test_queue_status_mixed_states(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        s.claim_task("agent-b", task_id="t2")
        s.complete_task("agent-b", "t2")
        status = s.queue_status()
        assert status["total"] == 3
        assert status["claimed_count"] == 1
        assert status["completed_count"] == 1
        assert status["pending_count"] == 1

    def test_queue_status_counts_consistent(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a")
        status = s.queue_status()
        total = (
            status["pending_count"]
            + status["claimed_count"]
            + status["completed_count"]
            + status["failed_count"]
        )
        assert total == status["total"]

    def test_queue_status_includes_agent_in_claimed(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        status = s.queue_status()
        claimed = status["claimed_tasks"]
        assert len(claimed) == 1
        assert claimed[0]["agent_id"] == "agent-a"
        assert claimed[0]["id"] == "t1"


# ---------------------------------------------------------------------------
# TestTasksRemaining (updated semantics)
# ---------------------------------------------------------------------------


class TestTasksRemaining:
    def test_remaining_excludes_completed(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.completed_task_ids.append("t1")
        assert s.tasks_remaining() == 2

    def test_remaining_excludes_failed(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.failed_task_ids.append("t2")
        assert s.tasks_remaining() == 2

    def test_remaining_includes_claimed(self):
        """Claimed tasks are 'in progress' — they count toward remaining."""
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        # claimed is not completed/failed → still counts as remaining
        assert s.tasks_remaining() == 3

    def test_remaining_zero_when_all_done_or_failed(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.completed_task_ids.extend(["t1", "t2"])
        s.failed_task_ids.append("t3")
        assert s.tasks_remaining() == 0


# ---------------------------------------------------------------------------
# TestToFromDict (round-trip with lease fields)
# ---------------------------------------------------------------------------


class TestToFromDict:
    def test_round_trip_preserves_lease_fields(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        s.failed_task_ids.append("t3")
        s.task_reclaim_counts["t3"] = 3

        data = s.to_dict()
        restored = DriftSession.from_dict(data)

        assert restored.active_leases == s.active_leases
        assert restored.failed_task_ids == s.failed_task_ids
        assert restored.task_reclaim_counts == s.task_reclaim_counts

    def test_from_dict_backward_compat_no_lease_fields(self):
        """Old sessions without lease fields should load cleanly."""
        data = {
            "session_id": "old-session",
            "repo_path": "/tmp/repo",
            "created_at": time.time(),
            "last_activity": time.time(),
            "completed_task_ids": ["t1"],
        }
        s = DriftSession.from_dict(data)
        assert s.active_leases == {}
        assert s.failed_task_ids == []
        assert s.task_reclaim_counts == {}
        assert s.completed_task_ids == ["t1"]

    def test_summary_includes_claimed_and_failed_counts(self):
        s = _make_session(list(SAMPLE_TASKS))
        s.claim_task("agent-a", task_id="t1")
        s.failed_task_ids.append("t3")
        summary = s.summary()
        tq = summary["task_queue"]
        assert tq["claimed"] == 1
        assert tq["failed"] == 1
        assert tq["completed"] == 0
        assert tq["remaining"] == 2  # t2 pending, t1 claimed (still remaining)
