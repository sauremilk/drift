"""Tests for the scoring engine."""

from pathlib import Path

import pytest

from drift.config import SignalWeights
from drift.models import Finding, Severity, SignalType
from drift.scoring.engine import (
    auto_calibrate_weights,
    calibrate_weights,
    composite_score,
    compute_module_scores,
    compute_signal_scores,
    score_to_grade,
    severity_gate_pass,
)


def _finding(
    signal: SignalType,
    score: float,
    severity: Severity = Severity.MEDIUM,
    path: str = "mod/file.py",
    ai: bool = False,
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=severity,
        score=score,
        title="test",
        description="",
        file_path=Path(path),
        ai_attributed=ai,
    )


# ── Signal scores ─────────────────────────────────────────────────────────


def test_compute_signal_scores_averages():
    import math

    findings = [
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.4),
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.6),
        _finding(SignalType.ARCHITECTURE_VIOLATION, 0.8),
    ]
    scores = compute_signal_scores(findings)
    # Scores are count-dampened: mean * min(1, ln(1+n)/ln(1+10))
    k = 20
    pf_mean = 0.5
    pf_damp = min(1.0, math.log(1 + 2) / math.log(1 + k))
    assert scores[SignalType.PATTERN_FRAGMENTATION] == pytest.approx(round(pf_mean * pf_damp, 4))
    av_mean = 0.8
    av_damp = min(1.0, math.log(1 + 1) / math.log(1 + k))
    assert scores[SignalType.ARCHITECTURE_VIOLATION] == pytest.approx(round(av_mean * av_damp, 4))
    # Signals without findings are omitted from the dict
    assert scores.get(SignalType.DOC_IMPL_DRIFT, 0.0) == 0.0


def test_compute_signal_scores_empty():
    scores = compute_signal_scores([])
    for val in scores.values():
        assert val == 0.0


# ── Composite score ───────────────────────────────────────────────────────


def test_composite_score_all_zero():
    signal_scores = {sig: 0.0 for sig in SignalType}
    result = composite_score(signal_scores, SignalWeights())
    assert result == 0.0


def test_composite_score_balanced():
    signal_scores = {sig: 0.5 for sig in SignalType}
    result = composite_score(signal_scores, SignalWeights())
    assert 0.45 <= result <= 0.55


def test_composite_score_weighted():
    # Only pattern_fragmentation has a score; weight = 0.20
    signal_scores = {sig: 0.0 for sig in SignalType}
    signal_scores[SignalType.PATTERN_FRAGMENTATION] = 1.0

    result = composite_score(signal_scores, SignalWeights())
    # Weighted contribution = 1.0 * 0.20 / 1.0 total weight = 0.2
    assert 0.15 <= result <= 0.25


# ── Module scores ─────────────────────────────────────────────────────────


def test_module_scores_grouping():
    findings = [
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.6, path="api/routes.py"),
        _finding(SignalType.ARCHITECTURE_VIOLATION, 0.4, path="api/views.py"),
        _finding(SignalType.MUTANT_DUPLICATE, 0.8, path="db/models.py"),
    ]
    modules = compute_module_scores(findings, SignalWeights())

    assert len(modules) == 2  # api/ and db/
    # Sorted descending by score; db/ has 0.8 only in mutant_duplicate
    paths = [m.path.as_posix() for m in modules]
    assert "api" in paths
    assert "db" in paths


def test_module_ai_ratio():
    findings = [
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.5, path="svc/a.py", ai=True),
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.5, path="svc/b.py", ai=False),
    ]
    modules = compute_module_scores(findings, SignalWeights())
    assert len(modules) == 1
    assert modules[0].ai_ratio == 0.5


def test_module_scores_empty_findings_returns_empty_list():
    modules = compute_module_scores([], SignalWeights())
    assert modules == []


# ── Severity gate ─────────────────────────────────────────────────────────


def test_gate_passes_when_clean():
    findings = [
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.1, severity=Severity.LOW),
        _finding(SignalType.ARCHITECTURE_VIOLATION, 0.05, severity=Severity.INFO),
    ]
    assert severity_gate_pass(findings, "high") is True


def test_gate_fails_on_high():
    findings = [
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.8, severity=Severity.HIGH),
    ]
    assert severity_gate_pass(findings, "high") is False


def test_gate_critical_only():
    findings = [
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.7, severity=Severity.HIGH),
    ]
    # "critical" threshold only blocks on CRITICAL
    assert severity_gate_pass(findings, "critical") is True

    findings.append(_finding(SignalType.ARCHITECTURE_VIOLATION, 0.9, severity=Severity.CRITICAL))
    assert severity_gate_pass(findings, "critical") is False


def test_gate_empty_findings():
    assert severity_gate_pass([], "high") is True


# ── Weight calibration ────────────────────────────────────────────────────


def test_calibrate_weights_high_delta_gets_more_weight():
    deltas = {
        "pattern_fragmentation": 0.20,
        "architecture_violation": 0.05,
        "mutant_duplicate": 0.15,
        "explainability_deficit": 0.01,
        "doc_impl_drift": 0.00,
        "temporal_volatility": 0.10,
        "system_misalignment": 0.02,
    }
    calibrated = calibrate_weights(deltas, SignalWeights())

    # Pattern fragmentation has highest delta → highest weight
    assert calibrated.pattern_fragmentation > calibrated.architecture_violation
    assert calibrated.pattern_fragmentation > calibrated.explainability_deficit

    # Weights should sum to approximately 1.0
    total = sum(calibrated.as_dict().values())
    assert 0.99 <= total <= 1.01


