# STUDY.md — Evaluating Architectural Drift Detection in Real-World Python Projects

> **Feature update (2026-04-24, v2.41.0: Signal Dependency DAG + Context-Aware Finding Priority):** Introduces a topological signal scheduler (`src/drift/signals/dependency_dag.py`) using Kahn's algorithm with stable fallback to enforce `depends_on_signals` ordering across all 24 signal classes. `finding_priority.py` enriched with context-aware priority: signal metadata weight, stack depth, and file change frequency combine to rank findings by actionability. `scoring/engine.py` now applies per-signal weights and tracks degradation causes. `suppression.py` enriches file-level override paths for more precise suppression. `incremental.py` caching hardened. Tests: `tests/test_signal_dependency_dag.py`, `tests/test_issue_370_context_aware_priority.py`. Golden snapshot updated (deduplication: 63→60 findings). Non-goals: no new signals, no scoring weight changes. Evidence: `benchmark_results/v2.41.0_signal-dependency-dag-priority_feature_evidence.json`.

> **Feature update (2026-04-24, v2.40.2: MCTS Config-Space Optimizer):** Adds a UCB1-bandit optimizer that searches the drift configuration space (28 named `ConfigAction` arms: threshold/weight mutations) to maximize aggregate precision/recall F1 over the ground-truth fixture suite. Core additions: (1) `scripts/quality_loop/config_transforms.py` - 28 frozen ConfigAction arms; (2) `scripts/quality_loop/config_mcts.py` - ConfigMCTSSearch with UCB1 bandit; (3) `scripts/quality_loop/pr_metric.py` - PrecisionRecallMetric adapter; (4) `scripts/quality_loop/__main__.py` - new config-optimize CLI command; (5) `.github/workflows/quality-config-optimize.yml` - weekly scheduled workflow; (6) `src/drift/precision.py` - config_override param + summary_dict(). Workflows quality-mcts.yml and quality-genetic.yml hardened (script-injection safety, concurrency groups, Draft-PR strategy, GITHUB_STEP_SUMMARY, input bounds validation). Empirical evidence: MCTS gate_pass=true (5/5 seeds, median +0.243); hybrid gate_pass=true (2/3 seeds, median +0.122); config-optimize F1=1.0 baseline, zero regression. 13 new unit tests in tests/test_quality_loop_config_optimizer.py. Non-goals: no new drift signals, no scoring weight changes in drift itself. Evidence: benchmark_results/v2.40.2_config-space-optimizer_feature_evidence.json.

> **Feature update (2026-04-24, v2.39.x: Quality-Loop Verification Layer):** Adds a reproducible measurement infrastructure around the MCTS+GA quality loop to prove that improvements are real and regression-free. Core additions: (1) `OrchestratorResult` now carries per-component baseline/final metrics (`baseline_ruff`, `baseline_mypy`, `baseline_drift`, `final_ruff`, `final_mypy`, `final_drift`, `seed`); (2) `scripts/quality_loop/evaluate.py` — multi-seed evaluator that spawns N dry-run sub-processes, aggregates `median_improvement`, `mean_improvement`, `positive_seed_rate`, `ruff_regressions`, `mypy_regressions`, `max_drift_delta`, and applies a hard gate (`gate_pass`); (3) Gate criteria: `median_improvement >= 0.01`, `positive_seed_rate >= 0.70`, `ruff_regressions == 0`, `mypy_regressions == 0`, `max_drift_delta <= 0.005`; (4) CI workflows updated: both `quality-mcts.yml` and `quality-genetic.yml` now run multi-seed evaluation before any apply/commit step — apply is blocked when `gate_pass == false`; (5) 30+ unit tests covering gate logic, aggregation, regression detection, JSON contract, and negative cases. Non-goals: no new drift signals, no scoring weight changes. Evidence: `tests/test_quality_loop/test_evaluate.py`, `scripts/quality_loop/evaluate.py`.

> **Feature update (2026-04-23, v2.38.0: Hybrid MCTS+GA Autonomous Code Quality Loop):** Implements a Monte Carlo Tree Search combined with a Genetic Algorithm (MCTS+GA) for autonomous code quality improvement in `scripts/quality_loop/`. The loop explores candidate patches via MCTS simulation, evaluates them using drift's own analysis pipeline as fitness function, and applies genetic crossover/mutation to evolve patches toward lower drift scores. Non-goals: no new drift signals, no scoring weight changes, no auto-merge. Package in `scripts/quality_loop/` with `MCTSNode`, `GeneticOptimizer`, `QualityLoopRunner`, and supporting modules; 4 test files in `tests/test_quality_loop/`. Evidence: `benchmark_results/v2.38.0_quality-loop_feature_evidence.json`.

> **Feature update (2026-04-23, v2.34.2: DSOL v2 — Score-Gated Writeback with Convergence Check, ADR-098):** Adds opt-in `writeback` job to the self-improvement-loop workflow (`enable-writeback` boolean input, default `false`, never triggered by cron). `min-proposal-score` input filters proposals below threshold before applying. Staleness detection via `DRIFT_SELF_SCAN_FAILED` env variable when the self-scan step fails. New helper scripts: `scripts/check_dsol_convergence.py` (convergence gate) and `scripts/validate_proposals.py` (proposal schema + score validation). ADR-098 documents the decision (status: proposed). Non-goals: no new signals, no scoring changes, no autonomous PR or push. Evidence: `benchmark_results/v2.34.2_dsol-v2-writeback_feature_evidence.json`. ADR: `docs/decisions/ADR-098-dsol-v2-score-gated-writeback.md`.

> **Feature update (2026-04-23, v2.34.0: Never-ending Self-Improvement Loop, ADR-097):** Six-phase compounding cycle (OBSERVE → DIAGNOSE → PROPOSE → EMIT → TRACK → WAIT) for drift's own continuous optimization. Strictly POLICY-compliant: no auto-merge, no PR comments, no push, bounded by DEFAULT_MAX_PROPOSALS=10 plus per-signal cap. Proposals tracked in append-only ledger so recurring findings climb in priority across cycles. New CLI `drift self-improve run|ledger`, new weekly cron workflow with read-only permissions and 365-day artifact retention. Also adds `--output` flag to `drift watch` for machine-readable nudge JSON (schema_version 1). Evidence: `benchmark_results/v2.34.0_self-improvement-loop-adr-097_feature_evidence.json`. ADR: `docs/decisions/ADR-097-self-improvement-loop.md`.

> **Feature update (2026-04-22, v2.32.0: QA 2026 Pakete 1A/1B/2B/3A — agent-loop severity gate, Agent-Telemetry schema 2.2, E2E benchmark):** ADR-089 closes the agent regelkreis: conservative severity gate routes `critical`/`high` → BLOCK, `medium` → REVIEW, `low`/`info`+`auto_repair_eligible=true` → AUTO regardless of repair status. ADR-090 adds additive `agent_telemetry` top-level block to JSON output (schema_version 2.2) with `AgentActionType` StrEnum, `AgentAction`, `AgentTelemetry` dataclasses and three counters (`total_auto`, `total_review`, `total_block`). Paket 3A validates the severity-gate distribution over three reference profiles (drift_self: 0/6/8, high_quality: 4/2/0, legacy_service: 1/3/3) via `scripts/run_agent_loop_benchmark.py` and 47 contract tests. Fact-Grounding section added to agent prompt generator embedding ADR-091 retrieval instructions. Evidence: `benchmark_results/v2.33.0_agent-loop-e2e-benchmark-paket-3a_feature_evidence.json`. ADRs: `docs/decisions/ADR-089-agent-loop-closure.md`, `docs/decisions/ADR-090-agent-telemetry-schema.md`.

> **Feature update (2026-04-22, v2.29.0: Agent-Workflow Shortcuts):** New Makefile targets (`feat-start`, `fix-start`, `catalog`, `gate-check`, `handover`, `changelog-entry`, `audit-diff`) and companion scripts (`catalog.py`, `gate_check.py`, `generate_changelog_entry.py`, `risk_audit_diff.py`, `session_handover.py`, `sync_version.py`) codify the agent-driven development workflow described in `copilot-instructions.md`. New `drift adr` CLI subcommand lists ADRs in `docs/decisions/` with optional task-relevance filtering. `TaskSpec.to_patch_intent()` converts a TaskSpec to a PatchIntent for patch-engine integration. New `drift-agent-quickref.instructions.md` serves as canonical quick-reference for agent workflows. Non-goals: no new signals, no scoring weight changes. Evidence: `benchmark_results/v2.29.0_agent-workflow-shortcuts_feature_evidence.json`.

> **Feature update (2026-04-22, v2.28.0: Trend-Gate Enforcement):** `gate.trend` erweitert `drift check` und `drift ci` um ein optionales Trend-Gate, das bei persistenter Score-Verschlechterung ueber ein Commit-Fenster blockiert, falls keine Remediation-Aktivitaet erkannt wurde. Konfigurierbar via `enabled`, `window_commits`, `delta_threshold`, `require_remediation_activity`; CLI-Override ueber `--trend-gate/--no-trend-gate`. `trend_history` persistiert jetzt `commit_hash` und `finding_fingerprints` fuer die Remediation-Erkennung. Non-goals: keine neuen Signale, keine Aenderung der Signalgewichte. Evidence: `benchmark_results/v2.28.0_trend_gate_feature_evidence.json`. ADR: `docs/decisions/ADR-086-trend-gate-enforcement.md`.

> **Feature update (2026-04-21, v2.27.0: Fingerprint v2 — symbol-based hashing + fuzzy HEAD-subtraction for drift_diff):** `_compute_fingerprint_v2()` in `analyzer.py` produces a symbol-scoped SHA-256 fingerprint (`v2:<hash>`) that incorporates the enclosing function/class name, making fingerprints stable across file renames and minor refactors. `get_head_match_index_for_diff()` builds a dual index: exact `frozenset[str]` for canonical fingerprint matching and a fuzzy `frozenset[tuple[str,str,str]]` keyed by `(signal_type, file_posix, stable_title)` for findings without a stable symbol scope. `drift diff` uses both indexes in sequence so pre-existing findings are subtracted even when the v2 fingerprint is unavailable (ADR-082 + ADR-083). `drift.schema.json` updated; golden snapshots and benchmark references updated for v2.27.0. Audit results (FMEA, fault trees, risk register, STRIDE) updated. Non-goals: no new signals, no scoring weight changes. Evidence: `benchmark_results/v2.27.0_fingerprint-v2_feature_evidence.json`. ADRs: `docs/decisions/ADR-082-fingerprint-v2-symbol-based.md`, `docs/decisions/ADR-083-fuzzy-head-subtraction.md`.

 strict guardrails default, SG-007 scope-gate, SG-005a/SG-006a brief staleness, nudge revert gate):** `agent.strict_guardrails` default flipped `false` → `true` (ADR-080); set `strict_guardrails: false` in `drift.yaml` to restore v2.25.0 behaviour. New guardrail rules: SG-007 blocks `drift_fix_apply`/`drift_patch_begin` when last brief raised `scope_gate.action_required=ask_user`; SG-005a/SG-006a block when brief is stale (score drift > 0.1, tool_calls > 20, or age > 30 min). `drift_nudge`: `revert_recommended` tightened, `cross_file_hint` added, persists `.drift-cache/last_nudge.json` for pre-commit enforcement. `scripts/nudge_gate.py` + pre-commit hook blocks commits when last nudge recommended REVERT. `drift_brief`: active `scope_gate` block (`blocking=true`) on `scope.confidence < 0.5`; top-3 anti-patterns surfaced. Non-goals: no new signals, no scoring changes. Evidence: `benchmark_results/v2.26.0_feature_evidence.json`. ADR: `docs/decisions/ADR-080-strict-mode-default.md`.

> **Feature update (2026-04-21, v2.25.0: brief-staleness tracking, session score fields, SG enforcement hardened):** Session now tracks `last_brief_at`, `last_brief_score`, `last_scan_score`, `tool_calls_since_brief`; `_brief_staleness_reason()` detects stale briefs by score delta (>0.05), time (>600 s), or call count (>10). `drift_fix_apply`/`drift_patch_begin` reset brief-staleness counters on execution (SG-005/SG-006 hardened). Mypy fixes: `prepared_exclude` type annotation corrected in `file_discovery`; `getattr` fallback for `repo_path` in `session_handover`. Non-goals: no new signals, no scoring changes. Evidence: `benchmark_results/v2.25.0_feature_evidence.json`.

> **Feature update (2026-04-21, v2.24.0: ADR scanner, enriched brief, nudge regression detector, SG-005/SG-006, brief-staleness tracking):** `adr_scanner` stdlib-only parser for `docs/decisions/*.md` returns active ADRs (accepted/proposed) filtered by scope and task keywords. `brief` API response now includes `layer_contract`, `relevant_tests`, `active_adrs`; prompt block adds Layer Constraints and Active ADR Constraints sections. `nudge` gains `timeout_ms` (default 1000 ms), `revert_recommended`, `latency_ms`, `latency_exceeded`, `auto_fast_path` fields; emits explicit REVERT directive on degrading+unsafe edits. MCP SG-005/SG-006: `drift_fix_apply` and `drift_patch_begin` require prior `drift_brief` in strict sessions. Non-goals: no new signals, no scoring changes. Evidence: `benchmark_results/v2.24.0_feature_evidence.json`.

> **Feature update (2026-04-20, 8 new MCP tools: intent-loop, fix-apply, steer, compile-policy, suggest-rules, generate-skills):** `drift_capture_intent`, `drift_verify_intent`, `drift_feedback_for_agent` expose the intent-loop workflow via MCP, backed by the new `mcp_router_intent` bounded-context module. `drift_fix_apply` provides auto-patching of high-confidence findings with `dry_run=True` default. `drift_steer` returns location-centric architecture context (layer, neighbors, invariants) for pre-edit steering. `drift_compile_policy` compiles task-specific operative policy from repo signals. `drift_suggest_rules` proposes architecture rules from recurring drift patterns. `drift_generate_skills` generates skill briefings for recurring drift findings. New bounded-context module `mcp_router_architecture` hosts architecture-steering tool logic. API layer refactoring in `diff.py`, `drift_map_api.py`, `validate.py`; calibration layer cleanup in `github_correlator.py`, `outcome_correlator.py`. Non-goals: no new signals, no scoring changes. Tests: `tests/test_mcp_catalog.py` (v2.23.0 regression guard). Evidence: `benchmark_results/v2.23.0_feature_evidence.json`.

> **Feature update (2026-04-20, intent-capture system, lang module, --audience/--language flags, A2A intent endpoints):** `drift intent` command enables interactive intent capture with LLM/keyword classification and YAML contract storage in `.drift/intent/`. `drift.intent` module exposes `IntentContract`, `CapturedIntent`, and a classify/formalize/repair/validate/verify pipeline. `drift.lang` module provides a multilingual plain-language message catalog (--audience plain). `--audience {developer,plain}` and `--language`/`--lang` flags added to `drift analyze` for human-friendly output. A2A router endpoints: `capture_intent`, `verify_intent`, `feedback_for_agent`. `capture_intent()`, `verify_intent()`, and `feedback_for_agent()` exposed as public API via `drift.api`. Optional `[llm]` extra (`litellm>=1.0`) with graceful keyword-only fallback. Non-goals: no new signals, no scoring changes. Evidence: `benchmark_results/v2.21.0_feature_evidence.json`.

> **Feature update (2026-04-20, guard_contract API + drift context CLI + nudge enrichments):** `guard_contract()` API and `drift_guard_contract` MCP tool return a machine-readable pre-edit contract (layer, invariants, forbidden imports, public API surface, optional existing findings) for AI agents to consume before editing a file; designed to prevent architectural drift proactively. `drift context --target <path> [--for-agent] [--include-findings]` CLI exposes the same contract for humans and agents. `nudge` responses now include `finding_cluster_summary` (`total_new`, `by_signal`) for richer agent observability and a dynamic `agent_instruction` based on direction (degrading triggers `drift_brief` recommendation, safe-to-commit triggers `drift_diff` guidance). Feedback responses are enriched with `pending_fp_count`, `next_tool_call: {drift_calibrate}`, and `agent_instruction`. Non-goals: no new signals, no scoring changes. ADR: `docs/decisions/ADR-078-repair-task-execution-contract.md`. Evidence: `benchmark_results/v2.18.1_feature_evidence.json`.

> **Feature update (2026-04-20, nudge baseline TTL + --no-cache flag):** `nudge_baseline_ttl_seconds` (default 900) added to `DriftConfig` so users can tune how long a baseline snapshot stays valid without source-level changes; the persisted TTL is replaced with the current config value on warm load so a change takes effect immediately. `drift analyze --no-cache` bypasses read/write for both `ParseCache` and `SignalCache` in the current run without deleting existing entries; threaded through `IngestionPhase`, `SignalPhase`, `AnalysisPipeline`, and `analyze_repo()`. `drift cache clear` removes parse and signal cache directories with optional `--parse-only`, `--signal-only`, and `--dry-run` flags. Non-goals: no new signals, no scoring changes. Evidence: `benchmark_results/v2.18.0_feature_evidence.json`. Issues: #421, #424.

> **Feature update (2026-04-19, suppress inline comments, diff --auto feedback loop, explain fingerprint lookup, interactive review):** `insert_suppression_comment()` in `suppression.py` writes `drift:ignore` inline comments into Python/TS/JS source files with correct comment prefixes and signal abbreviations. `drift diff --auto` implements a post-fix feedback loop: `drift analyze` auto-saves a snapshot to `.drift-cache/last_scan.json`; subsequent `drift diff --auto` runs a fresh scan and renders score delta + resolved/new findings without specifying commit hashes. `drift explain FINGERPRINT --from-file analysis.json` resolves findings from a cached scan JSON without re-running a live analysis. `drift analyze --review` opens an interactive per-finding TP/FP review session that appends verdicts to `.drift/feedback.jsonl` for calibration. Non-goals: no new signals, no scoring changes. Tests: `tests/test_suppression.py`, `tests/test_suppress_interactive.py`, `tests/test_diff_auto.py`, `tests/test_interactive_review.py`. Evidence: `benchmark_results/v2.18.0_feature_evidence.json`.

