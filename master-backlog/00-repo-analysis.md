# Phase 0 — Repo-Analyse für LLM-Sichtbarkeit

> Erstellt: 2026-03-25 | Branch: `llm-visibility-quickwins`

---

## README.md

### Vorhanden
- Titel mit starkem Claim ("Find the architecture damage AI coding tools leave behind")
- Badges: CI, codecov, PyPI, Downloads, Python, License, pre-commit, SARIF, TypeScript, Ruff, Stars, Documentation
- Try-it-now Abschnitt mit `pip install drift-analyzer`
- Demo-GIF und Demo-Projekt
- "Why drift" Abschnitt mit 4 Erosions-Mustern
- Setup: GitHub Action, CI gate, pre-commit hook
- "What you get" Beispiel-Output
- Signal-Familien aufgelistet (6 + DIA)
- Zielgruppen: "Ideal for", "Who should adopt now", "Who should wait"
- Trust & Limitations Abschnitt
- Contributing Verweis

### Fehlt (gemäß Anforderungen)
- **"What is drift?" Abschnitt** — Kurztext fehlt als eigenständiger, zitierbarer Abschnitt. Der Titel ist stark, aber kein LLM-lesbarer 2-3-Satz-Absatz mit Pflicht-Keywords.
- **Vergleichstabelle (drift vs. Alternativen)** — Nur prosaisch im Body erwähnt, nicht als eigenständige Tabelle im README.
- **Use Cases** — "Ideal for" listet Zielgruppen, aber keine konkreten Problem→Lösung→Befehl→Output-Szenarien.

### Darf nicht überschrieben werden
- Titel, Badges, Beschreibungsabsatz
- Bestehende Setup-Beispiele (GitHub Action, pre-commit)
- Trust & Limitations
- Contributing

---

## pyproject.toml

### Vorhanden
- `name = "drift-analyzer"`, `version = "0.5.0"`
- `description` mit relevanten Keywords
- 18 Keywords (code-analysis, technical-debt, architecture-drift, architectural-linter, ai-code, copilot, github-copilot, cursor, github-action, sarif, static-analysis, code-quality, u.a.)
- Classifiers: Development Status Alpha, Intended Audience Developers, Quality Assurance, Testing, MIT, Python 3.11–3.13, Console, Typed
- URLs: Homepage, Repository, Issues, Documentation, Changelog
- Dependencies, optional-dependencies, scripts, build config

### Fehlt (gemäß Anforderungen)
- Keywords: `"dependency analysis"`, `"monorepo"`, `"dependency cycle detection"`, `"import analysis"`, `"python linter"`, `"architecture enforcement"` — **teilweise fehlend**. Genau abzugleichen:
  - `"architectural linter"` → vorhanden als `"architectural-linter"`
  - `"static analysis"` → vorhanden als `"static-analysis"`
  - `"technical debt"` → vorhanden als `"technical-debt"` und `"technical-debt-detection"`
  - `"dependency analysis"` → **fehlt**
  - `"code quality"` → vorhanden als `"code-quality"`
  - `"monorepo"` → **fehlt**
  - `"dependency cycle detection"` → **fehlt**
  - `"import analysis"` → **fehlt**
  - `"python linter"` → **fehlt**
  - `"architecture enforcement"` → **fehlt**
- Classifiers:
  - `"Topic :: Software Development :: Quality Assurance"` → **vorhanden**
  - `"Topic :: Software Development :: Libraries :: Python Modules"` → **fehlt**
  - `"Intended Audience :: Developers"` → **vorhanden**

### Darf nicht überschrieben werden
- Bestehende keywords, classifiers, dependencies
- Version, name, description
- Build-System-Konfiguration

---

## llms.txt

### Vorhanden
- Projekt-Name, Kurzbeschreibung (1 Satz)
- Package-Name, Install-Befehl, Repository-URL, Docs-URL
- CLI-Befehl
- Keywords (10 Stück)
- Summary (1 Absatz)

### Fehlt (gemäß llmstxt.org-Standard)
- **Primäre Use Cases** (Stichpunkte)
- **Link zu STUDY.md**
- **Link zu CHANGELOG.md**
- **Sections** gemäß llmstxt.org: `## Docs`, `## Optional` mit strukturierten Link-Listen
- Maschinenlesbares Format nach Standard (H1 Titel, Blockquote Beschreibung, H2 Sektionen)

### Darf nicht überschrieben werden
- Bestehende Informationen (nur ergänzen)

---

## OUTREACH.md

### Vorhanden
- Naming + Claim Guardrails (Repo, Package, Command, safe signal claims)
- Show HN Text (fertig formuliert)
- Reddit r/Python, r/programming, r/softwarearchitecture, r/devops Texte
- awesome-static-analysis PR-Entwurf
- awesome-python PR-Entwurf
- Reddit r/ExperiencedDevs Diskussionstext
- Twitter/X Thread (5 Tweets)
- dev.to / Hashnode Artikel-Entwurf

### Fehlt
- Nichts gemäß Aufgabenstellung — OUTREACH.md deckt die meisten Outreach-Formate ab. Für Phase 3 können Drafts daraus abgeleitet werden.

### Darf nicht überschrieben werden
- Gesamte Datei (Referenzquelle für Outreach-Drafts)

