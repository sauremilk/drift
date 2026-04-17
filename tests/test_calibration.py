"""Tests for drift.calibration — feedback, profile builder, and correlators."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


def _fe(
    signal: str = "pfs",
    file: str = "a.py",
    verdict: str = "tp",
    source: str = "user",
    **kw: object,
) -> object:
    """Shorthand for creating a FeedbackEvent in tests."""
    from drift.calibration.feedback import FeedbackEvent

    return FeedbackEvent(
        signal_type=signal,
        file_path=file,
        verdict=verdict,  # type: ignore[arg-type]
        source=source,  # type: ignore[arg-type]
        **kw,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Feedback persistence tests
# ---------------------------------------------------------------------------


class TestFeedbackEvent:
    def test_create_event(self) -> None:
        from drift.calibration.feedback import FeedbackEvent

        event = FeedbackEvent(
            signal_type="pattern_fragmentation",
            file_path="src/foo.py",
            verdict="fp",
            source="user",
        )
        assert event.signal_type == "pattern_fragmentation"
        assert event.verdict == "fp"
        assert event.source == "user"
        assert event.finding_id  # auto-generated
        assert event.timestamp  # auto-generated

    def test_finding_id_stable(self) -> None:
        from drift.calibration.feedback import FeedbackEvent

        e1 = FeedbackEvent(signal_type="a", file_path="b.py", verdict="tp", source="user")
        e2 = FeedbackEvent(signal_type="a", file_path="b.py", verdict="fp", source="user")
        assert e1.finding_id == e2.finding_id  # same signal+file → same id

    def test_finding_id_differs(self) -> None:
        from drift.calibration.feedback import FeedbackEvent

        e1 = FeedbackEvent(signal_type="a", file_path="b.py", verdict="tp", source="user")
        e2 = FeedbackEvent(signal_type="a", file_path="c.py", verdict="tp", source="user")
        assert e1.finding_id != e2.finding_id


class TestFeedbackPersistence:
    def test_roundtrip(self, tmp_path: Path) -> None:
        from drift.calibration.feedback import load_feedback, record_feedback

        fp = tmp_path / ".drift" / "feedback.jsonl"
        event = _fe(signal="mutant_duplicate", file="src/x.py")
        record_feedback(fp, event)  # type: ignore[arg-type]
        record_feedback(fp, event)  # type: ignore[arg-type]

        loaded = load_feedback(fp)
        assert len(loaded) == 2
        assert loaded[0].signal_type == "mutant_duplicate"
        assert loaded[0].verdict == "tp"

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        from drift.calibration.feedback import load_feedback

        assert load_feedback(tmp_path / "nope.jsonl") == []

    def test_load_skips_malformed(self, tmp_path: Path) -> None:
        from drift.calibration.feedback import load_feedback, record_feedback

        fp = tmp_path / "f.jsonl"
        record_feedback(fp, _fe(signal="a", file="b"))  # type: ignore[arg-type]
        # Append garbage
        with fp.open("a", encoding="utf-8") as f:
            f.write("NOT-JSON\n")
        record_feedback(  # type: ignore[arg-type]
            fp,
            _fe(signal="c", file="d", verdict="fp"),
        )

        loaded = load_feedback(fp)
        assert len(loaded) == 2  # skipped the bad line

    def test_load_feedback_with_stats_counts_and_warns_on_skipped_lines(
        self, tmp_path: Path, caplog
    ) -> None:
        from drift.calibration.feedback import load_feedback_with_stats, record_feedback

        fp = tmp_path / "f.jsonl"
        record_feedback(fp, _fe(signal="a", file="b"))  # type: ignore[arg-type]
        with fp.open("a", encoding="utf-8") as f:
            f.write("NOT-JSON\n")
            f.write('{"signal_type":"pfs"}\n')
        record_feedback(fp, _fe(signal="c", file="d", verdict="fp"))  # type: ignore[arg-type]

        with caplog.at_level(logging.WARNING):
            loaded, skipped = load_feedback_with_stats(fp)

        assert len(loaded) == 2
        assert skipped == 2
        assert "skipped 2 malformed" in caplog.text


class TestFeedbackSummary:
    def test_summary(self) -> None:
        from drift.calibration.feedback import feedback_summary

        events = [
            _fe(signal="pfs", file="a"),
            _fe(signal="pfs", file="b", verdict="fp"),
            _fe(signal="pfs", file="c"),
            _fe(signal="avs", file="d", verdict="fn"),
        ]
        s = feedback_summary(events)  # type: ignore[arg-type]
        assert s["pfs"] == {"tp": 2, "fp": 1, "fn": 0}
        assert s["avs"] == {"tp": 0, "fp": 0, "fn": 1}

    def test_summary_dedupes_cross_source_by_signal_and_file(self) -> None:
        from drift.calibration.feedback import feedback_summary

        events = [
            _fe(signal="pfs", file="a.py", verdict="fp", source="user"),
            _fe(signal="pfs", file="a.py", verdict="tp", source="git_correlation"),
            _fe(signal="pfs", file="b.py", verdict="tp", source="git_correlation"),
        ]

        s = feedback_summary(events)  # type: ignore[arg-type]
        assert s["pfs"] == {"tp": 1, "fp": 1, "fn": 0}


# ---------------------------------------------------------------------------
# Profile builder tests
# ---------------------------------------------------------------------------


class TestProfileBuilder:
    def test_cold_start_returns_defaults(self) -> None:
        """No events → calibrated weights identical to defaults."""
        from drift.calibration.profile_builder import build_profile
        from drift.config import SignalWeights

        defaults = SignalWeights()
        result = build_profile([], defaults)

        assert result.total_events == 0
        assert result.signals_with_data == 0
        for key, val in defaults.as_dict().items():
            assert abs(result.calibrated_weights.as_dict()[key] - val) < 0.0001

    def test_pure_tp_keeps_weight(self) -> None:
        """All TP → weight stays close to default (precision=1.0)."""
        from drift.calibration.profile_builder import build_profile
        from drift.config import SignalWeights

        sig = "pattern_fragmentation"
        events = [_fe(signal=sig, file=f"f{i}.py") for i in range(25)]
        defaults = SignalWeights()
        result = build_profile(events, defaults, min_samples=20)

        pfs_w = result.calibrated_weights.as_dict()[sig]
        default_pfs = defaults.as_dict()[sig]
        assert abs(pfs_w - default_pfs) < 0.01

    def test_pure_fp_reduces_weight(self) -> None:
        """All FP → weight reduced significantly."""
        from drift.calibration.profile_builder import build_profile
        from drift.config import SignalWeights

        sig = "pattern_fragmentation"
        events = [_fe(signal=sig, file=f"f{i}.py", verdict="fp") for i in range(25)]
        defaults = SignalWeights()
        result = build_profile(events, defaults, min_samples=20)

        pfs_w = result.calibrated_weights.as_dict()[sig]
        default_pfs = defaults.as_dict()[sig]
        assert pfs_w < default_pfs * 0.1
        assert pfs_w >= 0.001  # floor

    def test_mixed_feedback(self) -> None:
        """Mixed TP/FP → weight is between default and zero."""
        from drift.calibration.profile_builder import build_profile
        from drift.config import SignalWeights

        sig = "pattern_fragmentation"
        events = [_fe(signal=sig, file=f"tp{i}.py") for i in range(15)] + [
            _fe(signal=sig, file=f"fp{i}.py", verdict="fp") for i in range(5)
        ]
        defaults = SignalWeights()
        result = build_profile(events, defaults, min_samples=20)

        pfs_w = result.calibrated_weights.as_dict()[sig]
        default_pfs = defaults.as_dict()[sig]
        assert pfs_w < default_pfs
        assert pfs_w > default_pfs * 0.5

    def test_low_confidence_stays_near_default(self) -> None:
        """Few observations → weight barely changes from default."""
        from drift.calibration.profile_builder import build_profile
        from drift.config import SignalWeights

        sig = "pattern_fragmentation"
        events = [
            _fe(signal=sig, file="fp1.py", verdict="fp"),
            _fe(signal=sig, file="fp2.py", verdict="fp"),
        ]
        defaults = SignalWeights()
        result = build_profile(events, defaults, min_samples=20)

        pfs_w = result.calibrated_weights.as_dict()[sig]
        default_pfs = defaults.as_dict()[sig]
        assert pfs_w > default_pfs * 0.8

    def test_weight_diff(self) -> None:
        from drift.calibration.profile_builder import build_profile
        from drift.config import SignalWeights

        sig = "pattern_fragmentation"
        events = [_fe(signal=sig, file=f"fp{i}.py", verdict="fp") for i in range(25)]
        defaults = SignalWeights()
        result = build_profile(events, defaults, min_samples=20)
        diff = result.weight_diff(defaults)

        assert sig in diff
        assert diff[sig]["delta"] < 0

    def test_fn_boost(self) -> None:
        """Signals with many FN get a weight boost."""
        from drift.calibration.profile_builder import build_profile
        from drift.config import SignalWeights

        sig = "architecture_violation"
        events = [_fe(signal=sig, file=f"tp{i}.py") for i in range(10)] + [
            _fe(signal=sig, file=f"fn{i}.py", verdict="fn") for i in range(10)
        ]
        defaults = SignalWeights()
        result_boost = build_profile(events, defaults, min_samples=20, fn_boost_factor=0.5)
        result_no_boost = build_profile(events, defaults, min_samples=20, fn_boost_factor=0.0)

        w_boost = result_boost.calibrated_weights.as_dict()["architecture_violation"]
        w_no_boost = result_no_boost.calibrated_weights.as_dict()["architecture_violation"]
        assert w_boost > w_no_boost

    def test_unattributed_fn_is_distributed_for_fn_boost(self) -> None:
        """Unattributed FN events should still influence FN boosting."""
        from drift.calibration.profile_builder import build_profile
        from drift.config import SignalWeights

        sig = "architecture_violation"
        events = [_fe(signal=sig, file=f"tp{i}.py") for i in range(10)] + [
            _fe(signal=sig, file=f"fp{i}.py", verdict="fp") for i in range(10)
        ] + [_fe(signal="_unattributed", file=f"fn{i}.py", verdict="fn") for i in range(10)]

        defaults = SignalWeights()
        result_with_unattributed = build_profile(
            events,
            defaults,
            min_samples=20,
            fn_boost_factor=0.5,
        )
        result_without_unattributed = build_profile(
            events[:-10],
            defaults,
            min_samples=20,
            fn_boost_factor=0.5,
        )

        w_with = result_with_unattributed.calibrated_weights.as_dict()[sig]
        w_without = result_without_unattributed.calibrated_weights.as_dict()[sig]
        assert w_with > w_without

    def test_floor_clamp_is_reported_and_warned(self, caplog: pytest.LogCaptureFixture) -> None:
        """Signals clamped to floor are recorded and emit a warning."""
        import logging

        from drift.calibration.profile_builder import build_profile
        from drift.config import SignalWeights

        sig = "pattern_fragmentation"
        events = [_fe(signal=sig, file=f"fp{i}.py", verdict="fp") for i in range(25)]
        defaults = SignalWeights()

        with caplog.at_level(logging.WARNING):
            result = build_profile(events, defaults, min_samples=20)

        assert sig in result.clamped_signals
        assert any(
            f"Signal {sig} calibrated to minimum floor" in rec.getMessage()
            for rec in caplog.records
        )


# ---------------------------------------------------------------------------
# Scan history tests
# ---------------------------------------------------------------------------


class TestScanHistory:
    def test_save_and_load(self, tmp_path: Path) -> None:
        from drift.calibration.history import (
            FindingSnapshot,
            ScanSnapshot,
            load_snapshots,
            save_snapshot,
        )

        snap = ScanSnapshot(
            drift_score=0.42,
            finding_count=3,
            findings=[
                FindingSnapshot(signal_type="pfs", file_path="a.py", score=0.8),
                FindingSnapshot(signal_type="avs", file_path="b.py", score=0.6),
                FindingSnapshot(signal_type="mds", file_path="c.py", score=0.4),
            ],
        )
        history_dir = tmp_path / "history"
        save_snapshot(history_dir, snap)

        loaded = load_snapshots(history_dir)
        assert len(loaded) == 1
        assert loaded[0].drift_score == 0.42
        assert len(loaded[0].findings) == 3

    def test_pruning(self, tmp_path: Path) -> None:
        from drift.calibration.history import ScanSnapshot, load_snapshots, save_snapshot

        history_dir = tmp_path / "history"
        for i in range(25):
            save_snapshot(
                history_dir,
                ScanSnapshot(drift_score=float(i) / 100),
                max_snapshots=10,
            )

        loaded = load_snapshots(history_dir)
        assert len(loaded) <= 10


# ---------------------------------------------------------------------------
# Outcome correlator tests
# ---------------------------------------------------------------------------


class TestOutcomeCorrelator:
    def test_tp_correlation(self) -> None:
        from drift.calibration.history import FindingSnapshot, ScanSnapshot
        from drift.calibration.outcome_correlator import correlate_outcomes

        now = datetime.now(UTC)
        scan_ts = (now - timedelta(days=40)).isoformat()

        snapshots = [
            ScanSnapshot(
                timestamp=scan_ts,
                findings=[
                    FindingSnapshot(signal_type="pfs", file_path="src/foo.py"),
                ],
            )
        ]
        commits = [
            {
                "timestamp": (now - timedelta(days=25)).isoformat(),
                "message": "fix: resolve null pointer in foo",
                "files_changed": ["src/foo.py"],
            }
        ]

        events = correlate_outcomes(snapshots, commits, correlation_window_days=30)
        assert len(events) == 1
        assert events[0].verdict == "tp"
        assert events[0].source == "git_correlation"

    def test_no_fix_creates_weak_fp(self) -> None:
        from drift.calibration.history import FindingSnapshot, ScanSnapshot
        from drift.calibration.outcome_correlator import correlate_outcomes

        now = datetime.now(UTC)
        scan_ts = (now - timedelta(days=90)).isoformat()

        snapshots = [
            ScanSnapshot(
                timestamp=scan_ts,
                findings=[
                    FindingSnapshot(signal_type="pfs", file_path="src/bar.py"),
                ],
            )
        ]
        # No defect commits at all
        events = correlate_outcomes(snapshots, [], weak_fp_window_days=60)
        assert len(events) == 1
        assert events[0].verdict == "fp"

    def test_empty_inputs(self) -> None:
        from drift.calibration.outcome_correlator import correlate_outcomes

        assert correlate_outcomes([], []) == []


# ---------------------------------------------------------------------------
# CalibrationConfig tests
# ---------------------------------------------------------------------------


class TestCalibrationConfig:
    def test_default_values(self) -> None:
        from drift.config import CalibrationConfig

        cfg = CalibrationConfig()
        assert cfg.enabled is False
        assert cfg.min_samples == 20
        assert cfg.correlation_window_days == 30
        assert cfg.decay_days == 90
        assert "bug" in cfg.bug_labels

    def test_config_load_with_calibration(self, tmp_path: Path) -> None:
        from drift.config import DriftConfig

        (tmp_path / "drift.yaml").write_text(
            "calibration:\n  enabled: true\n  min_samples: 10\n",
            encoding="utf-8",
        )
        cfg = DriftConfig.load(tmp_path)
        assert cfg.calibration.enabled is True
        assert cfg.calibration.min_samples == 10

    def test_config_load_without_calibration(self, tmp_path: Path) -> None:
        from drift.config import DriftConfig

        (tmp_path / "drift.yaml").write_text("fail_on: medium\n", encoding="utf-8")
        cfg = DriftConfig.load(tmp_path)
        assert cfg.calibration.enabled is False  # default


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


class TestCalibrationIntegration:
    def test_feedback_to_calibrate_roundtrip(self, tmp_path: Path) -> None:
        """Full pipeline: record feedback → build profile → verify."""
        from drift.calibration.feedback import load_feedback, record_feedback
        from drift.calibration.profile_builder import build_profile
        from drift.config import SignalWeights

        feedback_path = tmp_path / ".drift" / "feedback.jsonl"

        # Record lots of FP for one signal
        for i in range(25):
            record_feedback(
                feedback_path,
                _fe(  # type: ignore[arg-type]
                    signal="guard_clause_deficit",
                    file=f"scripts/etl_{i}.py",
                    verdict="fp",
                    evidence={"reason": "data script, not API"},
                ),
            )

        # Record TPs for another
        for i in range(20):
            record_feedback(
                feedback_path,
                _fe(  # type: ignore[arg-type]
                    signal="architecture_violation",
                    file=f"src/api/handler_{i}.py",
                ),
            )

        events = load_feedback(feedback_path)
        defaults = SignalWeights()
        result = build_profile(events, defaults, min_samples=20)

        gcd_w = result.calibrated_weights.as_dict()["guard_clause_deficit"]
        avs_w = result.calibrated_weights.as_dict()["architecture_violation"]
        gcd_default = defaults.as_dict()["guard_clause_deficit"]
        avs_default = defaults.as_dict()["architecture_violation"]

        # GCD should be significantly reduced (all FP)
        assert gcd_w < gcd_default * 0.1
        # AVS should stay near default (all TP)
        assert abs(avs_w - avs_default) < 0.01


# ---------------------------------------------------------------------------
# AP1: Finding-ID with start_line tests
# ---------------------------------------------------------------------------


class TestFindingIdWithStartLine:
    def test_same_file_different_lines_different_ids(self) -> None:
        """Two findings at different lines produce distinct IDs."""
        from drift.calibration.feedback import FeedbackEvent

        e1 = FeedbackEvent(
            signal_type="pfs",
            file_path="a.py",
            verdict="tp",
            source="user",
            start_line=10,
        )
        e2 = FeedbackEvent(
            signal_type="pfs",
            file_path="a.py",
            verdict="tp",
            source="user",
            start_line=42,
        )
        assert e1.finding_id != e2.finding_id

    def test_no_start_line_backward_compat(self) -> None:
        """Event without start_line produces the same ID as before."""
        from drift.calibration.feedback import FeedbackEvent, _compute_finding_id

        e = FeedbackEvent(
            signal_type="x",
            file_path="y.py",
            verdict="fp",
            source="user",
        )
        legacy_id = _compute_finding_id("x", "y.py")
        assert e.finding_id == legacy_id

    def test_finding_id_for_public_api(self) -> None:
        from drift.calibration.feedback import finding_id_for

        id_no_line = finding_id_for("pfs", "a.py")
        id_with_line = finding_id_for("pfs", "a.py", start_line=7)
        assert id_no_line != id_with_line

    def test_roundtrip_with_start_line(self, tmp_path: Path) -> None:
        from drift.calibration.feedback import load_feedback, record_feedback

        fp = tmp_path / "fb.jsonl"
        event = _fe(signal="pfs", file="x.py", start_line=99)
        record_feedback(fp, event)  # type: ignore[arg-type]
        loaded = load_feedback(fp)
        assert len(loaded) == 1
        assert loaded[0].start_line == 99

    def test_roundtrip_without_start_line(self, tmp_path: Path) -> None:
        from drift.calibration.feedback import load_feedback, record_feedback

        fp = tmp_path / "fb.jsonl"
        event = _fe(signal="avs", file="z.py")
        record_feedback(fp, event)  # type: ignore[arg-type]
        loaded = load_feedback(fp)
        assert len(loaded) == 1
        assert loaded[0].start_line is None


# ---------------------------------------------------------------------------
# AP3: Feedback metrics tests
# ---------------------------------------------------------------------------


class TestFeedbackMetrics:
    def test_mixed_signals(self) -> None:
        from drift.calibration.feedback import feedback_metrics

        events = [
            _fe(signal="pfs", file="a", verdict="tp"),
            _fe(signal="pfs", file="b", verdict="fp"),
            _fe(signal="pfs", file="c", verdict="fn"),
            _fe(signal="avs", file="d", verdict="tp"),
            _fe(signal="avs", file="e", verdict="tp"),
        ]
        m = feedback_metrics(events)  # type: ignore[arg-type]
        pfs = m["pfs"]
        assert pfs.tp == 1
        assert pfs.fp == 1
        assert pfs.fn == 1
        assert pfs.precision == 0.5
        assert pfs.recall == 0.5
        assert pfs.f1 == 0.5

        avs = m["avs"]
        assert avs.precision == 1.0
        assert avs.recall == 1.0
        assert avs.f1 == 1.0

    def test_only_fn(self) -> None:
        """Only FN events → precision=1.0, recall computable."""
        from drift.calibration.feedback import feedback_metrics

        events = [
            _fe(signal="mds", file="a", verdict="fn"),
            _fe(signal="mds", file="b", verdict="fn"),
        ]
        m = feedback_metrics(events)  # type: ignore[arg-type]
        mds = m["mds"]
        assert mds.precision == 1.0  # no FP/TP → default
        assert mds.recall == 0.0
        assert mds.f1 == 0.0

    def test_empty_events(self) -> None:
        from drift.calibration.feedback import feedback_metrics

        assert feedback_metrics([]) == {}


# ---------------------------------------------------------------------------
# AP4: Threshold adapter tests
# ---------------------------------------------------------------------------


class TestThresholdAdapter:
    def test_disabled_returns_base(self) -> None:
        from drift.calibration.feedback import SignalFeedbackMetrics
        from drift.calibration.threshold_adapter import adapt_threshold

        m = SignalFeedbackMetrics("pfs", tp=0, fp=20, fn=0)
        result = adapt_threshold("pfs", 0.5, m, enabled=False)
        assert result.adapted_threshold == 0.5
        assert result.adjustment == 0.0

    def test_none_metrics_returns_base(self) -> None:
        from drift.calibration.threshold_adapter import adapt_threshold

        result = adapt_threshold("pfs", 0.5, None, enabled=True)
        assert result.adapted_threshold == 0.5

    def test_high_fp_raises_threshold(self) -> None:
        from drift.calibration.feedback import SignalFeedbackMetrics
        from drift.calibration.threshold_adapter import adapt_threshold

        m = SignalFeedbackMetrics("pfs", tp=2, fp=18, fn=0)
        result = adapt_threshold("pfs", 0.5, m, enabled=True, min_observations=5)
        assert result.adapted_threshold > 0.5

    def test_high_fn_lowers_threshold(self) -> None:
        from drift.calibration.feedback import SignalFeedbackMetrics
        from drift.calibration.threshold_adapter import adapt_threshold

        m = SignalFeedbackMetrics("pfs", tp=5, fp=0, fn=15)
        result = adapt_threshold("pfs", 0.5, m, enabled=True, min_observations=5)
        assert result.adapted_threshold < 0.5

    def test_clamping_at_min(self) -> None:
        from drift.calibration.feedback import SignalFeedbackMetrics
        from drift.calibration.threshold_adapter import adapt_threshold

        m = SignalFeedbackMetrics("pfs", tp=1, fp=0, fn=99)
        result = adapt_threshold(
            "pfs",
            0.15,
            m,
            enabled=True,
            min_threshold=0.1,
            min_observations=1,
        )
        assert result.adapted_threshold >= 0.1
        assert result.clamped

    def test_clamping_at_max(self) -> None:
        from drift.calibration.feedback import SignalFeedbackMetrics
        from drift.calibration.threshold_adapter import adapt_threshold

        m = SignalFeedbackMetrics("pfs", tp=1, fp=99, fn=0)
        result = adapt_threshold(
            "pfs",
            0.9,
            m,
            enabled=True,
            max_threshold=0.95,
            min_observations=1,
        )
        assert result.adapted_threshold <= 0.95

    def test_insufficient_observations_returns_base(self) -> None:
        from drift.calibration.feedback import SignalFeedbackMetrics
        from drift.calibration.threshold_adapter import adapt_threshold

        m = SignalFeedbackMetrics("pfs", tp=1, fp=1, fn=0)
        result = adapt_threshold(
            "pfs",
            0.5,
            m,
            enabled=True,
            min_observations=10,
        )
        assert result.adapted_threshold == 0.5


# ---------------------------------------------------------------------------
# AP4: CalibrationConfig threshold gate test
# ---------------------------------------------------------------------------


class TestCalibrationConfigThresholdGate:
    def test_default_disabled(self) -> None:
        from drift.config import CalibrationConfig

        cfg = CalibrationConfig()
        assert cfg.threshold_adaptation_enabled is False

    def test_enable_via_yaml(self, tmp_path: Path) -> None:
        from drift.config import DriftConfig

        (tmp_path / "drift.yaml").write_text(
            "calibration:\n  threshold_adaptation_enabled: true\n",
            encoding="utf-8",
        )
        cfg = DriftConfig.load(tmp_path)
        assert cfg.calibration.threshold_adaptation_enabled is True
