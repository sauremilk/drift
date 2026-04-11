"""Ablation study: measure each signal's contribution to overall F1.

Deactivates each signal individually and measures the delta-F1
relative to the full-signal baseline. Signals with low delta
are candidates for weight reduction or removal.

Usage:
    pytest tests/test_ablation.py -v -s
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import pytest

import drift.signals.architecture_violation  # noqa: F401
import drift.signals.broad_exception_monoculture  # noqa: F401
import drift.signals.bypass_accumulation  # noqa: F401
import drift.signals.cohesion_deficit  # noqa: F401
import drift.signals.doc_impl_drift  # noqa: F401
import drift.signals.exception_contract_drift  # noqa: F401
import drift.signals.explainability_deficit  # noqa: F401
import drift.signals.guard_clause_deficit  # noqa: F401
import drift.signals.mutant_duplicates  # noqa: F401
import drift.signals.naming_contract_violation  # noqa: F401
import drift.signals.pattern_fragmentation  # noqa: F401
import drift.signals.system_misalignment  # noqa: F401
import drift.signals.temporal_volatility  # noqa: F401
import drift.signals.test_polarity_deficit  # noqa: F401
from drift.config import DriftConfig, SignalWeights
from drift.ingestion.ast_parser import parse_file
from drift.ingestion.file_discovery import discover_files
from drift.models import (
    FileHistory,
    Finding,
    SignalType,
)
from drift.scoring.engine import (
    composite_score,
    compute_signal_scores,
)
from drift.signals.base import AnalysisContext, create_signals
from tests.fixtures.ground_truth import (
    ALL_FIXTURES,
    GroundTruthFixture,
)

PreparedFixture = dict[str, Any]


def _prepare_fixtures(
    fixtures: list[GroundTruthFixture],
    tmp_path: Path,
) -> dict[str, PreparedFixture]:
    """Materialize fixtures once and precompute parse/history inputs."""
    prepared: dict[str, PreparedFixture] = {}

    for fixture in fixtures:
        fixture_dir = fixture.materialize(tmp_path)
        config = DriftConfig(
            include=["**/*.py"],
            exclude=["**/__pycache__/**"],
            embeddings_enabled=False,
        )

        files = discover_files(fixture_dir, config.include, config.exclude)
        parse_results = []
        for finfo in files:
            pr = parse_file(finfo.path, fixture_dir, finfo.language)
            parse_results.append(pr)

        now = datetime.datetime.now(tz=datetime.UTC)
        file_histories: dict[str, FileHistory] = {}
        for finfo in files:
            key = finfo.path.as_posix()
            is_new = "new_feature" in key

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
                    now
                    if is_new
                    else now - datetime.timedelta(days=60)
                ),
                first_seen=(
                    now - datetime.timedelta(days=3)
                    if is_new
                    else now - datetime.timedelta(days=120)
                ),
            )

        prepared[fixture.name] = {
            "fixture_dir": fixture_dir,
            "config": config,
            "parse_results": parse_results,
            "file_histories": file_histories,
        }

    return prepared


def _run_all_signals_grouped(
    fixtures: list[GroundTruthFixture],
    tmp_path: Path,
    exclude_signal: SignalType | None = None,
    prepared_fixtures: dict[str, PreparedFixture] | None = None,
) -> dict[str, list[Finding]]:
    """Run all signals per fixture, returning findings grouped by fixture name."""
    grouped: dict[str, list[Finding]] = {}

    if prepared_fixtures is None:
        prepared_fixtures = _prepare_fixtures(fixtures, tmp_path)

    for fixture in fixtures:
        prepared = prepared_fixtures[fixture.name]
        fixture_dir = prepared["fixture_dir"]
        config = prepared["config"]
        parse_results = prepared["parse_results"]
        file_histories = prepared["file_histories"]

        ctx = AnalysisContext(
            repo_path=fixture_dir,
            config=config,
            parse_results=parse_results,
            file_histories=file_histories,
            embedding_service=None,
        )

        signals = create_signals(ctx)
        if exclude_signal:
            signals = [s for s in signals if s.signal_type != exclude_signal]

        fixture_findings: list[Finding] = []
        for signal in signals:
            try:
                findings = signal.analyze(parse_results, file_histories, config)
                fixture_findings.extend(findings)
            except Exception:
                pass

        grouped[fixture.name] = fixture_findings

    return grouped


def _compute_fixture_f1(
    fixtures: list[GroundTruthFixture],
    findings_by_fixture: dict[str, list[Finding]],
) -> float:
    """Compute F1 over the ground-truth expectations."""
    tp = fp = fn = 0

    for fixture in fixtures:
        fixture_findings = findings_by_fixture.get(fixture.name, [])

        for exp in fixture.expected:
            matched = any(f.signal_type == exp.signal_type for f in fixture_findings)
            if exp.should_detect and matched:
                tp += 1
            elif exp.should_detect and not matched:
                fn += 1
            elif not exp.should_detect and matched:
                fp += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0


def _build_signal_presence(
    findings_by_fixture: dict[str, list[Finding]],
) -> dict[str, set[SignalType]]:
    """Build per-fixture signal presence set from baseline findings."""
    presence: dict[str, set[SignalType]] = {}
    for fixture_name, findings in findings_by_fixture.items():
        presence[fixture_name] = {f.signal_type for f in findings}
    return presence


def _compute_fixture_f1_from_presence(
    fixtures: list[GroundTruthFixture],
    signal_presence: dict[str, set[SignalType]],
    exclude_signal: SignalType | None = None,
) -> float:
    """Compute F1 using baseline presence map and optional excluded signal."""
    tp = fp = fn = 0

    for fixture in fixtures:
        fixture_presence = signal_presence.get(fixture.name, set())

        for exp in fixture.expected:
            matched = exp.signal_type in fixture_presence and exp.signal_type != exclude_signal
            if exp.should_detect and matched:
                tp += 1
            elif exp.should_detect and not matched:
                fn += 1
            elif not exp.should_detect and matched:
                fp += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0


# ── Signals to ablate ────────────────────────────────────────────────────

ACTIVE_SIGNALS = [
    SignalType.PATTERN_FRAGMENTATION,
    SignalType.ARCHITECTURE_VIOLATION,
    SignalType.MUTANT_DUPLICATE,
    SignalType.EXPLAINABILITY_DEFICIT,
    SignalType.TEMPORAL_VOLATILITY,
    SignalType.SYSTEM_MISALIGNMENT,
    SignalType.DOC_IMPL_DRIFT,
    SignalType.BROAD_EXCEPTION_MONOCULTURE,
    SignalType.TEST_POLARITY_DEFICIT,
    SignalType.GUARD_CLAUSE_DEFICIT,
    SignalType.COHESION_DEFICIT,
    SignalType.NAMING_CONTRACT_VIOLATION,
    SignalType.BYPASS_ACCUMULATION,
    SignalType.EXCEPTION_CONTRACT_DRIFT,
]


@pytest.mark.slow
def test_ablation_study(tmp_path: Path) -> None:
    """Deactivate each signal and measure delta-F1."""
    prepared_fixtures = _prepare_fixtures(ALL_FIXTURES, tmp_path / "prepared")

    # Baseline: all signals active
    baseline_grouped = _run_all_signals_grouped(
        ALL_FIXTURES,
        tmp_path,
        prepared_fixtures=prepared_fixtures,
    )
    signal_presence = _build_signal_presence(baseline_grouped)
    baseline_f1 = _compute_fixture_f1_from_presence(ALL_FIXTURES, signal_presence)

    print(f"\n{'=' * 60}")
    print(f"Ablation Study - Baseline F1: {baseline_f1:.3f}")
    print(f"{'=' * 60}")

    deltas: dict[str, float] = {}

    for signal in ACTIVE_SIGNALS:
        ablated_f1 = _compute_fixture_f1_from_presence(
            ALL_FIXTURES,
            signal_presence,
            exclude_signal=signal,
        )
        delta = baseline_f1 - ablated_f1

        deltas[signal.value] = delta
        indicator = "v" if delta > 0 else "^" if delta < 0 else "="
        print(f"  Without {signal.value:<30s} F1={ablated_f1:.3f}  delta={delta:+.3f} {indicator}")

    print(f"\n{'-' * 60}")
    print("Recommended weight adjustments:")

    # Sort by delta descending - high delta = important signal
    sorted_signals = sorted(deltas.items(), key=lambda x: abs(x[1]), reverse=True)
    for sig_name, delta in sorted_signals:
        if abs(delta) < 0.01:
            print(f"  {sig_name}: minimal impact -> consider reducing weight")
        elif delta > 0.05:
            print(f"  {sig_name}: HIGH impact (delta={delta:+.3f}) -> keep/increase weight")
        else:
            print(f"  {sig_name}: moderate impact (delta={delta:+.3f})")


@pytest.mark.slow
def test_scoring_sensitivity(tmp_path: Path) -> None:
    """Test how composite score changes with weight perturbations."""
    prepared_fixtures = _prepare_fixtures(ALL_FIXTURES, tmp_path / "prepared")
    grouped = _run_all_signals_grouped(
        ALL_FIXTURES,
        tmp_path,
        prepared_fixtures=prepared_fixtures,
    )
    all_findings = [f for fl in grouped.values() for f in fl]
    signal_scores = compute_signal_scores(all_findings)

    default_weights = SignalWeights()
    baseline = composite_score(signal_scores, default_weights)

    print(f"\n{'=' * 60}")
    print(f"Weight Sensitivity - Baseline composite: {baseline:.3f}")
    print(f"{'=' * 60}")
    print(f"Signal scores: {dict(signal_scores)}")

    # Perturb each weight by +0.1 and measure change
    for field_name in type(default_weights).model_fields:
        original = getattr(default_weights, field_name)
        perturbed = default_weights.model_copy(update={field_name: original + 0.1})
        new_score = composite_score(signal_scores, perturbed)
        delta = new_score - baseline
        print(
            f"  {field_name:<30s} "
            f"w={original:.2f}->{original + 0.1:.2f}  "
            f"score={new_score:.3f}  delta={delta:+.3f}"
        )
