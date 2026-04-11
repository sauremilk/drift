"""Shared precision/recall evaluation engine for ground-truth fixtures.

Used by both ``drift precision`` CLI and ``tests/test_precision_recall.py``.
"""

from __future__ import annotations

import datetime
import json
import subprocess
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from drift.config import DriftConfig
from drift.ingestion.ast_parser import parse_file
from drift.ingestion.file_discovery import discover_files
from drift.models import (
    AnalyzerWarning,
    FileHistory,
    Finding,
    ParseResult,
    SignalType,
)
from drift.signals.base import AnalysisContext, create_signals

if TYPE_CHECKING:
    from tests.fixtures.ground_truth import ExpectedFinding, GroundTruthFixture


def ensure_signals_registered() -> None:
    """Import all signal modules so ``@register_signal`` decorators execute."""
    import drift.signals.architecture_violation  # noqa: F401
    import drift.signals.broad_exception_monoculture  # noqa: F401
    import drift.signals.bypass_accumulation  # noqa: F401
    import drift.signals.circular_import  # noqa: F401
    import drift.signals.co_change_coupling  # noqa: F401
    import drift.signals.cognitive_complexity  # noqa: F401
    import drift.signals.cohesion_deficit  # noqa: F401
    import drift.signals.dead_code_accumulation  # noqa: F401
    import drift.signals.doc_impl_drift  # noqa: F401
    import drift.signals.exception_contract_drift  # noqa: F401
    import drift.signals.explainability_deficit  # noqa: F401
    import drift.signals.fan_out_explosion  # noqa: F401
    import drift.signals.guard_clause_deficit  # noqa: F401
    import drift.signals.hardcoded_secret  # noqa: F401
    import drift.signals.insecure_default  # noqa: F401
    import drift.signals.missing_authorization  # noqa: F401
    import drift.signals.mutant_duplicates  # noqa: F401
    import drift.signals.naming_contract_violation  # noqa: F401
    import drift.signals.pattern_fragmentation  # noqa: F401
    import drift.signals.system_misalignment  # noqa: F401
    import drift.signals.temporal_volatility  # noqa: F401
    import drift.signals.test_polarity_deficit  # noqa: F401


__all__ = [
    "PrecisionRecallReport",
    "ensure_signals_registered",
    "evaluate_fixtures",
    "has_matching_finding",
    "run_fixture",
]


def _run_git(cwd: Path, *args: str) -> None:
    """Run a git command silently in *cwd*."""
    subprocess.run(  # noqa: S603, S607
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        check=True,
        stdin=subprocess.DEVNULL,
    )


def _setup_git_history(
    fixture_dir: Path,
    old_sources: dict[str, str],
    current_files: dict[str, str],
) -> None:
    """Create a minimal git repo with two commits: old_sources → current_files."""
    _run_git(fixture_dir, "init")
    _run_git(fixture_dir, "config", "user.email", "fixture@test")
    _run_git(fixture_dir, "config", "user.name", "fixture")

    # Commit 1: old sources
    for rel_path, content in old_sources.items():
        full = fixture_dir / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(textwrap.dedent(content), encoding="utf-8")
    _run_git(fixture_dir, "add", ".")
    _run_git(fixture_dir, "commit", "-m", "initial")

    # Commit 2: current files (overwrites old sources)
    for rel_path, content in current_files.items():
        full = fixture_dir / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(textwrap.dedent(content), encoding="utf-8")
    _run_git(fixture_dir, "add", ".")
    _run_git(fixture_dir, "commit", "-m", "current", "--allow-empty")


