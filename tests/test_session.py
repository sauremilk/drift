"""Unit tests for drift.session — DriftSession + SessionManager.

Decision: ADR-022
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from drift.session import DriftSession, SessionManager


@pytest.fixture(autouse=True)
def _reset_manager():
    """Ensure a fresh SessionManager for every test."""
    SessionManager.reset_instance()
    yield
    SessionManager.reset_instance()


# ---------------------------------------------------------------------------
# DriftSession unit tests
# ---------------------------------------------------------------------------


class TestDriftSession:
    def test_is_valid_fresh(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        assert s.is_valid()

    def test_is_valid_expired(self):
        s = DriftSession(
            session_id="abc",
            repo_path="/tmp/repo",
            last_activity=time.time() - 3600,
            ttl_seconds=60,
        )
        assert not s.is_valid()

    def test_touch_updates_activity_and_counter(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        old_activity = s.last_activity
        old_calls = s.tool_calls
        # Tiny sleep to ensure timestamps differ
        time.sleep(0.01)
        s.touch()
        assert s.last_activity >= old_activity
        assert s.tool_calls == old_calls + 1

    def test_tasks_remaining_empty(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        assert s.tasks_remaining() == 0

    def test_tasks_remaining_with_tasks(self):
        s = DriftSession(
            session_id="abc",
            repo_path="/tmp/repo",
            selected_tasks=[
                {"id": "t1", "signal": "PFS"},
                {"id": "t2", "signal": "AVS"},
                {"id": "t3", "signal": "MDS"},
            ],
            completed_task_ids=["t1"],
        )
        assert s.tasks_remaining() == 2

    def test_scope_label_default(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        assert s.scope_label() == "all"

    def test_scope_label_with_filters(self):
        s = DriftSession(
            session_id="abc",
            repo_path="/tmp/repo",
            signals=["PFS", "AVS"],
            target_path="backend/",
        )
        label = s.scope_label()
        assert "PFS" in label
        assert "backend/" in label

    def test_summary_contains_key_fields(self):
        s = DriftSession(
            session_id="abc123",
            repo_path="/tmp/repo",
            last_scan_score=42.5,
        )
        summary = s.summary()
        assert summary["session_id"] == "abc123"
        assert summary["valid"] is True
        assert summary["last_scan"]["score"] == 42.5
        assert "task_queue" in summary
        assert "ttl_remaining_seconds" in summary

    def test_end_summary_with_score_delta(self):
        s = DriftSession(
            session_id="abc",
            repo_path="/tmp/repo",
            score_at_start=50.0,
            last_scan_score=38.0,
        )
        summary = s.end_summary()
        assert summary["score_start"] == 50.0
        assert summary["score_end"] == 38.0
        assert summary["score_delta"] == -12.0

    def test_begin_call_and_touch_timing(self):
        """WP-4: begin_call + touch track tool and inter-call timing."""
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        # Simulate first tool call
        s.begin_call()
        time.sleep(0.02)
        s.touch()
        # _total_tool_ms should be > 0 now
        assert s._total_tool_ms > 10  # at least 10ms
        # _total_inter_call_ms should still be ~0 (no previous call)
        assert s._total_inter_call_ms == 0.0

        # Simulate agent thinking for a bit, then second tool call
        time.sleep(0.02)
        s.begin_call()
        # inter_call gap should now be recorded
        assert s._total_inter_call_ms > 10  # at least 10ms gap
        time.sleep(0.02)
        s.touch()
        # Both totals should be positive now
        assert s._total_tool_ms > 20
        assert s.tool_calls == 2

    def test_end_summary_includes_timing(self):
        """WP-4: end_summary includes timing breakdown when calls recorded."""
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        s.begin_call()
        time.sleep(0.01)
        s.touch()
        time.sleep(0.01)
        s.begin_call()
        time.sleep(0.01)
        s.touch()

        summary = s.end_summary()
        assert "timing" in summary
        timing = summary["timing"]
        assert timing["total_tool_ms"] > 0
        assert timing["total_inter_call_ms"] > 0
        assert timing["total_wall_ms"] > 0
        assert 0 <= timing["tool_pct"] <= 100

    def test_to_dict_from_dict_roundtrip(self):
        s = DriftSession(
            session_id="abc",
            repo_path="/tmp/repo",
            signals=["PFS"],
            selected_tasks=[{"id": "t1"}],
            completed_task_ids=["t1"],
        )
        data = s.to_dict()
        restored = DriftSession.from_dict(data)
        assert restored.session_id == s.session_id
        assert restored.repo_path == s.repo_path
        assert restored.signals == s.signals
        assert restored.completed_task_ids == s.completed_task_ids


# ---------------------------------------------------------------------------
# SessionManager unit tests
# ---------------------------------------------------------------------------


class TestSessionManager:
    def test_singleton(self):
        mgr1 = SessionManager.instance()
        mgr2 = SessionManager.instance()
        assert mgr1 is mgr2

    def test_create_returns_session_id(self):
        mgr = SessionManager.instance()
        sid = mgr.create("/tmp/repo")
        assert isinstance(sid, str)
        assert len(sid) == 32  # hex UUID4

    def test_get_valid_session(self):
        mgr = SessionManager.instance()
        sid = mgr.create("/tmp/repo", signals=["PFS"])
        session = mgr.get(sid)
        assert session is not None
        assert session.signals == ["PFS"]

    def test_get_unknown_session_returns_none(self):
        mgr = SessionManager.instance()
        assert mgr.get("nonexistent") is None

    def test_get_expired_session_returns_none(self):
        mgr = SessionManager.instance()
        sid = mgr.create("/tmp/repo", ttl_seconds=0)
        # Force expiry by backdating last_activity
        session = mgr._sessions[sid]
        session.last_activity = time.time() - 10
        assert mgr.get(sid) is None

    def test_update_modifies_fields(self):
        mgr = SessionManager.instance()
        sid = mgr.create("/tmp/repo")
        mgr.update(sid, signals=["AVS", "MDS"])
        session = mgr.get(sid)
        assert session is not None
        assert session.signals == ["AVS", "MDS"]

    def test_update_ignores_unknown_fields(self):
        mgr = SessionManager.instance()
        sid = mgr.create("/tmp/repo")
        mgr.update(sid, nonexistent_field="value")
        session = mgr.get(sid)
        assert session is not None
        assert (
            not hasattr(session, "nonexistent_field")
            or getattr(session, "nonexistent_field", None) != "value"
        )

    def test_destroy_returns_summary(self):
        mgr = SessionManager.instance()
        sid = mgr.create("/tmp/repo")
        summary = mgr.destroy(sid)
        assert summary is not None
        assert summary["session_id"] == sid
        assert "duration_seconds" in summary
        # Session should be gone
        assert mgr.get(sid) is None

    def test_destroy_unknown_returns_none(self):
        mgr = SessionManager.instance()
        assert mgr.destroy("nonexistent") is None

    def test_list_active(self):
        mgr = SessionManager.instance()
        sid1 = mgr.create("/tmp/repo1")
        sid2 = mgr.create("/tmp/repo2")
        active = mgr.list_active()
        ids = {s["session_id"] for s in active}
        assert sid1 in ids
        assert sid2 in ids

    def test_prune_expired(self):
        mgr = SessionManager.instance()
        sid = mgr.create("/tmp/repo", ttl_seconds=0)
        mgr._sessions[sid].last_activity = time.time() - 10
        pruned = mgr.prune_expired()
        assert pruned == 1
        assert mgr.get(sid) is None

    def test_multiple_sessions_per_repo(self):
        mgr = SessionManager.instance()
        sid1 = mgr.create("/tmp/repo")
        sid2 = mgr.create("/tmp/repo")
        assert sid1 != sid2
        assert mgr.get(sid1) is not None
        assert mgr.get(sid2) is not None

    def test_save_to_disk_and_load(self, tmp_path: Path):
        mgr = SessionManager.instance()
        sid = mgr.create(str(tmp_path), signals=["PFS"])
        session = mgr.get(sid)
        assert session is not None
        session.last_scan_score = 42.0

        filepath = mgr.save_to_disk(sid, directory=tmp_path)
        assert filepath is not None
        assert filepath.exists()

        # Verify JSON content
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["session_id"] == sid
        assert data["signals"] == ["PFS"]

        # Load into a fresh manager
        SessionManager.reset_instance()
        mgr2 = SessionManager.instance()
        loaded_sid = mgr2.load_from_disk(filepath)
        assert loaded_sid is not None
        assert loaded_sid == sid
        loaded = mgr2.get(loaded_sid)
        assert loaded is not None
        assert loaded.signals == ["PFS"]
        assert loaded.last_scan_score == 42.0

    def test_load_from_disk_nonexistent(self):
        mgr = SessionManager.instance()
        assert mgr.load_from_disk("/nonexistent/path.json") is None

    def test_load_from_disk_invalid_json(self, tmp_path: Path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json", encoding="utf-8")
        mgr = SessionManager.instance()
        assert mgr.load_from_disk(bad_file) is None

    # -- Issue 373: mutable input isolation ---------------------------------

    def test_create_isolates_signals_list(self):
        mgr = SessionManager.instance()
        signals = ["PFS", "AVS"]
        sid = mgr.create("/tmp/repo", signals=signals)
        signals.append("CLK")
        session = mgr.get(sid)
        assert session is not None
        assert session.signals == ["PFS", "AVS"], (
            "mutation after create must not affect stored signals"
        )

    def test_create_isolates_exclude_paths_list(self):
        mgr = SessionManager.instance()
        exclude = ["tests/", "docs/"]
        sid = mgr.create("/tmp/repo", exclude_paths=exclude)
        exclude.append("build/")
        session = mgr.get(sid)
        assert session is not None
        assert session.exclude_paths == ["tests/", "docs/"]

    def test_update_isolates_selected_tasks_list(self):
        mgr = SessionManager.instance()
        sid = mgr.create("/tmp/repo")
        tasks = [{"id": "T1", "title": "task one"}]
        mgr.update(sid, selected_tasks=tasks)
        tasks.append({"id": "T2", "title": "intruder"})
        session = mgr.get(sid)
        assert session is not None
        assert len(session.selected_tasks) == 1
        assert session.selected_tasks[0]["id"] == "T1"

    def test_update_isolates_completed_task_ids_list(self):
        mgr = SessionManager.instance()
        sid = mgr.create("/tmp/repo")
        completed = ["T1"]
        mgr.update(sid, completed_task_ids=completed)
        completed.append("T2")
        session = mgr.get(sid)
        assert session is not None
        assert session.completed_task_ids == ["T1"]

    def test_shared_payload_does_not_bleed_across_sessions(self):
        mgr = SessionManager.instance()
        signals = ["PFS"]
        sid1 = mgr.create("/tmp/repo1", signals=signals)
        sid2 = mgr.create("/tmp/repo2", signals=signals)
        signals.append("AVS")
        s1 = mgr.get(sid1)
        s2 = mgr.get(sid2)
        assert s1 is not None and s2 is not None
        assert s1.signals == ["PFS"]
        assert s2.signals == ["PFS"]
