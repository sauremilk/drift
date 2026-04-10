# Risk Register

## 2026-06-14 - ADR-039: Activate MAZ/PHR/HSC/ISD/FOE for Scoring

- Risk ID: RISK-SIGNAL-ACTIVATION-2026-06-14-039
- Component: `src/drift/config.py` (SignalWeights), `tests/fixtures/ground_truth.py`
- Type: Signal behavior change (report-only → scoring-active for 5 signals)
- Description: Five previously report-only signals are promoted to scoring-active with conservative weights: MAZ=0.02, PHR=0.02, HSC=0.01, ISD=0.01, FOE=0.005. This adds +0.065 to the total signal weight budget (~6.5% of composite score). Finding detection logic is unchanged — only the weight (and therefore score impact) changes from 0.0 to non-zero.
- Severity: Low to Medium
- Likelihood: Low (all signals were already emitting findings in report-only mode; only score contribution changes)
- Mitigation:
  - Conservative weights chosen based on signal maturity and existing precision data
  - All 5 signals have ground-truth fixture coverage (ISD: 5 new, MAZ: 1 TN, HSC: 6, FOE: 3, PHR: 17)
  - Precision/recall validated via `test_precision_recall.py` — all fixtures pass
  - Existing FP-reduction mechanisms (CLI-path fence, drift:ignore-security, barrel-file detection, env-template suppression) remain active
  - Score comparability: baseline diff via `drift_diff` recommended after activation
  - Weights are configurable via `drift.yaml` — users can revert individual signals to 0.0
- Residual risk: Low. Primary residual risk is minor score inflation for repositories that trigger multiple newly-scoring signals simultaneously. Conservative weights and per-signal configurability bound the impact. No detection logic changes means no new FP/FN modes beyond those already documented.

## 2026-06-01 - ADR-042: Schema Evolution and Finding-ID Promotion

- Risk ID: RISK-OUTPUT-2026-06-01-042
- Component: `src/drift/output/json_output.py`, `src/drift/api_helpers.py`, `src/drift/api/explain.py`, `src/drift/models.py`, `src/drift/mcp_server.py`
- Type: Output schema version bump (additive, minor) + new output field + explain input extension
- Description: Schema version unified from split "1.1" (CLI) / "2.0" (API) to "2.1". All output channels (JSON, SARIF, API) gain a `finding_id` field (16-char SHA256 fingerprint). `drift explain` and MCP `drift_explain` now accept finding fingerprints for finding-level drill-down, triggering a full analysis scan.
- Severity: Low
- Likelihood: Low (additive changes only; no fields removed or renamed)
- Mitigation:
  - Schema version bump follows established minor-version convention (additive fields only)
  - `finding_id` is deterministic and content-based — no randomness or state dependency
  - Fingerprint-based explain reuses existing `analyze_repo()` pipeline with same security boundaries
  - Existing consumers of `schema_version` "1.1" or "2.0" may need test updates but face no runtime breakage (new fields are ignored by lenient parsers)
  - `drift.output.schema.json` enables machine-verifiable contract validation
  - Regression tests updated for new schema version
- Residual risk: Low. Consumers with strict schema validation against "1.1" or "2.0" will reject "2.1" output until updated. This is intentional — the version bump signals the schema change. Fingerprint-based explain has the same performance cost as a normal scan.

## 2026-04-10 - TypeScript signal expansion and parser/output wiring hardening

- Risk ID: RISK-TS-SIGNALS-2026-04-10
- Component: `src/drift/signals/type_safety_bypass.py`, `src/drift/signals/naming_contract_violation.py`, `src/drift/signals/ts_architecture.py`, `src/drift/ingestion/ts_parser.py`, `src/drift/output/agent_tasks.py`, `src/drift/models.py`
- Type: New signal + signal behavior change + ingestion/output path adjustments
- Description: TypeScript analysis coverage was expanded with a dedicated type-safety-bypass detector and additional TS naming/architecture checks. Parser extraction and agent-task output shaping were adjusted to surface the new findings consistently.
- Severity: Medium
- Likelihood: Low to Medium
- Mitigation:
  - New focused TS fixture suites for export detection, naming consistency, React hooks, and type-safety bypass
  - Golden cache artifacts updated for deterministic corpus behavior
  - Pre-commit lint gate enforced and fixed for touched files
- Residual risk: Medium-Low. Main residual risk is precision drift in heterogeneous TS codebases with mixed naming conventions or intentional casts.

## 2026-04-13 - ADR-036/037/038: AVS/DIA/MDS FP-Reduction

- Risk ID: RISK-SIGNAL-2026-04-13-036-037-038
- Component: `src/drift/signals/architecture_violation.py`, `src/drift/signals/doc_impl_drift.py`, `src/drift/signals/mutant_duplicates.py`, `src/drift/config.py`
- Type: Signal behavior change (FP-reduction heuristics) + new config fields
- Description: Three signals receive precision hardening: AVS moves `models/` to Omnilayer and adds configurable `omnilayer_dirs`; DIA adds configurable `extra_auxiliary_dirs`; MDS adds name-token similarity, protocol-method skip, and thin-wrapper dampening. All changes aim to reduce false positives without degrading recall.
- Severity: Low to Medium
- Likelihood: Low (conservative defaults; all changes bounded by narrow heuristics)
- Mitigation:
  - AVS: `models` Omnilayer is reversible via config; current default covers >80% of observed repos
  - DIA: extra_auxiliary_dirs starts empty — no default behavior change
  - MDS: name component is only 10% weight; protocol set is narrow; thin-wrapper gate is LOC + Call-count
  - Ground-truth fixtures cover all new behaviors (6 TN fixtures)
  - Precision/recall baseline validated via `test_precision_recall.py`
- Residual risk: Low. Primary residual risk is MDS protocol-method FN in rare cases where protocol implementations contain genuinely duplicated non-trivial logic.

## 2026-04-12 - ADR-035: Per-Repository Signal Calibration

- Risk ID: RISK-SIGNAL-2026-04-12-035
- Component: `src/drift/calibration/`, `src/drift/signals/phantom_reference.py`, `src/drift/task_spec.py`, `src/drift/commands/calibrate.py`, `src/drift/commands/feedback.py`
- Type: Signal behavior adaptation (repo-scoped calibration) + new local input path (`data/negative-patterns/`)
- Description: Drift now applies repository-scoped precision hardening for selected signal patterns (initially PHR) using persisted calibration snapshots derived from user feedback and benchmark traces.
- Severity: Medium
- Likelihood: Low to Medium (calibration is bounded and confidence-weighted, but mis-calibration can suppress valid findings)
- Mitigation:
  - Calibration operates per repository fingerprint, not globally
  - Conservative default when calibration data is missing or stale
  - Signal-level guardrails cap score dampening and prevent full suppression from a single sample
  - Tests cover calibration loading, persistence, and PHR behavior under calibrated/un-calibrated paths
  - Audit/benchmark artifacts are updated alongside calibration changes (`docs/STUDY.md`, evidence JSON)
