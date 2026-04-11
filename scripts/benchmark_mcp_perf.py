#!/usr/bin/env python3
"""Benchmark MCP tool latency and throughput (in-process tool layer).

This benchmark measures the MCP tool coroutine layer directly by importing
``drift.mcp_server`` and invoking the exported tool handlers.
It avoids stdio transport framing effects so timings reflect server-side
handler latency and throughput.

Usage:
    python scripts/benchmark_mcp_perf.py
    python scripts/benchmark_mcp_perf.py --iterations 5 --warmup 1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    idx = max(0, min(98, int(p) - 1))
    return statistics.quantiles(values, n=100, method="inclusive")[idx]


ToolCallable = Callable[[str], Awaitable[str]]


def _build_tool_calls() -> list[tuple[str, ToolCallable]]:
    from drift import mcp_server

    return [
        (
            "drift_scan",
            lambda repo: mcp_server.drift_scan(
                path=repo,
                max_findings=10,
                response_detail="concise",
            ),
        ),
        (
            "drift_fix_plan",
            lambda repo: mcp_server.drift_fix_plan(
                path=repo,
                max_tasks=5,
            ),
        ),
        (
            "drift_nudge",
            lambda repo: mcp_server.drift_nudge(path=repo),
        ),
        (
            "drift_brief",
            lambda repo: mcp_server.drift_brief(
                path=repo,
                task="implement mcp performance optimization",
                response_detail="concise",
            ),
        ),
        (
            "drift_negative_context",
            lambda repo: mcp_server.drift_negative_context(
                path=repo,
                max_items=10,
            ),
        ),
        (
            "drift_session_start_autopilot",
            lambda repo: mcp_server.drift_session_start(
                path=repo,
                autopilot=True,
                response_profile="coder",
            ),
        ),
    ]


async def _run_tool(name: str, fn: ToolCallable, repo_path: str) -> tuple[bool, float]:
    t0 = time.monotonic()
    payload = await fn(repo_path)
    elapsed = time.monotonic() - t0

    ok = False
    try:
        parsed = json.loads(payload)
        ok = isinstance(parsed, dict) and "error_code" not in parsed
    except json.JSONDecodeError:
        ok = False

    return ok, elapsed


async def _run_benchmark(
    repo_path: str,
    iterations: int,
    warmup: int,
) -> dict[str, Any]:
    tool_calls = _build_tool_calls()
    measurements: dict[str, list[float]] = {name: [] for name, _ in tool_calls}
    errors: list[dict[str, Any]] = []

    total_start = time.monotonic()
    for idx in range(warmup + iterations):
        is_warmup = idx < warmup
        for tool_name, tool_fn in tool_calls:
            ok, elapsed = await _run_tool(tool_name, tool_fn, repo_path)
            if not ok:
                errors.append({"iteration": idx + 1, "tool": tool_name})
            if not is_warmup:
                measurements[tool_name].append(elapsed)
    total_elapsed = time.monotonic() - total_start

    measured_calls = iterations * len(tool_calls)
    per_tool = {
        name: {
            "count": len(samples),
            "mean_seconds": round(statistics.mean(samples), 6) if samples else 0.0,
            "p50_seconds": round(_percentile(samples, 50), 6),
            "p95_seconds": round(_percentile(samples, 95), 6),
            "min_seconds": round(min(samples), 6) if samples else 0.0,
            "max_seconds": round(max(samples), 6) if samples else 0.0,
        }
        for name, samples in measurements.items()
    }

    return {
        "benchmark": "mcp_tool_layer_performance",
        "execution_mode": "in_process_mcp_tools",
        "repo": repo_path,
        "iterations": iterations,
        "warmup": warmup,
        "tools": [name for name, _ in tool_calls],
        "throughput_req_per_s": round(measured_calls / max(total_elapsed, 0.001), 3),
        "total_measured_calls": measured_calls,
        "total_measured_seconds": round(total_elapsed, 6),
        "errors": errors,
        "per_tool": per_tool,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark MCP tool performance")
    parser.add_argument(
        "--repo",
        default=str(Path(__file__).resolve().parent.parent),
        help="Repository path to benchmark against.",
    )
    parser.add_argument("--iterations", type=int, default=3, help="Measured iterations.")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup iterations.")
    parser.add_argument(
        "--output",
        default="benchmark_results/mcp_performance.json",
        help="Output JSON file path.",
    )
    args = parser.parse_args()

    repo_path = str(Path(args.repo).resolve())
    output = asyncio.run(_run_benchmark(repo_path, max(1, args.iterations), max(0, args.warmup)))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
