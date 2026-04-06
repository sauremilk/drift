# FMEA Matrix

## 2026-04-06 - HSC YAML env-template variable-name false positives (Issue #181)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| HSC | FP: multi-line YAML templates with `${ENV_VAR}` placeholders are flagged as hardcoded secrets | Secret-shaped variable names (`*_API_KEY`, `*_TOKEN`) trigger generic fallback although string literal is a configuration template referencing env injection | High-severity triage noise and reduced trust in HSC precision for framework/sample repos | Field report on microsoft/agent-framework + targeted HSC regressions | Suppress configuration-style multi-line literals containing env placeholders (`${...}`) before generic fallback detection while preserving known-prefix checks first | 6 | 5 | 4 | 120 |
| HSC | FN: credentials embedded in template-like literals could be under-reported | New suppression path could hide mixed literals that include both template markers and real credentials | Delayed remediation in rare misuse cases | Regression ensures known-prefix secrets are still emitted before suppression | Keep suppression narrow (multi-line + `${...}` + key/value template markers), preserve known-prefix detection ordering, monitor precision/recall deltas | 5 | 2 | 6 | 60 |

## 2026-04-06 - TPD ast.get_source_segment crash guard (Issue #180)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| TPD | FN: signal execution aborts with uncaught exception | `ast.get_source_segment` raises `IndexError`/`ValueError` when AST node position metadata references out-of-range lines | TPD findings are entirely absent for affected repositories | Deterministic field crash report + targeted regression on malformed assert node metadata | Wrap source-segment extraction in exception-safe fallback (`segment=None`) and continue counting | 8 | 4 | 4 | 128 |
| TPD | FN/precision drift risk on malformed nodes | Regex-based negative-assert fallback cannot run when source segment extraction fails | Individual assert polarity may rely only on AST heuristic in edge metadata cases | New regression validates graceful continuation without crash | Keep conservative AST polarity rules active and bypass only regex fallback for malformed nodes | 4 | 3 | 5 | 60 |

## 2026-04-06 - MDS numbered sample-step duplicate calibration (Issue #179)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MDS | FP: numbered sample step directories are flagged as high-severity exact duplicates | Tutorial-step suppression required `step*` token and missed numbered step dirs such as `01_single_agent`/`02_multi_agent` | High-severity noise on pedagogical repos using numbered sample progression and reduced trust in MDS precision | Field test on microsoft/agent-framework + targeted MDS regressions for numbered sample dirs | Extend tutorial-step suppression to also match conservative numbered sample-step directory pattern (`^\d{1,3}[-_].+`) under tutorial/sample/example context | 6 | 5 | 4 | 120 |
| MDS | FN: harmful duplicates in numbered tutorial steps can be under-reported | Numbered-step suppression now excludes more educational sample directories from duplicate analysis | Rare actionable refactoring opportunities in tutorial samples may be missed | Regression keeps non-step sample duplicates detectable | Keep suppression gated by tutorial/sample/example path marker plus conservative numbered-step folder shape | 4 | 3 | 6 | 72 |

## 2026-04-06 - MDS tutorial-step sample duplicate calibration (Issue #177)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MDS | FP: tutorial step samples are flagged as high-severity exact duplicates | Candidate collection treats intentional standalone tutorial-step helper copies as architectural drift | High-severity noise on pedagogical repositories and reduced trust in MDS precision | Field test on microsoft/agent-framework + targeted MDS regressions | Suppress MDS candidates in conservative tutorial-step sample path context (`tutorial/sample/example` + `step*`) | 6 | 6 | 4 | 144 |
| MDS | FN: harmful duplication in tutorial-step contexts can be under-reported | New path heuristic skips duplicate analysis for functions in tutorial step sample trees | Rare true refactoring opportunities in tutorial steps may not be surfaced | Regression keeps non-step sample duplicates detectable | Keep heuristic narrow to explicit step-marker directories and tutorial/sample/example path context | 4 | 3 | 6 | 72 |

## 2026-04-06 - DCA script-context false positives (Issue #176)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| DCA | FP: executable Python scripts are flagged for unused exports | DCA infers usage primarily from cross-file imports and treats script helpers as library exports | CI/utility scripts get noisy dead-code recommendations and DCA trust drops | Field test on microsoft/agent-framework + targeted DCA regression | Suppress export-based DCA evaluation for Python files in script-like path contexts (`.github/workflows`, `scripts`, `tools`, `bin`) | 6 | 5 | 4 | 120 |
| DCA | FN: true dead exports in script-like paths can be under-reported | Path-based script-context suppression bypasses report generation for those files | Some actionable cleanup candidates in script directories may be missed | Regression keeps non-script contexts unchanged | Keep suppression conservative and path-scoped to executable-context locations only | 4 | 3 | 6 | 72 |

