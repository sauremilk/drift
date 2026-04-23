---
id: ADR-062
status: proposed
date: 2026-04-11
supersedes: ADR-025
---

# ADR-062: Session-Autopilot Payload Compaction als Default

## Kontext

`drift_session_start(autopilot=true)` liefert derzeit eine voll eingebettete Payload (`validate`, `brief`, `scan`, `fix_plan`). Diese Vollausgabe ist fuer Agent-Loops oft groesser als notwendig und verbraucht unnoetig Tokens, obwohl die erste Aktion in der Praxis fast immer `drift_fix_plan(session_id=...)` ist.

## Entscheidung

Wir fuehren fuer `drift_session_start` einen neuen Parameter `autopilot_payload` ein und stellen den Default auf ein kompaktes Summary-Format um.

- `autopilot_payload="summary"` (Default):
  - Liefert im Feld `autopilot` nur kompakte Steuerdaten: `drift_score`, `task_count`, `top_signals`, `next_tool_call`.
  - Liefert kleine Vorschauen (`findings_preview`, `tasks_preview`, `guardrails_preview`) mit `total_available`.
  - Lagert Vollinhalte aus und liefert stattdessen Referenzen mit Checksummen (`payload_refs`) fuer On-Demand-Nachladen ueber bestehende Tools.
- `autopilot_payload="full"`:
  - Behaelt das heutige Verhalten mit voll eingebettetem `validate`/`brief`/`scan`/`fix_plan`.

Zusaetzlich wird `agent_instruction` fuer den Autopilot-Pfad auf eine kurze Form reduziert.

Nicht im Umfang:

- Keine neuen MCP-Tools.
- Keine Aenderung an Signalheuristiken, Scoring oder Audit-Artefakten.
- Keine Aenderung am Single-Analysis-Prinzip im Autopilot-Pfad.

## Begründung

Der Summary-Default reduziert den Token-Verbrauch deutlich, ohne den Workflow zu verschlechtern: Details sind ueber bestehende Tools sofort nachladbar. Durch den expliziten `full`-Modus bleibt Rueckwaertskompatibilitaet fuer Clients erhalten, die die eingebettete Vollstruktur benoetigen.

## Konsequenzen

Positiv:

- Weniger Response-Groesse im Standardpfad.
- Schnellere Agent-Orchestrierung durch kompakte Startantwort.
- Klarere Trennung zwischen Steuerdaten und Detaildaten.

Trade-offs:

- Clients, die bisher implizit Vollausgabe erwarteten, muessen ggf. `autopilot_payload="full"` setzen.
- Zusaetzlicher Pflegeaufwand fuer zwei Payload-Modi.

## Validierung

- `pytest tests/test_mcp_hardening.py -k "session_start_autopilot" -q`
- `pytest tests/test_mcp_copilot.py -k "session_start" -q`
- `pytest tests/test_negative_context_export.py -k "tool_catalog" -q`
- `ruff check src/drift/mcp_server.py tests/test_mcp_hardening.py`

Policy §10 Lernzyklus-Ergebnis: unklar.
