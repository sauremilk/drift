"""Unit tests for drift.session — DriftSession + SessionManager.

Decision: ADR-022
"""

from __future__ import annotations

import json
import logging
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


# ---------------------------------------------------------------------------
# Queue-log write hooks (ADR-078)
# ---------------------------------------------------------------------------


class TestQueueLogHooks:
    def test_claim_complete_emits_events(self, tmp_path: Path) -> None:
        from drift.session_queue_log import log_path, replay_events

        mgr = SessionManager.instance()
        sid = mgr.create(str(tmp_path))
        session = mgr.get(sid)
        assert session is not None
        session.selected_tasks = [{"id": "T1", "signal": "AVS"}]

        claim = session.claim_task(agent_id="bob", task_id="T1")
        assert claim is not None
        result = session.complete_task(agent_id="bob", task_id="T1")
        assert result["status"] == "completed"

        assert log_path(tmp_path).exists()
        events = replay_events(tmp_path)
        types = [e.type for e in events]
        assert "task_claimed" in types
        assert "task_completed" in types

    def test_release_emits_released_event(self, tmp_path: Path) -> None:
        from drift.session_queue_log import replay_events

        mgr = SessionManager.instance()
        sid = mgr.create(str(tmp_path))
        session = mgr.get(sid)
        assert session is not None
        session.selected_tasks = [{"id": "T1"}]
        session.claim_task(agent_id="bob", task_id="T1")
        session.release_task(agent_id="bob", task_id="T1")

        events = replay_events(tmp_path)
        types = [e.type for e in events]
        assert "task_released" in types

    def test_release_beyond_max_reclaim_emits_failed_event(
        self, tmp_path: Path
    ) -> None:
        from drift.session_queue_log import replay_events

        mgr = SessionManager.instance()
        sid = mgr.create(str(tmp_path))
        session = mgr.get(sid)
        assert session is not None
        session.selected_tasks = [{"id": "T1"}]
        for _ in range(2):
            session.claim_task(
                agent_id="bob", task_id="T1", max_reclaim=2
            )
            session.release_task(
                agent_id="bob", task_id="T1", max_reclaim=2
            )
        events = replay_events(tmp_path)
        assert "task_failed" in {e.type for e in events}


# ---------------------------------------------------------------------------
# Restart-replay integration (ADR-078)
# ---------------------------------------------------------------------------


class TestRestartReplay:
    def test_new_session_resumes_queue_from_log(self, tmp_path: Path) -> None:
        import asyncio

        from drift.mcp_router_session import run_session_start
        from drift.session_queue_log import QueueEvent, append_event

        # Seed log as if a previous session had built a plan and completed one task
        append_event(
            tmp_path,
            QueueEvent(
                type="plan_created",
                session_id="old-session",
                payload={"tasks": [{"id": "A"}, {"id": "B"}, {"id": "C"}]},
            ),
        )
        append_event(
            tmp_path,
            QueueEvent(
                type="task_completed",
                session_id="old-session",
                payload={"task_id": "A"},
            ),
        )

        SessionManager.reset_instance()
        raw = asyncio.run(
            run_session_start(
                path=str(tmp_path),
                signals=None,
                exclude_signals=None,
                target_path=None,
                exclude_paths=None,
                ttl_seconds=60,
                autopilot=False,
                autopilot_payload="summary",
                response_profile=None,
                fresh_start=False,
            )
        )
        data = json.loads(raw)
        assert data["resumed_from_log"] is True
        assert data["resumed_tasks"] == 3
        assert data["resumed_completed"] == 1

        new_sid = data["session_id"]
        session = SessionManager.instance().get(new_sid)
        assert session is not None
        assert session.selected_tasks is not None
        assert [t["id"] for t in session.selected_tasks] == ["A", "B", "C"]
        assert session.completed_task_ids == ["A"]

    def test_fresh_start_skips_replay(self, tmp_path: Path) -> None:
        import asyncio

        from drift.mcp_router_session import run_session_start
        from drift.session_queue_log import QueueEvent, append_event

        append_event(
            tmp_path,
            QueueEvent(
                type="plan_created",
                session_id="old",
                payload={"tasks": [{"id": "A"}]},
            ),
        )

        SessionManager.reset_instance()
        raw = asyncio.run(
            run_session_start(
                path=str(tmp_path),
                signals=None,
                exclude_signals=None,
                target_path=None,
                exclude_paths=None,
                ttl_seconds=60,
                autopilot=False,
                autopilot_payload="summary",
                response_profile=None,
                fresh_start=True,
            )
        )
        data = json.loads(raw)
        assert data["resumed_from_log"] is False
        assert data["resumed_tasks"] == 0
        session = SessionManager.instance().get(data["session_id"])
        assert session is not None
        assert not session.selected_tasks

    def test_no_log_yields_no_resume(self, tmp_path: Path) -> None:
        import asyncio

        from drift.mcp_router_session import run_session_start

        SessionManager.reset_instance()
        raw = asyncio.run(
            run_session_start(
                path=str(tmp_path),
                signals=None,
                exclude_signals=None,
                target_path=None,
                exclude_paths=None,
                ttl_seconds=60,
                autopilot=False,
                autopilot_payload="summary",
                response_profile=None,
                fresh_start=False,
            )
        )
        data = json.loads(raw)
        assert data["resumed_from_log"] is False
        assert data["resumed_tasks"] == 0