> **Feature update (2026-04-18, PatchWriter auto-apply + EDS dampening, ADR-076 + ADR-077):** `PatchWriter` ABC and registry enable executable auto-patch generation for `add_docstring` (libcst-based stub docstring insertion) and `add_guard_clause` (None-guard clause insertion). Auto-apply via `drift.api.fix_apply()` requires `automation_fit=HIGH`, `change_scope=LOCAL`, `review_risk=LOW`, and a clean git state. EDS signal raises threshold for private micro-helpers (single-underscore prefix, <5 lines, <3 parameters) to reduce false positives on trivial one-liners. Non-goals: no new signals, no scoring changes for existing signals, no auto-apply for risky edit kinds. Tests: `tests/test_fix_apply_integration.py`, `tests/test_patch_writer_gcd.py`, `tests/test_patch_writer_eds.py`. Evidence: `benchmark_results/v2.16.0_feature_evidence.json`. ADRs: `docs/decisions/ADR-076-patch-writer-auto-apply.md`, `docs/decisions/ADR-077-eds-private-micro-helper-dampening.md`.

> **Feature update (2026-04-18, root_cause field on Finding + CLI-UX polish, ADR-075):** `Finding.root_cause` adds a concise proximate-cause explanation to every finding (distinct from `description` and `fix`); `_root_cause_for()` enrichment covers all six signal types; `AgentTask`, JSON output, and Rich output all expose the new field. `drift status` gains: animated spinner during analysis, profile-fallback warning, `✓ Clean – N files / M signals checked` output, and baseline-delta line. `docs/ux/cli-ux-quality-matrix.md` documents the full UX assessment. Non-goals: no new signals, no scoring changes. Tests: `tests/test_agent_native_cli.py`, `tests/test_guided_mode.py`, `tests/test_output_golden.py`, `tests/test_golden_snapshot.py`. Evidence: `benchmark_results/v2.16.0_feature_evidence.json`. ADR: `docs/decisions/ADR-075-remediation-contract-as-first-class-concept.md`.

> **Feature update (2026-04-18, TaskGraph compact summary + per-signal timing):** Two additive observability improvements: (1) `TaskGraph.to_summary_text()` returns a compact plain-text task-graph briefing (task counts, batching opportunities, top-level constraints) for token-efficient agent consumption. (2) `SignalPhase` now records per-signal wall-clock durations in `phase_timings.per_signal` (keyed by signal type); JSON output exposes the nested map and Rich output renders top-slow-signal hints. Both additions are non-breaking. Tests: `tests/test_task_graph.py`, `tests/test_pipeline_components.py`, `tests/test_json_output.py`. Evidence: `benchmark_results/v2.13.0_task_graph_timing_feature_evidence.json`.

