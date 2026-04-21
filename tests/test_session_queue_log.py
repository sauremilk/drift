"""Unit tests for the queue-log primitive (ADR-081)."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from drift.session_queue_log import (
    EVENT_PLAN_CREATED,
    EVENT_TASK_CLAIMED,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_FAILED,
    EVENT_TASK_RELEASED,
    QueueEvent,
    _compact_events,
    _rotate_if_needed,
    append_event,
    clear_log,
    log_path,
    reduce_events,
    replay_events,
)


def _make_event(event_type: str, sid: str, **payload: object) -> QueueEvent:
    return QueueEvent(type=event_type, session_id=sid, payload=dict(payload))


def test_append_and_replay_roundtrip(tmp_path: Path) -> None:
    path = tmp_path
    append_event(path, _make_event(EVENT_PLAN_CREATED, "s1", tasks=[{"id": "T1"}]))
    append_event(path, _make_event(EVENT_TASK_CLAIMED, "s1", task_id="T1", agent_id="a"))
    append_event(path, _make_event(EVENT_TASK_COMPLETED, "s1", task_id="T1"))

    events = replay_events(path)
    assert [e.type for e in events] == [
        EVENT_PLAN_CREATED,
        EVENT_TASK_CLAIMED,
        EVENT_TASK_COMPLETED,
    ]
    assert events[0].payload["tasks"] == [{"id": "T1"}]
    assert events[2].payload["task_id"] == "T1"


def test_replay_missing_file_returns_empty(tmp_path: Path) -> None:
    assert replay_events(tmp_path) == []


def test_replay_skips_corrupt_lines(tmp_path: Path) -> None:
    path = log_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(
            '{"v": 1, "ts": 1.0, "sid": "s1", "type": "plan_created",'
            ' "payload": {"tasks": []}}\n'
        )
        fh.write("not valid json\n")
        fh.write('{"missing_fields": true}\n')
        fh.write(
            '{"v": 1, "ts": 2.0, "sid": "s1", "type": "task_completed",'
            ' "payload": {"task_id": "T1"}}\n'
        )

    events = replay_events(tmp_path)
    assert len(events) == 2
    assert events[0].type == EVENT_PLAN_CREATED
    assert events[1].type == EVENT_TASK_COMPLETED


def test_reduce_events_latest_plan_wins(tmp_path: Path) -> None:
    events = [
        QueueEvent(type=EVENT_PLAN_CREATED, session_id="s1", timestamp=1.0,
                   payload={"tasks": [{"id": "A"}, {"id": "B"}]}),
        QueueEvent(type=EVENT_TASK_COMPLETED, session_id="s1", timestamp=2.0,
                   payload={"task_id": "A"}),
        QueueEvent(type=EVENT_PLAN_CREATED, session_id="s2", timestamp=3.0,
                   payload={"tasks": [{"id": "X"}, {"id": "Y"}]}),
        QueueEvent(type=EVENT_TASK_COMPLETED, session_id="s2", timestamp=4.0,
                   payload={"task_id": "X"}),
        QueueEvent(type=EVENT_TASK_FAILED, session_id="s2", timestamp=5.0,
                   payload={"task_id": "Y"}),
    ]
    state = reduce_events(events)
    assert state.selected_tasks == [{"id": "X"}, {"id": "Y"}]
    assert state.completed_task_ids == ["X"]
    assert state.failed_task_ids == ["Y"]
    assert "s2" in state.source_session_ids


def test_reduce_events_empty_without_plan() -> None:
    events = [
        QueueEvent(type=EVENT_TASK_COMPLETED, session_id="s1", timestamp=1.0,
                   payload={"task_id": "A"}),
    ]
    state = reduce_events(events)
    assert state.selected_tasks == []
    assert state.completed_task_ids == []


def test_reduce_events_exposes_latest_plan_metadata() -> None:
    """ADR-081 Nachschärfung (Q2): reducer exposes plan_created_at / plan_session_id
    for the latest ``plan_created`` event so callers can detect stale replays.
    """
    events = [
        QueueEvent(type=EVENT_PLAN_CREATED, session_id="old", timestamp=100.0,
                   payload={"tasks": [{"id": "A"}]}),
        QueueEvent(type=EVENT_PLAN_CREATED, session_id="new", timestamp=500.0,
                   payload={"tasks": [{"id": "X"}, {"id": "Y"}]}),
        QueueEvent(type=EVENT_TASK_COMPLETED, session_id="new", timestamp=600.0,
                   payload={"task_id": "X"}),
    ]
    state = reduce_events(events)
    assert state.plan_created_at == 500.0
    assert state.plan_session_id == "new"
    assert state.selected_tasks == [{"id": "X"}, {"id": "Y"}]


def test_reduce_events_metadata_none_without_plan() -> None:
    """Without any plan_created event the metadata fields stay None."""
    events = [
        QueueEvent(type=EVENT_TASK_COMPLETED, session_id="s", timestamp=1.0,
                   payload={"task_id": "A"}),
    ]
    state = reduce_events(events)
    assert state.plan_created_at is None
    assert state.plan_session_id is None


def test_reduce_events_ignores_transient_events() -> None:
    events = [
        QueueEvent(type=EVENT_PLAN_CREATED, session_id="s1", timestamp=1.0,
                   payload={"tasks": [{"id": "A"}]}),
        QueueEvent(type=EVENT_TASK_CLAIMED, session_id="s1", timestamp=2.0,
                   payload={"task_id": "A", "agent_id": "bob"}),
        QueueEvent(type=EVENT_TASK_RELEASED, session_id="s1", timestamp=3.0,
                   payload={"task_id": "A", "reclaim_count": 1}),
    ]
    state = reduce_events(events)
    assert state.selected_tasks == [{"id": "A"}]
    assert state.completed_task_ids == []
    assert state.failed_task_ids == []


def test_reduce_events_skips_unknown_type() -> None:
    events = [
        QueueEvent(type=EVENT_PLAN_CREATED, session_id="s1", timestamp=1.0,
                   payload={"tasks": [{"id": "A"}]}),
        QueueEvent(type="future_event_type", session_id="s1", timestamp=2.0,
                   payload={"task_id": "A"}),
    ]
    state = reduce_events(events)
    assert state.selected_tasks == [{"id": "A"}]
    assert state.completed_task_ids == []


def test_from_dict_rejects_invalid() -> None:
    assert QueueEvent.from_dict({"type": "x"}) is None  # missing fields
    assert QueueEvent.from_dict({"type": "x", "sid": "s", "ts": "abc"}) is None
    assert QueueEvent.from_dict({"type": "x", "sid": "s", "ts": 1.0,
                                 "payload": "not-a-dict"}) is None


def test_threaded_appends_do_not_corrupt_lines(tmp_path: Path) -> None:
    """Concurrent intra-process writes must remain individually parseable."""

    def _writer(i: int) -> None:
        for j in range(20):
            append_event(
                tmp_path,
                _make_event(EVENT_TASK_COMPLETED, f"s{i}", task_id=f"T{i}-{j}"),
            )

    threads = [threading.Thread(target=_writer, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    events = replay_events(tmp_path)
    assert len(events) == 4 * 20
    assert all(e.type == EVENT_TASK_COMPLETED for e in events)


def test_compact_events_keeps_latest_plan_and_terminals() -> None:
    events = [
        QueueEvent(type=EVENT_PLAN_CREATED, session_id="s1", timestamp=1.0,
                   payload={"tasks": [{"id": "A"}]}),
        QueueEvent(type=EVENT_TASK_CLAIMED, session_id="s1", timestamp=2.0,
                   payload={"task_id": "A", "agent_id": "bob"}),
        QueueEvent(type=EVENT_PLAN_CREATED, session_id="s2", timestamp=3.0,
                   payload={"tasks": [{"id": "X"}]}),
        QueueEvent(type=EVENT_TASK_COMPLETED, session_id="s2", timestamp=4.0,
                   payload={"task_id": "X"}),
        QueueEvent(type=EVENT_TASK_RELEASED, session_id="s2", timestamp=5.0,
                   payload={"task_id": "X", "reclaim_count": 1}),
    ]
    compact = _compact_events(events)
    assert len(compact) == 2
    assert compact[0].type == EVENT_PLAN_CREATED
    assert compact[0].session_id == "s2"
    assert compact[1].type == EVENT_TASK_COMPLETED


def test_rotation_compacts_oversized_log(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "drift.session_queue_log._ROTATE_THRESHOLD_BYTES", 200
    )
    # Seed a small but over-threshold log manually
    append_event(tmp_path, _make_event(EVENT_PLAN_CREATED, "s1",
                                       tasks=[{"id": "A"}, {"id": "B"}]))
    for i in range(50):
        append_event(tmp_path, _make_event(EVENT_TASK_CLAIMED, "s1",
                                           task_id=f"T{i}", agent_id="bob"))
    append_event(tmp_path, _make_event(EVENT_TASK_COMPLETED, "s1",
                                       task_id="A"))
    # Trigger an explicit rotation pass in case final size was exactly at threshold
    _rotate_if_needed(log_path(tmp_path))

    after = replay_events(tmp_path)
    # Only plan + terminals survive rotation (task_claimed events dropped)
    assert all(e.type in {EVENT_PLAN_CREATED, EVENT_TASK_COMPLETED,
                          EVENT_TASK_FAILED} for e in after)
    assert any(e.type == EVENT_PLAN_CREATED for e in after)


def test_clear_log(tmp_path: Path) -> None:
    append_event(tmp_path, _make_event(EVENT_PLAN_CREATED, "s1", tasks=[]))
    assert log_path(tmp_path).exists()
    assert clear_log(tmp_path) is True
    assert not log_path(tmp_path).exists()
    assert clear_log(tmp_path) is False


def test_utf8_encoding_roundtrip(tmp_path: Path) -> None:
    """Ensure non-ASCII payloads survive write+read on Windows (CP1252 default)."""
    unicode_title = "Architektur-Ümlaut — em-dash • 日本語"
    append_event(
        tmp_path,
        _make_event(EVENT_PLAN_CREATED, "s1",
                    tasks=[{"id": "T1", "title": unicode_title}]),
    )
    raw = log_path(tmp_path).read_text(encoding="utf-8")
    parsed = json.loads(raw.strip())
    assert parsed["payload"]["tasks"][0]["title"] == unicode_title
    events = replay_events(tmp_path)
    assert events[0].payload["tasks"][0]["title"] == unicode_title
