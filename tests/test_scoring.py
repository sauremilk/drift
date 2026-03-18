"""Tests for the scoring engine."""

from pathlib import Path

from drift.config import SignalWeights
from drift.models import Finding, Severity, SignalType
from drift.scoring.engine import (
    composite_score,
    compute_module_scores,
    compute_signal_scores,
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
    findings = [
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.4),
        _finding(SignalType.PATTERN_FRAGMENTATION, 0.6),
        _finding(SignalType.ARCHITECTURE_VIOLATION, 0.8),
    ]
    scores = compute_signal_scores(findings)
    assert scores[SignalType.PATTERN_FRAGMENTATION] == 0.5
    assert scores[SignalType.ARCHITECTURE_VIOLATION] == 0.8
    # Signals without findings → 0.0
    assert scores[SignalType.DOC_IMPL_DRIFT] == 0.0


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

    findings.append(
        _finding(SignalType.ARCHITECTURE_VIOLATION, 0.9, severity=Severity.CRITICAL)
    )
    assert severity_gate_pass(findings, "critical") is False


def test_gate_empty_findings():
    assert severity_gate_pass([], "high") is True
