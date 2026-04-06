# Risk Register

## 2026-04-06 - DCA script-context false-positive mitigation (Issue #176)

- Risk ID: RISK-SIG-2026-04-06-176
- Component: src/drift/signals/dead_code_accumulation.py
- Type: Signal quality (false positives / precision calibration)
- Description: DCA reported script-internal functions in executable Python utility/CI modules as unused exports because usage is often local call graph + `__main__` execution, not cross-file imports.
- Trigger examples:
  - microsoft/agent-framework: `.github/workflows/python-check-coverage.py`
  - Similar repositories with executable Python scripts under `.github/workflows`, `scripts`, `tools`, or `bin`.
- Impact: Medium-high false-positive noise in DCA, reduced trust in dead-code recommendations.
- Mitigation:
  - Added conservative script-context path suppression for Python files in script-like locations.
  - Added regression test in `tests/test_dead_code_accumulation.py` for `.github/workflows/python-check-coverage.py`.
- Verification: `python -m pytest tests/test_dead_code_accumulation.py -q --maxfail=1`
- Residual risk: Medium-low; script-like paths containing genuine import-oriented library modules may be under-reported, but scope is intentionally limited to executable-context locations.

## 2026-04-05 - HSC OpenTelemetry GenAI semconv false-positive mitigation (Issue #175)

- Risk ID: RISK-SIG-2026-04-05-175
- Component: src/drift/signals/hardcoded_secret.py
- Type: Signal quality (false positives / precision calibration)
- Description: HSC flagged OpenTelemetry GenAI observability constants (for example `INPUT_TOKENS = "gen_ai.usage.input_tokens"`) as hardcoded secrets because `token` in symbol names triggered the secret-variable heuristic.
- Trigger examples:
  - microsoft/agent-framework: `python/packages/core/agent_framework/observability.py` with GenAI metrics constants.
  - Similar repositories using OpenTelemetry GenAI semantic-convention keys (`gen_ai.*`) in constants.
- Impact: High-severity false positives in telemetry modules, reduced trust in HSC precision, and avoidable remediation churn.
- Mitigation:
  - Added conservative suppression for OpenTelemetry GenAI semantic-convention literals (`gen_ai.<segment>.<segment...>`).
  - Preserved high-confidence secret detection ordering (known prefixes are evaluated before suppression).
  - Added targeted regressions in `tests/test_hardcoded_secret.py` for non-detection of semconv constants and continued detection of known-prefix secrets.
- Verification: `python -m pytest tests/test_hardcoded_secret.py -q --maxfail=1`
- Residual risk: Low-medium; rare credential strings mimicking `gen_ai.*` key format may be under-reported, but suppression scope is intentionally narrow and known-prefix checks remain active.

## 2026-04-05 - Scan/Analyze Cross-Validation Felder im Scan-Output (Issue #171)

- Risk ID: RISK-OUT-2026-04-05-171
- Component: src/drift/api.py, src/drift/api_helpers.py
- Type: Output contract clarity / automation reliability
- Description: Agenten mussten Scan- und Analyze-Resultate mit unterschiedlichen Feldnamen und ohne stabilen Finding-Fingerprint korrelieren. Das erhöhte das Risiko von fehlerhaften Deduplikationen und inkonsistenter Priorisierung.
- Trigger examples:
  - Vergleich `scan` vs `analyze` in CI/Agent-Workflows mit signalabhängiger Bündelung.
  - Automatisierte Merges von Findings über mehrere Läufe ohne stabile ID.
- Impact: Erhöhte Fehlzuordnung in Cross-Validation, geringere Reproduzierbarkeit bei agentischen Workflows.
- Mitigation:
  - Harmonisierte Scan-Felder: `signal_abbrev`, `signal_id`, `signal_type` in concise/detailed/fix_first.
  - Stabile Finding-ID im Scan-Output ergänzt: `fingerprint` (deterministisch über bestehende Baseline-Fingerprint-Logik).
  - Numerische Schweregradskalierung ergänzt: `severity_rank` je Finding.
  - Top-Level-Metadaten ergänzt: `cross_validation` mit Signalfeld-Mapping, Severity-Ranking und numerischer Score-Skala.
  - Regressionen ergänzt in `tests/test_scan_diversity.py`.
- Verification: `python -m pytest tests/test_scan_diversity.py tests/test_agent_native_cli.py -q --maxfail=1`
- Residual risk: Low; Änderung ist additiv und rückwärtskompatibel für bestehende Consumer, die unbekannte Felder ignorieren.

## 2026-04-05 - AVS/ECM/TPD Recall-Härtung auf Groß-Repositories (Issue #170)

