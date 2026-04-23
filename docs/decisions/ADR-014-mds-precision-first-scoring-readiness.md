---
id: ADR-014
status: proposed
date: 2026-04-06
supersedes:
---

# ADR-014: MDS Precision-First Kalibrierung für Scoring-Readiness

## Kontext

MDS ist bereits als Bewertungssignal gewichtet, erzeugt in realen
Repository-Scans jedoch noch relevante Noise-Klassen mit niedriger
Handlungsfähigkeit. Besonders betroffen sind:

- semantische Ähnlichkeiten ohne belastbare Duplicate-Intention
- Sync/Async-Varianten desselben API-Verhaltens
- intra-file semantische Paarungen

Diese Noise-Faelle senken die wahrgenommene Glaubwuerdigkeit und
verschlechtern die Priorisierungsqualitaet in score-getriebenen
Workflows.

## Entscheidung

Wir kalibrieren MDS praezisionsorientiert entlang drei Regeln:

1. Hybrid-Schwelle nicht unter AST-Schwelle absenken (precision-first).
2. Sync/Async-Dateivarianten mit gleichem Funktionsnamen als intentional
   behandeln und in MDS unterdruecken.
3. Semantic-Only-Duplikate verschaerfen:
   - hoehere Embedding-Schwelle
   - keine Intra-File-Semantic-Duplicates

## Begruendung

Diese Aenderung reduziert False Positives in den am haeufigsten
beobachteten MDS-Rauschmustern, ohne die Grundfaehigkeit zur
Cross-File-Duplicate-Erkennung aufzugeben.

Damit steigt die Signalqualitaet in Richtung belastbarer
Bewertungsnutzung (Scoring-Readiness), prioritaetskonform mit
Drift-Policy: Glaubwuerdigkeit vor Feature-Ausbau.

## Konsequenzen

- Erwartet: hoehere Praezision, geringere MDS-Noise-Dichte.
- Trade-off: moeglicher Recall-Verlust bei intentional-aehnlichen
  Sync/Async-Strukturen oder grenzwertigen semantic-only Paaren.
- Absicherung: gezielte Regressionstests fuer neue Suppressionspfade.

## Validierung

- `python -m pytest tests/test_mutant_duplicates_edge_cases.py -q --maxfail=1`
- `python -m pytest tests/test_precision_recall.py::test_precision_recall_report -q -s`

Erfolgsbedingung:

- keine Regression in bestehenden Ground-Truth-MDS-Faellen
- robuste Nicht-Erkennung fuer neue Confounder-Klassen
