---
id: ADR-090
status: proposed
date: 2026-04-22
supersedes:
---

# ADR-090: Agent-Telemetrie-Block im Output-Schema (Schema 2.2)

## Kontext

ADR-089 kodiert einen autonomen Regelkreis in `drift.agent.prompt.md`. Der
Regelkreis sieht vor, dass der Agent seine Aktionen (AUTO-Fix, REVIEW-Request,
BLOCK-Notation, Revert) in einem maschinenlesbaren Feld
`agent_telemetry.agent_actions_taken` dokumentiert. Zum Zeitpunkt von ADR-089
existiert dieses Feld noch nicht; der Prompt enthält deshalb den Platzhalter
_"sobald Schema 2.2 aktiv ist, siehe Paket 1B"_.

Das aktuelle Output-Schema (Version "2.1", `OUTPUT_SCHEMA_VERSION` in
`src/drift/models/_enums.py`) enthält keinen `agent_telemetry`-Schlüssel.
Ohne dieses Feld kann der Agent seine Aktionen nur in freiem Text im
`work_artifacts/agent_run_*.md` dokumentieren, was:

- für maschinelle Auswertung (CI, MCP-Tools) unzureichend ist,
- keine strukturierten Queries auf "welche Findings wurden AUTO-repaired?"
  erlaubt,
- `verify_gate_not_bypassed.py` (Paket 2B) zwingt auf Markdown-Parsen statt
  strukturiertes JSON.

## Entscheidung

Das Output-Schema wird auf **Version 2.2** angehoben. Die einzige Änderung
gegenüber 2.1 ist ein optionales, additives `agent_telemetry`-Feld.

### Neue Typen in `src/drift/models/_findings.py`

**`AgentAction`** — eine einzelne Aktion des autonomen Agenten:

| Feld | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `action_type` | `str` (AgentActionType) | JA | Was der Agent tat |
| `reason` | `str` | JA | Warum diese Aktion |
| `finding_id` | `str \| None` | NEIN | Fingerprint des adressierten Findings |
| `severity` | `str \| None` | NEIN | Severity zum Zeitpunkt der Aktion |
| `gate` | `str \| None` | NEIN | Routing-Entscheidung (AUTO/REVIEW/BLOCK) |
| `safe_to_commit` | `bool \| None` | NEIN | Nudge-Ergebnis zum Zeitpunkt |
| `feedback_mark` | `str \| None` | NEIN | Wert aus `drift feedback` |
| `timestamp` | `str \| None` | NEIN | ISO-8601-Zeitstempel |
| `metadata` | `dict` | NEIN | Erweiterungsraum ohne Schema-Bruch |

**`AgentTelemetry`** — Telemetrie-Block für einen Analyse-Zyklus:

| Feld | Typ | Bedeutung |
|---|---|---|
| `schema_version` | `str` | Immer `"2.2"` |
| `session_id` | `str \| None` | Optionaler MCP-Session-Identifier |
| `agent_actions_taken` | `list[AgentAction]` | Geordnete Aktionsliste |
| `total_auto` | `int` (property) | Anzahl AUTO-Aktionen |
| `total_review` | `int` (property) | Anzahl REVIEW-Requests |
| `total_block` | `int` (property) | Anzahl BLOCK-Notationen |

**`AgentActionType`** — StrEnum in `src/drift/models/_enums.py`:

```
auto_fix | review_request | block | revert | feedback | nudge
```

### Änderungen am Datenmodell

`RepoAnalysis` erhält ein neues optionales Feld:

```python
agent_telemetry: AgentTelemetry | None = None
```

`drift analyze` schreibt dieses Feld **nicht** (bleibt `null`). Der autonome
Agent schreibt die Einträge nach erfolgter Analyse in das gelesene
JSON-Artefakt. Damit ist `agent_telemetry` ein Agent-beschreibbares Protokoll-
feld, kein Analyse-Output.

### JSON-Output

`analysis_to_json()` serialisiert `agent_telemetry` in den Top-Level-Key
`"agent_telemetry"` — entweder `null` (wenn nicht gesetzt) oder:

```json
{
  "schema_version": "2.2",
  "session_id": null,
  "total_auto": 1,
  "total_review": 0,
  "total_block": 0,
  "agent_actions_taken": [
    {
      "action_type": "auto_fix",
      "reason": "reverted_on_degrading",
      "finding_id": "abc123",
      "severity": "low",
      "gate": "AUTO",
      "safe_to_commit": false,
      "feedback_mark": null,
      "timestamp": "2026-04-22T12:00:00Z",
      "metadata": {}
    }
  ]
}
```

### Schema-Version

`OUTPUT_SCHEMA_VERSION` in `src/drift/models/_enums.py` wird von `"2.1"` auf
`"2.2"` angehoben. Die Änderung ist **additiv** (kein Feld entfernt oder
umbenannt); Consumer, die `"2.1"` erwarten, können das neue Feld ignorieren.

## Begründung

**Additiver Top-Level-Key** statt eingebettetes Feld: `agent_telemetry` auf
Top-Level (neben `findings`, `trend`, …) macht es für CI-Tools findbar ohne
Traversierung, und erlaubt spätere Erweiterung (z. B. `agent_telemetry_v2`)
ohne Break.

**Optionales Feld / `null` default**: `drift analyze` selbst schreibt keine
Telemetrie — es gibt keine Aktionen zu berichten. Der Agent schreibt das Feld
nachträglich. Das Null-Default ist explizit im Schema (kein "fehlendes Feld"),
damit Consumer robust implementieren können.

**StrEnum statt freier String für `action_type`**: Schließt gegen freie
Strings, die `verify_gate_not_bypassed.py` nicht auswerten kann. Neue
Aktionstypen erfordern bewusste Enum-Erweiterung + ADR-Bewertung.

**Keine Breaking Change**: Schema 2.2 ist vollständig rückwärtskompatibel zu
2.1. Consumer mit `schema_version_min: "2.1"` können das neue Feld ignorieren.

## Konsequenzen

**Positiv**

- Der Agent hat ein strukturiertes, maschinenlesbares Protokoll seiner Aktionen.
- `verify_gate_not_bypassed.py` kann optional gegen JSON statt Markdown prüfen.
- CI kann auf "BLOCK ohne Approval" queryen ohne Markdown-Parsen.
- Grundlage für Paket 3A (E2E Agent-Loop-Benchmark mit Aktionsverteilung).

**Akzeptierte Trade-offs**

- Die JSON-Ausgabe wächst um einen `null`-Key, wenn kein Agent aktiv war.
  Overhead ist minimal (<50 Bytes).
- Consumer, die das Schema streng auf Version "2.1" validieren, müssen
  auf "2.2" aktualisieren.

**Negativ / Risiken**

- Feld wird nur sinnvoll, wenn der Agent das Format tatsächlich einhält.
  Mitigiert durch Contract-Tests in `tests/test_agent_telemetry_schema.py`.

## Validierung

- `tests/test_agent_telemetry_schema.py` muss grün sein; prüft:
  - `OUTPUT_SCHEMA_VERSION == "2.2"`
  - `AgentTelemetry` ist in `drift.models` importierbar
  - `AgentAction`-Felder haben korrekte Defaults
  - `total_auto/review/block`-Properties zählen korrekt
  - `analysis_to_json()` enthält `"agent_telemetry": null` wenn kein Agent aktiv
  - `analysis_to_json()` serialisiert `AgentTelemetry` vollständig wenn gesetzt
  - `schema_version` im JSON ist `"2.2"`
