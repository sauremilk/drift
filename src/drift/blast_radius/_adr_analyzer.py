"""ADR-Analyzer: Invalidierung von Architekturentscheidungen.

Strategien in dieser Reihenfolge:

1. **Strukturiert** — ADRs mit ``scope``-Frontmatter (ADR-087) werden per
   Glob gegen ``changed_files`` gematcht. Präzise, wenn Maintainer gepflegt
   haben.
2. **Fallback** — ADRs ohne ``scope`` werden via bestehendem
   ``drift.adr_scanner`` textuell gematcht. Wir filtern das Ergebnis so, dass
   nur ADRs mit tatsächlichem Scope-Treffer oder Task-Keyword-Match
   übernommen werden.

Severity-Regeln:

- ``criticality: critical`` + struktureller Scope-Match → ``critical``,
  ``requires_maintainer_ack=True``.
- ``criticality: high`` → ``high``.
- Alles andere → ``medium``.
- Fallback-Matches (textuell) bleiben maximal ``medium``, um
  False-Positive-Blockaden zu vermeiden.
"""

from __future__ import annotations

import logging
from pathlib import Path

from drift.blast_radius._adr_frontmatter import (
    ADRFrontmatter,
    load_all_adrs,
)
from drift.blast_radius._glob import files_matching
from drift.blast_radius._models import BlastImpact, BlastImpactKind, BlastSeverity

_log = logging.getLogger("drift.blast_radius.adr")


def _severity_for(adr: ADRFrontmatter) -> BlastSeverity:
    if adr.is_critical:
        return BlastSeverity.CRITICAL
    if adr.criticality == "high":
        return BlastSeverity.HIGH
    return BlastSeverity.MEDIUM


def _structured_match(
    adrs: list[ADRFrontmatter],
    changed_files: tuple[str, ...],
) -> tuple[list[BlastImpact], set[str]]:
    """Gib Impacts aus ADRs mit ``scope``-Frontmatter und die Menge der hit-IDs zurück."""
    impacts: list[BlastImpact] = []
    matched_ids: set[str] = set()
    for adr in adrs:
        if not adr.scope:
            continue
        hit_pattern: str | None = None
        matched_files: tuple[str, ...] = ()
        for pattern in adr.scope:
            candidates = files_matching(changed_files, pattern)
            if candidates:
                hit_pattern = pattern
                matched_files = candidates
                break
        if hit_pattern is None:
            continue
        severity = _severity_for(adr)
        requires_ack = severity is BlastSeverity.CRITICAL
        impacts.append(
            BlastImpact(
                kind=BlastImpactKind.ADR,
                target_id=adr.id,
                target_path=None,
                severity=severity,
                reason=(
                    f"ADR {adr.id} ({adr.status}) deckt geänderten Pfad via "
                    f"scope-Pattern {hit_pattern!r} ab und sollte re-validiert werden."
                ),
                scope_match=hit_pattern,
                matched_files=matched_files,
                requires_maintainer_ack=requires_ack,
            )
        )
        matched_ids.add(adr.id)
    return impacts, matched_ids


def _fallback_match(
    repo_path: Path,
    changed_files: tuple[str, ...],
    skip_ids: set[str],
) -> list[BlastImpact]:
    """Text-basiertes ADR-Matching für ADRs ohne strukturierten Scope."""
    try:
        from drift.adr_scanner import scan_active_adrs
    except ImportError:  # pragma: no cover
        _log.debug("adr_scanner nicht importierbar — Fallback übersprungen.")
        return []
    try:
        raw = scan_active_adrs(
            repo_path,
            scope_paths=list(changed_files),
            task="",
            max_results=25,
        )
    except Exception as exc:  # noqa: BLE001
        _log.debug("adr_scanner.scan_active_adrs fehlgeschlagen: %s", exc)
        return []
    impacts: list[BlastImpact] = []
    for entry in raw:
        adr_id = entry.get("id", "") or ""
        if not adr_id or adr_id in skip_ids:
            continue
        reason_token = entry.get("scope_match_reason", "") or ""
        if not reason_token or reason_token == "no_filter":
            # Ohne konkreten Match kein Impact — vermeidet Rauschen.
            continue
        impacts.append(
            BlastImpact(
                kind=BlastImpactKind.ADR,
                target_id=adr_id,
                target_path=None,
                severity=BlastSeverity.MEDIUM,
                reason=(
                    f"ADR {adr_id} ({entry.get('status', 'unknown')}) via textbasiertem "
                    f"Match ({reason_token}) potenziell betroffen — strukturierter Scope fehlt."
                ),
                scope_match=reason_token,
                matched_files=changed_files,
                requires_maintainer_ack=False,
            )
        )
    return impacts


def analyze_adr_impacts(
    repo_path: Path,
    changed_files: tuple[str, ...],
) -> tuple[list[BlastImpact], list[str]]:
    """Ermittle ADR-Invalidierungen (strukturiert + Fallback)."""
    if not changed_files:
        return [], []
    decisions_dir = repo_path / "docs" / "decisions"
    if not decisions_dir.is_dir():
        decisions_dir = repo_path / "decisions"
    if not decisions_dir.is_dir():
        return [], ["Kein decisions/-Verzeichnis — ADR-Analyse übersprungen."]
    adrs = load_all_adrs(decisions_dir)
    structured, matched_ids = _structured_match(adrs, changed_files)
    fallback = _fallback_match(repo_path, changed_files, matched_ids)
    return structured + fallback, []
