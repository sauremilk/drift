---
id: ADR-046
status: proposed
date: 2026-04-11
supersedes:
---

# ADR-046: Markdown als CLI-Output-Format für `drift analyze`

## Kontext

`src/drift/output/markdown_report.py` existiert mit vollem Feature-Set (`analysis_to_markdown()`) — Summary, Findings-Tabelle, Modul-Scores, Signal-Coverage, Preflight-Diagnostik, Interpretation. Dieses Modul wird intern von `drift brief` und `drift copilot-context` genutzt, ist aber **nicht** als `--format markdown` in `drift analyze` verfügbar.

PR-Kommentare, Slack-Posts und Wiki-Einträge brauchen Human-first-Output. JSON/SARIF sind Machine-first. Die Lücke zwischen "lesbare Findings" (Rich-Terminal) und "maschinenlesbare Findings" (JSON) wird durch Markdown geschlossen.

Adoptionsanalyse (10 trending GitHub-Repos, April 2026) identifiziert Copy-Paste-fähigen Output als Top-3-Shareability-Hebel.

## Entscheidung

`markdown` wird als siebtes Output-Format in `drift analyze --format` eingefügt. Dazu:

1. `click.Choice` in `analyze.py` um `"markdown"` erweitern
2. Im Format-Switch den Zweig `elif output_format == "markdown":` einfügen, der `analysis_to_markdown()` aufruft und via `_emit_machine_output()` ausgibt
3. `action.yml` dokumentiert `markdown` als gültige Format-Option

**Was explizit nicht getan wird:**
- Kein neuer Formatter — `markdown_report.py` wird unverändert wiederverwendet
- Keine Änderung am Markdown-Inhalt oder -Schema
- Keine neue Dependency

## Begründung

Das Modul existiert, ist getestet (indirekt über Brief/Copilot-Context), und braucht nur Wiring. Aufwand minimal, Nutzen hoch (Shareability für PRs, Wikis, Slack).

Alternative "HTML-Format" verworfen: höherer Aufwand, geringere Universalität als Markdown.

## Konsequenzen

- `drift analyze --format markdown` erzeugt stdout-Markdown, pipe-fähig
- `--output file.md` schreibt in Datei
- GitHub Action kann `format: markdown` nutzen für PR-Kommentare
- Output-Pfad erweitert: `audit_results/risk_register.md` muss aktualisiert werden (Policy §18)

## Validierung

```bash
drift analyze --repo . --format markdown | head -20  # Markdown-Header sichtbar
drift analyze --repo . --format markdown -o /tmp/report.md  # Datei-Output
pytest tests/ -k "markdown" --tb=short  # bestehende + neue Tests
```

Lernzyklus-Ergebnis: bestätigt (wenn Format in Praxis für PR-Kommentare genutzt wird)
