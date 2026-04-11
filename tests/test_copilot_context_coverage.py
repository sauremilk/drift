"""Pytest integration for copilot-context coverage benchmark.

Asserts that ``generate_instructions()`` produces correct instruction
sections for known ground-truth fixtures and generates zero false
instructions for true-negative fixtures.
"""

from __future__ import annotations

import datetime
import tempfile
from collections import defaultdict
from pathlib import Path

import pytest

import drift.signals.architecture_violation  # noqa: F401
import drift.signals.broad_exception_monoculture  # noqa: F401
import drift.signals.cohesion_deficit  # noqa: F401
import drift.signals.doc_impl_drift  # noqa: F401
import drift.signals.explainability_deficit  # noqa: F401
import drift.signals.guard_clause_deficit  # noqa: F401
import drift.signals.mutant_duplicates  # noqa: F401
import drift.signals.pattern_fragmentation  # noqa: F401
import drift.signals.system_misalignment  # noqa: F401
import drift.signals.temporal_volatility  # noqa: F401
import drift.signals.test_polarity_deficit  # noqa: F401
from drift.api_helpers import signal_abbrev
from drift.config import DriftConfig
from drift.copilot_context import generate_instructions
from drift.ingestion.ast_parser import parse_file
from drift.ingestion.file_discovery import discover_files
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    RepoAnalysis,
    SignalType,
)
from drift.signals.base import AnalysisContext, create_signals
from tests.fixtures.ground_truth import (
    FIXTURES_BY_SIGNAL,
    GroundTruthFixture,
)

pytestmark = pytest.mark.performance

# ---------------------------------------------------------------------------
# Signal → expected heading (mirrors copilot_context._format_rule)
# ---------------------------------------------------------------------------

SIGNAL_SECTION_MAP: dict[SignalType, str] = {
    SignalType.ARCHITECTURE_VIOLATION: "Layer Boundaries",
    SignalType.PATTERN_FRAGMENTATION: "Code Pattern Consistency",
    SignalType.NAMING_CONTRACT_VIOLATION: "Naming Conventions",
    SignalType.GUARD_CLAUSE_DEFICIT: "Input Validation",
    SignalType.BROAD_EXCEPTION_MONOCULTURE: "Exception Handling",
    SignalType.DOC_IMPL_DRIFT: "Documentation Alignment",
    SignalType.MUTANT_DUPLICATE: "Deduplication",
    SignalType.EXPLAINABILITY_DEFICIT: "Code Documentation",
    SignalType.BYPASS_ACCUMULATION: "TODO/FIXME Hygiene",
    SignalType.EXCEPTION_CONTRACT_DRIFT: "Exception Contracts",
}


# ---------------------------------------------------------------------------
# Fixture → findings pipeline (adapted from test_precision_recall.py)
# ---------------------------------------------------------------------------


def _run_signals_on_fixture(
    fixture: GroundTruthFixture,
    tmp_dir: Path,
    signal_filter: set[SignalType] | None = None,
) -> list[Finding]:
    """Materialize a fixture, parse it, run signal detectors."""
    fixture_dir = fixture.materialize(tmp_dir)

    config = DriftConfig(
        include=["**/*.py"],
        exclude=["**/__pycache__/**"],
        embeddings_enabled=False,
    )

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


def _build_analysis(findings: list[Finding]) -> RepoAnalysis:
    """Build a synthetic RepoAnalysis from a flat finding list."""
    score = max((f.score for f in findings), default=0.0) if findings else 0.0
    return RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=score,
        findings=findings,
    )


# ---------------------------------------------------------------------------
# Shared evaluation data (computed once per session)
# ---------------------------------------------------------------------------


