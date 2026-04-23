---
id: ADR-025
status: proposed
date: 2026-04-08
supersedes:
---

# ADR-025: Orchestration Layer — Workflow-Pläne, Typed Handoffs, Task-Graph, Autopilot

## Kontext

Die MCP-Tooling-Schicht (ADR-022 Sessions, ADR-024 Next-Step-Contracts, ADR-020/021 Batch-Metadata) liefert gute **Einzelschritt-Steuerung**. Der äußere Agent muss aber immer noch selbst die Reihenfolge orchestrieren, Abhängigkeiten zwischen Tasks einhalten und entscheiden, wann er fertig ist. Das erzeugt:

- Unnötige Latenz durch trial-and-error Orchestrierung
- Risiko falscher Reihenfolgen (z.B. abhängige Tasks parallel ausführen)
- Informationsverlust durch rollenfremde Response-Felder (Planner bekommt Code-Details, Coder bekommt Architektur-Overview)
- Manuellen Session-Aufbau (validate → scan → brief → fix_plan) bei jeder Session

**Kern-Lücken im Status Quo:**

| Capability | Status | Lücke |
|---|---|---|
| `next_tool_call` (ADR-024) | ✅ | Nur 1 Schritt voraus |
| `depends_on` auf AgentTask | ✅ | Kein `blocks`, `batch_group`, keine Topo-Sortierung |
| `DriftSession` (ADR-022) | ✅ | Kein Autopilot |
| `agent_instruction` (ADR-021) | ✅ | Keine Rollendifferenzierung |

## Entscheidung

Einführung einer **Orchestrierungs-Schicht** in 4 Phasen (A→B→C→D), jede eigenständig deploybar:

### Phase A — Task-Dependency-Graph

`AgentTask` erhält neue Felder: `blocks`, `batch_group`, `preferred_order`, `parallel_with`. Eine neue Funktion `build_task_graph()` in `api_helpers.py` erzeugt einen `TaskGraph` mit topologisch sortierten Tasks, Batch-Gruppen, Execution-Phasen und Critical-Path. Der Graph wird als `task_graph`-Feld in die `fix_plan()` Response integriert.

### Phase B — Typed Handoffs (Response Profile)

Neuer Parameter `response_profile` auf allen API-Funktionen mit Werten: `planner`, `coder`, `verifier`, `merge_readiness`, `default`. Jedes Profil filtert/erweitert Response-Felder rollenspezifisch. `default` erhält bisheriges Verhalten (backwards-compatible).

### Phase C — Workflow-Pläne als First-Class-Output

Neue Datenmodelle `WorkflowStep` und `WorkflowPlan`. Ein Plan-Generator erzeugt aus Analyse-Ergebnis + Task-Graph einen ausführbaren Multi-Step-Plan mit Preconditions, Parallelisierbarkeit, Abort-Criteria und Erfolgskriterium. Wird als `workflow_plan`-Feld in `scan()` (detailed) und `fix_plan()` Responses eingebettet.

### Phase D — Session-Autopilot

`drift_session_start` erhält einen `autopilot`-Parameter. Bei `autopilot=true`: validate → scan → brief → fix_plan → Plan-Generierung werden automatisch ausgeführt und als fertige Queue zurückgegeben.

### Phase E — Plan-Invalidierung mit Fingerprint und Repo-State-Binding

`WorkflowPlan` erhält neue Felder: `plan_id` (UUID), `created_at`, `depended_on_repo_state` (HEAD-Commit, Branch, affected-files-Hash), `plan_fingerprint` (SHA-256 über Steps+State), `invalidation_triggers`. Neue Funktion `validate_plan()` prüft den aktuellen Repo-State gegen den gespeicherten und gibt `{valid, reason, stale_files, recommendation}` zurück. Zwingender Re-Plan bei: HEAD-Commit geändert, Branch gewechselt, betroffene Datei modifiziert, abhängiger Task fehlgeschlagen, 2+ degrading Nudges.

### Phase F — Task-Verträge mit maschinenprüfbaren Boundaries

