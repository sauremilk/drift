---
id: ADR-047
status: proposed
date: 2026-04-11
supersedes:
---

# ADR-047: Rich TTY Output for drift fix-plan

## Kontext

`drift fix-plan` gibt bisher ausschließlich rohen JSON-Output aus — auch wenn es
interaktiv im Terminal aufgerufen wird. Ein neuer Nutzer, der
`drift fix-plan --repo . --max-tasks 5` ausführt, erhält mehrere hundert Zeilen
JSON-Flood mit dem Hinweis `"total_available": 438`. Das führt zu Desorientierung
und erhöht First-Run-Dropoff.

Das Signal `_is_non_tty_stdout()` (aus `drift/commands/_io.py`) erlaubt es bereits
anderen Commands (`analyze`, `check`), sich für CI/Pipe-Konsumenten automatisch
anzupassen — fix-plan tut das noch nicht für den Rich-Output-Kanal.

## Entscheidung

- `fix-plan` erhält eine `--format [rich|json]`-Option mit Default `auto`.
- Im `auto`-Modus: Rich-Output wenn stdout ein TTY ist, JSON wenn nicht.
- `--format json` erzwingt immer den bisherigen JSON-Output (backward-compat).
- `--format rich` erzwingt immer den Rich-Output (für explizite Nutzung in Scripts).
- Ein neuer Renderer `src/drift/output/fix_plan_rich.py` kapselt das Rich-Layout.
- Der Rich-Renderer zeigt: Header-Panel (Score, N/M Tasks), nummerierte Aufgabenliste
  (Signal, Datei, Titel, Automation-Fit), Footer-Hinweis `--format json` für Maschinen.
- Der JSON-Output-Kanal (`click.echo(to_json(result))`) bleibt unverändert.

## Nicht-Entscheidungen

- Kein neues Output-Schema: JSON-Schema bleibt identisch.
- Kein SARIF/Markdown-Output für fix-plan in diesem ADR.
- Die `--output file`-Option schreibt weiterhin immer JSON.

## Begründung

- Anpassung ist additive (neues Flag + neues Renderer-Modul) — kein Breaking Change.
- `_is_non_tty_stdout()` existiert bereits und wird in `analyze` + `check` verwendet.
- CI- und Agent-Konsumenten nutzen `--format json` oder Pipe — bleiben unberührt.
- Alternative (`--quiet` Flag statt TTY-Auto) wurde verworfen: zu viel Nutzerlast.

## Konsequenzen

- Neue Datei: `src/drift/output/fix_plan_rich.py`
- Geänderte Datei: `src/drift/commands/fix_plan.py` (neues `--format`-Argument)
- Tests: `tests/test_coverage_boost_6_fix_plan_api.py` erhält Tests für `--format rich`
  und TTY-Auto-Switching.
- CHANGELOG-Eintrag erforderlich (bereits vorbereitet unter `[Unreleased] Added`).

## Validierung

```bash
# Rich im Terminal (TTY):
drift fix-plan --repo . --max-tasks 5
# → zeigt Rich-Panel, kein raw JSON

# JSON erzwingen (backward-compat):
drift fix-plan --repo . --max-tasks 5 --format json | python -m json.tool

# Non-TTY (Pipe) bleibt JSON:
drift fix-plan --repo . --max-tasks 5 | python -m json.tool

# Tests:
pytest tests/test_coverage_boost_6_fix_plan_api.py -v
```

Lernzyklus-Erwartung: `bestätigt` wenn kein Regressions-Test fehlschlägt und
`drift fix-plan --repo . --max-tasks 5 | python -m json.tool` weiterhin valides
JSON produziert.
