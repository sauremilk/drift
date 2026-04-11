"""Coverage tests for pipeline helpers, temporal_volatility, and rich_output helpers."""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from unittest.mock import patch

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    SignalType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.UTC)


def _days_ago(days: int) -> datetime.datetime:
    return _now() - datetime.timedelta(days=days)


# ===========================================================================
# Pipeline helpers
# ===========================================================================


class TestDetermineDefaultWorkers:
    def test_env_override_valid(self):
        from drift.pipeline import _determine_default_workers

        with patch.dict(os.environ, {"DRIFT_WORKERS": "4"}):
            assert _determine_default_workers() == 4

    def test_env_override_invalid(self):
        from drift.pipeline import _determine_default_workers

        with patch.dict(os.environ, {"DRIFT_WORKERS": "abc"}):
            result = _determine_default_workers()
            assert 2 <= result <= 16

    def test_env_override_zero(self):
        from drift.pipeline import _determine_default_workers

        with patch.dict(os.environ, {"DRIFT_WORKERS": "0"}):
            # 0 is < 1, so fallback to CPU-based
            result = _determine_default_workers()
            assert 2 <= result <= 16

    def test_no_env_var(self):
        from drift.pipeline import _determine_default_workers

        with patch.dict(os.environ, {}, clear=False):
            if "DRIFT_WORKERS" in os.environ:
                del os.environ["DRIFT_WORKERS"]
            result = _determine_default_workers()
            assert 2 <= result <= 16


class TestMakeDegradationEvent:
    def test_without_details(self):
        from drift.pipeline import make_degradation_event

        event = make_degradation_event(
            cause="git_error", component="ingestion", message="git not found"
        )
        assert event["cause"] == "git_error"
        assert event["component"] == "ingestion"
        assert "details" not in event

    def test_with_details(self):
        from drift.pipeline import make_degradation_event

        event = make_degradation_event(
            cause="git_error",
            component="ingestion",
            message="git not found",
            details={"exit_code": "127"},
        )
        assert event["details"] == {"exit_code": "127"}


class TestPruneGitHistoryCache:
    def test_removes_stale_entries(self):
        import drift.pipeline as pipeline_mod
        from drift.pipeline import (
            _GIT_HISTORY_CACHE_TTL_SECONDS,
            _prune_git_history_cache,
        )

        now = 1000.0
        stale_time = now - _GIT_HISTORY_CACHE_TTL_SECONDS - 1
        pipeline_mod._GIT_HISTORY_CACHE["stale_key"] = (stale_time, [], {})
        pipeline_mod._GIT_HISTORY_CACHE["fresh_key"] = (now, [], {})

        _prune_git_history_cache(now)

        assert "stale_key" not in pipeline_mod._GIT_HISTORY_CACHE
        assert "fresh_key" in pipeline_mod._GIT_HISTORY_CACHE

        # Cleanup
        pipeline_mod._GIT_HISTORY_CACHE.pop("fresh_key", None)


# ===========================================================================
# Temporal Volatility helpers
# ===========================================================================


class TestZScore:
    def test_normal_z_score(self):
        from drift.signals.temporal_volatility import _z_score

        assert _z_score(10.0, 5.0, 2.5) == 2.0

    def test_zero_std(self):
        from drift.signals.temporal_volatility import _z_score

        assert _z_score(10.0, 5.0, 0.0) == 0.0

    def test_clamped_high(self):
        from drift.signals.temporal_volatility import _z_score

        result = _z_score(100.0, 0.0, 1.0)
        assert result == 5.0

    def test_clamped_low(self):
        from drift.signals.temporal_volatility import _z_score

        result = _z_score(-100.0, 0.0, 1.0)
        assert result == -5.0


class TestShannonEntropy:
    def test_zero_total(self):
        from drift.signals.temporal_volatility import _shannon_entropy

        assert _shannon_entropy([0, 0, 0]) == 0.0

    def test_uniform_distribution(self):
        from drift.signals.temporal_volatility import _shannon_entropy

        result = _shannon_entropy([5, 5, 5, 5])
        assert abs(result - 2.0) < 0.01  # log2(4)

    def test_single_value(self):
        from drift.signals.temporal_volatility import _shannon_entropy

        assert _shannon_entropy([10]) == 0.0