- Risk ID: RISK-SIG-2026-04-05-170
- Component: src/drift/signals/architecture_violation.py, src/drift/signals/exception_contract_drift.py, src/drift/signals/test_polarity_deficit.py
- Type: Signal quality (false negatives / recall)
- Description: Drei unabhängige Recall-Lücken konnten auf großen Repositories zu systematischen 0-Finding-Ergebnissen führen: (1) AVS verlor interne Kanten bei relativen Imports, (2) ECM analysierte bei großen Kandidatmengen ein zu kleines Hot-File-Subset, (3) TPD erhielt bei globalem `**/tests/**`-Exclude keine Test-ParseResults.
- Trigger examples:
  - Relative Imports (`from .service import ...`) in Paketstrukturen mit starker interner Modulkopplung.
  - Repositories mit tausenden ECM-Kandidaten und hoher Commit-Konzentration auf wenigen Dateien.
  - Standard-Setups mit globalem Test-Exclude, bei denen TPD trotz aktivem Signal keine Testdateien sieht.
- Impact: Unterberichtete Architektur- und Testsignal-Befunde, reduzierte Signal-Glaubwürdigkeit bei Real-World-Scans.
- Mitigation:
  - AVS: relative Import-Kandidatenauflösung für interne Graph-Kanten ergänzt.
  - ECM: adaptive Kandidatenobergrenze (konfigurierter Floor, skalierender Cap bis 300) ergänzt.
  - TPD: Fallback-Testdatei-Discovery aus Repo-Dateisystem ergänzt, wenn ParseResults keine Tests enthalten.
  - Regressionen ergänzt in `tests/test_architecture_violation.py`, `tests/test_exception_contract_drift.py`, `tests/test_test_polarity_deficit.py`.
- Verification: `python -m pytest tests/test_architecture_violation.py tests/test_exception_contract_drift.py tests/test_test_polarity_deficit.py -q --maxfail=1`
- Residual risk: Medium-low; relative Importauflösung bleibt best-effort ohne expliziten AST-Level, und TPD-Fallback kann in exotischen Repo-Layouts zusätzliche Laufzeit verursachen.

## 2026-04-05 - MAZ decorator fallback recall calibration (Issue #169)

- Risk ID: RISK-SIG-2026-04-05-169
- Component: src/drift/signals/missing_authorization.py
- Type: Signal quality (false negatives / recall)
- Description: MAZ depended fully on `API_ENDPOINT` patterns. In files where ingestion did not emit endpoint patterns despite route decorators, MAZ returned no findings.
- Trigger examples:
  - Framework files with decorated handlers (`@router.get`, `@app.post`) and missing auth where pattern extraction under-detects endpoints.
  - Large repositories with mixed routing idioms where ingestion coverage is incomplete per file.
- Impact: Missing-authorization gaps can be silently under-reported, reducing trust in MAZ recall.
- Mitigation:
  - Added conservative decorator fallback endpoint inference in MAZ, activated only when a file has no `API_ENDPOINT` patterns.
  - Added auth-decorator suppression in fallback path.
  - Added regressions in tests/test_missing_authorization.py for fallback detection and auth-decorator suppression.
- Verification: `python -m pytest tests/test_missing_authorization.py -q --maxfail=1`
- Residual risk: Medium-low; fallback may still need marker tuning for rare decorator naming collisions, but scope is constrained and existing suppressions remain active.

## 2026-04-05 - BEM fallback-assignment and AVS src-root import false-negative mitigation (Issue #168)

- Risk ID: RISK-SIG-2026-04-05-168
- Component: src/drift/ingestion/ast_parser.py, src/drift/signals/broad_exception_monoculture.py, src/drift/signals/architecture_violation.py
- Type: Signal quality (false negatives / recall)
- Description: Two recall gaps reduced signal quality on large real-world repositories: (1) BEM did not treat broad-exception fallback assignments as swallowing handlers, and (2) AVS failed to resolve internal imports in source-root layouts (`src/`, `lib/`, `python/`) when imports omitted the source-root prefix.
- Trigger examples:
  - huggingface/transformers: repeated `except Exception: _available = False` style handlers in import utility modules.
  - src-root package imports such as `transformers.api.routes` resolving to `src/transformers/api/routes.py`.
- Impact: Under-reported high-signal architectural drift and exception monoculture findings, reducing trust in Drift recall.
- Mitigation:
  - Added `fallback_assign` handler action in AST fingerprinting and included it in BEM swallowing-action criteria.
  - Added AVS module alias resolution for common source-root prefixes when building the import graph.
  - Added targeted regressions in `tests/test_ast_parser.py`, `tests/test_consistency_proxies.py`, and `tests/test_architecture_violation.py`.
