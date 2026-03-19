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

import drift.signals.architecture_violation  # noqa: F401
import drift.signals.doc_impl_drift  # noqa: F401
import drift.signals.explainability_deficit  # noqa: F401
import drift.signals.mutant_duplicates  # noqa: F401
import drift.signals.pattern_fragmentation  # noqa: F401
import drift.signals.system_misalignment  # noqa: F401
import drift.signals.temporal_volatility  # noqa: F401
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


def _run_all_signals_grouped(
    fixtures: list[GroundTruthFixture],
    tmp_path: Path,
    exclude_signal: SignalType | None = None,
) -> dict[str, list[Finding]]:
    """Run all signals per fixture, returning findings grouped by fixture name."""
    grouped: dict[str, list[Finding]] = {}

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


# ── Signals to ablate ────────────────────────────────────────────────────

ACTIVE_SIGNALS = [
    SignalType.PATTERN_FRAGMENTATION,
    SignalType.ARCHITECTURE_VIOLATION,
    SignalType.MUTANT_DUPLICATE,
    SignalType.EXPLAINABILITY_DEFICIT,
    SignalType.TEMPORAL_VOLATILITY,
    SignalType.SYSTEM_MISALIGNMENT,
    SignalType.DOC_IMPL_DRIFT,
]


def test_ablation_study(tmp_path: Path) -> None:
    """Deactivate each signal and measure delta-F1."""
    # Baseline: all signals active
    baseline_grouped = _run_all_signals_grouped(ALL_FIXTURES, tmp_path)
    baseline_f1 = _compute_fixture_f1(ALL_FIXTURES, baseline_grouped)

    print(f"\n{'=' * 60}")
    print(f"Ablation Study - Baseline F1: {baseline_f1:.3f}")
    print(f"{'=' * 60}")

    deltas: dict[str, float] = {}

    for signal in ACTIVE_SIGNALS:
        # Use a fresh tmp subdir per ablation run
        ablation_dir = tmp_path / f"ablation_{signal.value}"
        ablation_dir.mkdir()

        ablated_grouped = _run_all_signals_grouped(
            ALL_FIXTURES, ablation_dir, exclude_signal=signal
        )
        ablated_f1 = _compute_fixture_f1(ALL_FIXTURES, ablated_grouped)
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


def test_scoring_sensitivity(tmp_path: Path) -> None:
    """Test how composite score changes with weight perturbations."""
    grouped = _run_all_signals_grouped(ALL_FIXTURES, tmp_path)
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