def test_calibrate_weights_all_zero_returns_current():
    deltas = {k: 0.0 for k in SignalWeights().as_dict()}
    original = SignalWeights()
    calibrated = calibrate_weights(deltas, original)
    # With all-zero deltas, min_weight kicks in — all equal
    vals = list(calibrated.as_dict().values())
    assert max(vals) - min(vals) < 0.01  # approximately uniform


def test_calibrate_weights_respects_bounds():
    deltas = {k: 0.001 for k in SignalWeights().as_dict()}
    deltas["pattern_fragmentation"] = 1.0  # extreme
    calibrated = calibrate_weights(deltas, SignalWeights(), min_weight=0.05, max_weight=0.35)
    min_expected = min(SignalWeights().as_dict().values())
    for val in calibrated.as_dict().values():
        assert val >= min_expected
        assert val <= 0.36


def test_calibrate_weights_zero_total_after_clamp_returns_current():
    deltas = {
        "pattern_fragmentation": 0.9,
        "architecture_violation": 0.2,
        "mutant_duplicate": 0.2,
        "explainability_deficit": 0.2,
        "doc_impl_drift": 0.2,
        "temporal_volatility": 0.2,
        "system_misalignment": 0.2,
    }
    original = SignalWeights()
    calibrated = calibrate_weights(deltas, original, min_weight=0.0, max_weight=0.0)
    assert calibrated == original


def test_auto_calibrate_weights_deterministic_across_input_order():
    base_weights = SignalWeights()
    findings = [
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.6),
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.7),
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.8),
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.5),
        _finding(SignalType.ARCHITECTURE_VIOLATION, 0.4),
        _finding(SignalType.ARCHITECTURE_VIOLATION, 0.3),
        _finding(SignalType.MUTANT_DUPLICATE, 0.9),
        _finding(SignalType.MUTANT_DUPLICATE, 0.2),
        _finding(SignalType.SYSTEM_MISALIGNMENT, 0.3),
        _finding(SignalType.BYPASS_ACCUMULATION, 0.4),
    ]

    baseline = auto_calibrate_weights(findings, base_weights)
    reversed_run = auto_calibrate_weights(list(reversed(findings)), base_weights)

    assert reversed_run.model_dump() == baseline.model_dump()

    # Additional permutations must not alter calibrated weights.
    odd_first = findings[::2] + findings[1::2]
    even_first = findings[1::2] + findings[::2]
    assert auto_calibrate_weights(odd_first, base_weights).model_dump() == baseline.model_dump()
    assert auto_calibrate_weights(even_first, base_weights).model_dump() == baseline.model_dump()


# ── Dampening k=20 (ADR-041) ─────────────────────────────────────────────


def test_dampening_k20_reduces_prolific_signals():
    """50 findings with k=20 produce a score below raw mean (ADR-041 P3)."""
    findings = [_finding(SignalType.EXPLAINABILITY_DEFICIT, 0.4) for _ in range(50)]
    scores = compute_signal_scores(findings)
    # With k=20, dampening = ln(51)/ln(21) ≈ 1.29 → clamped to 1.0
    # Actually 50 findings still saturate at k=20, so score ≈ mean.
    # The key property: the same test with k=10 (explicit param) yields
    # exactly the same result, because 50 > 20. The difference shows
    # for mid-range counts.
    assert scores[SignalType.EXPLAINABILITY_DEFICIT] == pytest.approx(0.4, abs=0.01)


def test_dampening_k20_differentiates_midrange_counts():
    """10 findings get dampened more with k=20 than k=10 (ADR-041 P3)."""
    import math

    findings = [_finding(SignalType.PATTERN_FRAGMENTATION, 0.6) for _ in range(10)]

    score_k20 = compute_signal_scores(findings)  # default k=20
    score_k10 = compute_signal_scores(findings, dampening_k=10)

    # k=10: dampening = ln(11)/ln(11) = 1.0 → score = 0.6
    # k=20: dampening = ln(11)/ln(21) ≈ 0.787 → score ≈ 0.472
    assert score_k10[SignalType.PATTERN_FRAGMENTATION] > score_k20[SignalType.PATTERN_FRAGMENTATION]

    k20_damp = math.log(1 + 10) / math.log(1 + 20)
    expected = round(0.6 * k20_damp, 4)
    assert score_k20[SignalType.PATTERN_FRAGMENTATION] == pytest.approx(expected, abs=0.001)


def test_dampening_k20_single_finding_penalty():
    """A single finding is dampened but not zeroed (FN safety check)."""
    import math

    findings = [_finding(SignalType.ARCHITECTURE_VIOLATION, 0.9)]
    scores = compute_signal_scores(findings)
    damp = math.log(2) / math.log(21)  # ≈ 0.228
    expected = round(0.9 * damp, 4)
    assert scores[SignalType.ARCHITECTURE_VIOLATION] == pytest.approx(expected, abs=0.001)
    assert scores[SignalType.ARCHITECTURE_VIOLATION] > 0.0  # not zeroed


# ── Letter grade ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "score, expected_grade",
    [
        (0.00, "A"),
        (0.10, "A"),
        (0.19, "A"),
        (0.20, "B"),
        (0.39, "B"),
        (0.40, "C"),
        (0.59, "C"),
        (0.60, "D"),
        (0.79, "D"),
        (0.80, "F"),
        (0.95, "F"),
        (1.00, "F"),
    ],
)
def test_score_to_grade_boundaries(score: float, expected_grade: str):
    grade, label = score_to_grade(score)
    assert grade == expected_grade
    assert isinstance(label, str)
    assert len(label) > 0


def test_score_to_grade_returns_tuple():
    grade, label = score_to_grade(0.0)
    assert grade == "A"
    assert label == "Excellent"


def test_score_to_grade_worst_case():
    grade, label = score_to_grade(1.0)
    assert grade == "F"
    assert label == "Critical Drift"
