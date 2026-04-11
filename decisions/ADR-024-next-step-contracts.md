---
id: ADR-024
status: proposed
date: 2026-04-08
supersedes:
---

# ADR-024: Maschinenlesbare Next-Step-Verträge in API-Antworten

## Kontext

Drift liefert agent-orientierte Steuerungsinformationen über zwei Freitextfelder:

- `agent_instruction: str` — kontextabhängige Handlungsanweisung als Prosatext
- `recommended_next_actions: list[str]` — Aktionsliste als natürlichsprachliche Strings

Beide Felder erfordern Natural-Language-Parsing durch den konsumierenden Agenten. In der Praxis führt das zu:

1. **Halluzinationen im Agent-Loop**: Agenten interpretieren Freitext-Instruktionen kreativ statt deterministisch — z.B. wird `"Use drift_fix_plan"` zu einem `drift_scan`-Call umgedeutet.
2. **Fehlende Abbruchbedingung**: Ohne maschinenlesbares `done_when`-Prädikat drehen Agenten Loops weiter, obwohl das Ziel bereits erreicht ist.
3. **Kein Fallback-Pfad**: Bei Tool-Fehlern hat der Agent keine strukturierte Alternative und improvisiert.

ADR-020 und ADR-021 haben die Batch-Orchestrierung und die Konsistenz der `agent_instruction`-Texte verbessert. Der nächste Hebel ist die Aufwertung von Text zu maschinenlesbaren Contracts.

## Entscheidung

### Was getan wird

Jede agent-orientierte API-Antwort (scan detailed, diff, fix_plan, nudge, brief, negative_context) erhält drei zusätzliche Top-Level-Felder:

```json
{
  "next_tool_call": {
    "tool": "drift_fix_plan",
    "params": {"max_tasks": 20, "signal": "PFS"}
  },
  "fallback_tool_call": {
    "tool": "drift_explain",
    "params": {"signal": "PFS"}
  },
  "done_when": "accept_change == true AND blocking_reasons is empty"
}
```

**Feldspezifikation:**

| Feld | Typ | Nullable | Beschreibung |
|------|-----|----------|--------------|
| `next_tool_call` | `{"tool": str, "params": dict}` | Ja | Empfohlener nächster MCP-Tool-Aufruf. `null` wenn keine Aktion nötig (z.B. findings == 0). |
| `fallback_tool_call` | `{"tool": str, "params": dict}` | Ja | Alternative bei Fehler oder wenn next_tool_call nicht anwendbar. |
| `done_when` | `str` | Nein | Maschinenlesbares Abbruch-Prädikat — beschreibt den Zielzustand, bei dem der Agent den aktuellen Loop beenden soll. |

**Contracts pro Endpunkt:**

| Endpunkt | next_tool_call | fallback_tool_call | done_when |
|----------|-----------------|---------------------|-----------|
| scan (detailed, findings > 0) | `drift_fix_plan` | `drift_explain(signal=top)` | `accept_change == true AND blocking_reasons is empty` |
| scan (detailed, findings == 0) | `null` | `null` | `drift_score == 0.0 OR findings_returned == 0` |
| diff (degraded) | `drift_fix_plan` | `drift_scan(response_detail=concise)` | `accept_change == true` |
| diff (improved, accept) | nächstes Batch-Target oder `null` | `null` | `accept_change == true AND blocking_reasons is empty` |
| diff (no_staged_files) | `null` | `null` | `staged files exist` |
| fix_plan (batch_eligible) | `drift_diff(uncommitted=true)` | `drift_nudge` | `drift_diff.accept_change == true` |
| fix_plan (no batch) | `drift_nudge` | `drift_diff(uncommitted=true)` | `drift_diff.accept_change == true` |
| nudge (safe_to_commit) | `drift_diff(staged_only=true)` | `null` | `drift_diff.accept_change == true` |
| nudge (not safe) | `drift_fix_plan` | `drift_scan(response_detail=concise)` | `safe_to_commit == true` |
| brief | `drift_negative_context` oder `drift_scan` (risk-abhängig) | `drift_nudge` | `task completed AND drift_nudge.safe_to_commit == true` |
| negative_context | `drift_nudge` | `drift_scan(response_detail=concise)` | `drift_nudge.safe_to_commit == true` |

**Error-Responses** erhalten `recovery_tool_call` (statt `next_tool_call`) mit derselben Shape, wenn `recoverable == true`.

**Session-Enrichment:** Wenn eine Session aktiv ist, wird `session_id` automatisch in `next_tool_call.params` und `fallback_tool_call.params` injiziert.

### Was explizit nicht getan wird

- **Kein Entfernen bestehender Felder**: `agent_instruction` und `recommended_next_actions` bleiben unverändert. Die neuen Felder ergänzen, ersetzen nicht.
- **Kein Schema-Version-Bump**: Alle neuen Felder sind additiv und optional — Schema bleibt `"2.0"`.
- **Kein strukturiertes done_when-Objekt**: `done_when` bleibt ein Predicate-String, keine Expression-Language.
- **Kein Contract für explain()**: explain ist informativ/terminal, kein Loop-Schritt.
- **Keine Agent-seitige Validierung**: Contracts sind Empfehlungen — der Agent darf abweichen wenn der Kontext es erfordert.

## Begründung

**Warum Predicate-Strings statt strukturierter Conditions?**
LLMs interpretieren natürlichsprachliche Prädikate (`"accept_change == true AND ..."`) zuverlässiger als verschachtelte JSON-Bedingungsobjekte. Der Implementierungsaufwand einer Expression-Language wäre unverhältnismäßig hoch für den erwarteten Gewinn.

**Warum `next_tool_call` statt nur `recommended_next_actions` erweitern?**
`recommended_next_actions: list[str]` mischt Prosa mit Tool-Namen. Eine strikte Tool+Params-Shape ermöglicht direkte Invocation ohne NL-Parsing.

**Warum Error recovery_tool_call statt next_tool_call?**
Semantische Klarheit: Error-Recovery ist kein "nächster Schritt im Workflow", sondern eine Wiederherstellungsmaßnahme.

## Konsequenzen

- **Positiv**: Reduktion von Agent-Loop-Halluzinationen; deterministischer Workflow ohne NL-Parsing
- **Positiv**: Abbruchbedingung verhindert endlose Loops
- **Neutral**: Leichte Vergrößerung der Response-Payload (3 Felder, nullable)
- **Trade-off**: `done_when` als String ist nicht maschinell evaluierbar — Agenten müssen es weiterhin interpretieren
- **Risk**: Contract-Inkonsistenz wenn neue Tools hinzugefügt werden ohne Contract-Update (Mitigation: Shape-Tests + Konstanten-basierte Tool-Namen)

## Validierung

1. **Shape-Tests**: Jeder Endpunkt-Response enthält die drei Felder mit korrekter Shape (tool=string, params=dict, done_when=string)
2. **Rückwärtskompatibilität**: Bestehende `agent_instruction`-Tests bleiben grün
3. **Funktional**: `drift scan --repo . --format json` enthält `next_tool_call` im Output
4. **Session-Injection**: Session-aktive Responses haben `session_id` in Contract-Params
5. **Lernzyklus**: Nach 4 Wochen Field-Test mit Agent-Loops → Halluzinations-Rate vor/nach vergleichen → bestätigt | widerlegt | unklar | zurückgestellt
