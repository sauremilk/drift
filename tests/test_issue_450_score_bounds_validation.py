"""Regression tests for issue #450: enforce [0, 1] score bounds at model construction."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from drift.models import Finding, ModuleScore, RepoAnalysis, Severity


def test_finding_rejects_score_above_one() -> None:
    with pytest.raises(ValueError, match="Finding.score"):
        Finding(
            signal_type="pattern_fragmentation",
            severity=Severity.HIGH,
            score=1.1,
            title="t",
            description="d",
        )


def test_finding_rejects_impact_below_zero() -> None:
    with pytest.raises(ValueError, match="Finding.impact"):
        Finding(
            signal_type="pattern_fragmentation",
            severity=Severity.HIGH,
            score=0.5,
            impact=-0.1,
            title="t",
            description="d",
        )


def test_module_score_rejects_out_of_range_drift_score() -> None:
    with pytest.raises(ValueError, match="ModuleScore.drift_score"):
        ModuleScore(path=Path("src"), drift_score=1.2)


def test_repo_analysis_rejects_out_of_range_drift_score() -> None:
    with pytest.raises(ValueError, match="RepoAnalysis.drift_score"):
        RepoAnalysis(
            repo_path=Path("."),
            analyzed_at=datetime.datetime.now(datetime.UTC),
            drift_score=-0.01,
        )


def test_bounds_accept_zero_and_one() -> None:
    finding = Finding(
        signal_type="pattern_fragmentation",
        severity=Severity.HIGH,
        score=1.0,
        impact=0.0,
        title="t",
        description="d",
    )
    module_score = ModuleScore(path=Path("src"), drift_score=0.0)
    repo_analysis = RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(datetime.UTC),
        drift_score=1.0,
    )

    assert finding.score == 1.0
    assert finding.impact == 0.0
    assert module_score.drift_score == 0.0
    assert repo_analysis.drift_score == 1.0