"""Effort calibration based on observed outcome data.

Computes calibrated effort labels (low / medium / high) per signal type
from the median ``days_to_fix`` of resolved, non-suppressed outcomes.
No LLM, no network — purely statistical.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from drift.calibration._atomic_io import atomic_write_text
from drift.outcome_tracker import Outcome


@dataclass
class EffortCalibration:
    """Calibrated effort label for one signal type."""

    signal_type: str
    effort: str  # "low" | "medium" | "high"
    sample_size: int
    median_days_to_fix: float
    calibrated_at: str  # ISO-8601


def _days_to_effort(median_days: float) -> str:
    """Map median days-to-fix to an effort label (F-17)."""
    if median_days <= 1.0:
        return "low"
    if median_days <= 5.0:
        return "medium"
    return "high"


def calibrate_efforts(
    outcomes: list[Outcome],
    *,
    min_samples: int = 10,
) -> list[EffortCalibration]:
    """Compute calibrated effort labels from resolved outcome data.

    Only signal types with at least *min_samples* resolved,
    non-suppressed outcomes produce a calibration entry (F-18).
    """
    # Group resolved, non-suppressed outcomes by signal type
    by_signal: dict[str, list[float]] = {}
    for outcome in outcomes:
        if outcome.resolved_at is None:
            continue
        if outcome.was_suppressed:
            continue
        if outcome.days_to_fix is None:
            continue
        by_signal.setdefault(outcome.signal_type, []).append(outcome.days_to_fix)

    now_iso = datetime.now(UTC).isoformat()
    calibrations: list[EffortCalibration] = []

    for signal_type, days_values in sorted(by_signal.items()):
        if len(days_values) < min_samples:
            continue
        median = statistics.median(days_values)
        calibrations.append(
            EffortCalibration(
                signal_type=signal_type,
                effort=_days_to_effort(median),
                sample_size=len(days_values),
                median_days_to_fix=round(median, 2),
                calibrated_at=now_iso,
            )
        )

    return calibrations


def save_calibration(calibrations: list[EffortCalibration], path: Path) -> None:
    """Persist calibrations to a JSON file (F-20)."""
    data = [asdict(c) for c in calibrations]
    atomic_write_text(
        path,
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_calibration(path: Path) -> dict[str, str]:
    """Load ``{signal_type: effort}`` mapping from a calibration file.

    Returns an empty dict when the file does not exist.
    """
    if not path.exists():
        _out: dict[str, str] = {}
        return _out
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {entry["signal_type"]: entry["effort"] for entry in data}
    except (json.JSONDecodeError, KeyError, TypeError):
        return dict()


def load_effort(signal_type: str, calibration_path: Path | None = None) -> str | None:
    """Return the calibrated effort for *signal_type*, or ``None``.

    Convenience wrapper: loads the calibration file once and looks up
    a single signal type.
    """
    if calibration_path is None:
        return None
    mapping = load_calibration(calibration_path)
    return mapping.get(signal_type)
