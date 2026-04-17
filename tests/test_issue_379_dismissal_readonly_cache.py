"""Regression tests for get_active_dismissals() write-on-read bug (#379).

Verifies that:
1. get_active_dismissals() does NOT write the cache when no entries expired.
2. get_active_dismissals() DOES write the cache when expired entries are pruned.
3. get_active_dismissal_ids() succeeds on a read-only cache file when no
   entries have expired (the call that previously raised PermissionError).
"""

from __future__ import annotations

import json
import os
import stat
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import drift.fix_plan_dismissals as fix_plan_dismissals
from drift.fix_plan_dismissals import (
    _write_entries,
    dismiss_task,
    get_active_dismissal_ids,
    get_active_dismissals,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_CACHE_SUBDIR = ".drift-cache"
_CACHE_FILE = "fix-plan-dismissed.json"


def _cache_path(tmp_path: Path) -> Path:
    return tmp_path / _CACHE_SUBDIR / _CACHE_FILE


def _write_raw(tmp_path: Path, entries: list[dict]) -> None:
    p = _cache_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"version": 1, "dismissed": entries}, indent=2) + "\n",
        encoding="utf-8",
    )


def _future(days: int = 7) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def _past(days: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# 1. No write when nothing expired
# ---------------------------------------------------------------------------


class TestNoWriteOnCleanRead:
    """Cache file must NOT be touched when all entries are still active."""

    def test_mtime_unchanged_after_read(self, tmp_path: Path) -> None:
        entries = [
            {"task_id": "task-a", "expires_at": _future(3)},
            {"task_id": "task-b", "expires_at": _future(5)},
        ]
        _write_raw(tmp_path, entries)
        cache = _cache_path(tmp_path)
        mtime_before = cache.stat().st_mtime_ns

        get_active_dismissals(tmp_path)

        assert cache.stat().st_mtime_ns == mtime_before, (
            "Cache file was written even though no entries expired"
        )

    def test_empty_cache_not_written(self, tmp_path: Path) -> None:
        _write_raw(tmp_path, [])
        cache = _cache_path(tmp_path)
        mtime_before = cache.stat().st_mtime_ns

        get_active_dismissals(tmp_path)

        assert cache.stat().st_mtime_ns == mtime_before, (
            "Cache file was written even though it was already empty"
        )


# ---------------------------------------------------------------------------
# 2. Write happens when expired entries are pruned
# ---------------------------------------------------------------------------


class TestWriteOnExpiredPrune:
    """Cache file MUST be rewritten when at least one entry has expired."""

    def test_expired_entry_removed_and_file_updated(self, tmp_path: Path) -> None:
        entries = [
            {"task_id": "old-task", "expires_at": _past(2)},
            {"task_id": "active-task", "expires_at": _future(3)},
        ]
        _write_raw(tmp_path, entries)
        cache = _cache_path(tmp_path)
        mtime_before = cache.stat().st_mtime_ns

        active = get_active_dismissals(tmp_path)

        assert cache.stat().st_mtime_ns != mtime_before, (
            "Cache file was NOT rewritten after expired entry pruning"
        )
        assert [e["task_id"] for e in active] == ["active-task"]
        payload = json.loads(cache.read_text(encoding="utf-8"))
        assert len(payload["dismissed"]) == 1
        assert payload["dismissed"][0]["task_id"] == "active-task"


# ---------------------------------------------------------------------------
# 3. Read-only cache does not raise PermissionError when nothing expired
# ---------------------------------------------------------------------------


class TestReadOnlyCacheNoPermissionError:
    """get_active_dismissal_ids() must not fail on read-only cache when no entries expire."""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Read-only files on Windows can still be overwritten by file owner; skip.",
    )
    def test_readonly_cache_no_error(self, tmp_path: Path) -> None:
        entries = [{"task_id": "live-task", "expires_at": _future(7)}]
        _write_raw(tmp_path, entries)
        cache = _cache_path(tmp_path)
        cache.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)

        try:
            ids = get_active_dismissal_ids(tmp_path)
            assert "live-task" in ids
        finally:
            # Restore write permission so tmp_path cleanup can delete the file.
            cache.chmod(stat.S_IREAD | stat.S_IWRITE)

    def test_active_dismissal_ids_returns_correct_set(self, tmp_path: Path) -> None:
        dismiss_task(tmp_path, "task-x")
        dismiss_task(tmp_path, "task-y")

        ids = get_active_dismissal_ids(tmp_path)
        assert ids == {"task-x", "task-y"}


class TestAtomicWriteSafety:
    """Failed writes must never corrupt an existing cache file."""

    def test_failed_write_preserves_previous_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original_entries = [{"task_id": "keep-me", "expires_at": _future(4)}]
        _write_raw(tmp_path, original_entries)
        cache = _cache_path(tmp_path)

        def _crash_fdopen(fd: int, *args: object, **kwargs: object) -> object:
            os.close(fd)
            raise OSError("simulated write interruption")

        monkeypatch.setattr(fix_plan_dismissals.os, "fdopen", _crash_fdopen)

        with pytest.raises(OSError):
            _write_entries(tmp_path, [{"task_id": "new-task", "expires_at": _future(10)}])

        payload = json.loads(cache.read_text(encoding="utf-8"))
        task_ids = [entry["task_id"] for entry in payload["dismissed"]]
        assert task_ids == ["keep-me"]