## 2026-04-05 - HSC OpenTelemetry GenAI semconv false positives (Issue #175)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| HSC | FP: OpenTelemetry GenAI metric/attribute constants are flagged as hardcoded secrets | Variable-name heuristic matches `token` in telemetry symbols (`INPUT_TOKENS`), while literal values are semantic-convention keys (for example `gen_ai.usage.input_tokens`) | High-severity triage noise in observability modules and reduced confidence in HSC precision | Field test on microsoft/agent-framework + targeted HSC regressions | Suppress OpenTelemetry GenAI semantic-convention literals (`gen_ai.*`) before generic fallback detection while keeping known-prefix secret checks first | 6 | 6 | 4 | 144 |
| HSC | FN: real credentials could be under-reported if they resemble semconv literals | New semconv suppression could hide unusual dotted lowercase literals under secret-shaped variables | Rare credential leakage may be delayed | Regression verifies known-prefix secrets remain detectable before suppression | Keep suppression narrow to `gen_ai.<segment>.<segment...>` pattern, preserve high-confidence prefix detection ordering, monitor field deltas | 5 | 2 | 6 | 60 |

## 2026-04-05 - AVS/ECM/TPD Recall-Härtung auf Groß-Repositories (Issue #170)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| AVS | FN: interne Abhängigkeitskanten aus relativen Imports fehlen | Relative `ImportFrom`-Information war für Graph-Auflösung unterbestimmt; unverknüpfte Kanten wurden als extern behandelt | Upward/Cycle/Blast-Radius-Befunde bleiben aus trotz realer Kopplung | Neuer Regressionstest für relative Import-Kantenauflösung in AVS-Graph | Best-effort relative Kandidatenauflösung aus Quellpfad + Importmodul/Namen ergänzt | 7 | 5 | 4 | 140 |
| ECM | FN: Exception-Drift bleibt unentdeckt in sehr großen Repos | Starre Kandidatenbegrenzung (`ecm_max_files`) fokussiert zu stark auf kleines Hot-File-Subset | Module mit realer Contract-Drift werden nicht verglichen | Neuer Regressionstest für adaptive Limit-Berechnung | Adaptive Kandidatenobergrenze mit konfiguriertem Floor und skaliertem Cap (max 300) ergänzt | 6 | 5 | 4 | 120 |
| TPD | FN: 0 Findings trotz testlastigem Repo | Globale Exclude-Regeln können Testdateien vor Signalphase entfernen | TPD verliert seine gesamte Beobachtungsbasis | Neuer Regressionstest mit leerem ParseResult-Input und Repo-Fallback | Fallback-Testdatei-Discovery direkt aus Repo-Dateisystem ergänzt (nur wenn keine Test-Counter vorhanden) | 6 | 6 | 3 | 108 |

## 2026-04-05 - MAZ decorator fallback recall calibration (Issue #169)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MAZ | FN: route handlers are missed when API endpoint ingestion emits no API_ENDPOINT patterns | MAZ relied exclusively on ingestion patterns and had no conservative fallback for decorator-defined route handlers | Missing-authorization gaps stay unreported in framework files where pattern extraction under-detects endpoints | Field report on transformers + targeted MAZ regression for patternless decorated routes | Add conservative decorator fallback (`route`/HTTP method decorators) only when no API_ENDPOINT pattern exists in file | 7 | 5 | 4 | 140 |
| MAZ | FP: non-endpoint decorated functions could be misclassified as API routes by fallback | Decorator names like `get`/`post` might appear in non-web utility contexts | Additional triage noise and reduced precision in edge repositories | New regression verifies auth-decorated routes are suppressed in fallback path | Keep fallback gated (only when no API patterns), use conservative decorator marker set, skip auth-decorated functions, keep allowlist and dev-path suppressions active | 5 | 3 | 5 | 75 |

## 2026-04-05 - BEM fallback-assignment recall + AVS src-root import resolution (Issue #168)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| BEM | FN: broad `except Exception` fallback assignments are missed | Error-handler fingerprint classified `except ...: flag = False` as generic `other`, while BEM swallowing ratio accepted only pass/log/print | Clear monoculture cases (for example optional dependency probes) are under-reported | Field report on `huggingface/transformers` + targeted parser/BEM regressions | Classify assignment handlers as `fallback_assign` and include in BEM swallowing actions | 7 | 6 | 4 | 168 |
| AVS | FN: internal imports in src-root repos are treated as external/unresolved | Import graph module lookup only matched exact file module path (`src.pkg.mod`) and missed import aliases without source-root prefix (`pkg.mod`) | Upward import and related AVS checks silently miss valid internal edges | Field report on `huggingface/transformers` + targeted AVS regression | Add module alias resolution for common source roots (`src`, `lib`, `python`) when building module-to-file mapping | 7 | 5 | 4 | 140 |

