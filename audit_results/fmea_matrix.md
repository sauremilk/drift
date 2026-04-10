# FMEA Matrix

## 2026-06-14 - ADR-039: Activate MAZ/PHR/HSC/ISD/FOE for Scoring

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| MAZ | FP: localhost/dev-tool handlers flagged for missing auth | Handler serves local development traffic only; MAZ fallback sees decorated handler without auth markers | Triage noise in CLI-tool/dev-server repositories | `maz_tn_cli_serving_path` fixture + existing MAZ precision suite | Low weight (0.02); existing CLI-path/dev-path suppression; localhost false-positive fence already hardened | 4 | 3 | 3 | 36 | Mitigated |
| MAZ | FN: real unauthenticated endpoint ignored due conservative fallback | Expanded auth-parameter matching may suppress true missing-auth findings | Under-reporting for unusual parameter naming conventions | Existing MAZ TP fixtures + precision/recall run | Keep auth-marker set narrow; fallback-scoped only; existing decorator/allowlist guards retained | 5 | 3 | 5 | 75 | Open (bounded) |
| ISD | FP: debug/test configuration files flagged despite being non-production | ISD checks all non-test Python files; local-dev settings with `DEBUG=True` may be intentional | Developer-facing noise in projects with explicit dev configs | `isd_ignore_directive_tn` fixture; `drift:ignore-security` directive | `is_test_file()` gate + `drift:ignore-security` directive; low weight (0.01) bounds impact | 4 | 4 | 3 | 48 | Mitigated |
| ISD | FN: insecure defaults in non-Python config formats missed | ISD is AST-only Python; YAML/JSON/TOML configs not scanned | Under-reporting for polyglot projects | N/A (scope limitation) | Accept: Phase 1 scope is Python-only; future extension possible | 3 | 5 | 7 | 105 | Accepted |
| HSC | FP: template/placeholder values trigger secret detection | Generic variable names with template-like values may match entropy heuristics | Triage noise in scaffold/template repositories | Existing `hsc_placeholder_tn` fixture + env-template suppression | `_is_safe_value` checks, known-prefix ordering, env-template suppression already active | 4 | 3 | 3 | 36 | Mitigated |
| HSC | FN: obfuscated or encoded secrets missed | Base64-encoded or split credentials bypass literal matching | Under-reporting for sophisticated secret embedding | N/A (inherent static analysis limitation) | Accept: HSC targets plain-text literals; obfuscated secrets require runtime/entropy analysis | 5 | 3 | 7 | 105 | Accepted |
| PHR | FP: third-party module import flagged as phantom | PHR only resolves project-internal modules; valid third-party imports not in project tree | False phantom reference in stdlib/vendor import contexts | Existing `phr_builtin_tn` + `phr_star_import_tn` fixtures | Known-module allowlist, `__all__` resolution, star-import handling; weight 0.02 bounds impact | 4 | 3 | 3 | 36 | Mitigated |
| FOE | FP: barrel files flagged as high fan-out despite being re-export modules | `__init__.py` with many re-exports triggers import count threshold | Low-value finding for package index files | `foe_barrel_file_tn` fixture | Barrel-file suppression in FOE signal; very low weight (0.005) bounds score impact | 3 | 3 | 3 | 27 | Mitigated |
| ALL | Score inflation from 5 newly-scoring signals | Combined weight addition (+0.065) may inflate composite scores for repos triggering multiple signals | Score comparability break vs. pre-activation baselines | Baseline diff after activation; `drift_diff` verification | Conservative weights (total +0.065 out of ~1.0); gradual activation allows recalibration | 5 | 3 | 4 | 60 | Open (bounded) |

