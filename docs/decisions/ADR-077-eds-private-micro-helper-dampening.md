---
id: ADR-077
status: proposed
date: 2026-04-19
type: signal-design
signal_id: EDS
supersedes:
---

# ADR-077: EDS — Erhöhter Schwellwert für private Micro-Helpers

## Problemklasse

Der CXS→EDS Fix-Loop-Trade-off erzeugt einen strukturellen Deadlock im Drift-Eigenrepo:
Ein CXS-Finding (hohe kognitive Komplexität) lässt sich durch Helper-Extraktion beheben.
Der extrahierte Helper ist typischerweise privat (`_`-Prefix), kurz (LOC < 40), und
bisher ohne Docstring — und feuert dann sofort EDS.

**Resultat:** Jede CXS-Reduktion erzeugt ein neues EDS-Low-Finding.
Der Fix-Loop ist nicht terminierend.

Bisherige Gegenmassnahme (ADR-048): `exposition_weight`-Modell für öffentliche APIs.
ADR-048 ist aber noch `proposed` und adressiert explizit private Micro-Helpers nicht.

## Heuristik

Neues Threshold-Profil für den kombinierten Fall:

```
Bedingung: is_private AND func.loc < 40 AND NOT defect_correlated
→ min_threshold = 0.55  (statt bisher 0.45)
```

**Begründung der Formelwirkung:**

Für einen privaten Helper mit LOC=30 und Docstring:
- `loc_factor = min(1.0, 30/30) = 1.0`
- `visibility_factor = 0.7`
- `weighted_score = deficit × complexity_factor × (0.7 + 0.3 × 1.0) × 0.7`
- `= deficit × complexity_factor × 0.7`

Bei einem Docstring (z. B. Einzeiler) liegt `deficit` typischerweise um 0.5–0.6,
`complexity_factor` bei ca. 0.4 (LOC≈20, complexity≈8):
`weighted_score ≈ 0.55 × 0.4 × 0.7 ≈ 0.154` → bereits unter `0.45`

Für Helper mit LOC ≤ 20 (sehr kurz) ohne Docstring:
`weighted_score ≈ 0.9 × 0.4 × (0.7 + 0.2) × 0.7 ≈ 0.23` → unter `0.45`

Die Erhöhung auf `0.55` gilt nur für das **pathologische Grenzfall**:
private Funktion, LOC 30–40, Complexity 12–20, kein Docstring, kein Test.
Genau dieser Fall entsteht direkt nach CXS-Extraktion (vor Docstring-Ergänzung).

## Scope

`file_local` — reine Threshold-Anpassung in der Scoring-Logik von
`src/drift/signals/explainability_deficit.py`. Keine neuen Inputs, keine API-Änderung.

## Was explizit NICHT getan wird

- Kein genereller Raise des privaten Thresholds von 0.45 auf 0.55
- Kein Bypass für defekt-korrelierte Dateien
- Kein Suppression-Mechanismus für LOC ≥ 40
- Kein Einfluss auf EDS-Findings für öffentliche Funktionen

## Erwartete FP-Klassen

- Privater Micro-Helper mit LOC 30–40, kein Docstring, hoher echter Defekt-Impact:
  Wird **nicht** suppressed wenn `defect_correlated_commits > 0` (Bedingung nicht erfüllt)
- Privater Helper mit LOC 39, der faktisch von außen gemockt wird:
  Minimales Risiko — solche Helpers haben fast immer Tests oder Kommentare

## Erwartete FN-Klassen

- Privater Micro-Helper in defektfreier Datei der dennoch versteckter Komplexitäts-Hotspot ist:
  Akzeptiertes Risiko — Threshold-Profil lässt sich per `drift.yaml`
  (`cxs_max_complexity`, `thresholds.min_function_loc`) eng kalibrieren

## Fixture-Plan

Vor Implementation (Mindest-Fixtures):

1. **TN — `eds_private_micro_helper_tn`**: private Funktion, LOC=35, kein Docstring,
   kein Defekt-Korrelat, niedrige Komplexität → EDS soll NICHT feuern
2. **TP bleibt TP** — bestehende `eds_tp`-Fixture prüfen: private Funktion mit
   Docstring und Test muss weiterhin NOT feuern (kein Regression)
3. **Boundary — `eds_private_boundary`**: private Funktion, LOC=40 (genau an Grenze),
   kein Docstring → an oder über neuem Threshold

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| FN: privater Micro-Helper mit realem Defekt-Risiko wird unterdrückt | 4 | 2 | 6 | 48 |
| TP-Regression: bestehende EDS-Findings für Private feuern nicht mehr | 6 | 2 | 3 | 36 |
| Threshold-Boundary unscharf (LOC 39 vs. 40) | 2 | 3 | 2 | 12 |

## Validierungskriterium

1. `pytest tests/test_precision_recall.py` — keine TP-Regression
2. `pytest tests/test_eds_*.py` — alle bestehenden Tests grün
3. `pytest tests/test_benchmark_structure.py` — Fixture-Struktur valide
4. Drift-Selbstanalyse: EDS-Findings im Drift-Repo sinken oder bleiben stabil;
   CXS→EDS-Oscillation in `nudge`-Ergebnis nicht mehr auslösbar für LOC<40-Helper
5. Mutation-Benchmark: EDS-Präzision fällt nicht unter Baseline

## Referenz-Artefakte

- `src/drift/signals/explainability_deficit.py` — Implementierung
- `tests/fixtures/ground_truth.py` — TN- und Boundary-Fixture
- `audit_results/fmea_matrix.md` — EDS-Zeile aktualisieren
- `audit_results/risk_register.md` — FN-Risiko für Private-Micro-Helper dokumentieren
- `benchmark_results/eds-private-helper-threshold-evidence.json` — Evidence-Artefakt
- `.github/prompts/drift-fix-loop.prompt.md` — Oscillation-Detection-Sektion

## Decision Trailer

```
Decision: proposed
Evidence: ADR-077 (this document)
Audit: fmea_matrix.md, risk_register.md pending update
Status: awaiting maintainer acceptance before signal-code change
```