- Residual risk: Medium-Low. Main residual risk is repository-local false negatives if repeated incorrect feedback is provided; bounded dampening and fallback defaults reduce blast radius.

## 2026-04-12 - ADR-034: Causal Attribution via Git Blame

- Risk ID: RISK-INGESTION-2026-04-12-034
- Component: `src/drift/ingestion/git_blame.py`, `src/drift/attribution.py`, `src/drift/pipeline.py`
- Type: New subprocess input path (git blame) + additive output field (Finding.attribution)
- Description: Opt-in enrichment that invokes `git blame --porcelain` per analyzed file to attribute findings to commits, authors, and branches. Subprocess execution introduces a new trust boundary (drift ↔ git CLI). Author data from git history is surfaced in JSON/SARIF/Rich output.
- Severity: Low
- Likelihood: Low (opt-in, disabled by default; subprocess uses same git binary as existing git_history.py)
- Mitigation:
  - Feature disabled by default (`attribution.enabled: false`)
  - Per-file timeout (3s) prevents blame on slow/large files from blocking analysis
  - ThreadPoolExecutor capped at 4 workers; in-memory LRU cache (500 entries)
  - No `shell=True` in subprocess calls; arguments are explicit
  - File paths sourced from existing ingestion pipeline (already validated)
  - Branch hint extraction via deterministic regex on merge commit messages only
- Residual risk: Low. Author/email data in blame output could be spoofed in git history (inherent git limitation, not a drift-specific risk). Performance on very large repos with thousands of files may require increasing timeout or disabling attribution.

## 2026-04-09 - ADR-029: Preflight-Diagnose und Markdown-Report-Export

- Risk ID: RISK-OUTPUT-2026-04-09-029
- Component: `src/drift/preflight.py`, `src/drift/output/markdown_report.py`, `src/drift/finding_rendering.py`
- Type: Neuer Output-Pfad (additiv, non-breaking)
- Description: Die Analyseausgabe wird um einen strukturierten Preflight-Diagnosepfad und einen Markdown-Report erweitert. Ziel ist bessere Handlungsfaehigkeit fuer Review- und Agent-Workflows ohne Aenderung bestehender JSON-Schemas.
- Trigger: Aufrufe, die den neuen Markdown-/Preflight-Ausgabepfad aktivieren.
- Impact: Niedrig bis mittel. Falsche oder missverstaendliche Zusammenfassungen koennen die Priorisierung von Folgemaassnahmen beeinflussen, ohne den zugrunde liegenden Finding-Datensatz zu veraendern.
- Mitigation:
  - Additiver Kanal; bestehende JSON- und CLI-Standardausgaben bleiben erhalten
  - Deterministische Ableitung aus vorhandenen Findings und Metadaten
  - Testabdeckung fuer Rendering, Tool-Metadaten und semantische Advisory-Regeln
- Residual risk: Niedrig. Hauptrestrisiko liegt in Darstellungsinterpretation, nicht in der Kernanalyse oder Score-Berechnung.

## 2026-04-08 - ADR-027: Finding-Status fuer Suppression-Transparenz

- Risk ID: RISK-OUTPUT-2026-04-08-027
- Component: `src/drift/models.py`, `src/drift/suppression.py`, `src/drift/pipeline.py`, `src/drift/output/json_output.py`
- Type: Output schema extension + lifecycle transparency (additive, non-breaking)
- Description: Inline-Suppressions werden nicht mehr nur gezaehlt, sondern als expliziter Finding-Status (`suppressed`) modelliert und separat im JSON ausgegeben (`findings_suppressed`). Ziel ist die Trennung von real behobenen und nur unterdrueckten Findings.
- Trigger: `drift analyze`/`drift check` JSON-Ausgabe bei vorhandenen `drift:ignore` Kommentaren.
- Impact: Additiv. Bestehende `findings`-Consumer bleiben funktionsfaehig; neue Felder verbessern Audierbarkeit und reduzieren False-Negative-Wahrnehmung.
- Mitigation:
  - Statusfelder sind optional und additive (`schema_version` 1.1)
  - Primarliste `findings` bleibt unveraendert fuer Rueckwaertskompatibilitaet
  - Regressionstests fuer Suppression-Markierung und JSON-Serialisierung
- Residual risk: Niedrig. Consumer, die strikt auf exakte Payload-Groesse optimieren, sehen mehr Felder und sollten ggf. kompaktes Format verwenden.

## 2026-04-08 - ADR-026: A2A Agent Card and HTTP Serve Endpoint

- Risk ID: RISK-SERVE-2026-04-08-026a
- Component: `src/drift/serve/app.py`, `src/drift/serve/a2a_router.py`
- Type: New HTTP input/output path (network-accessible trust boundary)
- Description: `drift serve` exposes analysis capabilities over HTTP without authentication. Any client that can reach the bind address can invoke analysis on any local directory the OS user has read access to.
- Severity: Medium
- Likelihood: Low (default localhost-only; network exposure requires explicit `--host 0.0.0.0`)
- Mitigation:
  - Default bind to `127.0.0.1` — not reachable from network without explicit opt-in
  - Documentation warns about production exposure requiring reverse proxy with auth
  - No sensitive credentials stored or processed by the serve endpoint
- Residual risk: Low. Localhost-only default limits attack surface to local processes. Users deploying on `0.0.0.0` accept responsibility for network-level access control.

- Risk ID: RISK-SERVE-2026-04-08-026b
- Component: `src/drift/serve/a2a_router.py`
- Type: Input validation (path traversal prevention)
- Description: A2A JSON-RPC requests include a `path` parameter specifying which repository to analyze. Insufficient validation could allow path traversal to analyze or probe arbitrary filesystem directories.
- Severity: Medium
- Likelihood: Low (requires network access to the serve endpoint)
- Mitigation:
  - `_validate_repo_path()` normalizes via `os.path.realpath(os.path.normpath(path))`
  - Validates `os.path.isdir()` — rejects non-existent and non-directory paths
  - Resolved path is used for all downstream API calls (no raw user input forwarded)
  - ValueError raised with descriptive message on invalid paths
- Residual risk: Low. Validation prevents traversal; attacker can only analyze directories the OS user can read (same as running `drift` directly). Combined with localhost-only default, risk is very low.

## 2026-04-08 - Ingestion dedup + signal factory active_signals pass-through + git history cache