- Verification: `python -m pytest tests/test_ast_parser.py tests/test_consistency_proxies.py tests/test_architecture_violation.py -q --maxfail=1`
- Residual risk: Medium-low; alias resolution currently targets common source roots and may require extension for unusual repository layouts.

## 2026-04-05 - MAZ localhost CLI serving false-positive mitigation (Issue #167)

- Risk ID: RISK-SIG-2026-04-05-167
- Component: src/drift/signals/missing_authorization.py
- Type: Signal quality (false positives / context-sensitive suppression)
- Description: MAZ flagged local CLI serving endpoints (for example `src/transformers/cli/serving/server.py`) as missing authorization even when handlers are intended for localhost-oriented development tooling rather than production API exposure.
- Trigger examples:
  - huggingface/transformers: `cli/serving/server.py` handlers (`chat_completions`, `responses`, `load_model`, `list_models`, `generate`) reported as MAZ findings.
  - Similar repositories with route handlers embedded in CLI-local serving entry modules.
- Impact: Severe precision collapse in this context (reported 0%), high-priority triage noise, and risk of incorrect remediation guidance.
- Mitigation:
  - Added targeted MAZ suppression for CLI-local serving path context (`cli` + `serving/serve` markers).
  - Added Issue #167 regressions ensuring CLI-serving path is suppressed while non-CLI serving path remains reportable.
- Verification: `python -m pytest tests/test_missing_authorization.py -q`
- Residual risk: Medium-low; unusual production deployments using CLI-serving path conventions may be under-reported, but suppression remains tightly scoped.

## 2026-04-05 - HSC ML tokenizer constant false-positive mitigation (Issue #166)

- Risk ID: RISK-SIG-2026-04-05-166
- Component: src/drift/signals/hardcoded_secret.py
- Type: Signal quality (false positives / precision calibration)
- Description: HSC flagged ML tokenizer configuration constants as hardcoded secrets when symbol names contained `token` despite literals representing NLP metadata (for example `pad_token`, `cls_token`, `tokenizer_class_name`, `chat_template`).
- Trigger examples:
  - huggingface/transformers: tokenizer constants produced high FP volume in HSC findings.
  - Similar NLP repositories with tokenizer config objects and chat-template literals.
- Impact: Significant precision drop, high-severity triage noise, and reduced trust in HSC ranking.
- Mitigation:
  - Add tokenizer-context suppression for known tokenizer symbol names and token literal markers/template syntax.
  - Preserve high-confidence secret detection ordering (known token prefixes are evaluated before suppression).
  - Add targeted regressions for tokenizer constants, tokenizer keyword arguments, and guard test proving known-prefix secrets still fire.
- Verification: `python -m pytest tests/test_hardcoded_secret.py -q --maxfail=1`
- Residual risk: Medium-low; rare misuse of tokenizer-shaped symbols for real credentials may bypass generic detection, but known-prefix secret detection remains active.

## 2026-04-05 - NBV try_* attempt-semantics false-positive mitigation (Issue #165)

- Risk ID: RISK-SIG-2026-04-05-165
- Component: src/drift/signals/naming_contract_violation.py
- Type: Signal quality (false positives / precision calibration)
- Description: NBV flagged `try_*` helper functions as naming-contract violations when `try_` was used in natural "attempt/check" semantics (for example `try_neq_default`) without exception handling intent.
- Trigger examples:
  - langchain-ai/langchain: `libs/core/langchain_core/utils/function_calling.py::try_neq_default`
  - Similar utility/helper modules with comparison-oriented `try_*` functions.
- Impact: Medium-severity false positives, reduced trust in NBV signal, avoidable triage churn.
- Mitigation:
  - Added targeted suppression for `try_*` when body suggests comparison/check semantics (`ast.Compare`, `is None`, `isinstance`).
  - Added utility-context suppression via path tokens (`utils`, `helpers`, `common`).
  - Added regression tests for comparison-semantic and utility-context `try_*` helpers.
- Verification: `python -m pytest tests/test_naming_contract_violation.py -q --maxfail=1`
- Residual risk: Medium-low; some true try/except contract mismatches in helper paths may be under-reported, but suppression is scoped to `try_*` only.

## 2026-04-05 - DIA bootstrap-repo README false-positive mitigation

- Risk ID: RISK-SIG-2026-04-05-DIA-BOOTSTRAP
- Component: src/drift/signals/doc_impl_drift.py
- Type: Signal quality (false positives / actionability threshold)
- Description: `doc_impl_drift` reported `No README found` on bootstrap-sized repositories with zero or one parsed Python file, and on pure `__init__.py` package skeletons, even though the result was not actionable architectural drift for empty, single-file, or init-only repos.
- Trigger examples:
  - Temporary one-file scripts scanned via `drift.api.scan()`.
  - Minimal package skeletons containing only `__init__.py`.
