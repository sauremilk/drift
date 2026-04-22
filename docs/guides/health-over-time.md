# Code-Health über Zeit

Dieser Guide richtet sich an Maintainer und Team-Leads, die die architektonische Gesundheit ihrer Codebase nicht nur punktuell, sondern über Wochen und Monate hinweg beobachten wollen. Ein einzelner Analyse-Snapshot zeigt den aktuellen Zustand — aber erst der Verlauf zeigt, ob die Codebase besser oder schlechter wird, wann Erosion begann und wie schnell sie voranschreitet.

---

## 1. Warum Trend-Tracking?

Ein hoher Drift-Score reicht nicht als Information, um Prioritäten zu setzen. Entscheidend ist die Richtung: Ein Score von 0.45, der seit drei Monaten fällt, erfordert andere Reaktionen als ein Score von 0.30, der jede Woche steigt. `drift trend` und `drift timeline` machen diese Dynamik sichtbar — und damit handlungsfähig. Darüber hinaus zeigt `drift timeline`, in welchem Modul Erosion zuerst begann und welche Commit-Typen sie ausgelöst haben. Diese Kombination aus Trend und Ursache ist die Grundlage für fundierte Refactoring-Entscheidungen.

---

## 2. `drift trend` — Score-Verlauf über Zeit

`drift trend` analysiert das Repository und zeigt, wie sich der Drift-Score über die zuletzt gespeicherten Snapshots entwickelt hat. Snapshots werden bei jeder Analyse automatisch im Cache (`<repo>/.drift-cache/history.json`) gespeichert. Der Befehl erfordert mindestens zwei Snapshots für eine Trendanzeige.

### Verfügbare Flags

| Flag | Kurzform | Standard | Beschreibung |
|------|----------|----------|--------------|
| `--repo` | `-r` | `.` | Pfad zum Repository-Root |
| `--last` | `-l` | `90` | Anzahl der Tage, die als Git-Fenster für die aktuelle Analyse verwendet werden |
| `--config` | `-c` | _(automatisch)_ | Pfad zu einer `drift.yaml`-Konfigurationsdatei |

### Aufrufe

```bash
# Standard: 90-Tage-Fenster
drift trend

# Kürzeres Git-Fenster (nur letzte 30 Tage)
drift trend --last 30

# Für anderes Repository
drift trend --repo /pfad/zum/projekt
```

### Konstruiertes Beispiel-Output

```
Drift — trend (90-day history window)

  Score History (last 10)
  ┌─────────────────────┬────────┬────────┬──────────┐
  │ Timestamp           │  Score │      Δ │ Findings │
  ├─────────────────────┼────────┼────────┼──────────┤
  │ 2026-01-06 09:12:04 │  0.281 │ —      │ 12       │
  │ 2026-01-13 09:08:11 │  0.294 │ +0.013 │ 14       │
  │ 2026-01-20 09:14:33 │  0.287 │ -0.007 │ 13       │
  │ 2026-01-27 09:11:02 │  0.301 │ +0.014 │ 15       │
  │ 2026-02-03 08:59:17 │  0.318 │ +0.017 │ 17       │
  │ 2026-02-10 09:02:44 │  0.312 │ -0.006 │ 16       │
  │ 2026-02-17 09:05:33 │  0.335 │ +0.023 │ 19       │
  │ 2026-02-24 09:10:51 │  0.341 │ +0.006 │ 20       │
  │ 2026-03-03 09:07:22 │  0.358 │ +0.017 │ 22       │
  │ 2026-03-10 09:08:44 │  0.372 │ +0.014 │ 24       │
  └─────────────────────┴────────┴────────┴──────────┘

  Overall trend (10 snapshots): ↑ increasing  (+0.091)

  Current drift score: 0.372
  Files analyzed: 47
  Total findings: 24
  AI-attributed commits: 38%
```

Der Trend-Verlauf wird als ASCII-Sparkline ergänzt, wenn mindestens drei Snapshots vorliegen. Rote Δ-Werte (+0.013) zeigen Verschlechterung, grüne Werte Verbesserung an.

**Hinweis zur Datenlage:** Drift speichert maximal 100 Snapshots in der History-Datei. Sinnvolle Trends entstehen erst nach Akkumulierung über mindestens einige Tage; zeigt `drift trend` eine Warnung wie `All N snapshots span only X minutes`, sollten die Snapshots aus automatisierten CI-Läufen über mehrere Tage gesammelt werden, bevor Schlussfolgerungen gezogen werden.

### Snapshot-Persistenz in CI

