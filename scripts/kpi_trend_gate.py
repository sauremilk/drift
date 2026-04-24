#!/usr/bin/env python3
"""KPI Trend Regression Gate.

Analyses kpi_trend.jsonl for negative trends over a sliding window.
Emits GitHub Actions annotations and optionally blocks release.

Monitored metrics (all want high / stable):
  - aggregate_f1       (precision-recall F1 over ground-truth fixtures)
  - mutation_recall    (mutation detection recall)

Warning level : slope < --warn-slope  (default: -0.02/release)
Block level   : slope < --block-slope (default: -0.05/release)

Usage:
  python scripts/kpi_trend_gate.py \\
    --trend-log benchmark_results/kpi_trend.jsonl \\
    --window 5 \\
    --metrics aggregate_f1 mutation_recall \\
    --warn-slope -0.02 \\
    --block-slope -0.05

Exit codes:
  0 – no blocking trend detected
  1 – at least one metric declining faster than block-slope
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_trend(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        print(f"INFO: trend log not found: {path}. Skipping.", flush=True)
        return []
    entries = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _linear_slope(values: list[float]) -> float:
    """Return slope of best-fit line via least-squares (no scipy needed)."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def main() -> None:
    parser = argparse.ArgumentParser(description="KPI trend regression gate")
    parser.add_argument(
        "--trend-log",
        default="benchmark_results/kpi_trend.jsonl",
        help="Path to kpi_trend.jsonl",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=5,
        help="Number of most-recent entries to include (default: 5)",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=["aggregate_f1", "mutation_recall"],
        help="Metric keys to evaluate",
    )
    parser.add_argument(
        "--warn-slope",
        type=float,
        default=-0.02,
        help="Slope below which a ::warning:: is emitted (default: -0.02)",
    )
    parser.add_argument(
        "--block-slope",
        type=float,
        default=-0.05,
        help="Slope below which execution is blocked with exit 1 (default: -0.05)",
    )
    args = parser.parse_args()

    entries = _load_trend(args.trend_log)
    window_entries = entries[-args.window :]

    if len(window_entries) < 2:
        print(
            f"INFO: only {len(window_entries)} trend entries available "
            f"(need >= 2 for regression). Skipping.",
            flush=True,
        )
        sys.exit(0)

    print(
        f"Analysing {len(window_entries)} entries "
        f"(versions: {window_entries[0].get('version', '?')} .. "
        f"{window_entries[-1].get('version', '?')})"
    )

    should_block = False

    for metric in args.metrics:
        values = []
        for entry in window_entries:
            v = entry.get(metric)
            if v is None:
                # Skip entries where the metric is absent
                # (e.g. self_analysis_finding_count can be null)
                continue
            values.append(float(v))

        if len(values) < 2:
            print(f"  {metric}: insufficient data points ({len(values)}), skipping")
            continue

        slope = _linear_slope(values)
        trend_symbol = "~" if abs(slope) < 0.001 else ("+" if slope > 0 else "-")
        print(
            f"  {metric}: slope = {slope:+.4f}/release  "
            f"[{', '.join(f'{v:.4f}' for v in values)}]  {trend_symbol}"
        )

        if slope < args.block_slope:
            print(
                f"::error::{metric} declining at {slope:+.4f}/release "
                f"(block threshold: {args.block_slope})",
                flush=True,
            )
            should_block = True
        elif slope < args.warn_slope:
            print(
                f"::warning::{metric} trend declining: {slope:+.4f}/release "
                f"(warn threshold: {args.warn_slope})",
                flush=True,
            )

    if should_block:
        sys.exit(1)

    print("Trend gate: PASS", flush=True)


if __name__ == "__main__":
    main()
