# Risk Register

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
