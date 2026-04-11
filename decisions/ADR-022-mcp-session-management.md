---
id: ADR-022
status: proposed
date: 2026-04-08
supersedes:
---

# ADR-022: MCP Session Management

## Kontext

Drift MCP-Tools sind heute zustandslos: Jeder Tool-Aufruf ist unabhängig, und Agenten müssen Multi-Step-Workflows (Validate → Brief → Scan → Fix-Plan → Nudge → Diff) selbst orchestrieren. ADR-020 hat entschieden, dass die Baseline-Infrastruktur (`drift baseline save/diff`) als Persistenz-Layer dient — kein Session-Token in der API.

In der Praxis zeigt sich, dass Agenten bei jedem Aufruf redundante Parameter angeben müssen (Repo-Pfad, Signal-Filter, Target-Path), Scan-Ergebnisse nicht automatisch in nachfolgende Tool-Aufrufe fließen, und bei Unterbrechungen der gesamte Kontext verloren geht. Die Baseline löst das Persistenz-Problem, nicht das Orchestrierungs-Problem.

## Entscheidung

Einführung einer In-Memory-Session-Schicht im MCP-Layer (`src/drift/session.py`), die ADR-020 ergänzt (nicht ablöst):

1. **`DriftSession` Dataclass** — speichert `session_id` (UUID4), aktiven Scope (Repo-Pfad, Signal-Filter, Target-Path), letzten Scan-State (Score, Top-Signale, Finding-Count), Fix-Plan-Queue (aktive Tasks, abgehakte Tasks), Brief-Guardrails und Aktivitäts-Tracking (TTL 30 Min, touch-basiert).

2. **`SessionManager` Singleton** — verwaltet aktive Sessions (create/get/update/destroy/list/prune). Pattern analog zu `BaselineManager` in `incremental.py`.

3. **4 neue MCP-Tools:**
   - `drift_session_start` — erstellt Session, gibt `session_id` zurück
   - `drift_session_status` — zeigt aktuellen Session-State
   - `drift_session_update` — Scope/Tasks/Metadata anpassen, optional Disk-Persistenz
   - `drift_session_end` — beendet Session, gibt Zusammenfassung zurück

4. **Optionaler `session_id` Parameter** auf alle bestehenden 8 MCP-Tools — wenn gesetzt: Session-Defaults als Fallback, Session-State wird nach Ausführung aktualisiert. Wenn leer: exakt heutiges Verhalten (volle Abwärtskompatibilität).

5. **Optionale Disk-Persistenz** — Sessions können als `.drift-session-{id[:8]}.json` gespeichert/geladen werden (für MCP-Server-Neustarts).

### Was explizit nicht getan wird

- Die API-Schicht (`api.py`) wird **nicht** verändert — sie bleibt stateless.
- Session ersetzt **nicht** die Baseline-Persistenz — Baseline bleibt der primäre Checkpoint-Mechanismus (ADR-020 bleibt gültig).
- Kein HTTP-/WebSocket-Session-Management — Session lebt ausschließlich im MCP stdio-Server-Prozess.
- Keine Authentifizierung/Autorisierung auf Sessions — der MCP-Server ist lokal (stdio), nicht netzwerkexponiert.

## Begründung

- **Handlungsfähigkeit:** Agenten müssen bei Multi-Step-Workflows nicht mehr jeden Parameter wiederholen — Session speichert Scope-Defaults.
- **Robustheit:** Scan-Ergebnisse fließen automatisch in nachfolgende fix_plan/brief-Aufrufe; Guardrails bleiben über die Session verfügbar.
- **Einführbarkeit:** session_id ist optional — bestehende Workflows brechen nicht. Agenten können inkrementell migrieren.
- **Transparenz:** `drift_session_status` gibt jederzeit eine kompakte Übersicht: Score, Delta, offene Tasks, TTL.

Alternative „Session-State in die API-Schicht": Verworfen, weil die API bewusst als stateless-Library konzipiert ist (CLI, CI, Import-Nutzung). Session-State ist ein Orchestrierungs-Concern, kein Analyse-Concern.

Alternative „Baseline als einziger State": Bereits entschieden in ADR-020. Baseline löst Persistenz, nicht Orchestrierung. Beides ergänzt sich.

## Konsequenzen

- Neues Modul `src/drift/session.py` (~250 Zeilen)
- `src/drift/mcp_server.py` wächst um ~200 Zeilen (4 neue Tools + session_id-Wrapping)
- 12 statt 8 MCP-Tools in der Tool-Oberfläche
- Keine Änderung an signals/, ingestion/, output/ → kein Risk-Audit nötig
- Docstring-Gate gilt für neue public functions in `src/drift/session.py`

## Validierung

```bash
# Unit-Tests für Session-Modul
pytest tests/test_session.py -v

# MCP-Integration-Tests (inkl. Backward-Compat)
pytest tests/test_mcp_hardening.py -v

# Gesamte Testsuite unverändert grün
pytest tests/ --ignore=tests/test_smoke.py -q

# Lint + Type-Check
ruff check src/drift/session.py src/drift/mcp_server.py
python -m mypy src/drift/session.py src/drift/mcp_server.py

# Tool-Catalog zeigt 12 Tools
drift mcp --list
```

Erwartetes Lernzyklus-Ergebnis: `bestaetigt` nach erfolgreichem Agent-Roundtrip (session_start → scan → fix_plan → status → end) mit messbarer Reduktion redundanter Parameter-Angaben.