- Risk ID: RISK-INGESTION-2026-04-08-DEDUP
- Component: `src/drift/ingestion/file_discovery.py`, `src/drift/signals/base.py`, `src/drift/pipeline.py`
- Type: Ingestion correctness fix + signal factory optimization + performance cache
- Description: Three related changes applied together:
  1. **`file_discovery.py` (ingestion):** `include` patterns are now deduped via `dict.fromkeys` before glob iteration. Previously a file matching multiple patterns could be discovered and appended multiple times, producing duplicate `FileInfo` entries and inflated finding counts. Lazy `glob()` iterator replaces `list(glob())` to avoid materializing all matches at once; `relative_to()` result reused instead of called twice.
  2. **`signals/base.py` (signals):** `create_signals()` gains an `active_signals: set[str] | None` parameter so callers can pre-filter signals before instantiation. A `_SIGNAL_TYPE_VALUE_CACHE` avoids repeated probe-instantiation for the signal-type lookup on cached code paths.
  3. **`pipeline.py`:** `fetch_git_history()` adds a short-lived in-process LRU cache (TTL 120 s, max 16 entries, keyed by HEAD SHA + parameters) to avoid redundant `git log` parsing across rapid consecutive scans. `SignalPhase` passes `active_signals` to the factory directly with a backward-compatible fallback for custom `signal_factory` implementations.
- FP risk: Low. Dedup prevents double-processing; if a legitimate file happened to be discovered twice it was already a pre-existing FP source, not a TP. Active-signals pre-filtering uses same `signal_type.value` values that were already filtered downstream.
- FN risk: Low. Dedup cannot suppress files that match at least one pattern once. The cache is keyed on HEAD SHA + all analysis parameters; any repo or config change invalidates the cache entry.
- Mitigation:
  - New tests in `tests/test_pipeline_components.py` cover cache hit/miss and HEAD-change invalidation.
  - Full test suite passes; ruff + mypy clean.
- Residual risk: Very low. Cache is process-local and bounded; no persistent state. Dedup is idempotent. Backward-compat fallback ensures custom signal factories continue to work.

## 2026-04-11 - ADR-024: Machine-Readable Next-Step Contracts

- Risk ID: RISK-OUTPUT-2026-04-11-024
- Component: `src/drift/api.py`, `src/drift/api_helpers.py`, `src/drift/mcp_server.py`
- Type: Output schema extension (additive, non-breaking)
- Description: ADR-024 introduces machine-readable next-step contracts to reduce agent hallucinations in tool-call chains. Three fields added to every agent-oriented API response:
  - `next_tool_call`: `{tool: str, params: dict}` — primary recommended action. Null when no action needed.
  - `fallback_tool_call`: `{tool: str, params: dict}` — alternative if primary fails. Null when not applicable.
  - `done_when`: Predicate string describing the termination condition for the current workflow step.
  - MCP session enrichment injects `session_id` into contract params via `setdefault`.
  - `_error_response` gains optional `recovery_tool_call` for recoverable errors.
- Trigger: All API calls returning agent-oriented responses (scan detailed, diff, fix_plan, nudge, brief, negative_context), plus MCP session_start.
- Impact: Additive only — `schema_version` remains "2.0". Existing `agent_instruction` and `recommended_next_actions` fields preserved. No scoring, signal, or ingestion logic affected. Backward-compatible: consumers ignoring new fields are unaffected.
- Mitigation:
  - 9 new tests in `TestNextStepContract` class (tests/test_scan_diversity.py)
  - Contract shape validator `_assert_contract_shape()` enforces structural invariants
  - Full test suite passes (2147 passed); ruff + mypy clean
  - `done_when` is advisory text, not code — no injection or execution risk
  - `_tool_call()` helper centralizes descriptor construction
  - 8 `DONE_*` constants ensure predicate consistency across endpoints
- Residual risk: Very low. All contract content is deterministic, derived from existing response state. Agents may ignore contracts — no enforcement, no side effects if misinterpreted.

## 2026-04-08 - ADR-023: Canonical Examples in Agent-Output (fix_plan + brief)

- Risk ID: RISK-OUTPUT-2026-04-08-023
- Component: `src/drift/guardrails.py`, `src/drift/api_helpers.py`
- Type: Output schema extension (additive, non-breaking)
- Description: ADR-023 surfaces existing positive-reference data through two new additive fields:
  - `Guardrail.preferred_pattern`: Carries `NegativeContext.canonical_alternative` through to brief guardrails and prompt block (previously lost during NC→Guardrail transformation).
  - `canonical_refs` list in fix_plan task dicts: Extracts `canonical_exemplar` from Finding metadata (e.g. PFS file:line refs) and `canonical_alternative` from NegativeContext items. Capped at 3 refs per task.
  - `guardrails_to_prompt_block()`: Emits optional `PREFERRED:` line after each constraint when preferred_pattern is non-empty.
- Trigger: `brief()` and `fix_plan()` API calls; MCP `drift_brief` and `drift_fix_plan` tools (JSON passthrough).
- Impact: Additive only — `schema_version` remains "2.0". No existing fields changed. Empty defaults (`""` / `[]`) when source data unavailable. No scoring, signal, or ingestion logic affected.
- Mitigation:
  - 4 new tests in `tests/test_brief.py` (28 total in class)
  - 4 new tests in `tests/test_batch_metadata.py` (56 total)
  - Full test suite passes; ruff + mypy clean
  - canonical_refs capped at 3 per task (token budget)
  - preferred_pattern truncated to 200 chars (injection prevention)
- Residual risk: Very low. All new data is derived from existing analysis artifacts. Comment-prefix stripping is deterministic and bounded. No new computation paths or external data sources.

## 2026-04-09 - ADR-021: Batch-Dominant Fix-Loop Orchestration (Agent Instruction Alignment)

- Risk ID: RISK-OUTPUT-2026-04-09-021
- Component: `src/drift/api.py`, `src/drift/mcp_server.py`
- Type: Agent instruction text change (output channel, non-breaking)
- Description: ADR-021 resolves contradictory `agent_instruction` texts that caused agents to fall back to per-file verification even when batch capabilities (ADR-020) exist. Changes:
  - `_scan_agent_instruction()`: Threshold-based branching (>20 findings → batch-first guidance with max_tasks=20, ≤20 → nudge-based per-fix workflow)
  - `_fix_plan_agent_instruction()`: Non-batch path recommends nudge (not diff) for inner loop; batch path adds nudge guidance between edits
  - Diff `_agent_hint`: "improved" and "no change" cases now reference batch_eligible groups and nudge
  - Nudge `agent_instruction`: References new inner-loop/outer-loop model (nudge = inner, diff = outer)
  - MCP `_BASE_INSTRUCTIONS`: Removed "do not batch" from nudge tool description; added explicit FEEDBACK LOOP ROLES section; batch step 2 now mentions nudge between edits