## 2026-04-10 - TypeScript signal expansion: TSB + NCV TS checks

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| TSB | FP: intentional TypeScript escape hatch flagged as architectural bypass | `as any`, non-null assertions, or `@ts-ignore` used intentionally in migration or framework boundary code | Extra noise in TS-heavy repositories and lower prioritization trust | Dedicated fixtures in `tests/fixtures/typescript/type_safety_bypass/` and `tests/test_type_safety_bypass.py` | Keep severity bounded and rely on focused evidence in metadata for triage | 5 | 4 | 4 | 80 | Open (bounded) |
| TSB | FN: bypass pattern missed in nested or syntax-variant cast forms | AST shape variance across TS/TSX files or parser edge cases | Real type-safety erosion is under-reported | Parser and signal tests across clean/moderate/severe fixtures | Keep detection logic AST-based and add regression fixtures for new syntax variants | 7 | 3 | 4 | 84 | Open (bounded) |
| NCV | FP: mixed naming conventions reported in codebases with deliberate multi-style boundaries | Cross-team or generated-code coexistence intentionally mixes interface/generic conventions | Increased low-severity findings and possible alert fatigue | `tests/test_ts_naming_consistency.py` + fixture matrix | Low severity, convention ratio thresholds, and file-level context in findings | 4 | 5 | 4 | 80 | Mitigated |

## 2026-04-13 - ADR-036/037/038: AVS/DIA/MDS FP-Reduction

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| AVS | FN: models/ cross-layer import no longer detected | `models` moved to `_OMNILAYER_DIRS` — genuine layer violations from models/ are suppressed | Under-reporting for projects using models/ as a strict DB layer | `avs_models_omnilayer_tn` fixture + precision/recall run | Configurable `omnilayer_dirs` allows reversal; `models` is cross-cutting in >80% of observed repos | 4 | 2 | 4 | 32 | Open (bounded) |
| AVS | FP: custom omnilayer_dirs config too broad | User adds too many dirs → most imports become omnilayer → signal degrades | AVS produces very few findings → loss of signal value | Config validation at load time (empty default) | Conservative default (empty list); documentation explains risk | 3 | 2 | 5 | 30 | Mitigated |
| DIA | FN: custom auxiliary dir hides real undocumented source dir | `extra_auxiliary_dirs` config skips a dir that should be documented | Genuine documentation gap not reported | Default is empty (no dirs skipped by default) | Only user-configured dirs are skipped; no default change to _AUXILIARY_DIRS | 3 | 2 | 5 | 30 | Mitigated |
| MDS | FN: protocol-method skip suppresses real duplication | Two classes implement same protocol method with genuinely duplicated non-trivial logic | Real near-duplication in protocol implementations not detected | Protocol-method set is narrow (20 names); only same-name different-class skipped | Only exact bare-name match + different class qualifies; body similarity not checked for skip | 4 | 2 | 5 | 40 | Open (bounded) |
| MDS | FN: thin-wrapper gate suppresses refactoring opportunity | Wrapper function with LOC ≤ 5 that adds real behavior flagged as thin wrapper | Missed consolidation opportunity | `_is_thin_wrapper` checks for exactly 1 Call node in AST | Single-call heuristic is conservative; complex wrappers with conditions still detected | 3 | 2 | 4 | 24 | Mitigated |
| MDS | FP: name-token similarity inflates score for same-named functions | Two unrelated functions with similar names get bonus from name similarity | Unrelated functions flagged as near-duplicates | Name component is only 10% of hybrid formula | 10% weight limits maximum name-only inflation to 0.10 total similarity | 3 | 2 | 3 | 18 | Mitigated |

