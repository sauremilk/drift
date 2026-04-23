---
id: ADR-072
status: proposed
date: 2026-04-17
supersedes:
---

# ADR-072: Remediation Memory — Outcome-Informed Fix Recommendations

## Kontext

Agenten wiederholen gescheiterte Fix-Strategien, weil `fix_plan`-Tasks keine
Information über vergangene Outcomes enthalten. Die `RepairTemplateRegistry`
(ADR-065) trackt bereits Outcomes per (signal, edit_kind, context_class), aber:

1. Outcome-Records enthalten keine `new_findings_count` oder `resolved_count`
   — die Regressions-Granularität fehlt.
2. Session-End persistiert Outcomes nicht automatisch — nur explizite
   `record_outcome()`-Aufrufe werden erfasst.
3. `fix_plan`-Tasks exponieren `template_confidence` und `regression_guidance`,
   aber keine aggregierten Outcome-Statistiken (`similar_outcomes`).

## Entscheidung

### Was getan wird

1. **Outcome-Records erweitern**: `new_findings_count` und `resolved_count`
   als optionale Felder in `record_outcome()`.
2. **Auto-Persist bei Session-End**: `SessionManager.destroy()` iteriert
   `completed_results` und persistiert für jeden abgeschlossenen Task einen
   Outcome-Record in der Registry.
3. **`similar_outcomes`-Feld in fix_plan-Tasks**: Jeder Task enthält eine
   kompakte Zusammenfassung vergangener Outcomes für seine (signal, edit_kind)-
   Kombination.

### Was explizit nicht getan wird

- Kein neuer Persistenz-Layer — nutzt bestehende `outcomes.jsonl` (ADR-065).
- Keine Änderung an Signalen, Scoring oder Output-Schema.
- Kein team-shared Outcome-Store (bleibt user-local per `.gitignore`).

## Begründung

Die Registry-Infrastruktur existiert. Die Erweiterung ist ein Aufsatz auf
vorhandene Mechanismen, kein neues Subsystem. Das `similar_outcomes`-Feld
gibt Agenten Evidenz statt Instruktionen — sie können informiert entscheiden,
welche Strategie sie verfolgen.

## Konsequenzen

- Outcome-Records werden um ~2 Felder größer.
- Session-End wird ~10–50ms langsamer (JSONL-Writes pro Task).
- `similar_outcomes` erhöht fix_plan-Response-Größe um ~50–100 Bytes pro Task.

## Validierung

```bash
pytest tests/test_remediation_memory.py -v
pytest tests/test_session.py -v --tb=short
```

Erwartetes Lernzyklus-Ergebnis: `bestätigt` wenn Agent-Rückfallrate in
Self-Scan-Fix-Loops sinkt; `unklar` wenn Outcome-Daten zu dünn für Konfidenz.
