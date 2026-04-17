"""Atomic write helpers for calibration persistence."""

from __future__ import annotations

import os
import tempfile
import time
from contextlib import contextmanager, suppress
from io import BufferedRandom
from pathlib import Path


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Atomically write *content* to *path* via temp file + replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix or ".tmp"
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=suffix)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(content)
        tmp_path.replace(path)
    except OSError:
        with suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise


@contextmanager
def interprocess_lock(
    target_path: Path,
    *,
    timeout_seconds: float = 10.0,
    poll_interval_seconds: float = 0.05,
):
    """Acquire a cross-process advisory lock for *target_path*.

    The lock is held on a sidecar ``.lock`` file and released automatically
    when leaving the context manager.
    """
    lock_path = target_path.with_suffix(f"{target_path.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+b") as lock_file:
        _acquire_file_lock(lock_file, timeout_seconds, poll_interval_seconds)
        try:
            yield
        finally:
            _release_file_lock(lock_file)

    with suppress(OSError):
        lock_path.unlink(missing_ok=True)


def _acquire_file_lock(
    lock_file: BufferedRandom,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            if os.name == "nt":
                _acquire_file_lock_windows(lock_file)
            else:
                _acquire_file_lock_posix(lock_file)
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise TimeoutError("timed out waiting for interprocess file lock")
            time.sleep(poll_interval_seconds)


def _acquire_file_lock_windows(lock_file: BufferedRandom) -> None:
    import msvcrt

    lock_file.seek(0)
    if lock_file.read(1) == b"":
        lock_file.seek(0)
        lock_file.write(b"0")
        lock_file.flush()
    lock_file.seek(0)
    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)


def _acquire_file_lock_posix(lock_file: BufferedRandom) -> None:
    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_file_lock(lock_file: BufferedRandom) -> None:
    with suppress(OSError):
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
