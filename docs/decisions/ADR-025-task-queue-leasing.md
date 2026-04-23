---
id: ADR-025
status: proposed
date: 2026-04-08
supersedes:
---

# ADR-025: Task-Queue-Leasing für Multi-Agent-Koordination

## Kontext

Sessions (ADR-022) verwalten Scope, Scan-Zustand und Fix-Plan-Queue, aber die
Zuweisung einzelner Tasks an Agenten bleibt dem äußeren Orchestrator überlassen.
Sobald mehrere Agenten oder Rollen (z.B. Fixer + Reviewer) parallel an einer
Session arbeiten, fehlt ein Mechanismus gegen Doppelbearbeitung: zwei Agenten
können denselben Befund gleichzeitig bearbeiten oder sich gegenseitig
überholen.

Das Batch-Repair-Protokoll (ADR-020/021) setzt ebenfalls voraus, dass
Tasks eindeutig zugewiesen und nach Abschluss markiert werden, liefert aber
keine atomische Garantie gegen Race Conditions im Agentenfeld.

## Entscheidung

`DriftSession` erhält eine Lease-basierte Task-Queue mit folgenden Primitiven:

| Operation | Methode | MCP-Tool |
|-----------|---------|----------|
| Claim | `claim_task(agent_id, task_id?, lease_ttl, max_reclaim)` | `drift_task_claim` |
| Renew | `renew_lease(agent_id, task_id, extend_seconds)` | `drift_task_renew` |
| Release | `release_task(agent_id, task_id, max_reclaim)` | `drift_task_release` |
| Complete | `complete_task(agent_id, task_id, result?)` | `drift_task_complete` |
| Status | `queue_status()` | `drift_task_status` |

**Designentscheidungen:**

- **Session-scoped:** Jede Session hat ihre eigene Queue. Kein
  cross-session Queue-Manager.
- **FIFO-Claim:** Ohne explizite `task_id` wird der älteste pending Task
  gewählt (Beibeibehaltung der `fix_plan`-Sortierung nach Priorität).
- **Lease-TTL:** Default 300 Sekunden, pro Claim konfigurierbar.
- **Max-Reclaim:** Default 3. Nach 3 Lease-Ablaufen oder Releases wird
  ein Task als `failed` markiert und nicht erneut enqueued.
- **Thread-Safety:** Alle Lease-Operationen sind durch `threading.RLock`
  geschützt, da `anyio.to_thread` aus dem MCP-Server Worker-Threads erzeugt.

**Was nicht getan wird:**

- Kein cross-session Queue-Manager (Aufwand übersteigt Nutzen im
  Single-Server-Modell).
- Keine priority-basierte Claim-Strategie (FIFO reicht, da `fix_plan`
  bereits nach Priorität sortiert liefert).
- Keine dauerhafte Persistenz von Lease-State über Server-Neustarts
  (Sessions selbst sind flüchtig).
- Kein `task_result`-Store über die Tool-Response hinaus.

## Begründung

**Warum Leasing statt einfacher Zuweisung?** Lease-basierte Queues sind
ein bewährtes Pattern (SQS, Celery) für Szenarien, in denen Consumer
ausfallen können. Ein Agent kann abstürzen oder ein Timeout überschreiten;
das Lease verfällt automatisch und der Task wird re-enqueued.

**Warum session-scoped?** Der MCP-Server ist stdio-basiert und bedient
einen Client. Parallele Agenten laufen als Rollen innerhalb einer Session,
nicht als separate MCP-Verbindungen. Ein globaler Queue-Manager würde
Komplexität ohne klaren Nutzen erzeugen.

**Warum RLock statt asyncio.Lock?** Die Session-Methoden werden sowohl
aus dem Event-Loop als auch aus Worker-Threads (via `anyio.to_thread`)
aufgerufen. Ein `threading.RLock` schützt beide Pfade.

**Alternative verworfen: Task-Status in SessionManager statt Session.**
Würde die Session-Abstraktion aufbrechen und den Manager mit
kontextabhängiger Logik belasten.

## Konsequenzen

1. **Neue Felder in `DriftSession`:** `active_leases`, `failed_task_ids`,
   `task_reclaim_counts`, `_lock` — alle serialisierbar außer `_lock`.
2. **`tasks_remaining()`-Semantik ändert sich:** Excludiert jetzt auch
   `failed_task_ids`, nicht nur `completed_task_ids`.
3. **`summary()`-Dict erweitert:** `task_queue` enthält `claimed` und
   `failed` Zähler.
4. **5 neue MCP-Tools** in `_EXPORTED_MCP_TOOLS`.
5. **Rückwärtskompatibel:** `from_dict()` verwendet `.get()` mit Defaults;
   alte Sessions ohne Lease-Felder laden korrekt.

## Validierung

```bash
# Alle neuen Unit-Tests grün
pytest tests/test_task_queue.py -v

# Keine Regression in bestehenden Session-Tests
pytest tests/test_session.py -v

# Lint + Typecheck
ruff check src/drift/session.py src/drift/mcp_server.py
python -m mypy src/drift/session.py src/drift/mcp_server.py
```

Lernzyklus-Ergebnis: zurückgestellt — Validierung erfolgt bei erstem
Multi-Agent-Einsatz mit realen Agenten-Rollen.
