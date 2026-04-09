"""Precision / Recall evaluation framework for drift signals.

Runs each ground-truth fixture through its relevant signal detector(s)
and computes per-signal and aggregate P/R/F1 metrics.

Usage (pytest):
    pytest tests/test_precision_recall.py -v

Usage (standalone report):
    python -m pytest tests/test_precision_recall.py -v --tb=short
"""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.models import SignalType
from drift.precision import (
    PrecisionRecallReport,
    ensure_signals_registered,
    evaluate_fixtures,
    has_matching_finding,
    run_fixture,
)
from tests.fixtures.ground_truth import (
    ALL_FIXTURES,
    GroundTruthFixture,
)

ensure_signals_registered()


# ── Pytest tests ──────────────────────────────────────────────────────────


@pytest.fixture
def pr_report() -> PrecisionRecallReport:
    return PrecisionRecallReport()


@pytest.mark.ground_truth
@pytest.mark.parametrize(
    "fixture",
    ALL_FIXTURES,
    ids=[f.name for f in ALL_FIXTURES],
)
def test_ground_truth_fixture(
    fixture: GroundTruthFixture,
    tmp_path: Path,
) -> None:
    """Verify each fixture produces expected findings (TP) and
    does not produce unexpected findings (TN)."""
    relevant_signals = {e.signal_type for e in fixture.expected}
    findings, _warnings = run_fixture(fixture, tmp_path, signal_filter=relevant_signals)

    for exp in fixture.expected:
        detected = has_matching_finding(findings, exp)
        if exp.should_detect:
            assert detected, (
                f"[FN] {fixture.name}: expected {exp.signal_type} "
                f"at {exp.file_path} but not found. "
                f"Findings: {[(f.signal_type, f.file_path) for f in findings]}"
            )
        else:
            assert not detected, (
                f"[FP] {fixture.name}: did NOT expect "
                f"{exp.signal_type} at {exp.file_path} but found. "
                f"Findings: {[(f.signal_type, f.file_path) for f in findings]}"
            )


@pytest.mark.ground_truth
def test_precision_recall_report(tmp_path: Path) -> None:
    """Run all fixtures and print the P/R summary."""
    report, _warnings = evaluate_fixtures(ALL_FIXTURES, tmp_path)

    print("\n" + report.summary())
    # Minimum quality bar: macro-F1 must be ≥ 0.60
    assert report.aggregate_f1() >= 0.60, (
        f"Aggregate F1 too low: {report.aggregate_f1():.2f}\n" + report.summary()
    )

    # ── Per-signal precision gates ────────────────────────────────────
    # Signals with high expected precision get a stricter gate;
    # signals with known FP issues get a lower but non-zero bar.
    per_signal_precision: dict[SignalType, float] = {
        SignalType.PATTERN_FRAGMENTATION: 0.70,
        SignalType.EXPLAINABILITY_DEFICIT: 0.70,
        SignalType.SYSTEM_MISALIGNMENT: 0.70,
        SignalType.MUTANT_DUPLICATE: 0.60,
        SignalType.BROAD_EXCEPTION_MONOCULTURE: 0.60,
        SignalType.GUARD_CLAUSE_DEFICIT: 0.60,
        SignalType.NAMING_CONTRACT_VIOLATION: 0.60,
        SignalType.BYPASS_ACCUMULATION: 0.60,
        SignalType.TEST_POLARITY_DEFICIT: 0.50,
        SignalType.ARCHITECTURE_VIOLATION: 0.50,
        SignalType.DOC_IMPL_DRIFT: 0.50,
        SignalType.TEMPORAL_VOLATILITY: 0.50,
        SignalType.COHESION_DEFICIT: 0.50,
        SignalType.CO_CHANGE_COUPLING: 0.50,
    }
    for sig, min_prec in per_signal_precision.items():
        # Only enforce if the signal has any TP+FP observations
        if report.tp[sig] + report.fp[sig] > 0:
            actual = report.precision(sig)
            assert actual >= min_prec, (
                f"Per-signal precision gate failed for {sig.value}: "
                f"{actual:.2f} < {min_prec:.2f}\n" + report.summary()
            )
