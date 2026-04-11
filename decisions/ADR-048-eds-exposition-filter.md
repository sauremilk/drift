---
id: ADR-048
status: proposed
date: 2026-04-11
type: signal-design
signal_id: EDS
supersedes:
---

# ADR-048: EDS Exposition-Filter — Relevanzgewichtung für öffentliche APIs

## Problemklasse

`explainability_deficit` (EDS) erzeugt gegenwärtig Findings für **alle** Funktionen ohne Docstring, unabhängig davon, ob sie jemals von außen aufgerufen werden, in Test-Fixtures liegen oder als private Utility-Funktion arbeiten. Im Actionability Review (2026-04-11) wurden ~190 EDS-Findings gezählt, von denen schätzungsweise >80% für den Maintainer ohne handlungsrelevante Dringlichkeit sind (private Helfer, Test-Utilities, generierte Adapter).

## Heuristik

Neue Gewichtungsformel vor Finding-Erzeugung:

```
exposition_weight = 0.0
if is_public (kein "_"-Prefix):  +0.15
if external_callers > 5:          +0.25
if defect_correlated_commits > 0: +0.30
if complexity > 20 (McCabe):      +0.15
if context in ("fixture","test","generated"): × 0.0  (suppress entirely)

effective_score = raw_score + exposition_weight
Finding wird erzeugt nur wenn effective_score >= 0.35
```

Bestehende `effective_score`-Berechnung (in `_explanation_score()`) bleibt erhalten — `exposition_weight` addiert sich auf den Basiswert.

## Scope

`file_local` — EDS bleibt ein file-lokales Signal; keine neuen Cross-File-Abhängigkeiten. Der Felder `external_callers` muss aus `parse_results` extrahiert werden (falls verfügbar) oder geschätzt werden über `public_callers_map` aus dem AST-Kontext.

## Erwartete FP-Klassen

- Öffentliche Funktion in Test-Helper-Modul (false positive: wird suppressed wenn context=="test", aber eigentlich API)
- CLI-Entry-Points in Commands-Modul (werden korrekt NOT suppressed da kein "_"-Prefix)

## Erwartete FN-Klassen

- Private Funktion mit `_`-Prefix die tatsächlich von außerhalb des Moduls aufgerufen wird (Type-Ignore-Pattern)
- Stark genutzte interne Utility-Funktion ohne öffentlichen Status

## Fixture-Plan

- TP-Fixture: `eds_public_api_no_docstring_high_callers` — public function, > 5 external callers, no docstring → Finding ERWARTET
- TN-Fixture: `eds_private_utility_no_docstring` — private function (`_`-Prefix), no docstring → kein Finding ERWARTET

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| FP: Test-Helper wird als öffentliche API behandelt | 4 | 4 | 6 | 96 |
| FN: Stark genutzte private Funktion wird nicht erkannt | 5 | 5 | 5 | 125 |
| FP: Funktionen in generierten Dateien werden gemeldet | 3 | 3 | 7 | 63 |

## Validierungskriterium

1. EDS-Finding-Count auf self-analysis: von ~190 auf < 60 reduziert (>50% Reduktion).
2. `pytest tests/test_precision_recall.py` — EDS Recall ≥ 0.80 (Baseline nicht unterschreiten).
3. Neue Fixtures TP/TN bestehen.
4. `drift analyze --format json` für ein reines Test-Only-Repository: 0 EDS Findings.
