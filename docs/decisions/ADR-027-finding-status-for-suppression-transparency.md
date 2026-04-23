---
id: ADR-027
status: proposed
date: 2026-04-08
supersedes:
---

# ADR-027: Expliziter Finding-Status fuer Suppression-Transparenz

## Kontext

Drift blendet aktuell inline unterdrueckte Findings aus der primaeren Finding-Liste aus und zeigt nur einen Zaehler (`suppressed_count`). Dadurch kann in automatisierten Agenten-Workflows der Eindruck entstehen, dass Drift real reduziert wurde, obwohl Findings nur unterdrueckt wurden.

## Entscheidung

1. Wir fuehren additive Statusfelder auf `Finding` ein:
   - `status` (`active`, `suppressed`, `resolved`)
   - `status_set_by`
   - `status_reason`
2. Inline-Suppressions markieren Findings explizit als `suppressed` mit Herkunft `inline_comment`.
3. `RepoAnalysis` traegt suppresste Findings in einer separaten Liste (`suppressed_findings`) fuer maschinenlesbare Transparenz.
4. JSON-Output erweitert sich additiv um:
   - Statusfelder pro Finding
   - `findings_suppressed` (nur Full-JSON)
   - `compact_summary.suppressed_total`

### Was explizit nicht getan wird

- Keine Aenderung der Severity-Gate-Semantik in dieser Iteration.
- Kein neues Suppression-Policy-Format in dieser Iteration.
- Keine breaking schema changes; nur additive Felder.

## Begruendung

Die Trennung von `active` und `suppressed` ist die kleinste technisch robuste Aenderung, um False-Negative durch Suppression sichtbar zu machen, ohne bestehende Konsumenten zu brechen. Additive Felder erlauben schrittweise Adoption in CI und Agenten.

## Konsequenzen

- JSON-Schema-Minor wird auf `1.1` angehoben.
- Downstream-Consumer koennen weiterhin nur `findings` lesen; neue Transparenz ist opt-in.
- Grundlage fuer spaetere CI-Enforcement-Regeln (`no-new-suppressions`, Suppression-Budget) wird vorbereitet.

## Validierung

- [ ] `pytest tests/test_suppression.py -q --maxfail=1`
- [ ] `pytest tests/test_json_output.py -q --maxfail=1`
- [ ] `pytest tests/test_baseline.py -q --maxfail=1`
- [ ] `drift analyze --repo . --format json --exit-zero` enthaelt Statusfelder und `findings_suppressed`
- [ ] Lernzyklus-Ergebnis (Policy): bestaetigt | widerlegt | unklar | zurueckgestellt
