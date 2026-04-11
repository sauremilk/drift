from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import drift.mcp_server as mcp_server


def _run(coro):
    return json.loads(asyncio.run(coro))


class _FakeSession:
    def __init__(self) -> None:
        self.completed_task_ids = ["done-1"]
        self.trace = [{"tool": "scan"}]
        self.phase = "fixing"

    def summary(self):
        return {"session_id": "sid", "tool_calls": 2, "duration_seconds": 12}

    def tasks_remaining(self):
        return 2

    def scope_label(self):
        return "repo:."

    def queue_status(self):
        return {
            "pending_count": 1,
            "claimed_count": 1,
            "completed_count": 1,
            "failed_count": 0,
        }

    def claim_task(self, **kwargs):
        return {
            "task": {"id": "t-1", "title": "fix"},
            "lease": {"task_id": "t-1", "agent_id": kwargs["agent_id"]},
        }

    def renew_lease(self, **kwargs):
        if kwargs["task_id"] == "missing":
            return {"status": "not_found", "error": "missing"}
        return {"status": "renewed", "task_id": kwargs["task_id"]}

    def release_task(self, **kwargs):
        if kwargs["task_id"] == "failed":
            return {"status": "failed"}
        if kwargs["task_id"] == "bad":
            return {"status": "error", "error": "cannot"}
        return {"status": "released", "reclaim_count": 1}

    def complete_task(self, **kwargs):
        if kwargs["task_id"] == "again":
            return {"status": "already_completed"}
        if kwargs["task_id"] == "bad":
            return {"status": "error", "error": "cannot"}
        return {"status": "completed"}

    def touch(self):
        return None


class _FakeManager:
    def __init__(self, session: _FakeSession | None) -> None:
        self._session = session
        self.updated = None

    def get(self, _sid: str):
        return self._session

    def update(self, sid: str, **updates):
        self.updated = (sid, updates)

    def save_to_disk(self, sid: str):
        return Path(f".drift-session-{sid}.json")

    def destroy(self, sid: str):
        if sid == "missing":
            return None
        return {"tool_calls": 1, "duration_seconds": 1}


def _patch_session_manager(monkeypatch: pytest.MonkeyPatch, manager) -> None:
    import drift.session as sess

    monkeypatch.setattr(sess.SessionManager, "instance", classmethod(lambda cls: manager))


def test_session_update_status_end_trace_and_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    manager = _FakeManager(session)
    _patch_session_manager(monkeypatch, manager)
    monkeypatch.setattr(mcp_server, "_strict_guardrail_block_response", lambda *_a, **_k: None)

    updated = _run(
        mcp_server.drift_session_update(
            session_id="sid",
            signals="PFS,MDS",
            exclude_signals="AVS",
            target_path="src/drift",
            mark_tasks_complete="a,b",
            save_to_disk=True,
        )
    )
    assert updated["status"] == "ok"
    assert manager.updated is not None

    session_status = _run(mcp_server.drift_session_status(session_id="sid"))
    assert session_status["status"] == "ok"

    task_status = _run(mcp_server.drift_task_status(session_id="sid"))
    assert task_status["pending_count"] == 1

    trace = _run(mcp_server.drift_session_trace(session_id="sid", last_n=10))
    assert trace["returned_entries"] == 1

    claim = _run(mcp_server.drift_task_claim(session_id="sid", agent_id="agent-a"))
    assert claim["status"] == "claimed"

    renew_ok = _run(
        mcp_server.drift_task_renew(session_id="sid", agent_id="agent-a", task_id="t-1")
    )
    assert renew_ok["status"] == "renewed"

    renew_missing = _run(
        mcp_server.drift_task_renew(session_id="sid", agent_id="agent-a", task_id="missing")
    )
    assert renew_missing["status"] == "not_found"

    release_ok = _run(
        mcp_server.drift_task_release(session_id="sid", agent_id="agent-a", task_id="t-1")
    )
    assert release_ok["status"] == "released"

    release_failed = _run(
        mcp_server.drift_task_release(session_id="sid", agent_id="agent-a", task_id="failed")
    )
    assert release_failed["status"] == "failed"

    release_bad = _run(
        mcp_server.drift_task_release(session_id="sid", agent_id="agent-a", task_id="bad")
    )
    assert release_bad["status"] == "error"

    complete_ok = _run(
        mcp_server.drift_task_complete(session_id="sid", agent_id="agent-a", task_id="t-1")
    )
    assert complete_ok["status"] == "completed"

    complete_again = _run(
        mcp_server.drift_task_complete(session_id="sid", agent_id="agent-a", task_id="again")
    )
    assert complete_again["status"] == "already_completed"

    complete_bad = _run(
        mcp_server.drift_task_complete(session_id="sid", agent_id="agent-a", task_id="bad")
    )
    assert complete_bad["status"] == "error"

    ended = _run(mcp_server.drift_session_end(session_id="sid"))
    assert ended["status"] == "ok"


