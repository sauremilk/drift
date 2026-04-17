---
name: guard-src-drift-api
description: "Drift-generierter Guard fuer `src/drift/api`. Aktiv bei Signalen: EDS, PFS. Konfidenz: 0.95. Verwende diesen Skill wenn du Aenderungen an `src/drift/api` planst oder wiederholte Drift-Findings (EDS, PFS) fuer dieses Modul bearbeitest."
argument-hint: "Beschreibe die geplante Aenderung in `src/drift/api` — welche Funktion, welches Modul, welcher Zweck."
---

# Guard: `src/drift/api`

`src/drift/api` ist die einzige legitime Eintrittspforte fuer alle Agenten- und MCP-Aufrufe. Jede Datei hier (`scan.py`, `fix_plan.py`, `steer.py`, `nudge.py`, `brief.py`, `suggest_rules.py`, `generate_skills.py`, `diff.py`, `verify.py`) repraesentiert genau einen oeffentlichen Vertrag.

**Konfidenz: 0.95** — EDS und PFS treten wiederholt auf, weil API-Funktionen interne Submodule direkt verdrahten statt sauber zu delegieren.

## When To Use

- Du fuegest eine neue oeffentliche API-Funktion hinzu oder aenderst eine bestehende
- Du implementierst einen neuen MCP-Tool-Handler
- Du rufst intern `pipeline.py`, `analyzer.py` oder `scoring/` direkt aus einer neuen Funktion auf
- Drift meldet EDS oder PFS fuer eine Datei in `src/drift/api/`

**Nicht benutzen** fuer reine CLI-Aenderungen — dafuer gibt es `guard-src-drift-commands`.

## Warum dieses Modul kritisch ist

| Signal | Ursache in diesem Modul |
|--------|-------------------------|
| **EDS** | API-Funktionen greifen direkt auf `pipeline.py`, `analyzer.py`, `scoring/` und `output/` zu — je mehr Abhaengigkeiten, desto hoeher EDS |
| **PFS** | Verschiedene API-Funktionen handhaben Fehler, Rueckgabetypen und `agent_instruction`-Felder unterschiedlich — inkonsistente Muster |

## Core Rules

1. **Eine API-Funktion = ein Vertrag** — jede Datei in `src/drift/api/` darf genau einen Eintrittspunkt nach aussen haben. Hilfsfunktionen, die von mehreren API-Funktionen benoetigt werden, gehoeren in `_util.py`.

2. **Keine Pipeline-Direktaufrufe** — API-Funktionen duerfen nicht direkt `pipeline.run()` oder `Analyzer()` instanziieren. Der Einstiegspunkt geht ueber `_config.py`-Konfiguration und gemeinsame Bootstrapping-Logik.

3. **`agent_instruction`-Feld immer setzen** — alle API-Rueckgabe-Dicts muessen `agent_instruction` enthalten. PFS steigt wenn manche Funktionen es weglassen oder anders benennen.

4. **Kein Output-Formatting in der API** — API-Funktionen geben strukturierte Dicts zurueck, KEIN Rich-Text, kein Markdown, kein formatted String. Formatting gehoert in `src/drift/output/`.

5. **Fehlerpfad explizit** — jede API-Funktion hat einen definierten Fehlerpfad (`status: "error"`, `message: ...`). Kein `raise` ohne Catching-Wrapper nach aussen.

## Iron Law

> **Jede neue API-Funktion ohne `agent_instruction`-Feld ist eine Regression.** Das Feld ist der Vertrag fuer alle konsumierenden Agenten.

## Arbeitsablauf

```bash
# Nach Aenderung in src/drift/api/
drift nudge  # schnelle Richtungspruefung

# Vollstaendiger Check
drift analyze --repo . --exit-zero --format json | python -c "
import json, sys
d = json.load(sys.stdin)
findings = [f for f in d.get('findings', []) if 'api' in f.get('file', '')]
print(f'{len(findings)} findings in api/')
"
```

## Review Checklist

- [ ] Neue API-Funktion hat eigene Datei in `src/drift/api/`
- [ ] `agent_instruction`-Feld ist im Rueckgabe-Dict vorhanden
- [ ] Keine Direktaufrufe zu `pipeline.py` oder `Analyzer()` ohne `_config.py`-Wrapper
- [ ] Fehlerfall gibt `{"status": "error", "message": ...}` zurueck
- [ ] `drift nudge` zeigt `safe_to_commit: true`
- [ ] Keine neuen EDS- oder PFS-Findings in `src/drift/api/`

## References

- [src/drift/api/_util.py](../../../src/drift/api/_util.py) — Gemeinsame API-Hilfsfunktionen
- [src/drift/api/_config.py](../../../src/drift/api/_config.py) — API-Bootstrapping
- [src/drift/api/scan.py](../../../src/drift/api/scan.py) — Referenz-Implementierung
- [DEVELOPER.md](../../DEVELOPER.md)