Task-Output erhält neue Felder: `allowed_files` (aus file_path + related_files), `completion_evidence` (Typ + Tool + Prädikat), optional `forbidden_files`, `expected_symbols`, `required_tests`, `required_audit_artifacts`, `max_files_changed`. `complete_task()` speichert `result` tatsächlich (Bugfix: bisher verworfen). Enforcement in 3 Stufen: Advisory → Warning → Blocking. `OrchestrationMetrics`-Dataclass auf `DriftSession` erfasst Session-Level-Metriken: Plans erstellt/invalidiert, Tasks claimed/completed/failed/expired, Nudge-Ergebnisse, Token-Schätzungen, Waste-Ratios.

### Phase G — Orchestrierungsmetriken und Claim-Guard

`OrchestrationMetrics`-Dataclass auf `DriftSession` erfasst Session-Level-Metriken: Plans erstellt/invalidiert, Tasks claimed/completed/failed/expired, Nudge-Ergebnisse, Token-Schätzungen, Waste-Ratios. Explicit Claim-Guard in `claim_task()` verhindert Doppel-Claims auch ohne vorheriges Reaping. `end_summary()` emittiert aggregierte Metriken via Telemetrie.

### Explizit nicht umgesetzt

- Retry-Logik im Agenten selbst (bleibt Agent-Verantwortung)
- MCP-Client-Implementierung
- Änderungen an Signalen, Scoring-Gewichten oder Output-Formaten (SARIF/Rich)
- Konfigurierbare Workflow-Templates (ggf. Phase 2)
- Agent-Registry mit kryptografischer Identität (ggf. spätere Phase)
- Step-Level Execution Tracking (ggf. Phase H, nach E–G stabil)

## Begründung

**Warum Bottom-Up (A→B→C→D)?** Phase C und D bauen auf dem Task-Graph (A) auf. Response-Profile (B) bestimmen, was im Plan angezeigt wird.

**Warum `response_profile` statt separater Endpoints?** Weniger API-Surface, backwards-compatible via Default-Wert, keine Tool-Explosion im MCP-Server.

**Warum `workflow_plan` als Response-Feld?** Plan entsteht aus dem Analyse-Kontext, der beim Tool-Call ohnehin verfügbar ist. Ein separater Endpoint müsste die Analyse wiederholen.

**Warum Autopilot als Flag auf `session_start`?** Der Warm-Up gehört logisch zur Session-Eröffnung, nicht in einen separaten Tool-Call.

**Alternativen verworfen:**
- Eigener `drift_plan` Tool-Call → erfordert Analyse-Duplikation oder Session-Pflicht
- Client-seitige Orchestrierung → genau das Problem, das gelöst werden soll
- Webhook-basierte Orchestrierung → zu komplex für lokale MCP-Nutzung

## Konsequenzen

**Positive:**
- Agent folgt dem Tool statt selbst zu orchestrieren → weniger Latenz, weniger Fehler
- Rollenspezifische Responses → weniger Token-Verbrauch, relevantere Information
- Autopilot → 1 Tool-Call statt 4-5 für Session-Setup
- Task-Graph → Abhängigkeiten maschinenlesbar, Parallelisierung explizit

**Negative / Trade-offs:**
- Mehr Komplexität in der API-Schicht (neues Modul, neue Datenmodelle)
- Response-Size wächst bei `detailed` + Workflow-Plan
- Plan-Invalidierung bei Repo-State-Änderung erfordert Re-Plan (akzeptiert, Warning genügt)
- Schema-Version bleibt 2.0 (additive Felder, kein Breaking Change)

## Validierung

```bash
# Phase A
pytest tests/test_task_graph.py -v

# Phase B
pytest tests/test_response_profiles.py -v

# Phase C
pytest tests/test_workflow_plan.py -v

# Phase D
pytest tests/test_session_autopilot.py -v

# Phase E–G
pytest tests/test_plan_invalidation.py tests/test_task_contracts.py tests/test_orchestration_metrics.py -v

# Regression
pytest tests/test_mcp_hardening.py tests/test_session.py tests/test_agent_tasks.py tests/test_task_queue.py -v

# Vollständig
make check
```

**Lernzyklus-Erwartung:** `bestätigt` wenn Agent-Loop-Latenz in Benchmarks messbar sinkt und Orchestrierungsfehler (falsche Reihenfolge, vergessene Steps) reduziert werden.