## 2026-04-12 - ADR-035: PHR per-repository calibration

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| PHR | FN: relevant phantom reference finding down-ranked too strongly | Repository feedback history contains biased/incorrect "false positive" labels for structurally valid PHR cases | Under-prioritized remediation for real reference drift in calibrated repository | `tests/test_calibration.py`, `tests/test_phantom_reference.py`, precision/recall run | Bound dampening factors, confidence weighting, and default fallback when calibration confidence is low | 7 | 4 | 4 | 112 | Open (bounded) |
| PHR | FP: calibration not applied although repository has repeat FP pattern | Missing or stale `data/negative-patterns/` calibration snapshot, repo fingerprint mismatch, or cache invalidation | Repeated noisy PHR findings persist and reduce actionability | CLI calibration tests + snapshot persistence checks | Explicit calibrate/feedback commands, deterministic repo fingerprinting, lazy reload on changed calibration file | 5 | 3 | 4 | 60 | Mitigated |
| PHR | Integrity risk: malformed calibration payload influences scoring path | External/manual edits to calibration JSON introduce invalid schema/value ranges | Runtime errors or unstable score adjustments | `tests/test_task_spec.py`, schema validation in calibration loading path | Strict validation + safe defaults on parse/validation failure; ignore invalid entries | 6 | 2 | 3 | 36 | Mitigated |

## 2026-04-07 - PFS FTA v1: RETURN_PATTERN extraction (MCS-1 recall fix)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| PFS | FN: return-strategy diversity not detected | No `RETURN_PATTERN` enum value; no extraction path in `_process_function()` | pfs_002 recall = 0; overall PFS recall = 0.5 | `test_return_strategy_mutation_benchmark_scenario`, `test_return_pattern_two_variants_detected` | `PatternCategory.RETURN_PATTERN` + `_fingerprint_return_strategy()` in ast_parser.py | 7 | 8 | 2 | 112 | **Mitigated** |
| PFS | FP: intentional return-strategy overloading flagged | Module deliberately offers get/get_or_raise/get_result patterns | Low-value finding on API-convenience modules | `test_return_pattern_single_variant_no_finding`; ≥2 strategies threshold | Per-function ≥2-strategy gate; PFS aggregates per-module (canonical dominance dampens) | 3 | 3 | 7 | 63 | Accepted |
| PFS | FN: dynamic/callback returns not classifiable | Return strategy determined at runtime via callback or config | Under-reporting for indirection-heavy code | N/A — static analysis limitation | Accept: AST-level analysis cannot resolve runtime dispatch | 2 | 4 | 8 | 64 | Accepted |
| PFS | FP: nested function returns leak into outer fingerprint | `_fingerprint_return_strategy` walks into nested defs | Inflated strategy set for outer function | `test_return_strategy_ignores_nested_functions` | Queue-based walk skips `FunctionDef`/`AsyncFunctionDef`/`ClassDef` children | 5 | 2 | 2 | 20 | **Mitigated** |