---

## STUDY.md

### Vorhanden
- Executive Summary mit safe claims (97.3% precision, 86% recall, 15 repos)
- Methodology (1.1–1.3)
- Benchmark Results (2.1–2.4): Scores für 5 Primär-Repos
- Ground-Truth Precision Analysis (3.1–3.3): 263 klassifizierte Findings
- Controlled Mutation Benchmark (4.1–4.5): 14 Mutationen, 86% Recall
- Usefulness Case Studies (5.1–5.3): PWBS-Beispiele
- AI-Attribution Signal (§6)
- Threats to Validity (§7): 8 dokumentierte Limitations
- Reproducibility (§8)
- Tool Landscape Comparison (§9): Capability Matrix, Key Differentiators
- v0.2 Signal Enhancements (§10)

### Fehlt
- Nichts gemäß Aufgabenstellung — STUDY.md ist die Primär-Datenquelle für Vergleichstabellen und Outreach.

### Darf nicht überschrieben werden
- Gesamte Datei (Referenzquelle für alle Vergleiche und Claims)

---

## CHANGELOG.md

### Vorhanden
- v0.5.0 (2026-03-23): CLI Sort-By, AVS Mutations, Benchmark x15, MkDocs, CLI Refactor
- v0.3.0 (2026-03-20): Evaluation Framework, Temporal Drift, Smoke Tests
- v0.2.0 (2026-03-19): DIA, AVS, MDS Enhancements, Embeddings
- v0.1.0 (2026-02-15): Initial release

### Fehlt
- Nichts gemäß Aufgabenstellung.

### Darf nicht überschrieben werden
- Gesamte Datei

---

## mkdocs.yml

### Vorhanden
- Vollständige Navigation mit 12 Top-Level-Sektionen
- Bereits existierend: Use Cases (4 Seiten), Comparisons (3 Seiten), FAQ, Glossary, Case Studies (3)
- Trust & Evaluation Sektion
- Product Sektion

### Fehlt (gemäß Anforderungen)
- `docs/comparison.md` → Existiert bereits als `docs-site/comparisons/` mit 3 Vergleichsseiten. **Kein Bedarf für separate comparison.md.**
- `docs/use-cases.md` → Existiert bereits als `docs-site/use-cases/` mit 4 Seiten. **Kein Bedarf.**
- `docs/faq.md` → Existiert als `docs-site/faq.md` mit ~8 Fragen. **Ergänzung auf min. 10 Fragen nötig.**

### Darf nicht überschrieben werden
- Bestehende Navigation und Theme-Konfiguration

---

## docs/ Verzeichnis

### Vorhanden (docs/)
- `adr/` — Architecture Decision Records
- `go-mvp-scope.md`, `language-roadmap.md`, `language-support-matrix.md`
- `PRODUCT_STRATEGY.md`, `python-baseline.md`, `python-rule-inventory.md`, `tsjs-mvp-scope.md`

### Vorhanden (docs-site/)
- `algorithms/` (deep-dive, signals, scoring)
- `case-studies/` (index, fastapi, pydantic, django)
- `comparisons/` (drift-vs-ruff, drift-vs-semgrep-codeql, drift-vs-architecture-conformance)
- `getting-started/` (installation, quickstart, team-rollout, finding-triage, configuration)
- `use-cases/` (4 Seiten)
- `product/` (press-brand)
- `reference/` (api-outputs)
- `faq.md`, `glossary.md`, `integrations.md`, `trust-evidence.md`, `benchmarking.md`

### Fehlt
- FAQ hat < 10 Fragen → ergänzen
- Phase 3 Seiten: comparison.md und use-cases.md existieren bereits als Directories in docs-site/. Stattdessen: ggf. zentrale Übersichtsseiten erstellen.

---

## benchmark_results/

### Vorhanden
- 15 Repository-Benchmarks (json + full JSON)
- all_results.json (aggregiert)
- ground_truth_analysis.json, ground_truth_labels.json
- mutation_benchmark.json, holdout_validation.json
- Temporal Django-Studie

### Nutzbar für
- Vergleichstabellen in README und docs/comparison.md
- Outreach-Drafts (zahlenbasiert)

---

## Zusammenfassung: Handlungsbedarf je Phase

| Phase | Aufgabe | Status |
|-------|---------|--------|
| 1 | Baseline-Vorlage (10 Prompts) | Neu erstellen |
| 2.1 | pyproject.toml: 6 fehlende Keywords + 1 Classifier | Ergänzen |
| 2.2 | README.md: "What is drift?", Vergleichstabelle, Use Cases | Ergänzen |
| 2.3 | llms.txt: Use Cases, Links, llmstxt.org-Konformität | Erweitern |
| 2.4 | Manuelle Schritte dokumentieren | Neu erstellen |
| 3.1 | docs/comparison.md → als Übersicht über bestehende comparisons/ | Neu erstellen |
| 3.1 | docs/use-cases.md → als Übersicht über bestehende use-cases/ | Neu erstellen |
| 3.1 | docs/faq.md → auf min. 10 Fragen erweitern | Ergänzen |
| 3.2 | Outreach-Drafts (dev.to, Show HN, awesome-list) | Aus OUTREACH.md ableiten |
| 4 | Tracking-Template | Neu erstellen |
