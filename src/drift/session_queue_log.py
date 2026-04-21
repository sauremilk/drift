"""Append-only queue event log for cross-session fix-plan persistence.

This module provides a JSONL-based event log written to
``<repo>/.drift-cache/queue.jsonl`` that records every mutation of the
fix-plan queue (plan created, task claimed, completed, released, failed).
On session start, the log is replayed to reconstruct ``selected_tasks``,
``completed_task_ids`` and ``failed_task_ids`` so that agent work survives
server restarts and session TTL expiry.

Design goals
------------

* **Stdlib-only** — no new runtime dependency.
* **Single-writer per repo** — fixes the queue-log file to one process;
  best-effort OS-level locking covers accidental concurrent writes.
* **Forward-compatible** — unknown event ``type`` values are skipped on
  replay; every event carries a ``v`` (schema version) field.
* **Tolerant replay** — a corrupt single line does not abort replay;
  it is logged and skipped.
* **Cheap rotation** — when the log exceeds ``_ROTATE_THRESHOLD_BYTES``,
  a compact snapshot replaces the file (latest plan + terminal events).

Decision: ADR-081 (Session-Queue-Persistenz — proposed).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("drift")

_SCHEMA_VERSION = 1
_CACHE_DIR = ".drift-cache"
_LOG_FILENAME = "queue.jsonl"
_ROTATE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10 MB

EVENT_PLAN_CREATED = "plan_created"
EVENT_TASK_CLAIMED = "task_claimed"
EVENT_TASK_COMPLETED = "task_completed"
EVENT_TASK_RELEASED = "task_released"
EVENT_TASK_FAILED = "task_failed"

_KNOWN_EVENT_TYPES = frozenset(
    {
        EVENT_PLAN_CREATED,
        EVENT_TASK_CLAIMED,
        EVENT_TASK_COMPLETED,
        EVENT_TASK_RELEASED,
        EVENT_TASK_FAILED,
    }
)

# Serialise intra-process writes; cross-process coordination is best-effort
# via OS-level locking (msvcrt/fcntl) inside ``_locked_append``.
_write_lock = threading.Lock()


@dataclass(frozen=True)
class QueueEvent:
    """One append-only queue event.

    ``payload`` shape depends on ``type``:

    * ``plan_created``  → ``{"tasks": [<task dict>, ...]}``
    * ``task_claimed``  → ``{"task_id": str, "agent_id": str}``
    * ``task_completed``→ ``{"task_id": str}``
    * ``task_released`` → ``{"task_id": str, "reclaim_count": int}``
    * ``task_failed``   → ``{"task_id": str}``
    """

    type: str
    session_id: str
    timestamp: float = field(default_factory=time.time)
    payload: dict[str, Any] = field(default_factory=dict)
    version: int = _SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "v": self.version,
            "ts": self.timestamp,
            "sid": self.session_id,
            "type": self.type,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueueEvent | None:
        """Parse a dict into a ``QueueEvent`` or return ``None`` if invalid."""
        try:
            event_type = str(data["type"])
            session_id = str(data["sid"])
            timestamp = float(data["ts"])
            payload = data.get("payload") or {}
            version = int(data.get("v", _SCHEMA_VERSION))
        except (KeyError, TypeError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        return cls(
            type=event_type,
            session_id=session_id,
            timestamp=timestamp,
            payload=payload,
            version=version,
        )


def log_path(repo_path: str | Path) -> Path:
    """Return the absolute path of the queue log for ``repo_path``."""
    return Path(repo_path) / _CACHE_DIR / _LOG_FILENAME


# ---------------------------------------------------------------------------
# Cross-platform best-effort file lock
# ---------------------------------------------------------------------------


def _acquire_os_lock(fh: Any) -> None:
    """Best-effort exclusive lock on an open file handle."""
    try:
        if sys.platform == "win32":
            import msvcrt

            # Lock 1 byte at offset 0; enough to block concurrent writers.
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
    except OSError:
        # Locking is best-effort; single-writer per repo is the documented
        # contract. Continue without lock rather than fail the event write.
        logger.debug("queue-log: OS lock unavailable, continuing without")


def _release_os_lock(fh: Any) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Append
# ---------------------------------------------------------------------------


def append_event(repo_path: str | Path, event: QueueEvent) -> Path | None:
    """Append ``event`` to the repo's queue log.

    Returns the log file path on success, ``None`` on unrecoverable I/O error.
    Creates ``.drift-cache/`` if missing.  Triggers rotation when the log
    exceeds ``_ROTATE_THRESHOLD_BYTES`` after the write.
    """
    path = log_path(repo_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("queue-log: cannot create cache dir %s: %s", path.parent, exc)
        return None

    line = json.dumps(event.to_dict(), default=str, ensure_ascii=False) + "\n"
    with _write_lock:
        try:
            with path.open("a", encoding="utf-8") as fh:
                _acquire_os_lock(fh)
                try:
                    fh.write(line)
                    fh.flush()
                finally:
                    _release_os_lock(fh)
        except OSError as exc:
            logger.warning("queue-log: append failed %s: %s", path, exc)
            return None

    _rotate_if_needed(path)
    return path


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


def replay_events(repo_path: str | Path) -> list[QueueEvent]:
    """Read all events from the log in order.

    Corrupt lines are logged and skipped.  Returns an empty list when no
    log file exists.
    """
    path = log_path(repo_path)
    if not path.is_file():
        return []

    events: list[QueueEvent] = []
    skipped = 0
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line_no, raw in enumerate(fh, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    logger.debug("queue-log: skip corrupt line %d", line_no)
                    continue
                if not isinstance(data, dict):
                    skipped += 1
                    continue
                event = QueueEvent.from_dict(data)
                if event is None:
                    skipped += 1
                    continue
                events.append(event)
    except OSError as exc:
        logger.warning("queue-log: replay read failed %s: %s", path, exc)
        return []

    if skipped:
        logger.info("queue-log: replay skipped %d invalid event(s)", skipped)
    return events


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------


def _rotate_if_needed(path: Path) -> None:
    """Compact the log when it exceeds the rotation threshold."""
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size < _ROTATE_THRESHOLD_BYTES:
        return

    events = replay_events(path.parent.parent)
    compact = _compact_events(events)
    if not compact:
        return

    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            for evt in compact:
                fh.write(json.dumps(evt.to_dict(), default=str, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
        logger.info("queue-log: rotated %s (%d events)", path, len(compact))
    except OSError as exc:
        logger.warning("queue-log: rotation failed %s: %s", path, exc)
        with contextlib.suppress(OSError):
            tmp.unlink()


def _compact_events(events: list[QueueEvent]) -> list[QueueEvent]:
    """Return a compact event list representing the current queue state.

    Keeps the most recent ``plan_created`` event and every terminal event
    (``task_completed`` / ``task_failed``) that follows it.  Drops transient
    events (``task_claimed`` / ``task_released``) because they no longer
    represent live leases after a restart.
    """
    latest_plan_idx: int | None = None
    for idx, evt in enumerate(events):
        if evt.type == EVENT_PLAN_CREATED:
            latest_plan_idx = idx
    if latest_plan_idx is None:
        return []

    kept = [events[latest_plan_idx]]
    for evt in events[latest_plan_idx + 1 :]:
        if evt.type in (EVENT_TASK_COMPLETED, EVENT_TASK_FAILED):
            kept.append(evt)
    return kept


# ---------------------------------------------------------------------------
# State reducer (replay → session fields)
# ---------------------------------------------------------------------------


@dataclass
class ReplayedState:
    """State reconstructed from a queue-log replay.

    Fields mirror the subset of ``DriftSession`` that is restored on
    session start.  Transient runtime state (leases, metrics, trace) is
    intentionally *not* restored — expired leases would block new claims
    and metrics are per-session.
    """

    selected_tasks: list[dict[str, Any]] = field(default_factory=list)
    completed_task_ids: list[str] = field(default_factory=list)
    failed_task_ids: list[str] = field(default_factory=list)
    source_session_ids: list[str] = field(default_factory=list)
    # ADR-081 Nachschärfung (Q2): expose the latest-plan metadata so
    # callers can detect stale replays (e.g. a plan that was created days
    # ago by an abandoned session) and surface age hints in responses.
    plan_created_at: float | None = None
    plan_session_id: str | None = None


def reduce_events(events: list[QueueEvent]) -> ReplayedState:
    """Reduce a list of events to the restorable subset of session state."""
    state = ReplayedState()
    latest_plan: QueueEvent | None = None
    for evt in events:
        if evt.type == EVENT_PLAN_CREATED:
            latest_plan = evt

    if latest_plan is None:
        return state

    state.plan_created_at = latest_plan.timestamp
    state.plan_session_id = latest_plan.session_id

    raw_tasks = latest_plan.payload.get("tasks")
    if isinstance(raw_tasks, list):
        state.selected_tasks = [t for t in raw_tasks if isinstance(t, dict)]

    seen_sids: set[str] = {latest_plan.session_id}
    for evt in events:
        if evt.timestamp < latest_plan.timestamp:
            continue
        if evt.type not in _KNOWN_EVENT_TYPES:
            continue
        seen_sids.add(evt.session_id)
        task_id = evt.payload.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            continue
        if evt.type == EVENT_TASK_COMPLETED and task_id not in state.completed_task_ids:
            state.completed_task_ids.append(task_id)
        elif evt.type == EVENT_TASK_FAILED and task_id not in state.failed_task_ids:
            state.failed_task_ids.append(task_id)
        # task_claimed / task_released are transient and deliberately ignored.

    state.source_session_ids = sorted(seen_sids)
    return state


# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------


def clear_log(repo_path: str | Path) -> bool:
    """Delete the queue log for ``repo_path``. Returns ``True`` if removed."""
    path = log_path(repo_path)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning("queue-log: clear failed %s: %s", path, exc)
        return False