## 2026-04-07 - AVS FTA v1: co-change precision failure (3 primary MCS) — MITIGATED 2026-04-07

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| AVS | FP/Disputed: same-package sibling files flagged as hidden coupling | `_check_co_change` has no same-directory guard; sibling signal files co-change naturally via shared registry without import edge | 7/10 Disputed in drift_self sample; precision_strict 0.3 for avs_co_change | MCS-1 operationell test: `test_co_change_same_directory_suppressed` — PASSING | Same-directory guard via `PurePosixPath.parent` comparison with root-level exception (`!= "."`) in `_check_co_change` | 6 | 2 | 2 | 24 | **Mitigated** |
| AVS | FP/Disputed: test↔source pairs flagged as hidden coupling | `known_files` uses unfiltered `parse_results`; graph uses `filtered_prs` → `has_edge` always False for test-source pairs | Test-source co-evolution misreported as architectural violation (e.g. `config.py ↔ test_config.py` Disputed) | MCS-2 operationell test: `test_co_change_test_source_pair_suppressed` — PASSING | `known` now built from `filtered_prs` (consistent with graph): `known = {pr.file_path.as_posix() for pr in filtered_prs}` | 5 | 1 | 2 | 10 | **Mitigated** |
| AVS | FP/Disputed: bulk-commit sweep inflates co_change_count without semantic coupling | Release/FMEA-sweep commits touch all signal files simultaneously; `CoChangePair.confidence` counts all commits equally regardless of commit size | Inflated confidence scores for signal-file pairs that co-change only in sweep commits | MCS-3 operationell test: `test_co_change_bulk_commits_discounted` — PASSING | Commit-size discount `weight = 1.0 / max(1, len(files) - 1)` in `build_co_change_pairs`; hard >20 cut retained | 5 | 2 | 3 | 30 | **Mitigated** |
| AVS | Latent FP: `models.py` assigned to layer 2, imported cross-cuttingly | `_DEFAULT_LAYERS` maps `models` → 2 (DB layer); drift-style DTO/config models are cross-cutting and should be omnilayer | Potential `avs_upward_import` FPs in CLI-architecture repos (not yet observed in ground truth) | No Disputed avs_upward_import in current sample; latent risk | Add `models` to `_OMNILAYER_DIRS` or add default `allowed_cross_layer` pattern for `**/models.py` | 4 | 2 | 6 | 48 | Open (latent) |
| AVS | FN: same-directory guard suppresses cross-boundary findings in flat-root repos | After MCS-1 fix, repos with all modules in root dir will have same-directory pairs suppressed | Real hidden coupling in flat repos not reported | FN-guard test: `test_co_change_root_level_not_suppressed` — PASSING | Guard only applies when parent dir != "." (root-level files pass through) | 4 | 2 | 6 | 48 | Accepted |
| AVS | FN: test-file filter on `known` suppresses test-orchestrated cross-module coupling | After MCS-2 fix, test files are no longer candidates for co-change pairs | Rarely relevant (test files rarely cause architectural coupling concerns) | N/A — test files already excluded from import-graph analysis | Accept: test-source co-change is expected behavior, not a finding target for AVS | 2 | 1 | 8 | 16 | Accepted |

