---
id: ADR-041
status: proposed
date: 2026-04-10
supersedes:
---

# ADR-041: Scoring-Engine — Dampening k erhöhen und Breadth-Multiplier deckeln

## Kontext

Die FP-Reduktionsanalyse (work_artifacts/fp_reduction_2026-04-10/) identifizierte zwei systemische Score-Inflation-Mechanismen in `src/drift/scoring/engine.py`:

1. **Dampening-Sättigung bei k=10:** Die Formel `min(1, ln(1+n)/ln(1+k))` mit k=10 erreicht Dampening ≈ 1.0 bereits bei n≈10 Findings. Signale mit 20–55 Findings (z.B. EDS=55, MDS=22, AVS=21) erhalten den vollen Mean-Score ohne Volumen-Abzug. Das überhöht ihren Einfluss auf den Composite-Score.

2. **Unbegrenzter Breadth-Multiplier:** `impact = weight × score × (1 + log(1 + len(related_files)))`. Bei 1000 related_files erreicht der Multiplier ≈ 7.9×, was den Impact einzelner Findings künstlich aufbläht, obwohl die Evidenzstärke pro Datei nicht zunimmt.

**Empirische Basis (Self-Analysis v2.8.0):**
- EDS: 55 Findings, Dampening = 1.00 → mit k=20: 0.89 (−11%)
- MDS: 22 Findings, Dampening = 1.00 → mit k=20: 0.78 (−22%)
- PFS: 7 Findings, Dampening = 0.89 → mit k=20: 0.58 (−35%)

## Entscheidung

### P3: Dampening-Konstante von 10 auf 20 erhöhen

`_DAMPENING_K = 20` — bewirkt, dass Signale erst ab ~20 Findings den vollen Mean-Score erhalten. Signale mit 5–15 Findings werden stärker gedämpft, was die Differenzierungsfähigkeit verbessert.

### P4: Breadth-Multiplier mit Cap von 4.0 deckeln

`breadth = min(BREADTH_CAP, 1 + log(1 + len(related_files)))` mit `_BREADTH_CAP = 4.0`. Das begrenzt den Impact-Multiplikator auch bei sehr großen Cluster-Findings.

### Was explizit nicht getan wird

- Gewichte (SignalWeights) werden NICHT geändert — ADR-003-kalibriert.
- dominance_cap wird NICHT geändert (aktuell kein Trigger).
- Kein neues Signal, kein neuer Output-Kanal.

## Begründung

**Warum k=20?** Verdopplung bietet bessere Differenzierung für Signale mit 10–20 Findings (häufigster Bereich bei realen Repos), ohne Signale mit <5 Findings zu stark zu dämpfen. k=30 wäre zu aggressiv und würde FN-Risiko bei kleinen Repos erhöhen.

**Warum Cap=4.0?** Bei 4.0 entspricht der Multiplikator ~50 related_files (`1 + log(1+50) ≈ 4.0`). Darüber hinaus liefert Breadth keinen zusätzlichen Evidenzwert — ein Finding mit 1000 related_files ist nicht 16× wichtiger als eines mit 5.

**Verworfene Alternativen:**
- k=15 (zu konservativ, kaum Verbesserung für EDS/MDS)
- k=30 (zu aggressiv, FN-Risiko bei Repos mit 10–15 echten Findings)
- Cap=3.0 (würde Breadth-Differenzierung für 10–50 Files beschneiden)
- Cap=6.0 (zu wenig Begrenzungswirkung)

## Konsequenzen

- `drift_score` ändert sich für alle Repos — Baselines müssen nach Merge regeneriert werden.
- Delta-Gate-Vergleiche gegen alte Baselines schlagen fehl → Baseline-Regeneration erforderlich.
- Signale mit 10–20 Findings verlieren 15–35% Score — das ist gewollt.
- FN-Risiko bei Signalen mit <5 Findings ist minimal (dort wirkt bereits der alte k=10-Dampening).
- Breadth-Cap betrifft primär AVS/PFS/CCC-Findings mit großen Clustern.

## Validierung

```bash
# 1. Unit-Tests grün
pytest tests/test_scoring.py tests/test_scoring_edge_cases.py -v --tb=short

# 2. Self-Analysis Vergleich
drift analyze --repo . --format json --exit-zero > /tmp/after.json
# drift_score sollte sinken (weniger Inflation)

# 3. Precision/Recall-Baseline
pytest tests/test_precision_recall.py -v -k "not cxs_boundary_threshold"

# 4. Mutation Benchmark
python scripts/_mutation_benchmark.py
```

**Erwartetes Lernzyklus-Ergebnis:** bestätigt — wenn drift_score sinkt und P/R stabil bleibt; widerlegt — wenn Recall signifikant fällt.
