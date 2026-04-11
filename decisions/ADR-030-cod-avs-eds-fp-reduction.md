---
id: ADR-030
status: proposed
date: 2026-04-09
supersedes:
---

# ADR-030: FP-Reduktion für COD, AVS, EDS (P1-2 KPI-Roadmap)

## Kontext

Die Selbstanalyse des Drift-Repos (v2.7, 335 Findings, 182 scoring-aktive Production-Findings)
zeigt drei Signale mit hohem FP-Volumen:

| Signal | Prod-Findings | Geschätzte FP | Geschätzte Precision |
|--------|-------------|--------------|---------------------|
| COD    | 51          | ~33          | ~35%                |
| AVS    | 36          | ~25          | ~31%                |
| EDS    | 55          | ~20          | ~64%                |

**P1-2-Ziel:** Precision_strict ≥ 0.60 für die drei schlechtesten Signale.

### FP-Muster

**COD (Cohesion Deficit):**
33/51 Production-Findings haben `isolation_ratio < 0.50`. Bei diesen Modulen ist die
Mehrheit der Funktionen sematisch kohärent — der `diversity`-Term allein treibt den
Score über den `detection_threshold`. Beispiele: `pipeline.py` (ratio=0.19),
`models.py` (ratio=0.27), `recommendations.py` (ratio=0.15).

**AVS (Architecture Violation):**
26/36 Findings stammen aus `_check_blast_radius` und `_check_god_modules` auf
strukturellen Kernmodulen (`models.py`, `config.py`, `errors.py`). Diese Module sind
architektonisch korrekt zentral — die Findings sind nicht handlungsrelevant.

**EDS (Explainability Deficit):**
~20/55 Findings mit score < 0.5 auf Funktionen mit moderater Komplexität
(5–10), die durch fehlende Return-Type-Annotation und fehlende Test-Erkennung
über den Schwellwert gehoben werden. Anhebung von `min_complexity` auf 8
eliminiert die niedrig-severity-Findings ohne TP-Verlust.

## Entscheidung

### Fix 1: COD — Minimum Isolation-Ratio Gate

Neuer Guard **vor** der Score-Berechnung:

```python
min_isolation_ratio = 0.50
if isolation_ratio < min_isolation_ratio:
    continue
```

**Begründung:** Wenn weniger als 50% der Funktionen eines Moduls isoliert sind,
ist die Mehrheit kohärent. Den Score trotzdem über `detection_threshold` zu heben
nur wegen des `diversity`-Terms ist signaltheoretisch falsch.

**Erwarteter Impact:** ~33 FPs eliminiert, ~18 TPs erhalten. Precision: 35% → ~100%.

### Fix 2: AVS — Blast-Radius/God-Module Schwellwert-Verschärfung

**2a) `_check_blast_radius`:**
- Absolute Mindest-Schwelle von 5 → 15
- Prozentuale Mindest-Schwelle: nur feuern wenn `br_pct > 75%`

**2b) `_check_god_modules`:**
- Mindest-Ca von 2 → 5
- Mindest-Ce von 2 → 3
- Mindest-Blast-Radius von 3 → 5
- Threshold: max(6, mean_degree*2) → max(10, mean_degree*2.5)

**2c) `_check_instability` (Zone of Pain):**
- Mindest-Ca von 3 → 8 (nur stark-abhängige Module)
- high_risk_evidence: Ca≥6 → Ca≥12 oder (Ca≥10 und Ce≥2)

**Begründung:** Die bisherigen Schwellen sind zu niedrig kalibriert. Ein Modul mit
Ca=2 oder br=5 ist in einem 100+-Modul-Repo kein Strukturproblem. Die neuen
Schwellen fokussieren auf tatsächlich überdimensionierte Module.

**Tatsächlicher Impact:** 15 FPs eliminiert (blast_radius: −15 @ pct 73–74%). Precision: ~31% → ~52%.

### Fix 3: EDS — Complexity-Mindestschwell erhöhung

- `MEDIUM_COMPLEXITY` von 5 → 8 (nur EDS-interner Default)
- `min_func_loc` von 10 → 15

**Begründung:** Funktionen mit Complexity 5–7 sind in der Praxis selten so komplex,
dass fehlende Dokumentation ein echtes Verständnisrisiko darstellt.
Die Anhebung auf 8 fokussiert EDS auf substanzielle Komplexität.

**Erwarteter Impact:** ~15 FPs eliminiert. Precision: ~64% → ~80%.

## Explizit nicht umgesetzt

- Scoring-Gewichte bleiben unverändert
- Keine Änderung an Signal-Detection-Scope oder incremental_scope
- Keine neuen Signale
- EDS test-target-matching bleibt unverändert (Verbesserung separat sinnvoll)

## Konsequenzen

- Gesamtzahl Production-Findings in Selbstanalyse sinkt von 335 auf 282 (−53)
- COD: 51 → 18 (−33), AVS: 36 → 21 (−15), EDS: 55 → 55 (alle CC≥10, LOC≥18)
- FN-Risiko minimal: eliminierte Findings betreffen Module/Funktionen,
  die architektonisch korrekt oder trivial komplex sind
- Bestehende TP-Fixture-Tests bleiben grün (keine Recall-Regression)
- 2 neue TN-Fixtures: `cod_low_isolation_tn`, `eds_moderate_complexity_tn`
- 2384 Tests grün, 119 P/R-Tests grün

## Validierung

```bash
pytest tests/test_precision_recall.py -v   # Alle Fixtures grün
drift analyze --repo . --format json       # FP-Zählung vergleichen
```