def run_fixture(
    fixture: GroundTruthFixture,
    tmp_path: Path,
    signal_filter: set[SignalType] | None = None,
) -> tuple[list[Finding], list[AnalyzerWarning]]:
    """Materialize a fixture, parse it, run signals, return findings and warnings."""
    has_old_sources = bool(getattr(fixture, "old_sources", None))

    if has_old_sources:
        # Create git repo with old sources first, then overwrite with current
        fixture_dir = tmp_path / fixture.name
        fixture_dir.mkdir(parents=True, exist_ok=True)
        _setup_git_history(fixture_dir, fixture.old_sources, fixture.files)
    else:
        fixture_dir = fixture.materialize(tmp_path)

    config = DriftConfig(
        include=["**/*.py"],
        exclude=["**/__pycache__/**"],
        embeddings_enabled=False,
    )
    if has_old_sources:
        config.thresholds.ecm_lookback_commits = 1

    files = discover_files(fixture_dir, config.include, config.exclude)
    parse_results: list[ParseResult] = []
    for finfo in files:
        pr = parse_file(finfo.path, fixture_dir, finfo.language)
        parse_results.append(pr)

    file_histories: dict[str, FileHistory] = {}
    for finfo in files:
        key = finfo.path.as_posix()
        is_new = "new_feature" in key or "new_func" in key

        override = fixture.file_history_overrides.get(key)

        file_histories[key] = FileHistory(
            path=finfo.path,
            total_commits=(
                override.total_commits
                if override and override.total_commits is not None
                else (1 if is_new else 10)
            ),
            unique_authors=(
                override.unique_authors
                if override and override.unique_authors is not None
                else 1
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
        commits=fixture.commits if fixture.commits else [],
    )

    signals = create_signals(ctx)
    if signal_filter:
        signals = [s for s in signals if s.signal_type in signal_filter]

    all_findings: list[Finding] = []
    all_warnings: list[AnalyzerWarning] = []
    for signal in signals:
        try:
            findings = signal.analyze(parse_results, file_histories, config)
            all_findings.extend(findings)
            all_warnings.extend(signal._warnings)
        except Exception:
            pass

    return all_findings, all_warnings


def has_matching_finding(
    findings: list[Finding],
    expected: ExpectedFinding,
) -> bool:
    """Check if any finding matches the expected signal type and file."""
    for f in findings:
        if f.signal_type != expected.signal_type:
            continue
        if f.file_path is None:
            continue
        finding_path = f.file_path.as_posix()
        if expected.file_path.rstrip("/") in finding_path or finding_path in expected.file_path:
            return True
    for f in findings:
        if f.signal_type != expected.signal_type:
            continue
        for rf in f.related_files:
            if expected.file_path.rstrip("/") in rf.as_posix():
                return True
    return False


class PrecisionRecallReport:
    """Computes and formats P/R/F1 per signal type."""

    def __init__(self) -> None:
        """Initialize per-signal confusion-matrix counters."""
        self.tp: dict[SignalType, int] = defaultdict(int)
        self.fp: dict[SignalType, int] = defaultdict(int)
        self.fn: dict[SignalType, int] = defaultdict(int)
        self.tn: dict[SignalType, int] = defaultdict(int)

    def record_tp(self, signal: SignalType, fixture: str, desc: str) -> None:
        """Record a true positive observation for a signal."""
        self.tp[signal] += 1

    def record_fp(self, signal: SignalType, fixture: str, desc: str) -> None:
        """Record a false positive observation for a signal."""
        self.fp[signal] += 1

    def record_fn(self, signal: SignalType, fixture: str, desc: str) -> None:
        """Record a false negative observation for a signal."""
        self.fn[signal] += 1

    def record_tn(self, signal: SignalType, fixture: str, desc: str) -> None:
        """Record a true negative observation for a signal."""
        self.tn[signal] += 1

    def precision(self, signal: SignalType) -> float:
        """Return precision for one signal."""
        tp = self.tp[signal]
        fp = self.fp[signal]
        return tp / (tp + fp) if (tp + fp) > 0 else 1.0

    def recall(self, signal: SignalType) -> float:
        """Return recall for one signal."""
        tp = self.tp[signal]
        fn = self.fn[signal]
        return tp / (tp + fn) if (tp + fn) > 0 else 1.0

    def f1(self, signal: SignalType) -> float:
        """Return F1 score for one signal."""
        p = self.precision(signal)
        r = self.recall(signal)
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    def aggregate_f1(self) -> float:
        """Return macro-average F1 across observed signals."""
        signals = set(self.tp) | set(self.fp) | set(self.fn)
        if not signals:
            return 0.0
        return sum(self.f1(s) for s in signals) / len(signals)

    @property
    def all_signals(self) -> list[SignalType]:
        """All signals with at least one observation, sorted."""
        return sorted(
            set(self.tp) | set(self.fp) | set(self.fn) | set(self.tn),
            key=lambda s: s.value,
        )

    def to_dict(self) -> dict[str, Any]:
        """Machine-readable dict for JSON output."""
        signals = self.all_signals
        per_signal = {}
        for sig in signals:
            per_signal[sig.value] = {
                "tp": self.tp[sig],
                "tn": self.tn[sig],
                "fp": self.fp[sig],
                "fn": self.fn[sig],
                "precision": round(self.precision(sig), 4),
                "recall": round(self.recall(sig), 4),
                "f1": round(self.f1(sig), 4),
            }
        return {
            "signals": per_signal,
            "aggregate_f1": round(self.aggregate_f1(), 4),
            "total_fixtures": sum(
                self.tp[s] + self.tn[s] + self.fp[s] + self.fn[s]
                for s in signals
            ),
        }

    def to_json(self) -> str:
        """Serialize report as JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def summary(self) -> str:
        """Return a human-readable multiline precision/recall report."""
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


def evaluate_fixtures(
    fixtures: list[GroundTruthFixture],
    tmp_path: Path,
    signal_filter: set[SignalType] | None = None,
) -> tuple[PrecisionRecallReport, list[AnalyzerWarning]]:
    """Run all given fixtures and return a populated report + collected warnings."""
    report = PrecisionRecallReport()
    all_warnings: list[AnalyzerWarning] = []

    for fixture in fixtures:
        relevant_signals = {e.signal_type for e in fixture.expected}
        if signal_filter:
            relevant_signals &= signal_filter
            if not relevant_signals:
                continue

        findings, warnings = run_fixture(fixture, tmp_path, signal_filter=relevant_signals)
        all_warnings.extend(warnings)

        for exp in fixture.expected:
            if signal_filter and exp.signal_type not in signal_filter:
                continue
            detected = has_matching_finding(findings, exp)
            if exp.should_detect and detected:
                report.record_tp(exp.signal_type, fixture.name, exp.description)
            elif exp.should_detect and not detected:
                report.record_fn(exp.signal_type, fixture.name, exp.description)
            elif not exp.should_detect and detected:
                report.record_fp(exp.signal_type, fixture.name, exp.description)
            else:
                report.record_tn(exp.signal_type, fixture.name, exp.description)

    return report, all_warnings