- Impact: Medium-severity noise in baseline scans, lower trust in DIA, and misleading next-step guidance for repositories that are not yet architecturally shaped.
- Mitigation:
  - Suppress README-missing findings when `len(parse_results) <= 1` or all parsed files are named `__init__.py`.
  - Extend `tests/test_analysis_edge_cases.py` to assert zero findings for empty, single-file, and init-only repositories.
- Verification: `python -m pytest tests/test_analysis_edge_cases.py -q --maxfail=1`
- Residual risk: Low; very small repositories and pure package skeletons will no longer receive README nudges until they exceed bootstrap size, which is an acceptable tradeoff for signal credibility.

## 2026-04-05 - AVS lazy-import policy violation detection (Issue #146)

- Risk ID: RISK-SIG-2026-04-05-146
- Component: src/drift/signals/architecture_violation.py, src/drift/config.py, src/drift/ingestion/ast_parser.py, src/drift/models.py
- Type: Signal quality (false negatives / policy coverage)
- Description: AVS did not surface explicit lazy-import policy violations for heavy runtime libraries imported at module level, even when repository policy mandated lazy imports.
- Trigger examples:
  - mickg/Real-Time Fortnite Coach: module-level heavy import in perception detector path.
  - Similar ML/runtime-sensitive repositories with documented lazy-import conventions.
- Impact: Missed policy-level architecture findings, lower trust in AVS for enforcement-oriented workflows.
- Mitigation:
  - Added configurable `policies.lazy_import_rules` (`from`, `modules`, `module_level_only`) in config model/schema.
  - Added AVS check producing dedicated `avs_lazy_import_policy` findings.
  - Added import scope metadata (`ImportInfo.is_module_level`) to distinguish module-level from local lazy imports.
  - Added regressions for detection and local-import non-detection.
- Verification: `pytest tests/test_architecture_violation.py tests/test_ast_parser.py tests/test_config.py -q --maxfail=1` (37 passed).
- Residual risk: Medium-low; pattern-based module matching may require repo-specific tuning for unusual import aliasing conventions.

## 2026-04-05 - MDS package-level lazy __getattr__ false-positive mitigation (Issue #144)

- Risk ID: RISK-SIG-2026-04-05-144
- Component: src/drift/signals/mutant_duplicates.py
- Type: Signal quality (false positives / severity calibration)
- Description: `mutant_duplicate` flagged identical package-level `__getattr__` implementations in `__init__.py` as high-severity duplicates, even when this pattern is an intentional lazy-submodule loading idiom (PEP 562).
- Trigger examples:
  - mickg/Real-Time Fortnite Coach: multiple package `__init__.py` files with deliberate lazy-loading `__getattr__` implementation.
  - Similar Python package repos that expose lazy imports via package `__getattr__`.
- Impact: False-positive duplicate findings, inflated high-severity noise, reduced trust in MDS prioritization.
- Mitigation:
  - Add explicit `__getattr__` + `__init__.py` heuristic (`_is_package_lazy_getattr`) and exclude these functions from MDS duplicate candidate collection.
  - Keep duplicate detection active for non-package `__getattr__` implementations.
  - Add dedicated regression tests for both suppression and non-suppression cases.
- Verification: `pytest tests/test_mutant_duplicates_edge_cases.py -q --maxfail=1` (23 passed).
- Residual risk: Medium-low; rare repositories may hide truly problematic package-level `__getattr__` duplication, but this is generally intentional API plumbing.

## 2026-04-05 - TPD negative assertion undercount calibration (Issue #143)

- Risk ID: RISK-SIG-2026-04-05-143
- Component: src/drift/signals/test_polarity_deficit.py
- Type: Signal quality (false positives / polarity misclassification)
- Description: `test_polarity_deficit` undercounted negative assertions in Python tests, especially for expressive assert styles (`assert not ...`, `assert ... is False/None`) and functional negative helpers (`pytest.raises(...)`, `pytest.fail(...)`).
- Trigger examples:
  - mickg/Real-Time Fortnite Coach: `tests/biometric` reported as nearly all-positive despite many negative-path checks.
  - Similar repositories using assert-style failure checks instead of only context-manager `pytest.raises` patterns.
