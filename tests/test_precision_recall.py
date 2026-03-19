"""Precision / Recall evaluation framework for drift signals.

Runs each ground-truth fixture through its relevant signal detector(s)
and computes per-signal and aggregate P/R/F1 metrics.

Usage (pytest):
    pytest tests/test_precision_recall.py -v

Usage (standalone report):
    python -m pytest tests/test_precision_recall.py -v --tb=short
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from pathlib import Path

import pytest

import drift.signals.architecture_violation  # noqa: F401
import drift.signals.doc_impl_drift  # noqa: F401
import drift.signals.explainability_deficit  # noqa: F401
import drift.signals.mutant_duplicates  # noqa: F401
import drift.signals.pattern_fragmentation  # noqa: F401
import drift.signals.system_misalignment  # noqa: F401
import drift.signals.temporal_volatility  # noqa: F401
from drift.config import DriftConfig
from drift.ingestion.ast_parser import parse_file
from drift.ingestion.file_discovery import discover_files
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    SignalType,
)
from drift.signals.base import AnalysisContext, create_signals
from tests.fixtures.ground_truth import (
    ALL_FIXTURES,
    ExpectedFinding,
    GroundTruthFixture,
)


def _run_signals_on_fixture(
    fixture: GroundTruthFixture,
    tmp_path: Path,
    signal_filter: set[SignalType] | None = None,
) -> list[Finding]:
    """Materialize a fixture, parse it, run signals, return findings."""
    fixture_dir = fixture.materialize(tmp_path)

    config = DriftConfig(
        include=["**/*.py"],
        exclude=["**/__pycache__/**"],
        embeddings_enabled=False,
    )

    # Discover & parse files
    files = discover_files(fixture_dir, config.include, config.exclude)
    parse_results: list[ParseResult] = []
    for finfo in files:
        pr = parse_file(finfo.path, fixture_dir, finfo.language)
        parse_results.append(pr)

    # Mock file histories: SMS needs recency info, TVS needs churn outliers
    file_histories: dict[str, FileHistory] = {}
    for finfo in files:
        key = finfo.path.as_posix()
        is_new = "new_feature" in key or "new_func" in key

        # Apply fixture-level overrides if present
        override = fixture.file_history_overrides.get(key)

        file_histories[key] = FileHistory(
            path=finfo.path,
            total_commits=(
                override.total_commits
                if override and override.total_commits is not None
                else (1 if is_new else 10)
            ),
            unique_authors=(
                override.unique_authors if override and override.unique_authors is not None else 1
            ),
            ai_attributed_commits=(
                override.ai_attributed_commits
                if override and override.ai_attributed_commits is not None
                else 0
            ),
            change_frequency_30d=(
                override.change_frequency_30d
                if override and override.change_frequency_30d is not None
                else (5.0 if is_new else 0.5)
            ),
            defect_correlated_commits=(
                override.defect_correlated_commits
                if override and override.defect_correlated_commits is not None
                else 0
            ),
            last_modified=(
                datetime.datetime.now(tz=datetime.UTC)
                if is_new
                else datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=60)
            ),
            first_seen=(
                datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=3)
                if is_new
                else datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=120)
            ),
        )

    ctx = AnalysisContext(
        repo_path=fixture_dir,
        config=config,
        parse_results=parse_results,
        file_histories=file_histories,
        embedding_service=None,
    )

    signals = create_signals(ctx)
    if signal_filter:
        signals = [s for s in signals if s.signal_type in signal_filter]

    all_findings: list[Finding] = []
    for signal in signals:
        try:
            findings = signal.analyze(parse_results, file_histories, config)
            all_findings.extend(findings)
        except Exception:
            pass

    return all_findings


def _has_matching_finding(
    findings: list[Finding],
    expected: ExpectedFinding,
) -> bool:
    """Check if any finding matches the expected signal type and file."""
    for f in findings:
        if f.signal_type != expected.signal_type:
            continue
        if f.file_path is None:
            continue
        # Match if expected path is a prefix of the finding path
        # or finding path is a prefix of expected path (module-level)
        finding_path = f.file_path.as_posix()
        if expected.file_path.rstrip("/") in finding_path or finding_path in expected.file_path:
            return True
    # Also check related_files for broader matches
    for f in findings:
        if f.signal_type != expected.signal_type:
            continue
        for rf in f.related_files:
            if expected.file_path.rstrip("/") in rf.as_posix():
                return True
    return False


# ── Per-signal metrics computation ────────────────────────────────────────


class PrecisionRecallReport:
    """Computes and formats P/R/F1 per signal type."""

    def __init__(self) -> None:
        self.tp: dict[SignalType, int] = defaultdict(int)
        self.fp: dict[SignalType, int] = defaultdict(int)
        self.fn: dict[SignalType, int] = defaultdict(int)
        self.tn: dict[SignalType, int] = defaultdict(int)

    def record_tp(self, signal: SignalType, fixture: str, desc: str) -> None:
        self.tp[signal] += 1

    def record_fp(self, signal: SignalType, fixture: str, desc: str) -> None:
        self.fp[signal] += 1

    def record_fn(self, signal: SignalType, fixture: str, desc: str) -> None:
        self.fn[signal] += 1

    def record_tn(self, signal: SignalType, fixture: str, desc: str) -> None:
        self.tn[signal] += 1

    def precision(self, signal: SignalType) -> float:
        tp = self.tp[signal]
        fp = self.fp[signal]
        return tp / (tp + fp) if (tp + fp) > 0 else 1.0

    def recall(self, signal: SignalType) -> float:
        tp = self.tp[signal]
        fn = self.fn[signal]
        return tp / (tp + fn) if (tp + fn) > 0 else 1.0

    def f1(self, signal: SignalType) -> float:
        p = self.precision(signal)
        r = self.recall(signal)
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    def aggregate_f1(self) -> float:
        signals = set(self.tp) | set(self.fp) | set(self.fn)
        if not signals:
            return 0.0
        return sum(self.f1(s) for s in signals) / len(signals)

    def summary(self) -> str:
        lines = ["Signal Precision/Recall Report", "=" * 60]
        signals = sorted(
            set(self.tp) | set(self.fp) | set(self.fn),
            key=lambda s: s.value,
        )
        for sig in signals:
            lines.append(
                f"  {sig.value:<30s} "
                f"P={self.precision(sig):.2f} "
                f"R={self.recall(sig):.2f} "
                f"F1={self.f1(sig):.2f} "
                f"(TP={self.tp[sig]} FP={self.fp[sig]} "
                f"FN={self.fn[sig]} TN={self.tn[sig]})"
            )
        lines.append("-" * 60)
        lines.append(f"  Macro-Average F1: {self.aggregate_f1():.2f}")
        return "\n".join(lines)


# ── Pytest tests ──────────────────────────────────────────────────────────


@pytest.fixture
def pr_report() -> PrecisionRecallReport:
    return PrecisionRecallReport()


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
    findings = _run_signals_on_fixture(fixture, tmp_path, signal_filter=relevant_signals)

    for exp in fixture.expected:
        detected = _has_matching_finding(findings, exp)
        if exp.should_detect:
            assert detected, (
                f"[FN] {fixture.name}: expected {exp.signal_type.value} "
                f"at {exp.file_path} but not found. "
                f"Findings: {[(f.signal_type.value, f.file_path) for f in findings]}"
            )
        else:
            assert not detected, (
                f"[FP] {fixture.name}: did NOT expect "
                f"{exp.signal_type.value} at {exp.file_path} but found. "
                f"Findings: {[(f.signal_type.value, f.file_path) for f in findings]}"
            )


def test_precision_recall_report(tmp_path: Path) -> None:
    """Run all fixtures and print the P/R summary."""
    report = PrecisionRecallReport()

    for fixture in ALL_FIXTURES:
        relevant_signals = {e.signal_type for e in fixture.expected}
        findings = _run_signals_on_fixture(fixture, tmp_path, signal_filter=relevant_signals)

        for exp in fixture.expected:
            detected = _has_matching_finding(findings, exp)
            if exp.should_detect and detected:
                report.record_tp(exp.signal_type, fixture.name, exp.description)
            elif exp.should_detect and not detected:
                report.record_fn(exp.signal_type, fixture.name, exp.description)
            elif not exp.should_detect and detected:
                report.record_fp(exp.signal_type, fixture.name, exp.description)
            else:
                report.record_tn(exp.signal_type, fixture.name, exp.description)

    print("\n" + report.summary())
    # Minimum quality bar: macro-F1 must be ≥ 0.50
    assert report.aggregate_f1() >= 0.50, (
        f"Aggregate F1 too low: {report.aggregate_f1():.2f}\n" + report.summary()
    )
