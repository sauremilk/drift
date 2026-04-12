"""Coverage tests for pipeline helpers, temporal_volatility, and rich_output helpers."""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from unittest.mock import patch

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    FileInfo,
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


class TestResolveWorkerCount:
    def test_cli_requested_workers_wins(self):
        from drift.pipeline import resolve_worker_count

        cfg = DriftConfig()
        files = [FileInfo(path=Path("a.py"), language="python", size_bytes=100, line_count=1)]

        got = resolve_worker_count(config=cfg, files=files, requested_workers=7)
        assert got == 7

    def test_env_override_wins_over_config_strategy(self):
        from drift.pipeline import resolve_worker_count

        cfg = DriftConfig()
        cfg.performance.worker_strategy = "auto"
        files = [FileInfo(path=Path("a.py"), language="python", size_bytes=100, line_count=1)]

        with patch.dict(os.environ, {"DRIFT_WORKERS": "5"}):
            got = resolve_worker_count(config=cfg, files=files, requested_workers=None)
        assert got == 5

    def test_auto_conservative_downscales_small_repo(self):
        from drift.pipeline import resolve_worker_count

        cfg = DriftConfig()
        cfg.performance.worker_strategy = "auto"
        cfg.performance.small_repo_file_threshold = 10
        cfg.performance.min_workers = 2
        cfg.performance.max_workers = 16

        files = [
            FileInfo(path=Path(f"f{i}.py"), language="python", size_bytes=100, line_count=1)
            for i in range(3)
        ]

        with patch("drift.pipeline.os.cpu_count", return_value=8):
            got = resolve_worker_count(config=cfg, files=files, requested_workers=None)

        # cpu fallback 8 -> small repo conservative downscale -> 4
        assert got == 4

    def test_auto_conservative_io_heavy_dampens_workers(self):
        from drift.pipeline import resolve_worker_count

        cfg = DriftConfig()
        cfg.performance.worker_strategy = "auto"
        cfg.performance.small_repo_file_threshold = 1
        cfg.performance.io_heavy_non_parser_ratio = 0.3
        cfg.performance.large_file_ratio_threshold = 0.25
        cfg.performance.large_file_size_bytes = 1000
        cfg.performance.min_workers = 2
        cfg.performance.max_workers = 16

        files = [
            FileInfo(path=Path("a.md"), language="markdown", size_bytes=2000, line_count=1),
            FileInfo(path=Path("b.json"), language="json", size_bytes=2000, line_count=1),
            FileInfo(path=Path("c.py"), language="python", size_bytes=100, line_count=1),
            FileInfo(path=Path("d.py"), language="python", size_bytes=100, line_count=1),
        ]

        with patch("drift.pipeline.os.cpu_count", return_value=8):
            got = resolve_worker_count(config=cfg, files=files, requested_workers=None)

        # base 8, non-parser ratio 0.5 -> -1, large file ratio 0.5 -> -1 => 6
        assert got == 6


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

    def test_extension_workspace_burst_is_dampened(self):
        from drift.signals.temporal_volatility import TemporalVolatilitySignal

        signal = TemporalVolatilitySignal()
        histories = {}

        for i in range(40):
            histories[f"src/core_{i}.py"] = FileHistory(
                path=Path(f"src/core_{i}.py"),
                total_commits=3,
                unique_authors=1,
                change_frequency_30d=1.0,
                defect_correlated_commits=0,
                first_seen=_days_ago(120),
                last_modified=_days_ago(90),
            )

        for i in range(8):
            histories[f"extensions/discord/src/file_{i}.ts"] = FileHistory(
                path=Path(f"extensions/discord/src/file_{i}.ts"),
                total_commits=45,
                unique_authors=10,
                change_frequency_30d=24.0,
                defect_correlated_commits=4,
                first_seen=_days_ago(3),
                last_modified=_days_ago(1),
            )

        findings = signal.analyze([], histories, DriftConfig())

        extension_findings = [
            f for f in findings if f.file_path.as_posix().startswith("extensions/discord/")
        ]
        assert extension_findings
        assert all(f.severity in ("info", "low") for f in extension_findings)
        assert all(f.score <= 0.45 for f in extension_findings)
        assert all(f.metadata.get("workspace_burst_dampened") is True for f in extension_findings)

    def test_test_like_files_are_skipped_from_volatility_findings(self):
        from drift.signals.temporal_volatility import TemporalVolatilitySignal

        signal = TemporalVolatilitySignal()
        histories = {}

        for i in range(9):
            histories[f"src/core_{i}.py"] = FileHistory(
                path=Path(f"src/core_{i}.py"),
                total_commits=3,
                unique_authors=1,
                change_frequency_30d=1.0,
                defect_correlated_commits=0,
            )

        histories["extensions/discord/src/monitor.test.ts"] = FileHistory(
            path=Path("extensions/discord/src/monitor.test.ts"),
            total_commits=80,
            unique_authors=19,
            change_frequency_30d=25.0,
            defect_correlated_commits=35,
            ai_attributed_commits=60,
        )
        histories["src/hot_module.py"] = FileHistory(
            path=Path("src/hot_module.py"),
            total_commits=55,
            unique_authors=12,
            change_frequency_30d=22.0,
            defect_correlated_commits=8,
            ai_attributed_commits=25,
        )

        findings = signal.analyze([], histories, DriftConfig())

        assert any(f.file_path.as_posix() == "src/hot_module.py" for f in findings)
        assert all(".test." not in f.file_path.as_posix() for f in findings)

    def test_generated_suffix_files_are_skipped_from_volatility_findings(self):
        from drift.signals.temporal_volatility import TemporalVolatilitySignal

        signal = TemporalVolatilitySignal()
        histories = {}

        for i in range(9):
            histories[f"src/stable_{i}.py"] = FileHistory(
                path=Path(f"src/stable_{i}.py"),
                total_commits=3,
                unique_authors=1,
                change_frequency_30d=1.0,
                defect_correlated_commits=0,
            )

        histories["src/config/bundled-channel-config-metadata.generated.ts"] = FileHistory(
            path=Path("src/config/bundled-channel-config-metadata.generated.ts"),
            total_commits=80,
            unique_authors=20,
            change_frequency_30d=30.0,
            defect_correlated_commits=12,
            ai_attributed_commits=50,
        )
        histories["src/hot_module.py"] = FileHistory(
            path=Path("src/hot_module.py"),
            total_commits=55,
            unique_authors=12,
            change_frequency_30d=22.0,
            defect_correlated_commits=8,
            ai_attributed_commits=25,
        )

        findings = signal.analyze([], histories, DriftConfig())

        assert any(f.file_path.as_posix() == "src/hot_module.py" for f in findings)
        assert all(
            ".generated." not in f.file_path.as_posix().lower()
            for f in findings
        )

    def test_issue_290_schema_base_generated_ts_is_skipped_from_volatility_findings(self):
        from drift.signals.temporal_volatility import TemporalVolatilitySignal

        signal = TemporalVolatilitySignal()
        histories = {}

        for i in range(9):
            histories[f"src/stable_{i}.py"] = FileHistory(
                path=Path(f"src/stable_{i}.py"),
                total_commits=3,
                unique_authors=1,
                change_frequency_30d=1.0,
                defect_correlated_commits=0,
            )

        histories["src/config/schema.base.generated.ts"] = FileHistory(
            path=Path("src/config/schema.base.generated.ts"),
            total_commits=90,
            unique_authors=24,
            change_frequency_30d=31.0,
            defect_correlated_commits=51,
            ai_attributed_commits=67,
        )
        histories["src/hot_module.py"] = FileHistory(
            path=Path("src/hot_module.py"),
            total_commits=55,
            unique_authors=12,
            change_frequency_30d=22.0,
            defect_correlated_commits=8,
            ai_attributed_commits=25,
        )

        findings = signal.analyze([], histories, DriftConfig())

        assert any(f.file_path.as_posix() == "src/hot_module.py" for f in findings)
        assert all(
            f.file_path.as_posix() != "src/config/schema.base.generated.ts"
            for f in findings
        )

    def test_generated_header_files_are_skipped_from_volatility_findings(self, tmp_path: Path):
        from drift.signals.temporal_volatility import TemporalVolatilitySignal

        generated_file = tmp_path / "channel-metadata.ts"
        generated_file.write_text(
            "// Auto-generated by scripts/generate-channel.ts. Do not edit directly.\n"
            "export const CHANNELS = [];\n",
            encoding="utf-8",
        )

        signal = TemporalVolatilitySignal()
        histories = {}

        for i in range(9):
            histories[f"src/stable_{i}.py"] = FileHistory(
                path=Path(f"src/stable_{i}.py"),
                total_commits=3,
                unique_authors=1,
                change_frequency_30d=1.0,
                defect_correlated_commits=0,
            )

        histories[str(generated_file)] = FileHistory(
            path=generated_file,
            total_commits=80,
            unique_authors=20,
            change_frequency_30d=30.0,
            defect_correlated_commits=12,
            ai_attributed_commits=50,
        )
        histories["src/hot_module.py"] = FileHistory(
            path=Path("src/hot_module.py"),
            total_commits=55,
            unique_authors=12,
            change_frequency_30d=22.0,
            defect_correlated_commits=8,
            ai_attributed_commits=25,
        )

        findings = signal.analyze([], histories, DriftConfig())

        generated_path = generated_file.as_posix()
        assert any(f.file_path.as_posix() == "src/hot_module.py" for f in findings)
        assert all(f.file_path.as_posix() != generated_path for f in findings)

    def test_non_plugin_outlier_keeps_high_severity(self):
        from drift.signals.temporal_volatility import TemporalVolatilitySignal

        signal = TemporalVolatilitySignal()
        histories = {}

        for i in range(12):
            histories[f"src/stable_{i}.py"] = FileHistory(
                path=Path(f"src/stable_{i}.py"),
                total_commits=2,
                unique_authors=1,
                change_frequency_30d=1.0,
                defect_correlated_commits=0,
                first_seen=_days_ago(200),
                last_modified=_days_ago(120),
            )

        histories["src/hotspot.py"] = FileHistory(
            path=Path("src/hotspot.py"),
            total_commits=40,
            unique_authors=8,
            change_frequency_30d=18.0,
            defect_correlated_commits=5,
            first_seen=_days_ago(200),
            last_modified=_days_ago(1),
        )

        findings = signal.analyze([], histories, DriftConfig())
        target = next((f for f in findings if f.file_path.as_posix() == "src/hotspot.py"), None)
        assert target is not None
        assert target.severity == "high"
        assert target.metadata.get("workspace_burst_dampened") is False

    def test_new_workspace_dampening_not_blocked_by_stale_last_modified(self):
        from drift.signals.temporal_volatility import TemporalVolatilitySignal

        signal = TemporalVolatilitySignal()
        histories = {}

        for i in range(30):
            histories[f"src/base_{i}.py"] = FileHistory(
                path=Path(f"src/base_{i}.py"),
                total_commits=3,
                unique_authors=1,
                change_frequency_30d=1.0,
                defect_correlated_commits=0,
                first_seen=_days_ago(140),
                last_modified=_days_ago(100),
            )

        for i in range(6):
            histories[f"extensions/telegram/src/file_{i}.ts"] = FileHistory(
                path=Path(f"extensions/telegram/src/file_{i}.ts"),
                total_commits=30,
                unique_authors=7,
                change_frequency_30d=18.0,
                defect_correlated_commits=3,
                first_seen=_days_ago(2),
                last_modified=_days_ago(1),
            )

        # Simulate a quiet file in a still-new workspace: stale last_modified must
        # not mark the workspace as established.
        histories["extensions/telegram/src/legacy.ts"] = FileHistory(
            path=Path("extensions/telegram/src/legacy.ts"),
            total_commits=18,
            unique_authors=4,
            change_frequency_30d=2.0,
            defect_correlated_commits=0,
            first_seen=_days_ago(2),
            last_modified=_days_ago(40),
        )

        findings = signal.analyze([], histories, DriftConfig())
        telegram_findings = [
            f for f in findings if f.file_path.as_posix().startswith("extensions/telegram/")
        ]

        assert telegram_findings
        assert all(f.metadata.get("workspace_burst_dampened") is True for f in telegram_findings)

    def test_mature_workspace_coordinated_burst_is_dampened(self):
        from drift.signals.temporal_volatility import TemporalVolatilitySignal

        signal = TemporalVolatilitySignal()
        histories = {}

        for i in range(40):
            histories[f"src/base_{i}.py"] = FileHistory(
                path=Path(f"src/base_{i}.py"),
                total_commits=3,
                unique_authors=1,
                change_frequency_30d=1.0,
                defect_correlated_commits=0,
                first_seen=_days_ago(180),
                last_modified=_days_ago(90),
            )

        # Mixed-age extension workspace: not "new", but under coordinated activity.
        for i in range(7):
            histories[f"extensions/acpx/src/active_{i}.ts"] = FileHistory(
                path=Path(f"extensions/acpx/src/active_{i}.ts"),
                total_commits=38,
                unique_authors=8,
                change_frequency_30d=17.0,
                defect_correlated_commits=3,
                first_seen=_days_ago(150),
                last_modified=_days_ago(2),
            )

        for i in range(5):
            histories[f"extensions/acpx/src/stable_{i}.ts"] = FileHistory(
                path=Path(f"extensions/acpx/src/stable_{i}.ts"),
                total_commits=9,
                unique_authors=2,
                change_frequency_30d=1.5,
                defect_correlated_commits=0,
                first_seen=_days_ago(220),
                last_modified=_days_ago(120),
            )

        findings = signal.analyze([], histories, DriftConfig())
        acpx_findings = [
            f for f in findings if f.file_path.as_posix().startswith("extensions/acpx/")
        ]

        assert acpx_findings
        assert all(f.metadata.get("workspace_burst_dampened") is True for f in acpx_findings)
        assert all(f.score <= 0.45 for f in acpx_findings)


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
