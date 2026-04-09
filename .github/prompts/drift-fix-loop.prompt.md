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

Dieser eine Aufruf führt automatisch `validate → brief → scan → fix_plan` aus und gibt die kombinierten Ergebnisse zurück. Die Session-ID wird in allen Folge-Aufrufen wiederverwendet.

**Wichtig:** Die `session_id` aus der Antwort merken und an **jeden** weiteren Tool-Aufruf übergeben.

### Schritt 2 — Ersten Task aus fix_plan bearbeiten

Die Autopilot-Antwort enthält bereits den `fix_plan`. Den **ersten** Task nehmen und umsetzen.

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
**Wenn `safe_to_commit=true`:** Weiter mit nächstem Task oder Abschluss.

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
┌───────────────────────────┐
│  Task N bearbeiten        │
│  Datei editieren          │
│  nudge(changed_files=...) │ ← schnell (~0.2 s)
│  direction prüfen         │
│  ggf. korrigieren         │
└─────────┬─────────────────┘
          │ safe_to_commit?
          ↓
    fix_plan(max_tasks=1)    ← nächster Task
          │ keine Tasks mehr?
          ↓
    drift_diff(uncommitted)  ← Abschluss-Verifikation
          ↓
    Commit vorbereiten
```

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
