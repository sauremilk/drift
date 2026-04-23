# Quickstart

Dieser Guide führt dich in 10 Minuten von der Installation bis zum ersten aussagekräftigen Befund. Voraussetzung: Python 3.11+, ein Git-Repository.

---

## 1. Installation

### Standard-Installation (empfohlen)

```bash
pip install drift-analyzer
```

### Schnellstart ohne Installation (uvx)

```bash
uvx drift-analyzer analyze --repo .
```

> `uvx` führt drift in einer temporären, isolierten Umgebung aus. Keine dauerhafte Installation nötig.

### MCP-Server-Unterstützung (für KI-Agenten und IDE-Integration)

```bash
pip install drift-analyzer[mcp]
```

Der MCP-Extra aktiviert den Model Context Protocol-Server, der drift in VS Code, Claude Desktop und kompatible Agenten-Umgebungen einbettet. Lies [`agent-workflow.md`](agent-workflow.md) für Details.

---

## 2. `drift init` — Repository einrichten

`drift init` erzeugt eine `drift.yaml`-Konfiguration und optional weitere Integrationsdateien. Ohne Flags erzeugt es nur die Konfiguration:

```bash
drift init
```

Mit `--full` werden alle Integrationsdateien auf einmal angelegt:

```bash
drift init --full
```

**Was wird erzeugt:**

| Flag | Datei | Zweck |
|------|-------|-------|
| _(kein Flag)_ | `drift.yaml` | Analyse-Konfiguration (Profile, Gewichte, Ausschlüsse) |
| `--ci` | `.github/workflows/drift.yml` | GitHub Actions Workflow |
| `--hooks` | `.githooks/drift-pre-push` | Git Pre-Push-Hook |
| `--mcp` | `.vscode/mcp.json` | VS Code MCP-Server-Konfiguration |
| `--claude` | `claude_desktop_config.json` | Claude Desktop MCP-Snippet |
| `--full` | alle obigen | Kombiniert alle Flags |

**Profile** passen die Analyse an typische Entwicklungsszenarien an:

```bash
drift init --profile vibe-coding    # Höhere Gewichte für KI-typische Muster
drift init --profile strict         # Strenge Schwellwerte für vollständig manuellen Code
drift init --profile default        # Ausgewogene Standardgewichte
```

**Vorschau ohne Schreiben:**

```bash
drift init --full --dry-run         # Zeigt welche Dateien erzeugt würden
drift init --full --json            # Gleiche Vorschau als maschinenlesbares JSON
```

**Beispiel-Output nach `drift init`:**
```
# Beispiel-Output
  create drift.yaml
  create .github/workflows/drift.yml
  create .githooks/drift-pre-push
  create .vscode/mcp.json
  create claude_desktop_config.json
```

Die erzeugte `drift.yaml` legt fest, welche Dateien analysiert werden (`include`/`exclude`), welches Git-Fenster gilt (`since_days`) und mit welchen Gewichten die Signale in den Composite Score einfließen. Die Datei ist von Anfang an kommentiert und kann direkt angepasst werden.

---

## 3. `drift scan` — Erste Analyse

`drift scan` ist der agent-native Scan-Befehl und gibt strukturiertes JSON zurück. Er analysiert das aktuelle Repository und gibt die wichtigsten Befunde aus:

```bash
drift scan
```

Mit explizitem Repo-Pfad und begrenzten Findings:

```bash
drift scan --repo ./mein-projekt --max-findings 5
```

**Wichtige Optionen:**

| Option | Standard | Bedeutung |
|--------|----------|-----------|
| `--repo` / `-r` | `.` | Pfad zum Repository-Root |
| `--since` | `90` | Tage Git-History, die berücksichtigt werden |
| `--max-findings` | `10` | Maximale Anzahl zurückgegebener Befunde (1–200) |
| `--select` | alle | Nur bestimmte Signal-IDs auswerten, z. B. `PFS,AVS` |
| `--exclude` | keine | Signal-IDs ausschließen, z. B. `TVS,DIA` |
| `--strategy` | `diverse` | Auswahlstrategie: `diverse` (Vielfalt) oder `top-severity` |
| `--output` / `-o` | stdout | JSON-Ausgabe in Datei schreiben |
| `--progress` | `auto` | Fortschritt: `auto`, `json` (stderr), `none` |

**Beispiel-Output (gekürzt):**
```json
// Beispiel-Output
{
  "schema_version": "2.1",
  "drift_score": 0.42,
  "severity": "medium",
  "finding_count": 3,
  "findings": [
    {
      "id": "PFS-001",
      "signal_type": "pattern_fragmentation",
      "severity": "high",
      "score": 0.74,
      "title": "Error handling fragmented (3 variants)",
      "file_path": "src/api/handlers.py",
      "start_line": 12,
      "end_line": 58,
      "description": "Three incompatible error-handling strategies detected in one module.",
      "suggestion": "Consolidate to one canonical pattern per module."
    }
  ]
}
```

**Was die Felder bedeuten:**

