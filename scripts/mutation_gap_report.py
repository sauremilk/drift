#!/usr/bin/env python3
"""H3 instrument: Mutation-Gap-Report — compares real-world findings against mutation suite.

Reads all *_full.json artifacts in benchmark_results/, clusters findings by
(signal, title-pattern), and checks coverage against the 25 known mutation
patterns in mutation_benchmark.json.

Usage:
    python scripts/mutation_gap_report.py
    python scripts/mutation_gap_report.py --min-cluster 3

Outputs:
    benchmark_results/mutation_gap_report.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "benchmark_results"
MANIFEST_FILE = RESULTS_DIR / "mutation_benchmark.json"


def _load_manifest() -> list[dict]:
    """Load mutation patterns from manifest."""
    if not MANIFEST_FILE.exists():
        sys.exit(f"Mutation manifest not found: {MANIFEST_FILE}")
    data = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    return data.get("manifest", data).get("mutations", [])


def _load_real_findings() -> list[dict]:
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


def _normalize_title(title: str) -> str:
    """Reduce a finding title to a canonical pattern descriptor."""
    # Strip file paths, numbers, quotes
    t = re.sub(r"[`'\"].*?[`'\"]", "<name>", title)
    t = re.sub(r"\b\d+(\.\d+)?\b", "<n>", t)
    t = re.sub(r"\S+\.\w{1,4}(?=[:\s]|$)", "<file>", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def _cluster_findings(findings: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """Cluster findings by (signal, normalized title) -> list of findings."""
    clusters: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for f in findings:
        sig = f.get("signal", "unknown")
        title = f.get("title", "")
        pattern = _normalize_title(title)
        clusters[sig][pattern].append(f)
    return clusters


def _match_mutation_to_cluster(
    mutation: dict,
    signal_clusters: dict[str, list[dict]],
) -> bool:
    """Check if a mutation pattern has a matching real-world cluster."""
    rationale = mutation.get("rationale", "").lower()
    _mut_signal = mutation.get("signal", "")

    # Keywords from rationale
    keywords = set(re.findall(r"\b[a-z_]{4,}\b", rationale))

    for pattern, cluster_items in signal_clusters.items():
        # Check keyword overlap between mutation rationale and cluster pattern
        pattern_words = set(re.findall(r"\b[a-z_]{4,}\b", pattern))
        if keywords & pattern_words:
            return True
        # Check against raw titles in the cluster
        for item in cluster_items:
            raw_title = item.get("title", "").lower()
            title_words = set(re.findall(r"\b[a-z_]{4,}\b", raw_title))
            if len(keywords & title_words) >= 2:
                return True

    return False


def gap_report(min_cluster: int = 2) -> None:
    """Generate mutation gap report."""
    mutations = _load_manifest()
    findings = _load_real_findings()

    if not findings:
        print("No real-world findings found in benchmark_results/*_full.json", file=sys.stderr)
        sys.exit(1)

    clusters = _cluster_findings(findings)

    # Filter to significant clusters
    significant: dict[str, dict[str, int]] = {}
    for sig, patterns in clusters.items():
        for pattern, items in patterns.items():
            if len(items) >= min_cluster:
                significant.setdefault(sig, {})[pattern] = len(items)

    # Check mutation coverage
    covered: list[dict] = []
    uncovered: list[dict] = []

    for mut in mutations:
        sig = mut.get("signal", "")
        sig_clusters = clusters.get(sig, {})
        if _match_mutation_to_cluster(mut, sig_clusters):
            covered.append(mut)
        else:
            uncovered.append(mut)

    # Uncovered real-world patterns (clusters with no mutation match)
    uncovered_real: list[dict] = []
    mutation_signals = {m["signal"] for m in mutations}
    for sig, patterns in significant.items():
        if sig not in mutation_signals:
            for pattern, count in patterns.items():
                uncovered_real.append({"signal": sig, "pattern": pattern, "count": count})
            continue
        sig_mutations = [m for m in mutations if m["signal"] == sig]
        for pattern, count in patterns.items():
            matched = False
            for m in sig_mutations:
                if _match_mutation_to_cluster(m, {pattern: clusters[sig][pattern]}):
                    matched = True
                    break
            if not matched:
                uncovered_real.append({"signal": sig, "pattern": pattern, "count": count})

    total = len(mutations)
    covered_pct = len(covered) / total if total else 0.0

    # Print
    print("=" * 72)
    print("MUTATION GAP REPORT (H3)")
    print("=" * 72)
    print(f"  Mutations in suite:    {total}")
    print(f"  Covered by real data:  {len(covered)} ({covered_pct:.0%})")
    print(f"  Uncovered:             {len(uncovered)}")
    print(f"  Real findings loaded:  {len(findings)}")
    print(f"  Significant clusters:  {sum(len(v) for v in significant.values())} "
          f"(min_cluster={min_cluster})")
    print()

    if uncovered:
        print("  Uncovered mutation patterns:")
        for m in uncovered:
            print(f"    - {m['id']} ({m['signal']}): {m.get('rationale', '')[:80]}")

    if uncovered_real:
        print(f"\n  Real-world clusters without mutation counterpart ({len(uncovered_real)}):")
        for ur in sorted(uncovered_real, key=lambda x: -x["count"])[:20]:
            print(f"    - [{ur['signal']}] {ur['pattern'][:60]}  (n={ur['count']})")

    gate = covered_pct >= 0.80
    print(f"\n  H3 Gate (coverage ≥ 80%): {'PASS' if gate else 'FAIL'}")

    # Write artifact
    artifact = {
        "total_mutations": total,
        "covered_count": len(covered),
        "uncovered_count": len(uncovered),
        "coverage_pct": round(covered_pct, 4),
        "real_findings_loaded": len(findings),
        "significant_clusters": sum(len(v) for v in significant.values()),
        "min_cluster_threshold": min_cluster,
        "covered_patterns": [{"id": m["id"], "signal": m["signal"]} for m in covered],
        "uncovered_patterns": [
            {"id": m["id"], "signal": m["signal"], "rationale": m.get("rationale", "")}
            for m in uncovered
        ],
        "uncovered_real_world_clusters": uncovered_real[:50],
        "h3_gate_pass": gate,
    }
    out_path = RESULTS_DIR / "mutation_gap_report.json"
    out_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Artifact written to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="H3: Mutation-suite gap analysis")
    parser.add_argument(
        "--min-cluster", type=int, default=2,
        help="Minimum cluster size to count as significant (default: 2)",
    )
    args = parser.parse_args()
    gap_report(min_cluster=args.min_cluster)


if __name__ == "__main__":
    main()
