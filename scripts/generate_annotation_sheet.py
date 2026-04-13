#!/usr/bin/env python3
"""Generate blind annotation sheets for independent precision validation.

Creates a randomised sample of findings WITHOUT scores, so that human
reviewers classify TP/FP/Disputed based solely on the source-code context.
This breaks the circular validation where the tool's own score determines
ground truth.

Usage:
    python scripts/generate_annotation_sheet.py [--n 50] [--seed 42]
    python scripts/generate_annotation_sheet.py --evaluate annotated.json
    python scripts/generate_annotation_sheet.py --compare rater1.json rater2.json

Outputs:
    benchmark_results/annotation_sheet.json   — for reviewers (no scores)
    benchmark_results/annotation_key.json     — answer key (with scores, hidden)
    benchmark_results/annotation_agreement.json — inter-rater agreement (κ)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "benchmark_results"


def _load_all_findings() -> list[dict]:
    """Load findings from all *_full.json benchmark files."""
    findings: list[dict] = []
    for full_file in sorted(RESULTS_DIR.glob("*_full.json")):
        repo = full_file.stem.replace("_full", "")
        try:
            data = json.loads(full_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        for f in data.get("findings", []):
            f["_repo"] = repo
            findings.append(f)
    return findings


def _uniform_stratified_sample(
    findings: list[dict], n: int, rng: random.Random
) -> list[dict]:
    """Uniform-random stratified sample (equal per signal), NOT score-weighted."""
    by_signal: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        by_signal[f.get("signal", "unknown")].append(f)

    per_signal = max(1, n // len(by_signal)) if by_signal else n
    sample: list[dict] = []

    for _sig, items in sorted(by_signal.items()):
        rng.shuffle(items)
        sample.extend(items[:per_signal])

    # Fill remaining quota from all findings
    remaining = n - len(sample)
    if remaining > 0:
        pool = [f for f in findings if f not in sample]
        rng.shuffle(pool)
        sample.extend(pool[:remaining])

    rng.shuffle(sample)
    return sample[:n]


def generate(n: int = 50, seed: int = 42) -> None:
    """Generate annotation sheet and answer key."""
    findings = _load_all_findings()
    if not findings:
        print("No findings found in benchmark_results/*_full.json", file=sys.stderr)
        sys.exit(1)

    rng = random.Random(seed)
    sample = _uniform_stratified_sample(findings, n, rng)

    # Annotation sheet: what reviewers see (NO score, NO severity)
    sheet: list[dict] = []
    key: list[dict] = []

    for idx, f in enumerate(sample, 1):
        item_id = f"F{idx:03d}"

        sheet.append({
            "id": item_id,
            "signal": f.get("signal", ""),
            "repo": f.get("_repo", ""),
            "title": f.get("title", ""),
            "description": f.get("description", ""),
            "file": f.get("file", f.get("affected_file", "")),
            "label": "",  # reviewer fills this: TP / FP / Disputed
            "reviewer_notes": "",  # free-text justification
        })

        key.append({
            "id": item_id,
            "signal": f.get("signal", ""),
            "repo": f.get("_repo", ""),
            "title": f.get("title", ""),
            "score": f.get("score", 0),
            "severity": f.get("severity", ""),
        })

    sheet_path = RESULTS_DIR / "annotation_sheet.json"
    key_path = RESULTS_DIR / "annotation_key.json"

    sheet_path.write_text(json.dumps(sheet, indent=2, ensure_ascii=False), encoding="utf-8")
    key_path.write_text(json.dumps(key, indent=2, ensure_ascii=False), encoding="utf-8")

    # Signal distribution in sample
    dist: dict[str, int] = defaultdict(int)
    for f in sample:
        dist[f.get("signal", "unknown")] += 1

    print(f"Generated annotation sheet: {sheet_path}")
    print(f"Answer key (do NOT share with reviewers): {key_path}")
    print(f"\nSample: {len(sample)} findings from {len(set(f['_repo'] for f in sample))} repos")
    print(f"Sampling: uniform-random stratified (seed={seed})")
    print("\nSignal distribution:")
    for sig, count in sorted(dist.items()):
        print(f"  {sig:<30s} {count:>3d}")

    print("\n--- Instructions for reviewers ---")
    print("1. Open annotation_sheet.json")
    print("2. For each finding, inspect the source code at the given file path")
    print("3. Set 'label' to TP, FP, or Disputed")
    print("4. Add a brief justification in 'reviewer_notes'")
    print("5. Do NOT look at scores or the answer key")


def evaluate(annotated_path: str) -> None:
    """Compute inter-rater agreement and precision from annotated sheet."""
    data = json.loads(Path(annotated_path).read_text(encoding="utf-8"))

    by_signal: dict[str, dict[str, int]] = defaultdict(
        lambda: {"TP": 0, "FP": 0, "Disputed": 0, "unlabeled": 0, "total": 0}
    )
    total_tp = total_fp = total_disp = total_n = 0

    for item in data:
        sig = item.get("signal", "unknown")
        label = item.get("label", "").strip().upper()
        if label in ("TP", "FP", "DISPUTED"):
            if label == "DISPUTED":
                label = "Disputed"
            by_signal[sig][label] += 1
            by_signal[sig]["total"] += 1
            if label == "TP":
                total_tp += 1
            elif label == "FP":
                total_fp += 1
            else:
                total_disp += 1
            total_n += 1
        else:
            by_signal[sig]["unlabeled"] += 1

    print("=" * 72)
    print("INDEPENDENT ANNOTATION RESULTS")
    print("=" * 72)
    hdr = (
        f"{'Signal':<28s} {'n':>4s} {'TP':>4s} {'FP':>4s} {'Disp':>5s} "
        f"{'Prec(strict)':>13s} {'Prec(lenient)':>14s}"
    )
    print(hdr)
    print("-" * 72)

    for sig in sorted(by_signal):
        s = by_signal[sig]
        n = s["total"]
        tp, fp, disp = s["TP"], s["FP"], s["Disputed"]
        if n > 0:
            ps = tp / n
            pl = (tp + disp) / n
            print(
                f"{sig:<28s} {n:>4d} {tp:>4d} {fp:>4d} {disp:>5d} "
                f"{ps:>12.1%} {pl:>13.1%}"
            )

    if total_n > 0:
        print("-" * 72)
        ps = total_tp / total_n
        pl = (total_tp + total_disp) / total_n
        print(
            f"{'TOTAL':<28s} {total_n:>4d} {total_tp:>4d} {total_fp:>4d} "
            f"{total_disp:>5d} {ps:>12.1%} {pl:>13.1%}"
        )
    else:
        print("\nNo labeled findings found. Did the reviewer fill in the 'label' field?")


def _cohens_kappa(labels_a: list[str], labels_b: list[str]) -> float:
    """Compute Cohen's kappa for two lists of categorical labels."""
    if len(labels_a) != len(labels_b):
        raise ValueError("Rater label lists must have equal length")
    n = len(labels_a)
    if n == 0:
        return float("nan")
    categories = sorted(set(labels_a) | set(labels_b))
    # Build confusion matrix
    matrix: dict[str, dict[str, int]] = {c: {d: 0 for d in categories} for c in categories}
    for a, b in zip(labels_a, labels_b, strict=False):
        matrix[a][b] += 1
    # Observed agreement
    p_o = sum(matrix[c][c] for c in categories) / n
    # Expected agreement by chance
    p_e = 0.0
    for c in categories:
        row_sum = sum(matrix[c][d] for d in categories) / n
        col_sum = sum(matrix[d][c] for d in categories) / n
        p_e += row_sum * col_sum
    if p_e >= 1.0:
        return 1.0 if p_o >= 1.0 else 0.0
    return (p_o - p_e) / (1.0 - p_e)