## 2026-04-07 - DIA FTA v2: deep false-positive reduction (6 MCS)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| DIA | FP: language keyword compounds (`try/except`, `match/case`) extracted as dir refs | `_PROSE_DIR_RE` matches `word/` without checking if next char continues the token | Python syntax patterns produce phantom-dir findings in ADR codespans | P5 regression tests: `test_try_except_not_extracted`, `test_match_case_not_extracted` | P5: Negative lookahead `(?!\w)` on `_PROSE_DIR_RE` — only matches when slash is followed by non-word char or EOL | 5 | 6 | 2 | 60 |
| DIA | FP: prose slash-separator (`parent/tree`) extracted as dir ref | Slash used as concept separator in prose, not path separator | Non-directory tokens produce phantom-dir findings | P5 regression test: `test_parent_tree_not_extracted` | P5: `(?!\w)` negative lookahead blocks `word/word` continuations | 4 | 5 | 2 | 40 |
| DIA | FP: multi-segment path decomposes into intermediate refs | `src/drift/output/csv_output.py` → `output/` extracted as separate ref | Intermediate path segments produce phantom-dir findings | P5 regression tests: `test_multisegment_path_extracts_terminal_only`, `test_multisegment_trailing_slash_extracts_last` | P5: `(?!\w)` ensures only terminal segment (before whitespace/EOL) is extracted | 5 | 5 | 2 | 50 |
| DIA | FP: GitHub URL owner/repo in plain text | `mick-gsk/drift` in non-link text passes regex; URL path segments extracted | GitHub handles produce phantom-dir findings | P3 + P5 regression tests: `test_github_url_not_extracted` | P3: `_strip_urls()` removes URLs before regex; P5: `(?!\w)` blocks `mick-gsk/d` | 4 | 4 | 2 | 32 |
| DIA | FP: dotfile path produces phantom ref | `.drift-cache/history.json` → `drift-cache/` extracted → existence check fails | Dotfile-prefixed dirs not recognized by `_ref_exists_in_repo()` | P6 regression tests: `test_dotfile_prefix_found`, `test_dotfile_must_be_dir` | P6: Check `repo_path / f".{ref}"` in `_ref_exists_in_repo()`; P5 also blocks `drift-cache/h` | 3 | 3 | 2 | 18 |
| DIA | FP: auxiliary dirs (`tests/`, `scripts/`, `benchmarks/`) flagged as undocumented | `_source_directories()` includes all dirs with .py files; conventional dirs rarely in README | Low-value findings for universally understood directories | P1 regression tests: `test_tests_dir_not_flagged`, `test_nonaux_dir_still_flagged` | P1: `_AUXILIARY_DIRS` frozenset excludes conventional project directory names | 3 | 8 | 2 | 48 |
| DIA | FN: P5 lookahead may miss intermediate path segments | Only terminal segment of multi-segment path extracted (e.g. `src/drift/` → only `drift`) | Intermediate segments not checked for existence | Mutation benchmark DIA recall 3/3 = 100% | Terminal segment is always the meaningful claim target; intermediate segments rarely the intent | 3 | 3 | 5 | 45 |
| DIA | FN: P1 auxiliary set may exclude non-standard dir with conventional name | Project-specific dir named `test` or `scripts` would be excluded | Under-reporting if such a dir has genuine documentation gap | `test_nonaux_dir_still_flagged` verifies non-aux dirs still reported | Only well-known convention names in set; `artifacts`/`work_artifacts` added 2026-04-08 | 3 | 2 | 5 | 30 |
| DIA | FP: ADR example refs extracted via `trust_codespans=True` | ADR text about DIA uses illustrative path refs in inline codespans | Illustrative examples produce phantom-dir findings on own repo | `test_fenced_block_services_not_extracted` regression test | Move illustrative examples to fenced code blocks (DIA skips `block_code` tokens) | 2 | 2 | 2 | 8 |
| DIA | FP: `work_artifacts/` flagged as undocumented source dir | Working/artifact dirs with ad-hoc .py scripts not in `_AUXILIARY_DIRS` | Low-value finding for non-architectural scratch directory | `test_artifacts_dir_not_flagged` regression test | P1: Extended `_AUXILIARY_DIRS` with `artifacts`, `work_artifacts` | 2 | 3 | 2 | 12 |

## 2026-04-07 - DIA FTA v1: initial false-positive reduction (3 cut sets)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| DIA | FP: codespan directory refs extracted without structure context | `_walk_tokens()` set `allow_without_context=True` for all `codespan` tokens regardless of surrounding prose | REST paths, inline code examples, foreign-repo refs emitted as phantom-dir findings | New CS-1 regression tests (no-keyword codespan → no finding, keyword present → finding kept) | Sibling-context keyword gate: collect text-children from parent paragraph/heading, only trust codespans when structure keywords present; `trust_codespans=True` for ADR files | 5 | 7 | 3 | 105 |
| DIA | FN: codespan context gate may suppress legit structure refs in keyword-free prose | Paragraphs without structure keywords (e.g. "use `services/` for the logic") are no longer extracted | Potential under-reporting of phantom dirs in informal prose | Ground-truth regression for `dia_adr_mismatch_tp` + keyword set includes "architecture", "component" | Conservative keyword list covering common README section headings; running context propagation across siblings (heading → list) | 4 | 3 | 5 | 60 |
| DIA | FP: phantom dir finding when directory exists under src/ or lib/ prefix | `_source_directories()` only records `parts[0]`; `src/services/` yields `src` not `services` | README ref `services/` flagged as missing despite `src/services/` existing | New CS-2 regression tests (src/services/ exists → no finding; tests/services/ → finding stays) | Container-prefix existence check: `_ref_exists_in_repo()` checks direct path + curated prefix set (`src`, `lib`, `app`, `pkg`, `packages`, `libs`, `internal`) | 5 | 4 | 3 | 60 |
| DIA | FN: container-prefix check may mask phantom dirs existing only under src/ | If README claims top-level `services/` but only `src/services/` exists (unrelated context) | Phantom dir not reported | Regression test verifies `tests/services/` (non-container) still triggers finding | Curated prefix set excludes `tests`, `benchmarks`, `docs` etc.; only production-code containers | 4 | 2 | 5 | 40 |
| DIA | FP: superseded/deprecated ADR references flagged as phantom dirs | `_scan_adr_files()` treated all ADRs identically regardless of lifecycle status | Pre-refactoring or rejected ADRs produce stale-reference findings | New CS-3 regression tests (superseded → skip, accepted → finding, no status → finding) | Parse YAML frontmatter + MADR freetext status; skip `superseded`/`deprecated`/`rejected` | 5 | 4 | 3 | 60 |
| DIA | FN: skipped ADR may still reference a real phantom dir | Superseded ADR with coincidentally valid phantom-dir ref is not scanned | Under-reporting for edge case | N/A (superseded ADRs are not authoritative per policy) | Only skip 3 statuses; `proposed`/`accepted`/no-status continue to be scanned | 3 | 2 | 6 | 36 |

