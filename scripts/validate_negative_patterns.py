#!/usr/bin/env python3
"""Validate negative-pattern metadata files against the JSON Schema.

Checks:
- Every ``*.json`` in ``data/negative-patterns/patterns/`` validates against
  ``data/negative-patterns/schema.json``.
- Every ``*.json`` has a matching ``.py`` file **or** a directory with the same
  base name containing at least one ``.py`` file.
- No orphan ``.py`` files exist without a corresponding ``*.json``.

Exit code 0 = all valid, 1 = validation errors found.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema is not installed. Run: pip install jsonschema>=4.0", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
PATTERNS_DIR = REPO_ROOT / "data" / "negative-patterns" / "patterns"
SCHEMA_PATH = REPO_ROOT / "data" / "negative-patterns" / "schema.json"


def _discover_json_files() -> list[Path]:
    """Return all .json metadata files under patterns/, including subdirs."""
    return sorted(PATTERNS_DIR.rglob("*.json"))


def _discover_py_files() -> set[str]:
    """Return set of pattern IDs that have at least one .py file."""
    ids: set[str] = set()
    for py in PATTERNS_DIR.rglob("*.py"):
        # Single-file: guard_clause_deficit_001.py → id = guard_clause_deficit_001
        # Multi-file dir: mutant_duplicate_001/formatters.py → id = mutant_duplicate_001
        rel = py.relative_to(PATTERNS_DIR)
        parts = rel.parts
        if len(parts) == 1:
            ids.add(py.stem)
        elif len(parts) >= 2:
            ids.add(parts[0])
    return ids


def main() -> int:
    errors: list[str] = []

    if not SCHEMA_PATH.exists():
        print(f"ERROR: Schema not found at {SCHEMA_PATH}", file=sys.stderr)
        return 1

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    json_files = _discover_json_files()

    if not json_files:
        print("ERROR: No pattern JSON files found", file=sys.stderr)
        return 1

    json_ids: set[str] = set()

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{jf.name}: invalid JSON — {exc}")
            continue

        # Schema validation
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"{jf.name}: schema violation — {exc.message}")
            continue

        pattern_id = data["id"]
        json_ids.add(pattern_id)

        # Filename consistency: JSON filename prefix must match id
        expected_name = f"{pattern_id}.json"
        if jf.name != expected_name:
            errors.append(
                f"{jf.name}: filename does not match id '{pattern_id}' "
                f"(expected {expected_name})"
            )

    # Check every JSON has at least one .py
    py_ids = _discover_py_files()
    for jid in sorted(json_ids):
        if jid not in py_ids:
            errors.append(f"{jid}: no .py file or directory found for pattern")

    # Check for orphan .py without JSON
    for pid in sorted(py_ids - json_ids):
        errors.append(f"{pid}: .py file(s) exist but no matching .json metadata")

    # Report
    if errors:
        print(f"Negative-pattern validation FAILED ({len(errors)} errors):", file=sys.stderr)
        for e in errors:
            print(f"  • {e}", file=sys.stderr)
        return 1

    print(f"✓ {len(json_ids)} patterns validated successfully against schema")
    return 0


if __name__ == "__main__":
    sys.exit(main())
