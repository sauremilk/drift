#!/usr/bin/env python3
"""Convert confirmed FP findings into CONFOUNDER fixtures.

Reads ground_truth_labels.json for "FP" entries, fetches the corresponding
finding details from *_full.json, and generates GroundTruthFixture stubs
that can be appended to tests/fixtures/ground_truth.py.

Usage:
    python scripts/fp_to_fixture.py
    python scripts/fp_to_fixture.py --signal doc_impl_drift
    python scripts/fp_to_fixture.py --output fp_fixtures.py
    python scripts/fp_to_fixture.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

REPO_ROOT = Path(__file__).resolve().parent.parent
LABELS_PATH = REPO_ROOT / "benchmark_results" / "ground_truth_labels.json"
BENCHMARK_DIR = REPO_ROOT / "benchmark_results"

# Maps signal names to SignalType enum values
_SIGNAL_TO_ENUM: dict[str, str] = {
    "architecture_violation": "ARCHITECTURE_VIOLATION",
    "bypass_accumulation": "BYPASS_ACCUMULATION",
    "broad_exception_monoculture": "BROAD_EXCEPTION_MONOCULTURE",
    "cohesion_deficit": "COHESION_DEFICIT",
    "doc_impl_drift": "DOC_IMPL_DRIFT",
    "explainability_deficit": "EXPLAINABILITY_DEFICIT",
    "guard_clause_deficit": "GUARD_CLAUSE_DEFICIT",
    "mutant_duplicate": "MUTANT_DUPLICATE",
    "naming_contract_violation": "NAMING_CONTRACT_VIOLATION",
    "pattern_fragmentation": "PATTERN_FRAGMENTATION",
    "system_misalignment": "SYSTEM_MISALIGNMENT",
    "temporal_volatility": "TEMPORAL_VOLATILITY",
    "test_polarity_deficit": "TEST_POLARITY_DEFICIT",
}


def _load_labels() -> list[dict[str, str]]:
    if not LABELS_PATH.exists():
        return []
    return json.loads(LABELS_PATH.read_text(encoding="utf-8"))


def _load_all_findings() -> dict[str, dict]:
    """Load all *_full.json files into a {key: finding} lookup."""
    lookup: dict[str, dict] = {}
    for p in BENCHMARK_DIR.glob("*_full.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        repo = data.get("repo", p.stem.removesuffix("_full"))
        for f in data.get("findings", []):
            key = f"{repo}::{f.get('title', '')}"
            lookup[key] = f
    return lookup


def _sanitize_name(title: str, signal: str, seen: set[str]) -> str:
    """Create a unique valid Python identifier from a finding title."""
    # Take first meaningful words
    cleaned = re.sub(r"[^a-zA-Z0-9_\s]", "", title)
    words = cleaned.lower().split()[:5]
    if not words:
        words = [signal, "fp"]
    name = "_".join(words)
    # Prefix with signal abbreviation
    abbrev = "".join(w[0] for w in signal.split("_"))
    base = f"{abbrev}_confounder_{name}"
    # Ensure uniqueness
    candidate = base
    counter = 2
    while candidate in seen:
        candidate = f"{base}_{counter}"
        counter += 1
    seen.add(candidate)
    return candidate


def _generate_fixture(
    key: str, label_entry: dict, finding: dict | None, seen_names: set[str]
) -> str:
    """Generate a GroundTruthFixture Python snippet for a confirmed FP."""
    signal = label_entry.get("signal", "unknown")
    enum_name = _SIGNAL_TO_ENUM.get(signal, signal.upper())
    title = key.split("::", 1)[1] if "::" in key else key
    fixture_name = _sanitize_name(title, signal, seen_names)

    file_path = "unknown.py"
    description = title
    if finding:
        file_path = finding.get("file", "unknown.py")
        description = finding.get("description", title)
        if len(description) > 80:
            description = description[:77] + "..."

    # We can only generate a stub — actual code must be filled manually
    return textwrap.dedent(f"""\
    # --- FP from: {key} ---
    # TODO: Replace placeholder code with minimal reproducer from {file_path}
    {fixture_name.upper()} = GroundTruthFixture(
        name="{fixture_name}",
        description="{description}",
        kind=FixtureKind.CONFOUNDER,
        files={{
            "{Path(file_path).parent / '__init__.py'}": "",
            "{file_path}": \"\"\"\\
                # TODO: Extract minimal code snippet that triggers the FP
                # Original finding: {title}
                pass
            \"\"\",
        }},
        expected=[
            ExpectedFinding(
                signal_type=SignalType.{enum_name},
                file_path="{file_path}",
                should_detect=False,
                description="Confirmed FP — {title}",
            ),
        ],
    )
    """)


def generate_fixtures(
    *,
    signal_filter: set[str] | None = None,
    dry_run: bool = False,
    output_path: Path | None = None,
) -> int:
    """Generate fixture stubs for all FP labels. Returns count."""
    labels = _load_labels()
    fps = [e for e in labels if e.get("label") == "FP"]
    if signal_filter:
        fps = [e for e in fps if e.get("signal") in signal_filter]

    if not fps:
        print("No FP entries found matching filter.")
        return 0

    findings_lookup = _load_all_findings()

    snippets: list[str] = []
    header = textwrap.dedent("""\
    # ── Auto-generated CONFOUNDER fixtures from confirmed FPs ──
    # Generated by: python scripts/fp_to_fixture.py
    #
    # Each fixture is a stub. Before adding to ground_truth.py:
    # 1. Replace placeholder code with a minimal reproducer
    # 2. Verify the signal does NOT fire on the fixture
    # 3. Add to ALL_FIXTURES list
    #
    # Required imports (already in ground_truth.py):
    # from drift.models import SignalType
    # GroundTruthFixture, ExpectedFinding, FixtureKind
    """)
    snippets.append(header)

    seen_names: set[str] = set()
    for entry in fps:
        key = entry["key"]
        finding = findings_lookup.get(key)
        snippet = _generate_fixture(key, entry, finding, seen_names)
        snippets.append(snippet)

    output = "\n".join(snippets)

    if dry_run:
        print(output)
        print(f"\n--- {len(fps)} FP fixture stubs (dry run) ---")
    elif output_path:
        output_path.write_text(output, encoding="utf-8")
        print(f"Wrote {len(fps)} fixture stubs to {output_path}")
    else:
        print(output)
        print(f"\n--- {len(fps)} FP fixture stubs ---")
        print("Use --output <file> to save, then copy into ground_truth.py")

    return len(fps)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate CONFOUNDER fixtures from confirmed FP labels",
    )
    parser.add_argument(
        "--signal",
        nargs="+",
        help="Only process FPs from these signals",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write fixture stubs to this file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print stubs without writing",
    )
    args = parser.parse_args()

    signal_filter = set(args.signal) if args.signal else None
    count = generate_fixtures(
        signal_filter=signal_filter,
        dry_run=args.dry_run,
        output_path=args.output,
    )
    if count == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