## 2026-04-07 - MAZ/ISD/HSC wave-2 calibration

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MAZ | FN: auth-injected endpoints still flagged due narrow parameter normalization | Fallback previously matched only exact parameter markers and missed camelCase/composed auth-context names | Reduced precision and noisy missing-auth findings in decorator-only fallback contexts | New MAZ regressions for camelCase and access-token parameter variants | Normalize snake/camel/non-alnum parameter names and apply conservative auth-context regex patterns in fallback-only path | 6 | 4 | 4 | 96 |
| MAZ | FN: broad auth-parameter patterns may hide real unauthenticated routes | Expanded auth-like parameter matching can classify rare business params as auth context | Potential under-reporting in edge naming conventions | Control regression keeps plain path params reportable | Keep patterns conservative and fallback-scoped; retain existing auth-decorator/allowlist guards | 5 | 3 | 6 | 90 |
| ISD | FN: insecure defaults can be accidentally suppressed by loose ignore substring | Header check accepted any line containing `drift:ignore-security` substring | Entire-file skip in unintended comment variants, reducing signal trust | New regressions for valid directive vs similar invalid marker | Require explicit comment directive with word boundary in first header lines | 6 | 3 | 4 | 72 |
| HSC | FN: wrapped credential literals (for example `Bearer sk-...`) bypass known-prefix detection | Prefix detection expected token prefix at string start only | Missed high-confidence secret findings in auth-header style assignments | New regression for Bearer-wrapped prefix literal | Normalize common wrappers (`Bearer `, `token `) before known-prefix checks | 7 | 4 | 4 | 112 |