- `drift_score` — Gewichteter Composite-Score (0.0–1.0); 0.42 entspricht Severity `medium`
- `severity` — Aggregierte Severity des Repos (`info` / `low` / `medium` / `high` / `critical`)
- `signal_type` — Welches Signal den Befund ausgelöst hat (siehe [signals.md](../concepts/signals.md))
- `score` — Konfidenz des Befunds (0.0–1.0)
- `suggestion` — Konkreter Handlungshinweis

---

## 4. `drift explain` — Einen Befund verstehen

Hat `drift scan` einen Befund zurückgegeben, erklärt `drift explain` das zugrundeliegende Signal:

```bash
drift explain PFS        # Pattern Fragmentation Signal erklären
drift explain AVS        # Architecture Violation Signal erklären
drift explain --list     # Alle verfügbaren Signals auflisten
```

**Beispiel-Output:**

```
# Beispiel-Output
Signal: PFS — Pattern Fragmentation Score
Weight: 0.16

Beschreibung:
  Erkennt, wenn dieselbe Kategorie von Code-Mustern (z. B. Fehlerbehandlung,
  Validierung, Datenbankzugriff) mehrere inkompatible Implementierungsvarianten
  innerhalb eines Moduls hat.

Erkennt:
  Copy-paste-modify-Muster, die typisch für Multi-Session-KI-Generierung sind.

Beispiel:
  # Variante A — Custom Exception
  raise ValidationError(msg)

  # Variante B — Return Code
  return None, error_msg

  # Variante C — Bare except
  try: ... except: log(e)

Fix-Hinweis:
  In einer kanonischen Variante konsolidieren. Die expliziteste Variante wählen
  und die anderen refactoren.
```

`drift explain` funktioniert auch für Fehlercodes aus dem strukturierten Error-System:

```bash
drift explain DRIFT-1001   # Konfigurationsfehler erklären
drift explain DRIFT-2010   # Fehlende optionale Abhängigkeit erklären
```

---

## 5. `drift check` — CI-Integration

`drift check` ist der Befehl für CI-Pipelines. Er analysiert das Diff zu einem Git-Referenzpunkt und gibt Exit Code 1 zurück, wenn Befunde die konfigurierte Schwelle überschreiten:

```bash
drift check                        # Vergleicht mit HEAD~1 (Standard)
drift check --diff main            # Vergleicht aktuellen Branch mit main
drift check --fail-on high         # Exit 1 bei high oder critical
drift check --fail-on medium -q    # Minimal-Output für CI-Logs
```

**Exit-Code-Semantik:**

| Exit Code | Bedeutung |
|-----------|-----------|
| `0` | Analyse erfolgreich, Schwellwert nicht überschritten |
| `1` | Findings erreichen oder überschreiten `--fail-on`-Schwellwert |
| `2` | Konfigurationsfehler (ungültige Flags, fehlende Datei) |
| `3` | Analysefehler (AST-Parse-Fehler, Signal-Fehler) |
| `4` | Systemfehler (I/O, git nicht verfügbar) |

**Wichtige Optionen:**

| Option | Standard | Bedeutung |
|--------|----------|-----------|
| `--diff` | `HEAD~1` | Git-Ref für Vergleich |
| `--fail-on` | _(aus drift.yaml)_ | Schwellwert: `none` / `low` / `medium` / `high` / `critical` |
| `--quiet` / `-q` | `false` | Minimalausgabe: Score, Severity, Count, Exit Code |
| `--exit-zero` | `false` | Immer Exit 0 (nur berichten, nicht blockieren) |
| `--output-format` / `-f` | `rich` | Format: `rich`, `json`, `sarif`, `csv`, `github` |
| `--baseline` | _(keins)_ | Bekannte Findings aus einer Baseline-Datei unterdrücken |

**Warum `drift check` in CI wichtig ist:**

In einer KI-assistierten Entwicklungsumgebung kann jeder PR latente Strukturprobleme einführen, ohne dass Tests scheitern oder Lint-Regeln anschlagen. `drift check` schließt diese Lücke: Es analysiert ausschließlich die geänderten Dateien und blockiert PRs, die bekannte Muster wie Pattern Fragmentation oder Architekturverletzungen neu einführen — bevor sie in `main` landen.

Das `--fail-on`-Flag bestimmt die Aggressivität. Ein guter Einstiegspunkt ist `--fail-on high`, das nur echte, hochkonfidente Strukturprobleme blockiert.

**Beispiel: Minimaler CI-Step (GitHub Actions):**

```yaml
# Beispiel-Output
- uses: mick-gsk/drift@v2
  with:
    fail-on: "high"
    comment: "true"
```

---

## Nächste Schritte

- [**agent-workflow.md**](agent-workflow.md) — Drift in KI-Agenten-Workflows einbetten (MCP-Server, Guardrails, Nudge-Loop)
- [**ci-integration.md**](ci-integration.md) — Vollständige CI/CD-Integration mit GitHub Actions, SARIF, Baselines
- [**../concepts/signals.md**](../concepts/signals.md) — Alle Signals verstehen: Was wird gemessen, wann ist es kritisch?
- [**../concepts/baseline.md**](../concepts/baseline.md) — Bestehende Findings supprimieren, inkrementelle Adoption
- [**../concepts/scoring.md**](../concepts/scoring.md) — Wie der Drift-Score berechnet wird und was die Schwellwerte bedeuten
