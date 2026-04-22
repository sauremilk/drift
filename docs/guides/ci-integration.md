# CI/CD Integration

Dieser Guide richtet sich an Entwickler, die `drift` in eine bestehende CI/CD-Pipeline integrieren wollen. Voraussetzung: `drift-analyzer` ist installiert (`pip install drift-analyzer`).

---

## 1. Pre-commit Hook

Der schnellste Einstieg: drift läuft automatisch vor jedem Commit. Die offiziellen Hook-Definitionen liegen in `.pre-commit-hooks.yaml` und stehen über das `pre-commit`-Framework bereit.

### Minimalkonfiguration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/mick-gsk/drift
    rev: v2.5.1          # durch aktuellen Tag ersetzen
    hooks:
      - id: drift-check
```

Dieser Hook verwendet den in `.pre-commit-hooks.yaml` definierten Standard:
- Eintrittspunkt: `drift check`
- Standard-Threshold: `--fail-on high`
- Läuft bei jeder Python-Datei (`types: [python]`), aber ohne Dateiname-Übergabe (`pass_filenames: false`)
- Läuft immer (`always_run: true`)

### Verfügbare Hooks

| Hook-ID | Verhalten | Empfohlen für |
|---------|-----------|---------------|
| `drift-check` | Blockiert Commit bei Findings ≥ `high` | Produktive Codebases |
| `drift-report` | Zeigt Befunde, blockiert **nicht** | Einführungsphase, Kalibrierung |

### Threshold anpassen

Der Default-Threshold des Hooks (`high`) kann überschrieben werden:

```yaml
repos:
  - repo: https://github.com/mick-gsk/drift
    rev: v2.5.1
    hooks:
      - id: drift-check
        args: [--fail-on, medium]     # strenger
```

Oder nur beobachten ohne zu blockieren:

```yaml
      - id: drift-report              # report-only
```

### Empfohlenes Vorgehen bei der Einführung

1. Starte mit `drift-report` (kein Blocking)
2. Analysiere Befunde und kalibriere `drift.yaml`
3. Wechsle zu `drift-check` mit `--fail-on high`
4. Nach Stabilisierung optional auf `--fail-on medium` verschärfen

---

## 2. GitHub Actions — Quality Gate

### Minimaler Workflow

```yaml
# .github/workflows/drift.yml
name: Drift — Architectural Quality Gate

on:
  pull_request:

jobs:
  drift:
    runs-on: ubuntu-latest
    permissions:
      contents: read

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0           # vollständige Git-History für temporale Signale

      - uses: mick-gsk/drift@v2
        with:
          fail-on: high
```

> **Hinweis:** `fetch-depth: 0` ist erforderlich, damit temporale Signale (TVS, GCD, BAT) korrekt berechnet werden können. Ohne vollständige History fehlt drift der Git-Verlauf.

### Alle verfügbaren Inputs

Abgeleitet aus `action.yml`:

| Input | Typ | Standardwert | Beschreibung |
|-------|-----|-------------|--------------|
| `repo` | string | `.` | Pfad zum Repository-Root zur Analyse |
| `fail-on` | `critical` \| `high` \| `medium` \| `low` \| `none` | `none` | Exit 1 bei Findings ab diesem Schweregrad |
| `since` | integer | `90` | Git-Fenster in Tagen für temporale Signale |
| `format` | `rich` \| `json` \| `sarif` | `rich` | Terminal-Ausgabeformat |
| `config` | string | _(leer)_ | Pfad zu einer `drift.yaml`-Konfigurationsdatei |
| `upload-sarif` | boolean | `false` | SARIF-Ergebnisse in GitHub Code Scanning hochladen (braucht `security-events: write`) |
| `drift-version` | string | `drift-analyzer` | pip-Installationsspezifikation, z. B. `drift-analyzer==2.5.1` |
| `comment` | boolean | `false` | PR-Zusammenfassung als Kommentar posten (nur bei `pull_request`-Events, braucht `pull-requests: write`) |
| `brief` | boolean | `false` | `drift brief` ausführen und als PR-Kommentar posten (nur bei `pull_request`-Events, braucht `pull-requests: write`) |
| `brief-task` | string | _(leer)_ | Aufgabenbeschreibung für `drift brief`; falls leer, wird der PR-Titel verwendet |

### Verfügbare Outputs

| Output | Beschreibung | Beispielwert |
|--------|-------------|--------------|
| `sarif-file` | Absoluter Pfad zur SARIF-Datei (nur wenn `upload-sarif: true`) | `/tmp/drift-results.sarif` |
| `drift-score` | Drift-Score (0.00–1.00) | `0.34` |
| `finding-count` | Gesamtzahl der Befunde | `7` |
| `severity` | Gesamtschweregrad | `HIGH` |

### Threshold-Konfiguration über drift.yaml

Der `fail-on`-Threshold kann statt als Action-Input auch in der `drift.yaml` des Repositorys konfiguriert werden. Die Action liest diese Datei automatisch, wenn `config` auf den Pfad zeigt oder eine `drift.yaml` im Repo-Root liegt.

```yaml
# drift.yaml
thresholds:
  severity_gate: high    # entspricht --fail-on high