Damit Snapshots zwischen CI-Läufen erhalten bleiben, muss das Cache-Verzeichnis `.drift-cache/` als Actions-Cache konfiguriert werden. Ein fertiger Workflow dafür ist in [ci-integration.md](ci-integration.md) → Abschnitt „Trend-Tracking" dokumentiert.

---

## 3. `drift timeline` — Findings-Ursachen über Zeit

`drift timeline` geht tiefer als `drift trend`: Es zeigt nicht nur, dass der Score in einem Modul gestiegen ist, sondern wann der Clean-State endete, welche Commits den Drift ausgelöst haben und ob AI-Bursts (konzentrierte KI-Commit-Cluster) eine Rolle gespielt haben.

### Verfügbare Flags

| Flag | Kurzform | Standard | Beschreibung |
|------|----------|----------|--------------|
| `--repo` | `-r` | `.` | Pfad zum Repository-Root |
| `--since` | `-s` | `90` | Git-Fenster in Tagen |
| `--config` | `-c` | _(automatisch)_ | Pfad zu einer `drift.yaml` |

### Aufrufe

```bash
# Standard-Analyse der letzten 90 Tage
drift timeline

# Längeres Fenster für ältere Verläufe
drift timeline --since 180

# Für anderes Repository
drift timeline --repo /pfad/zum/projekt
```

### Konstruiertes Beispiel-Output

```
Drift Timeline — my-service  (90-day history)

  Module: src/checkout/
  ─────────────────────────────────────────────
  Clean until:   2026-01-14
  Drift started: 2026-01-17

  Trigger commits:
    2026-01-15  a3f9e12  [AI 87%]  feat: add PayPal provider via Copilot
                → AI-attributed (confidence: 87%); touched 7 files in module
    2026-01-17  b8c2d44  [AI 72%]  fix: broken checkout after PayPal merge
                → defect-correlated commit; AI-attributed (confidence: 72%)

  AI Burst detected:
    2026-01-15 – 2026-01-17 · 3 AI commits / 4 total
    Files: checkout/handlers.py, checkout/payment.py, checkout/validators.py

  Current score: 0.48   Findings: 6

  ─────────────────────────────────────────────

  Module: src/auth/
  ─────────────────────────────────────────────
  Clean until: (no clean period in window)
  No burst activity detected.
  Current score: 0.12   Findings: 1
```

**Was bedeuten die Felder?**

| Feld | Bedeutung |
|------|-----------|
| `Clean until` | Letztes Datum, an dem das Modul keine Problem-Commits hatte |
| `Drift started` | Datum des ersten Problem-Commits in einer Folge von ≥ 2 |
| `Trigger commits` | Commits, die als Auslöser identifiziert wurden (AI-attributed, defect-correlated, große Dateiänderungen) |
| `AI Burst` | Cluster von ≥ 3 AI-Commits in einem 3-Tage-Fenster |