## 2026-04-06 - MAZ/ISD/HSC scoring-readiness calibration

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MAZ | FP: decorator fallback flags routes that already carry injected auth context | Fallback previously treated all decorated handlers without auth decorators as unauthenticated, even when parameters indicated injected identity context | Reduced triage trust and lower actionability for missing-auth findings | New fallback regressions for auth-like and non-auth-like parameters | Skip fallback findings when conservative auth-like parameter markers are present; keep path-parameter control test | 6 | 4 | 4 | 96 |
| MAZ | FN: auth-like parameter suppression can hide real unauthenticated routes | Endpoint parameter names may overlap with auth-like marker tokens in edge naming conventions | Some true missing-auth findings may be delayed | Control regression keeps `user_id` path parameter reportable | Keep marker set conservative and scoped to fallback-only path; preserve allowlist/dev-path/auth-decorator checks | 5 | 3 | 6 | 90 |
| ISD | FP-severity: localhost `verify=False` is ranked too harshly for local-dev context | Previous rule emitted full `insecure_ssl_verify` severity without distinguishing loopback targets | Lower perceived signal credibility for local testing scenarios | New regression for localhost downgrade path | Keep finding visible but downgrade to `insecure_ssl_verify_localhost` with lower score for loopback/localhost URLs | 5 | 5 | 4 | 100 |
| ISD | FN-severity: non-loopback misuse could be downgraded if target classification is too broad | Loopback detection heuristic may overmatch unusual host strings | Real TLS verification misuse may be under-prioritized | Precision/recall suite plus localhost-specific regression | Restrict downgrade to first-argument literal HTTP(S) URLs with strict loopback host matching | 6 | 2 | 5 | 60 |
| HSC | FN: known API-token prefixes in generic variable names are missed | Previous detection depended heavily on secret-shaped variable names before high-confidence literal cues | High-confidence secret leaks remained undetected in generic config names | New regressions for generic variable and keyword-argument cases | Evaluate known-prefix literals before name-shaped fallback to emit `hardcoded_api_token` deterministically | 8 | 4 | 4 | 128 |
| HSC | FP: known-prefix expansion may flag benign placeholder-like values | Prefix-first detection increases sensitivity when generic names carry token-like literals | Potential triage noise in synthetic/template contexts | Existing TN fixtures + new template confounder in ground truth | Keep `_is_safe_value` checks and minimum literal length gate; retain TN fixture coverage in precision/recall suite | 5 | 3 | 6 | 90 |

## 2026-04-06 - MDS precision-first scoring-readiness calibration

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| MDS | FP: semantic-only and intentional variant pairs inflate scoring noise | Semantic-only matching accepted same-file conceptual similarity; sync/async intentional variants looked like duplicates; hybrid threshold was looser than AST threshold | Reduced confidence in MDS as scoring input and lower actionability of findings | Live-scan triage + targeted edge-case regression tests | Precision-first hybrid threshold, sync/async variant suppression, stricter semantic gate, same-file semantic suppression | 6 | 5 | 4 | 120 |
| MDS | FN: true duplicates in sync/async ecosystems may be suppressed | New suppression treats same-name sync/async path variants as intentional by default | Potential under-reporting of some real copy-paste drift patterns | Control regression keeps non-variant exact duplicates detectable | Conservative path-token gating and regression coverage for non-variant duplicate detection | 4 | 3 | 6 | 72 |

## 2026-04-06 - TPD unexpected source-segment exception hardening (Issue #184)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN |
|---|---|---|---|---|---|---:|---:|---:|---:|
| TPD | FN: signal execution aborts and gets skipped | `ast.get_source_segment` can raise unexpected exception types in edge AST/source-position scenarios, and the previous guard covered only selected exception classes | Missing TPD findings in export-context/cross-signal analysis and reduced trust in context completeness | Field-test report + targeted runtime-exception regression | Broaden source-segment exception guard to fail-safe behavior and add per-file analyze guards for parse/AST visit | 8 | 3 | 4 | 96 |
| TPD | FN: single malformed file can suppress module-level coverage | Unexpected AST parse/visit errors may occur on isolated files | Reduced per-module signal coverage (partial under-reporting) | New regression plus debug logging path for skipped files | Skip only failing file, continue analysis for remaining module files, keep deterministic thresholds | 5 | 3 | 5 | 75 |

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

