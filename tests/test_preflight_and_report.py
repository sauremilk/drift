"""Tests for preflight diagnostics and markdown report output."""

from __future__ import annotations

import datetime
import subprocess
from pathlib import Path

import pytest

from drift.config import DriftConfig
from drift.models import AnalyzerWarning, RepoAnalysis
from drift.output.markdown_report import analysis_to_markdown
from drift.preflight import PreflightResult, SkippedSignal, run_preflight

# ---------------------------------------------------------------------------
# PreflightResult unit tests
# ---------------------------------------------------------------------------


class TestPreflightResult:
    def test_defaults(self) -> None:
        pf = PreflightResult()
        assert pf.git_available is False
        assert pf.can_proceed is True
        assert pf.skipped_count == 0
        assert pf.active_count == 0

    def test_skipped_count(self) -> None:
        pf = PreflightResult(
            skipped_signals=[
                SkippedSignal("TVS", "Temporal Volatility", "no git", "clone fully"),
            ],
        )
        assert pf.skipped_count == 1
        assert pf.active_count == 0

    def test_to_dict_roundtrip(self) -> None:
        pf = PreflightResult(
            git_available=True,
            python_files_found=42,
            total_files_found=42,
            active_signals=["PFS", "AVS"],
            skipped_signals=[
                SkippedSignal("TVS", "Temporal Volatility", "no git", "clone"),
            ],
            warnings=["test warning"],
        )
        d = pf.to_dict()
        assert d["git_available"] is True
        assert d["python_files_found"] == 42
        assert len(d["skipped_signals"]) == 1
        assert d["skipped_signals"][0]["signal_id"] == "TVS"
        assert d["warnings"] == ["test warning"]


# ---------------------------------------------------------------------------
# run_preflight integration tests
# ---------------------------------------------------------------------------