```

Beide Methoden — `fail-on` in der Action und `severity_gate` in `drift.yaml` — haben die gleiche Wirkung. Der `fail-on`-Input der Action hat Vorrang.

### Konkretes Beispiel: PR schlägt fehl wenn Score zu hoch

```yaml
# .github/workflows/drift.yml
name: Drift — Quality Gate

on:
  pull_request:

jobs:
  drift:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write      # für den PR-Kommentar

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run drift check
        id: drift
        uses: mick-gsk/drift@v2
        with:
          fail-on: high
          comment: "true"        # Ergebnis als PR-Kommentar posten

      - name: Score im Job Summary zeigen
        if: always()
        run: |
          echo "## Drift Score: ${{ steps.drift.outputs.drift-score }}" >> "$GITHUB_STEP_SUMMARY"
          echo "Severity: ${{ steps.drift.outputs.severity }}" >> "$GITHUB_STEP_SUMMARY"
          echo "Findings: ${{ steps.drift.outputs.finding-count }}" >> "$GITHUB_STEP_SUMMARY"
```

Der PR schlägt ab dem ersten `HIGH`-Finding fehl (Exit Code 1). Der Job-Summary zeigt Score, Schweregrad und Anzahl immer an — auch wenn der Check fehlgeschlagen ist (`if: always()`).

### Erweitert: SARIF-Upload für Code-Scanning-Annotationen

```yaml
      - uses: mick-gsk/drift@v2
        with:
          upload-sarif: "true"
          fail-on: high
        id: drift

      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: ${{ steps.drift.outputs.sarif-file }}
```

Damit erscheinen drift-Befunde als Inline-Annotationen direkt im PR-Diff.

---

## 3. Score-Badge

### Badge generieren

```bash
# URL und Markdown-Snippet ausgeben
drift badge

# Anderen Repository-Pfad analysieren
drift badge --repo /pfad/zum/projekt

# Git-Fenster anpassen (Standard: 90 Tage)
drift badge --since 60

# Badge-Stil wählen
drift badge --style flat-square   # flat | flat-square | for-the-badge | plastic

