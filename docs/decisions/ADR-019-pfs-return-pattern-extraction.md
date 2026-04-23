---
id: ADR-019
status: proposed
date: 2026-04-07
type: signal-design
signal_id: PFS
supersedes:
---

# ADR-019: Signal Design — Return-Pattern-Extraktion für PFS

## Problemklasse

PFS erkennt ausschließlich ERROR_HANDLING- und API_ENDPOINT-Fragmentation.
Return-Strategie-Diversität innerhalb eines Moduls (z. B. `return None` vs. `raise`
vs. `return (value, error)`) wird nicht erfasst, obwohl sie ein Kohärenzproblem
darstellt (Policy §4.2: strukturelle Erosion durch inkonsistente Konventionen).

FTA v1 identifiziert dies als Single Point of Failure (MCS-1): Ein fehlender
Extraktionspfad in `_process_function()` ist hinreichend, um den gesamten
Return-Pattern-Recall auf 0 zu halten. Mutation-Benchmark zeigt PFS-Recall 0.5
(pfs_002 "return_pattern: 3 variants in models/" = undetected).

## Heuristik

1. Für jede geparste Funktion: Return-Exits klassifizieren
   - `return None` / nacktes `return` → Strategie `return_none`
   - `raise <Exc>` als Fehlerweg → Strategie `raise`
   - `return (<val>, <err>)` → Strategie `return_tuple`
   - `return {…}` (dict-literal) → Strategie `return_dict`
   - sonstige Returns → Strategie `return_value`
2. Fingerprint = `{"strategies": sorted(unique_strategies)}`
3. Emission als `PatternInstance(category=RETURN_PATTERN)` nur wenn ≥ 2 distinkte Strategien
4. PFS-Signal aggregiert per-Modul (bestehende Logik, keine Änderung)

## Scope

`file_local` — Return-Strategie wird pro Funktion aus dem AST extrahiert,
PFS aggregiert dann per Modul. Konsistent mit bestehendem `incremental_scope`.

## Erwartete FP-Klassen

| FP-Klasse | Beschreibung | Akzeptanz |
|-----------|-------------|-----------|
| Intentionale Überladung | Funktion bietet absichtlich verschiedene Return-Pfade (z. B. get_or_none + get_or_raise) | Akzeptabel — PFS meldet korrekt Diversität |
| Factory-Muster | Factory mit verschiedenen Return-Typen je nach Input | Niedrig — Fingerprint gruppiert per Funktion, nicht per Modul |

## Erwartete FN-Klassen

| FN-Klasse | Beschreibung |
|-----------|-------------|
| Dynamische Returns | Return-Strategien erst zur Laufzeit erkennbar (z. B. via Callback) |
| Implicit None | Funktionen, die None implizit durch Nicht-Return zurückgeben |

## Fixture-Plan

| Fixture | Typ | Beschreibung |
|---------|-----|-------------|
| PFS_RETURN_PATTERN_TP | TP | Modul mit 3 Funktionen: return-None, raise, return-Tuple |
| PFS_RETURN_PATTERN_TN | (bestehend pfs_tn) | Konsistente Patterns — kein neues Fixture nötig |

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| RETURN_PATTERN FP bei intentionaler Überladung | 3 | 3 | 7 | 63 |
| RETURN_PATTERN FN bei dynamischen Returns | 2 | 4 | 8 | 64 |
| Parser extrahiert Return-Strategie falsch | 5 | 2 | 3 | 30 |

## Entscheidung

`PatternCategory.RETURN_PATTERN` als neuen Enum-Wert einführen.
Neue Fingerprint-Funktion `_fingerprint_return_strategy()` in `ast_parser.py`.
Aufruf in `_process_function()` nach dem API-Endpoint-Block.

Explizit **nicht** Teil dieser ADR:
- Scoring-Gewichts-Änderung (PFS bleibt bei 0.16)
- Guard-Return / Assert als ERROR_HANDLING (MCS-2/3 — separates Issue)
- Benchmark-Enum-Validierung (MCS-4 — separates Issue)

## Begründung

Der Fix adressiert einen SPOF mit Recall-Impact 0.5 → 1.0 im Mutation-Benchmark.
Return-Strategie-Diversität ist semantisch distinkt von ERROR_HANDLING (Fehlerstrategie ≠
Return-Konvention), daher eigene PatternCategory statt Subsumierung.
Keine Scoring-Änderung nötig, da PFS generisch über alle PatternCategories aggregiert.

## Konsequenzen

- PFS-Recall im Mutation-Benchmark steigt von 0.5 auf 1.0
- Neue Pattern-Kategorie erfordert FMEA + Fault-Tree + Risk-Register-Update
- Bestehende PFS-Tests bleiben intakt (keine Verhaltensänderung bei ERROR_HANDLING)
- Spätere Erweiterung (Guard-Return, Assert) wird durch die Kategorie-Architektur erleichtert

## Validierungskriterium

```bash
pytest tests/test_ast_parser.py -v -k return_strategy
pytest tests/test_pattern_fragmentation.py -v -k return_pattern
pytest tests/test_precision_recall.py -v
python scripts/_mutation_benchmark.py  # pfs detected=2/2
```

Lernzyklus-Ergebnis: `bestaetigt` wenn PFS-Recall ≥ 0.9 im Mutation-Benchmark
und keine Precision-Regression (PFS-Precision ≥ 0.70).
