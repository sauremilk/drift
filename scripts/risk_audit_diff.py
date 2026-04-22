#!/usr/bin/env python3
"""Show required risk-audit updates based on changed files."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SIGNAL_AUDIT_MAP: dict[str, list[str]] = {
    "src/drift/signals/": [
        "audit_results/fmea_matrix.md (Signalzeile)",
        "audit_results/risk_register.md",
    ],
    "src/drift/ingestion/": [
        "audit_results/fmea_matrix.md (Ingestion)",
        "audit_results/fault_trees.md",
    ],
    "src/drift/output/": [
        "audit_results/stride_threat_model.md",
        "audit_results/fmea_matrix.md (Output)",
    ],
}


def required_audit_updates(changed_files: set[str]) -> list[str]:
    required: set[str] = set()
    for path in changed_files:
        for prefix, updates in SIGNAL_AUDIT_MAP.items():
            if path.startswith(prefix):
                required.update(updates)
    return sorted(required)


def _git_changed_files(staged: bool) -> set[str]:
    args = ["git", "diff", "--name-only"]
    if staged:
        args.append("--cached")
    else:
        args.append("HEAD")

    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Show risk-audit files required for current diff.")
    parser.add_argument(
        "--staged", action="store_true", help="Use staged diff instead of working tree."
    )
    args = parser.parse_args()

    changed_files = _git_changed_files(staged=args.staged)
    required = required_audit_updates(changed_files)

    if not required:
        print("No risk-audit updates required for current changes.")
        return 0

    print("Risk-audit updates required:")
    for item in required:
        print(f"- {item}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