## 2026-04-05 - MAZ localhost CLI serving false positives (Issue #167)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MAZ | FP: localhost CLI serving tool endpoints flagged as missing authorization | MAZ classified API endpoints by route/auth markers only and lacked deployment-context heuristics for local CLI serving modules (`cli/serving/*`) | 0% precision in this context, high-severity triage noise, and reduced trust in MAZ ranking | Field report on `huggingface/transformers` + targeted MAZ regressions for `cli/serving/server.py` | Suppress MAZ findings for CLI-local serving paths (`cli` + `serving/serve` path markers) while keeping standard endpoint checks elsewhere | 7 | 6 | 4 | 168 |
| MAZ | FN: true production auth gaps could be under-reported in CLI-marked serving modules | New path-based suppression may hide real externally exposed endpoints located under `cli/serving/*` | Delayed remediation for rare production deployments that reuse CLI serving path conventions | Regression test ensures serving paths without CLI marker are still flagged | Keep suppression narrow to combined markers (`cli` plus `serving/serve`), preserve non-CLI serving detection, and monitor precision/recall deltas from field reports | 6 | 2 | 6 | 72 |

## 2026-04-05 - HSC ML tokenizer constant false positives (Issue #166)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| HSC | FP: ML tokenizer metadata constants are flagged as hardcoded secrets | Variable-name heuristic matches `token` in NLP tokenizer terms (`pad_token`, `cls_token`, `tokenizer_class_name`, `chat_template`) without domain context | High-severity noise, poor precision on ML repositories, reduced trust in HSC prioritization | Field report on `huggingface/transformers` + targeted HSC regressions | Suppress tokenizer-context literals for known tokenizer symbol names and token markers/templates while preserving high-confidence prefix detection | 7 | 7 | 4 | 196 |
| HSC | FN: real credentials could be under-reported when assigned to tokenizer-shaped symbols | New tokenizer-context suppression can bypass generic fallback detection for misused tokenizer variable names | Rare secret leakage under tokenizer symbol names may be delayed | Regression keeps known-prefix detection active even on tokenizer symbols | Keep suppression narrow (known tokenizer symbols/patterns), run known-prefix checks before suppression, and monitor field precision/recall deltas | 5 | 2 | 6 | 60 |

## 2026-04-05 - NBV try_* attempt-semantics false positives (Issue #165)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| NBV | FP: `try_*` utility/comparison helpers are flagged as missing try/except | Prefix rule treated every `try_*` as exception-handling contract, ignoring common "attempt/check" semantics | Medium-severity noise and lower trust in NBV findings on helper-heavy repos | Field test on langchain (`try_neq_default`) + targeted regressions | Suppress `try_*` findings when function body shows comparison/checking semantics or when file path indicates utility/helper context | 6 | 6 | 4 | 144 |
| NBV | FN: genuine missing try/except in utility paths may be under-reported | New suppression allows utility context and comparison-like helpers to bypass try/except contract | Some real error-handling contract mismatches can receive lower visibility | Existing regressions keep non-utility/non-comparison `try_*` violations detectable | Keep suppression scoped to `try_*` only; preserve other naming contracts and default checks for non-matching contexts | 5 | 3 | 6 | 90 |

## 2026-04-05 - DIA bootstrap-repo README false positives

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| DIA | FP: Tiny bootstrap repositories are flagged with `No README found` | DIA treated missing README as actionable architectural drift even when the repository contains zero or one parsed Python file, or only `__init__.py` skeleton modules | Noise on empty, single-file, and init-only repos; lower trust in baseline scan output | Reproduced on minimal repos + strengthened edge-case regression tests | Suppress missing-README finding for repositories with `len(parse_results) <= 1` or all parsed files named `__init__.py`; keep normal README requirement for larger repos | 4 | 6 | 3 | 72 |
| DIA | FN: Minimal but intentionally documented bootstrap repos receive no README reminder | New bootstrap guard suppresses README guidance for tiny repos and pure package skeletons that may still benefit from documentation | Slightly lower README enforcement on very small repositories | Existing README presence still prevents finding; guard only applies to bootstrap-sized or init-only footprints | Keep threshold narrow (`<= 1` parsed file or all `__init__.py`), emit normal README finding as soon as repository shape exceeds bootstrap size | 2 | 3 | 6 | 36 |

