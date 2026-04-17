"""Atomic write helpers for calibration persistence."""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
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
