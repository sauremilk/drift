---
name: "Drift Fix-Loop"
description: "Optimierter Agent-Workflow zum Beheben von Drift-Findings über MCP-Sessions. Nutzt session_start(autopilot=true) + nudge als Inner-Loop für minimale Roundtrips."
---

# Drift Fix-Loop

Dieser Prompt beschreibt den optimalen Ablauf, um Drift-Findings in einem Workspace über MCP-Tools effizient zu beheben. Der Workflow minimiert Roundtrips und nutzt die vorhandene Session-Infrastruktur vollständig aus.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Push Gates:** `.github/instructions/drift-push-gates.instructions.md`
- **Skill:** `.github/skills/drift-effective-usage/SKILL.md`
- **Skill:** `.github/skills/drift-commit-push/SKILL.md`
- **MCP-Server:** `src/drift/mcp_server.py`
- **Session-Management:** `src/drift/session.py`

## Warum dieser Workflow

Ein naiver Agent-Loop ruft pro Finding: `validate → scan → fix_plan → [edit] → scan → diff` auf.
Jeder `scan`-Aufruf führt eine vollständige Repo-Analyse durch (~1–5 s). Bei mehreren Findings multipliziert sich die Wartezeit und die Roundtrips.

**Dieser Workflow reduziert das auf:**
1. Einen einzigen `session_start(autopilot=true)`-Aufruf (bündelt validate + brief + scan + fix_plan)
2. `nudge` als schnellen Inner-Loop nach jeder Dateiänderung (~0.2 s statt ~3 s für scan)
3. Einen einzigen `drift_diff` als Abschluss-Verifikation

## Ablauf

### Schritt 1 — Session starten mit Autopilot

```
drift_session_start(
    path=".",
    autopilot=true
)
```

Dieser eine Aufruf führt automatisch `validate → brief → scan → fix_plan` aus. Standardmäßig liefert die Antwort ein kompaktes Summary plus Referenzen/Checksummen (`autopilot_payload="summary"`).

Falls die volle eingebettete Payload benötigt wird:

```
drift_session_start(path=".", autopilot=true, autopilot_payload="full")
```

**Wichtig:** Die `session_id` aus der Antwort merken und an **jeden** weiteren Tool-Aufruf übergeben.

### Schritt 2 — Ersten Task aus fix_plan bearbeiten

Den **ersten** Task über `drift_fix_plan(session_id=..., max_tasks=1)` holen und umsetzen.

**Regel:** Immer nur einen Task gleichzeitig. Nicht mehrere Findings in einem Schritt mischen.

### Schritt 3 — Nach jeder Dateiänderung: nudge

```
drift_nudge(
    session_id="<session_id>",
    changed_files="<pfad/zur/geänderten/datei.py>"
)
```

`nudge` gibt schnelles Richtungsfeedback:
- `direction`: improving / stable / degrading
- `safe_to_commit`: true / false
- `confidence`: pro Signal

**Wenn `direction=degrading`:** Änderung rückgängig machen, anders lösen.
**Wenn `safe_to_commit=true`:** Weiter mit Test-Checkpoint (Schritt 3b).

### Schritt 3b — Test-Checkpoint nach jeder Änderung

Nachdem `nudge` kein Degrading meldet, **gezielte Tests** für die geänderte Datei ausführen.

**Pfad-zu-Test-Mapping** (kürzeste Match-Regel, oben zuerst):

