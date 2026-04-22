"""Tests for the ``drift baseline status`` read-only summary command."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from drift.baseline import save_baseline
from drift.cli import main
from drift.models import Finding, RepoAnalysis, Severity, SignalType


def _mk_finding(path: str = "src/foo.py", line: int = 10, title: str = "T") -> Finding:
    return Finding(
        signal_type=SignalType.PATTERN_FRAGMENTATION,
        severity=Severity.MEDIUM,
        score=0.5,
        title=title,
        description="D",
        file_path=Path(path),
        start_line=line,
        end_line=line + 1,
        fix="fix it",
    )


def _mk_analysis(findings: list[Finding]) -> RepoAnalysis:
    return RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(datetime.UTC),
        drift_score=0.2,
        findings=findings,
    )


class TestBaselineStatusCommand:
    """Command contract: ``baseline status`` is read-only and never exits non-zero."""

    def _install_fake_analyzer(
        self,
        monkeypatch: pytest.MonkeyPatch,
        findings: list[Finding],
    ) -> None:
        monkeypatch.setattr(
            "drift.analyzer.analyze_repo",
            lambda *_a, **_kw: _mk_analysis(findings),
        )

    def test_missing_baseline_exits_zero_with_hint(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._install_fake_analyzer(monkeypatch, [_mk_finding()])
        repo = tmp_path / "repo"
        repo.mkdir()
        result = CliRunner().invoke(
            main,
            [
                "baseline",
                "status",
                "--repo",
                str(repo),
                "--baseline-file",
                str(tmp_path / "nope.json"),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "No baseline" in result.output

    def test_clean_against_baseline(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        f = _mk_finding(title="stable")
        # Save a baseline that already contains the one finding, then re-run status.
        bl = tmp_path / "bl.json"
        save_baseline(_mk_analysis([f]), bl)

        self._install_fake_analyzer(monkeypatch, [f])
        repo = tmp_path / "repo"
        repo.mkdir()
        result = CliRunner().invoke(
            main,
            ["baseline", "status", "--repo", str(repo), "--baseline-file", str(bl)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "clean" in result.output

    def test_json_format_returns_structured_payload(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        baseline_finding = _mk_finding(title="stable")
        new_finding = _mk_finding(path="src/new.py", line=99, title="new")
        bl = tmp_path / "bl.json"
        save_baseline(_mk_analysis([baseline_finding]), bl)

        # Current analysis has the baseline finding plus one new finding.
        self._install_fake_analyzer(monkeypatch, [baseline_finding, new_finding])
        repo = tmp_path / "repo"
        repo.mkdir()
        result = CliRunner().invoke(
            main,
            [
                "baseline",
                "status",
                "--repo",
                str(repo),
                "--baseline-file",
                str(bl),
                "--format",
                "json",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["baseline_exists"] is True
        assert payload["total_findings"] == 2
        assert payload["new_findings"] >= 1
        assert payload["known_findings"] >= 1
        assert set(payload) >= {
            "baseline_exists",
            "baseline_path",
            "baseline_findings",
            "total_findings",
            "known_findings",
            "new_findings",
            "drift_score",
        }

    def test_status_never_exits_nonzero_on_drift(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Even with hundreds of new findings ``status`` stays exit 0."""
        many = [_mk_finding(path=f"src/f{i}.py", line=i, title=f"t{i}") for i in range(50)]
        bl = tmp_path / "bl.json"
        save_baseline(_mk_analysis([]), bl)

        self._install_fake_analyzer(monkeypatch, many)
        repo = tmp_path / "repo"
        repo.mkdir()
        result = CliRunner().invoke(
            main,
            ["baseline", "status", "--repo", str(repo), "--baseline-file", str(bl)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