def test_session_not_found_and_no_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _FakeManager(None)
    _patch_session_manager(monkeypatch, manager)

    upd = _run(mcp_server.drift_session_update(session_id="sid"))
    assert upd["type"] == "error"

    sts = _run(mcp_server.drift_session_status(session_id="sid"))
    assert sts["type"] == "error"

    tr = _run(mcp_server.drift_session_trace(session_id="sid"))
    assert tr["type"] == "error"

    cl = _run(mcp_server.drift_task_claim(session_id="sid", agent_id="a"))
    assert cl["type"] == "error"

    rn = _run(mcp_server.drift_task_renew(session_id="sid", agent_id="a", task_id="t"))
    assert rn["type"] == "error"

    rl = _run(mcp_server.drift_task_release(session_id="sid", agent_id="a", task_id="t"))
    assert rl["type"] == "error"

    cp = _run(mcp_server.drift_task_complete(session_id="sid", agent_id="a", task_id="t"))
    assert cp["type"] == "error"

    en = _run(mcp_server.drift_session_end(session_id="missing"))
    assert en["type"] == "error"


def test_task_claim_no_tasks_available(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    session.claim_task = lambda **kwargs: None
    manager = _FakeManager(session)
    _patch_session_manager(monkeypatch, manager)

    out = _run(mcp_server.drift_task_claim(session_id="sid", agent_id="agent-a"))
    assert out["status"] == "no_tasks_available"


def test_drift_map_success_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_server, "_resolve_session", lambda _sid: None)
    monkeypatch.setattr(mcp_server, "_session_defaults", lambda _s, d: d)

    async def _ok(fn):
        return fn()

    monkeypatch.setattr(mcp_server, "_run_sync_in_thread", _ok)
    monkeypatch.setattr(
        "drift.api.drift_map", lambda *args, **kwargs: {"status": "ok", "modules": []}
    )
    ok = _run(mcp_server.drift_map(path="."))
    assert ok["status"] == "ok"

    monkeypatch.setattr(
        "drift.api.drift_map", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    err = _run(mcp_server.drift_map(path="."))
    assert err["type"] == "error"


def test_feedback_and_calibrate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mcp_server, "_resolve_session", lambda _sid: None)
    monkeypatch.setattr(mcp_server, "_enrich_response_with_session", lambda raw, *_a, **_k: raw)

    async def _ok(fn):
        return fn()

    monkeypatch.setattr(mcp_server, "_run_sync_in_thread", _ok)
    monkeypatch.setattr(
        "drift.config.DriftConfig.load",
        lambda _repo: SimpleNamespace(
            calibration=SimpleNamespace(
                feedback_path="feedback.json", min_samples=1, fn_boost_factor=1.0
            ),
            weights=SimpleNamespace(),
            as_dict=lambda: {},
        ),
    )
    monkeypatch.setattr("drift.calibration.feedback.record_feedback", lambda *_a, **_k: None)

    fb = _run(
        mcp_server.drift_feedback(
            signal="PFS",
            file_path="src/a.py",
            verdict="tp",
            path=str(tmp_path),
        )
    )
    assert fb["status"] == "recorded"

    fb_bad = _run(
        mcp_server.drift_feedback(
            signal="PFS",
            file_path="src/a.py",
            verdict="invalid",
            path=str(tmp_path),
        )
    )
    assert "error" in fb_bad

    monkeypatch.setattr("drift.calibration.feedback.load_feedback", lambda _p: [])
    no_data = _run(mcp_server.drift_calibrate(path=str(tmp_path), dry_run=True))
    assert no_data["status"] == "no_data"

    class _SignalWeights:
        def as_dict(self):
            return {"pattern_fragmentation": 1.0}

    monkeypatch.setattr("drift.config.SignalWeights", _SignalWeights)

    class _Result:
        total_events = 3
        signals_with_data = ["pattern_fragmentation"]
        calibrated_weights = _SignalWeights()

        def weight_diff(self, _default):
            return {"pattern_fragmentation": 0.1}

    monkeypatch.setattr("drift.calibration.feedback.load_feedback", lambda _p: [1, 2])
    monkeypatch.setattr(
        "drift.calibration.profile_builder.build_profile", lambda *a, **k: _Result()
    )

    cal = _run(mcp_server.drift_calibrate(path=str(tmp_path), dry_run=True))
    assert cal["status"] == "calibrated"

    # Apply path writes drift.yaml
    cal_apply = _run(mcp_server.drift_calibrate(path=str(tmp_path), dry_run=False))
    assert cal_apply["written"] is True
