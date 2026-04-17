"""Coverage-Boost: commands/calibrate.py — CLI-Kommandos via Click CliRunner."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from drift.calibration.feedback import FeedbackEvent
from drift.commands.calibrate import calibrate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cfg(
    tmp_path: Path,
    *,
    enabled: bool = True,
    feedback_path: str = ".drift/feedback.jsonl",
    history_dir: str = ".drift/history",
    min_samples: int = 5,
    auto_recalibrate: bool = False,
    history_exists: bool = False,
) -> MagicMock:
    cal = MagicMock()
    cal.feedback_path = feedback_path
    cal.history_dir = history_dir
    cal.min_samples = min_samples
    cal.fn_boost_factor = 1.5
    cal.auto_recalibrate = auto_recalibrate
    cal.correlation_window_days = 30
    cal.weak_fp_window_days = 60
    cal.enabled = enabled

    cfg = MagicMock()
    cfg.calibration = cal
    cfg.weights = MagicMock()

    if history_exists:
        h_dir = tmp_path / ".drift" / "history"
        h_dir.mkdir(parents=True, exist_ok=True)

    return cfg


def _make_build_result(
    *,
    total_events: int = 10,
    signals_with_data: int = 3,
    diff: dict | None = None,
) -> MagicMock:
    result = MagicMock()
    result.total_events = total_events
    result.signals_with_data = signals_with_data
    result.evidence = {}
    result.confidence_per_signal = {}
    result.clamped_signals = []

    if diff is None:
        diff = {}

    def weight_diff(other: Any) -> dict:
        return diff

    result.weight_diff = weight_diff
    return result


# ---------------------------------------------------------------------------
# calibrate run — no events
# ---------------------------------------------------------------------------


def test_run_no_events_text_format(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _make_cfg(tmp_path)

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch("drift.calibration.feedback.load_feedback_with_stats", return_value=([], 0)),
    ):
        result = runner.invoke(calibrate, ["run", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "No feedback evidence" in result.output


def test_run_no_events_json_format(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _make_cfg(tmp_path)

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch("drift.calibration.feedback.load_feedback_with_stats", return_value=([], 0)),
    ):
        result = runner.invoke(calibrate, ["run", "--repo", str(tmp_path), "--format", "json"])

    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert data["status"] == "no_data"


# ---------------------------------------------------------------------------
# calibrate run — with events, no diff (empty weight changes)
# ---------------------------------------------------------------------------


def test_run_with_events_no_diff_text(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _make_cfg(tmp_path)
    build_result = _make_build_result(diff={})

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch(
            "drift.calibration.feedback.load_feedback_with_stats",
            return_value=([
                FeedbackEvent(
                    signal_type="pattern_fragmentation",
                    file_path="src/a.py",
                    verdict="tp",
                    source="user",
                )
            ], 0),
        ),
        patch("drift.calibration.profile_builder.build_profile", return_value=build_result),
    ):
        result = runner.invoke(calibrate, ["run", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "No weight changes" in result.output


# ---------------------------------------------------------------------------
# calibrate run — with events, with diff, dry_run
# ---------------------------------------------------------------------------


def test_run_with_diff_dry_run(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _make_cfg(tmp_path)
    diff = {
        "pfs": {"default": 1.0, "calibrated": 1.2, "delta": 0.2, "confidence": 0.8},
    }
    build_result = _make_build_result(diff=diff)

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch(
            "drift.calibration.feedback.load_feedback_with_stats",
            return_value=([
                FeedbackEvent(
                    signal_type="pattern_fragmentation",
                    file_path="src/a.py",
                    verdict="tp",
                    source="user",
                )
            ], 0),
        ),
        patch("drift.calibration.profile_builder.build_profile", return_value=build_result),
    ):
        result = runner.invoke(calibrate, ["run", "--repo", str(tmp_path), "--dry-run"])

    assert result.exit_code == 0
    # Should print the diff table
    assert "pfs" in result.output.lower() or "pfs" in result.output


# ---------------------------------------------------------------------------
# calibrate run — with history dir existing
# ---------------------------------------------------------------------------


def test_run_with_history_dir(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _make_cfg(tmp_path, history_exists=True)
    build_result = _make_build_result(diff={})
    fake_snapshot = MagicMock()

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch("drift.calibration.feedback.load_feedback_with_stats", return_value=([], 0)),
        patch("drift.calibration.history.load_snapshots", return_value=[fake_snapshot]),
        patch(
            "drift.commands.calibrate._collect_git_correlation",
            return_value=[
                FeedbackEvent(
                    signal_type="pattern_fragmentation",
                    file_path="src/git.py",
                    verdict="tp",
                    source="git_correlation",
                )
            ],
        ),
        patch("drift.calibration.profile_builder.build_profile", return_value=build_result),
    ):
        result = runner.invoke(calibrate, ["run", "--repo", str(tmp_path)])

    # Should have extended events (1 from git correlation)
    assert result.exit_code == 0


def test_run_dedupes_cross_source_and_prefers_explicit_feedback(tmp_path: Path) -> None:
    from drift.calibration.feedback import FeedbackEvent

    runner = CliRunner()
    cfg = _make_cfg(tmp_path, history_exists=True)
    build_result = _make_build_result(total_events=1, signals_with_data=1, diff={})
    fake_snapshot = MagicMock()

    user_event = FeedbackEvent(
        signal_type="phantom_reference",
        file_path="src/x.py",
        verdict="fp",
        source="user",
    )
    git_event = FeedbackEvent(
        signal_type="phantom_reference",
        file_path="src/x.py",
        verdict="tp",
        source="git_correlation",
    )

    captured: dict[str, list[FeedbackEvent]] = {}

    def _capture_build_profile(
        events: list[FeedbackEvent], *_args: Any, **_kwargs: Any
    ) -> MagicMock:
        captured["events"] = events
        return build_result

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch(
            "drift.calibration.feedback.load_feedback_with_stats",
            return_value=([user_event], 0),
        ),
        patch("drift.calibration.history.load_snapshots", return_value=[fake_snapshot]),
        patch("drift.commands.calibrate._collect_git_correlation", return_value=[git_event]),
        patch(
            "drift.calibration.profile_builder.build_profile", side_effect=_capture_build_profile
        ),
    ):
        result = runner.invoke(calibrate, ["run", "--repo", str(tmp_path), "--format", "json"])

    assert result.exit_code == 0
    assert "events" in captured
    assert len(captured["events"]) == 1
    assert captured["events"][0].source == "user"
    assert captured["events"][0].verdict == "fp"


# ---------------------------------------------------------------------------
# calibrate run — json format with diff
# ---------------------------------------------------------------------------


def test_run_json_format_with_diff(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _make_cfg(tmp_path)
    diff = {"avs": {"default": 0.5, "calibrated": 0.6, "delta": 0.1, "confidence": 0.7}}
    build_result = _make_build_result(diff=diff)

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch(
            "drift.calibration.feedback.load_feedback_with_stats",
            return_value=([
                FeedbackEvent(
                    signal_type="architecture_violation",
                    file_path="src/b.py",
                    verdict="fp",
                    source="user",
                )
            ], 0),
        ),
        patch("drift.calibration.profile_builder.build_profile", return_value=build_result),
    ):
        result = runner.invoke(calibrate, ["run", "--repo", str(tmp_path), "--format", "json"])

    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert data["status"] == "calibrated"
    assert data["dry_run"] is False


# ---------------------------------------------------------------------------
# calibrate explain — no events
# ---------------------------------------------------------------------------


def test_explain_no_events(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _make_cfg(tmp_path)

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch("drift.calibration.feedback.load_feedback", return_value=[]),
    ):
        result = runner.invoke(calibrate, ["explain", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "No feedback" in result.output


# ---------------------------------------------------------------------------
# calibrate explain — with events
# ---------------------------------------------------------------------------


def test_explain_with_events(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _make_cfg(tmp_path)

    ev = MagicMock()
    ev.total_observations = 5
    ev.fn = 1
    ev.tp = 3
    ev.fp = 1
    ev.precision = 0.75

    build_result = MagicMock()
    build_result.total_events = 5
    build_result.evidence = {"PFS": ev}
    build_result.confidence_per_signal = {"PFS": 0.6}

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch("drift.calibration.feedback.load_feedback", return_value=[MagicMock()]),
        patch("drift.calibration.profile_builder.build_profile", return_value=build_result),
    ):
        result = runner.invoke(calibrate, ["explain", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "PFS" in result.output or "pfs" in result.output.lower()


# ---------------------------------------------------------------------------
# calibrate status
# ---------------------------------------------------------------------------


def test_status_calibration_disabled(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _make_cfg(tmp_path, enabled=False)

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch("drift.calibration.feedback.load_feedback", return_value=[]),
    ):
        result = runner.invoke(calibrate, ["status", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "not enabled" in result.output.lower() or "Calibration is not enabled" in result.output


def test_status_enabled_no_history(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _make_cfg(tmp_path, enabled=True)

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch(
            "drift.calibration.feedback.load_feedback_with_stats",
            return_value=([MagicMock()], 0),
        ),
    ):
        result = runner.invoke(calibrate, ["status", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "Feedback events: 1" in result.output


def test_status_enabled_with_history(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg = _make_cfg(tmp_path, enabled=True, history_exists=True)

    with (
        patch("drift.config.DriftConfig.load", return_value=cfg),
        patch("drift.calibration.feedback.load_feedback_with_stats", return_value=([], 0)),
        patch("drift.calibration.history.load_snapshots", return_value=[MagicMock(), MagicMock()]),
    ):
        result = runner.invoke(calibrate, ["status", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "History snapshots: 2" in result.output


# ---------------------------------------------------------------------------
# calibrate reset
# ---------------------------------------------------------------------------


def test_reset_no_config_file(tmp_path: Path) -> None:
    runner = CliRunner()

    with patch("drift.config.DriftConfig._find_config_file", return_value=None):
        result = runner.invoke(calibrate, ["reset", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "No config file found" in result.output


def test_reset_with_weights_removes_them(tmp_path: Path) -> None:
    runner = CliRunner()
    import yaml

    config_file = tmp_path / "drift.yaml"
    config_file.write_text(
        yaml.dump({"weights": {"pfs": 1.2}, "analysis": {"timeout": 30}}),
        encoding="utf-8",
    )

    with patch("drift.config.DriftConfig._find_config_file", return_value=config_file):
        result = runner.invoke(calibrate, ["reset", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "removed" in result.output.lower() or "Calibrated weights removed" in result.output
    # Verify weights are gone from file
    remaining = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert "weights" not in remaining


def test_reset_no_weights_in_config(tmp_path: Path) -> None:
    runner = CliRunner()
    import yaml

    config_file = tmp_path / "drift.yaml"
    config_file.write_text(yaml.dump({"analysis": {"timeout": 30}}), encoding="utf-8")

    with patch("drift.config.DriftConfig._find_config_file", return_value=config_file):
        result = runner.invoke(calibrate, ["reset", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "No custom weights" in result.output


def test_write_calibrated_weights_keeps_original_on_replace_error(tmp_path: Path) -> None:
    import yaml

    from drift.commands.calibrate import _write_calibrated_weights

    config_file = tmp_path / "drift.yaml"
    original_content = yaml.dump({"weights": {"pattern_fragmentation": 0.1}, "x": 1})
    config_file.write_text(original_content, encoding="utf-8")

    fake_weights = MagicMock()
    fake_weights.as_dict.return_value = {"pattern_fragmentation": 0.5}
    fake_result = MagicMock()
    fake_result.calibrated_weights = fake_weights

    def _boom(_src: str, _dst: str) -> None:
        raise OSError("simulated replace failure")

    with patch("drift.commands.calibrate.os.replace", side_effect=_boom):
        try:
            _write_calibrated_weights(tmp_path, config_file, fake_result)
            raise AssertionError("Expected OSError")
        except OSError:
            pass

    assert config_file.read_text(encoding="utf-8") == original_content
    leftovers = [p for p in tmp_path.iterdir() if p.name != "drift.yaml"]
    assert leftovers == []


def test_reset_keeps_original_on_replace_error(tmp_path: Path) -> None:
    runner = CliRunner()
    import yaml

    config_file = tmp_path / "drift.yaml"
    original_data = {"weights": {"pfs": 1.2}, "analysis": {"timeout": 30}}
    config_file.write_text(yaml.dump(original_data), encoding="utf-8")

    def _boom(_src: str, _dst: str) -> None:
        raise OSError("simulated replace failure")

    with (
        patch("drift.config.DriftConfig._find_config_file", return_value=config_file),
        patch("drift.commands.calibrate.os.replace", side_effect=_boom),
    ):
        result = runner.invoke(calibrate, ["reset", "--repo", str(tmp_path)])

    assert result.exit_code != 0
    remaining = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert remaining == original_data