- Trigger: All API endpoints that return `agent_instruction` fields
- Impact: Only plaintext `agent_instruction` strings changed — `schema_version` remains "2.0". No structural, scoring, or field-level changes.
- Mitigation:
  - 5 new tests in `tests/test_batch_metadata.py` (24 total)
  - Full test suite passes (2083 passed, 168 skipped)
  - ruff + mypy clean
  - Contradictions verified eliminated via grep (zero matches for "do not batch" in MCP, zero matches for "After each file change.*drift_diff" in api.py)
- Residual risk: Very low. Agent instruction texts are non-binding recommendations that guide but do not constrain agent behavior. No scoring, schema, or functional logic changed.

## 2026-04-08 - Agent Repair Workflow Quick Wins (V-3a/V-5/V-6/V-8a/V-13)

- Risk ID: RISK-OUTPUT-2026-04-08-021
- Component: `src/drift/api.py`, `src/drift/output/agent_tasks.py`, `src/drift/api_helpers.py`, `src/drift/models.py`, `src/drift/mcp_server.py`
- Type: Output schema extension + MCP tool parameter addition (additive, non-breaking)
- Description: Six Quick Win improvements for agent repair workflow effectiveness:
  - V-3c: Baseline-warming step added to Fix-Loop Protocol in MCP system prompt
  - V-5: `finding_count_by_signal` dict added to scan response (Counter over ALL findings pre-truncation)
  - V-6: `expected_score_delta` field added to AgentTask model, populated from `finding.score_contribution`, exposed in `_task_to_api_dict()`
  - V-8a: Negative context `max_items` increased from 3 to 5 for richer anti-pattern guidance
  - V-3a: `signals`/`exclude_signals` params added to `nudge()` and MCP `drift_nudge` — post-hoc result filtering (score unaffected)
  - V-13: `dependency_depth` metadata via BFS in `_compute_dependencies()` — depth 0 = no deps, depth N = max(dep depths)+1, -1 = cycle
- Trigger: scan, fix_plan, or nudge API calls
- Impact: Schema additive only — `schema_version` remains "2.0". No existing fields removed or renamed.
- Mitigation:
  - All new fields are optional/additive (backward-compatible)
  - 7 new tests added to `tests/test_batch_metadata.py` (19 total)
  - Full test suite passes (2085 passed, 168 skipped)
  - ruff + mypy clean
- Residual risk: Low. Nudge signal filtering is display-only — score/direction always reflect full analysis.

## 2026-04-07 - ADR-020: Agent Fix-Loop Batch Metadata (Output Schema Extension)

- Risk ID: RISK-OUTPUT-2026-04-07-020
- Component: `src/drift/output/agent_tasks.py`, `src/drift/api.py`, `src/drift/api_helpers.py`
- Type: Output schema extension (additive, non-breaking)
- Description: ADR-020 adds batch metadata fields to fix_plan and diff responses to reduce agent fix-loop latency. Changes include:
  - `_inject_batch_metadata()` in agent_tasks.py computes fix-template equivalence classes
  - `_task_to_api_dict()` exposes 4 new fields: `batch_eligible`, `pattern_instance_count`, `affected_files_for_pattern`, `fix_template_class`
  - `diff()` gains `signals`/`exclude_signals` params, `resolved_count_by_rule`, `suggested_next_batch_targets`
  - `fix_plan()` gains `remaining_by_signal`, context-dependent `agent_instruction`
  - `scan()` gains `total_finding_count`
- Trigger: Any fix_plan, diff, or scan API call
- Impact: Schema additive only — no existing fields removed or renamed. `schema_version` remains "2.0".
- Mitigation:
  - All new fields are optional/additive (backward-compatible)
  - 12 dedicated tests in `tests/test_batch_metadata.py`
  - Existing test suite (865+ tests) passes without modifications
- Residual risk: Low. `_UNIFORM_TEMPLATE_SIGNALS` set may need expansion as new signals are added.

## 2026-04-07 - PFS FTA v1: RETURN_PATTERN extraction (MCS-1 recall fix)

- Risk ID: RISK-SIG-2026-04-07-193
- Component: `src/drift/ingestion/ast_parser.py` (`_process_function`, `_fingerprint_return_strategy`)
- Type: Signal quality (FTA v1 — 1 SPOF, mitigated)
- Description: FTA on pfs_002 mutation identifies a single SPOF: no `PatternCategory.RETURN_PATTERN` enum value and no return-strategy extraction path in `_process_function()`. This causes PFS recall = 0.5 (pfs_002 undetected in mutation benchmark).
  - MCS-1 (SPOF, RPN 112→20): `PatternCategory.RETURN_PATTERN` added to enum; `_fingerprint_return_strategy()` classifies per-function return exits into strategy labels (`return_none`, `raise`, `return_tuple`, `return_dict`, `return_value`); emits `PatternInstance` when ≥2 distinct strategies found. **Mitigated.**
- Trigger: `drift analyze` on repo with module containing functions using divergent return conventions (None vs raise vs tuple).
- Impact: PFS recall drops to 0.5; return-strategy fragmentation invisible to users.
- Mitigation (implemented, 2026-04-07):
  - `PatternCategory.RETURN_PATTERN` enum value in `src/drift/models.py`
  - `_fingerprint_return_strategy()` in `src/drift/ingestion/ast_parser.py`
  - Extraction call in `_process_function()` after API endpoint block
  - Queue-based walk excludes nested function/class defs
- Verification:
  - `test_return_strategy_mutation_benchmark_scenario` — exact pfs_002 scenario
  - `test_return_strategy_multiple_strategies_detected` — basic extraction
  - `test_return_strategy_ignores_nested_functions` — nested-def isolation
  - `test_return_pattern_two_variants_detected` — PFS integration
  - `PFS_RETURN_PATTERN_TP` ground-truth fixture
- Residual risk: Low. FP risk for intentional return-overloading modules (get/get_or_raise patterns) — accepted as correct detection of diversity. Dynamic returns via callbacks remain FN (static analysis limitation).

## 2026-04-07 - SMS FTA v1: sms_001 Recall=0 (Benchmark-Fixture, 2 SPOFs, behoben)

- Risk ID: RISK-BENCH-2026-04-07-192
- Component: `scripts/_mutation_benchmark.py` (Benchmark-Fixture, kein Signal-Code)
- Type: Benchmark-Fixture-Defekt (FTA v1 — 2 SPOFs, beide behoben)
- Description: FTA auf `sms_001`-Mutation deckt zwei minimale Schnittmengen auf, die zusammen Recall=0 erklären:
  - MCS-1 (SPOF): Fixture injiziert ausschließlich stdlib-Imports (`ctypes`, `struct`, `mmap`, `ast`, `dis`, `multiprocessing`, `xml`). `_STDLIB_MODULES` filtert alle — kein Novel-Import → leere Findings-Liste. Das Signal funktioniert korrekt; der Fehler liegt in der falschen Fixture-Erwartung.
  - MCS-2 (SPOF): Alle Baseline-Dateien im Initial-Commit ohne explizites Datum → Timestamp „heute“ → `established_count = 0` von `len(parse_results) ≈ 25` → 10%-Guard feuert → `return []` vor jeder Analyse. Unabhängig von MCS-1, würde auch bei validen Third-Party-Imports feuern.
  - Common Cause: fehlende Datum-Spreizung im Corpus-Setup aktiviert beide Äste gleichzeitig.
