---
id: ADR-052
status: proposed
date: 2026-04-11
type: output-format
supersedes:
---

# ADR-052: PR-Comment Output Format + SARIF Remediation Enrichment

## Problemklasse

Drift verfügt über 9 Output-Formate, aber keines eignet sich für den häufigsten sozialen Sharing-Kontext: den **GitHub Pull Request Kommentar**. Der `markdown`-Report ist vollständig (100+ Zeilen mit Preflight, Module-Scores, Signal-Coverage), nicht für PR-Kommentare geeignet. SARIF-Annotations im Code-Scanning enthalten das `fix`-Feld, aber keine `generate_recommendation()`-Ausgabe. Beide Lücken reduzieren die soziale Anschlussfähigkeit und die Einführbarkeit.

## Entscheidung

### 1. Neues Format `--format pr-comment`

Neue Datei `src/drift/output/pr_comment.py` mit Funktion `analysis_to_pr_comment(analysis, max_findings=5) -> str`.

**Design-Constraints:**
- Max. 5 Findings (hartcodiert in CLI-Dispatch)
- Signal-Langname statt Abkürzung (`signal_registry.get_meta()`)
- Action-Spalte aus `generate_recommendation().title` oder `f.fix` (Fallback)
- **Keine** Preflight-Diagnostics, Module-Scores, Signal-Coverage, Interpretation-Footer
- Score + Trend-Delta immer im Summary-Block

**Ausgabe-Template:**
```markdown
## 🔍 Drift Analysis · `{repo}` · {date}

| Score | Severity | Trend | Findings |
|-------|----------|-------|----------|
| **{score}** ({grade}) | {emoji} {severity} | {arrow} {delta} {direction} | {total} total, {high} high |

### Top Findings

| # | Severity | Signal | Location | Action |
|---|----------|--------|----------|--------|
| 1 | {emoji} {sev} | {signal_name} | `{file}:{line}` | {action} |

*{n} of {total} findings shown · [drift v{version}](https://github.com/mick-gsk/drift)*
```

### 2. SARIF `message.text` + `help` Anreicherung

SARIF-Findings in `findings_to_sarif()` werden um `generate_recommendation()` erweitert:
- `result["message"]["text"]`: Bereits vorhandenes `f.fix`-Suffix ergänzen mit `rec.title` wenn vorhanden; auf 400 Zeichen kappen.
- `rule_obj["help"]`: Neues Feld mit `text` und `markdown` aus `rec.description` für Signale, die einen Recommender haben.

### 3. Markdown Compact-Mode

`analysis_to_markdown()` erhält zwei neue optionale Parameter:
- `include_modules: bool = True` — wenn False: kein `## Module Scores`-Block
- `include_signal_coverage: bool = True` — wenn False: kein `## Signal Coverage`-Block

CLI: Das bestehende `--compact` Flag wirkt jetzt auch auf `--format markdown` (max 5 Findings, Module-Scores und Signal-Coverage ausgeblendet).

### 4. CSV `signal_label`-Spalte

`analysis_to_csv()` erhält eine neue `signal_label`-Spalte nach `signal` mit dem menschenlesbaren Signal-Langnamen via `signal_registry.get_meta()`.

**Breaking Change:** CSV-Spaltenindizes verschieben sich.

## Abgrenzung

| Format | Zweck | Zielkontext |
|--------|-------|-------------|
| `markdown` | Vollständiger Report | Wiki, Issue-Body, Archiv |
| `pr-comment` | Kurzfassung für Reviewer | PR-Kommentar, Slack |
| `sarif` | Maschinenlesbar, CI-Annotations | GitHub Code Scanning |
| `github` | GitHub Actions Annotations | CI Logs |

## Begründung

Das Format `pr-comment` schließt den einzigen unbesetzten sozialen Sharing-Kanal mit niedrigem Implementierungsaufwand (reines Template, kein neues Modell). Die SARIF-Ergänzung macht bestehende Code-Scanning-Workflows sofort actionable. Der Markdown-Compact-Mode reduziert die Hürde für manuelle Weitergabe ohne neues Top-Level-Format. Die CSV-Ergänzung macht das Format außerhalb der Drift-Community verwendbar.

Alle Änderungen liegen ausschließlich im Output-Layer — kein Signal-, Scoring- oder Ingestion-Code berührt.

## Risiken

- CSV Breaking Change: wird im CHANGELOG als `BREAKING CHANGE` dokumentiert
- SARIF `message.text` 400-Zeichen-Cap: basiert auf GitHub-UI-Praxis, nicht SARIF-Spec; konservativ gewählt
- `pr-comment` ohne Trend-Baseline: wenn `analysis.trend is None`, wird `n/a` angezeigt — kein Anzeigefehler

## Status-Verlauf

- 2026-04-11: `proposed` (automatisch generiert)