def compare(path_a: str, path_b: str) -> None:
    """Compare two annotated sheets and compute Cohen's kappa (H1 instrument)."""
    data_a = json.loads(Path(path_a).read_text(encoding="utf-8"))
    data_b = json.loads(Path(path_b).read_text(encoding="utf-8"))

    # Index by finding id
    map_a = {item["id"]: item.get("label", "").strip().upper() for item in data_a}
    map_b = {item["id"]: item.get("label", "").strip().upper() for item in data_b}

    valid_labels = {"TP", "FP", "DISPUTED"}
    common_ids = sorted(set(map_a) & set(map_b))
    # Keep only items where both raters provided a valid label
    paired: list[tuple[str, str, str]] = []
    for fid in common_ids:
        la = map_a[fid]
        lb = map_b[fid]
        if la in valid_labels and lb in valid_labels:
            paired.append((fid, la, lb))

    if not paired:
        print("No commonly-labeled findings found between the two files.", file=sys.stderr)
        sys.exit(1)

    labels_a = [la for _, la, _ in paired]
    labels_b = [lb for _, _, lb in paired]

    # Overall kappa
    kappa_overall = _cohens_kappa(labels_a, labels_b)

    # Per-signal kappa
    by_signal: dict[str, list[tuple[str, str]]] = defaultdict(list)
    signal_map_a = {item["id"]: item.get("signal", "unknown") for item in data_a}
    for fid, la, lb in paired:
        sig = signal_map_a.get(fid, "unknown")
        by_signal[sig].append((la, lb))

    kappa_per_signal: dict[str, float | None] = {}
    for sig in sorted(by_signal):
        pairs = by_signal[sig]
        if len(pairs) < 3:
            kappa_per_signal[sig] = None
            continue
        sig_a = [p[0] for p in pairs]
        sig_b = [p[1] for p in pairs]
        kappa_per_signal[sig] = _cohens_kappa(sig_a, sig_b)

    # Agreement breakdown
    agree = sum(1 for la, lb in zip(labels_a, labels_b, strict=False) if la == lb)
    agreement_pct = agree / len(paired)

    # Contested items (different labels)
    contested = [
        {"id": fid, "rater_a": la, "rater_b": lb}
        for fid, la, lb in paired if la != lb
    ]

    # Print summary
    print("=" * 72)
    print("INTER-RATER AGREEMENT (Cohen's κ)")
    print("=" * 72)
    print(f"  Paired items:     {len(paired)}")
    print(f"  Agreement:        {agree}/{len(paired)} ({agreement_pct:.1%})")
    print(f"  Cohen's κ:        {kappa_overall:.3f}")
    print()
    _kappa_interp = (
        "almost perfect" if kappa_overall >= 0.81 else
        "substantial" if kappa_overall >= 0.61 else
        "moderate" if kappa_overall >= 0.41 else
        "fair" if kappa_overall >= 0.21 else
        "slight" if kappa_overall >= 0.0 else
        "poor"
    )
    print(f"  Interpretation:   {_kappa_interp} (Landis & Koch)")
    print()
    print(f"  {'Signal':<28s} {'n':>4s} {'κ':>8s}")
    print(f"  {'-'*28} {'----':>4s} {'--------':>8s}")
    for sig in sorted(kappa_per_signal):
        k = kappa_per_signal[sig]
        n = len(by_signal[sig])
        if k is None:
            print(f"  {sig:<28s} {n:>4d} {'n<3':>8s}")
        else:
            print(f"  {sig:<28s} {n:>4d} {k:>8.3f}")

    if contested:
        print(f"\n  Contested items ({len(contested)}):")
        for c in contested[:20]:
            print(f"    {c['id']}: rater_a={c['rater_a']}  rater_b={c['rater_b']}")
        if len(contested) > 20:
            print(f"    ... and {len(contested) - 20} more")

    # H1 gate
    gate = kappa_overall >= 0.60
    print(f"\n  H1 Gate (κ ≥ 0.60): {'PASS' if gate else 'FAIL'}")

    # Write artifact
    artifact = {
        "n_paired": len(paired),
        "agreement_pct": round(agreement_pct, 4),
        "kappa_overall": round(kappa_overall, 4),
        "kappa_interpretation": _kappa_interp,
        "kappa_per_signal": {
            sig: round(k, 4) if k is not None else None
            for sig, k in sorted(kappa_per_signal.items())
        },
        "contested_items": contested,
        "h1_gate_pass": gate,
        "rater_a": str(Path(path_a).name),
        "rater_b": str(Path(path_b).name),
    }
    out_path = RESULTS_DIR / "annotation_agreement.json"
    out_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Artifact written to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Blind annotation tooling")
    parser.add_argument("--n", type=int, default=50, help="Sample size (default: 50)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument(
        "--evaluate", type=str, default=None,
        help="Path to annotated JSON file for evaluation",
    )
    parser.add_argument(
        "--compare", nargs=2, metavar=("RATER_A", "RATER_B"),
        help="Compare two annotated sheets and compute Cohen's κ",
    )
    args = parser.parse_args()

    if args.compare:
        compare(args.compare[0], args.compare[1])
    elif args.evaluate:
        evaluate(args.evaluate)
    else:
        generate(n=args.n, seed=args.seed)


if __name__ == "__main__":
    main()