# URL in Datei schreiben (für CI-Artefakte)
drift badge --output badge-url.txt
```

Die Farbe wird automatisch aus dem Score abgeleitet:

| Score-Bereich | Farbe | Bedeutung |
|--------------|-------|-----------|
| CRITICAL | `critical` (rot) | Schwere Erosion |
| HIGH | `orange` | Erhöhte Erosion |
| MEDIUM | `yellow` | Moderate Erosion |
| LOW / INFO | `brightgreen` | Gesunder Code |

### Konstruiertes Beispiel-Output

```
drift badge

  Score: 0.23  (low)

  URL:
    https://img.shields.io/badge/drift%20score-0.23-brightgreen?style=flat

  Markdown:
    [![Drift Score](https://img.shields.io/badge/drift%20score-0.23-brightgreen?style=flat)](https://github.com/mick-gsk/drift)
```

### Badge ins README einbinden

Das generierte Markdown-Snippet direkt in die `README.md` kopieren:

```markdown
<!-- In README.md -->
[![Drift Score](https://img.shields.io/badge/drift%20score-0.23-brightgreen?style=flat)](https://github.com/mick-gsk/drift)
```

Für einen statisch aktuellen Badge empfiehlt sich ein wöchentlicher CI-Job, der `drift badge --output badge-url.txt` ausführt und den Badge-Link im README aktualisiert.

---

## 4. Exit-Code-Referenz

Alle Exit-Codes sind in `src/drift/errors.py` definiert. Die folgende Tabelle ist direkt daraus abgeleitet:

| Exit Code | Konstante | Bedeutung | Empfohlene CI-Reaktion |
|-----------|-----------|-----------|------------------------|
| `0` | `EXIT_OK` | Erfolg — keine Findings über dem Threshold | Job grün markieren |
| `1` | `EXIT_FINDINGS_ABOVE_THRESHOLD` | Findings erreichen oder überschreiten den `--fail-on`-Threshold | Job fehlschlagen lassen; Befunde im Summary anzeigen |
| `2` | `EXIT_CONFIG_ERROR` | Konfigurationsfehler (ungültige `drift.yaml`, unbekanntes Signal) | Job fehlschlagen lassen; Fehlermeldung zur Diagnose ausgeben |
| `3` | `EXIT_ANALYSIS_ERROR` | Analyse-Pipeline-Fehler (AST-Parse-Fehler, Signal-Fehler; partielle Ergebnisse möglich) | Warnung loggen; optionaler Retry; Job nach Wunsch fehlschlagen lassen |
| `4` | `EXIT_SYSTEM_ERROR` | System-Fehler (I/O, git, Berechtigungen, fehlende Abhängigkeiten) | Job fehlschlagen lassen; Umgebung und Berechtigungen prüfen |
| `130` | `EXIT_INTERRUPTED` | Abgebrochen (Strg+C / SIGINT) | Manueller Abbruch; keine automatische Reaktion nötig |

**Hinweis zur Unterscheidung von Code 1 und Code 2–4:** Nur Code 1 bedeutet, dass drift erfolgreich gelaufen ist und ein Quality-Gate ausgelöst hat. Codes 2–4 sind Fehler-Zustände, bei denen das Analyse-Ergebnis unvollständig oder gar nicht vorhanden ist.

---

## 5. Trend-Tracking — Snapshots über CI-Läufe hinweg persistieren

`drift trend` ist nur dann aussagekräftig, wenn Snapshots über Tage und Wochen hinweg gesammelt werden. Jede `drift analyze`-Ausführung speichert automatisch einen Snapshot in `.drift-cache/history.json`. Damit diese Datei zwischen CI-Läufen erhalten bleibt, muss das Cache-Verzeichnis als Actions-Cache persistiert werden.

### Minimalkonfiguration: Wöchentlicher Trend-Job

```yaml
# .github/workflows/drift-trend.yml
name: Drift — Trend-Tracking

on:
  schedule:
    - cron: "0 3 * * 1"   # jeden Montag 03:00 UTC
  workflow_dispatch:

jobs:
  trend:
    runs-on: ubuntu-latest
    permissions:
      contents: read

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Snapshot-Cache wiederherstellen
        uses: actions/cache@v4
        with:
          path: .drift-cache
          key: drift-cache-${{ runner.os }}-${{ github.ref_name }}
          restore-keys: |
            drift-cache-${{ runner.os }}-

      - name: Analyse ausführen (Snapshot wird automatisch gespeichert)
        uses: mick-gsk/drift@v2
        with:
          fail-on: none

      - name: Trend anzeigen
        run: pip install drift-analyzer && drift trend --repo .
```

> **Warum `fail-on: none`?** Der Trend-Job soll den Score rein beobachten, nicht blockieren. Quality-Gates laufen im separaten PR-Workflow.

> **Cache-Key-Strategie:** Der `restore-keys`-Fallback stellt sicher, dass auch nach Branch-Wechseln auf den letzten verfügbaren Snapshot-Cache zurückgefallen wird.

### Integration in bestehenden Analyze-Job

Wenn bereits ein `drift analyze`-Job läuft, genügt das Ergänzen des Cache-Steps:

```yaml
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Snapshot-Cache
        uses: actions/cache@v4
        with:
          path: .drift-cache
          key: drift-cache-${{ runner.os }}-${{ github.sha }}
          restore-keys: |
            drift-cache-${{ runner.os }}-

      - uses: mick-gsk/drift@v2
        with:
          fail-on: high
```

Nach einigen Läufen über mehrere Tage zeigt `drift trend` einen aussagekräftigen Verlauf:

```
  Score History (last 10)
  ┌─────────────────────┬────────┬────────┬──────────┐
  │ 2026-04-14 03:02:11 │  0.281 │ —      │ 12       │
  │ 2026-04-21 03:01:44 │  0.294 │ +0.013 │ 14       │
  │ 2026-04-28 03:03:02 │  0.287 │ -0.007 │ 13       │
  └─────────────────────┴────────┴────────┴──────────┘
  Overall trend (3 snapshots): → stable  (+0.006)
```

---

## 6. Häufige Fehler

### 1. Git-History fehlt — temporale Signale greifen nicht

**Symptom:** `drift check` läuft durch, aber TVS-, GCD- oder BAT-Findings bleiben aus, obwohl die Codebase entsprechende Muster aufweist.

**Ursache:** In GitHub Actions wird standardmäßig nur ein flacher Checkout gemacht (`fetch-depth: 1`), der keine Git-History enthält.

**Lösung:**
```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0   # vollständige History laden
```

---

### 2. `drift check` schlägt fehl mit Exit Code 2 — unbekannte Konfiguration

**Symptom:** CI schlägt fehl mit einer Meldung wie `[DRIFT-1001] Invalid config value` oder `[DRIFT-1002] Configuration file is not valid`.

**Ursache:** In `drift.yaml` wurde ein Feld mit einem ungültigen Wert belegt oder ein unbekanntes Signal referenziert.

**Lösung:** Lokale Diagnose:
```bash
drift config show    # zeigt aktive Konfiguration
drift check --config drift.yaml   # validiert die Datei
```

Im Signal-Namen vertippt? Verfügbare IDs prüfen:
```bash
drift explain --list
```

---

### 3. Pre-commit Hook schlägt bei legacy Codebase sofort fehl

**Symptom:** Erster `git commit` nach Hook-Installation schlägt mit vielen Findings fehl.

**Ursache:** Bestehende Codebase enthält akkumulierte Drift-Muster, die auf dem Standard-Threshold (`high`) sofort ausgelöst werden.

**Lösung:** Einführungsphase mit Report-Only durchlaufen:
```yaml
hooks:
  - id: drift-report     # kein Blocking
```
Oder bekannte Befunde als Baseline speichern und ignorieren:
```bash
drift check --save-baseline .drift-baseline.json
# Danach im Hook:
# args: [--fail-on, high, --baseline, .drift-baseline.json]
```

---

### 4. Ausgabe enthält Rich-Escape-Sequenzen in CI-Logs

**Symptom:** CI-Log enthält ANSI-Farbcodes und Rich-Markup, die die Lesbarkeit verschlechtern.

**Ursache:** `drift check` verwendet standardmäßig Rich-Formatierung mit Farben.

**Lösung:**
```yaml
# In der Action: format: json für maschinenlesbare Ausgabe
with:
  format: json

# Oder in der CLI:
drift check --no-color
drift check --format json
```

---

### 5. Score schwankt zwischen CI-Läufen ohne Code-Änderungen

**Symptom:** Gleicher Commit ergibt in zwei CI-Läufen unterschiedliche Scores.

**Ursache:** Temporale Signale (TVS, GCD) basieren auf dem Zeitschiebefenster (`--since`). Wenn ein Commit kurz vor dem Ablauf des Fensters liegt, kann er bei einem Lauf einbezogen und beim nächsten nicht mehr.

**Lösung:** Festes `since`-Fenster in `drift.yaml` oder als Action-Input:
```yaml
# drift.yaml
since_days: 90   # explizit auf stabilen Wert setzen
```
Oder in der Action:
```yaml
with:
  since: "90"
```

---

---

## Nächste Schritte

- [Quickstart](quickstart.md) — Erste Analyse und Kalibrierung
- [health-over-time.md](health-over-time.md) — Score-Trend langfristig beobachten
- [agent-workflow.md](agent-workflow.md) — drift in KI-Agenten-Sessions einsetzen
- [reference/configuration.md](../reference/configuration.md) — Vollständige `drift.yaml`-Referenz