- Impact: False-positive happy-path-only findings, severity miscalibration, and reduced trust in test polarity diagnostics.
- Mitigation:
  - Added AST-aware assert polarity classification for negative assert forms.
  - Added conservative regex fallback for assert text variants not cleanly captured by AST heuristics.
  - Added explicit negative call detection for functional `raises`/`fail` patterns.
  - Added targeted regressions for mixed-polarity suites and functional raises/fail calls.
- Verification: `pytest tests/test_test_polarity_deficit.py -q --maxfail=1` (3 passed).
- Residual risk: Medium-low; heuristic classification may still need tuning for rare domain-specific assert semantics.

## 2026-04-05 - PFS framework-surface error-handling severity calibration (Issue #142)

- Risk ID: RISK-SIG-2026-04-05-142
- Component: src/drift/signals/pattern_fragmentation.py
- Type: Signal quality (false positives / severity calibration)
- Description: pattern_fragmentation over-prioritized error-handling variance in framework-facing application layers (for example routers/pages/server orchestration), where heterogeneity is often intentional.
- Trigger examples:
  - mickg/Real-Time Fortnite Coach: backend/api/routers, src/ui/pages, mcp_server
  - Similar monorepos with mixed framework boundaries and endpoint orchestration code
- Impact: High-severity false-positive clustering, reduced trust in PFS ranking, and avoidable remediation churn.
- Mitigation:
  - Add framework-surface heuristic hints (API endpoint co-location + path/file tokens such as router/page/controller/server).
  - Apply conservative score dampening for error_handling findings in framework-facing modules.
  - Prevent default HIGH severity for this context while preserving finding emission and explainability metadata.
  - Add targeted regressions for dampened framework modules and unchanged core-module behavior.
- Verification: pytest tests/test_pattern_fragmentation.py -q --maxfail=1
- Residual risk: Medium-low; heuristic hints may under-rank rare high-risk fragmentation at framework boundaries, but findings are still emitted with explicit context metadata.

## 2026-04-05 - drift_score scope disambiguation in machine outputs (Issue #159)

- Risk ID: RISK-OUT-2026-04-05-159
- Components: src/drift/api_helpers.py, src/drift/api.py, src/drift/output/json_output.py, src/drift/commands/analyze.py, src/drift/commands/check.py, src/drift/commands/baseline.py, src/drift/baseline.py, src/drift/output/agent_tasks.py, src/drift/copilot_context.py, src/drift/negative_context_export.py
- Type: Output contract clarity / agent decision safety
- Description: `drift_score` appeared with one key name across different execution scopes (repo, diff, baseline-filtered, fix-plan context), enabling incorrect cross-context comparisons by agents and CI orchestrators.
- Mitigation:
  - Added sibling field `drift_score_scope` to affected machine-readable payloads.
  - Introduced centralized scope builder (`build_drift_score_scope`) and signal-scope label helper (`signal_scope_label`) for deterministic descriptors.
  - Wired scope descriptors into analyze/check JSON, scan API, baseline outputs, fix-plan API, brief/negative-context payloads, copilot context payload, and agent-tasks JSON.
- Verification: `pytest tests/test_json_output.py tests/test_output_golden.py tests/test_scan_diversity.py tests/test_brief.py tests/test_mcp_copilot.py tests/test_baseline.py::TestBaselineIO tests/test_baseline.py::TestBaselineDiff -q --maxfail=1` (117 passed).
- Residual risk: Low; legacy consumers that ignore unknown fields remain compatible, while consumers that compare scores now have explicit scope metadata.

## 2026-04-05 - MAZ, AVS, EDS signal quality improvements (Issues #148, #149, #150, #151)

- Risk ID: RISK-SIG-2026-04-05-148-151
- Components: src/drift/signals/missing_authorization.py, src/drift/signals/architecture_violation.py, src/drift/signals/explainability_deficit.py, src/drift/models.py, src/drift/api_helpers.py, src/drift/config.py
- Type: Signal quality (precision, severity calibration, location completeness, sub-signal attribution)
- Description: Four signal quality issues addressed in a single batch:
  - #148: MAZ flagged intentionally public endpoints (anon, public, security_txt, etc.) and dev-tool paths as missing authorization. Estimated precision ~20%.
  - #149: Multiple signals produced findings with null start_line, making agent-driven fix workflows impossible.
  - #150: AVS scan output conflated co-change coupling, circular deps, blast radius, and other sub-checks under a single "AVS" signal abbreviation with no rule_id disambiguation.
  - #151: EDS severity was not calibrated to actual function complexity/LOC — trivial getters received the same HIGH rating as complex algorithms.