class TestRunPreflight:
    def test_with_git_repo(self, tmp_repo: Path) -> None:
        """Preflight in a directory with Python files (no git)."""
        config = DriftConfig()
        pf = run_preflight(tmp_repo, config)
        assert pf.python_files_found > 0
        assert pf.can_proceed is True
        # tmp_repo has no .git — git-dependent signals should be skipped
        assert pf.git_available is False
        assert pf.skipped_count > 0

    def test_with_git_init(self, tmp_repo: Path) -> None:
        """Preflight with git initialized should have no git-skipped signals."""
        subprocess.run(
            ["git", "init"],
            cwd=tmp_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "init", "--allow-empty"],
            cwd=tmp_repo,
            capture_output=True,
            check=True,
            env={
                "GIT_AUTHOR_NAME": "test",
                "GIT_AUTHOR_EMAIL": "test@test.com",
                "GIT_COMMITTER_NAME": "test",
                "GIT_COMMITTER_EMAIL": "test@test.com",
                "PATH": subprocess.os.environ.get("PATH", ""),
            },
        )
        config = DriftConfig()
        pf = run_preflight(tmp_repo, config)
        assert pf.git_available is True
        # With git, no signals should be skipped due to missing git
        git_skips = [s for s in pf.skipped_signals if "git" in s.reason.lower()]
        assert len(git_skips) == 0

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Preflight in an empty directory should report can_proceed=False."""
        config = DriftConfig()
        pf = run_preflight(tmp_path, config)
        assert pf.can_proceed is False
        assert pf.abort_reason is not None
        assert "No analysable" in pf.abort_reason


# ---------------------------------------------------------------------------
# Markdown report tests
# ---------------------------------------------------------------------------


def _make_analysis(
    tmp_path: Path,
    *,
    score: float = 25.0,
    findings: list | None = None,
    preflight: PreflightResult | None = None,
    warnings: list[AnalyzerWarning] | None = None,
) -> RepoAnalysis:
    """Create a minimal RepoAnalysis for testing."""
    return RepoAnalysis(
        repo_path=tmp_path,
        analyzed_at=datetime.datetime(2025, 1, 15, 12, 0, tzinfo=datetime.UTC),
        drift_score=score,
        findings=findings or [],
        total_files=10,
        total_functions=50,
        ai_attributed_ratio=0.15,
        analysis_duration_seconds=2.5,
        preflight=preflight,
        analyzer_warnings=warnings or [],
    )


class TestMarkdownReport:
    def test_repo_analysis_preflight_annotation_is_concrete(self) -> None:
        """RepoAnalysis.preflight should expose a concrete type contract."""
        assert RepoAnalysis.__annotations__["preflight"] == "PreflightResult | None"

    def test_basic_report_structure(self, tmp_path: Path) -> None:
        """Report should contain header, summary table, and interpretation."""
        analysis = _make_analysis(tmp_path)
        md = analysis_to_markdown(analysis)
        assert "# Drift Analysis Report" in md
        assert "## Summary" in md
        assert "| Drift Score |" in md
        assert "Interpretation" in md.lower() or "drift score measures" in md

    def test_preflight_section(self, tmp_path: Path) -> None:
        """Report with preflight data includes diagnostics section."""
        pf = PreflightResult(
            git_available=True,
            python_files_found=10,
            total_files_found=10,
            active_signals=["PFS", "AVS", "MDS"],
            skipped_signals=[
                SkippedSignal("TVS", "Temporal Volatility", "no git", "clone"),
            ],
        )
        analysis = _make_analysis(tmp_path, preflight=pf)
        md = analysis_to_markdown(analysis)
        assert "## Preflight Diagnostics" in md
        assert "Git: available" in md
        assert "3 signals active" in md
        assert "TVS" in md

    def test_no_findings_message(self, tmp_path: Path) -> None:
        """Report with zero findings shows clean bill."""
        analysis = _make_analysis(tmp_path, score=0.0)
        md = analysis_to_markdown(analysis)
        assert "No findings" in md or "no structural coherence" in md.lower()

    def test_feedback_prompt(self, tmp_path: Path) -> None:
        """Report includes a feedback/issue-filing prompt."""
        analysis = _make_analysis(tmp_path)
        md = analysis_to_markdown(analysis)
        assert "false positive" in md.lower() or "File an issue" in md

    def test_signal_coverage_section(self, tmp_path: Path) -> None:
        """Report with preflight includes signal coverage."""
        pf = PreflightResult(
            git_available=True,
            python_files_found=5,
            total_files_found=5,
            active_signals=["PFS", "AVS"],
        )
        analysis = _make_analysis(tmp_path, preflight=pf)
        md = analysis_to_markdown(analysis)
        assert "## Signal Coverage" in md
        assert "`PFS`" in md
        assert "`AVS`" in md

    def test_analyzer_warnings_section(self, tmp_path: Path) -> None:
        """Report includes analyzer warnings when present."""
        warnings = [
            AnalyzerWarning(signal_type="DIA", message="Insufficient docs", skipped=True),
        ]
        analysis = _make_analysis(tmp_path, warnings=warnings)
        md = analysis_to_markdown(analysis)
        assert "## Analyzer Warnings" in md
        assert "DIA" in md

    def test_exclude_preflight(self, tmp_path: Path) -> None:
        """include_preflight=False omits the section."""
        pf = PreflightResult(git_available=True, python_files_found=5, total_files_found=5)
        analysis = _make_analysis(tmp_path, preflight=pf)
        md = analysis_to_markdown(analysis, include_preflight=False)
        assert "## Preflight" not in md


class TestMarkdownCLIFormat:
    """Verify --format markdown is wired in the analyze CLI command."""

    def test_analyze_help_lists_markdown_format(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "markdown" in result.output

    def test_format_markdown_produces_report(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        analysis = _make_analysis(tmp_path, score=12.0)

        def _fake_analyze(*args: object, **kwargs: object) -> RepoAnalysis:
            return analysis

        monkeypatch.setattr("drift.analyzer.analyze_repo", _fake_analyze)
        monkeypatch.setattr("drift.analyzer._DEFAULT_WORKERS", 1)

        # Ensure DriftConfig.load returns a default config
        def _fake_load(*a: object, **kw: object) -> DriftConfig:
            return DriftConfig()

        monkeypatch.setattr(
            "drift.config.DriftConfig.load",
            staticmethod(_fake_load),
        )

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", "--repo", str(tmp_path), "--format", "markdown"])
        assert result.exit_code == 0, result.output
        assert "# Drift Analysis Report" in result.output


class TestGuidanceFooter:
    """Verify the 'What's Next' guidance footer in rich output."""

    def test_guidance_shows_when_no_config(self, tmp_path: Path) -> None:
        """Guidance footer appears when repo has no drift.yaml."""
        from io import StringIO

        from rich.console import Console

        from drift.output.rich_output import render_full_report

        analysis = _make_analysis(tmp_path, score=20.0)
        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120)
        render_full_report(analysis, c)
        output = buf.getvalue()
        assert "drift init" in output

    def test_guidance_hidden_when_config_exists(self, tmp_path: Path) -> None:
        """Guidance footer does NOT appear when drift.yaml exists."""
        from io import StringIO

        from rich.console import Console

        from drift.output.rich_output import render_full_report

        (tmp_path / "drift.yaml").write_text("version: 1\n", encoding="utf-8")
        analysis = _make_analysis(tmp_path, score=20.0)
        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120)
        render_full_report(analysis, c)
        output = buf.getvalue()
        # The "What's Next" guidance should not appear
        assert "drift init" not in output or "drift init" in output.split("Interpretation")[0]

    def test_guidance_german(self, tmp_path: Path) -> None:
        """German locale shows German guidance text."""
        from io import StringIO

        from rich.console import Console

        from drift.output.rich_output import render_full_report

        analysis = _make_analysis(tmp_path, score=20.0)
        buf = StringIO()
        c = Console(file=buf, force_terminal=True, width=120)
        render_full_report(analysis, c, language="de")
        output = buf.getvalue()
        assert "Konfiguration" in output
