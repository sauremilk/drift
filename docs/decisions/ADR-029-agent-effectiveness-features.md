---
id: ADR-029
status: proposed
date: 2026-04-09
supersedes:
---

# ADR-029: Agent-Effectiveness Features

## Kontext

Drift wird primär von KI-Agenten genutzt. Aktuell fehlen Mechanismen, die Agenten helfen, ihre Arbeit besser zu steuern:

1. **Kein deklaratives Ziel**: Agenten können nicht in drift.yaml angeben, was ihr Auftrag ist und was außerhalb liegt.
2. **Kein Tool-Signaling**: MCP-Tools kommunizieren nicht, wie teuer oder riskant ein Aufruf ist.
3. **Kein Outcome-Reward**: Signal-Count dient als impliziter Erfolgsproxy statt echter Qualitätsmetriken.
4. **Kein Qualitäts-Feedback**: Schwankungen zwischen Runs werden nicht erkannt oder kommuniziert.
5. **Kein JIT-Kontext**: Agenten erhalten alle Informationen im System-Prompt statt just-in-time vor Entscheidungen.
6. **Keine progressive Werkzeugvergabe**: Alle Tools sind sofort verfügbar, was den Entscheidungsraum unnötig groß macht.
7. **Kein aktiver Korrekturkreis**: Pre-Call-Hinweise fehlen, wenn ein Aufruf nicht zum deklarierten Ziel passt.
8. **Kein vollständiger Trace**: Tool-Aufrufe und Entscheidungen werden nicht session-lokal verfolgt.

## Entscheidung

Acht additive Erweiterungen werden implementiert:

### Was wird getan

1. **AgentObjective** in drift.yaml (`config.py`): optionale Deklaration von `goal`, `out_of_scope`, `success_criteria`.
2. **ToolCostMetadata** (`tool_metadata.py`): statische Metadaten (cost, risk, latency, token_estimate) für alle MCP-Tools.
3. **QualityMetrics** (`session.py`): Proxy-Precision/Recall (operational findings ratio) in OrchestrationMetrics.
4. **QualityDrift-Detection** (`quality_gate.py`): Vergleich zwischen Runs → improving/stable/degrading + advisory.
5. **JIT Context Hints** (`tool_metadata.py`): prerequisite_tools, when_to_use, when_not_to_use pro Tool.
6. **Progressive Tool Disclosure** (`session.py`): Phase-basierte Tool-Empfehlung (init→scan→fix→verify→done).
7. **Pre-Call Advisory** (`mcp_server.py`): leichtgewichtige Prüfung vor jedem Tool-Call (Phase, Scope, Redundanz).
8. **Session Trace** (`session.py` + MCP-Tool): TraceEntry-Log + `drift_session_trace` Tool.

### Was explizit nicht getan wird

- Keine Breaking Changes an bestehenden Config-Feldern oder MCP-Tool-Signaturen.
- Keine echte Precision/Recall-Berechnung (benötigt Ground-Truth, die zur Laufzeit nicht verfügbar ist) — nur Proxy-Metriken.
- Keine automatische Tool-Blockade — Progressive Disclosure und Advisories sind Hinweise, keine Sperren.
- Keine Änderung an Signalen, Scoring-Logik oder Output-Formaten.
- Kein Persistent State über Sessions hinweg für quality_gate (vermeidet IO-Dependency).

## Begründung

- **Additive Erweiterungen** minimieren Regressionsrisiko und benötigen keine Audit-Updates (kein Signal/Ingestion/Output-Pfad betroffen).
- **Statische ToolCostMetadata** statt Runtime-Messung: einfacher zu pflegen, deterministisch, kein Performance-Overhead.
- **Proxy-Metriken für P/R**: operational findings ratio und suppression rate sind zur Laufzeit verfügbar und geben qualitatives Signal. Echte P/R bleibt explizites Follow-up.
- **Soft Progressive Disclosure**: Agenten bleiben unbeschränkt, erhalten aber klare Orientierung. Blocking würde Agenten in Edge Cases behindern.
- **Session-lokaler Trace**: Ergänzt die bestehende JSONL-Telemetrie ohne sie zu ersetzen. Kein neuer IO-Pfad.

Alternativen verworfen:
- **Echte P/R zur Laufzeit**: Benötigt Ground-Truth-Mapping von Findings zu echten Problemen, das ist zur Analysezeit nicht verfügbar.
- **MCP tools/list Metadata-Injection**: FastMCP hat keine native API dafür. Cost-Metadata über `get_tool_catalog()` und enriched responses ist ausreichend.
- **Hard Tool-Blocking**: Würde Agenten in unerwarteten Situationen behindern und Workarounds provozieren.

## Konsequenzen

- `DriftConfig` erhält ein neues optionales `agent` Feld — bestehende drift.yaml Dateien bleiben kompatibel.
- `DriftSession` wird um ~6 neue Felder erweitert (phase, trace, run_history, agent_objective, quality_metrics Felder).
- MCP-Responses werden um optionale Felder angereichert (quality_drift, context_hint, available_tools, advisory).
- Zwei neue Module: `tool_metadata.py`, `quality_gate.py`.
- Ein neues MCP-Tool: `drift_session_trace`.
- `get_tool_catalog()` wird um cost_metadata erweitert.
- Keine Audit-Artefakt-Updates erforderlich (kein Signal/Ingestion/Output-Pfad betroffen).

## Validierung

```bash
pytest tests/test_agent_effectiveness.py tests/test_tool_metadata.py tests/test_quality_gate.py -v
pytest tests/test_session.py tests/test_mcp_copilot.py tests/test_mcp_hardening.py -v
ruff check src/drift/ tests/
python -m mypy src/drift
```

Erwartetes Lernzyklus-Ergebnis: **bestätigt** — wenn nutzende Agenten die neuen Felder konsumieren und messbar weniger redundante Tool-Calls und out-of-scope-Arbeit produzieren. **unklar** — wenn die Proxy-Metriken für P/R keinen Informationsgewinn bringen. **zurückgestellt** — wenn echte P/R-Integration in einem Follow-up-ADR adressiert wird.
