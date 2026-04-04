#!/usr/bin/env python3
"""Performance gate for the automated regression loop.

Combines wall-clock benchmarking (like benchmark_perf.py) with cProfile
hotspot extraction (like profile_drift.py) and a pass/fail gate with
structured JSON output for CI consumption.

Usage:
    # Human-readable
    python scripts/perf_gate.py --budget 30 --target-path src/drift

    # JSON for CI pipelines
    python scripts/perf_gate.py --budget 30 --target-path src/drift --json

    # Force fail (testing)
    python scripts/perf_gate.py --budget 1 --runs 1 --json

Exit codes:
    0 — Budget met (median wall-clock < budget)
    1 — Budget exceeded
"""

from __future__ import annotations

import argparse
import contextlib
import cProfile
import json
import pstats
import statistics
import sys
import time
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from drift.analyzer import analyze_repo  # noqa: E402
from drift.config import DriftConfig  # noqa: E402

# Aligned with tests/test_ci_reality.py::TestPerformanceBudget
_DEFAULT_BUDGET_S = 30.0
_DEFAULT_TARGET_PATH = "src/drift"
_DEFAULT_RUNS = 3
_DEFAULT_WARMUP = 1
_DEFAULT_MAX_ITERATIONS = 5
_TOP_HOTSPOTS = 10


def _run_once(
    repo: Path,
    cfg: DriftConfig,
    target_path: str | None,
) -> dict:
    """Single timed analysis run (no profiling)."""
    start = time.perf_counter()
    result = analyze_repo(repo, cfg, since_days=90, target_path=target_path)
    elapsed = time.perf_counter() - start
    return {
        "elapsed": elapsed,
        "score": result.drift_score,
        "files": result.total_files,
        "functions": result.total_functions,
        "findings": len(result.findings),
        "duration_internal": result.analysis_duration_seconds,
    }


def _run_profiled(
    repo: Path,
    cfg: DriftConfig,
    target_path: str | None,
) -> tuple[dict, list[dict]]:
    """Single profiled analysis run. Returns (metrics, hotspots)."""
    profiler = cProfile.Profile()
    start = time.perf_counter()
    profiler.enable()
    result = analyze_repo(repo, cfg, since_days=90, target_path=target_path)
    profiler.disable()
    elapsed = time.perf_counter() - start

    metrics = {
        "elapsed": elapsed,
        "score": result.drift_score,
        "files": result.total_files,
        "functions": result.total_functions,
        "findings": len(result.findings),
        "duration_internal": result.analysis_duration_seconds,
    }

    # Extract top hotspots by cumulative time
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")

    hotspots: list[dict] = []
    # pstats.Stats stores entries as (filename, line, funcname) -> stats tuple
    total_cumtime = max(
        sum(v[3] for v in stats.stats.values()), 0.001  # type: ignore[attr-defined]  # noqa: RUF015
    )
    sorted_entries = sorted(
        stats.stats.items(), key=lambda x: x[1][3], reverse=True  # type: ignore[attr-defined]
    )
    for (filename, _line, funcname), (
        _cc,
        _ncalls,
        _tottime,
        cumtime,
        _callers,
    ) in sorted_entries[:_TOP_HOTSPOTS]:
        # Make paths relative and concise
        short = filename
        with contextlib.suppress(ValueError, TypeError):
            short = str(Path(filename).relative_to(repo))
        hotspots.append({
            "function": f"{short}:{funcname}",
            "cumtime": round(cumtime, 3),
            "percent": round(100.0 * cumtime / total_cumtime, 1),
        })

    return metrics, hotspots


def _build_profile_summary(
    repo: Path, cfg: DriftConfig, target_path: str | None
) -> str:
    """Generate human-readable cProfile summary (top 15 by cumtime)."""
    profiler = cProfile.Profile()
    profiler.enable()
    analyze_repo(repo, cfg, since_days=90, target_path=target_path)
    profiler.disable()

    stream = StringIO()
    ps = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
    ps.print_stats(15)
    return stream.getvalue()


def _build_agent_prompt(
    *,
    iteration: int,
    max_iterations: int,
    wall_clock: float,
    budget: float,
    findings_count: int,
    hotspots: list[dict],
    profile_summary: str,
) -> str:
    """Build structured issue body for the Copilot Coding Agent."""
    delta = wall_clock - budget
    percent = 100.0 * delta / budget if budget > 0 else 0
    hotspot_table = "\n".join(
        f"| {i + 1} | `{h['function']}` | {h['cumtime']:.3f} | {h['percent']:.1f}% |"
        for i, h in enumerate(hotspots)
    )
    # Finding guard: ±5% tolerance
    lo = int(findings_count * 0.95)
    hi = int(findings_count * 1.05)

    return f"""## Performance-Regression: Drift Self-Analysis exceeds budget

**Iteration:** {iteration} / {max_iterations}
**Measured:** {wall_clock:.1f}s | **Budget:** {budget:.0f}s
**Overshoot:** +{delta:.1f}s ({percent:.1f}%)

### Profiler Hotspots (Top {len(hotspots)})

| # | Function | Cumulative (s) | Share |
|---|----------|-----------------|-------|
{hotspot_table}

### Optimization target

Reduce total wall-clock time of drift self-analysis (`src/drift/`) to under {budget:.0f}s.

### Constraints

- Do NOT change signal semantics (findings must remain equivalent)
- Do NOT add new dependencies
- All tests must pass (`make check`)
- Only modify files under `src/drift/`
- Focus on the top-3 hotspots listed above
- Finding count must stay within {lo}–{hi} (currently {findings_count}, ±5% tolerance)
- No silent finding elimination — performance only

### Reproduction

```bash
python scripts/perf_gate.py --budget {budget:.0f} --target-path src/drift --runs 3
```

### Full profile (top 15 by cumulative time)

```
{profile_summary.strip()}
```
"""