class TestTemporalVolatilitySignal:
    def test_empty_histories_returns_empty(self):
        from drift.signals.temporal_volatility import TemporalVolatilitySignal

        signal = TemporalVolatilitySignal()
        findings = signal.analyze([], {}, DriftConfig())
        assert findings == []

    def test_all_zero_commit_histories(self):
        from drift.signals.temporal_volatility import TemporalVolatilitySignal

        signal = TemporalVolatilitySignal()
        histories = {
            "a.py": FileHistory(path=Path("a.py"), total_commits=0, unique_authors=0),
        }
        findings = signal.analyze([], histories, DriftConfig())
        assert findings == []

    def test_detects_volatile_file(self):
        from drift.signals.temporal_volatility import TemporalVolatilitySignal

        signal = TemporalVolatilitySignal()

        # Create baseline: 9 calm files with low churn
        histories = {}
        for i in range(9):
            histories[f"file{i}.py"] = FileHistory(
                path=Path(f"file{i}.py"),
                total_commits=3,
                unique_authors=1,
                change_frequency_30d=1.0,
                defect_correlated_commits=0,
            )

        # One volatile outlier
        histories["hot.py"] = FileHistory(
            path=Path("hot.py"),
            total_commits=50,
            unique_authors=10,
            change_frequency_30d=20.0,
            defect_correlated_commits=5,
        )

        findings = signal.analyze([], histories, DriftConfig())
        assert len(findings) >= 1
        assert findings[0].signal_type == SignalType.TEMPORAL_VOLATILITY

    def test_ai_boost_applied(self):
        from drift.signals.temporal_volatility import TemporalVolatilitySignal

        signal = TemporalVolatilitySignal()

        histories = {}
        for i in range(9):
            histories[f"file{i}.py"] = FileHistory(
                path=Path(f"file{i}.py"),
                total_commits=3,
                unique_authors=1,
                change_frequency_30d=1.0,
                defect_correlated_commits=0,
            )

        histories["ai_file.py"] = FileHistory(
            path=Path("ai_file.py"),
            total_commits=50,
            unique_authors=5,
            change_frequency_30d=15.0,
            defect_correlated_commits=3,
            ai_attributed_commits=40,  # ai_ratio = 0.8
        )

        findings = signal.analyze([], histories, DriftConfig())
        assert len(findings) >= 1
        # At least one finding should have ai_attributed=True
        ai_findings = [f for f in findings if f.ai_attributed]
        assert len(ai_findings) >= 1


# ===========================================================================
# Rich output helpers
# ===========================================================================


class TestSignalLabel:
    def test_known_signal(self):
        from drift.output.rich_output import _signal_label

        # Known signals should not return the raw type
        label = _signal_label("pattern_fragmentation")
        assert isinstance(label, str)

    def test_unknown_signal_fallback(self):
        from drift.output.rich_output import _signal_label

        label = _signal_label("nonexistent_signal_type_xyz")
        assert label == "nonexistent_signal_type_xyz"


class TestScoreBar:
    def test_high_score_red(self):
        from drift.output.rich_output import _score_bar

        bar = _score_bar(0.9)
        assert "0.90" in bar.plain

    def test_medium_score_yellow(self):
        from drift.output.rich_output import _score_bar

        bar = _score_bar(0.5)
        assert "0.50" in bar.plain

    def test_low_score_green(self):
        from drift.output.rich_output import _score_bar

        bar = _score_bar(0.2)
        assert "0.20" in bar.plain


class TestSparkline:
    def test_empty_values(self):
        from drift.output.rich_output import _sparkline

        assert _sparkline([]) == ""

    def test_equal_values(self):
        from drift.output.rich_output import _sparkline

        result = _sparkline([5.0, 5.0, 5.0])
        assert len(result) == 3

    def test_ascending_values(self):
        from drift.output.rich_output import _sparkline

        result = _sparkline([0.0, 0.5, 1.0])
        assert len(result) == 3


class TestReadCodeSnippet:
    def test_none_file_path(self):
        from drift.output.rich_output import _read_code_snippet

        assert _read_code_snippet(None, 1) is None

    def test_none_start_line(self):
        from drift.output.rich_output import _read_code_snippet

        assert _read_code_snippet(Path("file.py"), None) is None

    def test_nonexistent_file(self):
        from drift.output.rich_output import _read_code_snippet

        assert _read_code_snippet(Path("/nonexistent/path.py"), 1) is None

    def test_valid_file(self, tmp_path: Path):
        from drift.output.rich_output import _read_code_snippet

        f = tmp_path / "example.py"
        f.write_text("line1\nline2\nline3\nline4\nline5\n", encoding="utf-8")

        snippet = _read_code_snippet(f, 2)
        assert snippet is not None
        assert "line2" in snippet.plain

    def test_with_repo_root(self, tmp_path: Path):
        from drift.output.rich_output import _read_code_snippet

        f = tmp_path / "src" / "module.py"
        f.parent.mkdir(parents=True)
        f.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")

        snippet = _read_code_snippet(
            Path("src/module.py"),
            1,
            repo_root=tmp_path,
        )
        assert snippet is not None

    def test_with_end_line(self, tmp_path: Path):
        from drift.output.rich_output import _read_code_snippet

        f = tmp_path / "example.py"
        f.write_text("line1\nline2\nline3\nline4\nline5\n", encoding="utf-8")

        snippet = _read_code_snippet(f, 2, end_line=4)
        assert snippet is not None
        assert "line3" in snippet.plain
