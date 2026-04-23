"""Coverage-Boost: commands/analyze.py — output format branches, signal filtering, baseline."""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from drift.cli import main
from drift.models import Finding, RepoAnalysis, Severity, SignalType


def _make_finding(
    signal: SignalType = SignalType.PATTERN_FRAGMENTATION,
    severity: Severity = Severity.MEDIUM,
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=severity,
        score=0.5,
        title="Test finding",
        description="desc",
        file_path=Path("src/foo.py"),
        start_line=10,
        end_line=15,
        fix="Do something",
    )


def _make_analysis(
    findings: list[Finding] | None = None,
    repo_path: Path = Path("."),
) -> RepoAnalysis:
    return RepoAnalysis(
        repo_path=repo_path,
        analyzed_at=datetime.datetime.now(datetime.UTC),
        drift_score=0.35,
        findings=findings or [],
    )


def _fake_analyze_repo(repo_path: Path) -> RepoAnalysis:
    return _make_analysis(repo_path=repo_path)


# ---------------------------------------------------------------------------
# sarif output
# ---------------------------------------------------------------------------

def test_analyze_format_sarif(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path
    monkeypatch.setattr(
        "drift.analyzer.analyze_repo",
        lambda *a, **kw: _make_analysis(repo_path=repo),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", "--repo", str(repo), "--format", "sarif", "--exit-zero"],
    )

    assert result.exit_code == 0
    output = result.output
    # SARIF output contains $schema or runs
    assert "$schema" in output or "runs" in output or "version" in output


# ---------------------------------------------------------------------------
# csv output
# ---------------------------------------------------------------------------

def test_analyze_format_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path
    finding = _make_finding()
    monkeypatch.setattr(
        "drift.analyzer.analyze_repo",
        lambda *a, **kw: _make_analysis(findings=[finding], repo_path=repo),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", "--repo", str(repo), "--format", "csv", "--exit-zero"],
    )

    assert result.exit_code == 0
    assert "signal_type" in result.output or "severity" in result.output


# ---------------------------------------------------------------------------
# agent-tasks output
# ---------------------------------------------------------------------------

def test_analyze_format_agent_tasks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path
    monkeypatch.setattr(
        "drift.analyzer.analyze_repo",
        lambda *a, **kw: _make_analysis(repo_path=repo),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", "--repo", str(repo), "--format", "agent-tasks", "--exit-zero"],
    )

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# github output
# ---------------------------------------------------------------------------

def test_analyze_format_github(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path
    finding = _make_finding()
    monkeypatch.setattr(
        "drift.analyzer.analyze_repo",
        lambda *a, **kw: _make_analysis(findings=[finding], repo_path=repo),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", "--repo", str(repo), "--format", "github", "--exit-zero"],
    )

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# markdown output
# ---------------------------------------------------------------------------

def test_analyze_format_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path
    monkeypatch.setattr(
        "drift.analyzer.analyze_repo",
        lambda *a, **kw: _make_analysis(repo_path=repo),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", "--repo", str(repo), "--format", "markdown", "--exit-zero"],
    )

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# --select    (signal filtering branch)
# ---------------------------------------------------------------------------

def test_analyze_with_select_signals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path
    monkeypatch.setattr(
        "drift.analyzer.analyze_repo",
        lambda *a, **kw: _make_analysis(repo_path=repo),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", "--repo", str(repo), "--select", "PFS", "--exit-zero", "--format", "json"],
    )

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# --ignore  (signal filtering branch)
# ---------------------------------------------------------------------------

def test_analyze_with_ignore_signals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path
    monkeypatch.setattr(
        "drift.analyzer.analyze_repo",
        lambda *a, **kw: _make_analysis(repo_path=repo),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", "--repo", str(repo), "--ignore", "TVS", "--exit-zero", "--format", "json"],
    )

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# --progress json  (JSON progress branch)
# ---------------------------------------------------------------------------

def test_analyze_progress_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path
    monkeypatch.setattr(
        "drift.analyzer.analyze_repo",
        lambda *a, **kw: _make_analysis(repo_path=repo),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", "--repo", str(repo), "--progress", "json", "--exit-zero", "--format", "json"],
    )

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# --progress none   (no progress)
# ---------------------------------------------------------------------------

def test_analyze_progress_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path
    monkeypatch.setattr(
        "drift.analyzer.analyze_repo",
        lambda *a, **kw: _make_analysis(repo_path=repo),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", "--repo", str(repo), "--progress", "none", "--exit-zero", "--format", "json"],
    )

    assert result.exit_code == 0
