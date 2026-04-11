---
id: ADR-049
status: proposed
date: 2026-04-11
type: signal-design
signal_id: PFS
supersedes:
---

# ADR-049: PFS Canonical Code-Snippet + canonical_min_ratio Severity-Downgrade

## Problemklasse

`pattern_fragmentation` (PFS) identifiziert Dateien, die von einem kanonischen Muster abweichen. Das Metadata-Feld `canonical_exemplar` enthält gegenwärtig nur eine Dateipfad-Zeilenreferenz (`"path/file.py:42"`), keinen lesbaren Code-Snippet. Maintainer müssen selbst zur Datei navigieren um zu sehen, **was** das kanonische Muster ist — das eliminiert den Handlungswert des Findings weitgehend.

Zusätzlich feuert PFS für Pattern-Gruppen mit einer `canonical_ratio` von < 10% (wenige kanonische Instanzen), was statistisch schwach ist und zu vielen False-Positives führt.

## Heuristik

**Snippet-Extraktion:**
```python
def _extract_canonical_snippet(file_path: str, start_line: int, max_lines: int = 8) -> str:
    """Read source lines around start_line for canonical pattern display."""
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
        snippet_lines = lines[start_line - 1 : start_line - 1 + max_lines]
        return "".join(snippet_lines).rstrip()
    except (OSError, IndexError):
        return ""
```

Ergebnis wird in `finding.metadata["canonical_snippet"]` gespeichert.

**Severity-Downgrade durch canonical_ratio:**
```
canonical_ratio < 0.10 → downgrade HIGH→MEDIUM, MEDIUM→LOW (statistisch schwach)
canonical_ratio < 0.15 → downgrade nur HIGH→MEDIUM
canonical_ratio >= 0.15 → keine Änderung
```

## Scope

`file_local` mit Zugriff auf Dateisystem zur Laufzeit (Snippet-Extraktion). Das ist safe, da `analyze()` ohnehin im analysierenden Repo-Kontext läuft.

## Erwartete FP-Klassen

- Snippet-Extraktion kann fehl schlagen (Datei nicht mehr vorhanden nach Git-Checkout-Wechsel) → graceful fallback auf leeren String
- Kanon-Instanz abstrahiert eine 3rd-Party-Dependency die geändert wurde → Snippet veraltet

## Erwartete FN-Klassen

- Kanonisches Pattern ist zu komplex für 8-Zeilen-Snippet → kürzt ab, aber zeigt Anfang

## Fixture-Plan

- TP-Fixture: `pfs_low_canonical_ratio_below_15pct` — 2 canon. Instanzen von 20 gesamt (10%) → HIGH → MEDIUM nach Downgrade
- TN-Fixture: `pfs_canonical_ratio_above_50pct` — > 50% canonical → kein Downgrade, normales Scoring

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| FP: Snippet aus veraltetem Kanonon gezeigt | 4 | 3 | 6 | 72 |
| FN: Snippet zu kurz, Pattern nicht erkennbar | 3 | 4 | 5 | 60 |
| FP: Severity-Downgrade maskiert echtes Pattern-Problem | 6 | 3 | 5 | 90 |

## Validierungskriterium

1. PFS-Findings enthalten `canonical_snippet` im Metadata-Feld (non-leerer String für TP-Fixtures).
2. Für `canonical_ratio < 0.10`: Severity nicht höher als MEDIUM.
3. `pytest tests/test_precision_recall.py` — PFS Recall ≥ 0.80 (Baseline).
4. Self-analysis PFS-Findings zeigen Snippet-Vorschau in JSON-Output.
