from __future__ import annotations

from pathlib import Path

import pytest

from drift.calibration.history import ScanSnapshot, save_snapshot
from drift.calibration.recommendation_calibrator import EffortCalibration, save_calibration
from drift.calibration.status import write_calibration_status


def _fail_replace(self: Path, _target: Path) -> None:  # pragma: no cover - test helper
    raise OSError("simulated replace failure")


def test_issue_433_history_save_snapshot_is_atomic_on_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history_dir = tmp_path / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    snapshot = ScanSnapshot(
        timestamp="2024-01-01T00:00:00+00:00",
        drift_score=0.5,
        finding_count=1,
    )
    target = history_dir / "scan_2024-01-01T00-00-00_00_00.json"
    previous = '{"old": true}\n'
    target.write_text(previous, encoding="utf-8")

    monkeypatch.setattr(Path, "replace", _fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        save_snapshot(history_dir, snapshot)

    assert target.read_text(encoding="utf-8") == previous
    assert sorted(p.name for p in history_dir.iterdir()) == [target.name]


def test_issue_433_status_write_is_atomic_on_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / ".drift" / "calibration_status.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = '{"status": "old"}\n'
    target.write_text(previous, encoding="utf-8")

    monkeypatch.setattr(Path, "replace", _fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_calibration_status(tmp_path, {"status": "new"})

    assert target.read_text(encoding="utf-8") == previous
    assert sorted(p.name for p in target.parent.iterdir()) == [target.name]


def test_issue_433_recommendation_save_is_atomic_on_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "calibration.json"
    previous = "[]\n"
    target.write_text(previous, encoding="utf-8")

    calibrations = [
        EffortCalibration(
            signal_type="pfs",
            effort="low",
            sample_size=12,
            median_days_to_fix=0.5,
            calibrated_at="2024-01-01T00:00:00+00:00",
        )
    ]

    monkeypatch.setattr(Path, "replace", _fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        save_calibration(calibrations, target)

    assert target.read_text(encoding="utf-8") == previous
    assert sorted(p.name for p in target.parent.iterdir()) == [target.name]
