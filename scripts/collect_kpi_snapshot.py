#!/usr/bin/env python3
"""Collect a KPI snapshot and append it to kpi_trend.jsonl.

Gathers quality metrics from three sources:
  1. Precision/Recall evaluation (ground-truth fixtures)
  2. Mutation benchmark results (if JSON exists)
  3. Self-analysis finding count (if JSON exists)

Usage:
    python scripts/collect_kpi_snapshot.py [--output benchmark_results/kpi_snapshot.json]

The snapshot is also appended as a single line to benchmark_results/kpi_trend.jsonl.
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TREND_FILE = REPO_ROOT / "benchmark_results" / "kpi_trend.jsonl"
MUTATION_FILE = REPO_ROOT / "benchmark_results" / "mutation_benchmark.json"


def _get_version() -> str:
    """Read the current drift version from pyproject.toml."""
    pyproject = REPO_ROOT / "pyproject.toml"
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "unknown"


def _get_git_sha() -> str:
    """Return short git SHA of HEAD."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def collect_precision_recall() -> dict:
    """Run ground-truth evaluation and return per-signal + aggregate metrics."""
    # Import locally to avoid top-level dependency issues in CI
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    sys.path.insert(0, str(REPO_ROOT / "src"))

    from drift.precision import ensure_signals_registered, evaluate_fixtures
    from fixtures.ground_truth import ALL_FIXTURES

    ensure_signals_registered()

    with tempfile.TemporaryDirectory() as tmp:
        report, _warnings = evaluate_fixtures(ALL_FIXTURES, Path(tmp))

    data = report.to_dict()
    # Flatten per-signal to just P/R/F1 for trend tracking
    per_signal = {}
    for sig_name, sig_data in data["signals"].items():
        per_signal[sig_name] = {
            "precision": sig_data["precision"],
            "recall": sig_data["recall"],
            "f1": sig_data["f1"],
            "tp": sig_data["tp"],
            "fp": sig_data["fp"],
            "fn": sig_data["fn"],
            "tn": sig_data["tn"],
        }

    return {
        "aggregate_f1": data["aggregate_f1"],
        "total_fixtures": data["total_fixtures"],
        "signals": per_signal,
    }


def collect_mutation_recall() -> dict | None:
    """Read mutation benchmark results if they exist."""
    if not MUTATION_FILE.exists():
        return None
    data = json.loads(MUTATION_FILE.read_text(encoding="utf-8"))
    per_signal = {}
    detection = data.get("detection", {})
    for sig_name, sig_data in detection.items():
        per_signal[sig_name] = {
            "injected": sig_data["injected"],
            "detected": sig_data["detected"],
            "recall": sig_data["recall"],
        }
    return {
        "overall_recall": data.get("overall_recall", 0.0),
        "total_injected": data.get("total_injected", 0),
        "total_detected": data.get("total_detected", 0),
        "signals": per_signal,
    }


def collect_self_analysis_count() -> int | None:
    """Run drift self-analysis and return finding count."""
    try:
        cmd = [
            sys.executable, "-m", "drift", "analyze",
            "--repo", ".", "--format", "json", "--exit-zero",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=120,
        )
        if result.returncode != 0:
            return None
        # Parse NDJSON — find the result object
        decoder = json.JSONDecoder()
        text = result.stdout
        idx = 0
        findings_count = None
        while idx < len(text):
            try:
                obj, end = decoder.raw_decode(text, idx)
                idx = end
                if isinstance(obj, dict) and "findings" in obj:
                    findings_count = len(obj["findings"])
                    break
            except json.JSONDecodeError:
                idx += 1
        return findings_count
    except Exception:
        return None


def build_snapshot(
    *,
    skip_self_analysis: bool = False,
) -> dict:
    """Build a complete KPI snapshot."""
    snapshot: dict = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "version": _get_version(),
        "git_sha": _get_git_sha(),
    }

    # 1. Precision/Recall
    pr_data = collect_precision_recall()
    snapshot["precision_recall"] = {
        "aggregate_f1": pr_data["aggregate_f1"],
        "total_fixtures": pr_data["total_fixtures"],
        "signals": pr_data["signals"],
    }

    # 2. Mutation Recall
    mutation_data = collect_mutation_recall()
    if mutation_data is not None:
        snapshot["mutation"] = mutation_data

    # 3. Self-analysis finding count
    if not skip_self_analysis:
        count = collect_self_analysis_count()
        if count is not None:
            snapshot["self_analysis_finding_count"] = count

    return snapshot


def append_to_trend(snapshot: dict) -> None:
    """Append a compact snapshot line to kpi_trend.jsonl."""
    # Compact representation for trend: no per-signal detail
    trend_entry = {
        "timestamp": snapshot["timestamp"],
        "version": snapshot["version"],
        "git_sha": snapshot["git_sha"],
        "aggregate_f1": snapshot["precision_recall"]["aggregate_f1"],
        "total_fixtures": snapshot["precision_recall"]["total_fixtures"],
    }
    if "mutation" in snapshot:
        trend_entry["mutation_recall"] = snapshot["mutation"]["overall_recall"]
        trend_entry["mutation_injected"] = snapshot["mutation"]["total_injected"]
    if "self_analysis_finding_count" in snapshot:
        trend_entry["self_analysis_finding_count"] = snapshot["self_analysis_finding_count"]

    # Per-signal F1 as flat dict
    trend_entry["per_signal_f1"] = {
        sig: data["f1"]
        for sig, data in snapshot["precision_recall"]["signals"].items()
    }

    TREND_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TREND_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(trend_entry, separators=(",", ":")) + "\n")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Collect KPI snapshot")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "benchmark_results" / "kpi_snapshot.json",
        help="Path for full snapshot JSON (default: benchmark_results/kpi_snapshot.json)",
    )
    parser.add_argument(
        "--skip-self-analysis",
        action="store_true",
        help="Skip self-analysis (faster, for CI where self-analysis runs separately)",
    )
    parser.add_argument(
        "--no-trend",
        action="store_true",
        help="Do not append to kpi_trend.jsonl",
    )
    args = parser.parse_args()

    print("Collecting KPI snapshot...")
    snapshot = build_snapshot(skip_self_analysis=args.skip_self_analysis)

    # Write full snapshot
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"Snapshot written to {args.output}")

    # Append to trend
    if not args.no_trend:
        append_to_trend(snapshot)
        print(f"Trend appended to {TREND_FILE}")

    # Summary
    pr = snapshot["precision_recall"]
    print(f"\n  Aggregate F1: {pr['aggregate_f1']:.4f}")
    print(f"  Fixtures:     {pr['total_fixtures']}")
    if "mutation" in snapshot:
        m = snapshot["mutation"]
        detected = m['total_detected']
        injected = m['total_injected']
        print(f"  Mutation:     {m['overall_recall']:.2%} ({detected}/{injected})")
    if "self_analysis_finding_count" in snapshot:
        print(f"  Self-findings: {snapshot['self_analysis_finding_count']}")


if __name__ == "__main__":
    main()
