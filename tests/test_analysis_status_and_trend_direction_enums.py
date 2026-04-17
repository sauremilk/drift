from __future__ import annotations

import datetime
from pathlib import Path

from drift.models import AnalysisStatus, RepoAnalysis, TrendContext, TrendDirection


def test_trend_context_uses_trend_direction_enum() -> None:
    trend = TrendContext(
        previous_score=0.5,
        delta=-0.1,
        direction=TrendDirection.IMPROVING,
        recent_scores=[0.6, 0.5],
        history_depth=2,
        transition_ratio=0.0,
    )

    assert trend.direction is TrendDirection.IMPROVING
    assert trend.direction == "improving"


def test_repo_analysis_uses_analysis_status_enum_by_default() -> None:
    analysis = RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=0.2,
    )

    assert analysis.analysis_status is AnalysisStatus.COMPLETE
    assert analysis.is_degraded is False

    analysis.analysis_status = AnalysisStatus.DEGRADED
    assert analysis.is_degraded is True
