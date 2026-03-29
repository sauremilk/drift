# Launch Checklist

Status-Tracker für den öffentlichen Launch von Drift.
Jeder Punkt hat einen Status und ggf. eine Erklärung was noch fehlt.

Last updated: v0.9.0 (2026-03-29)

---

## Phase 1 — Repo-Qualität finalisieren

- [x] **Debug-Artifacts entfernt** — `action_rate_err.txt`, `diag_err.txt`, `action_rate_test.txt` sind in `.gitignore` und nicht git-tracked. Nur lokal vorhanden.
- [x] **CI/CD Badges im README** — CI, Precision, Codecov, PyPI, Downloads, Python, License, pre-commit, SARIF, Ruff, Stars, Docs — alle vorhanden.
- [x] **Pre-Commit Hooks** — `.pre-commit-hooks.yaml` mit `drift-check` (gate) und `drift-report` (report-only). Remote-Hook-Anleitung in README und `docs-site/integrations.md`.
- [ ] **Demo-GIF rendern** — `demos/demo.tape` ist fertig, `demos/demo.gif` ist aktuell ein Placeholder (34 Bytes). Rendern mit: `vhs demos/demo.tape` (vhs ist installiert). README verweist bereits auf `demos/demo.gif`.
- [ ] **PyPI Release veröffentlichen** — Workflow `publish.yml` ist fertig (Trusted Publishing). Schritte:
  1. PyPI Trusted Publisher konfigurieren: https://pypi.org/manage/account/publishing/ (Repo: `sauremilk/drift`, Workflow: `publish.yml`, Environment: `pypi`)
  2. GitHub Environment `pypi` im Repo erstellen (Settings → Environments)
  3. Release erstellen: `gh release create v1.1.0 --title "v1.1.0" --generate-notes`
  4. Workflow veröffentlicht automatisch zu PyPI
  5. Kurz prüfen:
     - `gh release view vX.Y.Z`
     - `python -m pip index versions drift-analyzer`
     - `python -m pip install --upgrade drift-analyzer==X.Y.Z`
- [ ] **GitHub Pages aktivieren** — Workflow `docs.yml` ist fertig (MkDocs Material). Schritte:
  1. Repo Settings → Pages → Source: "GitHub Actions"
  2. Push zu `main` mit Änderung in `docs-site/` oder `mkdocs.yml` triggert Deploy
  3. Prüfen: https://sauremilk.github.io/drift/
- [ ] **GitHub Discussions aktivieren** — Settings → General → Features → Discussions ✓. Issue-Templates verweisen bereits auf Discussions.

---

## Phase 2 — Launch-Content

Alle Texte stehen in [`OUTREACH.md`](OUTREACH.md) — Copy-Paste-fertig.

- [ ] **Demo-Run auf FastAPI** — Ergebnisse bereits vorhanden in `benchmark_results/fastapi.json` (Score 0.62, 360 Findings). Für Screenshot: `drift analyze --repo <fastapi-clone> --format rich` ausführen und Terminal-Screenshot speichern.
- [x] **Show HN Text** — Fertig in OUTREACH.md §1
- [x] **Reddit r/Python Text** — Fertig in OUTREACH.md §2
- [x] **Reddit r/ExperiencedDevs Text** — Fertig in OUTREACH.md §5 (diskursiver Ton)
- [x] **dev.to / Hashnode Artikel** — Fertig in OUTREACH.md §7 (mit Benchmark-Daten)
- [x] **Twitter/X Thread** — Fertig in OUTREACH.md §6 (5 Tweets mit Benchmark-Zahlen)
- [x] **Discord-Post** — Fertig in OUTREACH.md §8

---

## Phase 3 — Launch-Tag

Optimaler Zeitpunkt: Dienstag oder Mittwoch, 15–17 Uhr CET (9–11 Uhr US Eastern).

- [ ] Show HN abschicken → https://news.ycombinator.com/submitlink?u=https://github.com/sauremilk/drift
- [ ] Reddit-Posts gleichzeitig: r/Python, r/programming, r/softwarearchitecture, r/ExperiencedDevs
- [ ] Twitter/X Thread veröffentlichen
- [ ] Discord: Python Discord (#showcase), The Programmer's Hangout, AI Engineer Discord

---

## Phase 4 — Sustain (Woche 2–4)

- [ ] **PR an awesome-static-analysis** — Text in OUTREACH.md §3
- [ ] **PR an awesome-python** — Text in OUTREACH.md §4
- [ ] **PyPI-Downloads tracken** — https://pypistats.org/packages/drift-analyzer
- [ ] **First-Issue Labels setzen** — Konkrete Kandidaten für `good first issue`:
  1. EDS: `__init__`-Methoden aus False-Positive-Berechnung ausschließen (`signals/explainability_deficit.py`)
  2. CSV-Output-Formatter hinzufügen (Pattern aus `output/json_output.py` folgen)
  3. Edge-Case-Tests für leere Repos / Single-File-Projekte (`tests/`)
  4. Monorepo-Konfigurationsbeispiele dokumentieren (`docs-site/getting-started/`)
  5. PFS Decorator-Varianten Normalisierung verbessern (`signals/pattern_fragmentation.py`)
- [ ] **Gezielt in relevanten Diskussionen kommentieren** (nur wo drift direkt hilft, kein Spam)