- Mitigations:
  - #148: Expanded default maz_public_endpoint_allowlist (+25 patterns: public, anon, security_txt, pricing, manifest, etc.) and added dev-tool path heuristic (maz_dev_tool_paths config with 7 defaults).
  - #149: Added start_line=1 fallback in Finding.__post_init__ when file_path is set but start_line is None, ensuring all findings have machine-readable location data.
  - #150: Added explicit rule_id to each AVS sub-check (avs_policy_boundary, avs_upward_import, avs_circular_dep, avs_blast_radius, avs_zone_of_pain, avs_god_module, avs_unstable_dep, avs_co_change). Exposed rule_id in concise scan output format.
  - #151: Added LOC-based dampening (loc_factor = loc/30) and private function visibility dampening (0.7×) to EDS severity calculation.
- Verification: 1903+ tests passed (excluding 1 pre-existing MCP schema type failure). New regression tests for MAZ allowlist, dev-tool path, and non-dev-path behavior.
- Residual risk: Low; allowlist-based pattern matching may need further tuning for unusual naming conventions.

## 2026-04-05 - HSC OAuth endpoint URL false-positive mitigation (Issue #161)

- Risk ID: RISK-SIG-2026-04-05-161
- Component: src/drift/signals/hardcoded_secret.py
- Type: Signal quality (false positives / precision calibration)
- Description: HSC flagged OAuth endpoint constants (for example `TOKEN_URL = "https://oauth2.googleapis.com/token"`) as hardcoded secrets when variable names matched secret-like tokens.
- Trigger examples:
  - onyx-dot-app/onyx: `backend/ee/onyx/server/oauth/google_drive.py` with `TOKEN_URL` endpoint constant.
  - Similar integration code with `AUTH_URL`/`TOKEN_URL` endpoint literals.
- Impact: High-severity false positives, lower trust in HSC results, and avoidable remediation work.
- Mitigation:
  - Add URL-aware suppression for plain HTTP(S) endpoint literals without embedded credentials.
  - Keep detection active for URLs with userinfo credentials (`username`/`password`) to avoid masking true secrets.
  - Add targeted regression tests for OAuth endpoint constants and credential-bearing URL literals.
