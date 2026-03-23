# Drift Precision Audit: cli

- **Score:** 0.474 (medium)
- **Files:** 86 | Functions: 502
- **Findings:** 38 total, 12 reviewable (MEDIUM+)
- **Duration:** 0.98s
- **Analyzed:** 2026-03-23T13:23:27.383421+00:00

## Review Instructions

For each finding, mark the **Verdict** column:
- **TP** — Real problem. You'd want this flagged in a code review.
- **FP** — Not a real problem. This would erode trust if shown to a dev.
- **?** — Unsure / context-dependent.

## Findings

| # | Signal | Sev | Score | File | Title | Verdict |
|---|--------|-----|-------|------|-------|---------|
| 1 | pattern_fragmentation | high | 0.933 | httpie | error_handling: 15 variants in httpie/ | |
| 2 | pattern_fragmentation | high | 0.917 | httpie\cli | error_handling: 12 variants in httpie/cli/ | |
| 3 | pattern_fragmentation | high | 0.8 | httpie\output | error_handling: 5 variants in httpie/output/ | |
| 4 | pattern_fragmentation | high | 0.75 | httpie\output\formatters | error_handling: 4 variants in httpie/output/formatters/ | |
| 5 | pattern_fragmentation | high | 0.75 | httpie\manager | error_handling: 4 variants in httpie/manager/ | |
| 6 | pattern_fragmentation | high | 0.75 | httpie\manager\tasks | error_handling: 4 variants in httpie/manager/tasks/ | |
| 7 | pattern_fragmentation | medium | 0.667 | httpie\output\ui | error_handling: 3 variants in httpie/output/ui/ | |
| 8 | explainability_deficit | high | 1.0 | httpie\cli\argparser.py | Unexplained complexity: HTTPieArgumentParser._process_auth | |
| 9 | explainability_deficit | high | 0.75 | httpie\client.py | Unexplained complexity: collect_messages | |
| 10 | explainability_deficit | high | 0.75 | httpie\core.py | Unexplained complexity: raw_main | |
| 11 | explainability_deficit | medium | 0.6 | httpie\cli\nested_json\interpret.py | Unexplained complexity: interpret | |
| 12 | explainability_deficit | medium | 0.5 | httpie\core.py | Unexplained complexity: program | |

## Detailed Findings

### #1: error_handling: 15 variants in httpie/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.933 | **Impact:** 0.692
**File:** httpie

> 15 error_handling variants in httpie/ (4/18 use canonical pattern).
  - __main__.py:7 (main)
  - compat.py:96 (get_dist_name)
  - config.py:66 (read_raw_config)

**Fix:** Konsolidiere auf das dominante Pattern (4×). 14 Abweichung(en) in: __main__.py, compat.py, config.py, context.py, core.py und 9 weitere.

**Related:** httpie\__main__.py, httpie\compat.py, httpie\config.py, httpie\config.py, httpie\context.py

**Verdict:** TP / FP / ?
**Note:**

---

### #2: error_handling: 12 variants in httpie/cli/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.917 | **Impact:** 0.654
**File:** httpie\cli

> 12 error_handling variants in httpie/cli/ (2/14 use canonical pattern).
  - argparser.py:130 (HTTPieManagerArgumentParser.parse_known_args)
  - argparser.py:251 (HTTPieArgumentParser._setup_standard_streams)
  - argparser.py:426 (HTTPieArgumentParser._guess_method)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 12 Abweichung(en) in: argparser.py, argtypes.py, requestitems.py und 7 weitere.

**Related:** httpie\cli\argparser.py, httpie\cli\argparser.py, httpie\cli\argparser.py, httpie\cli\argparser.py, httpie\cli\argtypes.py

**Verdict:** TP / FP / ?
**Note:**

---

### #3: error_handling: 5 variants in httpie/output/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.8 | **Impact:** 0.417
**File:** httpie\output