- Trigger: `drift analyze --repo <tmp_repo> --format json --since 90` auf synthetischem Benchmark-Repo.
- Mitigation (implementiert, 2026-04-07):
  - MCS-1: `outlier_module.py` in separatem Recent-Commit mit `numpy`, `cffi`, `msgpack` überschrieben.
  - MCS-2: Initial-Commits auf Feb 2026 zurückdatiert via `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`.
- Verification:
  - Benchmark post-fix: `sms_001` detected = 1, recall = 100%, Gesamt-Recall 16/17 = 94%.
  - 2056/2056 Test-Suite grün.
  - `benchmark_results/mutation_benchmark.json` aktualisiert.
- Residual risk: Kein Restrisiko für diesen Defekt. Langfristig: Benchmark-Fixture-Validierungsprozess sollte sicherstellen, dass injizierte Imports gegen Signal-Filterlogik ge-cross-validated werden.

## 2026-04-07 - AVS FTA v1: co-change precision failure (3 primary MCS, 1 latent)

- Risk ID: RISK-SIG-2026-04-07-191
- Component: src/drift/signals/architecture_violation.py (`_check_co_change`)
- Type: Signal quality (FTA v1 — causal decomposition, 3 primary MCS, 1 latent MCS) — **MITIGATED**
- Description: FTA auf `avs_co_change`-Sub-Check deckt drei minimale Schnittmengen auf, die zusammen alle 10 Disputed-Fälle in der `drift_self`-Stichprobe erklären (precision_strict = 0.3, n=20, 2026-03-25):
  - MCS-1 (SPOF, RPN 144→24): Same-directory guard via `PurePosixPath.parent` comparison mit root-level Exception (`!= "."`) in `_check_co_change`. **Mitigated.**
  - MCS-2 (SPOF, RPN 60→10): `known` wird jetzt aus `filtered_prs` statt `parse_results` gebaut — konsistent mit Graph. **Mitigated.**
  - MCS-3 (RPN 120→30): `build_co_change_pairs` diskontiert Commits nach Dateizahl (`weight = 1.0 / max(1, len(files) - 1)`). Hard >20 cut bleibt als Belt-and-Suspenders. **Mitigated.**
  - MCS-4 (latent, RPN 48): `_DEFAULT_LAYERS` mappt `models` auf Layer 2 ohne Cross-Cutting-Ausnahme — potenziell irreführende `avs_upward_import`-Findings auf DTO-Pattern-Repos. **Unchanged — keine Evidenz.**
  - Common Causes: CC-1 (Filter-Inkonsistenz) behoben durch MCS-2 Fix; CC-2 (kein Namespace-Kontext) behoben durch MCS-1 Guard.
- Implementation: ADR-018 (proposed), 3 Code-Fixes, 4 Regressionstests (27/27 grün), 97/97 Precision-Recall grün.
- Regressionstests:
  - `test_co_change_same_directory_suppressed` (MCS-1)
  - `test_co_change_root_level_not_suppressed` (MCS-1 FN guard)
  - `test_co_change_test_source_pair_suppressed` (MCS-2)
  - `test_co_change_bulk_commits_discounted` (MCS-3)
- Residual risk: Niedrig. MCS-4 (latent, `models.py` Layer-Zuordnung) ohne Disputed-Evidenz bleibt unverändert. Bulk-Commit-Diskont-Kurve (`1/(n-1)`) kann nach breiterer Benchmark-Validierung kalibriert werden.

## 2026-04-07 - DIA FTA v2: deep false-positive reduction (6 minimal cut sets)

- Risk ID: RISK-SIG-2026-04-07-190
- Component: src/drift/signals/doc_impl_drift.py
- Type: Signal quality (FTA v2 — deep causal decomposition to 16 basis events, 6 MCS)
- Description: FTA v1 (3 cut sets) reduced DIA self-analysis from 10→9 FPs with precision 63%. FTA v2 performed proper NIST/NASA-grade decomposition, identifying 3 common causes (CC-1: flat regex `_PROSE_DIR_RE`, CC-2: missing undocumented-dir convention filter, CC-3: ADR `trust_codespans=True` bypass) and 6 minimal cut sets. Four targeted guards implemented:
  - P5 (MCS-4): Negative lookahead `(?!\w)` on `_PROSE_DIR_RE` — blocks `try/except`, `match/case`, `parent/tree`, multi-segment path decomposition, dotfile-path, and URL owner/repo extractions.
  - P3 (MCS-2): URL stripping via `_strip_urls()` before regex extraction — defense-in-depth against GitHub/registry URLs in plain text.
  - P6 (MCS-5): Dotfile prefix check `.{ref}` in `_ref_exists_in_repo()` — recognizes `.drift-cache` for ref `drift-cache`.
  - P1 (MCS-1): Auxiliary directory exclusion `_AUXILIARY_DIRS` frozenset — suppresses undocumented-dir findings for `tests/`, `scripts/`, `benchmarks/`, `docs/`, etc.
- Dead code removed: `_FALLBACK_DIR_RE` (defined but never referenced).
- Impact: DIA self-analysis findings 9→2 (−78%), ground truth auxiliary FPs eliminated.
- Verification:
  - 73/73 DIA unit tests green (15 new tests for P1/P3/P5/P6)
  - 97/97 precision/recall fixtures green
  - 2056/2056 full test suite green
  - Mutation benchmark DIA recall 3/3 = 100%
  - Self-analysis DIA: 2 remaining (1× ADR meta-doc `services/`, 1× non-standard `work_artifacts/`)
- Residual risk: Low. P5 negative lookahead only extracts terminal path segments (before whitespace/EOL), which may miss intermediate segments in rare prose. Acceptable because intermediate segments (e.g. `src` in `src/drift/`) are never the meaningful claim target.

## 2026-04-08 - DIA FTA v2 refinement: eliminate remaining 2 self-analysis FPs

- Risk ID: RISK-SIG-2026-04-08-191
- Component: src/drift/signals/doc_impl_drift.py, decisions/ADR-017-dia-false-positive-reduction.md
- Type: Signal quality (final FP elimination in self-analysis)
- Description: Two residual DIA FPs from FTA v2 remain on self-analysis:
  1. `services/` extracted from ADR-017 inline codespan (illustrative example, not architectural claim). Root cause: ADR scanning uses `trust_codespans=True`, which extracts example refs.
  2. `work_artifacts/` flagged as undocumented source dir (contains ad-hoc Python scripts, not a structured module). Root cause: not in `_AUXILIARY_DIRS`.