**Abgrenzung zu `drift diff`:** `drift timeline` erklärt die Vergangenheit (Wann begann das Problem? Wer hat es ausgelöst?). `drift diff` zeigt, was sich zwischen zwei konkreten Punkten verändert hat — vorwärts gerichtet, ideal für Use-Cases nach einer Agent-Session oder einem PR-Merge. Für die vollständige `drift diff`-Referenz, siehe [Abschnitt 4](#4-drift-diff--score-delta-zwischen-zwei-punkten).

---

## 4. `drift diff` — Score-Delta zwischen zwei Punkten

`drift diff` analysiert, was sich zwischen dem aktuellen Stand und einem Referenzpunkt (Git-Ref, Baseline, Working-Tree) architektonisch verändert hat. Das Ergebnis ist strukturiertes JSON mit neuen Findings, aufgelösten Findings und einem Score-Delta.

> **Hinweis:** In [agent-workflow.md](agent-workflow.md) wird `drift diff` als Post-Session-Gate beschrieben — ein schneller Check nach einer Agent-Session um Regressionen zu erkennen. Dieser Abschnitt beschreibt `drift diff` aus der History-Perspektive: als Werkzeug, um Score-Veränderungen zwischen Release-Tags, Branches oder gespeicherten Baselines zu verstehen.

### Verfügbare Flags

| Flag | Standard | Beschreibung |
|------|----------|--------------|
| `--repo` / `-r` | `.` | Pfad zum Repository-Root |
| `--diff-ref` | `HEAD~1` | Git-Ref, gegen den diffed wird (Commit, Tag, Branch) |
| `--uncommitted` | _(Flag)_ | Working-Tree gegen HEAD vergleichen |
| `--staged-only` | _(Flag)_ | Nur staged Changes vergleichen |
| `--target-path` / `--path` | _(leer)_ | Analyse auf Unterverzeichnis beschränken |
| `--baseline` | _(leer)_ | Optionale Baseline-JSON-Datei |
| `--max-findings` | `10` | Maximale Anzahl Findings im Output |
| `--response-detail` | `concise` | `concise` oder `detailed` |
| `--output` / `-o` | _(stdout)_ | JSON-Ergebnis in Datei schreiben |
| `--signals` | _(alle)_ | Kommagetrennte Signal-IDs einschränken |
| `--exclude-signals` | _(keine)_ | Kommagetrennte Signal-IDs ausschließen |

### Aufrufe

```bash
# Gegen vorherigen Commit (Standard)
drift diff

# Gegen einen Release-Tag — "Was hat sich seit v2.0.0 verändert?"
drift diff --diff-ref v2.0.0

# Gegen den main-Branch
drift diff --diff-ref main

# Working-Tree prüfen (uncommitted Änderungen)
drift diff --uncommitted

# Gegen gespeicherte Baseline
drift diff --baseline .drift-baseline.json

# Auf einen Subpath beschränken
drift diff --diff-ref v2.0.0 --target-path src/checkout/

# Detailliertere Ausgabe
drift diff --diff-ref v2.0.0 --response-detail detailed

# Nur bestimmte Signale auswerten
drift diff --signals PFS,AVS,MDS
```

### Konstruiertes Beispiel-Output

```json
{
  "drift_detected": true,
  "score_delta": 0.071,
  "direction": "degrading",
  "new_findings": [
    {
      "signal": "PFS",
      "severity": "HIGH",
      "file": "src/checkout/payment.py",
      "line": 47,
      "title": "Pattern fragmentation: PaymentProcessor variant",
      "message": "New variant conflicts with canonical pattern in handlers.py:CheckoutPaymentHandler",
      "fix": "Consolidate into CheckoutPaymentHandler or extract shared base class"
    },
    {
      "signal": "MDS",
      "severity": "MEDIUM",
      "file": "src/checkout/utils.py",
      "line": 12,
      "title": "Mutant duplicate: validate_amount",
      "message": "Near-identical logic to validators.py:validate_order_amount (similarity: 0.91)",
      "fix": "Remove duplicate and import from validators.py"
    }
  ],
  "resolved_findings": [
    {
      "signal": "TVS",
      "severity": "LOW",
      "file": "src/auth/session.py"
    }
  ],
  "accept_change": false,
  "blocking_reasons": ["HIGH severity finding in src/checkout/payment.py"],
  "trend": {
    "direction": "degrading",
    "delta": 0.071
  }
}
```

### Baseline-Workflow für Release-Vergleiche

```bash
# 1. Beim Release: Baseline speichern
drift check --save-baseline .drift-baseline-v2.0.0.json

# 2. Später: Was hat sich seitdem verändert?
drift diff --baseline .drift-baseline-v2.0.0.json
```

---

## 5. `drift self` — Meta-Analyse: drift analysiert sich selbst

`drift self` ist kein Trend-Werkzeug, sondern ein Meta-Analyse-Command: Es führt eine vollständige drift-Analyse auf dem drift-Quellcode selbst aus. Das ermöglicht es, den aktuellen Gesundheitszustand des drift-Projekts zu inspizieren und dient als Referenzimplementierung dafür, wie `drift analyze` auf einem realen Produktionsprojekt verwendet werden kann.

> **Einschränkung:** `drift self` funktioniert nur innerhalb des drift-Quellcode-Repositorys (`github.com/mick-gsk/drift`). Für externe Projekte: `drift scan` oder `drift analyze` verwenden.

### Verfügbare Flags

| Flag | Kurzform | Standard | Beschreibung |
|------|----------|----------|--------------|
| `--since` | `-s` | `90` | Git-Fenster in Tagen |
| `--format` | `-f` | `rich` | Ausgabeformat: `rich`, `json`, `sarif`, `agent-tasks` |
| `--output` | `-o` | _(stdout)_ | Maschinenausgabe in Datei schreiben |

### Aufrufe

```bash
# Rich-Ausgabe im Terminal
drift self

# Als JSON-Datei für Archivierung
drift self --format json --output benchmark_results/drift_self.json

# Als SARIF (für Code-Scanning-Integration)
drift self --format sarif --output drift_self.sarif
```

### Wann ist `drift self` nützlich?

- **Beitragende:** Überprüfen ob ein eigener Patch neue Findings im drift-Code einführt, bevor er als PR eingereicht wird (`drift self` statt `drift check` für den drift-Repo-Kontext)
- **Maintainer:** Regelmäßige Selbstdiagnose des Projekts als Teil der Qualitätssicherung
- **Referenz:** Verständnis der eigenen Analyse-Heuristiken durch den eigenen Output

Der Command analysiert automatisch nur `src/drift/` (nicht Testdateien oder temporäre Venvs) und fügt temporäre Launch-Venvs zum Ausschluss hinzu, um Score-Verzerrungen in CI zu vermeiden.

---

## 6. Wöchentlicher Health-Report in GitHub Actions

Der folgende Workflow führt jeden Montag `drift trend` und `drift timeline` aus und postet die Ergebnisse als GitHub Job Summary. Er speichert außerdem einen wöchentlichen Snapshot als Artefakt, damit Trends über mehrere Wochen nachvollziehbar bleiben.

```yaml
# .github/workflows/drift-weekly.yml
name: Drift — Weekly Health Report

on:
  schedule:
    - cron: "0 8 * * 1"    # Jeden Montag um 08:00 UTC
  workflow_dispatch:         # Manueller Aufruf möglich

jobs:
  health-report:
    runs-on: ubuntu-latest
    permissions:
      contents: read

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # vollständige Git-History für temporale Signale

      - name: Install drift-analyzer
        run: pip install --quiet drift-analyzer

      - name: Run drift trend
        run: |
          drift trend --repo . --last 90 --config drift.yaml \
            2>&1 | tee /tmp/drift-trend.txt

      - name: Run drift timeline
        run: |
          drift timeline --repo . --since 90 --config drift.yaml \
            2>&1 | tee /tmp/drift-timeline.txt

      - name: Collect JSON snapshot for archiving
        run: |
          drift check --repo . --format json --fail-on none \
            --output /tmp/drift-snapshot.json

      - name: Post Job Summary
        run: |
          echo "## 📊 Drift Weekly Health Report" >> "$GITHUB_STEP_SUMMARY"
          echo "" >> "$GITHUB_STEP_SUMMARY"
          echo "**Date:** $(date -u +'%Y-%m-%d')" >> "$GITHUB_STEP_SUMMARY"
          echo "" >> "$GITHUB_STEP_SUMMARY"

          # Score aus JSON extrahieren
          SCORE=$(python3 -c "
          import json
          d = json.load(open('/tmp/drift-snapshot.json'))
          print(f\"{d['drift_score']:.3f}\")
          ")
          SEVERITY=$(python3 -c "
          import json
          d = json.load(open('/tmp/drift-snapshot.json'))
          print(d['severity'].upper())
          ")
          COUNT=$(python3 -c "
          import json
          d = json.load(open('/tmp/drift-snapshot.json'))
          print(len(d['findings']))
          ")

          echo "| Metric | Value |" >> "$GITHUB_STEP_SUMMARY"
          echo "|--------|-------|" >> "$GITHUB_STEP_SUMMARY"
          echo "| **Drift Score** | \`${SCORE}\` |" >> "$GITHUB_STEP_SUMMARY"
          echo "| **Severity** | ${SEVERITY} |" >> "$GITHUB_STEP_SUMMARY"
          echo "| **Findings** | ${COUNT} |" >> "$GITHUB_STEP_SUMMARY"
          echo "" >> "$GITHUB_STEP_SUMMARY"

          echo "### Trend (letzte 90 Tage)" >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          cat /tmp/drift-trend.txt >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          echo "" >> "$GITHUB_STEP_SUMMARY"

          echo "### Timeline (Modul-Ursachenanalyse)" >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          cat /tmp/drift-timeline.txt >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"

      - name: Upload wöchentlichen Snapshot
        uses: actions/upload-artifact@v4
        with:
          name: drift-snapshot-${{ github.run_id }}
          path: /tmp/drift-snapshot.json
          retention-days: 90
```

### Ergebnis

Nach dem Workflow-Lauf findet sich im GitHub-Repository unter **Actions → der Workflow-Lauf → Summary** eine formatierte Übersicht mit:
- Aktuellem Score und Schweregrad
- Trend-Tabelle der letzten Snapshots
- Timeline-Output mit Modul-Ursachenanalyse

Der hochgeladene Snapshot (`drift-snapshot-*.json`) kann für manuelle Vergleiche oder als Input für `drift diff --baseline` verwendet werden.

---

## Nächste Schritte

- [ci-integration.md](ci-integration.md) — Quality-Gate in CI einrichten und PR-Checks konfigurieren
- [agent-workflow.md](agent-workflow.md) — `drift diff` als Post-Session-Gate in KI-Agenten-Workflows
- [concepts/signals.md](../concepts/signals.md) — Signale verstehen, die in den Trend-Ergebnissen auftauchen
- [reference/commands.md](../reference/commands.md) — Vollständige Flag-Referenz aller Befehle