| Geänderte Datei (Pattern) | Gezielte Tests |
|---|---|
| `src/drift/signals/architecture_violation*` | `pytest tests/test_avs_*.py -q --tb=short` |
| `src/drift/signals/doc_impl_drift*` | `pytest tests/test_dia_*.py -q --tb=short` |
| `src/drift/signals/explainability_deficit*` | `pytest tests/test_eds_*.py -q --tb=short` |
| `src/drift/signals/mutant_duplicates*` | `pytest tests/test_mutant_duplicates*.py -q --tb=short` |
| `src/drift/signals/dead_code_accumulation*` | `pytest tests/test_dead_code*.py -q --tb=short` |
| `src/drift/signals/pattern_fragmentation*` | `pytest tests/test_pattern_fragmentation*.py -q --tb=short` |
| `src/drift/signals/naming_contract*` | `pytest tests/test_naming_contract*.py -q --tb=short` |
| `src/drift/signals/test_polarity_deficit*` | `pytest tests/test_test_polarity_deficit*.py -q --tb=short` |
| `src/drift/signals/cognitive_complexity*` | `pytest tests/test_cognitive_complexity*.py -q --tb=short` |
| `src/drift/signals/circular_import*` | `pytest tests/test_circular_import*.py -q --tb=short` |
| `src/drift/signals/guard_clause*` | `pytest tests/test_guard_clause*.py -q --tb=short` |
| `src/drift/signals/insecure_default*` | `pytest tests/test_insecure_default*.py -q --tb=short` |
| `src/drift/signals/missing_authorization*` | `pytest tests/test_missing_authorization*.py -q --tb=short` |
| `src/drift/signals/hardcoded_secret*` | `pytest tests/test_hardcoded_secret*.py -q --tb=short` |
| `src/drift/signals/exception_contract*` | `pytest tests/test_exception_contract*.py -q --tb=short` |
| `src/drift/signals/fan_out_explosion*` | `pytest tests/test_fan_out_explosion*.py -q --tb=short` |
| `src/drift/signals/cohesion_deficit*` | `pytest tests/test_cohesion_deficit*.py -q --tb=short` |
| `src/drift/signals/bypass_accumulation*` | `pytest tests/test_bypass_accumulation*.py -q --tb=short` |
| `src/drift/signals/*` (andere) | `pytest tests/test_precision_recall.py tests/test_mirofish_signal_improvements.py -q --tb=short` |
| `src/drift/api.py` | `pytest tests/test_brief.py tests/test_integration.py tests/test_incremental.py tests/test_fix_actionability.py tests/test_nudge.py -q --tb=short -m "not slow"` |
| `src/drift/mcp_server.py` | `pytest tests/test_mcp_copilot.py tests/test_mcp_hardening.py tests/test_tool_metadata.py tests/test_negative_context_export.py -q --tb=short` |
| `src/drift/output/*` | `pytest tests/test_json_output.py tests/test_csv_output.py tests/test_sarif_contract.py tests/test_output_golden.py tests/test_agent_tasks.py -q --tb=short` |
| `src/drift/ingestion/*` | `pytest tests/test_ast_parser.py tests/test_file_discovery.py tests/test_scope_resolver.py tests/test_typescript_parser.py -q --tb=short` |
| `src/drift/config.py` | `pytest tests/test_config.py tests/test_config_validate.py tests/test_model_consistency.py -q --tb=short` |
| `src/drift/commands/*` | `pytest tests/test_patterns_command.py -q --tb=short` |
| `src/drift/session.py` | `pytest tests/test_session.py -q --tb=short` |
| `src/drift/incremental.py` | `pytest tests/test_incremental.py tests/test_nudge.py -q --tb=short` |
| Fallback (kein Treffer) | `pytest tests/ -q --tb=short --ignore=tests/test_smoke_real_repos.py -m "not slow" --maxfail=5` |

**Bei Testfehlschlag — Entscheidungsbaum:**

| Fehlerbild | Ursache | Reaktion |
|---|---|---|
| `AttributeError: has no attribute X` | Test prüft Implementation-Details | **Test anpassen** |
| `TypeError: N arguments expected` | Signatur wurde geändert | **Test anpassen** |
| Test erwartet altes Drift-Pattern, das absichtlich entfernt wurde | Finding war Ziel des Fixes | **Test anpassen** |
| `AssertionError` auf dokumentiertes Public-API-Verhalten | Vertrag verletzt | **Production-Fix überdenken oder reverten** |
| `AssertionError` auf Rückgabewert eines öffentlichen Contracts | Semantische Regression | **Production-Fix überdenken oder reverten** |

**Kein Hard-Block:** Der Workflow wird nicht abgebrochen. Der Agent wendet den Entscheidungsbaum an und setzt mit dem bereinigten Zustand fort.

### Schritt 4 — Nächsten Task holen (falls nötig)

Wenn weitere Findings offen sind:

```
drift_fix_plan(
    session_id="<session_id>",
    max_tasks=1
)
```

**Immer `max_tasks=1` verwenden.** Das reduziert die Response-Größe und den Parsing-Overhead erheblich.

Dann zurück zu Schritt 2.

### Schritt 5 — Abschluss-Verifikation

Erst wenn alle Tasks bearbeitet sind:

```
drift_diff(
    session_id="<session_id>",
    uncommitted=true
)
```

Prüfen:
- `resolved_count` > 0
- `new_count` == 0
- Keine Regressionen

## Zusammenfassung als Ablaufdiagramm

```
session_start(autopilot=true)       ← 1 Aufruf statt 4
    ↓
fix_plan (in Autopilot enthalten)
    ↓
┌──────────────────────────────────────────┐
│  Task N bearbeiten                       │
│  Datei editieren                         │
│  nudge(changed_files=...)  ← ~0.2 s      │
│  direction prüfen                        │
│  ggf. korrigieren                        │
│  pytest <gezielte Tests> --tb=short  ← 3b│
│  bei rot: Test anpassen oder reverten    │
└─────────┬────────────────────────────────┘
          │ safe_to_commit + Tests grün?
          ↓
    fix_plan(max_tasks=1)    ← nächster Task
          │ keine Tasks mehr?
          ↓
    drift_diff(uncommitted)  ← Abschluss-Verifikation
          ↓
    Commit vorbereiten
```