# ---------------------------------------------------------------------------
# Plan-staleness surfacing (ADR-081 Nachschärfung, Q2)
# ---------------------------------------------------------------------------


class TestResumedPlanStaleness:
    """``run_session_start`` surfaces plan age on replay so agents can
    choose to re-plan rather than follow a stale queue."""

    def _seed_plan(self, repo: Path, *, ts: float) -> None:
        from drift.session_queue_log import QueueEvent, append_event

        append_event(
            repo,
            QueueEvent(
                type="plan_created",
                session_id="old-session",
                timestamp=ts,
                payload={"tasks": [{"id": "A"}, {"id": "B"}]},
            ),
        )

    def _start_session(self, repo: Path) -> dict[str, object]:
        import asyncio

        from drift.mcp_router_session import run_session_start

        SessionManager.reset_instance()
        raw = asyncio.run(
            run_session_start(
                path=str(repo),
                signals=None,
                exclude_signals=None,
                target_path=None,
                exclude_paths=None,
                ttl_seconds=60,
                autopilot=False,
                autopilot_payload="summary",
                response_profile=None,
                fresh_start=False,
            )
        )
        return json.loads(raw)

    def test_fresh_plan_reports_age_and_not_stale(self, tmp_path: Path) -> None:
        import time as _t

        self._seed_plan(tmp_path, ts=_t.time() - 60.0)  # 1 min ago
        data = self._start_session(tmp_path)

        assert data["resumed_from_log"] is True
        assert data["resumed_plan_stale"] is False
        assert isinstance(data["resumed_plan_created_at"], float)
        assert isinstance(data["resumed_plan_age_seconds"], float)
        assert data["resumed_plan_age_seconds"] < 3600.0
        # Fresh plan with pending tasks: P5 routes straight to fix_apply
        # (see TestResumedNextToolCall); stale-override does not kick in.
        assert data["next_tool_call"]["tool"] == "drift_fix_apply"

    def test_stale_plan_flips_stale_and_redirects_next_tool_call(
        self, tmp_path: Path
    ) -> None:
        import time as _t

        # 48 h old — well beyond the 24 h default threshold
        self._seed_plan(tmp_path, ts=_t.time() - 48 * 3600.0)
        data = self._start_session(tmp_path)

        assert data["resumed_from_log"] is True
        assert data["resumed_plan_stale"] is True
        assert data["resumed_plan_age_seconds"] is not None
        assert data["resumed_plan_age_seconds"] > 24 * 3600.0
        assert data["next_tool_call"]["tool"] == "drift_fix_plan"
        assert data["fallback_tool_call"]["tool"] == "drift_scan"
        assert "stale" in data["agent_instruction"].lower()
        assert "drift_fix_plan" in data["agent_instruction"]

    def test_env_override_lowers_staleness_threshold(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """DRIFT_QUEUE_STALE_SECONDS lowers the threshold so tests / projects
        with fast cadence can tune the heuristic."""
        import time as _t

        # Lower threshold to 60 s so a 5-minute-old plan is stale
        monkeypatch.setenv("DRIFT_QUEUE_STALE_SECONDS", "60")
        self._seed_plan(tmp_path, ts=_t.time() - 300.0)
        data = self._start_session(tmp_path)

        assert data["resumed_plan_stale"] is True
        assert data["next_tool_call"]["tool"] == "drift_fix_plan"

    def test_env_override_invalid_falls_back_to_default(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        import time as _t

        monkeypatch.setenv("DRIFT_QUEUE_STALE_SECONDS", "not-a-number")
        # 1 min old plan — would be stale only with a sub-minute override,
        # so with the default 24 h threshold it must still be fresh.
        self._seed_plan(tmp_path, ts=_t.time() - 60.0)
        data = self._start_session(tmp_path)

        assert data["resumed_plan_stale"] is False

    def test_env_override_non_positive_falls_back_to_default(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        import time as _t

        monkeypatch.setenv("DRIFT_QUEUE_STALE_SECONDS", "0")
        self._seed_plan(tmp_path, ts=_t.time() - 60.0)
        data = self._start_session(tmp_path)

        assert data["resumed_plan_stale"] is False

    def test_fresh_start_skips_plan_age_metadata(self, tmp_path: Path) -> None:
        """``fresh_start=true`` must not surface replay metadata at all."""
        import asyncio
        import time as _t

        from drift.mcp_router_session import run_session_start

        self._seed_plan(tmp_path, ts=_t.time() - 48 * 3600.0)

        SessionManager.reset_instance()
        raw = asyncio.run(
            run_session_start(
                path=str(tmp_path),
                signals=None,
                exclude_signals=None,
                target_path=None,
                exclude_paths=None,
                ttl_seconds=60,
                autopilot=False,
                autopilot_payload="summary",
                response_profile=None,
                fresh_start=True,
            )
        )
        data = json.loads(raw)
        assert data["resumed_from_log"] is False
        assert data["resumed_plan_stale"] is False
        assert data["resumed_plan_age_seconds"] is None
        assert data["resumed_plan_created_at"] is None
        # Fresh start must not redirect next_tool_call
        assert data["next_tool_call"]["tool"] == "drift_scan"

    def test_empty_log_yields_none_plan_metadata(self, tmp_path: Path) -> None:
        """No queue log → plan-age fields stay None, stale False, default nav."""
        import asyncio

        from drift.mcp_router_session import run_session_start

        SessionManager.reset_instance()
        raw = asyncio.run(
            run_session_start(
                path=str(tmp_path),
                signals=None,
                exclude_signals=None,
                target_path=None,
                exclude_paths=None,
                ttl_seconds=60,
                autopilot=False,
                autopilot_payload="summary",
                response_profile=None,
                fresh_start=False,
            )
        )
        data = json.loads(raw)
        assert data["resumed_plan_created_at"] is None
        assert data["resumed_plan_age_seconds"] is None
        assert data["resumed_plan_stale"] is False
        assert data["next_tool_call"]["tool"] == "drift_scan"
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

    def test_create_rejects_when_max_sessions_reached(self):
        mgr = SessionManager(max_sessions=2)
        mgr.create("/tmp/repo1")
        mgr.create("/tmp/repo2")

        with pytest.raises(RuntimeError, match="DRIFT-4000"):
            mgr.create("/tmp/repo3")

    def test_create_logs_warning_near_capacity(self, caplog: pytest.LogCaptureFixture):
        mgr = SessionManager(max_sessions=5, warning_threshold_ratio=0.8)
        caplog.set_level(logging.WARNING, logger="drift")

        mgr.create("/tmp/repo1")
        mgr.create("/tmp/repo2")
        mgr.create("/tmp/repo3")
        mgr.create("/tmp/repo4")

        assert any(
            "Session capacity warning" in message
            for message in caplog.messages
        )


# ---------------------------------------------------------------------------
# Concurrent-writer advisory (ADR-081 Q3)
# ---------------------------------------------------------------------------


class TestConcurrentWriterAdvisory:
    """``run_session_start`` surfaces a live previous writer so operators
    can pause a competing session; release happens on ``run_session_end``.
    """

    def _start(self, repo: Path, *, session_id_hint: str | None = None):
        import asyncio

        from drift.mcp_router_session import run_session_start

        SessionManager.reset_instance()
        raw = asyncio.run(
            run_session_start(
                path=str(repo),
                signals=None,
                exclude_signals=None,
                target_path=None,
                exclude_paths=None,
                ttl_seconds=60,
                autopilot=False,
                autopilot_payload="summary",
                response_profile=None,
                fresh_start=False,
            )
        )
        return json.loads(raw)

    def test_no_lockfile_reports_no_concurrent_writer(self, tmp_path: Path) -> None:
        data = self._start(tmp_path)
        assert data["concurrent_sessions_detected"] is False
        assert data["concurrent_writer"] is None

    def test_live_previous_writer_is_surfaced(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        import os as _os

        from drift.session_writer_lock import _lock_path

        # Seed a lockfile that looks like a live, foreign session.
        path = _lock_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "pid": _os.getpid(),  # our pid → guaranteed alive
                    "session_id": "foreign-session-1234",
                    "started_at": time.time() - 5.0,
                }
            ),
            encoding="utf-8",
        )

        data = self._start(tmp_path)

        assert data["concurrent_sessions_detected"] is True
        assert data["concurrent_writer"] is not None
        assert data["concurrent_writer"]["session_id"] == "foreign-session-1234"
        assert data["concurrent_writer"]["pid"] == _os.getpid()
        assert "Concurrent writer detected" in data["agent_instruction"]

    def test_dead_pid_holder_is_ignored(self, tmp_path: Path) -> None:
        from drift.session_writer_lock import _lock_path

        path = _lock_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "pid": 2**31 - 2,  # highly improbable / dead
                    "session_id": "ghost-session",
                    "started_at": time.time(),
                }
            ),
            encoding="utf-8",
        )

        data = self._start(tmp_path)

        assert data["concurrent_sessions_detected"] is False
        assert data["concurrent_writer"] is None

    def test_session_start_always_takes_ownership(self, tmp_path: Path) -> None:
        """ADR-081 'last session wins' — lockfile is overwritten on start."""
        import json as _json

        from drift.session_writer_lock import _lock_path

        # Pre-seed with a stale lockfile.
        _lock_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        _lock_path(tmp_path).write_text(
            _json.dumps(
                {
                    "pid": 2**31 - 2,
                    "session_id": "previous",
                    "started_at": time.time() - 10.0,
                }
            ),
            encoding="utf-8",
        )

        data = self._start(tmp_path)

        # After session start, the lockfile belongs to the new session.
        after = _json.loads(_lock_path(tmp_path).read_text(encoding="utf-8"))
        assert after["session_id"] == data["session_id"]

    def test_session_end_releases_writer_advisory(self, tmp_path: Path) -> None:
        import asyncio

        from drift.mcp_router_session import run_session_end, run_session_start
        from drift.session_writer_lock import _lock_path

        SessionManager.reset_instance()
        start_raw = asyncio.run(
            run_session_start(
                path=str(tmp_path),
                signals=None,
                exclude_signals=None,
                target_path=None,
                exclude_paths=None,
                ttl_seconds=60,
                autopilot=False,
                autopilot_payload="summary",
                response_profile=None,
                fresh_start=False,
            )
        )
        session_id = json.loads(start_raw)["session_id"]
        assert _lock_path(tmp_path).exists()

        def _err(code: str, msg: str, sid: str) -> str:
            return json.dumps({"error": code, "msg": msg, "sid": sid})

        asyncio.run(
            run_session_end(
                session_id=session_id,
                session_error_response=_err,
                force=True,
                bypass_reason=(
                    "chore: release writer-advisory lock in test so the "
                    "next session on this repo does not see us as holder."
                ),
            )
        )

        assert not _lock_path(tmp_path).exists()


