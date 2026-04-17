"""Persistence helpers for calibration status metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drift.calibration._atomic_io import atomic_write_text

CALIBRATION_STATUS_REL_PATH = ".drift/calibration_status.json"


def calibration_status_path(repo: Path) -> Path:
    """Return the canonical path for calibration status metadata."""
    return repo / CALIBRATION_STATUS_REL_PATH


def load_calibration_status(repo: Path) -> dict[str, Any] | None:
    """Load calibration status metadata if available and valid."""
    status_path = calibration_status_path(repo)
    if not status_path.exists():
        return None

    try:
        raw = status_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None

    if isinstance(data, dict):
        return data
    return None


def write_calibration_status(repo: Path, payload: dict[str, Any]) -> Path:
    """Write calibration status metadata as UTF-8 JSON."""
    status_path = calibration_status_path(repo)
    atomic_write_text(
        status_path,
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return status_path
