---
id: ADR-031
status: proposed
date: 2026-04-09
supersedes:
---

# ADR-031: Agent Context Layer — Plan-Staleness, Auto-Profiling, Architecture Map

## Kontext

FTA-Ergebnis (2026-04-09): Bei agentenbasierter Arbeit in großen Codebasen verlieren Agenten den belastbaren Arbeitskontext durch drei kritische Pfade:

1. **Plan-Staleness (Pfad D3+D2):** Fix-Plan wird nach Repo-Zustandsänderung nicht invalidiert → Agent arbeitet gegen veralteten Zustand.
2. **Finding-Explosion ohne Rollenfilterung (Pfad A1+C2):** Agent erhält ungefilterte Findings → Fokus-Verlust → symptomatische statt kausale Fixes.
3. **Fehlende Architektur-Karte (Pfad B1):** Implizite Konventionen, Modulstruktur und Abhängigkeiten sind nicht als Tool-Output verfügbar → Agent verletzt Invarianten.

## Entscheidung

Drei zusammengehörige Maßnahmen als „Agent Context Layer":

### M7 — Plan-Invalidierungs-Check

- `DriftSession` speichert `git_head_at_plan` (SHA) beim Erstellen eines Fix-Plans.
- Bei jedem Tool-Aufruf mit `session_id`: aktuellen HEAD vergleichen.
- Bei Mismatch: `plan_stale: true` + `plan_stale_reason` im Response.
- **Kein** automatischer Re-Plan (bleibt Agent-Entscheidung).

### M3 — Auto-Profiling

- Session-Phase → Default `response_profile`:
  - `init` / `scan` → `"planner"`
  - `fix` → `"coder"`
  - `verify` → `"verifier"`
  - `done` → `"merge_readiness"`
- Expliziter `response_profile`-Parameter hat Vorrang (Opt-out).
- Mapping in `_session_defaults()` als konfigurierbar deklariert.

### M1 — drift_map

- Neue API-Funktion `drift_map(path, session_id=None)` → kompakte Architektur-Karte.
- Output (< 500 Tokens): Module, Top-Level-Packages, Import-Dependency-Edges, Signal-Hotspots, Schichtgrenzen.
- Neues MCP-Tool `drift_map` mit session-aware Defaults.
- Nutzt vorhandene Ingestion-Daten (keine neue Parsierung nötig wenn Cache warm).

### Nicht umgesetzt

- Kein kNN-Semantic-Search (Aufwand L, Nutzen unklar).
- Keine Instruktions-Kondensation (erfordert LLM-seitige Prompt-Steuerung).
- Kein automatischer Re-Plan (Agent soll bewusst entscheiden).
- Keine Token-Budget-Enforcement (separate Maßnahme, koppelt an Output-Layer).

## Begründung

Die drei Maßnahmen adressieren die drei gefährlichsten Kausalketten aus der FTA mit dem besten Impact-to-Effort-Verhältnis. Alternative Einzelmaßnahmen (Token-Budgets, Dependency-Graph-Export, Kontext-Zusammenfassung) haben höheren Aufwand bei geringerem Primäreffekt.

Auto-Profiling nutzt die bereits existierende Session-Phase-Maschine (ADR-022) und Response-Profile (ADR-025) — es fehlt nur die Default-Zuordnung. Plan-Staleness nutzt `_current_git_head` aus `pipeline.py`. drift_map nutzt vorhandene Ingestion-Daten.

## Konsequenzen

- Agenten erhalten rollengerechten Output ohne manuelle Konfiguration.
- Stale-Plan-Warnungen verhindern Arbeit gegen veralteten Zustand.
- drift_map liefert Orientierung in unbekannten Codebasen in < 1 Tool-Aufruf.
- Trade-off: Auto-Profiling kann Felder filtern, die ein Agent unerwartet benötigt → Opt-out via expliziten `response_profile`-Parameter bleibt erhalten.

## Validierung

```bash
pytest tests/test_session.py tests/test_mcp_tools.py tests/test_api.py -v --tb=short -k "stale or auto_profile or drift_map"
```

Erwartetes Lernzyklus-Ergebnis: `bestätigt` wenn:
- Plan-Stale-Warnung bei HEAD-Änderung nach fix_plan nachweisbar
- Auto-Profiling filtert Responses korrekt nach Phase
- drift_map Output < 500 Tokens bei Drift-Selbstanalyse