> 5 error_handling variants in httpie/output/ (1/5 use canonical pattern).
  - utils.py:21 (load_prefixed_json)
  - utils.py:14 (load_prefixed_json)
  - writer.py:48 (write_message)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 4 Abweichung(en) in: utils.py, writer.py.

**Related:** httpie\output\utils.py, httpie\output\utils.py, httpie\output\writer.py, httpie\output\writer.py

**Verdict:** TP / FP / ?
**Note:**

---

### #4: error_handling: 4 variants in httpie/output/formatters/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.75 | **Impact:** 0.391
**File:** httpie\output\formatters

> 4 error_handling variants in httpie/output/formatters/ (2/6 use canonical pattern).
  - colors.py:136 (ColorFormatter.get_style_class)
  - colors.py:175 (get_lexer)
  - colors.py:168 (get_lexer)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 4 Abweichung(en) in: colors.py, xml.py.

**Related:** httpie\output\formatters\colors.py, httpie\output\formatters\colors.py, httpie\output\formatters\colors.py, httpie\output\formatters\xml.py

**Verdict:** TP / FP / ?
**Note:**

---

### #5: error_handling: 4 variants in httpie/manager/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.75 | **Impact:** 0.358
**File:** httpie\manager

> 4 error_handling variants in httpie/manager/ (1/4 use canonical pattern).
  - __main__.py:35 (main)
  - __main__.py:52 (program)
  - compat.py:48 (_run_pip_subprocess)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 3 Abweichung(en) in: __main__.py, compat.py.

**Related:** httpie\manager\__main__.py, httpie\manager\__main__.py, httpie\manager\compat.py

**Verdict:** TP / FP / ?
**Note:**

---

### #6: error_handling: 4 variants in httpie/manager/tasks/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.75 | **Impact:** 0.358
**File:** httpie\manager\tasks

> 4 error_handling variants in httpie/manager/tasks/ (1/4 use canonical pattern).
  - plugins.py:73 (PluginInstaller._install)
  - plugins.py:149 (PluginInstaller._uninstall)
  - plugins.py:243 (cli_plugins)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 3 Abweichung(en) in: plugins.py.

**Related:** httpie\manager\tasks\plugins.py, httpie\manager\tasks\plugins.py, httpie\manager\tasks\plugins.py

**Verdict:** TP / FP / ?
**Note:**

---

### #7: error_handling: 3 variants in httpie/output/ui/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** httpie\output\ui

> 3 error_handling variants in httpie/output/ui/ (1/3 use canonical pattern).
  - rich_palette.py:49 (_make_rich_color_theme)
  - rich_utils.py:30 (enable_highlighter)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 2 Abweichung(en) in: rich_palette.py, rich_utils.py.

**Related:** httpie\output\ui\rich_palette.py, httpie\output\ui\rich_utils.py

**Verdict:** TP / FP / ?
**Note:**

---

### #8: Unexplained complexity: HTTPieArgumentParser._process_auth
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** httpie\cli\argparser.py (line 282)

> Complexity: 24, LOC: 74. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion HTTPieArgumentParser._process_auth (Complexity 24): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #9: Unexplained complexity: collect_messages
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** httpie\client.py (line 43)

> Complexity: 21, LOC: 98. No docstring. No corresponding test found.

**Fix:** Funktion collect_messages (Complexity 21): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #10: Unexplained complexity: raw_main
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** httpie\core.py (line 32)

> Complexity: 30, LOC: 112. No docstring. No corresponding test found.

**Fix:** Funktion raw_main (Complexity 30): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #11: Unexplained complexity: interpret
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** httpie\cli\nested_json\interpret.py (line 30)

> Complexity: 16, LOC: 75. No docstring. No corresponding test found.

**Fix:** Funktion interpret (Complexity 16): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #12: Unexplained complexity: program
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** httpie\core.py (line 170)

> Complexity: 27, LOC: 98. No corresponding test found.

**Fix:** Funktion program (Complexity 27): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---