## 2026-04-05 - AVS lazy-import policy violation detection (Issue #146)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| AVS | FN: policy-relevant heavy module-level imports are not surfaced | AVS had boundary and inferred-layer checks, but no dedicated lazy-import policy rule for heavy runtime libraries | Documented architecture policy violations (for example `onnxruntime`/`torch` at module scope) are missed | Field report from Real-Time Fortnite Coach + targeted AVS/parser/config regressions | Add configurable `policies.lazy_import_rules` with module-level enforcement and explicit `avs_lazy_import_policy` findings | 7 | 5 | 4 | 140 |
| AVS | FP: legitimate local lazy imports are flagged as violations | Import analysis lacks scope distinction between module-level and function-local imports | Noisy triage and reduced trust in policy findings | Regression case with local `import torch` in function scope | Extend `ImportInfo` with `is_module_level`, default rule `module_level_only=true`, and test coverage for scope-aware suppression | 5 | 3 | 4 | 60 |

## 2026-04-05 - MDS package-level lazy __getattr__ false positives (Issue #144)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MDS | FP: package `__init__.py` lazy-loading `__getattr__` functions reported as high-severity exact duplicates | Duplicate detector treated intentional PEP 562 package plumbing as copy-paste drift | High-priority triage noise and lower confidence in MDS findings | Field-test issue report + dedicated regression tests | Exclude package-level `__getattr__` in `__init__.py` from MDS candidate set; keep non-package `__getattr__` detection active | 5 | 6 | 4 | 120 |
| MDS | FN: true architectural duplication in package-level `__getattr__` can be under-reported | New suppression heuristic intentionally skips this idiom by default | Rare real duplication problems may be surfaced later by reviewers instead of MDS | Regression guard for non-`__init__.py` `__getattr__` duplicates | Scope suppression strictly to `__init__.py` + `__getattr__` only | 4 | 2 | 6 | 48 |

## 2026-04-05 - TPD negative assertion undercount calibration (Issue #143)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| TPD | FP: happy-path-only finding emitted despite meaningful negative tests | Python `assert` statements were treated as positive by default; negative forms like `assert not ...`, `assert ... is False/None`, and functional `pytest.raises`/`pytest.fail` were undercounted | Inflated TPD score, noisy findings, and reduced trust in polarity diagnostics | Field report on Real-Time Fortnite Coach + new focused regressions | AST-aware assert polarity classification, regex fallback for assert text variants, and explicit negative call handling for raises/fail patterns | 6 | 6 | 4 | 144 |
| TPD | FN risk: weak assertions could be over-counted as negative | Heuristic classification may treat some non-failure semantics as negative in ambiguous assert expressions | True happy-path-only suites may be under-reported in edge cases | Regression coverage for mixed positive/negative suites and explicit call-pattern checks | Keep heuristics conservative (`not`, `False`, `None`, explicit fail/raises calls), preserve ratio threshold gate, and monitor future field reports | 5 | 2 | 6 | 60 |

## 2026-04-05 - PFS framework-surface error-handling calibration (Issue #142)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| PFS | FP-severity: framework-facing modules reported as HIGH for expected error-handling variance | Context-agnostic fragmentation scoring treated endpoint/orchestration diversity as structural drift | Triage noise, lower trust, and over-prioritized low-actionability work | Field test report + targeted PFS regressions | Framework-surface heuristic hints + score dampening + HIGH-to-MEDIUM cap for error_handling in framework context | 6 | 6 | 4 | 144 |
| PFS | FN-severity: truly harmful framework-boundary fragmentation may be under-ranked | Dampening heuristic can lower urgency in edge cases where variance is actually risky | Delayed remediation for rare high-impact boundary inconsistencies | Regression control test on non-framework core modules | Keep finding emission (no suppression), apply dampening only with explicit hints, expose metadata hints for reviewer override | 6 | 2 | 6 | 72 |

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

## 2026-04-05 - HSC error-message constant false positives (Issue #163)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| HSC | FP: Natural-language error/warning/message constants are flagged as hardcoded secrets | Secret-shaped variable names (`token`, `secret`) matched without checking if literal is a human-readable message constant (for example `_MAX_TOKENS_ERROR`) | High-severity triage noise and lower trust in HSC findings | Field test on langchain + new regression test for `_MAX_TOKENS_ERROR`-style constant | Suppress literals when variable name suffix indicates message constant (`_ERROR`, `_WARNING`, `_MESSAGE`) and content looks like natural-language message text | 6 | 6 | 4 | 144 |
| HSC | FN: Real credential assigned to `*_ERROR`/`*_WARNING`/`*_MESSAGE` may be under-reported | New suppression heuristic can treat malformed or unusual credential strings as messages | Rare real secret leaks in misnamed constants may be delayed | Existing token-prefix and URL-userinfo detections still fire before suppression | Keep suppression narrow: suffix + natural-language heuristic (minimum length, word count, whitespace) and preserve high-confidence prefix checks | 5 | 2 | 6 | 60 |

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
