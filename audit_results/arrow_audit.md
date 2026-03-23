# Drift Precision Audit: arrow

- **Score:** 0.339 (low)
- **Files:** 10 | Functions: 175
- **Findings:** 20 total, 8 reviewable (MEDIUM+)
- **Duration:** 1.75s
- **Analyzed:** 2026-03-23T13:23:30.192022+00:00

## Review Instructions

For each finding, mark the **Verdict** column:
- **TP** — Real problem. You'd want this flagged in a code review.
- **FP** — Not a real problem. This would erode trust if shown to a dev.
- **?** — Unsure / context-dependent.

## Findings

| # | Signal | Sev | Score | File | Title | Verdict |
|---|--------|-----|-------|------|-------|---------|
| 1 | pattern_fragmentation | high | 0.889 | arrow | error_handling: 9 variants in arrow/ | |
| 2 | mutant_duplicate | high | 0.9 | arrow\locales.py | Exact duplicates (2×): CroatianLocale._format_timeframe, Ser | |
| 3 | mutant_duplicate | high | 0.85 | arrow\locales.py | Near-duplicate (100%): CzechLocale._format_timeframe ↔ Slova | |
| 4 | explainability_deficit | high | 0.75 | arrow\formatter.py | Unexplained complexity: DateTimeFormatter._format_token | |
| 5 | explainability_deficit | medium | 0.5 | arrow\arrow.py | Unexplained complexity: Arrow.humanize | |
| 6 | explainability_deficit | medium | 0.5 | arrow\factory.py | Unexplained complexity: ArrowFactory.get | |
| 7 | explainability_deficit | medium | 0.5 | arrow\parser.py | Unexplained complexity: DateTimeParser.parse_iso | |
| 8 | explainability_deficit | medium | 0.5 | arrow\parser.py | Unexplained complexity: DateTimeParser._parse_token | |

## Detailed Findings

### #1: error_handling: 9 variants in arrow/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.889 | **Impact:** 0.568
**File:** arrow

> 9 error_handling variants in arrow/ (2/10 use canonical pattern).
  - arrow.py:783 (Arrow.interval)
  - arrow.py:786 (Arrow.interval)
  - arrow.py:1831 (Arrow._get_tzinfo)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 8 Abweichung(en) in: arrow.py, parser.py, util.py und 3 weitere.

**Related:** arrow\arrow.py, arrow\arrow.py, arrow\arrow.py, arrow\parser.py, arrow\parser.py

**Verdict:** TP / FP / ?
**Note:**

---

### #2: Exact duplicates (2×): CroatianLocale._format_timeframe, SerbianLocale._format_timeframe
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.9 | **Impact:** 0.229
**File:** arrow\locales.py (line 4969)

> 2 identical copies (10 lines each) at: arrow\locales.py:4969, arrow\locales.py:5560. Consider consolidating.

**Fix:** Extrahiere CroatianLocale._format_timeframe() in arrow/shared.py. 2 identische Kopien (Similarity: 1.00). Aufwand: S.

**Related:** arrow\locales.py

**Verdict:** TP / FP / ?
**Note:**

---

### #3: Near-duplicate (100%): CzechLocale._format_timeframe ↔ SlovakLocale._format_timeframe
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.85 | **Impact:** 0.216
**File:** arrow\locales.py (line 3296)

> arrow\locales.py:3296 and arrow\locales.py:3427 are 100% similar. Small differences may indicate copy-paste divergence.

**Fix:** Extrahiere CzechLocale._format_timeframe() in arrow/shared.py. Similarity: 100%. Aufwand: S.

**Related:** arrow\locales.py

**Verdict:** TP / FP / ?
**Note:**

---

### #4: Unexplained complexity: DateTimeFormatter._format_token
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** arrow\formatter.py (line 43)

> Complexity: 38, LOC: 98. No docstring. No corresponding test found.

**Fix:** Funktion DateTimeFormatter._format_token (Complexity 38): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #5: Unexplained complexity: Arrow.humanize
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** arrow\arrow.py (line 1133)

> Complexity: 43, LOC: 212. No corresponding test found.

**Fix:** Funktion Arrow.humanize (Complexity 43): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #6: Unexplained complexity: ArrowFactory.get
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** arrow\factory.py (line 85)

> Complexity: 28, LOC: 213. No corresponding test found.

**Fix:** Funktion ArrowFactory.get (Complexity 28): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #7: Unexplained complexity: DateTimeParser.parse_iso
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** arrow\parser.py (line 252)

> Complexity: 21, LOC: 120. No corresponding test found.

**Fix:** Funktion DateTimeParser.parse_iso (Complexity 21): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #8: Unexplained complexity: DateTimeParser._parse_token
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** arrow\parser.py (line 591)

> Complexity: 27, LOC: 103. No corresponding test found.

**Fix:** Funktion DateTimeParser._parse_token (Complexity 27): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---
