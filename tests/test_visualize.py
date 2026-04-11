"""Tests for drift visualize command (C1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


class TestVisualizeCommand:
    """Test the visualize CLI command."""

    def test_visualize_without_textual_shows_error(self) -> None:
        """When textual is not installed, show a helpful error message."""
        from drift.commands.visualize import visualize

        runner = CliRunner()
        with (
            patch("drift.commands.visualize.console"),
            patch.dict("sys.modules", {"drift.output.tui_renderer": None}),
        ):
            # Simulate ImportError by patching the import
            original_import = (
                __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__
            )

            def mock_import(name, *args, **kwargs):
                if name == "drift.output.tui_renderer":
                    raise ImportError("No module named 'textual'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = runner.invoke(visualize, ["--repo", "."])
                assert result.exit_code != 0

    def test_visualize_no_modules_exits_gracefully(self, tmp_path: Path) -> None:
        """When no module scores exist, show a message instead of crashing."""
        from drift.commands.visualize import visualize
        from drift.models import RepoAnalysis

        runner = CliRunner()
        mock_analysis = MagicMock(spec=RepoAnalysis)
        mock_analysis.module_scores = []

        with (
            patch("drift.analyzer.analyze_repo", return_value=mock_analysis),
            patch("drift.config.DriftConfig.load", return_value=MagicMock()),
        ):
            result = runner.invoke(visualize, ["--repo", str(tmp_path)])
            # Should not crash
            assert result.exit_code == 0


class TestTuiRenderer:
    """Test the TUI renderer components."""

    def test_severity_label(self) -> None:
        from drift.output.tui_renderer import _severity_label

        assert _severity_label(0.9) == "critical"
        assert _severity_label(0.7) == "high"
        assert _severity_label(0.5) == "medium"
        assert _severity_label(0.3) == "low"
        assert _severity_label(0.1) == "info"

    def test_score_bar(self) -> None:
        from drift.output.tui_renderer import _score_bar

        bar = _score_bar(0.5, 10)
        assert len(bar) == 10
        assert "█" in bar
        assert "░" in bar

    def test_score_bar_full(self) -> None:
        from drift.output.tui_renderer import _score_bar

        bar = _score_bar(1.0, 10)
        assert bar == "█" * 10

    def test_score_bar_empty(self) -> None:
        from drift.output.tui_renderer import _score_bar

        bar = _score_bar(0.0, 10)
        assert bar == "░" * 10

    def test_app_creation(self) -> None:
        """TUI app can be instantiated with a RepoAnalysis."""
        import datetime

        from drift.models import ModuleScore, RepoAnalysis
        from drift.output.tui_renderer import DriftVisualizeApp

        analysis = RepoAnalysis(
            repo_path=Path("."),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.42,
            module_scores=[
                ModuleScore(
                    path=Path("src/auth"),
                    drift_score=0.6,
                    file_count=5,
                    function_count=20,
                ),
                ModuleScore(
                    path=Path("src/api"),
                    drift_score=0.3,
                    file_count=3,
                    function_count=10,
                ),
            ],
            total_files=8,
        )
        app = DriftVisualizeApp(analysis)
        assert app._analysis is analysis
        assert len(app._modules) == 2
        # Sorted by score descending
        assert app._modules[0].drift_score >= app._modules[1].drift_score

    def test_build_summary_contains_core_metrics(self) -> None:
        """Summary bar should include score, module count, finding count and files."""
        import datetime

        from drift.models import RepoAnalysis
        from drift.output.tui_renderer import DriftVisualizeApp

        analysis = RepoAnalysis(
            repo_path=Path("."),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.61,
            module_scores=[],
            findings=[],
            total_files=12,
        )
        app = DriftVisualizeApp(analysis)
        summary = app._build_summary()

        assert "Drift Score" in summary
        assert "Modules:" in summary
        assert "Findings:" in summary
        assert "Files:" in summary

    def test_build_detail_renders_signal_breakdown_and_findings(self) -> None:
        """Detail pane should render module metadata, signal bars and finding lines."""
        import datetime

        from drift.models import Finding, ModuleScore, RepoAnalysis, Severity
        from drift.output.tui_renderer import DriftVisualizeApp

        finding = Finding(
            signal_type="pattern_fragmentation",
            severity=Severity.HIGH,
            score=0.74,
            title="Fragmented helper",
            description="Duplicate helper implementation found.",
            file_path=Path("src/app/helpers.py"),
            start_line=33,
        )
        module = ModuleScore(
            path=Path("src/app"),
            drift_score=0.67,
            signal_scores={
                "pattern_fragmentation": 0.67,
                "architecture_violation": 0.11,
            },
            findings=[finding],
            file_count=4,
            function_count=12,
            ai_ratio=0.25,
        )
        analysis = RepoAnalysis(
            repo_path=Path("."),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.67,
            module_scores=[module],
            findings=[finding],
            total_files=4,
        )

        app = DriftVisualizeApp(analysis)
        detail = app._build_detail(module)

        assert "Signal Scores" in detail
        assert "Findings (1)" in detail
        assert "pattern_fragmentation" in detail
        assert "helpers.py:33" in detail

    def test_mount_and_selection_update_detail_panel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exercise table population and detail update callbacks without full TUI runtime."""
        import datetime

        from drift.models import ModuleScore, RepoAnalysis
        from drift.output.tui_renderer import DriftVisualizeApp

        module = ModuleScore(
            path=Path("src/app"),
            drift_score=0.67,
            signal_scores={"pattern_fragmentation": 0.67},
            findings=[],
            file_count=4,
            function_count=12,
            ai_ratio=0.25,
        )
        analysis = RepoAnalysis(
            repo_path=Path("."),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.67,
            module_scores=[module],
            findings=[],
            total_files=4,
        )
        app = DriftVisualizeApp(analysis)

        class FakeTable:
            def __init__(self) -> None:
                self.columns: list[tuple[str, ...]] = []
                self.rows: list[tuple[str, ...]] = []

            def add_columns(self, *cols: str) -> None:
                self.columns.append(cols)

            def add_row(self, *row: str) -> None:
                self.rows.append(row)

        class FakePanel:
            def __init__(self) -> None:
                self.value: str | None = None

            def update(self, value: str) -> None:
                self.value = value

        table = FakeTable()
        panel = FakePanel()

        def fake_query_one(selector: str, _type: object = None) -> object:  # noqa: ANN401
            if selector == "#module-table":
                return table
            if selector == "#detail-panel":
                return panel
            raise AssertionError(f"Unexpected selector: {selector}")

        monkeypatch.setattr(app, "query_one", fake_query_one)

        app.on_mount()
        assert table.columns
        assert table.rows

        event = type("Evt", (), {"cursor_row": 0})()
        app.on_data_table_row_selected(event)
        assert panel.value is not None
        assert "src" in panel.value
        assert "app" in panel.value

        app.action_deselect()
        assert panel.value is not None
        assert "Select a module" in panel.value

    def test_selection_out_of_bounds_is_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Out-of-range selection should return early without touching the panel."""
        import datetime

        from drift.models import ModuleScore, RepoAnalysis
        from drift.output.tui_renderer import DriftVisualizeApp

        module = ModuleScore(path=Path("src/app"), drift_score=0.2)
        analysis = RepoAnalysis(
            repo_path=Path("."),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.2,
            module_scores=[module],
            findings=[],
            total_files=1,
        )
        app = DriftVisualizeApp(analysis)

        class FakePanel:
            def __init__(self) -> None:
                self.updated = False

            def update(self, _value: str) -> None:
                self.updated = True

        panel = FakePanel()

        monkeypatch.setattr(app, "query_one", lambda *_args, **_kwargs: panel)

        event = type("Evt", (), {"cursor_row": 99})()
        app.on_data_table_row_selected(event)
        assert panel.updated is False

    def test_build_detail_skips_zero_signal_scores_and_handles_no_findings(self) -> None:
        """Zero-valued signal entries should not render bars; no findings shows fallback text."""
        import datetime

        from drift.models import ModuleScore, RepoAnalysis
        from drift.output.tui_renderer import DriftVisualizeApp

        module = ModuleScore(
            path=Path("src/zero"),
            drift_score=0.1,
            signal_scores={"pattern_fragmentation": 0.0},
            findings=[],
            file_count=1,
            function_count=1,
            ai_ratio=0.0,
        )
        analysis = RepoAnalysis(
            repo_path=Path("."),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.1,
            module_scores=[module],
            findings=[],
            total_files=1,
        )

        app = DriftVisualizeApp(analysis)
        detail = app._build_detail(module)

        assert "Signal Scores" in detail
        assert "No findings in this module" in detail
        # score=0 entry should not create a rendered score line for the signal name
        assert "0.000  pattern_fragmentation" not in detail
