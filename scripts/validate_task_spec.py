#!/usr/bin/env python3
"""Validate a TaskSpec file (YAML or JSON) against the schema.

Usage::

    python scripts/validate_task_spec.py task.yaml
    python scripts/validate_task_spec.py task.json
    python scripts/validate_task_spec.py --example   # print example spec

Exit codes:
    0 — valid (with optional advisory warnings)
    1 — validation errors found
    2 — file not found or parse error
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from drift.task_spec import TaskSpec, validate_task_spec

EXAMPLE_SPEC = """\
# Example TaskSpec — copy and adapt for your task
goal: "Add phantom-reference signal for stale imports"
affected_layers:
  - signals
scope_boundaries:
  - "src/drift/signals/phantom_reference.py"
  - "tests/test_phantom_reference*.py"
forbidden_paths:
  - "src/drift/scoring/**"
quality_constraints:
  - "Precision >= 70% on ground-truth fixtures"
  - "No regressions on existing signal scores"
acceptance_criteria:
  - "Signal registered in config.py with weight > 0"
  - "FMEA entry added for FP and FN"
  - "Tests pass: pytest tests/test_phantom_reference*.py"
requires_adr: true
requires_audit_update: true
commit_type: "feat"
depends_on:
  - "ADR-033"
"""


def main() -> int:
    """Run task spec validation."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_task_spec.py <spec.yaml|spec.json|--example>")
        return 2

    if sys.argv[1] == "--example":
        print(EXAMPLE_SPEC)
        return 0

    spec_path = Path(sys.argv[1])
    if not spec_path.exists():
        print(f"ERROR: File not found: {spec_path}")
        return 2

    # Parse file
    raw_text = spec_path.read_text(encoding="utf-8")
    try:
        if spec_path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(raw_text)
        elif spec_path.suffix == ".json":
            data = json.loads(raw_text)
        else:
            print(f"ERROR: Unsupported file format: {spec_path.suffix} (use .yaml or .json)")
            return 2
    except Exception as exc:
        print(f"ERROR: Failed to parse {spec_path}: {exc}")
        return 2

    if not isinstance(data, dict):
        print(f"ERROR: Expected a mapping, got {type(data).__name__}")
        return 2

    # Validate against Pydantic model
    try:
        spec = TaskSpec(**data)
    except ValidationError as exc:
        print(f"VALIDATION ERRORS in {spec_path}:\n")
        for error in exc.errors():
            loc = " → ".join(str(p) for p in error["loc"])
            print(f"  [{loc}] {error['msg']}")
        return 1

    # Run semantic validation
    issues = validate_task_spec(spec)

    # Output results
    print(f"TaskSpec: {spec_path}")
    print(f"  Goal: {spec.goal}")
    print(f"  Layers: {', '.join(layer.value for layer in spec.affected_layers)}")
    print(f"  Scope: {spec.scope_boundaries or '(unrestricted)'}")
    print(f"  ADR required: {spec.requires_adr}")
    print(f"  Audit required: {spec.requires_audit_update}")
    print(f"  Commit type: {spec.commit_type or '(not set)'}")

    if issues:
        print(f"\nADVISORIES ({len(issues)}):")
        for issue in issues:
            print(f"  [!] {issue}")

    print("\n[OK] TaskSpec is structurally valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
