"""Fuzz tests for the drift scoring engine.

Invariants verified:
- composite_score always returns a value in [0.0, 1.0].
- compute_signal_scores never raises on arbitrary Finding lists.
- Per-signal scores are all in [0.0, 1.0].
- assign_impact_scores never raises and modifies findings in-place.
- score_to_grade always returns a non-empty (grade, label) tuple.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from drift.config._schema import SignalWeights
from drift.models import Severity
from drift.models._enums import SignalType
from drift.models._findings import Finding
from drift.scoring.engine import (
    assign_impact_scores,
    composite_score,
    compute_signal_scores,
    score_to_grade,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_all_signal_type_strs = [str(s) for s in SignalType]

_signal_score_strategy = st.dictionaries(
    keys=st.one_of(
        st.sampled_from(_all_signal_type_strs),
        st.text(min_size=1, max_size=30).filter(str.isidentifier),
    ),
    values=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    max_size=30,
)


@st.composite
def finding_strategy(draw: st.DrawFn) -> Finding:
    sig = draw(
        st.one_of(
            st.sampled_from(_all_signal_type_strs),
            st.text(min_size=1, max_size=20).filter(str.isidentifier),
        )
    )
    score = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    severity = draw(st.sampled_from(list(Severity)))
    return Finding(
        signal_type=sig,
        severity=severity,
        score=score,
        title="fuzz",
        description="fuzz",
        file_path=Path("fuzz.py"),
    )


_findings_strategy = st.lists(finding_strategy(), min_size=0, max_size=50)

_default_weights = SignalWeights()


# ---------------------------------------------------------------------------
# composite_score
# ---------------------------------------------------------------------------


@pytest.mark.fuzz
@given(signal_scores=_signal_score_strategy)
def test_fuzz_composite_score_range(signal_scores: dict[str, float]) -> None:
    """composite_score must always return a float in [0.0, 1.0]."""
    result = composite_score(signal_scores, _default_weights)
    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0, f"composite_score out of range: {result}"


@pytest.mark.fuzz
@given(signal_scores=_signal_score_strategy)
def test_fuzz_composite_score_empty_is_zero(signal_scores: dict[str, float]) -> None:
    """An empty signal_scores dict must always return 0.0."""
    result = composite_score({}, _default_weights)
    assert result == 0.0


# ---------------------------------------------------------------------------
# compute_signal_scores
# ---------------------------------------------------------------------------


@pytest.mark.fuzz
@given(findings=_findings_strategy)
def test_fuzz_compute_signal_scores_range(findings: list[Finding]) -> None:
    """All per-signal scores returned by compute_signal_scores must be in [0.0, 1.0]."""
    scores = compute_signal_scores(findings)
    assert isinstance(scores, dict)
    for sig, score in scores.items():
        assert isinstance(sig, str)
        assert 0.0 <= score <= 1.0, f"signal score out of range for {sig}: {score}"


@pytest.mark.fuzz
@given(findings=_findings_strategy)
def test_fuzz_compute_signal_scores_no_crash(findings: list[Finding]) -> None:
    """compute_signal_scores must not raise on any list of Findings."""
    compute_signal_scores(findings)


# ---------------------------------------------------------------------------
# assign_impact_scores
# ---------------------------------------------------------------------------


@pytest.mark.fuzz
@given(findings=_findings_strategy)
def test_fuzz_assign_impact_scores_no_crash(findings: list[Finding]) -> None:
    """assign_impact_scores must not raise and must modify findings in-place."""
    # Make a shallow copy to avoid mutation of hypothesis-owned objects
    findings_copy = list(findings)
    assign_impact_scores(findings_copy, _default_weights)
    for f in findings_copy:
        assert isinstance(f.impact, float)


# ---------------------------------------------------------------------------
# score_to_grade
# ---------------------------------------------------------------------------


@pytest.mark.fuzz
@given(score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
def test_fuzz_score_to_grade_always_returns(score: float) -> None:
    """score_to_grade must always return a non-empty (grade, label) tuple."""
    grade, label = score_to_grade(score)
    assert isinstance(grade, str) and len(grade) > 0
    assert isinstance(label, str) and len(label) > 0
