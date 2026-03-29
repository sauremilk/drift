"""Performance benchmarking for drift analyze.

Usage:
    python scripts/benchmark_perf.py [repo_path] [--runs N] [--warmup N]

Measures:
- Total wall-clock time for ``drift analyze``
- Per-phase breakdown (ingestion, signals, scoring) via internal API
- Comparison baseline for validating optimisations

Requires: drift installed in the current environment.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from drift.analyzer import analyze_repo
from drift.config import DriftConfig


def _run_once(repo: Path, cfg: DriftConfig) -> dict:
    """Run a single analysis and return timing + result summary."""
    start = time.perf_counter()
    result = analyze_repo(repo, cfg, since_days=90)
    elapsed = time.perf_counter() - start
    return {
        "elapsed": elapsed,
        "score": result.drift_score,
        "files": result.total_files,
        "functions": result.total_functions,
        "findings": len(result.findings),
        "duration_internal": result.analysis_duration_seconds,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark drift analyze")
    parser.add_argument(
        "repo", nargs="?", default=str(Path(__file__).parent.parent),
        help="Repository path to analyze (default: drift itself)",
    )
    parser.add_argument("--runs", type=int, default=5, help="Number of timed runs")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup runs (not timed)")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    cfg = DriftConfig.load(repo)
    print(f"Benchmarking: {repo}")
    print(f"Warmup: {args.warmup}, Runs: {args.runs}")
    print()

    # Warmup
    for i in range(args.warmup):
        print(f"  warmup {i + 1}/{args.warmup} ...", end="", flush=True)
        r = _run_once(repo, cfg)
        print(f" {r['elapsed']:.2f}s")

    # Timed runs
    timings: list[float] = []
    last_result: dict = {}
    for i in range(args.runs):
        print(f"  run {i + 1}/{args.runs} ...", end="", flush=True)
        r = _run_once(repo, cfg)
        timings.append(r["elapsed"])
        last_result = r
        print(f" {r['elapsed']:.2f}s")

    print()
    print("=" * 50)
    print(f"Repo:      {repo.name}")
    print(f"Files:     {last_result['files']}")
    print(f"Functions: {last_result['functions']}")
    print(f"Findings:  {last_result['findings']}")
    print(f"Score:     {last_result['score']}")
    print()
    print(f"Mean:      {statistics.mean(timings):.3f}s")
    print(f"Median:    {statistics.median(timings):.3f}s")
    if len(timings) > 1:
        print(f"Stdev:     {statistics.stdev(timings):.3f}s")
    print(f"Min:       {min(timings):.3f}s")
    print(f"Max:       {max(timings):.3f}s")
    print(f"Runs:      {timings}")


if __name__ == "__main__":
    main()