# ---------------------------------------------------------------------------
# Resume-UX routing (ADR-081 Q5) and replan-semantics counter (Q4)
# ---------------------------------------------------------------------------


class TestResumedNextToolCall:
    """When replay restores pending tasks, ``next_tool_call`` should route
    the agent straight to ``drift_fix_apply``.  Stale plans (Q2) and
    empty queues continue to use the defaults.
    """

    def _seed_plan(
        self,
        repo: Path,
        *,
        tasks: list[dict],
        ts: float | None = None,
        session_id: str = "prev",
    ) -> None:
        from drift.session_queue_log import QueueEvent, append_event

        append_event(
            repo,
            QueueEvent(
                type="plan_created",
                session_id=session_id,
                timestamp=ts if ts is not None else time.time() - 60.0,
                payload={"tasks": tasks},
            ),
        )

    def _start(self, repo: Path) -> dict:
        import asyncio

        from drift.mcp_router_session import run_session_start

        SessionManager.reset_instance()
        raw = asyncio.run(
            run_session_start(
                path=str(repo),
                signals=None,
                exclude_signals=None,
                target_path=None,
                exclude_paths=None,
                ttl_seconds=60,
                autopilot=False,
                autopilot_payload="summary",
                response_profile=None,
                fresh_start=False,
            )
        )
        return json.loads(raw)

    def test_fresh_resume_points_next_tool_call_at_fix_apply(
        self, tmp_path: Path
    ) -> None:
        self._seed_plan(
            tmp_path,
            tasks=[
                {"id": "A", "priority_score": 0.5},
                {"id": "B", "priority_score": 0.9},
                {"id": "C", "priority_score": 0.2},
            ],
        )

        data = self._start(tmp_path)

        assert data["resumed_from_log"] is True
        assert data["resumed_tasks"] == 3
        # B has the highest priority_score → routed first.
        assert data["resumed_next_task_id"] == "B"
        assert data["next_tool_call"]["tool"] == "drift_fix_apply"
        assert data["next_tool_call"]["params"]["task_id"] == "B"
        assert data["fallback_tool_call"]["tool"] == "drift_fix_plan"

    def test_priority_ties_break_by_original_order(self, tmp_path: Path) -> None:
        self._seed_plan(
            tmp_path,
            tasks=[
                {"id": "A", "priority_score": 0.5},
                {"id": "B", "priority_score": 0.5},
            ],
        )

        data = self._start(tmp_path)

        assert data["resumed_next_task_id"] == "A"

    def test_missing_priority_score_falls_back_to_zero(self, tmp_path: Path) -> None:
        self._seed_plan(
            tmp_path,
            tasks=[
                {"id": "A"},
                {"id": "B", "priority_score": 0.1},
            ],
        )

        data = self._start(tmp_path)

        assert data["resumed_next_task_id"] == "B"

    def test_completed_tasks_are_skipped(self, tmp_path: Path) -> None:
        from drift.session_queue_log import QueueEvent, append_event

        ts = time.time() - 60.0
        self._seed_plan(
            tmp_path,
            ts=ts,
            tasks=[
                {"id": "A", "priority_score": 0.9},
                {"id": "B", "priority_score": 0.1},
            ],
        )
        append_event(
            tmp_path,
            QueueEvent(
                type="task_completed",
                session_id="prev",
                timestamp=ts + 1.0,
                payload={"task_id": "A"},
            ),
        )

        data = self._start(tmp_path)

        assert data["resumed_next_task_id"] == "B"
        assert data["next_tool_call"]["params"]["task_id"] == "B"

    def test_all_tasks_terminal_yields_no_next_task_redirect(
        self, tmp_path: Path
    ) -> None:
        """When no pending task remains after replay, fall back to
        ``selected_tasks`` default (``drift_scan``) — the plan is a
        finished artifact, not active work."""
        from drift.session_queue_log import QueueEvent, append_event

        ts = time.time() - 60.0
        self._seed_plan(
            tmp_path,
            ts=ts,
            tasks=[{"id": "A", "priority_score": 0.5}],
        )
        append_event(
            tmp_path,
            QueueEvent(
                type="task_completed",
                session_id="prev",
                timestamp=ts + 1.0,
                payload={"task_id": "A"},
            ),
        )

        data = self._start(tmp_path)

        assert data["resumed_from_log"] is True
        assert data["resumed_next_task_id"] is None
        # No pending work → default ``drift_scan`` route unchanged.
        assert data["next_tool_call"]["tool"] == "drift_scan"

    def test_stale_plan_wins_over_fix_apply_routing(self, tmp_path: Path) -> None:
        """Q2 stale-override must take precedence over Q5 fix-apply routing."""
        self._seed_plan(
            tmp_path,
            tasks=[{"id": "A", "priority_score": 0.5}],
            ts=time.time() - 48 * 3600.0,  # 48 h old
        )

        data = self._start(tmp_path)

        assert data["resumed_plan_stale"] is True
        # Stale wins — agent must re-plan before touching fix_apply.
        assert data["next_tool_call"]["tool"] == "drift_fix_plan"
        assert data["fallback_tool_call"]["tool"] == "drift_scan"

    def test_resumed_older_plans_counter_tracks_discards(
        self, tmp_path: Path
    ) -> None:
        """Q4: count of older plan_created events discarded during replay."""
        from drift.session_queue_log import QueueEvent, append_event

        base = time.time() - 3600.0
        for idx, ts in enumerate([base, base + 10.0, base + 20.0]):
            append_event(
                tmp_path,
                QueueEvent(
                    type="plan_created",
                    session_id=f"plan-{idx}",
                    timestamp=ts,
                    payload={"tasks": [{"id": f"task-{idx}"}]},
                ),
            )

        data = self._start(tmp_path)

        # Latest plan (index 2) wins; two older plans were discarded.
        assert data["resumed_older_plans_discarded"] == 2
        assert data["resumed_next_task_id"] == "task-2"

    def test_no_queue_yields_zero_discards_and_no_redirect(
        self, tmp_path: Path
    ) -> None:
        data = self._start(tmp_path)

        assert data["resumed_older_plans_discarded"] == 0
        assert data["resumed_next_task_id"] is None
        assert data["next_tool_call"]["tool"] == "drift_scan"
