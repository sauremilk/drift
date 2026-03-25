# LLM Visibility Tracking Template

> Wöchentliches Tracking der LLM-Sichtbarkeit und Web-Metriken.
> Kopiere den Abschnitt "KW [X]" jede Woche und fülle ihn aus.

---

## Baseline (vor Quick Wins)

- **Datum:** ____-__-__
- **Baseline-Erwähnungsrate:** __/30 (Summe über alle 3 LLMs)
- **PyPI Downloads (30d):** [MISSING DATA]
- **GitHub Stars:** [MISSING DATA]
- **GitHub Traffic (Views/Unique, 14d):** [MISSING DATA]

---

## KW [__] — ____-__-__

### LLM-Tests

| Prompt | ChatGPT | Perplexity | Claude | Notiz |
|--------|---------|------------|--------|-------|
| P1: Statische Analyse-Tools für Python | Y/N/Pos | Y/N/Pos | Y/N/Pos | |
| P2: Bester architectural linter Python | Y/N/Pos | Y/N/Pos | Y/N/Pos | |
| P3: Technische Schulden erkennen | Y/N/Pos | Y/N/Pos | Y/N/Pos | |
| P4: Alternativen zu pylint | Y/N/Pos | Y/N/Pos | Y/N/Pos | |
| P5: Abhängigkeiten in Monorepos | Y/N/Pos | Y/N/Pos | Y/N/Pos | |
| P6: Was ist drift-analyzer? | Y/N/Pos | Y/N/Pos | Y/N/Pos | |
| P7: Python-Linter + GitHub Actions | Y/N/Pos | Y/N/Pos | Y/N/Pos | |
| P8: Dependency Cycles in Python | Y/N/Pos | Y/N/Pos | Y/N/Pos | |
| P9: Architektonische Erosion erkennen | Y/N/Pos | Y/N/Pos | Y/N/Pos | |
| P10: Code-Quality große Codebasen | Y/N/Pos | Y/N/Pos | Y/N/Pos | |

**Format:** Y = erwähnt, N = nicht erwähnt, Pos = Position in Liste (1–10 / –)

### Web-Metriken

- PyPI Downloads (30d): ____
- GitHub Stars: ____
- GitHub Traffic Views / Unique (14d): ____ / ____
- Neue externe Mentions: [Links]

### Delta zur Baseline

- Erwähnungsrate: ___% (Baseline: __%)
- Trend: ↑ / ↔ / ↓
- Notizen:

---

## Kopiervorlage

```markdown
## KW [__] — ____-__-__

### LLM-Tests

| Prompt | ChatGPT | Perplexity | Claude | Notiz |
|--------|---------|------------|--------|-------|
| P1 | | | | |
| P2 | | | | |
| P3 | | | | |
| P4 | | | | |
| P5 | | | | |
| P6 | | | | |
| P7 | | | | |
| P8 | | | | |
| P9 | | | | |
| P10 | | | | |

### Web-Metriken

- PyPI Downloads (30d):
- GitHub Stars:
- GitHub Traffic Views / Unique (14d):
- Neue externe Mentions:

### Delta zur Baseline

- Erwähnungsrate: ___% (Baseline: __%)
- Trend: ↑ / ↔ / ↓
- Notizen:
```

---

## Erfolgskriterien (nach 30 Tagen)

- [ ] drift in min. 6 von 10 Prompts erwähnt (bei min. 2 LLMs)
- [ ] PyPI Downloads: Baseline + 20%
- [ ] GitHub Stars: Baseline + 10
- [ ] Min. 1 awesome-* PR geöffnet
- [ ] llms.txt vollständig und llmstxt.org-konform
- [ ] Tracking-Template wöchentlich befüllt
