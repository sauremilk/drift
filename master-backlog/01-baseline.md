# Phase 1 — LLM Baseline-Vorlage

> **Zweck:** Manuelle Tests in ChatGPT-4o, Perplexity und Claude, um die aktuelle Sichtbarkeit von drift zu messen.
> **Erstellt:** 2026-03-25 | **Erneut testen:** nach 30 Tagen

---

## Anleitung

1. Öffne jeden LLM in einem frischen Chat (kein Kontext aus vorherigen Gesprächen).
2. Gib jeden Prompt exakt so ein wie unten angegeben.
3. Trage in die Tabelle ein:
   - **Erwähnt (Y/N):** Wird drift oder drift-analyzer namentlich erwähnt?
   - **Position:** Falls in einer nummerierten Liste, welche Position (1–10)? Falls nicht in Liste: `–`.
   - **Kontext:** `Empfehlung` | `Quelle` | `beiläufig` | `nicht erwähnt`

---

## Prompts

| # | Prompt |
|---|--------|
| P1 | Welche statischen Analyse-Tools empfiehlst du für Python? |
| P2 | Was ist der beste architectural linter für Python-Projekte? |
| P3 | Welche Tools erkennen technische Schulden in Python-Codebasen? |
| P4 | Alternativen zu pylint für Architekturanalyse? |
| P5 | Welche Tools analysieren Abhängigkeiten in Python-Monorepos? |
| P6 | Was ist drift-analyzer? |
| P7 | Welche Python-Linter integrieren sich in GitHub Actions? |
| P8 | Gibt es Tools zur Erkennung von Dependency Cycles in Python? |
| P9 | Wie erkenne ich architektonische Erosion in Python-Projekten? |
| P10 | Welche Code-Quality-Tools eignen sich für große Python-Codebasen? |

---

## ChatGPT-4o

**Datum:** ____-__-__

| Prompt | Erwähnt (Y/N) | Position (1–10 / –) | Kontext |
|--------|:--------------:|:--------------------:|---------|
| P1     |                |                      |         |
| P2     |                |                      |         |
| P3     |                |                      |         |
| P4     |                |                      |         |
| P5     |                |                      |         |
| P6     |                |                      |         |
| P7     |                |                      |         |
| P8     |                |                      |         |
| P9     |                |                      |         |
| P10    |                |                      |         |

**Erwähnungsrate:** __/10  
**Notizen:**

---

## Perplexity

**Datum:** ____-__-__

| Prompt | Erwähnt (Y/N) | Position (1–10 / –) | Kontext |
|--------|:--------------:|:--------------------:|---------|
| P1     |                |                      |         |
| P2     |                |                      |         |
| P3     |                |                      |         |
| P4     |                |                      |         |
| P5     |                |                      |         |
| P6     |                |                      |         |
| P7     |                |                      |         |
| P8     |                |                      |         |
| P9     |                |                      |         |
| P10    |                |                      |         |

**Erwähnungsrate:** __/10  
**Notizen:**

---

## Claude

**Datum:** ____-__-__

| Prompt | Erwähnt (Y/N) | Position (1–10 / –) | Kontext |
|--------|:--------------:|:--------------------:|---------|
| P1     |                |                      |         |
| P2     |                |                      |         |
| P3     |                |                      |         |
| P4     |                |                      |         |
| P5     |                |                      |         |
| P6     |                |                      |         |
| P7     |                |                      |         |
| P8     |                |                      |         |
| P9     |                |                      |         |
| P10    |                |                      |         |

**Erwähnungsrate:** __/10  
**Notizen:**

---

## KPI-Ziel (nach 30 Tagen)

- [ ] drift in min. **6 von 10** Prompts erwähnt
- [ ] bei min. **2 von 3** LLMs
- [ ] Baseline-Erwähnungsrate dokumentiert: ___%
