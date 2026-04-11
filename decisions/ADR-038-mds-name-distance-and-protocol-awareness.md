---
id: ADR-038
status: proposed
date: 2026-04-10
type: signal-design
signal_id: MDS
supersedes:
---

# ADR-038: MDS — Name-Token-Similarity + Protocol-Awareness + Thin-Wrapper-Gate

## Problemklasse

MDS hat eine strict-Precision von 0.82 (2 FP / 68 Samples) und 10 Disputed-Findings. Die FPs entstehen durch: (1) strukturell ähnliche aber semantisch unterschiedliche Helfer, (2) Protocol/Interface-Implementierungen mit gleicher Signatur in verschiedenen Klassen, (3) Thin-Wrapper-Delegationen mit hoher AST-Ähnlichkeit zum Delegationsziel.

## Heuristik

### 1. Name-Token-Similarity als dritter Hybrid-Faktor

Neue Funktion `_name_token_similarity(name_a, name_b) -> float`:
- Splittet CamelCase/snake_case in Tokens
- Berechnet Jaccard-Similarity auf Token-Sets
- Eingebaut in Hybrid-Formel:
  - Mit Embeddings: `0.55 × AST + 0.35 × Embedding + 0.10 × Name`
  - Ohne Embeddings: `0.85 × AST + 0.15 × Name`

### 2. Protocol-Implementation-Awareness

Erkennung von Methodenpaaren in verschiedenen Klassen mit gleichem Namen aus einem konfigurierbaren Interface-Pattern-Set. Diese Paare werden übersprungen.

### 3. Thin-Wrapper-Delegation-Gate

Erkennung von Thin-Wrapper-Funktionen (LOC ≤ 5, genau ein Call-Ausdruck). Wenn ein Partner eine Thin-Wrapper ist, wird der Score um 50% gedämpft.

## Scope

`cross_file` — keine Änderung am bestehenden Scope.

## Erwartete FP-Klassen

- **Reduziert:** Strukturell ähnliche Helfer mit unterschiedlichen Namen (score penalty ~10–15%)
- **Reduziert:** Protocol-Methoden in verschiedenen Klassen (vollständig unterdrückt)
- **Reduziert:** Thin-Wrapper-Delegationen (50% Score-Reduktion)

## Erwartete FN-Klassen

- **Neu:** Echte near-duplicates mit zufällig verschiedenen Namen könnten knapp unter Threshold fallen
- **Mitigation:** Name-Distance-Gewicht nur 0.10–0.15; AST dominiert weiterhin mit 0.55–0.85

## Fixture-Plan

- `mds_confounder_protocol_methods_tn` — gleiche Methode in verschiedenen Klassen → kein Finding
- `mds_confounder_thin_wrapper_tn` — Delegation → kein Finding
- `mds_confounder_name_diverse_tn` — ähnlicher Body, verschiedene Namen → kein Finding

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| FN: Echte near-duplicates mit abweichenden Namen nicht erkannt | 5 | 2 | 4 | 40 |
| FP: Protocol-Pattern-Set zu breit → echte Duplikate unterdrückt | 3 | 2 | 5 | 30 |
| FN: Thin-wrapper-Gate zu aggressiv → echte copy-paste-wrapper nicht gemeldet | 4 | 2 | 5 | 40 |

## Validierungskriterium

- `pytest tests/test_precision_recall.py -v` — MDS precision ≥ 0.60 (aktuell 0.82)
- MDS recall ≥ 0.95 im Mutation-Benchmark
- Bestehende MDS-Fixtures bleiben grün
- Lernzyklus-Ergebnis: `bestaetigt` wenn MDS precision_strict ≥ 0.85 und recall ≥ 0.95