- Mitigation:
  - ADR-017: Illustrative directory references moved from inline codespans to fenced code block. DIA already correctly skips `block_code` tokens, so example refs are no longer extracted.
  - `_AUXILIARY_DIRS`: Extended with `artifacts` and `work_artifacts` entries to cover CI/build artifact and working directories — common conventions across projects.
- Impact: DIA self-analysis findings 2→0 (100% FP elimination on own repo).
- FN-risk: Negligible. Directories named `artifacts` or `work_artifacts` virtually never contain architecturally significant source modules. Fenced code block usage in ADRs for example paths is semantically correct and improves readability.
- Verification:
  - 76/76 DIA unit tests green (3 new regression tests)
  - 97/97 precision/recall fixtures green
  - 2056/2056 full test suite green
  - Self-analysis DIA: 0 findings

## 2026-04-07 - DIA false-positive reduction (FTA v1, 3 cut sets)

- Risk ID: RISK-SIG-2026-04-07-189
- Component: src/drift/signals/doc_impl_drift.py
- Type: Signal quality (false-positive reduction via FTA-driven precision hardening)
- Description: DIA signal emitted false positives through three independent failure paths identified via Fault Tree Analysis: (CS-1) inline codespan tokens were extracted without context validation, (CS-2) directory existence checks missed paths under common prefixes like `src/`, (CS-3) superseded/deprecated ADR documents were scanned as if active.
- Trigger examples:
  - README with `` `auth/callback` `` in prose → phantom-dir finding for `auth/` (CS-1).
  - Repo with `src/services/` + README mentioning `services/` → false FP (CS-2).
  - ADR with `status: superseded` referencing pre-refactoring path → stale finding (CS-3).
- Impact: Reduced DIA precision and triage trust, especially on repos with inline code examples and mature ADR processes.
- Mitigation:
  - CS-1: Sibling-context keyword gate — collect text-children from paragraph/heading, only trust codespans when structure keywords present in sibling context. Added "architecture" and "component"/"components" to keyword set. ADR files use `trust_codespans=True`.
  - CS-2: Container-prefix existence check via `_ref_exists_in_repo()` — checks direct path plus curated prefixes (`src`, `lib`, `app`, `pkg`, `packages`, `libs`, `internal`).
  - CS-3: ADR status parsing via `_extract_adr_status()` — YAML frontmatter + MADR freetext; skip `superseded`/`deprecated`/`rejected`.
  - 14 new regression tests covering all 3 cut sets + FN edge cases.
  - Golden snapshots updated (corpus findings count changed due to improved precision).
- Verification:
  - `python -m pytest tests/test_dia_enhanced.py -v --maxfail=1`
  - `python -m pytest tests/test_precision_recall.py -k dia -v --maxfail=1`
  - `python -m pytest tests/test_golden_snapshot.py -v`
- Residual risk: Low; conservative defaults limit FN surface. Codespan context gate may miss structure refs in keyword-free prose, but such cases are rare and rarely constitute genuine structure claims. Container-prefix set is curated and excludes test/docs dirs.

## 2026-04-07 - MAZ/ISD/HSC wave-2 calibration

- Risk ID: RISK-SIG-2026-04-07-188
- Component: src/drift/signals/missing_authorization.py, src/drift/signals/insecure_default.py, src/drift/signals/hardcoded_secret.py
- Type: Signal quality (edge-case precision/recall hardening)
- Description: Follow-up calibration addressed remaining edge-cases after ADR-015: MAZ auth-parameter matching was too narrow for composed/camelCase contexts, ISD ignore directive parsing was too permissive, and HSC missed wrapped known-prefix tokens.
- Trigger examples:
  - Decorator fallback endpoints with `currentUserContext` or `access_token` parameters.
  - Header comments like `drift:ignore-security-bypass` accidentally suppressing ISD.
  - Literals like `Bearer sk-...` in auth-header assignments.
- Impact: Prior behavior could reduce signal credibility via missed detections or unintended suppression.
- Mitigation:
  - MAZ: normalize parameter names and apply conservative auth-context regexes in fallback path.
  - ISD: accept only explicit `# drift:ignore-security` directive forms.
  - HSC: normalize common credential wrappers before known-prefix checks.
  - Add regressions in `tests/test_missing_authorization.py`, `tests/test_insecure_default.py`, `tests/test_hardcoded_secret.py`.
- Verification:
  - `python -m pytest tests/test_missing_authorization.py tests/test_insecure_default.py tests/test_hardcoded_secret.py -q --maxfail=1`
  - `python -m pytest tests/test_precision_recall.py::test_precision_recall_report -q -s`
- Residual risk: Medium-low; matcher scope is conservative but may require future tuning for uncommon naming conventions.

## 2026-04-06 - MAZ/ISD/HSC scoring-readiness calibration

- Risk ID: RISK-SIG-2026-04-06-187
- Component: src/drift/signals/missing_authorization.py, src/drift/signals/insecure_default.py, src/drift/signals/hardcoded_secret.py
- Type: Signal quality (precision/recall readiness for scoring promotion)
- Description: MAZ/ISD/HSC had quality gaps that reduced scoring-readiness credibility: MAZ fallback over-reported some auth-injected routes, ISD lacked local-dev severity context for localhost `verify=False`, and HSC under-reported known token prefixes in generic variable names.
- Trigger examples:
  - Decorated route handlers with injected auth context but no explicit auth decorator marker.
  - Localhost health calls using `verify=False` for local development.
  - Generic config names containing high-confidence API-token prefixes (`ghp_`, `sk-`, `AKIA`).
- Impact: Unbalanced precision/recall behavior in security findings, limiting confidence for future scoring-weight activation.
- Mitigation:
  - MAZ: conservative auth-like parameter suppression in decorator fallback path.
  - ISD: explicit localhost/loopback downgrade rule (`insecure_ssl_verify_localhost`, lower score) while keeping finding visibility.
  - HSC: prefix-first known-token literal detection independent of variable name shape.
  - Expanded TP/TN fixtures and explicit security precision/recall gates in `tests/test_precision_recall.py`.
- Verification:
  - `python -m pytest tests/test_missing_authorization.py tests/test_insecure_default.py tests/test_hardcoded_secret.py -q --maxfail=1`
  - `python -m pytest tests/test_precision_recall.py::test_precision_recall_report -q -s`
- Residual risk: Medium-low; conservative heuristics may still trade off edge-case recall or severity ranking, but regression coverage now enforces explicit security readiness gates.

