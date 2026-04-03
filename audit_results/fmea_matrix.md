# FMEA Matrix

## 2026-04-03 - PFS/NBV copilot-context actionability (Issue #125)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| PFS | Finding text too vague to execute | Fix text omitted canonical exemplar and line-level deviation anchors | Agents must open multiple files to infer next step, reducing trust and speed | Issue report + regression test assertions | Include canonical exemplar `file:line` and explicit deviation refs in fix text | 5 | 6 | 3 | 90 |
| NBV | Contract violation guidance not specific enough | Generic fix text ignored matched naming rule semantics | Incorrect or delayed implementation choices (rename vs behavior change) | Issue report + regression test assertions | Prefix-specific suggestions plus location anchor `file:line` in fix text | 5 | 5 | 3 | 75 |

## 2026-07-18 - Security audit: is_test_file guard for PFS/AVS/MDS

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| PFS | FP: Test file pattern variants reported as fragmentation | No is_test_file() guard; test helpers use intentionally varied patterns | Inflated fragmentation scores, noise in fix_first | Regression tests + default exclude covers most cases | Added is_test_file() skip in pattern collection loop | 3 | 3 | 3 | 27 |
| AVS | FP: Test imports flagged as layer violations | Tests legitimately import across all layers | False architecture violation findings | Regression tests + default exclude covers most cases | Added is_test_file() filter before import graph construction | 4 | 3 | 3 | 36 |
| MDS | FP: Test helper duplicates flagged as mutant clones | Test files often contain intentional near-duplicates | Noise in duplicate detection results | Regression tests + default exclude covers most cases | Added is_test_file() skip in function collection loop | 3 | 3 | 3 | 27 |

## 2026-07-18 - Security audit: negative_context metadata injection

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| AVS/NBV | Output injection: Crafted metadata values could inject fake code blocks in negative context output | Unsanitized metadata strings embedded in f-string code templates | Agent could execute injected instructions from negative context | Manual code review | Added _sanitize() helper stripping control chars/newlines from metadata before f-string embedding | 5 | 2 | 4 | 40 |

## 2026-04-03 - DIA Markdown slash-token false positives (Issue #121)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| DIA | FP: Generic prose tokens (e.g. async/, scan/, connectors/) reported as missing directories | Slash-token extraction without structural context in markdown prose | Trust erosion, noisy findings, reduced actionability | User report + regression test in tests/test_dia_enhanced.py | Context-aware extraction: accept only backticked refs or nearby structural keywords; keep code-span refs | 5 | 6 | 4 | 120 |
| DIA | FN: Real directory mention in plain prose filtered too aggressively | Context window misses valid wording | Missed drift signal | DIA regression tests for context-positive phrases | Structural keyword list + explicit backtick acceptance | 4 | 3 | 5 | 60 |
