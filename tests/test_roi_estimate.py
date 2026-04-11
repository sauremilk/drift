"""Tests for ``drift roi-estimate`` command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from drift.cli import main
from drift.commands.roi_estimate import _build_estimate, _estimate_hours

# ---------------------------------------------------------------------------
# Unit tests for estimation helpers
# ---------------------------------------------------------------------------


class TestEstimateHours:
    def test_known_signal_returns_configured_hours(self) -> None:
        assert _estimate_hours("pattern_fragmentation") == 2.0
        assert _estimate_hours("naming_contract_violation") == 0.3
        assert _estimate_hours("architecture_violation") == 3.0

    def test_unknown_signal_returns_default(self) -> None:
        assert _estimate_hours("totally_unknown_signal") == 1.0


class TestBuildEstimate:
    def test_empty_findings(self) -> None:
        assert _build_estimate([]) == []

    def test_groups_by_signal_type(self) -> None:
        class FakeFinding:
            def __init__(self, signal_type: str, location: str | None = None):
                self.signal_type = signal_type
                self.location = location

        findings = [
            FakeFinding("pattern_fragmentation", "src/a.py"),
            FakeFinding("pattern_fragmentation", "src/b.py"),
            FakeFinding("mutant_duplicate", "src/c.py"),
        ]
        rows = _build_estimate(findings)
        assert len(rows) == 2

        pfs_row = next(r for r in rows if r["signal_type"] == "pattern_fragmentation")
        assert pfs_row["findings"] == 2
        assert pfs_row["files_affected"] == 2
        assert pfs_row["estimated_hours"] == 4.0  # 2 x 2.0h

        mds_row = next(r for r in rows if r["signal_type"] == "mutant_duplicate")
        assert mds_row["findings"] == 1
        assert mds_row["estimated_hours"] == 1.5

    def test_finding_without_location(self) -> None:
        class FakeFinding:
            def __init__(self, signal_type: str):
                self.signal_type = signal_type
                self.location = None

        rows = _build_estimate([FakeFinding("explainability_deficit")])
        assert rows[0]["files_affected"] == 0
        assert rows[0]["estimated_hours"] == 0.5


# ---------------------------------------------------------------------------
# CLI integration tests (mocked analysis)
# ---------------------------------------------------------------------------


def _make_fake_analysis(findings=None):
    """Return a minimal mock RepoAnalysis."""

    class FakeAnalysis:
        drift_score = 0.42

    analysis = FakeAnalysis()
    analysis.findings = findings or []
    return analysis


class _FakeDriftConfig:
    @classmethod
    def load(cls, *args, **kwargs):
        return cls()


class TestRoiEstimateCLI:
    def test_json_output_empty_findings(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with (
            patch("drift.analyzer.analyze_repo", return_value=_make_fake_analysis()),
            patch("drift.config.DriftConfig", _FakeDriftConfig),
        ):
            result = runner.invoke(
                main, ["roi-estimate", "--format", "json", "--repo", str(tmp_path)]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_findings"] == 0
        assert data["total_estimated_hours"] == 0
        assert data["drift_score"] == 0.42
        assert data["signals"] == []

    def test_json_output_with_findings(self, tmp_path: Path) -> None:
        class FakeFinding:
            def __init__(self, signal_type: str, location: str | None = None):
                self.signal_type = signal_type
                self.location = location

        findings = [
            FakeFinding("pattern_fragmentation", "src/a.py"),
            FakeFinding("pattern_fragmentation", "src/b.py"),
            FakeFinding("cohesion_deficit", "src/c.py"),
        ]
        runner = CliRunner()
        with (
            patch("drift.analyzer.analyze_repo", return_value=_make_fake_analysis(findings)),
            patch("drift.config.DriftConfig", _FakeDriftConfig),
        ):
            result = runner.invoke(
                main, ["roi-estimate", "--format", "json", "--repo", str(tmp_path)]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_findings"] == 3
        assert data["total_estimated_hours"] == 6.5  # 2x2.0 + 1x2.5

    def test_rich_output_no_findings(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with (
            patch("drift.analyzer.analyze_repo", return_value=_make_fake_analysis()),
            patch("drift.config.DriftConfig", _FakeDriftConfig),
        ):
            result = runner.invoke(main, ["roi-estimate", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "No findings" in result.output

    def test_rich_output_with_findings(self, tmp_path: Path) -> None:
        class FakeFinding:
            def __init__(self, signal_type: str, location: str | None = None):
                self.signal_type = signal_type
                self.location = location

        findings = [
            FakeFinding("pattern_fragmentation", "src/a.py"),
            FakeFinding("mutant_duplicate", "src/b.py"),
        ]
        runner = CliRunner()
        with (
            patch("drift.analyzer.analyze_repo", return_value=_make_fake_analysis(findings)),
            patch("drift.config.DriftConfig", _FakeDriftConfig),
        ):
            result = runner.invoke(main, ["roi-estimate", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "ROI Estimate" in result.output
        assert "pattern_fragmentation" in result.output

    def test_help_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["roi-estimate", "--help"])
        assert result.exit_code == 0
        assert "Estimate refactoring hours" in result.output