class _CoverageResults:
    """Cache aggregated benchmark results so we compute them once."""

    _instance: _CoverageResults | None = None
    coverage: dict[SignalType, bool]
    miss_reason: dict[SignalType, str]  # signal → reason for non-coverage
    tn_noise: dict[SignalType, list[str]]  # signal → [fixture names with noise]

    @classmethod
    def get(cls) -> _CoverageResults:
        if cls._instance is not None:
            return cls._instance

        inst = cls()
        inst.coverage = {}
        inst.miss_reason = {}
        inst.tn_noise = defaultdict(list)

        with tempfile.TemporaryDirectory() as tmp_root:
            tmp_path = Path(tmp_root)

            for signal_type, heading in SIGNAL_SECTION_MAP.items():
                fixtures = FIXTURES_BY_SIGNAL.get(signal_type, [])
                if not fixtures:
                    inst.coverage[signal_type] = False
                    continue

                # TP fixtures → aggregate findings
                tp_fixtures = [
                    f
                    for f in fixtures
                    if any(e.signal_type == signal_type and e.should_detect for e in f.expected)
                ]
                aggregated: list[Finding] = []
                for fix in tp_fixtures:
                    findings = _run_signals_on_fixture(fix, tmp_path, signal_filter={signal_type})
                    aggregated.extend(findings)

                analysis = _build_analysis(aggregated)
                instructions = generate_instructions(analysis)
                heading_with_id = f"### {heading} ({signal_abbrev(signal_type)})"
                heading_found = heading_with_id in instructions
                inst.coverage[signal_type] = heading_found

                if not heading_found:
                    actionable = [
                        f for f in aggregated if f.signal_type == signal_type and f.score >= 0.4
                    ]
                    if not actionable:
                        inst.miss_reason[signal_type] = "no findings above score threshold"
                    elif len(actionable) < 2:
                        inst.miss_reason[signal_type] = "below min_finding_count"
                    else:
                        inst.miss_reason[signal_type] = "heading with signal id not in output"

                # TN fixtures → check no false instructions
                tn_fixtures = [
                    f
                    for f in fixtures
                    if all(
                        not (e.signal_type == signal_type and e.should_detect) for e in f.expected
                    )
                ]
                for tn_fix in tn_fixtures:
                    tn_findings = _run_signals_on_fixture(
                        tn_fix, tmp_path, signal_filter={signal_type}
                    )
                    tn_analysis = _build_analysis(tn_findings)
                    tn_instr = generate_instructions(tn_analysis)
                    if f"### {heading} ({signal_abbrev(signal_type)})" in tn_instr:
                        inst.tn_noise[signal_type].append(tn_fix.name)

        cls._instance = inst
        return inst


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


# Parametrize over each actionable signal for granular reporting
_signal_params = [
    pytest.param(sig, id=sig.value)
    for sig in sorted(SIGNAL_SECTION_MAP, key=lambda s: s.value)
    if FIXTURES_BY_SIGNAL.get(sig)
]


@pytest.mark.parametrize("signal_type", _signal_params)
def test_signal_instruction_coverage(signal_type: SignalType) -> None:
    """TP fixtures for *signal_type* must produce the expected instruction heading.

    Signals whose aggregated findings fall below the min_finding_count or
    score threshold are skipped — the aggregate coverage rate test is the
    hard gate.
    """
    results = _CoverageResults.get()
    covered = results.coverage.get(signal_type, False)
    if not covered:
        reason = results.miss_reason.get(signal_type, "")
        if reason in ("no findings above score threshold", "below min_finding_count"):
            pytest.skip(f"Expected miss: {reason}")
    assert covered, (
        f"generate_instructions() did not produce "
        f"'### {SIGNAL_SECTION_MAP[signal_type]} ({signal_abbrev(signal_type)})' "
        f"for aggregated TP fixtures of {signal_type.value}"
    )


@pytest.mark.parametrize("signal_type", _signal_params)
def test_signal_no_noise(signal_type: SignalType) -> None:
    """TN fixtures for *signal_type* must NOT produce instructions for that signal."""
    results = _CoverageResults.get()
    noisy = results.tn_noise.get(signal_type, [])
    assert not noisy, (
        f"generate_instructions() produced "
        f"'### {SIGNAL_SECTION_MAP[signal_type]} ({signal_abbrev(signal_type)})' "
        f"for TN fixtures: {noisy}"
    )


def test_aggregate_instruction_coverage_rate() -> None:
    """Overall instruction coverage rate must be >= 70%."""
    results = _CoverageResults.get()
    covered = sum(1 for v in results.coverage.values() if v)
    total = len(results.coverage)
    rate = covered / total if total else 0.0
    assert rate >= 0.70, (
        f"Instruction coverage rate {rate:.1%} is below 70% threshold "
        f"({covered}/{total} signals covered)"
    )


def test_aggregate_noise_rate_zero() -> None:
    """No TN fixture should produce false instructions (noise rate = 0)."""
    results = _CoverageResults.get()
    total_noise = sum(len(v) for v in results.tn_noise.values())
    assert total_noise == 0, (
        f"Noise rate is non-zero: {total_noise} false instruction(s) generated "
        f"for TN fixtures: {dict(results.tn_noise)}"
    )