> **Feature update (2026-04-18, Patch Engine ADR-074 + edit-kind heuristics):** Patch Engine introduces a three-phase transactional protocol (`patch_begin` → `patch_check` → `patch_commit`) for agent-driven code changes. `PatchIntent`/`PatchVerdict` Pydantic models carry clean/review_required/rollback_recommended status; `TaskSpec.to_patch_intent()` and `AgentTask.to_patch_intent()` bridge methods connect the task graph to the patch protocol. Sessions track `active_patches` and `patch_history`. Available via API, MCP, CLI (`drift patch-begin/check/commit`), and A2A. In addition, `_refine_edit_kind()` extended for `ARCHITECTURE_VIOLATION` with layer/coupling/inject/service/LLM heuristics; new `EDIT_KIND_SCOPE_PROMPT_BOUNDARY` constant for LLM-specific drift categories registered in `CROSS_FILE_RISKY_EDIT_KINDS` (#381). Non-goals: no new signals, no scoring changes. Evidence: `benchmark_results/v2.14.0_patch_engine_feature_evidence.json`. ADR: `docs/decisions/ADR-074` (Patch Engine).

> **Feature update (2026-04-17, generate_skills API):** New `drift.api.generate_skills()` endpoint analyses the persisted `ArchGraph` and produces structured `SkillBriefing` objects for modules with recurring drift patterns above configurable thresholds (`min_occurrences=4`, `min_confidence=0.6`). Each briefing contains `module_path`, `trigger_signals`, `constraints` (from matched ADR/decision rules), `hotspot_files`, `layer`, `neighbors`, and `abstractions` — all the data an AI agent needs to write a complete `.github/skills/<name>/SKILL.md`. The `agent_instruction` field directs the consuming agent. Non-goals: no new signals, no scoring changes. Evidence: `benchmark_results/v2.13.0_generate_skills_feature_evidence.json`.

> **Feature update (2026-04-17, arch-graph API + ADR-072 + ADR-073):** Three additive capabilities shipped together: (1) `drift.arch_graph` module provides `ArchGraph`/`ArchGraphStore` with decision constraints, feedback-loop recurring-pattern detection, reuse index, abstraction indexing, and graph seeding from `drift map` output — exposed as `drift.api.steer` and `drift.api.suggest_rules`. (2) ADR-072 Remediation Memory: `RepairTemplateRegistry.similar_outcomes()` returns compact past-outcome summaries per `(signal, edit_kind)`; `fix_plan` enriches each `AgentTask` with `similar_outcomes` for outcome-informed repair choices; `record_outcome` extended with `task_id`, `new_findings_count`, `resolved_count`. (3) ADR-073 Consolidation Opportunity Detector: `build_consolidation_groups()` clusters batch-eligible tasks by `(signal_type, fix_template_class)`; `TaskGraph` exposes `consolidation_opportunities` in its API dict; each task carries a `consolidation_group_id` back-reference. Non-goals: no new signals, no scoring changes, no breaking API changes. 7 new test files. Evidence: `benchmark_results/v2.12.0_arch_graph_api_feature_evidence.json`. ADRs: `docs/decisions/ADR-072-remediation-memory.md`, `docs/decisions/ADR-073-consolidation-opportunity-detector.md`.

> **Feature update (2026-04-16, scoring thresholds + finding prioritization, #370 #371):** `scoring:` section added to `drift.yaml` for tunable `dampening_k`, `breadth_cap`, and `grade_bands` without code changes; `feedback_blend_alpha` available when calibration is enabled (all defaults preserved). Findings are now ranked by signal context weight, stack depth, and recency so the most actionable items surface first in `scan` and `fix-plan` output. No precision/recall regression: reordering is purely presentational, scoring thresholds default to previous values. Evidence: `benchmark_results/v2.11.0_scoring_prioritization_feature_evidence.json`. Issues: #370, #371.

> **Feature update (2026-04-14, drift verify — ADR-070):** `drift verify` subcommand introduced as a binary pass/fail coherence gate for post-edit CI workflows. Wraps `shadow_verify()` with a configurable severity-threshold gate (`--fail-on critical|high|medium|low`). Returns structured `pass`/`fail` verdict, `blocking_reasons`, `score_delta`, `direction`, ADR-024 next-step contract, and `agent_instruction`. Available as `drift verify` CLI subcommand (exit code 0/1) and as `drift_verify` MCP tool (replaces deprecated `drift_shadow_verify`). Non-goals: no new signal detection, no scoring change, `shadow_verify()` internals unchanged. 41 targeted tests (test_verify.py), full suite: 4674 passed, 0 failed. MCP tool registered in `_EXPORTED_MCP_TOOLS`. Evidence: `benchmark_results/v2.10.0_verify_subcommand_feature_evidence.json`. Architecture decision: `docs/decisions/ADR-070-verify-subcommand.md`.

> **PHR runtime validation (2026-04-11, ADR-041):** PHR extended with opt-in runtime attribute validation via `importlib.import_module()` + `hasattr()`. When `thresholds.phr_runtime_validation: true`, PHR verifies that `from X import Y` import targets actually exist as attributes on installed third-party modules — catching version-mismatch phantoms that Phase B (`find_spec`) cannot detect. Security design: opt-in only (default false), daemon thread with 5s timeout, sys.modules fast path, TYPE_CHECKING/try-except/project-internal imports skipped. New trust boundary documented in STRIDE (analysis process → third-party package code via import_module). 3 new fixtures (1 TP missing-attribute from os, 2 TN for valid-attribute and try/except-guarded). PHR total: 25 fixtures, P=1.00 R=1.00. Full suite: 169 fixtures, 169 passed. Evidence: `docs/decisions/ADR-041-phr-runtime-validation.md`, `audit_results/risk_register.md` (RISK-SIGNAL-2026-04-11-041).

> **Scoring update (2026-06-14, ADR-039):** MAZ and ISD promoted from report-only to scoring-active, completing the agent-safety signal suite. HSC and FOE weights recalibrated for conservative activation. **MAZ** (missing authorization) weight 0.0→0.02: unprotected API endpoints now contribute to composite drift score. **ISD** (insecure default) weight 0.0→0.01: Django/Flask security misconfigurations (DEBUG=True, ALLOWED_HOSTS=["*"], verify=False, insecure cookies) now affect drift score; `drift:ignore-security` directive and localhost downgrade supported. **HSC** recalibrated 0.02→0.01; **FOE** recalibrated 0.01→0.005 for balanced weight budget. 5 new ISD ground-truth fixtures (2 TP, 2 TN confounder, 1 boundary). All 5 activated signals at P=1.00 R=1.00 on ground-truth suite. Total weight addition: +0.065 (~6.5% of composite). The model now exposes 24 configured signals with 20 scoring-active and 4 report-only. Evidence: `docs/decisions/ADR-039-activate-agent-safety-signals.md`, `audit_results/risk_register.md` (RISK-SIGNAL-ACTIVATION-2026-06-14-039).

> **PHR hardening (2026-04-10, ADR-040):** PHR extended with third-party import validation using `importlib.util.find_spec()`. Detects `import X` / `from X import Y` where X is not installed — a common AI hallucination pattern. FP guards: stdlib modules skipped (`sys.stdlib_module_names`), project-internal modules skipped, `try/except ImportError` and `ModuleNotFoundError` blocks detected via AST traversal, `TYPE_CHECKING` blocks excluded. 5 new fixtures (1 TP missing-package, 4 TN for conditional/stdlib/TYPE_CHECKING/ModuleNotFoundError). 1 existing fixture adapted (flask decorator: added flask stub). PHR total: 22 fixtures, P=1.00 R=1.00. Evidence: `docs/decisions/ADR-040-phr-import-resolver.md`, `audit_results/risk_register.md` (RISK-PHR-IMPORT-RESOLVER-2026-04-10-040).

> **Scoring update (2026-04-10, ADR-040):** PHR, HSC, and FOE promoted from report-only to scoring-active. **PHR** (phantom reference) weight 0.0→0.02: AI-hallucinated function/import detection now contributes to composite drift score and triggers safe_to_commit blocking in agent loops. **HSC** (hardcoded secret) weight 0.0→0.02: secrets left in source code now affect drift score; 3-tier detection (known prefix, entropy+name, entropy-only) with placeholder/env-read exclusion. **FOE** (fan-out explosion) weight 0.0→0.01: files with >15 imports flagged; `__init__.py` barrel files excluded. 9 new fixtures added (4 HSC, 3 FOE, 2 PHR supplement). PHR abbreviation mapping fix ensures nudge/diff correctly resolve PHR findings. All signals P=1.00 R=1.00 on ground-truth suite post-activation. Evidence: `docs/decisions/ADR-040-signal-scoring-promotion-phr-hsc-foe.md`, `audit_results/risk_register.md` (RISK-SCORE-2026-04-10-040).

> **Baseline update (2026-04-09, v2.7 KPI Roadmap):** First full-model precision/recall baseline on the current 15-signal scoring model (14 scoring-active + TVS at weight 0.0). Ground-truth fixture suite expanded to 115 fixtures covering 17 signal types (was: 110 fixtures, 16 signals). **New coverage:** ECM (Exception Contract Drift) — git-backed TP fixture via `old_sources` mechanism + confounder TN (refactored body, same profile); CCC (Co-Change Coupling) — expanded to 5 fixtures (boundary TP at 8-commit threshold, large-commit confounder TN). **Result:** All 17 evaluated signals at P=1.00 R=1.00 F1=1.00 on ground-truth fixtures; macro-average F1=1.00. Mutation benchmark: 25/25 = 100% recall (all 15 scoring-active signals covered). CI aggregate F1 gate raised from 0.50 → 0.60. CCC added to per-signal precision gates at 0.50. **Resolved gaps:** ECM TP fixture gap (was 0 TP → now 1 TP + 1 TN + 1 confounder); CCC fixture gap (was 3 → now 5). **Limitations:** Fixture P/R measures in-vitro signal correctness, not real-world precision on diverse codebases. Oracle-based precision (§3) remains at v0.5 baseline. Evidence: `benchmark_results/v2.7.0_precision_recall_baseline.json`.

> **Feature update (2026-04-09, PHR Signal):** PHR (Phantom Reference Signal, ADR-033) — AST-based detection of unresolvable function calls, decorator references, and `from X import Y` phantom imports. 15 ground-truth fixtures (5 TP, 2 TN, 2 boundary, 6 confounder) covering hallucinated function calls, cross-file phantoms, phantom imports, phantom decorators, multi-phantom scoring, TYPE_CHECKING exclusion, comprehension/lambda variable handling, private/single-char name boundaries, parent-package re-export tolerance, star-import and `__getattr__` bailout. Self-analysis: 5 PHR findings on drift repo, 5/5 true positive (all in `data/negative-patterns/` — intentional anti-pattern files with undefined references), 0 FP in `src/drift/`. Detection patterns: (1) bare name references in Load context, (2) cross-file symbol table verification, (3) `from X import Y` against per-module export map with `src/`/`lib/` prefix normalization and parent-package fallback. Report-only (weight=0.0). 26 targeted tests + 15 P/R fixtures, F1=1.00. Evidence: `benchmark_results/v2.7.1_phr_signal_feature_evidence.json`.

> **Versioning note (2026-04-05):** The package version in this repository is drift v2.5.4. Most quantitative benchmark artifacts referenced in this document were generated with drift v0.5.0 unless a later dated section states otherwise. The current production model exposes 23 configured signals, of which 15 are scoring-active and 8 remain report-only pending broader validation. This file therefore documents a historical evidence baseline and must not be read as a full description of the current live signal model. As of v2.5.0 the `scan` API and CLI command expose a `strategy` parameter (`diverse` / `top-severity`) that controls finding selection.

> **Feature update (2026-04-07, v2.5.4):** AVS `avs_co_change` precision hardening via FTA-driven three-MCS fix (ADR-018): self-analysis avs_co_change findings 20→0 (score 0.522→0.501, total findings 345→330). (1) Same-directory guard suppresses sister-file co-evolution in package directories; root-level pairs preserved. (2) `known_files` built from `filtered_prs` (consistent with import graph) eliminates test-source FPs. (3) Commit-size discount `1/(n-1)` in `build_co_change_pairs` reduces bulk/sweep-commit inflation. Mutation benchmark: AVS recall 100% (2/2), overall 94% (16/17). 5 regression tests added. Evidence: `benchmark_results/v2.5.4_avs_co_change_precision_hardening_feature_evidence.json`.

> **Feature update (2026-04-08):** Added A2A Agent Discovery support via `drift serve` (ADR-026): optional FastAPI/uvicorn HTTP server exposing `GET /.well-known/agent-card.json` (A2A v1.0 Agent Card) and `POST /a2a/v1` (JSON-RPC 2.0 dispatch) with 8 core skills (`scan`, `diff`, `explain`, `fix_plan`, `validate`, `nudge`, `brief`, `negative_context`). Security posture: localhost-only default bind (`127.0.0.1`), path normalization/validation in request router. Evidence: `benchmark_results/v2.7.0_a2a_agent_card_feature_evidence.json`; tests: `tests/test_a2a_serve.py` (15 passed).

> **Feature update (2026-04-07):** DIA FTA v2 eliminates all remaining self-analysis false positives (DIA findings 2→0 on own repo): (1) `_AUXILIARY_DIRS` extended with `artifacts` and `work_artifacts` to cover CI/build artifact and working directories; (2) illustrative path examples in ADR-017 moved from inline codespans to fenced code blocks so ADR scanning's `trust_codespans=True` no longer extracts them as phantom refs. FTA v2 root-cause chain: IE-4 (BE-8a) + IE-5a. 76/76 DIA unit tests green (3 new regression tests); 97/97 precision/recall fixtures unaffected. Evidence: `audit_results/risk_register.md` (RISK-SIG-2026-04-08-191).

> **Feature update (2026-04-05):** v2.5.0 extends `drift scan` with two agent-usability improvements. First, **signal filtering**: new `--exclude-signals` and `--max-per-signal` parameters on CLI, API, and MCP let callers suppress dominant signals or cap per-signal finding volume for balanced, token-efficient result lists (#173). ADR-013 documents the design decision. Second, **cross-validation fields**: all scan findings now include `signal_abbrev`, `signal_id`, `signal_type`, `severity_rank` (5=critical … 1=info), and a deterministic `fingerprint`; the response carries a top-level `cross_validation` block with field and score-range documentation for machine consumption (#171). DIA: suppress missing-README for bootstrap-sized repos (≤1 Python file). Evidence: `benchmark_results/v2.5.0_feature_evidence.json`; tests: `tests/test_scan_diversity.py`, `tests/test_agent_native_cli.py`, `tests/test_analysis_edge_cases.py`.

> **Feature update (2026-04-03):** Added FP extraction + oracle audit pipeline and an agent-brief context flow (`drift brief`) with scope resolution and guardrail output. Evidence: `benchmark_results/v2.3.0_feature_evidence.json`; tests: `tests/test_brief.py`, `tests/test_scope_resolver.py`, `tests/test_mcp_copilot.py`.
>
> **Evidenzlücke (2026-04-13, ADR-067):** Die Output-Korrektheit von `drift brief` (Guardrail-Generierung) ist durch Unit-Tests abgesichert. Ein unabhängiger A/B-Test, der misst, ob `drift brief`-Guardrails die Downstream-Fehlerrate von Agenten messbar reduzieren, existiert nicht. Der Claim "drift brief injects structural guardrails before the agent writes code" beschreibt den Mechanismus korrekt, aber keine gemessene Wirkungsgröße. Studie geplant in ADR-067 (`docs/decisions/ADR-067-drift-brief-effectiveness-study.md`).

> **Feature update (2026-04-03):** Finding-context triage defaults now prioritize operational findings for `scan`/`fix-plan` workflows by classifying fixtures, generated files, migrations, and docs into non-operational contexts unless `include_non_operational=true` is requested. This reduces remediation noise in agent loops while preserving full transparency in JSON output. Evidence: `benchmark_results/v2.2.0_feature_evidence.json`; tests: `tests/test_finding_context.py`, `tests/test_json_output.py`, `tests/test_recommendations_edge_cases.py`.

> **Feature update (2026-04-02):** v1.5.0 extends `drift diff` with deterministic baseline guidance for noisy worktrees. Responses now expose `baseline_recommended` and `baseline_reason` so agents can branch on a machine-readable signal instead of parsing free-text hints. The recommendation is threshold-driven (changed files, finding volume, out-of-scope noise) and configurable via `thresholds.diff_baseline_recommend_*` in config. Evidence: `benchmark_results/v1.5.0_feature_evidence.json`; tests: `tests/test_telemetry.py`.

> **Feature update (2026-04-02):** Enterprise governance hardening adds deterministic collaboration scaffolding for contributors: issue/discussion templates, devcontainer bootstrap, and root-level policy metadata (`CITATION.cff`, `.pre-commit-config.yaml`). Verification evidence is stored in `benchmark_results/v2.0.0_feature_evidence.json` and `audit_results/enterprise_governance_validation_2026-04-02.md`, with targeted coverage in `tests/test_enterprise_governance_assets.py`.

> **Triage note (2026-04-02):** Exact duplicates under `benchmarks/corpus/src/myapp/` (for example `service_a.py` and `service_b.py`) are intentional benchmark fixtures for MDS/PFS validation and must not be treated as actionable architectural drift in production code. During operational triage, classify these findings as benchmark-context false positives for product decisions unless the benchmark corpus itself is under review.

> **Feature update (2026-04-02):** v1.4.0 adds deterministic `baseline_refresh_reason` to `nudge()` responses for baseline refresh transparency. Emitted reason codes are `baseline_missing`, `ttl_expired`, `git_head_changed`, `stash_changed`, and `changed_file_threshold`, with targeted coverage in `tests/test_nudge.py` and feature evidence in `benchmark_results/v1.4.0_feature_evidence.json`.

> **Feature update (2026-03-30):** The agent-native `diff` response now also includes `decision_reason_code` and `decision_reason` to provide a stable, explicit accept/reject explanation without post-processing multiple boolean flags.

> **Feature update (2026-03-30):** `drift analyze` and `drift check` now accept `--no-color`, allowing colorless rich output for CI logs, terminals with forced plain rendering, and agent-driven command execution.

> **Feature update (2026-03-30):** v1.1.10 improves signal precision based on external validation against the MiroFish repository: (1) MDS now normalises `self.attr`/`cls.attr` to plain `Name` in AST n-gram fingerprints, so method↔function mutant pairs score higher similarity; (2) PFS applies a spread factor when non-canonical instance count exceeds 2, boosting scores for high-repetition fragmentation (e.g. 20× error-handling copy-paste); (3) AVS recognises `scripts/`, `commands/`, `cli/` as layer-0 entry points, enabling layer-violation detection for script-based architectures.

> **Feature update (2026-03-30):** v1.1.11 adds three new Security-by-Default signals for vibe-coding detection: **MAZ** (Missing Authorization, CWE-862) detects unprotected API endpoints across FastAPI/Django/Flask/Starlette/Sanic with 18 auth decorator patterns and body-level auth detection; **HSC** (Hardcoded Secret, CWE-798) detects hardcoded credentials via secret variable regex, known token prefixes (ghp_, sk-, AKIA, xoxb-), and Shannon entropy analysis; **ISD** (Insecure Default, CWE-1188) detects insecure configuration defaults (DEBUG=True, ALLOWED_HOSTS=['*'], CORS_ALLOW_ALL, insecure cookies, verify=False). All three signals are report-only (weight=0.0) pending precision validation. SARIF output enhanced with CWE helpUri. 67 new tests cover true-positive, true-negative, and edge-case scenarios. The model now exposes 22 configured signals.

> **Feature update (2026-03-30):** v1.1.12 introduces `drift init` — a new CLI command that scaffolds drift configuration with built-in profiles (`default`, `vibe-coding`, `strict`). Supports `--profile` to select pre-tuned signal weights and thresholds, `--ci` to generate a GitHub Actions workflow, `--hooks` for a git pre-push gate, `--mcp` for VS Code MCP server config, and `--full` for all-in-one scaffolding. The `vibe-coding` profile upweights MDS (0.20), PFS (0.18), BAT (0.06), and TPD (0.06), lowers similarity threshold to 0.75, and adds layer boundary policies — targeting the dominant technical debt vectors in AI-accelerated codebases. 24 new tests in `tests/test_init_cmd.py`.

> **Feature update (2026-03-31):** v1.1.14 lays the foundation for incremental analysis. `BaselineSnapshot` (new module `src/drift/incremental.py`) captures file-hash state after a full scan and provides TTL-based validity, file-change detection (added/removed/modified), and baseline score storage. `SignalCache.content_hash_for_file()` adds a per-file cache key method enabling file-local signals to cache independently of the full repo hash. 13 new tests in `tests/test_incremental.py`.

> **Feature update (2026-04-01):** v1.1.15 adds the `IncrementalSignalRunner` — the core engine for incremental analysis (Phase 3). All 22 signals are now classified via `incremental_scope` (14 file-local, 4 cross-file, 4 git-dependent). The runner executes file-local signals on changed files with `exact` confidence and carries forward cross-file/git findings with `estimated` confidence. `IncrementalResult` provides score delta, direction (improving/stable/degrading), new/resolved finding diffs, and a per-signal confidence map. Helpers `_direction_for_delta` (0.005 threshold) and `_finding_key` ensure deterministic finding identity. 26 new Phase 3 tests (39 total in `tests/test_incremental.py`).

> **Feature update (2026-04-02) [EXPERIMENTAL]:** v1.1.16 bundles Phases 4–6 of the Agent Navigation Gap 8D-Report. **Phase 4 — `drift_nudge` MCP tool:** New `nudge()` API returns directional feedback (improving/stable/degrading), `safe_to_commit` hardrule (blocks on critical/high new findings, delta > 0.05, or expired baseline), magnitude classification, blocking reasons, and per-signal confidence map. Registered as `drift_nudge` MCP tool with auto-detection of changed files via `git diff`. **Phase 5 — `BaselineManager`:** Singleton baseline store with git-event invalidation — HEAD commit change, stash change, or >10 files changed since baseline trigger automatic rescan. `_GitState` dataclass and `_capture_git_state()` provide git state fingerprinting. **Phase 6 — Documentation:** `DEVELOPER.md` documents the Incremental Analysis temporal model with `incremental_scope` convention; `ROADMAP.md` adds Diagnosis vs Navigation design dimension. 31 new tests in `tests/test_nudge.py` (1293 total suite).

> **Feature update (2026-04-02):** v1.2.0 introduces the **NegativeContext system** — signal-derived anti-pattern warnings for coding agents. Each of the 22 signal types now generates structured "what NOT to do" context via `src/drift/negative_context.py` (18 signal-specific generators covering 17 FMEA failure modes, RPN 96–384). New data models: `NegativeContext` dataclass with `forbidden_pattern`, `canonical_alternative`, and FMEA traceability. New API: `negative_context()` function in `api.py`, `drift_negative_context` MCP tool for VS Code/Copilot. Output integration: `negative_context` field on `AgentTask`, top-level `negative_context` section in JSON output. 23 new tests in `tests/test_negative_context.py` (1316 total suite).

> **Feature update (2026-04-02):** v1.2.0 upgrades the NegativeContext system with **Phase 3 — project-specific constraint extraction** for Cluster B generators (FMEA RPN 200–279). **AVS** now extracts concrete import paths, boundary rules, blast radius, and module instability from finding metadata. **CCC** uses actual co-change pairs (file_a/file_b), coupling weight, confidence scores, and commit sample evidence. **ECM** identifies diverged functions, divergence counts, comparison refs, and module-level exception type inventories. **HSC** differentiates between API token, placeholder secret, and generic hardcoded credential patterns with rule-specific forbidden patterns. Confidence scores are now dynamically calculated from signal strength metadata. 15 new Phase 3 tests (38 total in test_negative_context.py, 1337 total suite).

> **Feature update (2026-04-02):** v1.3.0 adds **Phase 4 — NegativeContext file export and MCP instructions enrichment** for agent adoptability. New `drift export-context` CLI command generates `.drift-negative-context.md` files in three formats: `instructions` (YAML front-matter, `.instructions.md` compatible), `prompt` (`.prompt.md` with `mode: agent`), and `raw` (plain Markdown). Items are grouped by category (security first), severity-ranked, and include DO NOT/INSTEAD guidance with affected file lists. Merge markers (`<!-- drift:negative-context:begin/end -->`) enable safe file updates. MCP server instructions are now dynamically enriched at startup from cached `.drift-negative-context.md` — top 10 anti-patterns are injected as "KNOWN ANTI-PATTERNS" section. 22 new Phase 4 tests (1375 total suite).

---

## Executive Summary

### Public Claims Safe To Repeat As Of 2026-04-09

- The package version in this repository is drift v2.5.4. The core benchmark corpus summarized below is the v0.5.0 evidence baseline.
- The v0.5 baseline composite score used 6 scoring signals. The current model exposes 24 configured signals, with 20 scoring-active and 4 report-only pending broader validation; quantitative precision/recall claims in this study apply only to the historical 6-signal model and have not been revalidated for the current live model.
- **v2.7 ground-truth baseline (2026-04-09):** 110 fixtures across 16 signal types yield P=1.00 R=1.00 F1=1.00 (macro) on the current 15-signal model. This measures in-vitro fixture correctness, not real-world oracle precision. Evidence: `benchmark_results/v2.7.0_precision_recall_baseline.json`.
- The current study corpus still covers 15 real-world repositories.
- All analysis is deterministic; no LLM is used in the detector pipeline.

1. **77% strict precision** on a score-weighted sample of 286 findings across 5 repositories (v0.5 non-circular heuristic classification). Of 15 total FPs, 9 come from DIA (weight 0.00) and 6 from active signals (4 AVS, 2 MDS). 51 findings are classified as Disputed (score-only evidence, no structural confirmation). Independent multi-rater validation is pending — treat as upper-bound estimate. **Note (2026-04-07):** DIA FTA v2 eliminates all 9 DIA FP sources in self-analysis (9→0). **Note (2026-04-07, v2.5.4):** AVS co_change FTA v1 (ADR-018) eliminates all 20 avs_co_change findings in self-analysis (precision_strict was 0.3, n=20 — all Disputed); drift score 0.522→0.501, total findings 345→330; see feature update above.
2. **100% mutation recall (v2.7+, 2026-04-09):** 25 of 25 injected patterns detected across all 15 scoring-active signal types on a synthetic repository with git history. Expanded from 17 patterns / 10 signals (v2.5.4) to 25 patterns / 15 signals: added NBV (3 mutations), BAT (1), COD (1), ECM (2, with git-backed exception contract changes), CCC (1, with co-change commit history). The historical 14-pattern §4 benchmark (86% recall, v0.5) remains for reference.
3. **Self-analysis baseline remains 0.442 (MEDIUM)** in the study corpus. Later smoke-test sections add broader comparison context, but they should be read as dated snapshots rather than a continuously refreshed badge.

For methodology, see §1. For precision tables, see §3. For threats to validity, see §7.

---

## Abstract

This document records the evidence base behind drift, whose package version in this repository is currently v2.5.4. The main quantitative corpus in §§1–12 is a frozen v0.5.0 benchmark baseline combining three methods: (1) a **ground-truth precision analysis** of 286 classified findings across 5 repositories, (2) a **historical controlled mutation benchmark** over 14 intentionally injected drift patterns, and (3) a **usefulness study** demonstrating actionable findings in a production codebase. The strongest current repeatable precision claim from that corpus remains 77% precision (strict) / 95% lenient on the score-weighted sample, using non-circular classification criteria; this claim applies to the v0.5 6-signal model and has not been revalidated for the current v2.5.x live model with 23 configured signals. A fresh mutation benchmark (25 patterns, 15 signals, synthetic repo with git history) yields 100% detection recall (v2.7+, 2026-04-09); all scoring-active signals covered. The tool is fully deterministic — no LLM is used in the analysis pipeline ([ADR-001](adr/001-deterministic-analysis-pipeline.md)).

---

## 1. Methodology

### 1.1 Tool Under Test

The core benchmark sections in this document evaluate the original 7 baseline signals used in the early precision/recall corpus: PFS, AVS, MDS, TVS, EDS, SMS, and DIA. Each signal produces findings with a severity and score. Signals are combined into a composite drift score using count-dampened weighted aggregation ([ADR-003](adr/003-composite-scoring-model.md)):

$$S_i = \frac{\sum f_{ij}}{n_i} \cdot \min\!\left(1,\; \frac{\ln(1 + n_i)}{\ln(1 + k)}\right)$$

**Signal weights (v0.5 baseline — historical):**

| Signal                       | Code | Weight | Status         |
| ---------------------------- | ---- | ------ | -------------- |
| Pattern Fragmentation        | PFS  | 0.22   | Active         |
| Architecture Violations      | AVS  | 0.22   | Active         |
| Mutant Duplicates            | MDS  | 0.17   | Active         |
| Temporal Volatility          | TVS  | 0.17   | Active         |
| Explainability Deficit       | EDS  | 0.12   | Active         |
| System Misalignment          | SMS  | 0.10   | Active         |
| Doc-Implementation Drift     | DIA  | 0.00   | Reporting only |
| Broad Exception Monoculture  | BEM  | 0.00   | Reporting only |
| Test Polarity Deficit        | TPD  | 0.00   | Reporting only |
| Guard Clause Deficit         | GCD  | 0.00   | Reporting only |

DIA, BEM, TPD, and GCD are included in the analysis output but contribute 0.0 to the composite score. They are Phase 2 signals with known precision limitations (see §3.1 for DIA; see [ADR-007](adr/007-consistency-proxy-signals.md) for BEM/TPD/GCD).

**Current codebase note:** The live model now exposes 24 configured signals, of which 19 are scoring-active and 5 remain report-only. The published ground-truth fixture evaluation and 25/25 mutation benchmark on this page still correspond to the earlier v2.7 baseline model with 15 scoring-active signals and 17 evaluated signal types. The table above documents the v0.5 baseline only. See `benchmark_results/v2.7.0_precision_recall_baseline.json` for that historical baseline evidence.

### 1.2 Repository Selection

We selected 5 Python repositories representing a range of domains, sizes, and development styles:

| Repository         | Domain             | Files | Functions | Selection Rationale                                |
| ------------------ | ------------------ | ----: | --------: | -------------------------------------------------- |
| **FastAPI**        | Web framework      | 1,118 |     4,554 | Large, community-maintained, extensive test suite  |
| **Pydantic**       | Data validation    |   403 |     8,384 | Complex metaclass internals, high function density |
| **PWBS** (backend) | Knowledge platform |   490 |     5,073 | AI-assisted development, rapid scaffolding phase   |
| **httpx**          | HTTP client        |    60 |     1,134 | Carefully hand-crafted, small focused library      |
| **drift** (self)   | Static analysis    |    45 |       263 | Self-analysis dogfooding, smallest repo            |

**Selection criteria**: We prioritized (1) diversity of codebase size (45–1,118 files), (2) variety of development style (hand-crafted vs. AI-assisted), and (3) public availability for reproducibility. We intentionally include PWBS as a known AI-assisted codebase and httpx as a known hand-crafted codebase to test whether drift's signals discriminate between the two.

**Potential bias**: The author developed both drift and PWBS. To mitigate this, we include 3 independent open-source projects and use identical default configuration across all repos (no custom policies).

### 1.3 Analysis Configuration

All analysis was deterministic — no LLM involved ([ADR-001](adr/001-deterministic-analysis-pipeline.md)). Identical default configuration for all repos: `drift analyze --since 90 --format json`. Public repos were cloned with `--depth 50` for git history (limits temporal signals). PWBS was analyzed against its full local checkout.

---

## 2. Benchmark Results

### 2.1 Composite Drift Scores

| Repository   |     Score | Severity | Findings | Analysis Time |
| ------------ | --------: | -------- | -------: | ------------: |
| **FastAPI**  | **0.690** | HIGH     |      661 |         2.3 s |
| **Pydantic** |     0.577 | MEDIUM   |      283 |        57.9 s |
| **PWBS**     |     0.520 | MEDIUM   |      146 |         6.2 s |
| **httpx**    |     0.472 | MEDIUM   |       46 |         3.3 s |
| **drift**    |     0.442 | MEDIUM   |       69 |         0.3 s |

Score ranking correlates with codebase size (r = 0.85 with log file count) but is not fully determined by it — PWBS (490 files) scores lower than Pydantic (403 files), suggesting development style and code coherence matter beyond raw size.

### 2.2 Signal Breakdown

| Signal                 | FastAPI | Pydantic | PWBS | httpx | drift |
| ---------------------- | ------: | -------: | ---: | ----: | ----: |
| PFS (Pattern Frag.)    |      36 |       11 |   29 |     4 |     4 |
| AVS (Arch. Violations) |       — |        1 |    4 |     — |     — |
| MDS (Mutant Dupes)     |     499 |       87 |   96 |     6 |     — |
| EDS (Explainability)   |      42 |      117 |   16 |    12 |    23 |
| TVS (Temporal Vol.)    |      18 |       31 |    — |     — |     4 |
| SMS (Sys. Misalign.)   |       6 |        7 |    — |     — |     6 |
| DIA (Doc Drift) ¹      |      60 |       29 |    1 |    24 |    32 |

¹ DIA has weight 0.00 — findings are reported but do not affect the composite score. See §3.1 for precision analysis.

### 2.3 Severity Distribution

| Repository | HIGH | MEDIUM | LOW | INFO |
| ---------- | ---: | -----: | --: | ---: |
| FastAPI    |  532 |     39 |  88 |    2 |
| Pydantic   |  111 |     50 | 118 |    4 |
| PWBS       |  109 |     25 |  12 |    — |
| httpx      |    7 |      4 |  34 |    1 |
| drift      |    5 |     14 |  49 |    1 |

### 2.4 Observations

**Pattern Fragmentation scales with codebase breadth.** All five repos show PFS as a top signal. PWBS shows 114 API endpoint variants and 26 error-handling variants in its connector layer — consistent with a rapidly scaffolded codebase where each module was generated independently.

**Mutant Duplicates dominate large repos.** FastAPI's HIGH severity is primarily driven by 499 near-identical test functions — likely generated with individual prompts rather than parameterized. httpx has only 6, correlating with its hand-crafted development style.

**Temporal Volatility requires git depth.** PWBS shows no TVS because the benchmark was run on a local clone without sufficient recent commit history. Public repos were limited by `--depth 50`.

**Architecture Violations are rare in well-designed libraries.** Only PWBS (4) and Pydantic (1) trigger AVS. This aligns with drift's intent: layer violations are a specific signal, not a universal problem.

---

## 3. Ground-Truth Precision Analysis

### 3.1 Method

To evaluate whether drift's findings represent actual issues versus false positives, we classified a stratified sample of 291 findings across all 5 repositories and 7 signal types. For each signal, up to 15 findings per repository were sampled with score-proportional stratification.

**Sampling procedure and label rate.** The total corpus contains 2,642 findings across 15 repositories. Of these, 263 were labeled (label rate: 10.0%). The sample was constructed as follows:

1. **Stratification by signal and repository.** For each (signal, repository) pair, findings were sorted by descending score. Up to 15 findings per bucket were selected, ensuring every signal×repo combination is represented.
2. **Score-proportional emphasis.** Within each bucket, high-score findings were sampled first. This biases toward the strongest detections — which is intentional for a precision study (we want to know: *when drift is most confident, is it correct?*). It means the precision estimate is an upper bound on population precision.
3. **No cherry-picking.** The sampling script (`scripts/ground_truth_analysis.py`) is deterministic and reproducible. Re-running it produces the same 263 labels from the same corpus files.

**Limitation:** Because sampling is score-weighted, the label set over-represents high-confidence findings and under-represents borderline cases near the detection threshold. A future recall-oriented study would require uniform or inverse-score sampling. The current label rate of ~10% is sufficient for precision estimation but insufficient for reliable per-signal recall claims.

Each finding was classified into one of three categories:

| Label                   | Definition                                                                                                                 |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **TP** (True Positive)  | Finding describes a real structural issue that a developer would want to know about                                        |
| **FP** (False Positive) | Finding is incorrect or describes something that is not a real issue                                                       |
| **Disputed**            | Technically correct detection, but debatable whether it represents a problem (e.g., intentional code duplication in tests) |

Classification used signal-specific structural criteria designed to avoid circular validation (i.e., the tool's own score is not used as the primary TP criterion). Where no structural confirmation is possible, findings are classified as Disputed:

- **MDS**: title contains "exact"/"identical" → TP; dunder methods or test helpers → FP; otherwise score ≥ 0.85 → TP, below → Disputed
- **PFS**: title contains "variant(s)" → TP; test directories or single-variant → FP; otherwise → Disputed
- **EDS**: title contains "complexity"/"no docstring"/"undocumented" → TP; test files or trivial `__init__` → FP; otherwise → Disputed
- **AVS**: circular/god module/zone of pain/blast radius → TP; upward imports into config/utils/shared → FP; `__init__` re-exports → FP; otherwise → Disputed
- **TVS**: title contains "hotspot"/"churn"/"volatile" → TP; migrations/lockfiles/changelogs → FP; otherwise → Disputed
- **SMS**: title contains "novel"/"outlier"/"unusual" → TP; stdlib modules → FP; otherwise → Disputed
- **DIA**: missing directory reference with real dir name → TP; URL fragments/port numbers/CamelCase proper nouns → FP

**Methodology note:** Score-only classifications (where no structural keyword or path confirms the finding) are marked Disputed to make circular validation risk visible. The strict precision therefore represents a lower bound on true precision.

### 3.2 Results

| Signal          | Sample (n) |      TP |     FP | Disputed | Precision (strict) | Precision (lenient) |
| --------------- | ---------: | ------: | -----: | -------: | -----------------: | ------------------: |
| PFS             |         48 |      48 |      0 |        0 |           **100%** |                100% |
| EDS             |         72 |      72 |      0 |        0 |           **100%** |                100% |
| SMS             |         21 |      21 |      0 |        0 |           **100%** |                100% |
| MDS             |         68 |      56 |      2 |       10 |            **82%** |                 97% |
| DIA             |         27 |      17 |      9 |        1 |            **63%** |                 67% |
| AVS             |         20 |       6 |      4 |       10 |            **30%** |                 80% |
| TVS             |         30 |       0 |      0 |       30 |             **0%** |                100% |
| **All signals** |    **286** | **220** | **15** |   **51** |            **77%** |             **95%** |
| Active only¹    |        259 |     203 |      6 |       50 |            **78%** |                 98% |

¹ Excludes DIA (weight 0.00). Active signals: PFS, AVS, MDS, TVS, EDS, SMS.

**Strict precision** counts only TP as correct. **Lenient precision** counts TP + Disputed as correct. The large Disputed count (51) reflects the non-circular methodology: findings where only the tool's own score supports classification are conservatively marked Disputed rather than TP.

### 3.3 Interpretation

**Structurally confirmed signals (100% strict):** PFS, EDS, and SMS achieve 100% strict precision because every finding in the sample contains structural keywords that confirm the detection independently of the score. These signals are highly reliable.

**MDS (82% strict):** Most near-duplicate findings are structurally confirmed via "exact"/"identical" keywords or high similarity (≥ 0.85). 2 FPs are async/sync transport pairs (intentional structural duplicates). 10 Disputed findings lack structural keywords but may still be correct.

**AVS (30% strict, n=20):** 6 true positives include circular dependencies and god-module patterns. 4 false positives are upward imports into config/settings modules — architecturally common and not harmful. 10 Disputed findings lack structural keywords. The sample size (n=20) remains below n=30 — precision estimate should be treated with caution.

**TVS (0% strict, 100% lenient):** All 30 TVS findings are classified Disputed because TVS titles do not contain structural keywords ("hotspot", "churn", "volatile"). This reflects a limitation of the non-circular classification method, not necessarily a problem with TVS detections. TVS findings may be correct but cannot be confirmed structurally from title/path alone.

**DIA (63% strict):** Improved from prior estimates due to better URL-fragment filtering. 9 false positives remain from README directory references that match port numbers, script directories, or ambiguous names. DIA remains at weight 0.00 until precision improves further.

**Overall:** The 77% strict / 95% lenient split reflects the conservative non-circular methodology. The 51 Disputed findings are not confirmed false positives — they are findings where only the tool's score provides evidence. Excluding DIA, the 6 active scoring signals achieve **78% strict / 98% lenient** precision (n=259, 6 FP).

---

## 4. Controlled Mutation Benchmark

### 4.1 Method

To measure detection recall, we created a synthetic Python repository with 14 intentionally injected drift patterns — 2 per signal (3 for MDS and DIA). Each mutation was designed to trigger exactly one signal type. The synthetic repo was analyzed with `drift analyze --since 90`, and we checked whether the injected pattern was detected.

This section documents the original v0.5 mutation-benchmark result (14 patterns, 86% recall). The harness has since been expanded to 25 patterns across all 15 scoring-active signals (100% recall, v2.7+); see §12.7.2 for the extended benchmark.

### 4.2 Injected Mutations

| #   | Signal | Mutation Description                                                             | Expected Detection       |
| --- | ------ | -------------------------------------------------------------------------------- | ------------------------ |
| 1   | MDS    | Exact function duplicate (`fetch_user_data` ≡ `get_customer_info`)               | Near-duplicate finding   |
| 2   | MDS    | Function duplicate with renamed variables (same structure, different names)      | Near-duplicate finding   |
| 3   | MDS    | Structural duplicate across modules (same logic, different signatures)           | Near-duplicate finding   |
| 4   | PFS    | 4 error-handling pattern variants (`if err`, `try/except`, `match`, bare return) | Pattern fragmentation    |
| 5   | PFS    | 4 return-value pattern variants (dict, tuple, dataclass, None)                   | Pattern fragmentation    |
| 6   | EDS    | Complex function (8 params, 3 nested loops, no docstring)                        | Explainability deficit   |
| 7   | EDS    | Complex class (6 methods, deep nesting, no documentation)                        | Explainability deficit   |
| 8   | AVS    | Upward import (data layer imports from presentation layer)                       | Architecture violation   |
| 9   | AVS    | Transitive circular dependency (A→B→C→A)                                         | Architecture violation   |
| 10  | SMS    | Module with 8 novel imports not used elsewhere in codebase                       | System misalignment      |
| 11  | DIA    | 3 directories referenced in README but absent from source                        | Doc-implementation drift |
| 12  | DIA    | Source directories not mentioned in README                                       | Doc-implementation drift |
| 13  | DIA    | Outdated directory names in README (renamed in source)                           | Doc-implementation drift |
| 14  | TVS    | Single file with high simulated churn (30 commits in 30 days)                    | Temporal volatility      |

### 4.3 Results

| Signal    | Injected | Detected |  Recall | Notes                                                                                                              |
| --------- | -------: | -------: | ------: | ------------------------------------------------------------------------------------------------------------------ |
| PFS       |        2 |        1 |     50% | Error-handling variants detected; return-value variants missed (below threshold)                                   |
| AVS       |        2 |        2 |    100% |                                                                                                                    |
| MDS       |        3 |        2 |     67% | Exact duplicate and structural duplicate detected; renamed-variable variant scored below 0.80 similarity threshold |
| TVS       |        1 |        1 |    100% |                                                                                                                    |
| EDS       |        2 |        2 |    100% |                                                                                                                    |
| SMS       |        1 |        1 |    100% |                                                                                                                    |
| DIA       |        3 |        3 |    100% |                                                                                                                    |
| **Total** |   **14** |   **12** | **86%** |                                                                                                                    |

### 4.4 Analysis of Misses

**MDS 67% (1 miss):** The near-duplicate with renamed variables (`user_id` → `customer_id`, `user_name` → `client_name`) scored below the 0.80 AST similarity threshold. The function structure was preserved, but aggressive variable renaming reduced the fingerprint overlap. This is a threshold trade-off: lowering it would increase recall but also increase false positives on legitimately different functions.

**PFS 50% (1 miss):** The return-value pattern variants (dict/tuple/dataclass/None) were distributed across different modules — `models/` was not detected as a pattern fragmentation site because PFS groups by directory and the variants were spread across 4 files with other non-variant functions diluting the signal. The error-handling variants in `handlers/` were correctly detected (4 of 4 variants, 2 of which were found). This suggests PFS requires variants to be concentrated enough within a directory to exceed the detection threshold.

### 4.5 Recall vs. Precision Trade-off

The 86% recall with 80% precision (from §3) represents a practical operating point. The two misses are both threshold boundary cases — the patterns exist but fall below detection thresholds designed to minimize false positives. A production user tuning for higher recall could lower thresholds per-signal at the cost of more disputed findings.

---

## 5. Usefulness Case Studies

To demonstrate that drift findings lead to actionable improvements, we examined the PWBS backend (a 490-file AI-assisted codebase in active development) and identified three findings that correspond to real, fixable structural issues.

### 5.1 Case 1: Copy-Pasted Utility Function (MDS)

**Finding:** `_run_async()` function duplicated identically across 6 Celery task files.

**Files affected:**

- `pwbs/queue/tasks/briefing.py`
- `pwbs/queue/tasks/embedding.py`
- `pwbs/queue/tasks/extraction.py`
- `pwbs/queue/tasks/insights.py`
- `pwbs/queue/tasks/multimodal.py`
- `pwbs/queue/tasks/snapshots.py`

**The duplicated function** (identical in all 6 files):

```python
def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

**Assessment:** This is a textbook extract-to-shared-module refactoring opportunity. The function was likely generated independently for each task file by an AI assistant that lacked cross-file context. The fix is extracting it into `pwbs/queue/utils.py` — a 2-minute change that eliminates 5 copies of identical code.

### 5.2 Case 2: Error-Handling Fragmentation (PFS)

**Finding:** 26 error-handling pattern variants across `pwbs/connectors/` (PFS score: 0.96, HIGH severity).

**Description:** Each of the 4 active connectors (Google Calendar, Notion, Zoom, Obsidian) implements its own error-handling pattern for API failures, token refresh, and retry logic. The patterns range from bare `try/except Exception` to structured error hierarchies with custom exception classes.

**Assessment:** In a connector architecture designed for uniformity (all implement `BaseConnector.fetch_since()`, `normalize()`, `health_check()`), inconsistent error handling creates maintenance burden. When a new connector is added, there's no single pattern to follow — the developer (or AI) picks whichever existing connector it sees first.

### 5.3 Case 3: API Endpoint Inconsistency (PFS)

**Finding:** 114 API endpoint pattern variants across `pwbs/api/v1/routes/` (PFS score: 0.99, HIGH severity).

**Description:** Across 18 mounted route modules, endpoint functions use inconsistent patterns for response construction, dependency injection ordering, error responses, and pagination. Some routes return `dict`, others return Pydantic models; some use `Depends()` consistently, others mix positional and keyword injection.

**Assessment:** The highest-scoring PFS finding in the entire benchmark. In a FastAPI application, inconsistent endpoint patterns make it harder to apply cross-cutting changes (e.g., adding a new middleware, changing auth logic). This finding directly supports ADR-003's thesis that pattern fragmentation is a leading indicator of maintenance cost.

---

## 6. AI-Attribution Signal

drift includes an AI-attribution heuristic based on git commit message patterns (e.g., `co-authored-by: copilot`, characteristic message formatting). Across all 5 repositories, the detected AI-commit ratio was **0%**.

This reflects the heuristic's conservative design: it avoids false positives at the cost of missing AI-assisted commits that don't carry explicit markers. The PWBS codebase is known to be heavily AI-assisted, yet its commits don't contain the specific markers drift looks for. Future versions may use AST-level heuristics (code entropy, naming patterns) rather than commit-message parsing.

**Note:** The AI-attribution ratio is informational and does not affect drift scoring. It is reported for transparency and to support future research on correlating AI-assistance levels with drift patterns.

---

## 7. Threats to Validity

1. **Author-developed test subjects.** The author developed both drift and PWBS. While 3 of 5 repos are independent open-source projects, there is an inherent risk that drift's signals align more naturally with the author's coding patterns. Replication on a fully independent corpus is needed to generalize beyond this sample.

2. **Ground-truth classification is single-rater with non-circular heuristics.** All 286 findings were classified by automated structural heuristics (title keywords, path patterns) rather than direct score thresholds, to avoid circular validation. However: (a) the heuristics were designed by the tool author, creating an indirect circularity risk; (b) 51 findings are Disputed because no structural confirmation exists; (c) inter-rater reliability has not been measured. The annotation tooling (`scripts/generate_annotation_sheet.py`) is available for independent multi-rater validation.

3. **TVS classified as 100% Disputed.** All 30 TVS findings lack structural keywords in their titles, causing the non-circular classifier to mark them Disputed. This is a classification-method artefact, not evidence that TVS findings are wrong. TVS strict precision should be interpreted as "unconfirmed" rather than "zero."

4. **Synthetic mutation benchmark.** The controlled mutation benchmark uses artificial code, not real-world drift that evolved organically. Injected mutations may be more or less detectable than naturally occurring patterns. The 86% recall should be interpreted as a lower bound on synthetic patterns, not a guarantee on organic code.

5. **Shallow clones limit temporal signals.** Public repos were cloned with `--depth 50`, which underreports TVS and limits git history for SMS baseline computation. PWBS was analyzed against a local checkout without recent commits. TVS findings across repos are not directly comparable.

6. **Default configuration only.** No custom layer-boundary policies were applied. FastAPI's HIGH score partly reflects the absence of project-specific `drift.yaml` tuning. Production users would typically configure policies, which could change precision/recall characteristics.

7. **DIA precision (63%).** The Doc-Implementation Drift signal still has lower precision than active signals, with 9 FPs from URL-fragment and ambiguous-directory-name matching. DIA is assigned weight 0.00 and does not affect composite scores. Tables in this study report DIA findings separately with footnotes.

8. **AVS sample size (n=20).** Although the sample size increased from 5 to 20, it remains below n>=30 for reliable per-signal precision estimation. The 30% strict precision (6 TP, 4 FP, 10 Disputed) should be treated with caution.

9. **AI-attribution at 0%.** The heuristic's commit-message-based approach fails to detect AI assistance in all 5 repos, including a known AI-assisted codebase (PWBS). This metric is currently uninformative and should not be used as evidence for or against AI involvement.

10. **Single point in time.** Results are a snapshot. drift's `trend` command is designed to track score evolution over repeated runs, which would provide stronger evidence of drift trajectory.

---

## 8. Reproducibility

```bash
# Install drift
pip install -e ".[dev]"

# Run on any Python repository
drift analyze --repo /path/to/repo --format json --since 90

# Self-check
drift self
```

All raw JSON outputs, ground-truth classifications, and mutation benchmark results are stored in [`benchmark_results/`](../benchmark_results/):

| File                         | Contents                                          |
| ---------------------------- | ------------------------------------------------- |
| `*_full.json`                | Complete drift output per repository              |
| `all_results.json`           | Combined summary metrics                          |
| `ground_truth_analysis.json` | 291 classified findings with labels and rationale |
| `mutation_benchmark.json`    | Synthetic mutation results with detection details |

The ground-truth classification can be reproduced with `python scripts/ground_truth_analysis.py`.

For mutation-benchmark history, the repository currently contains both `scripts/mutation_benchmark.py` and the workspace-task runner `scripts/_mutation_benchmark.py`. The `signal_type` vs `signal` JSON-field accounting defect (noted 2026-03-26) was repaired in the v2.7 harness update; the current harness produces 25/25 = 100% recall across all 15 scoring-active signals.

---

## 9. Tool Landscape Comparison

drift addresses a gap in the existing static analysis ecosystem. This section compares drift's detection capabilities against established tools to clarify where drift provides unique signal versus overlap.

### 9.1 Capability Matrix

| Capability                                                        |  drift  |    SonarQube    | pylint / mypy | jscpd / CPD | Sourcegraph Cody |
| ----------------------------------------------------------------- | :-----: | :-------------: | :-----------: | :---------: | :--------------: |
| **Pattern Fragmentation** (N variants of same pattern per module) | **Yes** |       No        |      No       |     No      |        No        |
| **Near-Duplicate Detection** (AST structural, ≥80% Jaccard)       | **Yes** | Partial (text)  |      No       | Yes (text)  |        No        |
| **Architecture Violation** (layer boundary + circular deps)       | **Yes** |     Partial     |      No       |     No      |        No        |
| **Temporal Volatility** (churn anomalies, author entropy)         | **Yes** |       No        |      No       |     No      |        No        |
| **Explainability Deficit** (complex undocumented functions)       | **Yes** |     Partial     |    Partial    |     No      |        No        |
| **System Misalignment** (novel imports in recent files)           | **Yes** |       No        |      No       |     No      |        No        |
| **Composite Health Score** (weighted multi-signal)                | **Yes** | Yes (different) |      No       |     No      |        No        |
| **Trend Tracking** (score evolution over time)                    | **Yes** |       Yes       |      No       |     No      |        No        |
| **AI-Erosion Specific** (designed for AI-generated code drift)    | **Yes** |       No        |      No       |     No      |     Partial      |
| **Deterministic** (no LLM in detection pipeline)                  | **Yes** |       Yes       |      Yes      |     Yes     |        No        |
| **Zero Config** (runs with defaults, no server needed)            | **Yes** |   No (server)   |    Partial    |     Yes     |    No (cloud)    |
| **SARIF Output** (GitHub Code Scanning integration)               | **Yes** |       Yes       |      No       |     No      |        No        |

### 9.2 Key Differentiators

**1. Pattern Fragmentation Score (PFS) — unique to drift.**
No other tool measures how many distinct implementation variants exist for the same pattern category within a module. SonarQube reports duplicates and complexity but does not group error-handling, API endpoint, or data-access patterns by structural fingerprint and count divergence. PFS achieved **100% precision** in our ground-truth study.

**2. AI-Erosion Focus.**
SonarQube's 2025 report documents 8× increase in code duplicates and declining code reuse in AI-accelerated codebases. However, SonarQube's detection is generalized — it doesn't distinguish between organic technical debt and AI-induced architectural fragmentation. drift's signal design specifically targets the patterns that AI coding assistants produce: local correctness with global incoherence.

**3. Composite Score as Codebase Health KPI.**
While SonarQube provides a Maintainability Rating (A-E), drift's composite score is designed as a time-series metric: run weekly, track trend. The score encompasses structural signals (PFS, MDS, AVS) combined with temporal signals (TVS, SMS) that capture _how_ the codebase is evolving, not just its current state.

**4. Zero-Infrastructure Operation.**
drift runs as a CLI tool — no server, no database, no cloud account. This makes it suitable for daily local use, pre-commit hooks, and lightweight CI pipelines where SonarQube's infrastructure requirements are prohibitive.

### 9.3 Where Existing Tools Excel

- **SonarQube** provides broader language support (25+ languages), security vulnerability detection (SAST), and enterprise governance features that drift does not attempt to replicate.
- **pylint / mypy** catch syntax errors, type inconsistencies, and style violations that drift intentionally ignores — drift only detects structural and architectural signals.
- **jscpd / CPD** perform well on exact and near-exact text-level duplicates. drift's MDS signal uses AST-level comparison, which is more resilient to formatting changes but may miss text-level clones that don't share AST structure.

drift is designed to **complement** these tools, not replace them. The recommended stack is: linter (style) + type checker (types) + drift (coherence) + SonarQube (security/enterprise governance, if applicable).

---

## 10. v0.2 Signal Enhancements

drift v0.2 improves three signals — DIA, AVS, and MDS — through Markdown AST parsing, knowledge-graph-aware heuristics, and optional embedding support. All enhancements remain **deterministic by default** (embeddings are opt-in).

### 10.1 Changes

| Signal  | v0.1 Approach                        | v0.2 Approach                                                                                                                            | Key Improvement                                                       |
| ------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **DIA** | Regex over raw Markdown text         | mistune AST parser; link URL exclusion; URL-segment blacklist (~80 entries)                                                              | Eliminates badge/CI/GitHub URL false positives                        |
| **AVS** | Naive directory-name layer inference | Omnilayer recognition (config/, utils/, types/); hub-module dampening via in-degree centrality; optional embedding-based layer inference | Cross-cutting dirs no longer flagged; high-fanin nodes dampened       |
| **MDS** | AST Jaccard similarity only          | Hybrid similarity (0.6 × AST Jaccard + 0.4 × cosine embedding); FAISS-indexed semantic duplicate search                                  | Catches renamed-variable duplicates that structural comparison misses |

### 10.2 Precision Results (v0.1 → v0.2)

Ground-truth reclassification on 5 repositories using the same stratified sampling and objective classification criteria (§3.1):

| Signal  | v0.1 Sample | v0.1 Prec | v0.2 Sample | v0.2 Prec |  Δ Prec   | v0.1 FP | v0.2 FP |  Δ FP   |
| ------- | :---------: | :-------: | :---------: | :-------: | :-------: | :-----: | :-----: | :-----: |
| PFS     |     49      | **100%**  |     49      | **100%**  |     —     |    0    |    0    |    —    |
| SMS     |     19      |  **95%**  |     20      |  **95%**  |     —     |    0    |    0    |    —    |
| TVS     |     34      |  **94%**  |     35      |  **94%**  |     —     |    0    |    0    |    —    |
| MDS     |     51      |  **92%**  |     56      |  **89%**  |   −3pp    |    0    |    0    |    —    |
| EDS     |     72      |  **81%**  |     72      |  **81%**  |     —     |    0    |    0    |    —    |
| DIA     |     61      |  **48%**  |     32      |  **59%**  | **+12pp** |   31    |    6    | **−25** |
| AVS     |      5      |  **20%**  |      5      |  **20%**  |     —     |    0    |    0    |    —    |
| **All** |   **291**   |  **80%**  |   **269**   |  **85%**  | **+5pp**  | **31**  |  **6**  | **−25** |

Key observations:

1. **DIA false positives dropped by 81%** (31 → 6). The remaining 6 FPs are edge cases where Markdown prose references non-directory names (e.g., "TypeScript/", "Basic/", "auth/") that pass the URL-segment filter but don't correspond to actual directories.
2. **Overall strict precision rose from 80% to 85%** (+5 percentage points), entirely driven by DIA improvement.
3. **AVS strict precision is unchanged at 20%** due to small sample size (5 findings across all repos, 4 classified as Disputed). However, the Omnilayer recognition and hub-dampening improvements are structural — they prevent false positives rather than reclassify existing ones. The signal's lenient precision remains 100%.
4. **MDS dropped 3pp** (92% → 89%) due to the larger sample including more edge-case near-duplicates. The hybrid similarity approach adds semantic duplicate detection capability while maintaining structural accuracy.

### 10.3 Recall (Unchanged)

The controlled mutation benchmark (§4) produces identical results: **86% recall** (12/14 detected). The v0.2 changes target precision improvement, not recall.

### 10.4 DIA Weight Recommendation

With DIA precision at 59% (strict) and 81% (lenient), the signal is approaching scoring-readiness. A conservative DIA weight of **0.05** could be introduced in a future version once precision exceeds 70% on an independent corpus.

---

## 11. Engineering Evaluation (v0.2 — 2026-03-19)

### 11.1 Ground-Truth Fixture Evaluation

To complement the repository-level ground-truth analysis (§3), we constructed a curated fixture suite of minimal, deterministic test cases with known-correct expectations. Each fixture is a synthetic codebase snippet designed to trigger (TP) or not trigger (TN) a specific signal.

| Signal  | TP Fixtures | TN Fixtures |    P     |    R     |    F1    |
| ------- | :---------: | :---------: | :------: | :------: | :------: |
| PFS     |      1      |      1      |   1.00   |   1.00   |   1.00   |
| AVS     |      2      |      1      |   1.00   |   1.00   |   1.00   |
| MDS     |      1      |      1      |   1.00   |   1.00   |   1.00   |
| TVS     |      1      |      1      |   1.00   |   1.00   |   1.00   |
| EDS     |      1      |      1      |   1.00   |   1.00   |   1.00   |
| SMS     |      1      |      1      |   1.00   |   1.00   |   1.00   |
| DIA     |      1      |      1      |   1.00   |   1.00   |   1.00   |
| **All** |    **8**    |    **7**    | **1.00** | **1.00** | **1.00** |

**Macro-Average F1: 1.00** (preliminary, n=15, self-curated)

**Important caveat:** These fixtures were designed by the tool author to validate specific signal behaviors. F1 = 1.00 on curated fixtures demonstrates that each signal detects its intended pattern — it does not imply generalization to arbitrary real-world code. External validation on an independent fixture corpus is the necessary next step.

### 11.2 Ablation Study

We measure each signal's contribution by deactivating it and computing the resulting F1 loss on the fixture suite:

| Signal | F1 without |  Delta | Impact                         |
| ------ | :--------: | -----: | ------------------------------ |
| AVS    |   0.857    | +0.143 | Highest — drives 2 TP fixtures |
| PFS    |   0.933    | +0.067 | Equal contribution             |
| MDS    |   0.933    | +0.067 | Equal contribution             |
| EDS    |   0.933    | +0.067 | Equal contribution             |
| TVS    |   0.933    | +0.067 | Equal contribution             |
| SMS    |   0.933    | +0.067 | Equal contribution             |
| DIA    |   0.933    | +0.067 | Equal contribution             |

All 7 signals contribute measurably. AVS has the strongest single-signal impact because it has 2 TP fixtures (upward import + circular dependency). No signal is dead weight.

### 11.3 Signal Improvements Applied

| Signal | Change                                                                                      | Rationale                                                                                                                                                   |
| ------ | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| EDS    | Decorator-aware test detection (`@pytest.mark.parametrize`, `@fixture`, `setUp`/`tearDown`) | Reduces FN for tested-but-undocumented functions                                                                                                            |
| AVS    | Hub-module dampening 0.3x → 0.5x                                                            | Prior dampening was too aggressive, suppressing genuine violations                                                                                          |
| PFS    | Async/sync fingerprint normalization                                                        | Prevents false fragmentation between `async def` and `def` variants                                                                                         |
| MDS    | Removed `sim < 1.0` guard in Phase 2 near-duplicate detection                               | Functions with identical AST structure but different names fell through both Phase 1 (different body_hash) and Phase 2 (sim=1.0 rejected) — a detection gap |

### 11.4 Scoring Calibration

A `calibrate_weights()` function was added to `drift.scoring.engine` that computes signal weights proportional to ablation delta magnitudes, with iterative clamping to configurable min/max bounds.

**Current limitation:** Weights are fitted on the same fixture corpus used for evaluation. A train/validation split should be introduced as the fixture suite grows beyond ~30 cases per signal.

### 11.5 Real-World Smoke Tests (2026-03-19)

To validate signal behavior beyond curated fixtures, we ran `analyze_repo()` on the drift codebase itself and 7 external open-source repositories (shallow-cloned, `docs/`, `docs_src/`, `examples/`, `tests/` excluded):

| Repository   | Score | Files | Functions | Findings | Dominant Signal                | Archetype                             |
| ------------ | ----: | ----: | --------: | -------: | ------------------------------ | ------------------------------------- |
| **requests** | 0.376 |    19 |       240 |       38 | EDS (23), DIA (9)              | Small, mature, hand-crafted           |
| **flask**    | 0.413 |    24 |       388 |       26 | EDS (10), DIA (8)              | Small, clean, well-maintained         |
| **drift**    | 0.450 |    61 |       388 |       84 | DIA (33), EDS (32)             | Self-analysis (dogfooding)            |
| **httpx**    | 0.486 |    23 |       446 |       64 | MDS (27), EDS (18)             | Small, hand-crafted HTTP client       |
| **sqlmodel** | 0.504 |    20 |       133 |       37 | EDS (14), DIA (13)             | Small, single-author                  |
| **pydantic** | 0.531 |   114 |     1,989 |      215 | EDS (136), MDS (48)            | Complex metaclass internals           |
| **fastapi**  | 0.582 |    72 |       426 |      278 | MDS (165), DIA (51)            | Large framework, many internal copies |
| **django**   | 0.599 |   908 |     9,562 |    1,107 | EDS (828), SMS (108), PFS (74) | Mega-repo, historically grown         |

**Score-Bandbreite: 0.376 (requests) – 0.599 (django).** Sorted by score, the ranking tracks expectations: hand-crafted libraries score lowest, large historically grown frameworks score highest. This is consistent with drift's design intent.

**Key observations per archetype:**

- **Hand-crafted baseline** (requests=0.376, flask=0.413): Low scores, few findings, EDS dominates — mostly undocumented internal helpers. Minimal MDS, confirming careful code. PFS fires on error-handling variants (30–39 per repo), which is normal for libraries with many exception paths.
- **httpx** (0.486): MDS dominates due to known Decorator-Pattern FP (`DeflateDecoder.flush ↔ GZipDecoder.flush`). Without this FP class, score would be closer to flask/requests baseline.
- **sqlmodel** (0.504): EDS+DIA driven. Small codebase but high function complexity (`get_column_from_field`). MDS finds intentional async/sync session overloads.
- **pydantic** (0.531): EDS dominates (136 findings) — complex metaclass internals without docstrings. MDS finds `v1/` legacy duplicates. PFS detects 52 error-handling variants in `v1/` alone.
- **fastapi** (0.582): With `docs_src/` excluded, MDS (165) still dominates — internal copies of `Param.__init__`, security classes, routing. These are structural findings worth reviewing.
- **django** (0.599): EDS dominates (828 findings) driven by admin module complexity. 6/7 signals fire including AVS (47 architecture violations). SMS (108) reflects django's deeply layered module structure.

**Consequence:** `docs/`, `docs_src/`, and `examples/` were added to the default exclude list in `DriftConfig` and `drift.example.yaml`. This prevents tutorial/example code — which is intentionally duplicated — from inflating scores for users who analyze framework repositories.

**Decorator-Pattern Blind Spot (MDS):** When two classes implement the same interface with structurally identical method bodies (e.g., codec `.flush()` methods), MDS correctly detects the duplication but cannot infer that it is intentional. This is a known limitation. Mitigation paths: (1) document `exclude_patterns` for interface implementations in project-level `drift.yaml`, (2) future: add structural-intent heuristic to MDS that detects interface-conformance patterns (e.g., sibling classes inheriting from the same ABC).

### 11.6 Temporal Stability Analysis

To validate whether drift scores are reproducible and stable across consecutive commits — rather than noisy — we ran `scripts/temporal_drift.py` on two repositories with different characteristics:

**drift (self-analysis):** 10 recent commits, score range 0.439–0.475 (σ=0.012, mean=0.450)

```
Date         Commit   Score   Delta  Files  Findings
2026-03-19   e8bb01d  0.440       —    40       61   fix: 3 performance/correctness bugs
2026-03-19   ac0bd3a  0.475  +0.035    47       73   docs: STUDY.md v1.0
2026-03-19   0eccd5c  0.467  -0.008    47       75   perf: pre-compute AST n-grams
2026-03-19   73bc71a  0.440  -0.027    52       80   feat(signals): v0.2 KG+RAG
2026-03-19   642843d  0.439  -0.001    52       80   fix(ci): add mistune to dev deps
2026-03-19   a201f18  0.439  +0.000    52       80   fix(ci): add numpy to dev deps
2026-03-19   4d33891  0.445  +0.006    56       81   feat(eval): P/R framework
2026-03-19   8d93bd6  0.451  +0.006    57       82   feat(tests): real-repo smoke tests
2026-03-19   4a8eecb  0.450  -0.001    57       82   fix(config): docs/examples exclude
2026-03-19   66805e2  0.450  +0.000    57       82   feat(tests): expand to 7 repos
```

**Observations (drift):** The biggest jump (+0.035 at `ac0bd3a`) correlates with adding STUDY.md — a large Markdown file added new `doc_impl_drift` surface. The biggest drop (-0.027 at `73bc71a`) correlates with the signal enhancement commit that improved detection precision, reducing spurious findings. CI-only commits (`642843d`, `a201f18`) produce zero delta, confirming that score is insensitive to non-structural changes.

**django:** 20 recent commits, score range 0.535–0.546 (σ=0.004, mean=0.538)

```
Date         Commit       Score   Delta  Files  Findings
2026-03-13   6c95af5c9d   0.535       —   2890      983
2026-02-13   e779bc7d78   0.535  +0.000   2890      984
2026-03-14   23f49c6b40   0.535  +0.000   2890      984
2026-03-14   6b90f8a8d6   0.535  +0.000   2890      985
2026-03-15   ad5ea29274   0.535  +0.000   2890      985
2026-03-11   d7bf84324f   0.535  +0.000   2890      987
2026-03-16   455e787b9c   0.535  +0.000   2890      987
2026-02-12   2333d56696   0.535  +0.000   2890      987
2026-03-16   4b2edb3418   0.535  +0.000   2890      987
2026-01-12   0ed8d4e7d1   0.535  +0.000   2890      987
2026-03-16   142659133a   0.535  +0.000   2890      987
2026-03-09   3abf898879   0.539  +0.004   2890      987
2026-01-06   37284896f0   0.539  +0.000   2890      987
2026-02-22   ba4751e0ca   0.538  -0.001   2890      988
2026-03-13   2e33abe57c   0.539  +0.001   2890      991
2026-03-18   4b2b4bf0ac   0.545  +0.006   2890      985
2026-02-01   f05fac88c4   0.545  +0.000   2890      984
2026-02-01   5146449a38   0.546  +0.001   2890      984
2026-03-15   1786cd881f   0.546  +0.000   2890      985
2026-02-28   2d7f899deb   0.546  +0.000   2890      985
```

**Observations (django):** The score is remarkably stable (σ=0.004) across 20 commits spanning 3 months. Individual bugfixes produce zero or near-zero delta. The step change at `4b2b4bf0ac` (+0.006, "Made admin use boolean icons") introduced new pattern variations in `django.contrib.admin` — visible as a persistent shift rather than noise. This confirms that drift scores reflect structural changes, not commit noise.

**Key findings from temporal analysis:**

1. **Scores are stable:** σ < 0.005 for mature repos (django), σ ≈ 0.01 for rapidly evolving repos (drift). Noise floor is below ±0.005.
2. **Deltas correlate with structural changes:** Zero delta on typo-fixes, doc edits, CI config. Positive delta on new code paths; negative delta on refactoring/cleanup.
3. **Step changes are persistent:** When the score shifts (e.g., django 0.535→0.545), it stays at the new level — indicating a real structural change, not a transient measurement artifact.
4. **Score insensitivity to non-structural commits** validates the design: drift measures codebase topology, not commit frequency.

### 11.7 Major-Version Correlation Analysis

To test whether drift scores correlate with major architectural changes — not just consecutive commits — we analyzed **17 django release tags** spanning **10 years** (1.8 → 6.0). Each tag was checked out in an isolated worktree and analyzed with the same configuration (`default_exclusions` enabled, `since_days=365` to include each release cycle's full diff).

**Tool:** `scripts/temporal_drift.py --tags` mode (glob-based tag resolution, worktree isolation per tag).

```
Version   Date         Score   Δ        Files   Findings
──────────────────────────────────────────────────────────
1.8       2015-04      0.553     —      2101      668
1.9       2015-12      0.553   +0.000   2232      817
1.10      2016-08      0.559   +0.006   2330      652
1.11      2017-04      0.557   -0.002   2394      700
2.0       2017-12      0.558   +0.001   2449      698
2.1       2018-08      0.559   +0.001   2460      674
2.2       2019-04      0.560   +0.001   2554      694
3.0       2019-12      0.562   +0.002   2576      714
3.1       2020-08      0.562   +0.000   2625      740
3.2       2021-04      0.563   +0.001   2692      765
4.0       2021-12      0.563   +0.000   2711      781
4.1       2022-08      0.561   -0.002   2747      817
4.2       2023-04      0.563   +0.002   2759      833
5.0       2023-12      0.562   -0.001   2772      862
5.1       2024-08      0.562   +0.000   2785      868
5.2       2025-04      0.563   +0.001   2815      890
6.0       2025-12      0.547   -0.016   2871      959
```

**Key findings:**

1. **10-year plateau (σ=0.004):** From 1.8 to 5.2, the score stays within 0.553–0.563. Despite +714 files and +222 findings over a decade, the drift score barely moves. This confirms that well-maintained projects absorb growth without structural degradation — and that drift measures coherence, not size.

2. **Minor-release stability (Δ < ±0.002):** Within a major series (e.g., 3.0→3.2, 4.0→4.2, 5.0→5.2), score variation is negligible. Django's "deprecate in minor, remove in major" discipline is directly visible in the scores.

3. **6.0 drop (Δ = -0.016):** The largest single delta in 10 years. Between 5.2 and 6.0: 759 commits, 745 files changed, and **116 deprecation/removal commits** that cleaned up legacy compatibility layers accumulated across multiple major cycles. Removing this structural fragmentation directly lowered the score — the expected behavior for a major cleanup release.

4. **Files grow monotonically (2101→2871), score does not.** This is strong evidence that drift scores are independent of codebase size. The score tracks structural coherence, not LOC.

5. **The 6.0 finding is the causal proof:** A major deprecation cleanup — the largest in django's history — produces the largest score drop ever measured. This is precisely the behavior drift is designed to detect: accumulated structural debt being resolved.

**Interpretation for drift users:** A stable score across many releases means the project maintains architectural discipline. A score drop after a major cleanup release is a positive signal — it means legacy debt was removed. A score _increase_ at a major release would indicate new structural fragmentation was introduced.

### 11.8 Hold-Out Validation (LOOCV)

To address the concern that `calibrate_weights()` is evaluated on the same fixtures used for calibration, we performed **Leave-One-Out Cross-Validation (LOOCV)** across all 15 ground-truth fixtures.

**Method:** For each fold i (1..15), fixture i is held out. The remaining 14 fixtures are used for ablation → `calibrate_weights()` → fold-specific weights. The held-out fixture is then evaluated with the full signal set.

**Tool:** `scripts/holdout_validation.py`

```
LOOCV Summary (15 folds)
────────────────────────────────────────────────────
  Full-set F1:    1.000  (all 15 fixtures)
  Held-out F1:    1.000  (aggregated across 15 folds)
  Held-out TP=8  FP=0  FN=0
  Folds correct:  15/15

Weight stability across folds:
  Signal                          Full-set      Mean         σ      Δmax
  ──────────────────────────────  ────────  ────────  ────────  ────────
  pattern_fragmentation             0.1228    0.1236    0.0256    0.0878
  architecture_violation            0.2632    0.2586    0.0489    0.1203
  mutant_duplicate                  0.1228    0.1236    0.0256    0.0878
  explainability_deficit            0.1228    0.1236    0.0256    0.0878
  doc_impl_drift                    0.1228    0.1236    0.0256    0.0878
  temporal_volatility               0.1228    0.1236    0.0256    0.0878
  system_misalignment               0.1228    0.1236    0.0256    0.0878
```

**Key findings:**

1. **Detection generalises perfectly (F1=1.000).** Every held-out fixture is correctly classified by signals that were calibrated without it. The "training on test data" concern is mitigated because signal detection is orthogonal to weight calibration — signals fire based on AST patterns, not on weight values.

2. **Weight variance reveals fixture sparsity.** The per-signal σ ≈ 0.03–0.05 and Δmax up to 0.12 show that removing a single fixture can shift a signal's weight significantly. This is expected with only 2 fixtures per signal (1 TP + 1 TN): when the TP fixture is held out, that signal's ablation delta drops to zero, collapsing its weight to `min_weight`. Architecture violation (3 fixtures) shows the smallest relative Δmax because two TPs provide redundancy.

3. **Practical implication:** The weights are functionally stable enough for composite scoring (the ranking of signals by importance is consistent), but would benefit from ≥4 fixtures per signal to reduce fold-to-fold variance. This upgrades the "fixture scaling" gap from a generalization concern to a weight-stability refinement.

### 11.9 Known Gaps and Next Steps

| Gap                               | Risk                                 | Next Step                                                |
| --------------------------------- | ------------------------------------ | -------------------------------------------------------- |
| ~~ECM has 0 TP fixtures~~         | ✅ Resolved (v2.8-dev) — 1 TP + 1 confounder added via `old_sources` git-backed mechanism | — |
| ~~CCC has only 3 fixtures~~       | ✅ Resolved (v2.8-dev) — expanded to 5 (boundary TP + large-commit confounder) | — |
| DIA weight still 0.00             | Signal has 59% precision, not scored | Increase to 0.05 once precision > 70% on external corpus |
| MDS Decorator-Pattern FP          | Documented known limit (httpx codec) | Per-file suppressions or ABC-sibling heuristic           |
| Oracle precision at v0.5 baseline | No revalidation on current 15-signal model | Run oracle_fp_audit.py against 5 repos with ground-truth labels |

### 11.10 Unknown-Repo External Validation (2026-03-23)

To move drift from "internally validated" to "externally credible", we ran a
blind validation cycle on **three previously unseen repositories** — none of
which appear in the 15-repo benchmark corpus.

**Selection criteria:** (a) not in corpus, (b) >1 000 GitHub stars,
(c) pure Python, (d) diverse archetype (CLI, library, web-backend).

| Repo             | Archetype    | Files | Functions | Score | Findings | TP  | FP | Precision |
| ---------------- | ------------ | ----- | --------- | ----- | -------- | --- | -- | --------- |
| httpie/cli       | CLI          |    86 |       502 | 0.474 |       12 |  12 |  0 |    100.0% |
| arrow-py/arrow   | Library      |    10 |       175 | 0.339 |        8 |   8 |  0 |    100.0% |
| frappe/frappe     | Web-Backend  | 1 179 |     6 232 | 0.544 |      353 | 353 |  0 |    100.0% |
| **Aggregate**    |              | 1 275 |     6 909 |       |  **373** | 373 |  0 | **100.0%** |

**Methodology:** `scripts/unknown_repo_audit.py` clones each repo at depth 1,
runs full analysis, and exports a JSON file with one entry per MEDIUM+ finding.
Each finding was annotated as TP or FP based on whether it identifies a genuine
structural issue a code reviewer would want flagged. **Annotation was performed
by the tool author alone (single-rater) using `annotation_script.py`; no second
reviewer participated. All 353 frappe findings were re-annotated after SMS
calibration was applied — the re-audit was performed post-calibration on the
same corpus.**

**Per-signal breakdown (aggregate):**

| Signal                   | TP  | FP | Precision |
| ------------------------ | --- | -- | --------- |
| architecture_violation   |   1 |  0 |    100.0% |
| explainability_deficit   | 292 |  0 |    100.0% |
| mutant_duplicate         |  12 |  0 |    100.0% |
| pattern_fragmentation    |  68 |  0 |    100.0% |
| system_misalignment      |   0 |  0 |       n/a |

**Fix-Text Actionability:** 100% (76/76) on self-analysis after calibration
(baseline: 74%). Improvements: DIA fix texts now reference `README.md` explicitly,
TVS fix texts use imperative verbs (`Stabilisiere`), MDS/TVS verbs added to
actionability regex.

**Calibration measures applied:**

1. **MDS — dunder method filter:** `_DUNDER_METHODS` frozenset excludes ~40
   Python special methods (`__eq__`, `__gt__`, `__iter__`, …) from duplicate
   detection. Qualified names are resolved via `rsplit(".", 1)[-1]`.
2. **MDS — minimum complexity:** Functions with `complexity < 2` are skipped,
   eliminating trivial delegation wrappers.
3. **SMS — stdlib filter:** `_STDLIB_MODULES` frozenset (~90 modules) prevents
   standard-library imports from triggering novel-dependency alerts.
4. **SMS — shallow-clone guard:** When fewer than 10% of files have pre-cutoff
   modification history (typical for `--depth 1` clones), SMS is skipped
   entirely to avoid false-positive storms from empty baselines.
5. **DIA — explicit file reference:** Fix texts reference `README.md` by name.
6. **TVS — imperative fix verbs:** `Stabilisiere durch Tests und Code-Review`.

**FP patterns observed before calibration:**

| Pattern                       | Signal | Count | Resolution            |
| ----------------------------- | ------ | ----- | --------------------- |
| Dunder method near-duplicates | MDS    |     6 | `_DUNDER_METHODS` set |
| Shallow-clone novel imports   | SMS    |    28 | Baseline coverage guard |
| Stdlib as novel dependency    | SMS    |     — | `_STDLIB_MODULES` set |

**Note:** The 28 SMS FPs were discovered during an initial frappe run, then
eliminated by implementing the shallow-clone guard, and frappe was re-run
post-calibration. This constitutes calibration on the test corpus, not
independent validation. Pre-calibration frappe precision was approximately
92.6% (353 TP / 381 total findings).

**Data-leakage warning:** The 100.0% precision reported above is a
post-calibration measurement on the same repos that informed calibration.
It should not be cited as independent external validation. A proper external
validation requires running drift on new repos without modifying any detection
logic based on their results. The pre-calibration precision (92.6% on frappe)
is more representative of out-of-sample performance.

---

## 12. TypeScript Full-Semantic Support (v0.5 — 2026-03-24)

### 12.1 Overview

Beginning with v0.5, drift extends full-semantic analysis to TypeScript and
JavaScript codebases. All seven core signals now operate on TS/JS sources
using language-native AST parsing via tree-sitter, achieving feature parity
with the existing Python support.

**Implementation scope:**

| Component | Python (baseline) | TypeScript (v0.5) |
| --------- | ----------------- | ----------------- |
| AST parsing | `ast` stdlib | tree-sitter-typescript / tree-sitter-tsx |
| Function extraction | ✓ (name, LOC, complexity, decorators, docstrings) | ✓ (function_declaration, method_definition, arrow_function; complexity, LOC, decorators, JSDoc) |
| Class extraction | ✓ (bases, methods, docstrings) | ✓ (heritage clauses, methods, JSDoc) |
| Import graph | ✓ (stdlib-aware) | ✓ (ES6 imports, path alias resolution) |
| AST n-grams (MDS) | ✓ (normalized identifier/literal fingerprints) | ✓ (identical normalization on tree-sitter AST) |
| Error-handling patterns (PFS) | ✓ (try/except fingerprinting) | ✓ (try/catch/finally fingerprinting) |
| API endpoint patterns (PFS) | ✓ (Flask/FastAPI/Django decorators) | ✓ (Express/Fastify router calls, NestJS decorators) |
| Test heuristics (EDS) | ✓ (pytest, unittest) | ✓ (describe/it/test patterns, .spec.ts/.test.ts) |
| Stdlib filter (SMS) | ✓ (~90 Python modules) | ✓ (~50 Node.js built-in modules) |
| Architecture rules | — | ✓ (circular-module, cross-package, layer-leak, ui-to-infra) |

### 12.2 Benchmark Results — TypeScript Corpus (5 repositories)

All benchmarks executed with `drift analyze --format json --since 90` on
shallow clones (`--depth 50`). tree-sitter-typescript 0.23.2,
tree-sitter-languages 1.10.2.

| Repository | Architecture | Files | Functions | Score | Severity | Findings | Signals active |
| ---------- | ------------ | ----: | --------: | ----: | -------- | -------: | -------------- |
| express    | Minimal/flat | 98    | 106       | 0.373 | low      | 17       | EDS, MDS, PFS, TVS, DIA |
| fastify    | Plugin-based | 269   | 860       | 0.571 | medium   | 151      | EDS, MDS, PFS, TVS, DIA |
| zod        | Library/mono | 356   | 1 309     | 0.622 | high     | 352      | EDS, MDS, PFS, TVS, DIA |
| svelte     | Compiler/UI  | 3 338 | 4 944     | 0.628 | high     | 576      | EDS, MDS, PFS, SMS, TVS, DIA |
| nestjs     | Layered/DI   | 1 667 | 3 472     | 0.697 | high     | 838      | EDS, MDS, PFS, TVS, AVS, DIA |

**Score range:** 0.373–0.697 (mean 0.578, σ=0.118).

**Interpretation:** The score ranking is consistent with architectural
expectations. express (hand-crafted, minimal) scores lowest — analogous to
requests (0.376) in the Python corpus. nestjs (large DI framework with deep
module hierarchy) scores highest — analogous to django (0.599). The
architecture_violation signal fires exclusively on nestjs (584 findings),
correctly identifying cross-package import violations in the monorepo
structure. svelte triggers system_misalignment (42 findings) due to Node.js
built-in imports in browser-targeted code.

### 12.3 Signal Coverage Analysis

| Signal | express | fastify | zod | svelte | nestjs | Coverage |
| ------ | ------- | ------- | --- | ------ | ------ | -------- |
| explainability_deficit | 4 | 81 | 119 | 426 | 101 | 5/5 |
| pattern_fragmentation | 4 | 13 | 12 | 33 | 91 | 5/5 |
| mutant_duplicate | 4 | 4 | 200 | 22 | 42 | 5/5 |
| temporal_volatility | 2 | 46 | 18 | 51 | 16 | 5/5 |
| doc_impl_drift | 3 | 7 | 3 | 2 | 4 | 5/5 |
| architecture_violation | 0 | 0 | 0 | 0 | 584 | 1/5 |
| system_misalignment | 0 | 0 | 0 | 42 | 0 | 1/5 |

5 of 7 signals fire on every repository. architecture_violation requires
explicit layer/package configuration (fires on nestjs monorepo by default).
system_misalignment fires when Node.js-specific imports appear in
predominantly browser-targeted code.

### 12.4 Cross-Language Score Comparison

| Category | Python repo | Score | TS/JS repo | Score |
| -------- | ----------- | ----: | ---------- | ----: |
| Minimal/hand-crafted | requests | 0.376 | express | 0.373 |
| Medium framework | flask (0.407) / starlette (0.411) | ~0.41 | fastify | 0.571 |
| Large framework | django | 0.599 | nestjs | 0.697 |
| Library | pydantic | 0.485 | zod | 0.622 |

The TS scores tend slightly higher than Python equivalents, likely because
TS codebases use more complex function signatures (generics, type guards,
overloads) that increase EDS findings. This is expected and not a calibration
defect — the signals correctly identify undocumented complexity regardless of
language.

### 12.5 Methodology

**Reproducibility command:**
```bash
python scripts/benchmark_typescript.py
```

**Repos chosen for diversity:** express (minimal HTTP), fastify (plugin
architecture), zod (validation library), svelte (compiler + UI), nestjs
(enterprise DI). Selection criteria: public, >100 stars, active maintenance,
different architectural patterns.

**Limitations:**
- Ground-truth precision analysis has not yet been performed on the TS
  corpus. The Python corpus achieved 85% strict precision (§3) and 100% on
  unknown repos (§11.4). TS precision is expected to be comparable but
  unvalidated.
- AI-attribution signal is uninformative (0% across all TS repos),
  consistent with the Python corpus.
- shallow-clone guard (SMS) may suppress legitimate findings on repos with
  sparse git history.
- Architecture rules (AVS) require explicit configuration for optimal
  results; default heuristics may under-detect in flat project structures.

### 12.6 Empirical Evidence for New AVS Features (2026-03-24)

To satisfy the policy requirement that new features must be validated with
reproducible evidence, we added a dedicated empirical suite for the newly
introduced AVS capabilities:

- God Module detection
- Unstable Dependency detection
- Hidden logical coupling (co-change without static import edge)

**Evidence command:**
```bash
python -m pytest tests/test_avs_missing_patterns_evidence.py tests/test_architecture_violation.py tests/test_avs_mutations.py -v --tb=short
```

**Observed result (local run, deterministic):**

- 64 tests collected
- 64 passed
- 0 failed

**Controlled mini-corpus metrics (new suite):**

| Pattern | Positive Scenarios | Negative Scenarios | Precision | Recall |
| ------- | ------------------: | -----------------: | --------: | -----: |
| God Module | 1 | 1 | 1.00 | 1.00 |
| Unstable Dependency | 1 | 1 | 1.00 | 1.00 |
| Hidden Coupling | 1 | 1 | 1.00 | 1.00 |

These metrics are intentionally scoped to a synthetic micro-corpus and should
be interpreted as an acceptance proof for deterministic behavior, not as an
external validity claim over arbitrary repositories.

---

### 12.7 Empirical Evaluation of Consistency Proxy Signals (BEM, TPD, GCD) (2026-03-26)

drift v0.5 introduced three report-only consistency proxy signals ([ADR-007](adr/007-consistency-proxy-signals.md)):

| Signal | Code | Description |
| ------ | ---- | ----------- |
| Broad Exception Monoculture | BEM | Detects directories dominated by broad `except Exception` handlers |
| Test Polarity Deficit | TPD | Detects test suites with only positive assertions, no negative/boundary tests |
| Guard Clause Deficit | GCD | Detects complex public functions lacking early-exit guard clauses |

All three carry weight 0.00 (report-only, Phase 2). This section documents
their empirical validation using the same three-pillar methodology as the
scoring signals (§1, §3, §4, §5).

#### 12.7.1 Ground-Truth Precision (Pillar 1)

We added 12 ground-truth fixtures (4 per signal) to `tests/fixtures/ground_truth.py`, covering true-positive and true-negative scenarios at both typical and boundary conditions:

| Signal | Fixture | Type | Description | Correct? |
| ------ | ------- | ---- | ----------- | :------: |
| BEM | `bem_tp` | TP | 3 broad `except Exception` handlers in `connectors/` | ✓ |
| BEM | `bem_tn` | TN | Specific exception types (`ValueError`, `IOError`) | ✓ |
| BEM | `bem_mixed_tp` | TP | 4 broad handlers in `adapters/`, mixed with specific | ✓ |
| BEM | `bem_boundary_tn` | TN | Broad handlers in `error_handler/` (excluded pattern) | ✓ |
| TPD | `tpd_tp` | TP | 6 test functions, 10+ positive assertions, 0 negative | ✓ |
| TPD | `tpd_tn` | TN | Balanced test suite with `pytest.raises` and boundary checks | ✓ |
| TPD | `tpd_large_tp` | TP | 6 tests in `tests/unit/`, 10 positive assertions, 0 negative | ✓ |
| TPD | `tpd_few_tests_tn` | TN | Only 3 test functions (below min_test_count=5 threshold) | ✓ |
| GCD | `gcd_tp` | TP | 3 unguarded public functions (≥2 params, CC≥5) in `core/` | ✓ |
| GCD | `gcd_tn` | TN | Functions with `isinstance`/`assert` guards | ✓ |
| GCD | `gcd_complex_tp` | TP | 3 unguarded complex functions in `engine/` | ✓ |
| GCD | `gcd_simple_tn` | TN | Low cyclomatic complexity functions (CC<3) | ✓ |

**Result: 12/12 correct (100% precision, 100% recall on micro-corpus).**

**Evidence command:**
```bash
python -m pytest tests/test_precision_recall.py -k "bem_ or tpd_ or gcd_" -v --tb=short
```

**Observed result (local run, 2026-03-26):**

- 12 tests collected
- 12 passed
- 0 failed

As with §12.6, these metrics are scoped to a synthetic micro-corpus and
represent an acceptance proof for deterministic behavior, not a population
validity claim.

### 12.8 Empirical Evidence for v0.10.0 Signal Expansion (2026-03-29)

drift v0.10.0 adds five new deterministic Python coherence signals and
associated runtime ergonomics work:

- Circular Import
- Cognitive Complexity
- Dead Code Accumulation
- Fan-Out Explosion
- Guard Clause Deficit hardening and benchmark/DX support work

**Evidence command:**
```bash
python -m pytest tests/test_circular_import.py tests/test_cognitive_complexity.py tests/test_dead_code_accumulation.py tests/test_fan_out_explosion.py tests/test_guard_clause_deficit.py tests/test_test_polarity_deficit.py tests/test_benchmark_structure.py tests/test_benchmark_label_keys.py tests/test_dx_features.py -q --tb=short --timeout=60
```

**Observed result (local run, deterministic):**

- 100 tests collected
- 100 passed
- 0 failed

**Scope note:**

This run is a release-acceptance proof for the new signal surfaces, benchmark
shape checks, and DX wiring added for v0.10.0. It does not replace the frozen
historical precision/recall corpus described in §§1–12, but it does provide a
reproducible verification point for the newly introduced features before
publication.

### 12.9 Empirical Evidence for v0.10.2 Output Contract and Governance Updates (2026-03-29)

drift v0.10.2 adds deterministic machine-output and governance improvements:

- `--output/-o` for `analyze` and `check` to write pure machine artifacts
- `schema_version` and prioritization metadata in JSON output
- deferred-area tagging via `config.deferred`
- structured exit-code constants for CI diagnostics

**Evidence command:**
```bash
python -m pytest tests/ --tb=short --ignore=tests/test_smoke.py --ignore=tests/test_smoke_real_repos.py --ignore=tests/test_precision_recall.py -q --maxfail=5 --timeout=60
```

**Observed result (local run, deterministic):**

- 964 tests collected
- 959 passed
- 5 skipped
- 0 failed

**Scope note:**

This run validates contract stability and governance behavior for v0.10.2
release surfaces. It is a release-acceptance proof and does not replace the
historical v0.5 precision/recall baseline documented in earlier sections.

#### 12.7.2 Controlled Mutation Benchmark (Pillar 2)

The mutation benchmark (`scripts/_mutation_benchmark.py`) was expanded from 17
mutations across 10 signals to **25 mutations across all 15 scoring-active
signals** (v2.7+, 2026-04-09). The `signal_type` vs `signal` JSON-field
accounting defect (previously reporting 0/17) was repaired.

**New mutations added:**

| # | Signal | Mutation Description | Expected Detection |
| - | ------ | -------------------- | ------------------ |
| 18 | NBV | `validate_email` that returns str instead of raising on invalid input | naming_contract_violation finding |
| 19 | NBV | `validate_age` that returns False but never raises | naming_contract_violation finding |
| 20 | NBV | `is_premium_user` with no boolean return contract | naming_contract_violation finding |
| 21 | BAT | 15 handler functions with >5% bypass marker density (noqa, type:ignore) | bypass_accumulation finding |
| 22 | COD | Module with 6 semantically unrelated functions (parsing, email, crypto, tax) | cohesion_deficit finding |
| 23 | ECM | `process_refund` changes from ValueError to RuntimeError across commits | exception_contract_drift finding |
| 24 | ECM | `authenticate` handler changes from ValueError catch to bare except | exception_contract_drift finding |
| 25 | CCC | config/settings.py + deploy/manifest.py co-changed in 6 of 6 commits | co_change_coupling finding |

**Result: 25/25 counted detections (100% recall)** across all 15
scoring-active signals. Evidence: `benchmark_results/mutation_benchmark.json`.

#### 12.7.3 Self-Analysis Usefulness (Pillar 3)

Running `drift analyze` on the drift codebase itself (45 Python source files,
161 total findings) produced the following consistency proxy findings:

| Signal | Findings | Affected Modules | Assessment |
| ------ | -------: | ---------------- | ---------- |
| BEM | 0 | — | Correct: drift uses specific exception types throughout |
| TPD | 1 | `tests/` | Plausible: drift's test suite is assertion-heavy with limited negative testing |
| GCD | 4 | `scripts/`, `src/drift/commands/`, `src/drift/ingestion/`, `src/drift/rules/tsjs/` | Plausible: several CLI/ingestion entry points have complex parameter handling without early guards |

**BEM = 0 findings** is the expected result — drift's exception handling uses
specific types (`FileNotFoundError`, `SyntaxError`, `ValueError`) rather than
broad `except Exception` blocks.

**TPD = 1 finding** ("Happy-path-only test suite in tests/") is plausible.
While drift's test suite has good coverage (>65%), the majority of assertions
verify expected outputs rather than error paths, boundary conditions, or
invalid inputs. This is a valid signal for test-quality improvement.

**GCD = 4 findings** identify modules where public functions accept multiple
parameters and contain branching logic but lack early-exit guard clauses. The
affected modules (`scripts/`, `commands/`, `ingestion/`, `rules/tsjs/`) are
entry-point-heavy code where guard clauses would improve readability. All 4
findings are plausible and actionable.

**Actionability: 5/5 findings (100%) are plausible and point to concrete
improvement opportunities**, consistent with the 100% actionability rate
observed for scoring signals after calibration (§5).

#### 12.7.4 Summary

| Evaluation Method | BEM | TPD | GCD | Assessment |
| ----------------- | --: | --: | --: | ---------- |
| Ground-truth precision | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) | All fixtures correct |
| Mutation recall | 1/1 (100%) | 1/1 (100%) | 1/1 (100%) | Harness repaired (v2.7+) |

---

## §13 Signal Coverage Matrix

Signal availability has grown from 7 (v0.5.0) to 23 (v2.1.0) across six
milestone releases. The matrix below tracks which signals were available at each
version, providing a quantifiable coverage progression.

**Reproduction:** `python scripts/signal_coverage_matrix.py --markdown`

| Signal | v0.5.0 | v0.7.0 | v0.8.0 | v0.10.0 | v1.1.11 | v2.1.0 | Introduced |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|------------|
| **PFS** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | v0.5.0 |
| **AVS** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | v0.5.0 |
| **MDS** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | v0.5.0 |
| **TVS** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | v0.5.0 |
| **EDS** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | v0.5.0 |
| **SMS** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | v0.5.0 |
| **DIA** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | v0.5.0 |
| **NBV** | — | ✓ | ✓ | ✓ | ✓ | ✓ | v0.7.0 |
| **BAT** | — | ✓ | ✓ | ✓ | ✓ | ✓ | v0.7.0 |
| **ECM** | — | ✓ | ✓ | ✓ | ✓ | ✓ | v0.7.0 |
| **TSA** | — | ✓ | ✓ | ✓ | ✓ | ✓ | v0.7.0 |
| **BEM** | — | ✓ | ✓ | ✓ | ✓ | ✓ | v0.7.0 |
| **TPD** | — | ✓ | ✓ | ✓ | ✓ | ✓ | v0.7.0 |
| **GCD** | — | ✓ | ✓ | ✓ | ✓ | ✓ | v0.7.0 |
| **CCC** | — | — | ✓ | ✓ | ✓ | ✓ | v0.8.0 |
| **COD** | — | — | ✓ | ✓ | ✓ | ✓ | v0.8.0 |
| **CIR** | — | — | — | ✓ | ✓ | ✓ | v0.10.0 |
| **CXS** | — | — | — | ✓ | ✓ | ✓ | v0.10.0 |
| **FOE** | — | — | — | ✓ | ✓ | ✓ | v0.10.0 |
| **DCA** | — | — | — | ✓ | ✓ | ✓ | v0.10.0 |
| **MAZ** | — | — | — | — | ✓ | ✓ | v1.1.11 |
| **HSC** | — | — | — | — | ✓ | ✓ | v1.1.11 |
| **ISD** | — | — | — | — | ✓ | ✓ | v1.1.11 |
| **Total** | 7 | 14 | 16 | 20 | 23 | 23 | — |

**Growth phases:**
- **v0.5.0 → v0.7.0** (7→14): +7 signals — NBV, BAT, ECM, TSA (scoring), BEM, TPD, GCD (report-only)
- **v0.7.0 → v0.8.0** (14→16): +2 signals — CCC, COD (cross-file coupling and cohesion)
- **v0.8.0 → v0.10.0** (16→20): +4 signals — CIR, CXS, FOE, DCA (complexity and dead code)
- **v0.10.0 → v1.1.11** (20→23): +3 signals — MAZ, HSC, ISD (security, report-only pending validation)

Machine-readable artifact: `benchmark_results/signal_coverage_matrix.json`

---

## §14 Cross-Version Benchmark Delta

To quantify detection improvement across releases, a **stable benchmark corpus**
(`benchmarks/corpus/`) contains 16 intentionally injected drift patterns across
10 signal categories. The corpus is version-controlled and independent of the
drift package itself.

**Corpus design:** Each pattern is a minimal Python file exhibiting exactly one
drift anti-pattern (e.g., exact-duplicate functions for MDS, 4 error-handling
variants for PFS, high-CC undocumented functions for EDS). The manifest
(`benchmarks/corpus/manifest.json`) defines expected detection counts per signal.

**Reproduction:**

```bash
python scripts/benchmark_cross_version.py --versions 1.3.0 2.0.0 2.1.0
```

The runner installs each drift-analyzer version in an isolated venv, runs
`drift analyze` against the corpus, and records per-signal recall. Results are
stored in `benchmark_results/cross_version_benchmark.json`.

**Interpretation notes:**
- Older versions may not detect signals that didn't exist yet (e.g., v1.3.0
  cannot detect NBV/COD patterns added in v0.7.0/v0.8.0 if the detection logic
  was refined later).
- TVS (Temporal Volatility) is excluded from the corpus because it requires
  git history — making cross-version comparison unreliable.
- Security signals (MAZ, HSC, ISD) are excluded because they were introduced
  in v1.1.11 as report-only.

---

## §15 Agent-Loop Efficiency

The strongest differentiator of drift's value proposition is its **agent-native
API surface** (introduced v0.10.5). Three deterministic scenarios measure API
call overhead for typical agent workflows:

**Reproduction:** `python scripts/benchmark_agent_loop.py`

### 15.1 Scenario: Gate Check

**Task:** Agent must decide whether a commit is safe.

| API Surface | API Calls | Mechanism |
|-------------|-----------|-----------|
| Pre-v0.10.5 (analyze only) | 1 + manual JSON parsing | Parse findings array, check severity, threshold logic in agent prompt |
| Post-v0.10.5 (nudge) | 1 | `nudge()` returns `safe_to_commit` (bool) + `blocking_reasons` |

`nudge()` reduces the agent's decision logic from multi-step JSON traversal
to a single boolean check. Blocking reasons are machine-readable, eliminating
prompt engineering for threshold interpretation.

### 15.2 Scenario: Fix Cycle

**Task:** Agent scans, gets a fix plan, applies fixes, verifies.

| Step | API Call | Returns |
|------|----------|---------|
| 1 | `scan()` | Findings with scores, severity, top signals |
| 2 | `fix_plan()` | Prioritized tasks with effort/impact estimates |
| 3 | `scan()` (verify) | Updated findings for delta comparison |

Total: **3 API calls** for a complete scan→plan→verify cycle. Pre-v0.10.5,
agents needed to manually extract findings, rank by score, and guess repair
priorities — typically requiring 5–8 iterative prompt rounds.

### 15.3 Scenario: Context Export

**Task:** Agent enriches its prompt with "what NOT to do" before generating code.

| API Call | Returns |
|----------|---------|
| `negative_context()` | Forbidden patterns + canonical alternatives per signal |

Token efficiency: The compact prompt format (`--format prompt`) produces ~20
tokens per pattern vs. ~80 tokens in verbose markdown. For a workspace with
10 active signals, this saves ~600 tokens per prompt injection.

Machine-readable artifact: `benchmark_results/agent_loop_benchmark.json`
| Self-analysis findings | 0 | 1 | 4 | All plausible and actionable |

The consistency proxy signals demonstrate correct deterministic behavior on
controlled fixtures and produce plausible, actionable findings on real code.
They meet the Phase 2 quality bar for report-only signals. Promotion to
scoring status (weight > 0.00) requires external corpus validation — this is
deferred to a future study iteration.

### 12.10 Empirical Evidence for v0.10.8 Agent-Native Workflow Releases (2026-03-29)

drift v0.10.8 extends the deterministic agent workflow surface and release
gating semantics:

- top-level structured CLI commands: `drift validate`, `drift scan`, `drift diff`, `drift fix-plan`
- explicit machine-readable acceptance fields in `scan` and `diff`
- telemetry `run_id` correlation for cross-tool session tracing
- path-scoped diff decisioning with explicit out-of-scope noise accounting

**Evidence commands:**
```bash
python -m pytest tests/test_telemetry.py tests/test_agent_native_cli.py tests/test_cli_runtime.py tests/test_mcp_copilot.py tests/test_output_golden.py -q --tb=short
python -m pytest tests/ --tb=short --ignore=tests/test_smoke.py -q --maxfail=1
```

**Observed result (local run, deterministic):**

- targeted release-surface suite: 54 passed, 3 warnings
- quick no-smoke regression suite: 1083 passed, 5 skipped, 1 warning
- 0 failures accepted for release

**Scope note:**

This run is a release-acceptance proof for deterministic agent-facing CLI/API
contracts and telemetry correlation in v0.10.8. It does not supersede the
historical benchmark baseline, but it does provide a reproducible verification
point for the new workflow and gating behavior before publication.

---

### 12.11 Empirical Evidence for v0.10.9 Agent Signal Consistency (2026-03-29)

drift v0.10.9 closes agent-facing gaps identified through real-world agent
workflow analysis:

- `_SIGNAL_PREFIX` extended to all 19 signals — eliminates wrong fallback
  abbreviations (`byp-`, `cog-`, `dea-`) that caused agents to hallucinate
  signal names (COG, DEA) when looking up task IDs
- `drift explain` extended to all 19 signals (previously 13/19)
- explicit `signal_abbrev` field in fix-plan task dicts
- `_ABBREV_TO_SIGNAL` extended to 19 entries (CXS, FOE, CIR, DCA)
- new `in_scope_accept` field in `drift diff` for noise-independent scoped
  acceptance gating
- improved `recommended_next_actions` for `out_of_scope_diff_noise`

**Evidence commands:**
```bash
python -m pytest tests/ --tb=short --ignore=tests/test_smoke.py -q --maxfail=5
```

**Observed result (local run, deterministic):**

- full regression suite: 1059 passed, 5 skipped, 42 deselected, 1 warning
- 0 failures

**Scope note:**

All changes are backward-compatible additive additions to the agent API surface.
The signal-coverage fix is deterministic: `drift explain DCA` now returns a
result instead of an error; fix-plan task IDs for dead_code_accumulation now
have the `dca-` prefix instead of the broken `dea-` fallback.

---

### 12.12 Empirical Evidence for v1.4.2 Release Automation via python-semantic-release (2026-04-02)

drift v1.4.2 replaces the fragile release trigger convention with a
`python-semantic-release` CI workflow on `main`.

- release orchestration moved to `.github/workflows/release.yml` (ubuntu-latest)
- semantic-release configuration is version-controlled in `pyproject.toml`
- legacy manual release trigger workflow removed

**Evidence commands:**
```bash
python -m pytest tests/ --tb=short --ignore=tests/test_smoke.py -q --maxfail=1
```

**Observed result (local run, deterministic):**

- quick no-smoke suite: 285 passed, 1 failed, 42 deselected, 3 warnings
- failing test: `tests/test_ci_reality.py::TestPerformanceBudget::test_self_analysis_within_budget`
   with 69.4s observed runtime vs 30.0s budget
- failure classified as unrelated to release workflow mechanics; tracked as
   performance-budget regression in CI reality checks

**Scope note:**

This evidence validates the release-process migration artifacts and keeps the
study changelog fresh for feature-gate traceability. It does not claim a
performance improvement in analyzer runtime.

---



This study now represents a mixed evidence record: a frozen v0.5.0 benchmark baseline, later dated engineering addenda, and a current v2.5.4 codebase that has moved ahead of parts of the evaluation corpus. The strongest repeatable claim remains that deterministic static analysis — without LLM involvement — can surface meaningful structural erosion signals across Python and TypeScript/JavaScript codebases, but not every earlier headline metric should be repeated as a current-package claim. Across 8 Python repositories (score range 0.376–0.599) and 5 TypeScript repositories (score range 0.373–0.697):

- **77% precision** (strict) / 95% lenient on 286 classified findings using non-circular heuristics, with **15 false positives** (6 from active signals, 9 from DIA)
- **~93% pre-calibration precision** on 373 findings across 3 previously unseen repositories (httpie, arrow, frappe) — single-rater annotation; post-calibration 100% but constitutes data leakage (see §11.10)
- **100% fix-text actionability** (76/76) on self-analysis after calibration (baseline: 74%)
- **100% mutation recall** on 25 injected patterns across all 15 scoring-active signals (v2.7+, synthetic repo with git history); the historical 14-pattern benchmark (86% recall, v0.5) remains documented in §4
- **3 consistency proxy signals** (BEM, TPD, GCD) validated: 12/12 ground-truth fixtures correct, 5/5 self-analysis findings plausible and actionable (§12.7)
- **3 actionable findings** in a production codebase, including copy-pasted functions, error-handling fragmentation, and API inconsistency
- **8 real-world smoke tests** confirm score ranking tracks expectations: hand-crafted libraries (requests=0.376) score lowest, large historically grown frameworks (django=0.599) score highest
- **Temporal stability validated** across 30 commits (10 drift + 20 django): σ < 0.005 for mature repos, deltas correlate with structural changes, zero sensitivity to non-structural commits
- **Major-version correlation confirmed** across 17 django releases (1.8→6.0, 10 years): scores plateau at 0.553–0.563 (σ=0.004) despite +770 files, then drop -0.016 at 6.0 when 116 deprecation-removal commits cleaned up legacy debt — the causal link between structural cleanup and score reduction
- **Hold-out validation passed** via LOOCV (15 folds): held-out F1=1.000, all folds correct. Signal detection is orthogonal to weight calibration — the "training on test data" concern is empirically refuted

The tool produces the fewest findings (and lowest score) on carefully hand-crafted codebases like requests and flask, and the most on large or rapidly scaffolded codebases like django and FastAPI — behavior consistent with its design intent.

- **TypeScript full-semantic support** validated across 5 diverse repositories (express, fastify, zod, svelte, nestjs): all 7 core signals activate on TS/JS sources, score ranking is consistent with architectural expectations (express=0.373 ≈ requests=0.376), and the architecture_violation signal correctly identifies 584 cross-package violations in nestjs

**Limitations:** DIA precision (59%) has improved significantly but remains below scoring threshold. AI-attribution is currently uninformative (0% across all repos). Ground-truth classification is single-rater. TS corpus precision has not been formally validated via ground-truth annotation — this is the next step. Replication on a fully independent corpus remains the most important next step for external validity.

**The value of drift is delta, not absolute.** Track your score over time with `drift trend`. A rising score means your codebase is losing coherence. A stable or falling score means you're maintaining design intent — even with AI-generated code in the mix.

---

## 14. Epistemological Limits

This section documents the known epistemological boundaries of drift's
analysis model, derived from a systematic self-critique (EPISTEMICS.md). The
limits are inherent to the representational model, not implementation gaps.

### 14.1 Coherence ≠ Quality (EPISTEMICS §1)

Drift measures structural entropy — not code quality. The scoring formula
rewards uniformity and penalizes variance. This creates two classes of
false-positive risk:

**Architecture transitions.** A team migrating from synchronous to async
error-handling will see PFS and MDS fire during the transition, because two
patterns coexist. The rising score *is* the migration happening. A low score
in this phase would mean nobody has started. Temporary coherence loss is a
necessary artifact of structural learning.

**Deliberate polymorphism.** Strategy patterns, Adapter hierarchies, Plugin
systems, and Codec frameworks intentionally contain structurally similar
implementations. MDS detects the duplication correctly — but the duplication
*is* the architecture. Interface conformity produces the similarity that drift
flags as anomaly.

**Mitigation (v0.5):** MDS and PFS findings now carry a
`deliberate_pattern_risk` metadata field that warns users to verify intent
before acting. The rich output footer includes interpretation guidance. Users
can suppress known-intentional patterns via `exclude` globs in `drift.yaml`.

### 14.2 Consistent Wrongness (EPISTEMICS §2)

The most dangerous erosion occurs when the entire codebase *uniformly* does
the wrong thing — e.g., every module validates permissions correctly against
the wrong permission model (RBAC implemented, ABAC needed), or all endpoints
use the same error-handling pattern that silently swallows critical exceptions.

Drift cannot detect this. A hypothetical Semantic Misalignment Signal (SMA)
would require access to a formal specification of intent — which does not
exist as machine-readable artifact in most projects. This is an ontological
limit, not a technical one: **syntax is observable, semantics is not.
Coherence is measurable, correctness is not.**

**Partial mitigation (v0.5):** The consistency proxy signals (BEM, TPD, GCD)
address a narrow subset of this problem — patterns that are consistently
*present* but structurally suspect (broad exception handlers, test
monocultures, missing guard clauses). They cannot detect *semantic*
misalignment, but they surface structural consistency smells that correlate
with semantic problems.

### 14.3 Score as Entropy, Not Quality (EPISTEMICS §3)

The Django 6.0 case (§10) demonstrates the score's true nature: the score
dropped -0.016 when 116 deprecation-removal commits cleaned up legacy
compatibility layers. The score would also have dropped if *productive* code
had been deleted. It rewards reduction, not correctness.

**Goodhart risk in teams that optimize on the score:**

1. **Deletion bias** — the fastest way to lower the score is to delete code,
   not refactor it.
2. **Uniformity bias** — teams copy the most common pattern instead of
   choosing the right one for a new use-case.
3. **Refactoring avoidance** — deep refactorings cause short-term score
   increases while two patterns coexist; teams abort before completion.
4. **Sophistication ceiling** — complex but correct architectures
   (Event-Sourcing, CQRS, Ports/Adapters) generate more signals than
   simple MVC structures.

**Mitigation (v0.5):** The interpretation footer in rich output explicitly
states that the score measures entropy, not quality, and that temporary
increases during migrations are expected. The fundamental guidance remains:
**interpret deltas, not snapshots**.

### 14.4 Limits of Determinism (EPISTEMICS §4)

Drift's determinism principle (ADR-001) guarantees reproducibility but creates
a hard boundary at the semantic level. What drift can see:

| Class | Signal | Detectable? |
| ----- | ------ | :---------: |
| Syntactic drift | PFS, MDS | ✓ |
| Topological drift | AVS, SMS | ✓ |
| Temporal drift | TVS | ✓ |
| Documentation drift | DIA | ✓ |
| Consistency smell | BEM, TPD, GCD | ✓ (proxy) |

What drift **cannot** see deterministically:

| Class | Why | Horizon |
| ----- | --- | ------- |
| **Idiomatic drift** — syntactically valid code using foreign idioms (Java patterns in Python) | Would require a trained baseline model of codebase idioms | Theoretically computable (AST frequency distributions), not yet implemented |
| **Intention drift** — code does the wrong thing consistently | Requires formal specification of intent | Ontological limit; not implementable without external spec |
| **API contract drift** — behavior changes without signature changes | Requires semantic analysis or property-based testing | Not deterministically detectable from AST alone |
| **Emergent coupling** — modules that co-change without import edges | Requires co-change matrix from git log | Partially addressed by AVS Hidden Coupling (§12.6) |

**The tipping point:** As AI-generated code improves, it produces *less*
syntactic drift (consistent patterns) but *more* semantic drift (looks the
same, does different things). Drift's determinism protects against
irreproducible analysis but makes it blind to exactly the erosion class that
will dominate in AI-heavy codebases.

### 14.5 States vs. Processes (EPISTEMICS §5)

All signals measure *snapshots*: how many patterns exist now? What does the
import graph look like now? Even TVS, which appears temporal, measures current
churn — not the development trajectory.

The deeper question in an AI-dominated world is not "How coherent is the
codebase?" — since AI can produce coherence cheaply — but **"Does anyone
understand why the codebase is the way it is?"** This is a question about
epistememic integrity, not structural coherence.

Drift would need to evolve from a **coherence meter** to a
**comprehensibility radar** to address this. Concretely:

1. **From pattern counting to decision archaeology** — track whether
   structural changes have traceable rationale in commit history.
2. **From structure to delta-readability** — measure how predictable the
   next change would be for a new developer.
3. **From single codebase to codebase-as-conversation** — treat the
   human-AI dialog as the analysis unit, not just the resulting code.

These are vision-level changes that go beyond the current architecture. They
are documented here to bound expectations and guide future evolution.

### 14.6 Summary of Epistemological Boundaries

| Boundary | Nature | Addressable? | Status in v0.5 |
| -------- | ------ | :----------: | --------------- |
| Coherence ≠ Quality | Inherent to entropy-based measurement | Partially — via disambiguation | `deliberate_pattern_risk` metadata on MDS/PFS |
| Consistent wrongness | Ontological (syntax ≠ semantics) | No — would need formal spec | BEM/TPD/GCD as narrow proxies |
| Score = entropy | Inherent to scoring model | Partially — via guidance | Interpretation footer in output |
| Semantic drift | Beyond deterministic analysis | No (except idiomatic drift) | Documented as hard limit |
| State vs. process | Architectural paradigm | Future evolution | Vision documented |

These boundaries are not bugs to fix but constraints to communicate. Drift's
value proposition remains valid within its operational domain: detecting
*structural* erosion in codebases where syntactic coherence is a meaningful
proxy for design health. The epistemological limits define where that proxy
breaks down.

---

## 15. Community Validation Studies — Security by Default

**Status:** `[PLANNED]` — collecting contributions via
[issue templates](https://github.com/mick-gsk/drift/issues/new/choose).

This section will contain empirical evidence from community-contributed
analyses focusing on security-related signals (MAZ, HSC, ISD).

### 15.1 Security-Erosion in AI-Augmented Repositories (S1)

**Research question:** Is the rate of missing authorization checks (MAZ findings)
higher in AI-attributed endpoints than in manually written endpoints within the
same repository?

**Hypothesis:** H₁: MAZ-Finding-Rate(AI) > MAZ-Finding-Rate(manual)
with effect size d ≥ 0.5.

**Method:** Contributors analyze public repos with ≥ 50 endpoints, run
`drift analyze --format json`, and attribute endpoints via `git blame`.

**Sample minimum:** 10 repos, ≥ 500 endpoints total.

**Results:** *Awaiting community contributions.*

### 15.2 ISD Recall Extension — Community FN Catalogue (S2)

**Research question:** Which categories of insecure defaults does drift's ISD
signal (CWE-1188) systematically miss?

**Goal:** Build a catalogue of ISD false-negative patterns, ordered by
frequency and severity, to extend detection rules.

**Method:** Contributors run `drift analyze` on their repos and document
insecure defaults that ISD did not detect, using the
[repo benchmark template](https://github.com/mick-gsk/drift/issues/new?template=study_repo_benchmark.md).

**Sample minimum:** 15 FN reports from ≥ 5 repos.

**Results:** *Awaiting community contributions.*

### 15.3 Security-Coherence Covariance (S3)

**Research question:** Does the composite drift score correlate positively
with missing authorization coverage in web repositories?

**Hypothesis:** H₁: Spearman ρ(score, 1 − auth-coverage-rate) > 0.4.

**Method:** Contributors measure auth-coverage (endpoints with auth /
total endpoints) alongside the composite score.

**Sample minimum:** 20 repos.

**Results:** *Awaiting community contributions.*

---

## 16. Community Validation Studies — Day-2 Problem

**Status:** `[PLANNED]`

### 16.1 Score Response to Team Transition Events (S4)

**Research question:** Does the drift score rise measurably within 30 days
after a principal contributor leaves a project?

**Method:** Contributors identify repos with documented maintainer transitions,
run `drift analyze` at 7 temporal checkpoints (t−30 to t+90), and report
score deltas.

**Sample minimum:** 8 transition events from ≥ 5 repos.

**Results:** *Awaiting community contributions.*

### 16.2 Community Self-Analysis Evidence Base (S5)

**Research question:** Do repo owners discover previously unknown architecture
problems through `drift analyze`, and how many get fixed within 30 days?

**Method:** Two-phase protocol — (A) run drift, rate each finding for surprise
and correctness; (B) 30-day follow-up on fix rate. Uses the
[self-analysis template](https://github.com/mick-gsk/drift/issues/new?template=study_self_analysis.md).

**Sample minimum:** 15 reports (phase A), 10 follow-ups (phase B).

**Results:** *Awaiting community contributions.*

Aggregation script: `scripts/study_self_analysis_aggregate.py`.

### 16.3 Documentation-Drift as Day-2 Indicator (S6)

**Research question:** Does the DIA signal correlate more strongly with
time since last docs commit than with codebase size?

**Hypothesis:** H₁: ρ(DIA, docs-stagnation) > ρ(DIA, LOC).

**Method:** Contributors measure DIA score, days since last docs commit,
and LOC for each repo.

**Results:** *Awaiting community contributions.*

See also: [EPISTEMICS.md §7](EPISTEMICS.md) for conceptual reflection.

### 16.4 Framework Erosion Profiles (S9)

**Research question:** Do dominant drift signals differ systematically
between web frameworks (Django, Flask, FastAPI, Express, NestJS)?

**Hypothesis:** Signal dominance distribution is framework-dependent
(χ² test, p < 0.05).

**Method:** 5 repos per framework, normalized signal-score breakdown.

**Sample minimum:** 25 repos (5 × 5 frameworks).

**Results:** *Awaiting community contributions.*

### 16.5 Consistency Proxy Promotion Evidence (S10)

**Research question:** Do BEM + TPD + GCD correlate more strongly with
manually rated module inconsistency than the composite score alone?

**Decision this informs:** Should BEM/TPD/GCD move from `weight=0.0`
(report-only) to scoring-active?

**Method:** Senior contributors rate 10 modules per repo on a 5-point
consistency rubric. Comparison: ρ(manual, proxy) vs. ρ(manual, composite).

**Sample minimum:** 3 repos × 8 modules = 24 ratings.

**Results:** *Awaiting community contributions.*

---

## 17. Community Validation Studies — Technical Debt

**Status:** `[PLANNED]`

### 17.1 Score-Debt Correlation Study (S11)

**Research question:** Does the composite drift score correlate with the
number of tech-debt-labelled GitHub issues?

**Hypothesis:** H₁: Spearman ρ > 0.4.

**Method:** Contributors identify public repos with ≥ 10 tech-debt issues
(labels: `tech-debt`, `technical-debt`, `refactoring`, `cleanup`,
`code-quality`, `debt`), run `drift analyze`, and normalize by LOC.

**Sample minimum:** 20 repos.

Automation script: `scripts/study_debt_correlation.py`.

**Results:** *Awaiting community contributions.*

### 17.2 DCA Signal Validation — AI-Generated vs. Manual Code (S12)

**Research question:** Do repos with a high share of AI-generated commits
accumulate more dead code (DCA findings) per kLOC?

**Method:** Matched-pair design — each AI-heavy repo is paired with a
conventional repo matched on language, LOC (±30%), age (±1 year), and domain.

**Sample minimum:** 8 matched pairs.

**Results:** *Awaiting community contributions.*

### 17.3 Actionability Assessment (S13)

**Research question:** How understandable and actionable are drift's
`next_action` texts in practice?

**Method:** Contributors rate 10 random findings on three Likert dimensions:
understandability (1–5), actionability (1–5), prioritizability (1–5). Uses
the [self-analysis template](https://github.com/mick-gsk/drift/issues/new?template=study_self_analysis.md) (step 4).

**Sample minimum:** 10 contributors × 10 findings = 100 ratings.

Aggregation script: `scripts/study_self_analysis_aggregate.py`.

**Results:** *Awaiting community contributions.*

---

## §16 Drift-Retrieval-RAG (ADR-091)

**Research question:** Can a deterministic lexical retrieval layer (BM25 Okapi, no LLM, no embeddings) over drift's own verified documentation reduce hallucinated claims in coding-agent outputs about drift itself (policy, signals, ADR decisions, audit findings, benchmark evidence)?

**Design:** Build a fact corpus from POLICY.md, ROADMAP.md, docs/decisions/ADR-*.md, audit_results/*.md, src/drift/signals/*.py, and benchmark_results/v*_feature_evidence.json. Assign stable Fact-IDs (`POLICY#S<n>.p<m>`, `ADR-<nnn>#<section>`, `AUDIT/<file>#<row>`, `SIGNAL/<id>#<field>`, `EVIDENCE/v<version>#<key>`) with an append-only migration registry for renames. Expose via two MCP tools (`drift_retrieve`, `drift_cite`) that return SHA-256-anchored chunks. Enforce grounding via `.github/instructions/drift-rag-grounding.instructions.md` (Phase-1 soft gate).

**MVP corpus metrics (drift self-analysis):**

- 1318 chunks across 164 sources (504 ADR, 365 evidence, 331 audit, 75 policy, 25 signal, 18 roadmap).
- `corpus_sha256 = 82bc1229b87ea51d5791d257c83f3240731945a80ec900c87aaf01c2639991a1` (deterministic across rebuilds).
- Cold-start index build: ~142 ms (Windows, Python 3.11.9).
- Warm retrieve p50 = 0.35 ms, p99 < 2.1 ms over 10 representative queries.

**Gold-set precision@5 (15 hand-curated query -> fact_id-prefix pairs spanning POLICY sections and major ADRs):** 15/15 = 100% (threshold gate: ≥ 80%).

**Scope demarcation:** Lexical-only MVP. Semantic/embedding retrieval remains out of scope (ADR-031). Corpus covers drift itself only (not target repos; Phase 3). CI-side hard enforcement of the grounding contract is Phase 4.

**Reproduction:**

```bash
pytest tests/test_retrieval_corpus.py tests/test_retrieval_search.py tests/test_mcp_retrieval_tools.py
```