## 2026-04-06 - MDS precision-first scoring-readiness calibration

- Risk ID: RISK-SIG-2026-04-06-186
- Component: src/drift/signals/mutant_duplicates.py
- Type: Signal quality (false positives / scoring credibility)
- Description: MDS produced low-actionability noise from semantic-only matches and
  intentional sync/async API variants, weakening trust when MDS contributes to
  repository scoring.
- Trigger examples:
  - Semantic-only matches within same-file context with high embedding similarity.
  - Sync/async file variants (`sync_*` vs `async_*`) with same function names.
  - Hybrid threshold previously lower than AST threshold, allowing borderline findings.
- Impact: Inflated MDS noise density and score distortion in precision-sensitive workflows.
- Mitigation:
  - Hybrid threshold is now precision-first (not lower than AST threshold).
  - Suppress intentional sync/async variant pairs for exact/near/semantic checks.
  - Tighten semantic-only gate and suppress same-file semantic pairs.
  - Keep cross-file semantic matches (including same class names) to avoid over-suppression.
  - Add regression tests in `tests/test_mutant_duplicates_edge_cases.py`.
- Verification:
  - `python -m pytest tests/test_mutant_duplicates_edge_cases.py -q --maxfail=1`
  - `python -m pytest tests/test_precision_recall.py::test_precision_recall_report -q -s`
- Residual risk: Medium-low; some true duplicates in sync/async ecosystems may be
  under-reported, but suppression is conservative and precision gains improve scoring reliability.

## 2026-04-06 - TPD unexpected source-segment exception hardening (Issue #184)

- Risk ID: RISK-SIG-2026-04-06-184
- Component: src/drift/signals/test_polarity_deficit.py
- Type: Signal quality (runtime robustness / false negatives)
- Description: `test_polarity_deficit` could still abort signal execution when `ast.get_source_segment` raised unexpected exception types beyond the previously guarded metadata errors.
- Trigger examples:
  - Field-test runs against microsoft/agent-framework showed TPD skip with `IndexError` and degraded context export quality.
  - Similar repositories with edge-case AST/source position behavior.
- Impact: Full TPD signal dropout for affected runs, causing incomplete context export and under-reporting.
- Mitigation:
  - Broadened source-segment guard in `_AssertionCounter.visit_Assert` to handle unexpected exceptions safely.
  - Added defensive per-file guards around parse/AST visit in TPD analyze path to prevent whole-signal abort.
  - Added regression `test_tpd_ignores_unexpected_source_segment_exception` in `tests/test_test_polarity_deficit.py`.
- Verification: `python -m pytest tests/test_test_polarity_deficit.py -q --maxfail=1`
- Residual risk: Low-medium; malformed files can be skipped for TPD counting, but signal execution remains stable and explicit logging supports diagnosis.

## 2026-04-06 - Stable signal abbreviation mapping in scan/analyze JSON (Issue #183)

- Risk ID: RISK-OUT-2026-04-06-183
- Component: src/drift/api.py, src/drift/api_helpers.py, src/drift/output/json_output.py
- Type: Output contract clarity / cross-command interoperability
- Description: `scan` and `analyze` used different identifier conventions without a
  first-class mapping field, forcing consumers to hardcode and maintain manual lookup tables.
- Trigger examples:
  - Agent workflows that correlate `scan` findings (`signal_id`/abbrev) with
    `analyze` findings (`signal_type`/snake_case).
  - CI pipelines that merge or compare findings across commands and versions.
- Impact: Reduced reproducibility and higher risk of wrong signal joins when mapping drifts.
- Mitigation:
  - Added top-level `signal_abbrev_map` (abbrev -> canonical `signal_type`) to
    both `scan` and `analyze --format json` outputs.
  - Reused centralized mapping source in `api_helpers` to prevent divergent maps.
  - Added regression tests in `tests/test_scan_diversity.py` and `tests/test_json_output.py`.
- Verification: `python -m pytest tests/test_scan_diversity.py tests/test_json_output.py -q --maxfail=1`
- Residual risk: Low; additive schema extension, existing fields remain unchanged.

## 2026-04-06 - HSC YAML env-template variable-name false-positive mitigation (Issue #181)

- Risk ID: RISK-SIG-2026-04-06-181
- Component: src/drift/signals/hardcoded_secret.py
- Type: Signal quality (false positives / precision calibration)
- Description: HSC flagged YAML configuration templates as hardcoded secrets when variable names contained secret-like tokens (for example `YAML_OPENAI_WITH_API_KEY`) although values only referenced `${ENV_VAR}` placeholders.
- Trigger examples:
  - microsoft/agent-framework: multi-line YAML template containing `openai_api_key: ${OPENAI_API_KEY}`.
  - Similar repositories storing config templates in Python triple-quoted strings.
- Impact: High-severity false positives and reduced trust in HSC precision/actionability.
- Mitigation:
  - Added narrow suppression for multi-line key/value template literals that contain environment placeholders (`${...}`).
  - Preserved high-confidence known-prefix checks before suppression.
  - Added targeted regressions in `tests/test_hardcoded_secret.py` for suppression and known-prefix safety.
- Verification: `python -m pytest tests/test_hardcoded_secret.py -q --maxfail=1`
- Residual risk: Low-medium; mixed template literals containing unusual non-prefixed credentials may be under-reported, but suppression remains constrained and known-prefix coverage is unchanged.

## 2026-04-06 - TPD ast.get_source_segment crash mitigation (Issue #180)

- Risk ID: RISK-SIG-2026-04-06-180
- Component: src/drift/signals/test_polarity_deficit.py
- Type: Signal quality (runtime robustness / false negatives)
- Description: `test_polarity_deficit` could crash with `IndexError: list index out of range` (or `ValueError`) when `ast.get_source_segment` processes assert nodes with malformed source-position metadata.
- Trigger examples:
  - microsoft/agent-framework scan reported deterministic TPD crash during assert polarity classification.
  - Similar repositories containing edge-case AST metadata combinations in assert nodes.
- Impact: Full TPD signal dropout on affected scans (0 findings), causing systematic under-reporting and drift-score distortion for TPD weight.
- Mitigation:
  - Added exception-safe guard around `ast.get_source_segment` in `_AssertionCounter.visit_Assert`.
  - Added targeted regression `test_tpd_ignores_out_of_range_assert_position_metadata` in `tests/test_test_polarity_deficit.py`.
- Verification: `python -m pytest tests/test_test_polarity_deficit.py -q --maxfail=1`
- Residual risk: Low-medium; malformed-node asserts may skip regex-based fallback classification, but scan stability is preserved and AST-based polarity heuristics remain active.

## 2026-04-06 - MDS numbered sample-step duplicate false-positive mitigation (Issue #179)

