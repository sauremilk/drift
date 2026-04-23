---
id: ADR-029
status: proposed
date: 2026-04-09
supersedes:
---

# ADR-029: Preflight-Diagnose und Markdown-Report-Export

## Kontext

Externe Erstnutzer, die `drift analyze` auf einem fremden Repository ausführen, erhalten bei fehlenden Voraussetzungen (z. B. keine Git-History, 0 Python-Dateien) stille Skips ohne Erklärung. Das untergräbt Vertrauen in die Ergebnisse (Phase 1: Vertrauen) und erschwert die Einführbarkeit (Phase 3).

Zusätzlich existiert kein standardisiertes, teilbares Ergebnisformat für externe Reviews. JSON ist maschinenlesbar, Rich-Output ist nicht kopierbar, und SARIF/CSV sind für Code-Scanning-Tools optimiert, nicht für menschliche Triage.

## Entscheidung

### Was wird getan

1. **Preflight-Diagnose** integriert in den `analyze`-Flow (kein separater Subcommand). Ein neues Modul `src/drift/preflight.py` führt vor der Analyse eine kompakte Prüfung durch: `.git` vorhanden, Python-Dateien vorhanden, aktive Excludes, git-abhängige Signale auswertbar. Das Ergebnis wird als `PreflightResult`-Datenklasse an `RepoAnalysis` angehängt und in Rich- und JSON-Output sichtbar gemacht.

2. **Signal-Warnings propagieren**: `AnalyzerWarning`-Instanzen aus Signalen werden durch die Pipeline bis in `RepoAnalysis` durchgereicht und in der Ausgabe als Skip-Erklärungen mit konkreten Handlungsanweisungen dargestellt.

3. **Markdown-Report-Export** als neues Output-Format (`--format markdown`). Der Report enthält: Repo-Metadaten, Preflight-Status, Score, Top-Findings, übersprungene Signale, Feedback-Sektion. GitHub-Issue-ready (kein ANSI, keine lokalen Pfade außerhalb des Repos).

4. **`--report` Convenience-Flag**: erzeugt automatisch `drift-report.md` + `drift-report.json` im CWD.

### Was explizit nicht getan wird

- Kein separater `drift doctor` Subcommand (CLI-Oberfläche bleibt klein)
- Keine neuen Signale oder Scoring-Neukalibrierung
- Keine Telemetrie oder Dashboard-Integration
- Keine Änderung am bestehenden JSON-Schema-Major (additive Felder nur)

## Begründung

**Integrierter Preflight statt `drift doctor`**: Erstnutzer sollen die Diagnose automatisch sehen, nicht einen separaten Befehl kennen müssen. Der Mehraufwand pro Analyse-Lauf ist minimal (File-Discovery und Git-Check laufen ohnehin).

**Markdown als Output-Format statt separatem Report-Befehl**: Konsistent mit dem bestehenden `--format`-System. Ermöglicht Kombination mit `--output` für Dateiexport.

**`--report` Shortcut**: Senkt die Hürde für externe Tester auf einen einzelnen Befehl.

Verworfene Alternative: Separater `drift report` Subcommand — würde die CLI-Oberfläche vergrößern und den Analyze-Flow duplizieren.

## Konsequenzen

- **Neuer Output-Pfad**: `src/drift/output/markdown_report.py` — erfordert STRIDE-Update für Trust Boundary (Markdown-Inhalt wird potentiell auf GitHub veröffentlicht)
- **Additives Feld in RepoAnalysis**: `preflight` und `warnings` — bestehende Konsumenten nicht betroffen (default None / leere Liste)
- **JSON-Schema bleibt 1.x**: Neue Felder `preflight` und `signal_coverage` sind additiv (Minor-Bump)
- **Verbindung zu WP4**: Markdown-Report ist direkt in GitHub-Issues kopierbar und verlinkt auf ein neues Issue-Template

## Validierung

```bash
# Preflight-Tests
pytest tests/test_preflight.py -v

# Markdown-Output-Tests
pytest tests/test_output_markdown.py -v

# Gesamtintegration
drift analyze --repo . --format markdown -o /dev/null --exit-zero
drift analyze --repo . --report --exit-zero

# Kein Breaking Change
make check

# Audit-Gate
python scripts/check_risk_audit.py --diff-base origin/main
```

Lernzyklus-Ergebnis: **unklar** — wird nach den ersten 5 externen Testläufen bewertet (bestätigt wenn Reports ohne Rückfragen nutzbar, widerlegt wenn wesentliche Informationen fehlen).
