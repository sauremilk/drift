#!/usr/bin/env python3
"""Generate the repair-coverage matrix artifact.

Reads signal metadata from ``drift.signal_registry`` and writes a
JSON file to ``benchmark_results/repair_coverage_matrix.json``.

Usage::

    python scripts/generate_repair_coverage_matrix.py [--output PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure the repo src/ is importable when run from repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

_DEFAULT_OUTPUT = _REPO_ROOT / "benchmark_results" / "repair_coverage_matrix.json"

# Ordered from weakest to strongest repair capability.
_LEVEL_ORDER = ["diagnosis", "plannable", "example_based", "verifiable"]


def _build_matrix() -> dict:
    """Build the full repair-coverage matrix payload."""
    from drift import __version__
    from drift.signal_registry import get_all_meta, get_repair_coverage_summary

    summary = get_repair_coverage_summary()
    all_meta = {m.signal_id: m for m in get_all_meta()}

    # Per-level counts
    level_counts: dict[str, int] = {lvl: 0 for lvl in _LEVEL_ORDER}
    for entry in summary.values():
        lvl = str(entry["repair_level"])
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    total = len(summary)
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "drift_version": __version__,
        "total_signals": total,
        "repair_level_distribution": level_counts,
        "actionable_ratio": round(
            sum(v for k, v in level_counts.items() if k != "diagnosis") / max(total, 1),
            3,
        ),
        "signals": {
            sid: {
                **entry,
                "default_weight": all_meta[sid].default_weight,
            }
            for sid, entry in sorted(summary.items())
        },
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate repair-coverage matrix.")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Output JSON path (default: benchmark_results/repair_coverage_matrix.json)",
    )
    args = parser.parse_args(argv)

    matrix = _build_matrix()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(matrix, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output}  ({matrix['total_signals']} signals)")

    # Quick summary
    dist = matrix["repair_level_distribution"]
    for lvl in _LEVEL_ORDER:
        print(f"  {lvl:15s}: {dist.get(lvl, 0)}")
    print(f"  actionable_ratio: {matrix['actionable_ratio']}")


if __name__ == "__main__":
    main()