## Oscillation-Detection: CXS↔EDS Trade-off

Wenn ein CXS-Finding durch Helper-Extraktion behoben wird, kann die neu entstandene
Hilfsfunktion selbst EDS feuern — dieser Kreislauf blockiert den Fix-Loop.

### Erkennungsbedingung

Nach einem `nudge`-Aufruf: `direction = degrading` für EDS-Score in derselben Datei,
obwohl CXS-Score gesunken ist → **Oscillation erkannt**.

### Atomare Extraktions-Regel (Pflicht bei CXS-Fixes via Helper)

Jeder extrahierte Helper muss **gleichzeitig** alle drei Bedingungen erfüllen:

| Bedingung | EDS-Effekt | Wert |
|---|---|---|
| `_` Prefix (privat) | `visibility_factor=0.7`, `min_threshold=0.45` | Pflicht |
| LOC < 40 | `loc_factor < 1.0` → reduzierter Multiplikator | Ziel |
| Einzeiler-Docstring | senkt `deficit`-Basis erheblich | Pflicht |

Werden alle drei eingehalten, bleibt `weighted_score` der neuen Funktion i.d.R. unter
dem privaten Schwellwert von `0.45` — kein neues EDS-Finding entsteht.

### Entscheidungsbaum bei Oscillation

```
nudge → direction = degrading für EDS in Datei X?
    JA
    ├─ Helper erfüllt alle drei Atomaren-Extraktions-Regeln?
    │   NEIN → Docstring + _ Prefix + LOC<40 nachrüsten, dann nudge erneut
    │   JA  → EDS feuert trotz Regeln?
    │           NEIN → stabil, fortfahren
    │           JA  → Funktion hat defect_correlated_commits > 0?
    │                   JA  → EDS ist berechtigt: erst EDS (Docs+Tests) fixen,
    │                         DANN CXS-Extraktion wiederholen
    │                   NEIN → Eskalationspfad (siehe unten)
    NEIN → normal fortfahren
```

### Eskalationspfad

Wenn Atomare Extraktion EDS trotz `_`-Prefix, LOC<40, Docstring immer noch feuert
und keine Defekt-Korrelation vorliegt:

1. Nichts erzwingen. **Den nudge-Befund dokumentieren** — Dateiname, Funktion,
   `weighted_score`, `min_threshold`.
2. Im nächsten `fix_plan`-Ergebnis prüfen: Gibt es ein ADR das EDS-Threshold für
   private Micro-Helpers regelt (ADR-077)?
3. Falls ADR-077 vorhanden und `accepted`: Signal-Kalibrierung ist implementiert —
   nach Update nochmal `nudge` prüfen.
4. Falls ADR-077 noch `proposed`: Finding als bekannte Limitation dokumentieren
   (Kommentar in ADR-077), CXS-Fix ausliefern, EDS-Finding bleibt als Low-Risk offen.

## Anti-Patterns: Was NICHT tun

| Anti-Pattern | Problem | Stattdessen |
|---|---|---|
| `drift_scan` nach jeder Dateiänderung | Volle Repo-Analyse pro Edit (~3–5 s) | `drift_nudge` verwenden (~0.2 s) |
| `session_start` ohne `autopilot=true` | 4 separate Roundtrips für validate/brief/scan/fix_plan | `autopilot=true` setzen |
| `fix_plan(max_tasks=5)` oder mehr | Große Response, Agent parst unnötig viel | `max_tasks=1` im Loop verwenden (initiale Übersicht wird von autopilot oder scan-Guidance gesteuert) |
| Kein `session_id` weitergeben | Jeder Aufruf verliert Kontext, kein Scope-Carry-Over | Immer `session_id` übergeben |
| `drift_diff` nach jedem Edit | Teurer als nötig für Zwischenfeedback | `nudge` als Inner-Loop, `diff` nur am Ende |
| Mehrere Findings gleichzeitig fixen | Unklar welche Änderung welchen Effekt hat | Immer ein Finding pro Iteration |

## Verhalten bei `agent_instruction` in Responses

Drift-MCP-Tools geben in jeder Antwort ein Feld `agent_instruction` zurück. **Dieses Feld befolgen.** Es enthält den empfohlenen nächsten Schritt, der zum Session-Zustand passt.

Zusätzlich gibt `next_tool_call` den konkreten nächsten Tool-Aufruf mit Parametern vor. Wenn vorhanden, diesen bevorzugt verwenden.

## Artefakte

Dieser Prompt erzeugt keine separaten Artefakte. Die Änderungen sind die Code-Fixes selbst.
