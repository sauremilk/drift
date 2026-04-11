#!/usr/bin/env python3
"""Validate a Policy Gate declaration against repository state.

Replaces self-reported Policy Gate compliance with machine-checkable
plausibility validation.  Designed to be called by agents after producing
the PFLICHT-GATE output, or by CI as a pre-push check.

Usage::

    python scripts/check_policy_gate.py gate.yaml
    python scripts/check_policy_gate.py gate.json
    python scripts/check_policy_gate.py --from-task-spec task.yaml

Exit codes:
    0 — gate declaration is plausible
    1 — gate declaration has issues (details printed)
    2 — file not found or parse error
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

# Layers that require ADR before implementation
ADR_LAYERS = {"signals", "scoring", "output"}

# Layers that require audit artifact updates (Policy §18)
AUDIT_LAYERS = {"signals", "ingestion", "output"}

AUDIT_ARTIFACTS = (
    "audit_results/fmea_matrix.md",
    "audit_results/stride_threat_model.md",
    "audit_results/fault_trees.md",
    "audit_results/risk_register.md",
)

VALID_CRITERIA = {
    "unsicherheit",
    "signal",
    "glaubwürdigkeit",
    "glaubwurdigkeit",
    "handlungsfähigkeit",
    "handlungsfahigkeit",
    "trend",
    "einführbarkeit",
    "einfuhrbarkeit",
}

VALID_DECISIONS = {"zulässig", "zulassig", "abbruch"}


def validate_gate(gate: dict[str, str | bool], repo_root: Path | None = None) -> list[str]:
    """Validate a Policy Gate declaration for plausibility.

    Args:
        gate: Dict with gate fields (aufgabe, zulassungskriterium, entscheidung, etc.)
        repo_root: Repository root for file existence checks (defaults to cwd).

    Returns:
        List of issues found (empty = plausible).
    """
    issues: list[str] = []
    root = repo_root or Path.cwd()

    # Normalize keys to lowercase for flexible input
    g = {k.lower().replace("-", "_").replace(" ", "_"): v for k, v in gate.items()}

    # Check required fields
    required = ["aufgabe", "entscheidung"]
    for field in required:
        if field not in g or not str(g[field]).strip():
            issues.append(f"Required field '{field}' is missing or empty.")

    # Validate decision value
    entscheidung = str(g.get("entscheidung", "")).lower().strip()
    if entscheidung and entscheidung not in VALID_DECISIONS:
        issues.append(
            f"entscheidung '{g.get('entscheidung')}' is not valid. "
            f"Expected: ZULÄSSIG or ABBRUCH."
        )

    # Validate criterion
    kriterium = str(g.get("zulassungskriterium", g.get("zulassungskriterium_erfüllt", ""))).lower()
    if kriterium:
        # Extract criterion name after arrow (→) or colon
        match = re.search(r"[→:]\s*(\w+)", kriterium)
        if match:
            criterion = match.group(1).strip()
            if criterion and criterion not in VALID_CRITERIA:
                issues.append(
                    f"Criterion '{criterion}' is not a recognized admission criterion. "
                    f"Expected one of: {', '.join(sorted(VALID_CRITERIA))}"
                )

    # Check affected_layers consistency (if provided via task_spec enrichment)
    affected_layers = g.get("affected_layers", [])
    if isinstance(affected_layers, str):
        affected_layers = [l.strip() for l in affected_layers.split(",")]

    betrifft_signal = str(g.get("betrifft_signal_architektur", g.get("betrifft_signal", ""))).lower()
    if affected_layers:
        has_signal_layers = bool(AUDIT_LAYERS & set(affected_layers))
        if has_signal_layers and "nein" in betrifft_signal:
            issues.append(
                "affected_layers includes signal/ingestion/output but "
                "'betrifft_signal_architektur' says NEIN — inconsistent."
            )

    # Check ADR existence for signal/scoring/output work
    if affected_layers and (ADR_LAYERS & set(affected_layers)):
        requires_adr = g.get("requires_adr", True)
        if requires_adr:
            decisions_dir = root / "decisions"
            if decisions_dir.is_dir():
                adrs = list(decisions_dir.glob("ADR-*.md"))
                if not adrs:
                    issues.append(
                        "Task affects signal/scoring/output layers but no ADRs found "
                        "under decisions/. ADR required before implementation."
                    )

    # Check audit artifacts exist when signal work is declared
    if "ja" in betrifft_signal:
        resolved_root = root.resolve()
        for artifact in AUDIT_ARTIFACTS:
            artifact_path = (root / artifact).resolve()
            if not artifact_path.is_relative_to(resolved_root):
                issues.append(f"Audit artifact path escapes repo root: {artifact}")
            elif not artifact_path.is_file():
                issues.append(f"Audit artifact missing: {artifact}")

    # Check begründung is not empty/ritualistic
    begruendung = str(g.get("begründung", g.get("begruendung", g.get("begründung", "")))).strip()
    if begruendung and len(begruendung) < 10:
        issues.append(
            f"Begründung too short ({len(begruendung)} chars) — "
            "may be ritualistic rather than substantive."
        )

    return issues


def main() -> int:
    """Run policy gate validation."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_policy_gate.py <gate.yaml|gate.json>")
        return 2

    gate_path = Path(sys.argv[1])
    if not gate_path.exists():
        print(f"ERROR: File not found: {gate_path}")
        return 2

    raw_text = gate_path.read_text(encoding="utf-8")
    try:
        if gate_path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(raw_text)
        elif gate_path.suffix == ".json":
            data = json.loads(raw_text)
        else:
            print(f"ERROR: Unsupported format: {gate_path.suffix}")
            return 2
    except Exception as exc:
        print(f"ERROR: Failed to parse {gate_path}: {exc}")
        return 2

    if not isinstance(data, dict):
        print(f"ERROR: Expected a mapping, got {type(data).__name__}")
        return 2

    issues = validate_gate(data)

    if issues:
        print(f"POLICY GATE ISSUES ({len(issues)}):")
        for issue in issues:
            print(f"  ✗ {issue}")
        return 1

    print("✓ Policy Gate declaration is plausible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
