#!/usr/bin/env python3
"""Validiere ADR-Frontmatter gegen das ADR-087-Schema.

Prüft alle ``docs/decisions/ADR-*.md`` auf:

- bekannten ``status``
- gültige ``criticality`` (wenn gesetzt)
- ``criticality: critical`` → ``scope`` ist Pflicht
- nicht-leere ``scope``-Einträge

Liefert exit 0 bei Erfolg (Warnings erlaubt) und exit 1 bei Errors.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _main() -> int:
    parser = argparse.ArgumentParser(description="ADR-Frontmatter-Validator (ADR-087).")
    parser.add_argument(
        "--repo",
        default=".",
        help="Repository-Pfad (default: aktuelles Verzeichnis).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Warnings als Errors behandeln.",
    )
    args = parser.parse_args()

    try:
        from drift.blast_radius._adr_frontmatter import validate_adr_frontmatter
    except ImportError as exc:
        print(f"[adr-frontmatter] drift nicht importierbar: {exc}", file=sys.stderr)
        return 1

    repo = Path(args.repo).resolve()
    decisions_dir = repo / "docs" / "decisions"
    issues = validate_adr_frontmatter(decisions_dir)

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    for issue in sorted(issues, key=lambda i: (i.severity != "error", i.adr_id)):
        rel = issue.path.relative_to(repo) if issue.path.is_absolute() else issue.path
        print(f"[{issue.severity.upper()}] {rel} ({issue.adr_id}): {issue.message}")

    if errors:
        print(f"\n{len(errors)} Error(s), {len(warnings)} Warning(s).", file=sys.stderr)
        return 1
    if args.strict and warnings:
        print(
            f"\nStrict-Modus: {len(warnings)} Warning(s) wie Errors behandelt.",
            file=sys.stderr,
        )
        return 1
    print(f"\nOK — {len(warnings)} Warning(s), 0 Error(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