## 2026-04-09 - PHR Signal: Phantom Reference (ADR-033)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| PHR | FP: star-import file references name provided by star | Star imports (`from X import *`) inject unknown names into scope | False phantom finding for names actually available via star import | `phr_star_import_tn` fixture | Conservative skip: files with star imports are excluded from PHR analysis | 4 | 3 | 2 | 24 | **Mitigated** |
| PHR | FP: module __getattr__ provides dynamic names | Module-level `__getattr__` makes any attribute access valid | False phantom finding for dynamically provided names | `phr_dynamic_tn` fixture | Conservative skip: files with module-level `__getattr__` are excluded | 4 | 2 | 2 | 16 | **Mitigated** |
| PHR | FP: plugin/extension names resolved at runtime | Plugin systems register names dynamically via entry points or registries | False positive for intentionally late-bound names | Manual review | `_FRAMEWORK_GLOBALS` allowlist covers common framework names; further refinement via config | 3 | 3 | 5 | 45 | Accepted |
| PHR | FN: exec/eval introduce names not visible to AST | `exec()` or `eval()` can inject names into scope at runtime | Phantom names created by exec/eval not detected as defined | `_has_exec_eval` detection flag (logged, not yet used for suppression) | Accept: static analysis limitation; exec/eval usage is rare in well-structured code | 3 | 2 | 8 | 48 | Accepted |
| PHR | FN: getattr-based access not tracked | `getattr(obj, "name")` resolves names at runtime | Under-reporting for highly dynamic codebases | N/A — static analysis limitation | Accept: getattr patterns are intentionally dynamic | 2 | 3 | 8 | 48 | Accepted |
| PHR | FP: third-party library names not in project symbol table | Names from installed packages (e.g. `requests.get`) not tracked | False positive for external dependency calls | Project-wide symbol table includes import-resolved names | Import-tracked names are added to available set; root name resolution covers `import X; X.call()` | 5 | 4 | 3 | 60 | **Mitigated** |

## 2026-04-10 - Scoring Promotion: HSC, FOE, PHR (ADR-040)

| Signal | Failure Mode | Cause | Effect | Detection | Mitigation | S | O | D | RPN | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| HSC | FP: non-secret config value in secret-free file | Variable names like DB_HOST, API_TIMEOUT don't match secret patterns | No false trigger expected | `hsc_placeholder_tn` fixture | Variable-name heuristic requires known secret-indicating patterns | 2 | 1 | 2 | 4 | **Mitigated** |
| HSC | FP: environment-read variable flagged as hardcoded | Variable name matches secret pattern but value is `os.environ[...]` call | False finding on properly externalized secrets | `hsc_env_read_tn` fixture | AST check: RHS is `os.environ`/`os.getenv` call → skip | 5 | 3 | 2 | 30 | **Mitigated** |
| HSC | FN: obfuscated secret not detected | Secret is base64-encoded, split across variables, or loaded from non-standard path | Missed hardcoded credential | Manual review | Accept: HSC is first-pass static heuristic; obfuscated secrets require dedicated secret scanning tools | 6 | 3 | 7 | 126 | Accepted |
| HSC | FP: ML tokenizer/model constants flagged | High-entropy hex strings in ML vocabulary files match secret heuristic | False finding on legitimate ML constants | `hsc_tn_ml_tokenizer_constants` fixture | Context-aware skip for known ML file patterns | 4 | 2 | 2 | 16 | **Mitigated** |
| FOE | FP: barrel/re-export __init__.py flagged | `__init__.py` files re-export many names from submodules | False fan-out finding on standard package pattern | `foe_barrel_file_tn` fixture | `__init__.py` files excluded from FOE detection | 3 | 4 | 2 | 24 | **Mitigated** |
| FOE | FN: high fan-out via dynamic imports | `importlib.import_module()` or `__import__()` used to load modules | Under-reporting for dynamically assembled modules | N/A — static analysis limitation | Accept: dynamic imports are invisible to AST-based import counting | 3 | 2 | 8 | 48 | Accepted |
| FOE | FP: test file with many test-helper imports | Test files often import many fixtures, helpers, and mocks | False finding on standard test organization | `is_test_file()` guard | Test files excluded via file-discovery filter | 3 | 3 | 2 | 18 | **Mitigated** |
| PHR | Scoring promotion: FP in composite score | PHR false positive now affects composite drift score (weight 0.02) instead of being report-only | Slightly inflated drift score for affected modules | Precision/recall suite + `phr_conditional_import_tn`, `phr_framework_decorator_tn` fixtures | Low weight (0.02) limits score impact; existing FP mitigations remain active | 5 | 3 | 3 | 45 | **Mitigated** |
