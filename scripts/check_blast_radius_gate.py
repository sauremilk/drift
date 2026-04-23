#!/usr/bin/env python3
"""Pre-Push Gate 9 — Blast-Radius (ADR-087).

Prüft vor jedem Push:

1. **Trigger**: Umfasst der Push-Range Pfade in ``src/drift/**``, ``docs/decisions/**``,
   ``POLICY.md`` oder ``.github/skills/**``? Wenn nein → ``exit 0``.
2. **Report-Existenz**: Existiert ``blast_reports/*_<short_sha>.json`` für den
   HEAD-SHA? Wenn nein → Gate schreibt einen Report live, falls ``DRIFT_BLAST_LIVE``
   gesetzt ist, sonst ``exit 1``.
3. **Report-Ancestry**: Stimmt ``trigger.head_sha`` im Report mit HEAD überein?
   Wenn nein → ``exit 1``.
4. **Critical-Ack**: Enthält der Report kritische Impacts
   (``requires_maintainer_ack=True``)? Wenn ja, muss
   ``blast_reports/acks/<short_sha>.yaml`` existieren.
5. **Degraded-Fall**: Wenn der Report ``degraded=True`` meldet, blockiert das
   Gate nicht hart (Warning).

Bypass: ``DRIFT_SKIP_BLAST_GATE=1`` loggt Warning und exit 0.

Aufruf aus ``hooks/pre-push``:

.. code-block:: bash

    python scripts/check_blast_radius_gate.py --ref "$remote_sha" --head "$local_sha"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_TRIGGER_GLOBS = (
    "src/drift/**",
    "docs/decisions/**",
    "POLICY.md",
    ".github/skills/**",
)


def _find_repo_root(start: Path) -> Path:
    cur = start.resolve()
    for parent in [cur, *cur.parents]:
        if (parent / ".git").exists():
            return parent
    return start.resolve()


def _log(msg: str) -> None:
    print(f"[blast-radius-gate] {msg}", file=sys.stderr)


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-Push Gate 9 — Blast-Radius (ADR-087)."
    )
    parser.add_argument("--ref", default="HEAD~1", help="Git-Basis-Ref für den Diff.")
    parser.add_argument("--head", default="HEAD", help="Git-HEAD für den Diff.")
    parser.add_argument(
        "--repo",
        default=".",
        help="Repository-Pfad (default: aktuelles Verzeichnis).",
    )
    args = parser.parse_args()

    if os.environ.get("DRIFT_SKIP_BLAST_GATE") == "1":
        _log("DRIFT_SKIP_BLAST_GATE=1 gesetzt — Gate übersprungen (Warning geloggt).")
        return 0

    repo_path = _find_repo_root(Path(args.repo))

    # Lazy-Import, damit das Script auch ohne installiertes drift-Paket scheitert
    try:
        from drift.blast_radius import (
            BlastReport,
            compute_blast_report,
            save_blast_report,
        )
        from drift.blast_radius._change_detector import detect_changes, short_sha
        from drift.blast_radius._glob import files_matching
        from drift.blast_radius._persistence import (
            find_ack_for_sha,
            find_report_for_sha,
        )
    except ImportError as exc:
        _log(f"drift.blast_radius nicht importierbar: {exc}")
        _log("Bitte 'pip install -e .' ausführen. Gate blockiert vorsichtshalber.")
        return 1

    # 1. Trigger-Prüfung
    changeset = detect_changes(repo_path, ref=args.ref, head=args.head)
    if not changeset.changed_files:
        _log("Kein Diff erkannt — Gate übersprungen.")
        return 0
    triggers: list[str] = []
    for glob in _TRIGGER_GLOBS:
        if files_matching(changeset.changed_files, glob):
            triggers.append(glob)
    if not triggers:
        _log("Keine Blast-Trigger-Pfade im Diff — Gate übersprungen.")
        return 0
    _log(f"Trigger-Patterns gematcht: {triggers}")

    head_sha = changeset.head_sha or ""
    if not head_sha:
        _log("HEAD-SHA konnte nicht aufgelöst werden — Gate blockiert.")
        return 1

    # 2. Report suchen oder live erzeugen
    report_path = find_report_for_sha(repo_path, head_sha)
    report: BlastReport | None = None
    if report_path is not None:
        try:
            from drift.blast_radius import load_blast_report

            report = load_blast_report(report_path)
            _log(f"Report geladen: {report_path.relative_to(repo_path)}")
        except ValueError as exc:
            _log(f"Report {report_path} ungültig: {exc}")
            return 1
    else:
        if os.environ.get("DRIFT_BLAST_LIVE") == "1":
            _log("Kein gespeicherter Report — erzeuge live (DRIFT_BLAST_LIVE=1).")
            report = compute_blast_report(
                repo_path, ref=args.ref, head=args.head
            )
            report_path = save_blast_report(repo_path, report)
            _log(f"Report live erzeugt: {report_path.relative_to(repo_path)}")
        else:
            _log(
                f"Kein Blast-Report für HEAD-SHA {short_sha(head_sha)} gefunden. "
                "Führe entweder 'python -m drift.blast_radius' aus "
                "oder setze DRIFT_BLAST_LIVE=1 für Live-Generierung."
            )
            return 1

    # 3. Ancestry-Check
    if report.trigger.head_sha and report.trigger.head_sha != head_sha:
        _log(
            f"Report-SHA {report.trigger.head_sha} != HEAD {head_sha}. "
            "Neuen Report erzeugen oder DRIFT_BLAST_LIVE=1 nutzen."
        )
        return 1

    # 4. Critical-Ack-Check
    if report.has_critical_impacts():
        ack_path = find_ack_for_sha(repo_path, head_sha)
        if ack_path is None:
            ids = ", ".join(report.critical_impact_ids())
            _log(
                "Kritische Impacts ohne Maintainer-Ack: "
                f"{ids}. "
                f"Lege blast_reports/acks/{short_sha(head_sha)}.yaml an (nur Maintainer)."
            )
            return 1
        _log(f"Maintainer-Ack gefunden: {ack_path.relative_to(repo_path)}")

    # 5. Degraded-Warning
    if report.degraded:
        _log("Report degraded — Gate warnt, blockiert aber nicht hart:")
        for note in report.degradation_notes:
            _log(f"  - {note}")

    _log("Gate bestanden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
