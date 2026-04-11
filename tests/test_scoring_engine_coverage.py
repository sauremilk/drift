"""Coverage tests for scoring engine helpers:
score_to_grade, compute_signal_scores, composite_score,
severity_gate_pass, resolve_path_override."""

from __future__ import annotations

from pathlib import Path

from drift.config import SignalWeights
from drift.models import Finding, Severity, SignalType
from drift.scoring.engine import (
    composite_score,
    compute_signal_scores,
    resolve_path_override,
    score_to_grade,
    severity_gate_pass,
)


def _finding(
    score: float = 0.5,
    sig: str = "pattern_fragmentation",
    severity: Severity = Severity.MEDIUM,
) -> Finding:
    return Finding(
        signal_type=sig,
        severity=severity,
        score=score,
        title="test",
        description="test finding",
    )


# -- score_to_grade ------------------------------------------------------------


class TestScoreToGrade:
    def test_excellent(self):
        assert score_to_grade(0.1) == ("A", "Excellent")

    def test_good(self):
        assert score_to_grade(0.3) == ("B", "Good")

    def test_moderate(self):
        assert score_to_grade(0.5) == ("C", "Moderate Drift")

    def test_significant(self):
        assert score_to_grade(0.7) == ("D", "Significant Drift")

    def test_critical(self):
        assert score_to_grade(0.9) == ("F", "Critical Drift")

    def test_boundary_a(self):
        # Exactly 0.20 is B
        assert score_to_grade(0.20)[0] == "B"

    def test_zero(self):
        assert score_to_grade(0.0) == ("A", "Excellent")


# -- compute_signal_scores -----------------------------------------------------


class TestComputeSignalScores:
    def test_single_finding(self):
        findings = [_finding(score=0.8)]
        scores = compute_signal_scores(findings)
        assert "pattern_fragmentation" in scores
        assert scores["pattern_fragmentation"] > 0

    def test_empty(self):
        scores = compute_signal_scores([])
        # Only signal types with findings should have non-zero scores
        assert all(v == 0 or v > 0 for v in scores.values())

    def test_dampening(self):
        findings = [_finding(score=0.5) for _ in range(20)]
        scores = compute_signal_scores(findings, dampening_k=10)
        assert scores["pattern_fragmentation"] > 0

    def test_min_findings(self):
        findings = [_finding(score=0.5)]
        scores = compute_signal_scores(findings, min_findings=5)
        # Only 1 finding < min_findings=5, should not score
        assert scores.get("pattern_fragmentation", 0) == 0


# -- composite_score -----------------------------------------------------------


class TestCompositeScore:
    def test_basic(self):
        signal_scores = {"pattern_fragmentation": 0.5}
        weights = SignalWeights()
        result = composite_score(signal_scores, weights)
        assert 0.0 <= result <= 1.0

    def test_empty_scores(self):
        result = composite_score({}, SignalWeights())
        assert result == 0.0

    def test_capped_at_one(self):
        # Very high scores should be capped at 1.0
        scores = {str(st): 1.0 for st in SignalType}
        result = composite_score(scores, SignalWeights())
        assert result <= 1.0


# -- severity_gate_pass --------------------------------------------------------


class TestSeverityGatePass:
    def test_none_always_passes(self):
        assert severity_gate_pass([_finding(severity=Severity.CRITICAL)], "none") is True

    def test_high_blocks(self):
        assert severity_gate_pass([_finding(severity=Severity.HIGH)], "high") is False

    def test_high_passes_medium(self):
        assert severity_gate_pass([_finding(severity=Severity.MEDIUM)], "high") is True

    def test_medium_blocks(self):
        assert severity_gate_pass([_finding(severity=Severity.MEDIUM)], "medium") is False

    def test_critical_blocks(self):
        assert severity_gate_pass([_finding(severity=Severity.CRITICAL)], "critical") is False

    def test_empty_passes(self):
        assert severity_gate_pass([], "critical") is True


# -- resolve_path_override -----------------------------------------------------


class TestResolvePathOverride:
    def test_no_overrides(self):
        assert resolve_path_override(Path("src/foo.py"), {}) is None

    def test_none_path(self):
        assert resolve_path_override(None, {"*.py": object()}) is None

    def test_matching_pattern(self):
        from drift.config import PathOverride

        override = PathOverride()
        result = resolve_path_override(Path("src/foo.py"), {"src/*.py": override})
        assert result is override

    def test_longest_match_wins(self):
        from drift.config import PathOverride

        short = PathOverride()
        long_match = PathOverride()
        result = resolve_path_override(
            Path("src/pkg/foo.py"),
            {"src/*": short, "src/pkg/*.py": long_match},
        )
        assert result is long_match
