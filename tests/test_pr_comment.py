"""Unit tests for PR-comment output format (ADR-052)."""

from __future__ import annotations

import datetime
from pathlib import Path
from types import SimpleNamespace

from drift.models import Finding, RepoAnalysis, Severity, SignalType
from drift.output.pr_comment import analysis_to_pr_comment


def _make_finding(
    **kwargs: object,
) -> Finding:
    defaults: dict[str, object] = {
        "signal_type": SignalType.PATTERN_FRAGMENTATION,
        "severity": Severity.HIGH,
        "score": 0.8,
        "title": "Error handling fragmented",
        "description": "Multiple divergent patterns detected.",
        "file_path": Path("src/api/routes.py"),
        "start_line": 42,
        "impact": 0.75,
    }
    defaults.update(kwargs)
    return Finding(**defaults)  # type: ignore[arg-type]


def _sample_analysis(**overrides: object) -> RepoAnalysis:
    findings = overrides.pop(
        "findings",
        [
            _make_finding(severity=Severity.HIGH),
            _make_finding(
                signal_type=SignalType.SYSTEM_MISALIGNMENT,
                severity=Severity.MEDIUM,
                score=0.6,
                title="Config drift",
                description="Different env handling.",
                file_path=Path("src/config.py"),
                start_line=10,
                impact=0.4,
            ),
        ],
    )
    base = RepoAnalysis(
        repo_path=Path("my-repo"),
        analyzed_at=datetime.datetime(2026, 4, 11, 12, 0, tzinfo=datetime.UTC),
        drift_score=28.5,
        findings=findings,
        total_files=50,
        total_functions=200,
        ai_attributed_ratio=0.1,
        analysis_duration_seconds=1.5,
    )
    for k, v in overrides.items():
        object.__setattr__(base, k, v)
    return base


# --- structural tests ---


def test_pr_comment_contains_header() -> None:
    result = analysis_to_pr_comment(_sample_analysis())
    assert "## 🔍 Drift Analysis" in result
    assert "`my-repo`" in result
    assert "2026-04-11" in result


def test_pr_comment_summary_table() -> None:
    result = analysis_to_pr_comment(_sample_analysis())
    assert "| Score | Severity | Trend | Findings |" in result
    assert "28.5" in result
    assert "🟠" in result or "🟡" in result  # high or medium severity emoji


def test_pr_comment_top_findings_heading() -> None:
    result = analysis_to_pr_comment(_sample_analysis())
    assert "### Top Findings" in result
    assert "| # | Severity | Signal | Location | Action |" in result


def test_pr_comment_findings_rows() -> None:
    result = analysis_to_pr_comment(_sample_analysis())
    # Location with line number
    assert "src/api/routes.py:42" in result
    # Signal long name (falls back gracefully if registry not available)
    assert "Pattern" in result or "PFS" in result


def test_pr_comment_max_findings_limit() -> None:
    many = [_make_finding(title=f"Finding {i}", impact=float(i)) for i in range(10)]
    result = analysis_to_pr_comment(_sample_analysis(findings=many), max_findings=3)
    # Footer should say "3 of 10"
    assert "3 of 10" in result


def test_pr_comment_no_trend_shown_as_na() -> None:
    analysis = _sample_analysis()
    # Ensure no trend attribute
    if hasattr(analysis, "trend"):
        object.__setattr__(analysis, "trend", None)
    result = analysis_to_pr_comment(analysis)
    assert "n/a" in result


def test_pr_comment_trend_worsening_arrow() -> None:
    trend = SimpleNamespace(direction="worsening", delta=5.2, previous_score=20.0)
    analysis = _sample_analysis()
    object.__setattr__(analysis, "trend", trend)
    result = analysis_to_pr_comment(analysis)
    assert "↑" in result
    assert "+5.2" in result


def test_pr_comment_trend_improving_arrow() -> None:
    trend = SimpleNamespace(direction="improving", delta=-3.1, previous_score=30.0)
    analysis = _sample_analysis()
    object.__setattr__(analysis, "trend", trend)
    result = analysis_to_pr_comment(analysis)
    assert "↓" in result
    assert "-3.1" in result


def test_pr_comment_empty_findings() -> None:
    result = analysis_to_pr_comment(_sample_analysis(findings=[]))
    # No findings table when there are no findings
    assert "### Top Findings" not in result
    # But header and summary still present
    assert "## 🔍 Drift Analysis" in result
    assert "0 total" in result


def test_pr_comment_no_location_for_file_less_finding() -> None:
    finding = _make_finding(file_path=None, start_line=None)
    result = analysis_to_pr_comment(_sample_analysis(findings=[finding]))
    # Empty location cell — no crash
    assert "### Top Findings" in result
    assert "` |" in result  # the backtick pair around empty string
