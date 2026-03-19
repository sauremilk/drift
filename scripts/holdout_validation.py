"""Leave-One-Out Cross-Validation for weight calibration.

Validates that calibrate_weights() generalises beyond the 15 training
fixtures. For each fold, one fixture is held out:

  1. Ablation study runs on the remaining 14 → delta-F1 per signal
  2. calibrate_weights() produces fold-specific weights
  3. Held-out fixture is evaluated with the fold-specific signals

Reports:
  - Per-fold detection accuracy on the held-out fixture
  - Aggregate held-out F1 across all 15 folds
  - Weight stability: σ per signal across folds
  - Comparison to full-set weights

Usage:
    python scripts/holdout_validation.py
    python scripts/holdout_validation.py --json benchmark_results/holdout_validation.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean, stdev

# Ensure drift is importable from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
from drift.models import FileHistory, Finding, SignalType
from drift.scoring.engine import calibrate_weights
from drift.signals.base import AnalysisContext, create_signals
from tests.fixtures.ground_truth import ALL_FIXTURES, GroundTruthFixture

ACTIVE_SIGNALS = [
    SignalType.PATTERN_FRAGMENTATION,
    SignalType.ARCHITECTURE_VIOLATION,
    SignalType.MUTANT_DUPLICATE,
    SignalType.EXPLAINABILITY_DEFICIT,
    SignalType.TEMPORAL_VOLATILITY,
    SignalType.SYSTEM_MISALIGNMENT,
    SignalType.DOC_IMPL_DRIFT,
]


# ── Helpers (reused from test_ablation.py) ───────────────────────────────


def _run_fixtures(
    fixtures: list[GroundTruthFixture],
    base_dir: Path,
    *,
    exclude_signal: SignalType | None = None,
) -> dict[str, list[Finding]]:
    """Run all signals on each fixture, returning findings grouped by name."""
    grouped: dict[str, list[Finding]] = {}

    for fixture in fixtures:
        fixture_dir = fixture.materialize(base_dir)
        config = DriftConfig(
            include=["**/*.py"],
            exclude=["**/__pycache__/**"],
            embeddings_enabled=False,
        )

        files = discover_files(fixture_dir, config.include, config.exclude)
        parse_results = [
            parse_file(f.path, fixture_dir, f.language) for f in files
        ]

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
                    else datetime.datetime.now(tz=datetime.UTC)
                    - datetime.timedelta(days=60)
                ),
                first_seen=(
                    datetime.datetime.now(tz=datetime.UTC)
                    - datetime.timedelta(days=3)
                    if is_new
                    else datetime.datetime.now(tz=datetime.UTC)
                    - datetime.timedelta(days=120)
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


def _compute_f1(
    fixtures: list[GroundTruthFixture],
    findings_by_fixture: dict[str, list[Finding]],
) -> tuple[float, int, int, int]:
    """Compute F1, returning (f1, tp, fp, fn)."""
    tp = fp = fn = 0

    for fixture in fixtures:
        fixture_findings = findings_by_fixture.get(fixture.name, [])
        for exp in fixture.expected:
            matched = any(
                f.signal_type == exp.signal_type for f in fixture_findings
            )
            if exp.should_detect and matched:
                tp += 1
            elif exp.should_detect and not matched:
                fn += 1
            elif not exp.should_detect and matched:
                fp += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return f1, tp, fp, fn


# ── Data classes ─────────────────────────────────────────────────────────


@dataclass
class FoldResult:
    fold: int
    held_out: str
    train_f1: float
    held_out_correct: bool
    held_out_tp: int
    held_out_fp: int
    held_out_fn: int
    weights: dict[str, float]
    ablation_deltas: dict[str, float]


@dataclass
class LOOCVResult:
    n_fixtures: int
    n_folds: int
    held_out_f1: float
    held_out_tp: int
    held_out_fp: int
    held_out_fn: int
    full_set_f1: float
    weight_means: dict[str, float]
    weight_stdevs: dict[str, float]
    full_set_weights: dict[str, float]
    folds: list[FoldResult] = field(default_factory=list)


# ── Core LOOCV ───────────────────────────────────────────────────────────


def run_loocv() -> LOOCVResult:
    """Run Leave-One-Out Cross-Validation across all fixtures."""
    n = len(ALL_FIXTURES)
    folds: list[FoldResult] = []

    # Accumulated held-out predictions
    total_tp = total_fp = total_fn = 0

    with tempfile.TemporaryDirectory(prefix="drift-loocv-") as tmpdir:
        tmp = Path(tmpdir)

        # ── Full-set baseline ────────────────────────────────────────
        print(f"{'=' * 65}")
        print(f"LOOCV: {n} fixtures, {n} folds")
        print(f"{'=' * 65}")

        full_dir = tmp / "full"
        full_dir.mkdir()
        full_grouped = _run_fixtures(ALL_FIXTURES, full_dir)
        full_f1, _, _, _ = _compute_f1(ALL_FIXTURES, full_grouped)

        # Full-set ablation → full-set weights
        full_deltas: dict[str, float] = {}
        for signal in ACTIVE_SIGNALS:
            abl_dir = tmp / f"full_abl_{signal.value}"
            abl_dir.mkdir()
            abl_grouped = _run_fixtures(ALL_FIXTURES, abl_dir, exclude_signal=signal)
            abl_f1, _, _, _ = _compute_f1(ALL_FIXTURES, abl_grouped)
            full_deltas[signal.value] = full_f1 - abl_f1

        full_weights = calibrate_weights(full_deltas, SignalWeights())
        full_weights_dict = full_weights.as_dict()

        print(f"\nFull-set baseline: F1={full_f1:.3f}")
        print(f"Full-set weights:  {_fmt_weights(full_weights_dict)}")
        print()

        # ── Per-fold ─────────────────────────────────────────────────
        for i, held_out_fixture in enumerate(ALL_FIXTURES):
            train_fixtures = [f for j, f in enumerate(ALL_FIXTURES) if j != i]

            # Train: run signals on 14 fixtures
            train_dir = tmp / f"fold_{i}_train"
            train_dir.mkdir()
            train_grouped = _run_fixtures(train_fixtures, train_dir)
            train_f1, _, _, _ = _compute_f1(train_fixtures, train_grouped)

            # Train: ablation on 14 fixtures → fold weights
            fold_deltas: dict[str, float] = {}
            for signal in ACTIVE_SIGNALS:
                abl_dir = tmp / f"fold_{i}_abl_{signal.value}"
                abl_dir.mkdir()
                abl_grouped = _run_fixtures(
                    train_fixtures, abl_dir, exclude_signal=signal
                )
                abl_f1, _, _, _ = _compute_f1(train_fixtures, abl_grouped)
                fold_deltas[signal.value] = train_f1 - abl_f1

            fold_weights = calibrate_weights(fold_deltas, SignalWeights())

            # Evaluate: run signals on held-out fixture
            val_dir = tmp / f"fold_{i}_val"
            val_dir.mkdir()
            val_grouped = _run_fixtures([held_out_fixture], val_dir)
            _, tp, fp, fn = _compute_f1([held_out_fixture], val_grouped)

            total_tp += tp
            total_fp += fp
            total_fn += fn

            all_correct = fp == 0 and fn == 0
            status = "✓" if all_correct else "✗"

            fold = FoldResult(
                fold=i,
                held_out=held_out_fixture.name,
                train_f1=train_f1,
                held_out_correct=all_correct,
                held_out_tp=tp,
                held_out_fp=fp,
                held_out_fn=fn,
                weights=fold_weights.as_dict(),
                ablation_deltas=fold_deltas,
            )
            folds.append(fold)

            print(
                f"  Fold {i:>2d}  held_out={held_out_fixture.name:<20s}  "
                f"train_F1={train_f1:.3f}  "
                f"val: tp={tp} fp={fp} fn={fn}  {status}"
            )

    # ── Aggregate ────────────────────────────────────────────────────
    prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    held_out_f1 = (
        2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    )

    # Weight stability across folds
    weight_keys = list(folds[0].weights.keys())
    weight_means = {k: mean(f.weights[k] for f in folds) for k in weight_keys}
    weight_stdevs = {
        k: stdev(f.weights[k] for f in folds) if n > 1 else 0.0
        for k in weight_keys
    }

    result = LOOCVResult(
        n_fixtures=n,
        n_folds=n,
        held_out_f1=held_out_f1,
        held_out_tp=total_tp,
        held_out_fp=total_fp,
        held_out_fn=total_fn,
        full_set_f1=full_f1,
        weight_means=weight_means,
        weight_stdevs=weight_stdevs,
        full_set_weights=full_weights_dict,
        folds=folds,
    )

    # ── Print summary ────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print("LOOCV Summary")
    print(f"{'=' * 65}")
    print(f"  Full-set F1:    {full_f1:.3f}  (all {n} fixtures)")
    print(f"  Held-out F1:    {held_out_f1:.3f}  (aggregated across {n} folds)")
    print(f"  Held-out TP={total_tp}  FP={total_fp}  FN={total_fn}")
    folds_correct = sum(1 for f in folds if f.held_out_correct)
    print(f"  Folds correct:  {folds_correct}/{n}")
    print()
    print("Weight stability across folds:")
    print(f"  {'Signal':<30s}  {'Full-set':>8s}  {'Mean':>8s}  {'σ':>8s}  {'Δmax':>8s}")
    print(f"  {'-'*30}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}")
    for k in weight_keys:
        full_w = full_weights_dict[k]
        mean_w = weight_means[k]
        std_w = weight_stdevs[k]
        max_delta = max(abs(f.weights[k] - full_w) for f in folds)
        print(f"  {k:<30s}  {full_w:>8.4f}  {mean_w:>8.4f}  {std_w:>8.4f}  {max_delta:>8.4f}")

    return result


def _fmt_weights(w: dict[str, float]) -> str:
    """Short one-line weight summary."""
    parts = [f"{k[:3]}={v:.3f}" for k, v in sorted(w.items()) if v > 0.03]
    return "  ".join(parts)


# ── CLI ──────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LOOCV validation for drift weight calibration"
    )
    parser.add_argument(
        "--json",
        type=str,
        help="Save results to JSON file",
    )
    args = parser.parse_args()

    result = run_loocv()

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(asdict(result), indent=2, default=str),
            encoding="utf-8",
        )
        print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()

