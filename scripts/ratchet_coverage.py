#!/usr/bin/env python3
"""Coverage Ratchet — automatically advances fail_under in pyproject.toml.

After running ``pytest --cov=drift --cov-report=json``, this script reads
``coverage.json``, compares the measured percentage against the current
``fail_under`` threshold, and bumps the threshold by ``--step`` percentage
points when measured coverage exceeds it by at least ``--margin`` points.

This is a one-direction ratchet: the threshold only ever increases.

Usage
-----
    # After pytest --cov=drift --cov-report=json:
    python scripts/ratchet_coverage.py

    # Dry-run (print what would change without writing):
    python scripts/ratchet_coverage.py --dry-run

    # Custom step and margin:
    python scripts/ratchet_coverage.py --step 2 --margin 2

Exit codes
----------
0  No change needed or ratchet applied successfully.
1  Error (pyproject.toml or coverage.json not found / not parseable).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
COVERAGE_JSON = REPO_ROOT / "coverage.json"

# Matches the fail_under line in [tool.coverage.report]
_RE_FAIL_UNDER = re.compile(r"^(fail_under\s*=\s*)(\d+(?:\.\d+)?)", re.MULTILINE)


def _read_measured_coverage(coverage_file: Path) -> float:
    """Return overall branch+line coverage percentage from coverage.json."""
    try:
        data = json.loads(coverage_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ratchet] ERROR reading {coverage_file}: {exc}", file=sys.stderr)
        sys.exit(1)

    # coverage.py JSON format: data["totals"]["percent_covered"]
    totals = data.get("totals", {})
    pct = totals.get("percent_covered")
    if pct is None:
        print(
            "[ratchet] ERROR coverage.json has no 'totals.percent_covered' field.",
            file=sys.stderr,
        )
        sys.exit(1)
    return float(pct)


def _read_current_threshold(pyproject: Path) -> float:
    """Return the current fail_under value from pyproject.toml."""
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[ratchet] ERROR reading {pyproject}: {exc}", file=sys.stderr)
        sys.exit(1)

    match = _RE_FAIL_UNDER.search(text)
    if not match:
        print(
            "[ratchet] ERROR could not find 'fail_under' in [tool.coverage.report].",
            file=sys.stderr,
        )
        sys.exit(1)
    return float(match.group(2))


def _apply_ratchet(pyproject: Path, new_threshold: int) -> None:
    """Write the new fail_under value to pyproject.toml."""
    text = pyproject.read_text(encoding="utf-8")

    def _replace(m: re.Match) -> str:
        return f"{m.group(1)}{new_threshold}"

    new_text = _RE_FAIL_UNDER.sub(_replace, text, count=1)
    pyproject.write_text(new_text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ratchet_coverage",
        description="Advance the coverage fail_under threshold in pyproject.toml.",
    )
    parser.add_argument(
        "--coverage-json",
        type=Path,
        default=COVERAGE_JSON,
        metavar="PATH",
        help="Path to coverage.json (default: coverage.json in repo root).",
    )
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=PYPROJECT,
        metavar="PATH",
        help="Path to pyproject.toml (default: pyproject.toml in repo root).",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=2,
        metavar="PP",
        help="Percentage points to advance the threshold by (default: 2).",
    )
    parser.add_argument(
        "--margin",
        type=int,
        default=2,
        metavar="PP",
        help=(
            "Minimum gap between measured coverage and threshold required "
            "to trigger a ratchet advance (default: 2)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print what would change without writing pyproject.toml.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
    )
    args = parser.parse_args(argv)

    measured = _read_measured_coverage(args.coverage_json)
    current = _read_current_threshold(args.pyproject)

    gap = measured - current
    new_threshold = int(current) + args.step

    if args.verbose or args.dry_run:
        print(
            f"[ratchet] measured={measured:.1f}%  current_threshold={current:.0f}%  "
            f"gap={gap:.1f}pp  step={args.step}pp  margin={args.margin}pp"
        )

    if gap < args.margin:
        print(
            f"[ratchet] No advance: gap {gap:.1f}pp < margin {args.margin}pp "
            f"(measured={measured:.1f}%, threshold={current:.0f}%)."
        )
        return 0

    if args.dry_run:
        print(
            f"[ratchet] DRY-RUN: would advance fail_under from {current:.0f} → {new_threshold}."
        )
        return 0

    _apply_ratchet(args.pyproject, new_threshold)
    print(
        f"[ratchet] Advanced fail_under: {current:.0f} → {new_threshold} "
        f"(measured coverage = {measured:.1f}%)."
    )
    print(f"[ratchet] Remember to commit the pyproject.toml change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
