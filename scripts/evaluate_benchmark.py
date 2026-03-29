"""Evaluate benchmark results: per-signal precision from ground-truth labels.

Usage:
  python scripts/evaluate_benchmark.py [--results-dir benchmark_results]

Reads all *_full.json files, loads ground_truth_labels.json for TP/FP
classifications, and prints a precision summary per signal.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "benchmark_results"
LABELS_FILE = RESULTS_DIR / "ground_truth_labels.json"


def _load_labels() -> dict[str, str]:
    """Load ground-truth labels into a lookup map."""
    if not LABELS_FILE.exists():
        print(f"No labels file at {LABELS_FILE} — run classify first.", file=sys.stderr)
        return {}
    data = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    labels: dict[str, str] = {}
    for entry in data:
        label = entry.get("label", "")
        key = entry.get("key")
        if key:
            labels[key] = label
        legacy_key = entry.get("legacy_key")
        if legacy_key:
            labels[legacy_key] = label
    return labels


def _finding_keys(repo: str, finding: dict) -> list[str]:
    """Return stable lookup keys ordered from strict to legacy.

    Key v2 is resilient to title collisions by including signal + location.
    Key v1 keeps compatibility with existing label sets.
    """
    title = str(finding.get("title", ""))
    signal = str(finding.get("signal", "unknown"))
    file_path = str(
        finding.get("file")
        or finding.get("file_path")
        or finding.get("path")
        or "?"
    )
    line = finding.get("line")
    line_text = str(line) if isinstance(line, int) else "?"
    key_v2 = f"{repo}::{signal}::{file_path}:{line_text}::{title}"
    key_v1 = f"{repo}::{title}"
    return [key_v2, key_v1]


def main() -> None:
    results_dir = RESULTS_DIR
    if len(sys.argv) > 2 and sys.argv[1] == "--results-dir":
        results_dir = Path(sys.argv[2])

    labels = _load_labels()

    # Aggregate findings from all full results
    stats: dict[str, dict[str, int]] = {}  # signal -> {tp, fp, disputed, unlabeled}
    total_findings = 0

    for full_file in sorted(results_dir.glob("*_full.json")):
        repo_name = full_file.stem.replace("_full", "")
        try:
            data = json.loads(full_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"  Skip {full_file.name}: parse error")
            continue

        findings = data.get("findings", [])
        total_findings += len(findings)

        for f in findings:
            signal = f.get("signal", "unknown")
            candidates = _finding_keys(repo_name, f)
            label = "UNLABELED"
            for key in candidates:
                if key in labels:
                    label = labels[key]
                    break

            if signal not in stats:
                stats[signal] = {"tp": 0, "fp": 0, "disputed": 0, "unlabeled": 0}

            bucket = label.lower() if label in ("TP", "FP", "DISPUTED") else "unlabeled"
            stats[signal][bucket] += 1

    # Print summary
    print(f"\nBenchmark Precision Report ({total_findings} total findings)")
    print(f"Labels loaded: {len(labels)}")
    hdr = (
        f"{'Signal':<28} {'TP':>4} {'FP':>4} {'Disp':>5} "
        f"{'Unlab':>6} {'Prec(strict)':>13} {'Prec(lenient)':>14}"
    )
    print(hdr)
    print("-" * 80)

    all_tp, all_fp, all_disp = 0, 0, 0
    for signal in sorted(stats):
        s = stats[signal]
        tp, fp, disp, unlab = s["tp"], s["fp"], s["disputed"], s["unlabeled"]
        all_tp += tp
        all_fp += fp
        all_disp += disp
        n = tp + fp + disp
        prec_strict = tp / n if n > 0 else 0.0
        prec_lenient = (tp + disp) / n if n > 0 else 0.0
        print(
            f"{signal:<28} {tp:>4} {fp:>4} {disp:>5} {unlab:>6} "
            f"{prec_strict:>12.1%} {prec_lenient:>13.1%}"
        )

    total_n = all_tp + all_fp + all_disp
    if total_n > 0:
        print("-" * 80)
        print(
            f"{'TOTAL':<28} {all_tp:>4} {all_fp:>4} {all_disp:>5} {'':>6} "
            f"{all_tp / total_n:>12.1%} {(all_tp + all_disp) / total_n:>13.1%}"
        )

    # Export updated analysis
    output = {
        "total_findings": total_findings,
        "labeled": len(labels),
        "precision_by_signal": {},
        "total": {
            "tp": all_tp,
            "fp": all_fp,
            "disputed": all_disp,
            "precision_strict": all_tp / total_n if total_n else 0,
            "precision_lenient": (all_tp + all_disp) / total_n if total_n else 0,
        },
    }
    for signal, s in sorted(stats.items()):
        n = s["tp"] + s["fp"] + s["disputed"]
        output["precision_by_signal"][signal] = {
            "sample": n,
            "tp": s["tp"],
            "fp": s["fp"],
            "disputed": s["disputed"],
            "precision_strict": s["tp"] / n if n else 0,
            "precision_lenient": (s["tp"] + s["disputed"]) / n if n else 0,
        }

    out_path = results_dir / "ground_truth_analysis.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nUpdated: {out_path}")


if __name__ == "__main__":
    main()
