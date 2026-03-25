# Phase 2 — Manuelle Schritte (Mick)

> Diese Schritte können nicht automatisiert werden und müssen manuell ausgeführt werden.

---

## GitHub Topics setzen

**URL:** https://github.com/sauremilk/drift → About (Zahnrad-Icon) → Edit

**Topics eintragen:**

```
static-analysis, architectural-linter, technical-debt, dependency-analysis,
python, code-quality, monorepo, linter, github-actions, pre-commit,
dependency-cycles, import-analysis, architecture-enforcement
```

- [ ] Topics unter Repository → About → Edit gesetzt
- [ ] Sichtbar unter https://github.com/sauremilk/drift (rechte Sidebar)

---

## Baseline-Vorlage ausfüllen

**Datei:** `master-backlog/01-baseline.md`

- [ ] ChatGPT-4o: 10 Prompts in frischem Chat testen, Tabelle ausfüllen
- [ ] Perplexity: 10 Prompts in frischem Chat testen, Tabelle ausfüllen
- [ ] Claude: 10 Prompts in frischem Chat testen, Tabelle ausfüllen
- [ ] Erwähnungsraten berechnen und eintragen
- [ ] Datum dokumentieren

**Zeitpunkt:** Vor der nächsten Änderungsrunde (= Baseline vor Quick Wins).

---

## Nach 30 Tagen erneut testen

- [ ] 01-baseline.md erneut mit denselben 10 Prompts testen
- [ ] Delta zur Baseline in `master-backlog/03-llm-tracking-template.md` eintragen
- [ ] KPI prüfen: drift in min. 6/10 Prompts bei min. 2 LLMs erwähnt?
