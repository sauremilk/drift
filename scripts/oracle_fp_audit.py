#!/usr/bin/env python3
"""Oracle FP Audit — Run drift on curated high-quality repos and measure FP rates.

Reads the oracle repo manifest (benchmarks/oracle_repos.json), shallow-clones
each repo, runs ``drift analyze --json``, and compares findings against
ground-truth labels and FP budgets.

Usage:
    python scripts/oracle_fp_audit.py                          # All repos
    python scripts/oracle_fp_audit.py --repo requests httpx    # Specific repos
    python scripts/oracle_fp_audit.py --dry-run                # Parse manifest only
    python scripts/oracle_fp_audit.py --save-history           # Append to trend log
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "benchmarks" / "oracle_repos.json"
RESULTS_DIR = REPO_ROOT / "benchmark_results"
LABELS_PATH = RESULTS_DIR / "ground_truth_labels.json"
REPORT_PATH = RESULTS_DIR / "oracle_fp_report.json"
HISTORY_PATH = RESULTS_DIR / "oracle_fp_history.json"

# Valid FP taxonomy types (Schicht 3)
FP_TYPES = {"structural", "threshold", "scope", "semantic", "co_occurrence"}


def load_manifest() -> dict:
    """Load and validate the oracle repo manifest."""
    if not MANIFEST_PATH.exists():
        print(f"ERROR: Manifest not found: {MANIFEST_PATH}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if "repos" not in data:
        print("ERROR: Manifest missing 'repos' key", file=sys.stderr)
        sys.exit(1)
    return data


def load_labels() -> dict[str, dict]:
    """Load ground-truth labels into a lookup map (key → full entry)."""
    if not LABELS_PATH.exists():
        return {}
    data = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    labels: dict[str, dict] = {}
    for entry in data:
        key = entry.get("key", "")
        if key:
            labels[key] = entry
        legacy_key = entry.get("legacy_key")
        if legacy_key:
            labels[legacy_key] = entry
    return labels


def finding_keys(repo: str, finding: dict) -> list[str]:
    """Return stable lookup keys for a finding (v2 strict, v1 legacy)."""
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


def clone_repo(url: str, ref: str, dest: Path) -> bool:
    """Shallow-clone a repo. Returns True on success."""
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", ref, url, str(dest)],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"  WARN: Clone failed for {url}: {exc}", file=sys.stderr)
        return False


def analyze_repo(repo_path: Path) -> dict | None:
    """Run drift analyze on a repo and return the JSON result."""
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "drift", "analyze",
                "--repo", str(repo_path),
                "--format", "json",
                "--exit-zero",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as exc:
        print(f"  WARN: Analysis failed: {exc}", file=sys.stderr)
        return None


def classify_findings(
    repo_name: str, findings: list[dict], labels: dict[str, dict]
) -> dict[str, dict[str, int]]:
    """Classify findings using existing labels. Returns stats per signal."""
    stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "disputed": 0, "unlabeled": 0}
    )
    for f in findings:
        signal = f.get("signal", "unknown")
        candidates = finding_keys(repo_name, f)
        label_entry = None
        for key in candidates:
            if key in labels:
                label_entry = labels[key]
                break
        label = label_entry.get("label", "UNLABELED") if label_entry else "UNLABELED"
        bucket = label.lower() if label in ("TP", "FP", "Disputed") else "unlabeled"
        stats[signal][bucket] += 1
    return dict(stats)


def compute_fp_rates(stats: dict[str, dict[str, int]]) -> dict[str, float | None]:
    """Compute FP rate per signal from classified stats.

    FP rate = FP / (TP + FP + Disputed).  Returns None if no labeled findings.
    """
    rates: dict[str, float | None] = {}
    for signal, counts in stats.items():
        labeled = counts["tp"] + counts["fp"] + counts["disputed"]
        if labeled == 0:
            rates[signal] = None
        else:
            rates[signal] = counts["fp"] / labeled
    return rates


def check_budget(
    fp_rates: dict[str, float | None], budget: dict[str, float]
) -> list[dict]:
    """Compare measured FP rates against budget. Returns list of violations."""
    violations = []
    for signal, rate in fp_rates.items():
        if rate is None:
            continue
        limit = budget.get(signal)
        if limit is not None and rate > limit:
            violations.append({
                "signal": signal,
                "measured_fp_rate": round(rate, 4),
                "budget": limit,
                "over_by": round(rate - limit, 4),
            })
    return violations


def run_audit(
    repos: list[dict],
    labels: dict[str, dict],
    budget: dict[str, float],
    *,
    dry_run: bool = False,
) -> dict:
    """Run the full FP audit. Returns the report dict."""
    try:
        from drift import __version__ as drift_version
    except ImportError:
        drift_version = "unknown"

    report: dict = {
        "_metadata": {
            "drift_version": drift_version,
            "generated_at": datetime.now(UTC).isoformat(),
            "manifest": str(MANIFEST_PATH),
            "dry_run": dry_run,
        },
        "repos": {},
        "aggregate": {},
        "budget_violations": [],
    }

    if dry_run:
        print(f"DRY RUN: Would analyze {len(repos)} repos:")
        for r in repos:
            print(f"  - {r['name']} ({r['url']} @ {r['ref']})")
        print(f"\nFP Budget ({len(budget)} signals):")
        for sig, limit in sorted(budget.items()):
            print(f"  {sig:<30s} {limit:.0%}")
        report["_metadata"]["status"] = "dry_run"
        return report

    aggregate_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "disputed": 0, "unlabeled": 0, "total": 0}
    )

    for repo_info in repos:
        name = repo_info["name"]
        url = repo_info["url"]
        ref = repo_info["ref"]
        print(f"\n{'=' * 60}")
        print(f"Oracle Repo: {name} ({url} @ {ref})")
        print(f"{'=' * 60}")

        with tempfile.TemporaryDirectory(prefix=f"drift_oracle_{name}_") as tmp:
            clone_path = Path(tmp) / name
            if not clone_repo(url, ref, clone_path):
                report["repos"][name] = {"status": "clone_failed"}
                continue

            result = analyze_repo(clone_path)
            if result is None:
                report["repos"][name] = {"status": "analysis_failed"}
                continue

        findings = result.get("findings", [])
        print(f"  Findings: {len(findings)}")

        stats = classify_findings(name, findings, labels)
        fp_rates = compute_fp_rates(stats)

        # Aggregate
        for signal, counts in stats.items():
            for k, v in counts.items():
                aggregate_stats[signal][k] += v
            aggregate_stats[signal]["total"] += sum(counts.values())

        # Per-repo report
        report["repos"][name] = {
            "status": "ok",
            "findings_count": len(findings),
            "stats_by_signal": {
                sig: {**counts, "fp_rate": fp_rates.get(sig)}
                for sig, counts in stats.items()
            },
        }

        # Save full results for future triage
        full_out = RESULTS_DIR / f"{name}_full.json"
        full_out.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  Saved: {full_out.name}")

    # Aggregate FP rates
    agg_fp_rates = compute_fp_rates(dict(aggregate_stats))
    violations = check_budget(agg_fp_rates, budget)

    report["aggregate"] = {
        sig: {
            **dict(counts),
            "fp_rate": agg_fp_rates.get(sig),
            "budget": budget.get(sig),
        }
        for sig, counts in aggregate_stats.items()
    }
    report["budget_violations"] = violations

    # Print summary
    print(f"\n{'=' * 60}")
    print("AGGREGATE FP REPORT")
    print(f"{'=' * 60}")
    hdr = (
        f"{'Signal':<30s} {'TP':>4} {'FP':>4} {'Disp':>5} "
        f"{'Unlab':>6} {'FP%':>6} {'Budget':>7} {'Status':>8}"
    )
    print(hdr)
    print("-" * 80)

    for signal in sorted(aggregate_stats):
        s = aggregate_stats[signal]
        rate = agg_fp_rates.get(signal)
        limit = budget.get(signal)
        rate_str = f"{rate:.1%}" if rate is not None else "n/a"
        limit_str = f"{limit:.0%}" if limit is not None else "n/a"
        is_over = rate is not None and limit is not None and rate > limit
        status = "OVER!" if is_over else "ok"
        print(
            f"{signal:<30s} {s['tp']:>4} {s['fp']:>4} {s['disputed']:>5} "
            f"{s['unlabeled']:>6} {rate_str:>6} {limit_str:>7} {status:>8}"
        )

    if violations:
        print(f"\nWARNING: {len(violations)} signal(s) over FP budget:")
        for v in violations:
            print(
                f"  - {v['signal']}: {v['measured_fp_rate']:.1%} "
                f"(budget: {v['budget']:.0%}, over by {v['over_by']:.1%})"
            )
    else:
        print("\nAll signals within FP budget.")

    return report


def append_history(report: dict) -> None:
    """Append a summary entry to the FP history trend log."""
    history: list[dict] = []
    if HISTORY_PATH.exists():
        try:
            history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = []

    entry = {
        "timestamp": report["_metadata"]["generated_at"],
        "drift_version": report["_metadata"]["drift_version"],
        "fp_rates": {
            sig: data.get("fp_rate")
            for sig, data in report.get("aggregate", {}).items()
        },
        "violations": len(report.get("budget_violations", [])),
    }
    history.append(entry)

    HISTORY_PATH.write_text(
        json.dumps(history, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"History updated: {HISTORY_PATH.name} ({len(history)} entries)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Oracle FP Audit — measure FP rates on curated repos",
    )
    parser.add_argument(
        "--repo",
        nargs="+",
        help="Only audit specific repos from the manifest (by name)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse manifest and print plan without cloning/analyzing",
    )
    parser.add_argument(
        "--save-history",
        action="store_true",
        help="Append results to oracle_fp_history.json trend log",
    )
    args = parser.parse_args()

    manifest = load_manifest()
    labels = load_labels()
    budget = manifest.get("fp_budget", {})
    # Remove non-signal keys from budget
    budget = {k: v for k, v in budget.items() if not k.startswith("_")}

    repos = manifest["repos"]
    if args.repo:
        names = set(args.repo)
        repos = [r for r in repos if r["name"] in names]
        missing = names - {r["name"] for r in repos}
        if missing:
            print(
                f"WARN: Repos not in manifest: {', '.join(sorted(missing))}",
                file=sys.stderr,
            )

    if not repos:
        print("No repos to audit.", file=sys.stderr)
        sys.exit(1)

    report = run_audit(repos, labels, budget, dry_run=args.dry_run)

    # Save report
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nReport saved: {REPORT_PATH}")

    if args.save_history and not args.dry_run:
        append_history(report)


if __name__ == "__main__":
    main()