def main() -> int:
    """Run performance gate and return exit code."""
    parser = argparse.ArgumentParser(
        description="Performance gate: benchmark + profile + pass/fail"
    )
    parser.add_argument(
        "--repo",
        default=str(Path(__file__).parent.parent),
        help="Repository path (default: drift root)",
    )
    parser.add_argument(
        "--target-path",
        default=_DEFAULT_TARGET_PATH,
        help=f"Restrict analysis to subpath (default: {_DEFAULT_TARGET_PATH})",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=_DEFAULT_BUDGET_S,
        help=f"Wall-clock budget in seconds (default: {_DEFAULT_BUDGET_S})",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=_DEFAULT_RUNS,
        help=f"Number of timed runs (default: {_DEFAULT_RUNS})",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=_DEFAULT_WARMUP,
        help=f"Warmup runs (default: {_DEFAULT_WARMUP})",
    )
    parser.add_argument(
        "--iteration",
        type=int,
        default=1,
        help="Current iteration number (for agent prompt)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=_DEFAULT_MAX_ITERATIONS,
        help=f"Maximum iterations (default: {_DEFAULT_MAX_ITERATIONS})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON to stdout",
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    cfg = DriftConfig.load(repo)
    target = args.target_path or None

    if not args.json:
        print(f"Perf gate: {repo} (target: {target})")
        print(f"Budget: {args.budget}s | Runs: {args.runs} | Warmup: {args.warmup}")
        print()

    # --- Warmup ---
    for i in range(args.warmup):
        if not args.json:
            print(f"  warmup {i + 1}/{args.warmup} ...", end="", flush=True)
        r = _run_once(repo, cfg, target)
        if not args.json:
            print(f" {r['elapsed']:.2f}s")

    # --- Timed runs (last run is profiled) ---
    timings: list[float] = []
    last_result: dict = {}
    hotspots: list[dict] = []

    for i in range(args.runs):
        if not args.json:
            print(f"  run {i + 1}/{args.runs} ...", end="", flush=True)

        if i == args.runs - 1:
            # Profile the final run
            r, hotspots = _run_profiled(repo, cfg, target)
        else:
            r = _run_once(repo, cfg, target)

        timings.append(r["elapsed"])
        last_result = r
        if not args.json:
            print(f" {r['elapsed']:.2f}s")

    # --- Evaluate ---
    median_time = statistics.median(timings)
    passed = median_time < args.budget
    overshoot = max(0.0, median_time - args.budget)
    overshoot_pct = 100.0 * overshoot / args.budget if args.budget > 0 else 0

    if args.json:
        # Build profile summary for the agent prompt (extra profiled run)
        profile_summary = _build_profile_summary(repo, cfg, target)
        agent_prompt = _build_agent_prompt(
            iteration=args.iteration,
            max_iterations=args.max_iterations,
            wall_clock=median_time,
            budget=args.budget,
            findings_count=last_result.get("findings", 0),
            hotspots=hotspots,
            profile_summary=profile_summary,
        )

        output = {
            "passed": passed,
            "wall_clock_seconds": round(median_time, 3),
            "budget_seconds": args.budget,
            "overshoot_seconds": round(overshoot, 3),
            "overshoot_percent": round(overshoot_pct, 1),
            "iteration": args.iteration,
            "max_iterations": args.max_iterations,
            "drift_score": last_result.get("score", 0.0),
            "files_analyzed": last_result.get("files", 0),
            "findings_count": last_result.get("findings", 0),
            "runs": len(timings),
            "timings": [round(t, 3) for t in timings],
            "median": round(median_time, 3),
            "top_hotspots": hotspots,
            "agent_prompt": agent_prompt,
        }
        json.dump(output, sys.stdout, indent=2)
        print()  # trailing newline
    else:
        print()
        print("=" * 55)
        print(f"  Repo:      {repo.name}")
        print(f"  Target:    {target or '(all)'}")
        print(f"  Files:     {last_result.get('files', '?')}")
        print(f"  Findings:  {last_result.get('findings', '?')}")
        print(f"  Score:     {last_result.get('score', '?')}")
        print()
        print(f"  Median:    {median_time:.3f}s")
        print(f"  Budget:    {args.budget:.1f}s")
        print(f"  Overshoot: {overshoot:.3f}s ({overshoot_pct:.1f}%)")
        print()
        if passed:
            print(f"  PASS — median {median_time:.1f}s < {args.budget:.0f}s budget")
        else:
            print(
                f"  FAIL — median {median_time:.1f}s exceeds "
                f"{args.budget:.0f}s budget by {overshoot:.1f}s"
            )
        print()
        if hotspots:
            print("  Top hotspots:")
            for i, h in enumerate(hotspots[:5], 1):
                print(
                    f"    {i}. {h['function']}  "
                    f"{h['cumtime']:.3f}s ({h['percent']:.1f}%)"
                )
        print("=" * 55)

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
