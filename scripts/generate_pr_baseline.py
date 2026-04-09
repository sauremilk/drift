#!/usr/bin/env python3
"""Generate Precision/Recall baseline JSON for the KPI roadmap.

Runs all ground-truth fixtures through the current signal model and
produces a versioned baseline artifact with per-signal P/R/F1 metrics,
fixture coverage analysis, and mutation benchmark gap analysis.

Usage:
    python scripts/generate_pr_baseline.py
    python scripts/generate_pr_baseline.py \
        --output benchmark_results/v2.7.0_precision_recall_baseline.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from tests.fixtures.ground_truth import (  # noqa: E402
    ALL_FIXTURES,
    GroundTruthFixture,
)

from drift import __version__  # noqa: E402
from drift.config import SignalWeights  # noqa: E402
from drift.models import SignalType  # noqa: E402
from drift.precision import (  # noqa: E402
    PrecisionRecallReport,
    ensure_signals_registered,
    evaluate_fixtures,
)


def _fixture_coverage_analysis(
    fixtures: list[GroundTruthFixture],
) -> dict[str, dict]:
    """Analyze fixture coverage per signal."""
    weights = SignalWeights()
    weight_dict = weights.as_dict()

    # All scoring-active signals (weight > 0)
    scoring_active = sorted(
        [st for st in SignalType if weight_dict.get(str(st), 0.0) > 0.0],
        key=lambda s: s.value,
    )
    report_only = sorted(
        [st for st in SignalType if weight_dict.get(str(st), 0.0) == 0.0],
        key=lambda s: s.value,
    )

    by_signal: dict[SignalType, list[GroundTruthFixture]] = defaultdict(list)
    for f in fixtures:
        for exp in f.expected:
            by_signal[exp.signal_type].append(f)

    coverage = {}
    for st in SignalType:
        fxts = by_signal.get(st, [])
        tp_count = sum(
            1 for f in fxts for e in f.expected if e.signal_type == st and e.should_detect
        )
        tn_count = sum(
            1 for f in fxts for e in f.expected if e.signal_type == st and not e.should_detect
        )
        unique_count = len({f.name for f in fxts})
        coverage[st.value] = {
            "total_fixtures": unique_count,
            "tp_expectations": tp_count,
            "tn_expectations": tn_count,
            "meets_minimum_5": unique_count >= 5,
            "scoring_active": weight_dict.get(str(st), 0.0) > 0.0,
            "weight": weight_dict.get(str(st), 0.0),
        }

    scoring_with_min5 = sum(
        1 for st in scoring_active if coverage[st.value]["meets_minimum_5"]
    )
    scoring_below_min5 = [
        st.value for st in scoring_active if not coverage[st.value]["meets_minimum_5"]
    ]
    return {
        "per_signal": coverage,
        "summary": {
            "total_signals": len(list(SignalType)),
            "scoring_active_count": len(scoring_active),
            "report_only_count": len(report_only),
            "scoring_signals_with_min5_fixtures": scoring_with_min5,
            "scoring_signals_below_min5": scoring_below_min5,
            "total_fixtures": len(fixtures),
        },
    }


def _mutation_gap_analysis() -> dict:
    """Identify scoring-active signals missing from the mutation benchmark."""
    weights = SignalWeights()
    weight_dict = weights.as_dict()

    scoring_active = sorted(
        [st for st in SignalType if weight_dict.get(str(st), 0.0) > 0.0],
        key=lambda s: s.value,
    )

    # Load existing mutation benchmark results
    mutation_path = ROOT / "benchmark_results" / "mutation_benchmark.json"
    covered_signals: set[str] = set()
    mutation_recall = None
    total_injected = 0
    total_detected = 0

    if mutation_path.exists():
        with open(mutation_path) as f:
            data = json.load(f)
        detection = data.get("detection", {})
        covered_signals = set(detection.keys())
        total_injected = data.get("total_injected", 0)
        total_detected = data.get("total_detected", 0)
        mutation_recall = data.get("overall_recall")

    missing = []
    for st in scoring_active:
        if str(st) not in covered_signals and st.value not in covered_signals:
            missing.append(st.value)

    return {
        "mutation_benchmark_recall": mutation_recall,
        "total_injected": total_injected,
        "total_detected": total_detected,
        "signals_covered": sorted(covered_signals),
        "scoring_signals_missing_mutations": missing,
        "coverage_ratio": f"{len(covered_signals)}/{len(scoring_active)} scoring-active",
    }


def main() -> None:
    """Generate baseline artifact."""
    parser = argparse.ArgumentParser(description="Generate P/R baseline JSON")
    parser.add_argument(
        "--output",
        default=str(ROOT / "benchmark_results" / "v2.7.0_precision_recall_baseline.json"),
        help="Output path for baseline JSON",
    )
    args = parser.parse_args()

    ensure_signals_registered()

    print("Running all ground-truth fixtures...")
    with tempfile.TemporaryDirectory() as tmp:
        report, warnings = evaluate_fixtures(ALL_FIXTURES, Path(tmp))

    print(report.summary())
    print()

    # Fixture coverage
    print("Analyzing fixture coverage...")
    fixture_coverage = _fixture_coverage_analysis(ALL_FIXTURES)

    # Mutation gap
    print("Analyzing mutation benchmark gaps...")
    mutation_gaps = _mutation_gap_analysis()

    # Build baseline artifact
    baseline = {
        "_metadata": {
            "drift_version": __version__,
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "artifact_type": "precision_recall_baseline",
            "purpose": "KPI Roadmap v2.7 — belastbare Baseline auf aktuellem 15-Signal-Modell",
            "fixture_count": len(ALL_FIXTURES),
            "methodology": (
                "Automated evaluation of all ground-truth fixtures in "
                "tests/fixtures/ground_truth.py via drift.precision.evaluate_fixtures(). "
                "Per-signal and aggregate P/R/F1 computed. "
                "This replaces the historical v0.5 baseline (6 scoring signals) "
                "with a current-model evaluation (15 scoring-active signals)."
            ),
        },
        "precision_recall": report.to_dict(),
        "fixture_coverage": fixture_coverage,
        "mutation_benchmark_gaps": mutation_gaps,
        "ci_gate_recommendations": _compute_gate_recommendations(report),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(baseline, f, indent=2)
    print(f"\nBaseline written to: {output_path}")

    # Print summary
    _print_summary(baseline)


def _compute_gate_recommendations(report: PrecisionRecallReport) -> dict:
    """Compute recommended CI gate thresholds based on current baseline."""
    gates = {}
    for sig in report.all_signals:
        # Gate = current precision - 2pp (floor at 0.40)
        current_prec = report.precision(sig)
        obs = report.tp[sig] + report.fp[sig]
        gate = max(0.40, round(current_prec - 0.02, 2)) if obs >= 3 else None
        gates[sig.value] = {
            "current_precision": round(current_prec, 4),
            "current_recall": round(report.recall(sig), 4),
            "current_f1": round(report.f1(sig), 4),
            "observations_tp_fp": obs,
            "recommended_precision_gate": gate,
            "note": "Insufficient observations (<3)" if gate is None else "Baseline - 2pp",
        }
    return {
        "per_signal": gates,
        "aggregate_f1_gate": max(0.40, round(report.aggregate_f1() - 0.02, 2)),
    }


def _print_summary(baseline: dict) -> None:
    """Print human-readable summary."""
    pr = baseline["precision_recall"]
    cov = baseline["fixture_coverage"]["summary"]
    mut = baseline["mutation_benchmark_gaps"]

    print("\n" + "=" * 70)
    print("KPI BASELINE SUMMARY (v2.7)")
    print("=" * 70)

    print(f"\nDrift version:        {baseline['_metadata']['drift_version']}")
    print(f"Total fixtures:       {cov['total_fixtures']}")
    print(f"Scoring-active:       {cov['scoring_active_count']} signals")
    print(f"Report-only:          {cov['report_only_count']} signals")
    print(f"Aggregate F1:         {pr['aggregate_f1']:.4f}")

    print("\nFixture coverage:")
    n5 = cov['scoring_signals_with_min5_fixtures']
    sa = cov['scoring_active_count']
    print(f"  ≥5 fixtures:        {n5}/{sa}")
    if cov["scoring_signals_below_min5"]:
        print(f"  Below minimum:      {', '.join(cov['scoring_signals_below_min5'])}")

    print("\nMutation benchmark:")
    print(f"  Recall:             {mut['mutation_benchmark_recall']}")
    print(f"  Coverage:           {mut['coverage_ratio']}")
    if mut["scoring_signals_missing_mutations"]:
        print(f"  Missing:            {', '.join(mut['scoring_signals_missing_mutations'])}")

    print("\nPer-signal precision (scoring-active only):")
    for sig_name, data in sorted(pr["signals"].items()):
        fc = baseline["fixture_coverage"]["per_signal"].get(sig_name, {})
        if fc.get("scoring_active", False):
            print(
                f"  {sig_name:<35s} P={data['precision']:.2f} R={data['recall']:.2f} "
                f"F1={data['f1']:.2f} (TP={data['tp']} FP={data['fp']} "
                f"FN={data['fn']} TN={data['tn']})"
            )

    print("\nPer-signal precision (report-only):")
    for sig_name, data in sorted(pr["signals"].items()):
        fc = baseline["fixture_coverage"]["per_signal"].get(sig_name, {})
        if not fc.get("scoring_active", True):
            print(
                f"  {sig_name:<35s} P={data['precision']:.2f} R={data['recall']:.2f} "
                f"F1={data['f1']:.2f} (TP={data['tp']} FP={data['fp']} "
                f"FN={data['fn']} TN={data['tn']})"
            )

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