- Verification: tests/test_hardcoded_secret.py (new Issue #161 regressions, suite green).
- Residual risk: Low; unusual credential encodings outside URL userinfo remain heuristic-driven.

## 2026-04-05 - HSC error-message constant false-positive mitigation (Issue #163)

- Risk ID: RISK-SIG-2026-04-05-163
- Component: src/drift/signals/hardcoded_secret.py
- Type: Signal quality (false positives / precision calibration)
- Description: HSC flagged natural-language error message constants (for example `_MAX_TOKENS_ERROR`) as hardcoded secrets because variable names matched secret-like tokens while the literal itself was plain-text guidance.
- Trigger examples:
  - langchain-ai/langchain: `_MAX_TOKENS_ERROR` in output parser module.
  - Similar repositories using UPPER_CASE `*_ERROR`/`*_WARNING`/`*_MESSAGE` constants.
- Impact: High-severity false positives, triage noise, reduced trust in HSC output.
- Mitigation:
  - Added message-constant suppression for variable suffixes `_ERROR`, `_WARNING`, `_MESSAGE` when the literal matches natural-language message characteristics.
  - Preserved higher-confidence detection order (known token prefixes and credential-bearing URLs are evaluated before suppression).
  - Added regression test in `tests/test_hardcoded_secret.py` for `_MAX_TOKENS_ERROR` style constants.
- Verification: `python -m pytest tests/test_hardcoded_secret.py -q --maxfail=1`
- Residual risk: Low; intentional misnaming of real credentials as message constants is rare, and high-confidence token-prefix checks still trigger before suppression.

## 2026-04-05 - MAZ documented public-safe publishable-key severity downgrade (Issue #162)

- Risk ID: RISK-SIG-2026-04-05-162
- Component: src/drift/signals/missing_authorization.py
- Type: Signal quality (severity calibration / false-positive reduction)
- Description: MAZ emitted HIGH severity for intentionally public-safe publishable-key endpoints where no authorization is expected by design.
- Trigger examples:
  - onyx-dot-app/onyx: `get_stripe_publishable_key` reported as MAZ HIGH despite explicit public-safe rationale in code documentation.
  - Similar endpoint families: publishable/public client key retrieval routes.
- Impact: Over-prioritized findings, reduced analyst trust, and avoidable remediation churn.
- Mitigation:
  - Add conservative public-safe heuristic for MAZ severity dampening.
  - Require both conditions for LOW downgrade: endpoint name marker (`publishable/public key`) + explicit function docstring.
  - Keep finding emitted (no suppression) and expose `public_safe_documented` metadata for explainability.
  - Add regression tests for downgraded documented case and non-documented HIGH case.
- Verification: tests/test_missing_authorization.py (new Issue #162 regressions).
- Residual risk: Medium-low; semantic naming/docstring heuristics may still need repository-specific tuning for edge cases.

## 2026-04-05 - AVS tiny foundational module over-severity recalibration (Issue #153)

- Risk ID: RISK-SIG-2026-04-05-153
- Component: src/drift/signals/architecture_violation.py
- Type: Signal quality (severity calibration / false positives)
- Description: AVS Zone-of-Pain scoring emitted HIGH findings for tiny, intentionally stable foundational modules (for example logger/base adapters) without sufficient coupling evidence.
- Trigger examples:
  - fastapi/fastapi: tiny foundation modules reported as "Zone of Pain" with HIGH severity.
  - Typical profile: low instability, high distance, small file size, low structural footprint.
- Impact: Over-prioritization of low-actionability findings, reduced trust in AVS severity guidance.
- Mitigation:
  - Add tiny-foundational dampening in Zone-of-Pain scoring (`line_count <= 20`, `entity_count <= 2`, `ce <= 1`).
  - Require stronger coupling evidence for HIGH (`ca >= 6` or `ca >= 4 and ce >= 2`).
  - Emit explainability metadata (`tiny_foundational_dampened`, `has_high_risk_evidence`, `line_count`, `entity_count`).
  - Add regression tests covering dampened tiny modules and strong-evidence HIGH cases.
- Verification: tests/test_architecture_violation.py (19 passed, includes new Issue #153 regressions).
- Residual risk: Medium-low; heuristics may still need profile tuning for unusually dense tiny modules.

## 2026-04-05 - DCA package public API false-positive mitigation (Issue #152)

- Risk ID: RISK-SIG-2026-04-05-152
- Component: src/drift/signals/dead_code_accumulation.py
- Type: Signal quality (false positives / recall balance)
- Description: DCA treated public exports in package-layout framework/library repositories as dead code when symbols are externally consumed but not internally imported.
- Trigger examples:
  - fastapi/applications.py and related package modules with externally used public symbols.
  - Aggregate finding title: "N potentially unused exports" in framework API files.
- Impact: High false-positive rate, reduced trust in DCA remediation guidance.
- Mitigation:
  - Add package-layout heuristic that suppresses dead-export reporting for likely public API modules.
  - Keep internal/private path tokens in scope to preserve internal dead-code detection.
  - Add dedicated regression tests for both suppression and internal-path coverage.
- Verification: tests/test_dead_code_accumulation.py (7 passed, including new Issue #152 regressions).
- Residual risk: Medium-low; path-based heuristics may still under-report edge-case internal modules in package roots.

## 2026-04-04 - MCP stdio deadlock hardening on Windows

- Risk ID: RISK-MCP-2026-04-04-STDIO
- Component: src/drift/mcp_server.py, src/drift/analyzer.py, src/drift/api.py, src/drift/incremental.py, src/drift/ingestion/git_history.py, src/drift/pipeline.py, src/drift/signals/exception_contract_drift.py
- Type: Runtime availability and transport safety
- Description: MCP tool calls could hang permanently on Windows when subprocesses inherited server stdin handles or when heavy C-extension modules were first imported from worker threads after event-loop startup.
- Trigger examples:
  - `subprocess.run(...)` without `stdin=subprocess.DEVNULL` inside MCP-invoked paths.
  - First-time lazy import of heavy dependencies (for example numpy/torch/faiss) during `asyncio.to_thread` execution.
- Impact: Tool invocation stalls, session instability, and reduced trust because MCP responses do not complete.
- Mitigation:
  - Add `stdin=subprocess.DEVNULL` to affected subprocess calls across analyzer/API/ingestion/signal paths.
  - Ensure MCP tools remain async and return structured error envelopes on exceptions.
  - Add eager imports before `mcp.run()` to avoid loader-lock deadlocks during threaded execution.
- Verification: tests/test_mcp_hardening.py, tests/test_nudge.py, quick no-smoke pytest suite.
- Residual risk: Low; remaining risk is limited to future regressions where new subprocess calls omit explicit stdin handling.

## 2026-04-03 - Parse I/O resilience and malformed trend history hardening

- Risk ID: RISK-ING-2026-04-03-RESILIENCE
- Component: src/drift/ingestion/ast_parser.py, src/drift/ingestion/ts_parser.py, src/drift/signals/_utils.py, src/drift/trend_history.py, src/drift/commands/trend.py
- Type: Ingestion robustness and result continuity
- Description: Transient file-system race conditions (file removed between discovery and parse) and malformed trend snapshots could raise unhandled exceptions or break CLI rendering.
- Trigger examples:
  - `FileNotFoundError` / `PermissionError` while reading discovered Python/TypeScript files.
  - History entries without numeric `drift_score` or missing `timestamp` fields.
- Impact: Analyzer interruption, reduced reproducibility, and unstable user feedback under non-deterministic file-system conditions.
- Mitigation:
  - Parse paths now return structured `ParseResult.parse_errors` on `OSError` instead of propagating exceptions.
  - Trend context and trend CLI now filter malformed snapshots and continue with valid entries.
  - TypeScript parse helper degrades cleanly when parser dependencies are unavailable and logs debug details for unexpected parser failures.
- Verification: tests/test_parse_file_resilience.py, tests/test_malformed_history.py, tests/test_brief.py.
- Residual risk: Low; malformed historical data is skipped, so derived trend depth may be lower than raw snapshot count.

## 2026-04-03 - PFS/NBV copilot-context actionability upgrade (Issue #125)

- Risk ID: RISK-SIG-2026-04-03-125
- Component: src/drift/signals/pattern_fragmentation.py, src/drift/signals/naming_contract_violation.py
- Type: Signal remediation quality (actionability / trust)
- Description: PFS and NBV remediation text was too generic for agent execution and lacked concrete location anchors.
- Trigger examples:
  - PFS: "Consolidate to the dominant pattern" without exemplar or line-level deviation refs.
  - NBV: generic "add missing behaviour" without contract-specific implementation direction.
- Impact: Higher manual triage effort, reduced confidence in AI-context guidance, delayed remediation.
- Mitigation:
  - PFS fix now includes canonical exemplar `file:line` and concrete deviation references.
  - NBV fix now includes `file:line` and prefix-specific suggestion (`validate_/check_`, `ensure_`, `is_/has_`, etc.).
- Verification: tests/test_pattern_fragmentation.py, tests/test_naming_contract_violation.py.
- Residual risk: Low; signals remain heuristic and may still need repo-specific interpretation.

## 2026-07-18 - Security audit: P0–P2 hardening

- Risk ID: RISK-SEC-2026-07-18-AUDIT
- Component: api.py, cache.py, signals/PFS+AVS+MDS, ingestion/file_discovery.py, negative_context.py
- Type: Security hardening + false-positive reduction
- Description: Multi-vector audit implementing path traversal prevention, config validation, test-file FP guards, OS error handling, and metadata injection sanitization.
- Changes:
  - P0: SignalCache pickle→JSON serialization (CWE-502 deserialization fix, previous session)
  - P0: _get_changed_files_from_git() returns None on failure with warning (previous session)
  - P1: _warn_config_issues() called after every DriftConfig.load() in scan/diff/fix_plan/nudge/negative_context
  - P1: Path sandbox validation for baseline_file and config_file parameters (CWE-22)
  - P2: is_test_file() guard added to PFS, AVS, MDS signals
  - P2: try/except OSError in file_discovery.py glob/stat/is_file operations
  - P2: _sanitize() strips control chars from metadata before f-string embedding in negative_context
- Verification: 1581 tests passed, mypy clean, ruff clean.
- Residual risk: Low; test-file guard is defense-in-depth (default exclude already covers most cases).

## 2026-04-03 - CSV output formatter (Issue #14)

- Risk ID: RISK-OUT-2026-04-03-014
- Component: src/drift/output/csv_output.py + CLI output format routing
- Type: Output channel integrity and consumer compatibility
- Description: New CSV serializer could introduce unstable ordering or malformed escaping, reducing trust in machine exports.
- Trigger examples: quoted titles, commas in title text, missing file/line values.
- Impact: Downstream ingestion can break or produce inconsistent triage tables.
- Mitigation: Use Python `csv` module, deterministic sorting key, and regression tests for header/order/escaping.
- Verification: tests/test_csv_output.py + tests/test_compat.py::TestOutputFormatAlias::test_csv_format_in_choices.
- Residual risk: Low; schema is intentionally minimal and additive.

## 2026-04-03 - DIA markdown slash-token FP reduction (Issue #121)

- Risk ID: RISK-DIA-2026-04-03-121
- Component: src/drift/signals/doc_impl_drift.py
- Type: Model quality (false positives)
- Description: DIA classified generic markdown slash tokens as missing directories.
- Trigger examples: async/, scan/, connectors/ in prose examples.
- Impact: Reduced signal credibility and remediation focus.
- Mitigation: Context-aware extraction with structural-keyword window and backtick-preserved refs.
- Verification: tests/test_dia_enhanced.py (new regression cases) + quick no-smoke suite pass.
- Residual risk: Low; uncommon prose phrasing without structural terms may still be filtered.
