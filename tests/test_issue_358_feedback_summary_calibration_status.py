from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from drift.calibration.feedback import FeedbackEvent
from drift.commands.calibrate import calibrate
from drift.commands.feedback import feedback
from drift.config import SignalWeights


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(
        calibration=SimpleNamespace(
            feedback_path="feedback.jsonl",
            history_dir="history",
            min_samples=1,
            fn_boost_factor=0.1,
            enabled=True,
            auto_recalibrate=False,
            correlation_window_days=30,
            weak_fp_window_days=60,
        ),
        weights=SignalWeights(),
    )


def test_feedback_summary_shows_pending_calibration_when_never_calibrated(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _cfg()
    events = [
        FeedbackEvent(
            signal_type="phantom_reference",
            file_path="src/x.py",
            verdict="fp",
            source="user",
        )
    ]

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch("drift.calibration.feedback.load_feedback", return_value=events),
    ):
        result = runner.invoke(feedback, ["summary", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "Calibration Status" in result.output
    assert "Last calibrated: never" in result.output
    assert "pending" in result.output


def test_feedback_summary_shows_weight_effect_after_calibrate_run(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _cfg()
    events = [
        FeedbackEvent(
            signal_type="phantom_reference",
            file_path="src/x.py",
            verdict="fp",
            source="user",
        )
        for _ in range(5)
    ]

    class _Result:
        total_events = 5
        signals_with_data = 1

        @staticmethod
        def weight_diff(_default: SignalWeights) -> dict[str, dict[str, float]]:
            return {
                "phantom_reference": {
                    "default": 1.0,
                    "calibrated": 0.7,
                    "delta": -0.3,
                    "confidence": 1.0,
                }
            }

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch("drift.calibration.feedback.load_feedback", return_value=events),
        patch("drift.calibration.profile_builder.build_profile", return_value=_Result()),
        patch("drift.commands.calibrate._write_calibrated_weights", return_value=None),
    ):
        run_result = runner.invoke(calibrate, ["run", "--repo", str(tmp_path)])

    assert run_result.exit_code == 0
    assert (tmp_path / ".drift" / "calibration_status.json").exists()

    cfg.weights = SignalWeights().model_copy(update={"phantom_reference": 0.7})

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch("drift.calibration.feedback.load_feedback", return_value=events),
    ):
        summary_result = runner.invoke(feedback, ["summary", "--repo", str(tmp_path)])

    assert summary_result.exit_code == 0
    assert "Calibration Status" in summary_result.output
    assert "Last calibrated:" in summary_result.output
    assert "none pending" in summary_result.output
    assert "PHR" in summary_result.output
    phr_default = SignalWeights().as_dict()["phantom_reference"]
    assert f"{phr_default:>5.2f}" in summary_result.output
    assert "0.70" in summary_result.output
    assert "5 FP marks applied" in summary_result.output