- Risk ID: RISK-SIG-2026-04-06-179
- Component: src/drift/signals/mutant_duplicates.py
- Type: Signal quality (false positives / precision calibration)
- Description: `mutant_duplicate` over-penalized intentional duplication across numbered sample progression directories (for example `01_single_agent` and `02_multi_agent`) because suppression only matched `step*` directory names.
- Trigger examples:
  - microsoft/agent-framework: `python/samples/04-hosting/durabletask/01_single_agent/worker.py` and `02_multi_agent/worker.py` duplicate `get_worker` helper patterns.
  - Similar repositories that structure tutorial/sample progression via numeric prefixes instead of `step_*` naming.
- Impact: High-severity false-positive noise in MDS and reduced confidence in duplicate findings.
- Mitigation:
  - Extended tutorial-step suppression to include conservative numbered sample-step directory names (`^\d{1,3}[-_].+`) in addition to `step*`.
  - Kept suppression context-gated to tutorial/sample/example path markers.
  - Added regressions in `tests/test_mutant_duplicates_edge_cases.py` for helper detection and exact-duplicate suppression in numbered sample directories.
- Verification: `python -m pytest tests/test_mutant_duplicates_edge_cases.py -q --maxfail=1`
- Residual risk: Medium-low; true duplicates in pedagogical numbered sample trees may be under-reported, while non-step sample duplicates remain detectable.

## 2026-04-06 - MDS tutorial-step sample duplicate false-positive mitigation (Issue #177)

- Risk ID: RISK-SIG-2026-04-06-177
- Component: src/drift/signals/mutant_duplicates.py
- Type: Signal quality (false positives / precision calibration)
- Description: `mutant_duplicate` over-penalized intentional helper duplication across tutorial step sample directories (for example repeated `get_worker` across `step_*` folders) as high-severity exact duplicates.
- Trigger examples:
  - microsoft/agent-framework: durabletask tutorial steps with standalone helper copies.
  - Similar repositories with pedagogical step-by-step sample trees.
- Impact: High-severity triage noise in MDS and reduced confidence in duplicate findings.
- Mitigation:
  - Added conservative path-context suppression for MDS candidate collection when file path indicates tutorial/sample/example plus explicit `step*` directory markers.
  - Added regressions in `tests/test_mutant_duplicates_edge_cases.py` for suppression and control-case detection outside step directories.
- Verification: `python -m pytest tests/test_mutant_duplicates_edge_cases.py -q --maxfail=1`
- Residual risk: Medium-low; true duplication in tutorial-step paths may be under-reported, but heuristic scope is intentionally narrow and non-step sample duplicates remain detectable.

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

## 2026-04-09 - PHR Signal: Phantom Reference (ADR-033)

- Risk ID: RISK-PHR-2026-04-09-033
- Component: src/drift/signals/phantom_reference.py
- Type: New signal (report-only, weight 0.0)
- Description: PHR detects unresolvable function/class references in Python files — names used in call expressions that cannot be resolved against local definitions, imports, builtins, or the project-wide symbol table. Primary use case: detecting AI-hallucinated function references.
- FP mitigations:
  - Star-import files conservatively skipped (complete exclusion)
  - Module-level `__getattr__` files conservatively skipped
  - `_FRAMEWORK_GLOBALS` allowlist for common framework-injected names
  - Import-resolved names added to available set (root-name resolution)
  - Private names (`_prefix`) and dunder names excluded from flagging
  - TYPE_CHECKING blocks excluded from name collection
- FN acceptance:
  - `exec()`/`eval()` introduced names: static analysis limitation
  - `getattr(obj, "name")`: dynamic access invisible to AST
  - Decorator-only references: partially covered via _ScopeCollector
- Verification: 22 targeted tests (test_phantom_reference.py) + 6 ground-truth fixtures (2 TP, 4 TN/confounder) all passing. P=1.00 R=1.00 on fixture suite.
- Residual risk: Medium; report-only status (weight 0.0) prevents false positives from affecting composite scores. Real-world precision validation pending on external repos.

## 2026-04-10 - AST Logical Location Enrichment (ADR-039)

- Risk ID: RISK-LL-2026-04-10-039
- Component: src/drift/logical_location.py, src/drift/models.py, src/drift/pipeline.py, src/drift/output/json_output.py, src/drift/output/agent_tasks.py, src/drift/api_helpers.py
- Type: Output schema extension (additive field on Finding model)
- Description: Findings are enriched with AST-based logical locations (class, method, function, module) from existing ParseResult data. New `logical_location` object in JSON, `logicalLocations` in SARIF, and `logical_location` dict in AgentTask/API responses.
- Trigger examples: All findings emitted by any signal; enrichment is post-processing in ScoringPhase.
- Impact: Downstream consumers that strictly validate JSON schema may encounter unexpected new field. SARIF consumers gain richer location data.
- Mitigation: Field is optional (`None` when no match); existing fields unchanged; backward-compatible. Symbol backfill only when `Finding.symbol` was previously empty.
- Verification: tests/test_logical_location.py (22 tests), tests/test_precision_recall.py (no regression), full `make check`.
- Residual risk: Low; purely additive output with no signal logic changes.

## 2026-04-10 - Scoring Promotion: HSC, FOE, PHR (ADR-040)

- Risk ID: RISK-SCORE-2026-04-10-040
- Component: src/drift/config.py (SignalWeights), src/drift/signal_mapping.py
- Type: Scoring change (weight activation for 3 previously report-only signals)
- Description: HSC (hardcoded secrets), FOE (fan-out explosion), and PHR (phantom references) are promoted from report-only (weight 0.0) to scoring-active (HSC 0.02, FOE 0.01, PHR 0.02). This means findings from these signals now contribute to the composite drift score, affect module-level severity, and can trigger safe_to_commit blocking in agent loops.
- Trigger examples: Any codebase with hardcoded secrets (HSC), files with >15 imports (FOE), or unresolvable function references (PHR) will now see score impact.
- Impact: Composite scores may increase for affected modules. Agent loops (drift_nudge) will block commits when new HIGH-severity PHR/HSC findings appear.
- Mitigation:
  - Conservative weights (0.01–0.02) limit maximum score contribution per signal.
  - All three signals retain their existing FP-reduction heuristics.
  - 11 new ground-truth fixtures added (4 HSC, 3 FOE, 2 PHR supplement, 2 existing PHR TP).
  - Precision/recall validation on full fixture suite before merge.
  - PHR abbreviation mapping fix ensures drift_nudge/diff correctly reference PHR findings.
- Verification: `pytest tests/test_precision_recall.py -v` (all signals P=1.00 R=1.00), `make check` (full CI suite).
- Residual risk: Medium; real-world FP rates for scoring-active HSC/FOE/PHR not yet validated on external repos. Weight can be reverted to 0.0 without code changes if FP rate is unacceptable.
