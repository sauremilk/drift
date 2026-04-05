# FMEA Matrix

## 2026-04-05 - MAZ, AVS, EDS signal quality batch (Issues #148, #149, #150, #151)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MAZ | FP: intentionally public endpoints flagged as missing auth | Allowlist too narrow — common public patterns (anon, pricing, security_txt) not covered; dev-tool paths not excluded | ~20% precision, triage noise, trust erosion | Quality audit benchmark + new regression tests | Expanded allowlist (+25 patterns) + dev-tool path heuristic (7 defaults) | 6 | 6 | 3 | 108 |
| MAZ | FN: real auth gap missed due to expanded allowlist | Over-broad substring matching could suppress genuine missing-auth endpoints | Delayed remediation for true auth gaps | Regression test: non-dev-path still flagged | Conservative substring matching, keep finding emitted, metadata for auditability | 7 | 2 | 5 | 70 |
| EDS | FP-severity: trivial getters rated HIGH same as complex algorithms | No LOC or visibility weighting — severity derived from raw complexity ratio only | LOW-complexity findings clutter HIGH-priority triage | Field comparison across benchmark repos | LOC-based dampening (loc/30) + private-function visibility dampening (0.7×) | 5 | 5 | 3 | 75 |
| EDS | FN-severity: meaningful private complex function under-ranked | Private visibility factor always 0.7× even for high-complexity functions | Delayed remediation for complex private code | Test: complexity-20 private function still emitted as HIGH | Visibility dampening is mild (0.7×), only reduces not suppresses | 5 | 2 | 5 | 50 |
| AVS | Attribution: all sub-checks conflated under "AVS" abbreviation | No rule_id on 8 AVS sub-checks (boundary, upward-import, circular-dep, etc.) | Impossible to filter or distinguish sub-signals in scan output | Quality audit issue #150 | Added explicit rule_id per sub-check, exposed in concise output | 4 | 7 | 2 | 56 |
| All | Location gap: findings with null start_line | Signals emit findings without start_line when AST node unavailable | Agent fix workflows cannot navigate to finding location | Automated field check across all 9 signal files | Finding.__post_init__ fallback: start_line=1 when file_path is set | 4 | 5 | 2 | 40 |

## 2026-04-05 - HSC OAuth endpoint URL false positives (Issue #161)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| HSC | FP: OAuth endpoint constants are flagged as hardcoded secrets | Variable-name heuristic matches `TOKEN_URL`/`AUTH_URL`; endpoint URLs are treated like credential literals | High-severity triage noise and reduced trust in HSC findings | Field test on onyx-dot-app/onyx + targeted HSC regressions | Suppress plain HTTP(S) endpoint URLs without embedded credentials (userinfo) | 6 | 5 | 4 | 120 |
| HSC | FN: Credential-bearing URL literal could be under-reported after suppression | Over-broad URL suppression in secret-sensitive variables | Real secret material in URL userinfo may be missed | Regression test with `https://user:secret@...` | Keep detection active when URL contains username/password and retain known-prefix checks | 7 | 2 | 5 | 70 |

## 2026-04-05 - MAZ documented public-safe endpoint severity calibration (Issue #162)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MAZ | FP-severity: intentionally public publishable-key endpoint is emitted as HIGH | MAZ considered only missing auth marker and endpoint naming allowlist, but not explicit documented public-safe intent | High-priority triage noise, reduced trust in MAZ findings | Field report on onyx-dot-app/onyx + targeted regression test | Downgrade to LOW when endpoint name indicates publishable/public key semantics and function is explicitly documented (docstring present) | 6 | 5 | 4 | 120 |
| MAZ | FN risk: real sensitive endpoint under-ranked due heuristic dampening | Over-broad public-safe matching could hide materially risky unauthenticated endpoints | Delayed remediation for true auth gaps | Regression test for same endpoint name without docstring (remains HIGH) | Keep finding emitted (no suppression), require docstring + conservative marker set, attach metadata for auditability | 7 | 2 | 6 | 84 |

## 2026-04-05 - AVS tiny foundational module severity calibration (Issue #153)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| AVS (Zone of Pain) | FP-severity: tiny foundational modules are emitted as HIGH without sufficient evidence | Severity derived mainly from distance metric; tiny module structure and coupling evidence not considered | Triage noise, low-actionability work prioritized too high, trust erosion | Field test on fastapi/fastapi + targeted regressions | Tiny-foundational dampening and explicit high-risk evidence gate for HIGH severity | 6 | 6 | 4 | 144 |
| AVS (Zone of Pain) | FN-severity: meaningful tiny modules may be under-ranked after dampening | Over-conservative tiny-module dampening thresholds | Real high-impact foundation risks may be delayed in remediation order | Regression test for tiny module with strong coupling evidence (HIGH retained) | High-risk evidence override (`ca >= 6` or `ca >= 4 and ce >= 2`) plus metadata for observability | 5 | 3 | 5 | 75 |

## 2026-04-05 - DCA framework/library public API suppression (Issue #152)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| DCA | FP: Public framework/library exports are flagged as unused dead code | Internal-import-only heuristic cannot observe external consumers of package APIs | Trust erosion, noisy findings, misprioritized cleanup work | Field report on fastapi/fastapi + regression test on package-layout API modules | Suppress dead-export findings for package-layout public API modules in framework/library profile | 6 | 6 | 4 | 144 |
| DCA | FN: Internal dead exports may be missed after public API suppression | Over-broad package-level suppression can hide true dead symbols | Reduced dead-code recall in library repositories | Added regression test for internal path token handling | Restrict suppression to package public API paths and keep internal/private path tokens reportable | 5 | 3 | 5 | 75 |

## 2026-04-04 - MCP stdio deadlock hardening on Windows

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| ECD and git-backed analysis paths | MCP call hangs while invoking git subprocesses | `subprocess.run` inherits MCP stdin handle when `stdin` is not explicitly set | Stalled tool call, no actionable result returned | Regression test scans all `subprocess.run` calls in `src/drift` for `stdin`/`input` | Enforce `stdin=subprocess.DEVNULL` for affected subprocess calls | 8 | 3 | 3 | 72 |
| MCP tool execution pipeline | Deadlock during first threaded import of heavy C-extension modules | Lazy first import happens inside worker thread after event loop starts | Session teardown risk and non-deterministic hangs on Windows | Regression test asserts `_eager_imports()` is called before `mcp.run()` | Eager-import heavy modules before event loop startup | 8 | 2 | 4 | 64 |

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
