## [Unreleased]

### Added

- **Defect corpus benchmark**: ground-truth fixture set and recall benchmark (`scripts/defect_corpus_benchmark.py`, `benchmarks/defect_corpus/`, `benchmark_results/defect_corpus_recall.json`) for externally validated signal recall measurement.
- **Drift skills**: add `brainstorming`, `systematic-debugging`, `test-driven-development`, and `writing-plans` skill files under `.github/skills/` for structured agent workflows.

### Fixed

- **Async MCP session loop resolution modernized (#487)**: `run_session_start()` in `mcp_router_session` now uses `asyncio.get_running_loop()` (statt `get_event_loop()`) im `async def`-Kontext, damit Autopilot-Pfade unter Python 3.12+ ohne Deprecation-Regression stabil bleiben; ein Regressionstest verhindert Rueckfall.
- **`drift_fix_plan` Router-Fast-Path pending-Filter korrigiert (#486)**: `_session_fix_plan_fast_response()` in `mcp_router_repair` nutzt jetzt `session.queue_status()`-Semantik, sodass `claimed`- und `failed`-Tasks nicht mehr fälschlich als `pending` ausgeliefert werden; die vollständigen Task-Payloads aus `selected_tasks` bleiben dabei erhalten.
- **`drift_fix_plan` Fast-Path Profile-Konsistenz (#485)**: Die zulässigen Profile für den Session-Queue-Fast-Path sind nun explizit dokumentiert (`None`, `planner`, `coder`) und per Regressionstest abgesichert; `verifier` bleibt korrekt im API-Fallback-Pfad statt Cache-Hit.
- **Kanonisches `finding_id` über Scan/Status-Surfaces (#479)**: `finding_rendering._finding_concise()` und `finding_rendering._finding_detailed()` emittieren jetzt zusätzlich `finding_id` als kanonischen stabilen Identifier; `fingerprint` bleibt als Rueckwaertskompatibilitaets-Alias erhalten. Dadurch funktionieren cross-surface Deduplizierung und Agent-Pipelines (`scan -> diff -> status`) ohne feldspezifische Sonderbehandlung.
- **`drift ci --format junit|llm` missing deprecation warnings (#477)**: `ci._emit_output()` now emits the same `DeprecationWarning` and stderr migration guidance as `analyze`/`check` when deprecated `junit` or `llm` formats are used.
- **Konsistente Zeilenfelder in Finding-Serialisierung (#478)**: `finding_rendering._finding_concise()` emittiert jetzt zusätzlich `start_line` und `end_line`; `finding_rendering._finding_detailed()` emittiert zusätzlich den Alias `line`. Dadurch können Agent-Workflows über concise/detailed hinweg stabil auf dieselben Line-Keys zugreifen.
- **`drift export-context --write` emits confirmation on stderr (#476)**: write-mode success text now uses stderr (`click.echo(..., err=True)`) so stdout remains clean for machine-readable payloads and command-substitution workflows.
- **External integrations not wired into pipeline**: `drift init` and the analysis pipeline now discover, validate, and execute registered external integrations via the new `src/drift/integrations/` package (`base.py`, `registry.py`, `runner.py`) and the built-in `superpowers` integration. Integration configuration is declared under a new `integrations:` key in `drift.yaml` and validated at load time.
- **`drift validate` exit code contract when `valid=false` (#474)**: the `validate` CLI command now exits with `EXIT_CONFIG_ERROR` (`2`) when `api.validate()` reports an invalid preflight result, while still emitting the JSON payload to stdout or `--output`.
- **`_task_graph_critical_path()` empty-input crash and non-deterministic tie-breaking (#393)**: direct calls with an empty `sorted_ids` list now return `[]` instead of raising `ValueError`; tie-breaking among leaf nodes with equal `dist` values now uses the lexicographically smallest task ID for deterministic `critical_path` output across runs.
- **`load_baseline()` silently ignores stored `drift_version` (#394)**: `load_baseline()` now reads the `drift_version` field from the baseline JSON and emits a `WARNING`-level log message when the stored version differs from the running version, prompting the user to regenerate the baseline. Baselines without a `drift_version` field (legacy files) are accepted without warning. No breaking behaviour change.
- **Signal exception surfacing in precision evaluation (#369)**: `run_fixture` previously swallowed all signal exceptions with a bare `except Exception: pass`. Exceptions are now caught, formatted with a traceback, and emitted as both a `RuntimeWarning` and an `AnalyzerWarning` so callers can observe and triage failing signals.
- **Newlines in GitHub Actions annotations (#388)**: `findings_to_github_annotations()` now `%0A`-encodes embedded newlines in `description` and `fix` before building the `::error …::` command string, preventing broken multi-line annotations in the Actions log.
- **Missing signal labels in rich output (#389)**: `_SIGNAL_LABELS` in `rich_output.py` was missing entries for `PHANTOM_REFERENCE`, `TYPE_SAFETY_BYPASS`, `FAN_OUT_EXPLOSION`, `COGNITIVE_COMPLEXITY`, `CIRCULAR_IMPORT`, and `DEAD_CODE_ACCUMULATION`, causing raw signal IDs to appear in the findings table instead of formatted `ABBR · Short Name` labels. All six entries added to `_SIGNAL_LABELS`; `TSB` (Type Safety) also added to `_SIGNAL_SHORT_NAMES`.
- **`_task_graph_topological_sort` O(n²) and non-determinism (#391)**: Replaced `queue.sort()` + `list.pop(0)` (O(n² log n)) with `heapq` (O(n log n)). Initial queue is now `sorted(…)` + `heapify`, children are iterated in sorted order, so `execution_phases` is identical for the same task set regardless of the input list order.
- **`extends: vibe-coding` crash (#382)**: `_apply_extends` injected `profile.guided_thresholds` as `thresholds.guided`, but `ThresholdsConfig` has `extra="forbid"` and no `guided` field, causing `DriftConfigError [DRIFT-1001]`. Fix promotes `guided_thresholds` to a first-class `GuidedThresholds | None` field on `DriftConfig`; `_apply_extends` now sets it at the top level. All profiles with non-empty `guided_thresholds` (currently: `vibe-coding`) are now usable via `extends:`.

## [2.11.0] - 2026-04-16

Short version: Configurable scoring thresholds, context-aware finding prioritization, and a wave of precision and stability fixes.

### Added

- **Configurable scoring thresholds (#371)**: `dampening_k`, `breadth_cap`, and `grade_bands` are tunable via a new `scoring:` section in `drift.yaml`; optional `feedback_blend_alpha` blends auto-calibration weights with persisted feedback.
- **Context-aware finding prioritization (#370)**: findings are now ranked by operational context signals so the most actionable items surface first in agent and CLI output.

### Fixed

- **`load_baseline()` version mismatch warning (#394)**: `load_baseline()` now emits a `WARNING` when the stored `drift_version` differs from the running version; legacy baselines without the field are accepted silently.
- **`extends: vibe-coding` crash (#382)**: `_apply_extends` now sets `guided_thresholds` at the top-level `DriftConfig` field instead of injecting it into the forbidden `thresholds.guided` key.
- **Stability hardening**: guard empty-input crash in `_task_graph_critical_path`, fix heapq sort in `_task_graph_topological_sort`, `%0A`-encode newlines in GitHub Actions annotations, and fix missing rich-output signal labels for PHR/TSB/FOE/CXS/CIR/DCA.

## [2.10.1] - 2026-04-14

Short version: Patch release — fix context_dampening default comment, harden CLI output, config show onboarding, and Windows console encoding fallback.

### Fixed

- Correct `context_dampening` default comment in `drift.example.yaml` (#384).
- Harden finding context path handling for edge cases.
- Prioritize operational agent context in finding triage output.
- Improve `drift config show` onboarding summary.
- Harden Windows CLI output fallback to ASCII-safe borders and symbols.

## [2.10.0] - 2026-04-14

Short version: Add verify and interactive init flows, trend JSON output, fix-plan dismissal support, and configurable scoring thresholds.

### Added

- Add `drift verify`, `drift init --interactive`, `drift trend --json`, and fix-plan dismissal support for safer agent workflows.
- **Configurable scoring thresholds (#371)**: `dampening_k`, `breadth_cap`, and `grade_bands` are now tunable via the new `scoring:` section in `drift.yaml`. Optionally blend `auto_calibrate_weights()` output with persisted feedback using `scoring.feedback_blend_alpha` (requires `calibration.enabled: true`). All defaults preserve existing behavior.

### Changed

- Refactor shared analysis/config internals and improve feedback visibility plus `nudge` warm-up guidance.

### Deprecated

- Begin deprecating older setup, format, MCP, and calibration paths in favor of the newer init and calibration flows.

### Fixed

- **MCP client-disconnect handling (#376)**: All `_run_api_tool`, `drift_feedback`, and `drift_map` worker-thread calls now pass `abandon_on_cancel=True` to `_run_sync_in_thread`. When an MCP client disconnects mid-call, the async coroutine receives `CancelledError` immediately instead of blocking the event loop while the worker thread completes. Session-state mutations (e.g. `session.last_scan_score`, `session.touch()`) are correctly skipped because `CancelledError` propagates past all `except Exception` handlers; this prevents half-applied session state after orphaned tool calls.
- **MCP enum validation at tool boundary (#375)**: `drift_scan`, `drift_diff`, `drift_verify`, and `drift_fix_plan` now validate `response_detail`, `response_profile`, `fail_on`, and `automation_fit_min` at the MCP tool entry point. Invalid values immediately return a structured `DRIFT-1003` error with `invalid_fields` and `suggested_fix` instead of propagating failures from deep internal call frames. A shared `_validate_enum_param` helper centralises the pattern already used by `drift_session_start`.
- Preserve the literal MCP install hint in drift init output so onboarding shows drift-analyzer[mcp] correctly.
- **Session mutable input isolation (#373)**: `SessionManager.create` and `SessionManager.update` now defensively copy all caller-supplied list arguments (`signals`, `exclude_signals`, `exclude_paths`, `selected_tasks`, `completed_task_ids`, `last_scan_top_signals`, `guardrails`). External mutation of the original lists after a create or update call no longer affects the stored session state, preventing cross-session bleed in MCP multi-agent workflows.
- Make `drift config show` print a newcomer-friendly overview of the active profile, globs, non-defaults, and recommended next command while keeping YAML-only output available via `--raw`.
- Resolve adaptive recommendation typing and add managed inline suppression tooling for ignore comments.
- Reject duplicate abbreviation registrations in `register_signal_meta` with a `ValueError` instead of silently overwriting core signal mappings (#368).
- Fix `BaselineManager._git_state_changed` bypass TTL cache on the invalidation path so rapid HEAD changes within the 5-second window are no longer silently hidden by a stale cached git state (#372).
- **Graceful parser degradation in IngestionPhase (#374)**: A single parse-worker exception no longer aborts the entire ingestion phase. Failures are now caught per-file, recorded as a `parser_failure` degradation event, and the affected file is replaced with an empty `ParseResult` carrying the error in `parse_errors`; the rest of the repository continues to be analyzed normally.

## [2.9.16] - 2026-04-13

Short version: Harden copilot-autopilot risky-edit completion with fix-intent contracts, shadow-verify, and repair-template registry evidence.

### Added

- Add `fix_intent` normalization plus serialized task contracts for deterministic risky-edit handling (ADR-063).
- Add `drift_shadow_verify` and shadow-verify task metadata/evidence for cross-file-risky edit kinds (ADR-064).
- Add repair-template registry seed data and coverage matrix generation for template confidence and regression guidance (ADR-065).

### Changed

- Agent-task payloads now carry shadow-verify scope, completion-evidence wiring, and richer verify plans for risky edits.

### Fixed

- Prevent false-safe completion verdicts by requiring shadow verification for risky cross-file edit kinds before merge decisions.

## [2.9.13] - 2026-04-12

Short version: Introduce output format expansion (pr-comment, junit, llm, ci, gate, completions), signal clarity hardening, and actionability improvements across 24 signals.

### Added
- Six new output formats: `--format pr-comment`, `--format junit`, `--format llm`, `drift ci`, `drift gate` alias, and `drift completions` for shell tab-completion.
- Signal clarity improvements via ADR-048–ADR-052: EDS private-function recall guard, PFS canonical code snippet, AVS blast-radius churn guard, and CCC commit-context test template.

### Changed
- SARIF rule `help` field populated from `generate_recommendation()`; CSV gains `signal_label` column (breaking: column indices ≥ 2 shift by 1).

### Fixed
- Actionability hardening across CXS, TVS, AVS, DCA, MAZ, TSB, and PHR to reduce false positives on test files, passive definition modules, and published-package exports.
- Convert all relative `docs-site/` and `docs/` links in README.md to absolute URLs so banner image, GIF, and documentation links render correctly on PyPI.

## [2.9.8] - 2026-04-12

Short version: Introduce calibration hardening and signal quality improvements for AVS, DIA, and MDS.

### Added
- Consolidate AVS, DIA, and MDS quality hardening with updated thresholds and calibration support.
- Extend feedback tooling and calibration workflow, including new automation script support.
- Refresh golden snapshots and ground-truth fixtures for regression-safe behavior checks.
- Add ADR coverage and risk-audit updates for the affected signal and ingestion changes.

## [2.7.2] - 2026-04-09

Short version: Align release metadata so release-discipline checks pass.

### Changed

- Align top changelog release marker with project version `2.7.2` in `pyproject.toml`.

## [2.7.1] - 2026-04-09

Short version: Align release metadata so release-discipline checks pass.

### Changed

- Align top changelog release marker with project version `2.7.1` in `pyproject.toml`.

## [2.7.0] - 2026-04-09

Short version: Signal-filtering for scan, cross-validation fields, and false-positive reductions across multiple signals.

### Added

- Add `--exclude-signals` and `--max-per-signal` options to `drift scan` and the MCP `drift_scan` tool so callers can suppress dominant signals or cap per-signal finding counts.
- Harmonize scan finding fields (`signal_abbrev`, `signal_id`, `severity_rank`, `fingerprint`) and a `cross_validation` block across all scan output formats for stable agent correlation.

### Fixed

- Reduce DIA false positives for bootstrap-sized repositories and improve recall for AVS, MAZ, BEM, NBV, and ECM on large or src-root repository shapes.
- Suppress HSC false positives for OpenTelemetry semantic-convention constants, natural-language error messages, and OAuth endpoint URL literals.

## [2.4.5] - 2026-04-05

Short version: Restore release-discipline consistency after the automated patch release.

### Changed

- Align top changelog release metadata with project version `2.4.5` so release-discipline gates stay green.

## [2.4.4] - 2026-04-05

Short version: Align release metadata with current project version.

### Changed

- Sync top changelog release marker to 2.4.2 so release-discipline checks match [project] version in pyproject.toml.

## [2.1.3] - 2026-04-02

Short version: Keep release metadata aligned after CI runner hardening updates.
### Fixed

- Align release bookkeeping so `pyproject.toml` and top changelog release stay in sync for pre-push release-discipline checks.

## [2.1.2] - 2026-04-02

Short version: Add workspace-value benchmark suite and validation coverage.

### Added

- Add signal coverage matrix generation, a reproducible benchmark corpus, and an agent-loop efficiency benchmark for measurable workspace-value evidence.
- Add test coverage for workspace-value scripts and corpus integrity checks.

### Changed

- Update README and STUDY documentation with signal coverage, cross-version benchmark, and agent-loop reporting.

## [2.1.1] - 2026-04-02

Short version: Release follow-up after 2.1.0.

### Fixed

- Cut the automated 2.1.1 release line so repository version metadata stays aligned with the published package version.

## [2.1.0] - 2026-04-02

Short version: Ship agent UX improvements, release hardening, and output consistency updates.

### Added

- `drift patterns`, `drift self`, and `drift trend` gained agent-facing usability improvements including JSON/file output options and freshness warnings (#98, #101, #102).

### Changed

- Migrate release automation to `python-semantic-release` in CI, update release instructions/skills, and add maintainer/push-gate documentation for repository operations.
- Improve contributor and governance docs plus `drift copilot-context` output so stable signal IDs and maintainer workflows are easier to follow.

### Fixed

- Standardize score precision/help output, keep JSON responses deterministic, and reduce self-analysis noise from temporary environments and internal workspace artifacts.
- Harden self-hosted CI and release workflows across Welcome, Release, Security Hygiene, CodeQL, Dependency Review, Publish, and Workflow Sanity to avoid recurring Windows- and billing-related failures.

## [2.0.0] - 2026-04-02

Short version: Migrate release automation to python-semantic-release in CI.

### Changed

- Replace manual `chore: Release`-gated workflow with `python-semantic-release` automation in `.github/workflows/release.yml`.
- Move release versioning/changelog/tag orchestration to PSR with conventional-commit parsing on push to `main`.

### Fixed

- Align README trust signals by reconciling development-status wording, removing hardcoded coverage percentage, softening single-rater badge framing, and updating stale pre-commit revision example.

## [1.5.0] - 2026-04-02

Short version: Add tests for issues #69-73 agent-ux improvements. (+7 more commits)

### Changed

- Add tests for issues #69-73 agent-ux improvements. (+7 more commits)

## [1.4.2] - 2026-04-02

Short version: Harden release automation tag fallback logic.

### Fixed

- Fall back from remote tag lookup to local semantic tags when origin is unreachable.
- Fall back from missing base-tag commit range to `HEAD` when collecting release commit messages.
- Keep the Unreleased section on top when appending the first concrete release section.

## [1.4.1] - 2026-04-02

Short version: Add explicit docstring for patterns target_path. (+1 more commits)

### Changed

- Add explicit docstring for patterns target_path. (+1 more commits)

## [1.4.0] - 2026-04-02

Short version: Add deterministic baseline refresh reason in nudge.

### Changed

- Add deterministic baseline refresh reason in nudge.


## [1.3.6] - 2026-04-01

Short version: Fix JSON error consistency across CLI commands.

### Fixed

- Ensure consistent machine-readable CLI error envelopes for Issue #66 by honoring `--format json` / `--json` and `DRIFT_ERROR_FORMAT=json`, and by returning structured `DRIFT-2001` / `DRIFT-2010` errors for `drift self` and `drift mcp --serve` failure paths.

## [1.3.5] - 2026-04-01

Short version: Maintenance and dependency updates.

### Changed

- Maintenance and dependency updates.


## [1.3.4] - 2026-04-01

Short version: Maintenance and dependency updates.

### Changed

- Maintenance and dependency updates.


## [1.3.3] - 2026-04-01

Short version: Maintenance and dependency updates.

### Changed

- Maintenance and dependency updates.


## [1.3.2] - 2026-04-01

Short version: Release 1.3.2. (+8 more commits)

### Changed

- Release 1.3.2. (+8 more commits)


## [1.3.1] - 2026-04-01

Short version: Mark Pages + Discussions active, trigger docs deployment. (+4 more commits)

### Changed

- Mark Pages + Discussions active, trigger docs deployment. (+4 more commits)


## [1.3.0] - 2026-04-01

Short version: Fix SECURITY.md to include 1.3.x as supported. (+2 more commits)

### Changed

- Fix SECURITY.md to include 1.3.x as supported. (+2 more commits)


## [1.2.0] - 2026-04-01

Short version: Phase 3  project-specific constraint extraction for AVS/CCC/ECM/HSC generators. (+5 more commits)

### Changed

- Phase 3  project-specific constraint extraction for AVS/CCC/ECM/HSC generators. (+5 more commits)


## [1.1.17] - 2026-03-31

Short version: Refine v1.1.16 release notes. (+2 more commits)

### Changed

- Refine v1.1.16 release notes. (+2 more commits)


## [1.1.16] - 2026-03-31

Short version: Experimental release for agent navigation improvements across Phases 4-6.

### Changed

- Added `drift_nudge` as an experimental MCP tool that returns directional feedback (`improving` / `stable` / `degrading`), blocking reasons, and a non-configurable `safe_to_commit` hard rule.
- Introduced `BaselineManager` with git-event invalidation for incremental navigation feedback: baseline refresh is triggered on HEAD changes, stash changes, or large working-tree drift.
- Documented the incremental temporal model in `DEVELOPER.md` and the diagnosis-vs-navigation product dimension in `ROADMAP.md`.
- Fixed a mypy type-assignment issue in `nudge()` caused by a `FileInfo` variable name collision.

## [1.1.15] - 2026-03-31

Short version: Add IncrementalSignalRunner with signal scope registry (Phase 3). (+1 more commits)

### Changed

- Add IncrementalSignalRunner with signal scope registry (Phase 3). (+1 more commits)

## [1.1.14] - 2026-03-31

Short version: Add BaselineSnapshot and per-file SignalCache key (Phase 2 foundation). (+1 more commits)

### Changed

- Add BaselineSnapshot and per-file SignalCache key (Phase 2 foundation). (+1 more commits)

## [1.1.13] - 2026-03-31

Short version: Release automation runs pre-push preflight after commit. (+24 more commits)

### Changed

- Release automation runs pre-push preflight after commit. (+24 more commits)

## [1.1.12] - 2026-03-30

Short version: Add drift init command with built-in profiles (default, vibe-coding, strict).

### Changed

- Add drift init command with built-in profiles (default, vibe-coding, strict).

## [1.1.12] - 2026-03-30

Short version: Add `drift init` command with built-in profiles (default, vibe-coding, strict).

### Added

- **`drift init`** CLI command: scaffolds drift.yaml, GitHub Actions workflow, git pre-push hook, and VS Code MCP config in one command.
- **Profile system** (`src/drift/profiles.py`): built-in `default`, `vibe-coding`, and `strict` configuration profiles with pre-tuned signal weights, thresholds, and policies.
- `--profile vibe-coding` upweights MDS (0.20), PFS (0.18), BAT (0.06), TPD (0.06), lowers similarity threshold to 0.75, adds layer boundary policies.
- `--profile strict` sets `fail_on: medium` for zero-tolerance CI gates.
- Flags: `--ci`, `--hooks`, `--mcp`, `--full` for selective or all-in-one scaffolding.
- 24 new tests in `tests/test_init_cmd.py`.

## [1.1.11] - 2026-03-30

Short version: Security-by-Default signals (MAZ, ISD, HSC) for vibe-coding detection.

### Added

- **MAZ** (Missing Authorization, CWE-862): detects unprotected API endpoints across FastAPI/Django/Flask/Starlette/Sanic with 18 auth decorator patterns and body-level auth detection.
- **HSC** (Hardcoded Secret, CWE-798): detects hardcoded credentials via secret variable regex, known token prefixes (ghp_, sk-, AKIA, xoxb-), and Shannon entropy analysis.
- **ISD** (Insecure Default, CWE-1188): detects insecure configuration defaults (DEBUG=True, ALLOWED_HOSTS=['*'], CORS_ALLOW_ALL, insecure cookies, verify=False).
- Extended `ast_parser` auth detection (18 decorators, body-level checks, `auth_mechanism` fingerprint field); SARIF output with CWE helpUri; 67 new tests.
- Signal model expanded from 19 to 22 configured signals (3 new report-only, weight=0.0).

## [1.1.10] - 2026-03-30

Short version: Improve MDS/PFS/AVS signal precision from MiroFish validation.

### Changed

- Improve MDS/PFS/AVS signal precision from MiroFish validation.

## [1.1.9] - 2026-03-30

Short version: Add --signals alias to analyze and check commands for consistency with scan. (+1 more commits)

### Changed

- Add --signals alias to analyze and check commands for consistency with scan. (+1 more commits)

## [1.1.8] - 2026-03-30

Short version: Extract api helpers and improve mcp docs.

### Changed

- Extract api helpers and improve mcp docs.

## [1.1.7] - 2026-03-30

### Changed

- Refresh branding and add no-color CLI output.
- Relocate docs artifacts under approved directories.

## [1.1.6] - 2026-03-30

Short version: Maintenance and dependency updates.

### Changed

- Maintenance and dependency updates.

## [1.1.5] - 2026-03-30

Short version: AVS dedup + MDS remediation placeholders + cache version bump. (+3 more commits)

### Changed

- AVS dedup + MDS remediation placeholders + cache version bump. (+3 more commits)

## [1.1.4] - 2026-03-30

### Added

- `drift diff` now returns `decision_reason_code` and `decision_reason` as explicit machine-readable acceptance context.

### Changed

- Add explicit diff decision reason fields.
- Version-bump gate uses remote tags instead of local git describe.

## [1.1.3] - 2026-03-30

Short version: Update _top_signals mock to accept keyword arguments. (+18 more commits)

### Changed

- Update _top_signals mock to accept keyword arguments. (+18 more commits)

## [1.1.3] - 2026-03-30

Short version: Use remote tags for version tracking and clean up release state. (+17 more commits)

### Changed

- Use remote tags for version tracking and clean up release state. (+17 more commits)

## [1.1.2] - 2026-03-30

### Fixed
- Reduce DCA false positives for framework entry-points: route-decorated handlers and schema-adjacent classes in router files are no longer prioritized as potentially unused exports.

## [1.1.1] - 2026-03-30

### Release
- Version 1.1.1

## [0.10.10] - 2026-03-30

Short version: drift closes agent-facing workflow gaps identified through real-world agent behavior analysis — scoped fix-plan filtering, explicit in_scope_accept hints for noise isolation, and baseline workflow recommendations for legacy codebases.

### Added

- **`fix-plan --target-path` for agent-scoped repair**: Agents can now restrict fix-plan output to findings in a specific subdirectory (e.g., `drift fix-plan --target-path src/api`), preventing information overload when working on localized changes.
- **Explicit `in_scope_accept` hints in `drift diff` recommendations**: When `out_of_scope_diff_noise` is the only blocker and the scoped target is clean, `recommended_next_actions` now explicitly says "use in_scope_accept (true) as the scoped gate decision" so agents recognize the viable decision path.
- **Baseline workflow recommendation in `drift scan`**: When >20 high/critical findings exist, `recommended_next_actions` suggests `drift baseline save` → `drift diff --baseline` workflow so agents avoid the `accept_change=false` gate loop on legacy repos.

### Changed

- **Improved agent decision guidance**: Updated `_diff_next_actions` and `_scan_next_actions` to surface actionable next steps for common agent workflow patterns (scoped acceptance, baseline framing, uncommitted-change handling).

## [0.10.9] - 2026-03-29

Short version: drift closes agent-facing gaps identified through real-world agent workflow analysis — consistent signal abbreviations, full explain coverage, and a scoped acceptance field that unblocks agents from pre-existing diff noise.

### Added

- **Full signal coverage in `drift explain`**: Added the 6 previously missing signals — COD, CCC, CXS, FOE, CIR, DCA — so all 19 signals are now reachable via `drift explain <ABBREV>`.
- **Consistent task ID prefixes for all 19 signals**: Extended `_SIGNAL_PREFIX` from 6 to all 19 signals, eliminating wrong fallback prefixes (`byp-`, `cog-`, `dea-`). Added explicit `signal_abbrev` field to fix-plan task dicts so agents can call `drift explain <signal_abbrev>` directly.
- **Complete `_ABBREV_TO_SIGNAL` mapping**: Extended from 15 to 19 entries (CXS, FOE, CIR, DCA) so `drift fix-plan --signal CXS` and `resolve_signal()` work for all signals.
- **`in_scope_accept` field in `drift diff`**: New boolean field that signals whether the scoped target path is clean, independent of pre-existing out-of-scope diff noise — prevents agents from blocking on noise they cannot resolve.
- **Actionable `out_of_scope_diff_noise` guidance**: `recommended_next_actions` in diff responses explains what out-of-scope noise means and provides a concrete resolution path (`commit changes ; drift diff --diff-ref HEAD~1`).

## [0.10.8] - 2026-03-29

Short version: drift strengthens its agent-native workflow with top-level CLI parity, explicit machine-readable acceptance fields, and better telemetry correlation.

### Added

- **Agent-native top-level CLI commands**: Added `drift validate`, `drift scan`, `drift diff`, and `drift fix-plan` as direct structured JSON entry points aligned with the Python API and MCP surface.
- **Explicit scan/diff decision fields**: Added machine-readable acceptance signals such as `accept_change`, `blocking_reasons`, and severity regression indicators so agents no longer need to infer gating decisions externally.
- **Telemetry run correlation**: Added stable `run_id` correlation for telemetry events, with optional override via `DRIFT_TELEMETRY_RUN_ID`.

### Changed

- **API output documentation**: Expanded output docs to describe the agent-native workflow surface, decision fields, and the current machine-readable error schema v2.0.
- **Scoped diff decisioning**: `drift diff` can now scope acceptance logic to a target path while reporting out-of-scope diff noise separately.

## [0.10.7] - 2026-03-29

Short version: drift adds token-efficient compact JSON output with deduplicated findings and explicit CLI toggles for agent/CI workflows.

### Added

- **Compact JSON mode for analyze/check**: Added `--compact` to `drift analyze --format json` and `drift check --format json` so automation can consume a concise payload without large detail sections.
- **Deduplicated compact finding view**: JSON output now includes `findings_compact` with stable dedupe keys and per-item `duplicate_count` to preserve signal counts while reducing payload redundancy.
- **Decision-first compact counters**: Added `compact_summary` with `findings_total`, deduplicated counts, duplicate reduction, and high/critical counts for quick gating decisions.

### Changed

- **JSON output documentation**: Updated API output reference with compact mode usage and clear distinction between compact and full finding payloads.

## [0.10.5] - 2026-03-29

Short version: drift introduces an agent-native API surface and expands MCP capabilities with concise machine-first responses and improved CLI ergonomics.

### Added

- **Programmatic agent API module**: Added `drift.api` with stable entry points (`scan`, `diff`, `explain`, `fix_plan`, `validate`) for deterministic tool integration.
- **Expanded MCP tool surface**: Reworked MCP server to expose five agent-native tools: `drift_scan`, `drift_diff`, `drift_explain`, `drift_fix_plan`, and `drift_validate`.
- **Agent-friendly JSON shortcuts**: Added `--json` shortcut flags to `drift analyze` and `drift check` to reduce command friction in automated workflows.

### Changed

- **Machine-error contract v2.0**: CLI JSON error payloads now include recovery metadata (`recoverable`, `suggested_action`) for safer agent decision-making.
- **MCP contract coverage**: Updated MCP and CLI runtime tests to align with the new API and error-schema behavior.

## [0.10.3] - 2026-03-29

Short version: drift adds deterministic machine-error contracts and a decision-ready fix-first queue so CI and sprint planning can act directly on analyzer output.

### Added

- **Machine-readable CLI error payloads**: Added opt-in `DRIFT_ERROR_FORMAT=json` support so runtime failures emit a single stable JSON object on stderr with explicit `error_code`, `category`, `exit_code`, and hint fields.
- **Decision-ready `fix_first` output queue**: Added a top-level `fix_first` list in JSON output that ranks remediation work deterministically and exposes rank, priority class, next step, and expected benefit.

### Changed

- **Output contract documentation and tests**: Expanded API output docs and golden/contract coverage for error payloads, deterministic ordering, remediation objects, and fix-first prioritization.

## [0.10.2] - 2026-03-29

Short version: drift hardens machine-output contracts and CI release ergonomics with deterministic file output, schema versioning, deferred-area governance, and explicit exit-code semantics.

### Added

- **Deterministic machine file output**: Added `--output/-o` for `drift analyze` and `drift check`, plus `--save-baseline` on `analyze`, so CI can persist pure JSON/SARIF artifacts without shell redirection workarounds.
- **Deferred-area governance model**: Added config-level `deferred` path rules so legacy zones remain analyzed but findings are explicitly tagged as deferred debt instead of being silently excluded.

### Changed

- **Versioned JSON contract and prioritization metadata**: JSON output now carries `schema_version`, `score_contribution`, `impact_rank`, plus `symbol` and `deferred` fields to stabilize downstream integrations and improve hotspot ranking.
- **Structured CLI exit semantics**: Replaced magic exit numbers with explicit constants, separating threshold findings, config/user errors, analysis failures, and system failures for clearer CI diagnostics.

### Fixed

- **Self-smoke file-count guardrail drift**: Updated repository self-smoke file-count upper bound to accommodate organic project growth while preserving sanity-check intent.

## [0.10.1] - 2026-03-29

Short version: drift restores fully English user-facing finding output so CLI and release surfaces stay language-consistent.

### Fixed

- **English-only finding remediation text**: Translated the remaining German fix/recommendation strings in pattern fragmentation, architecture violation, co-change coupling, mutant duplicates, and rich-output remainder rendering.
- **Regression coverage for output language**: Added focused assertions so the translated fix text remains actionable and does not regress back to mixed German/English output.

## [0.10.0] - 2026-03-29

Short version: drift broadens deterministic architecture coverage with five new Python coherence signals while improving runtime ergonomics for larger analysis workflows.

### Added

- **Five new Python coherence signals**: Added circular import, cognitive complexity, dead code accumulation, fan-out explosion, and guard-clause deficit detection with dedicated fixture-backed coverage.
- **GitHub-friendly result rendering**: Added dedicated GitHub output formatting and structured error surfaces for CI and agent-driven workflows.

### Changed

- **Analysis throughput and cache behavior**: Refined cache, pipeline, and CLI execution paths to reduce friction in repeated analyzer runs and large benchmark workflows.
- **Ground-truth and benchmark tooling**: Expanded benchmark label validation, synthetic mutation corpus metadata, and migration helpers so new signal evidence stays reproducible.

## [0.9.0] - 2026-03-28

Short version: drift now ships first-class Copilot/MCP integration and extends core signal analysis to TypeScript/JavaScript for more actionable cross-tool architecture guidance.

### Added

- **`drift copilot-context` + instruction engine**: New command and generator that convert high-impact findings into merge-safe Copilot instruction blocks with deterministic sectioning and remediation guidance.
- **`drift mcp --serve` server mode**: New MCP server entrypoint exposing drift analysis tools for editor/agent workflows, plus CLI wiring and dedicated MCP/Copilot coverage tests.
- **Copilot evidence tooling**: New benchmark scripts and prompt-pair artifacts for reproducible Copilot-context coverage and behavioral evaluation.

### Changed

- **AI-attribution pipeline output**: Repository analysis now surfaces detected AI tool indicators and manual-ratio policy overrides in pipeline assembly and JSON output.
- **TypeScript/JavaScript signal coverage**: Extended GCD, BEM, NBV, ECM, and TPD with shared tree-sitter utilities and dedicated phase test suites for TS/JS parity.

## [0.8.2] - 2026-03-28

Short version: drift gains `drift config validate/show`, stable `rule_id` on findings, per-path configuration overrides, and expanded docs.

### Added

- **`drift config validate/show`**: Validates `drift.yaml` schema, extreme weights, unknown signals; `show` displays resolved config as Rich table or JSON.
- **Stable `rule_id` on Finding**: Every finding carries a `rule_id` field (default: `signal_type.value`), emitted in JSON and used as SARIF `ruleId`.
- **Per-path overrides**: New `path_overrides` config section with glob-based `exclude_signals`, custom `weights`, and `severity_gate` per directory.
- **Documentation expansion**: Troubleshooting guide, performance matrix (16 repos), GitLab CI template, Python API examples, check-vs-analyze comparison.

### Changed

- **Pipeline + SARIF**: `apply_path_overrides` runs after scoring; SARIF output uses `rule_id` for better tool integration.

## [0.8.1] - 2026-03-27

Short version: drift now enforces English-only user-facing finding remediation text to keep CLI output and demo assets language-consistent.

### Fixed

- **Language consistency in findings**: Translated remaining user-facing recommendation/fix strings from German to English across AVS, EDS, MDS, SMS, and TVS signal outputs.
- **Demo output reliability**: Demo generation now reflects fully English drift output in rendered CLI captures.

## [0.8.0] - 2026-03-27

Short version: drift adds a deterministic Co-Change Coupling (CCC) scoring signal to expose hidden file coupling from git history with actionable remediation.

### Added

- **Co-Change Coupling (CCC) signal**: Added a dedicated deterministic signal that flags file pairs repeatedly co-changed in git history without explicit import dependency, including graceful degradation for thin history and weighted suppression for merge/bot-heavy commits.
- **CCC recommendation handler**: Added actionable remediation guidance for hidden coupling findings, including explicit dependency direction, shared-module extraction, and regression-test hardening.
- **CCC fixture coverage + evidence artifact**: Added isolated TP/TN unit tests with synthetic git history and a release evidence artifact documenting reproducible validation commands.

### Changed

- **Signal model + scoring defaults**: Extended the active scoring model to 15 signals with a conservative default weight for CCC (`0.005`) to preserve rollout stability while surfacing coupling hotspots.
- **Documentation consistency**: Updated signal-count and scoring references across docs, study notes, and outreach material to keep public claims aligned with the live model.

## [0.7.4] - 2026-03-27

Short version: release publishing now supports secure PyPI token usage for automation without exposing credentials in the repository.

### Changed

- **Publish workflow token path**: `publish.yml` now supports token-based PyPI publishing through repository secret `PYPI_API_TOKEN`, with Trusted Publishing as fallback when no token is configured.
- **Manual release control**: Added `workflow_dispatch` for the publish workflow so release publication can be retried explicitly.

### Fixed

- **Secret hygiene guardrails**: Added explicit documentation that tokens must never be committed and ignored local `.pypirc` to prevent accidental credential commits.

## [0.7.3] - 2026-03-27

Short version: drift gains a deterministic cohesion-deficit signal with actionable remediation, plus aligned release evidence and consistency messaging.

### Added

- **Cohesion Deficit (COD) signal**: Added deterministic detection for low internal module cohesion (god-files/utility-dumps) based on semantic unit overlap, with built-in small-repo dampening and full fixture/unit coverage.
- **CLI explain subcommand**: Added `drift explain` signal reference output so teams can inspect signal intent, detection scope, examples, and tuning hints directly in the terminal.

### Changed

- **Scoring model extension**: Added `cohesion_deficit` to `SignalType`, default signal weights, and signal registration so COD participates in composite scoring and ablation/precision pipelines.
- **Recommendation coverage**: Added actionable COD recommendations that prioritize extracting isolated responsibilities into cohesive modules.

### Fixed

- **Model-consistency evidence**: Updated public docs and outreach references from 13 to 14 scoring signals so release/consistency gates remain reproducible and accurate.

## [0.7.2] - 2026-03-27

Short version: architecture-violation detection is more robust, and release validation/workflow consistency is tightened for safer publication.

### Changed

- **AVS detection hardening**: Refined architecture-violation detection behavior and corresponding coverage to reduce ambiguity in boundary-violation interpretation.
- **Release workflow consistency**: Updated release validation/publish workflow behavior so release checks are enforced consistently before publication.

### Fixed

- **Lint compatibility on Python 3.11+**: Moved `Callable` import in the signal base module to `collections.abc` to satisfy enforced Ruff typing/lint rules during push and release gates.

## [0.7.1] - 2026-03-27

Short version: deterministic auto-calibration output, dedicated ECM signal coverage, and scoped trend-history persistence for diff-only CI pipelines.

### Added

- **Dedicated ECM tests**: Added a standalone ECM signal test module with explicit true-positive, true-negative, and edge-case coverage for signature changes, missing history, and private-function handling.

### Changed

- **Deterministic weight auto-calibration**: `auto_calibrate_weights()` now uses canonical key ordering and deterministic residual correction during renormalization, ensuring stable results for identical input across iteration-order differences.
- **Diff trend/history parity**: `analyze_diff()` now computes trend context and persists snapshots, scoped to diff-mode history so CI pipelines that only run diff analysis retain functional trend and delta context without mixing full-repo snapshots.

### Fixed

- **Regression stability**: Added regression tests for deterministic auto-calibration output and for scoped diff-history persistence semantics.

## [0.7.0] - 2026-03-27

Short version: all 13 signals are now scoring-active with automatic weight calibration and small-repo noise suppression.

### Added

- **All signals scoring-active**: Promoted all 7 previously report-only signals (DIA, BEM, TPD, GCD, NBV, BAT, ECM) to scoring; no signals remain report-only. New ECM signal detects exception-profile drift via git-history comparison (MVP).
- **Auto-calibration**: Runtime weight rebalancing (`auto_calibrate: true`, default) — dampens dominant signals within a ±50 % band; deterministic and reproducible.
- **Small-repo noise suppression**: Adaptive dampening (K=20) and per-signal minimum-finding thresholds for repositories with fewer than 15 modules.

### Changed

- **Default signal weights**: Redistributed to 13-signal simplex; `compute_signal_scores()` accepts `dampening_k` and `min_findings` for context-aware scoring.

### Fixed

- **BEM docstring + ground-truth**: Fixed escaped triple-quote syntax error in `broad_exception_monoculture.py`; added 12 new NBV/BAT ground-truth fixtures and full 13-signal ablation coverage.

## [0.6.0] - 2026-03-26

Short version: stronger TypeScript analysis, delta- and context-aware rollout signals, and new report-only consistency proxies backed by tighter release and evidence guardrails.

### Added

- **TypeScript analysis expansion**: Added stronger import resolution, workspace assignment, vendor filtering, and dedicated TS/TSX architectural rules with benchmark coverage.
- **Rollout-aware reporting**: Added delta-first interpretation, context tags, and the ADR-007 report-only consistency proxies to make rollout and migration states more actionable.

### Changed

- **Release hygiene and onboarding**: Tightened feature-evidence gates and expanded rollout, trust, and onboarding documentation around the actual product maturity.

### Fixed

- **Core hardening**: Improved pipeline, config, suppression, cache, observational analysis behavior, and delta-gate correctness while keeping existing `fail_on` behavior backward compatible.

## [0.5.0] - 2026-03-23

### Added

- **CLI `--sort-by` + `--max-findings`**: `analyze` command now accepts `--sort-by impact|score` (default: impact) and `--max-findings N` (default: 20) for prioritised output.
- **AVS Mutation Tests** (`tests/test_avs_mutations.py`): 41 new tests across 8 classes covering DB→API violations, omnilayer directions, circular-dependency detection, hub-dampening calibration, and policy-boundary enforcement.
- **Benchmark corpus ×15**: Extended from 5 to 15 real-world repositories (+Flask, Starlette, Django, Celery, Poetry, Requests, SQLModel, Uvicorn, Sanic, Rich). 2 642 total findings. Precision strict 97.3%.
- **CLI refactored into `src/drift/commands/` package**: `analyze`, `check`, `self`, `trend`, `timeline`, `patterns`, `badge` each in their own module.
- **MkDocs documentation site** (`docs-site/`): algorithms deep-dive, signal reference, case studies (Django, FastAPI, Pydantic), getting-started guides.
- `scripts/evaluate_benchmark.py` — precision reports against ground-truth labels.
- `scripts/migrate_ground_truth.py` — migration helper for key-based label format.
- `scripts/sensitivity_analysis.py` — threshold sensitivity analysis.
- `scripts/ablation_mds_threshold.py` — MDS similarity threshold ablation.
- Ground-truth labels migrated to key-based format (269 → key-based).

### Changed

- `render_findings()` / `render_full_report()` in `rich_output.py` accept `sort_by` / `max_findings`.
- `drift.example.yaml` updated with current field set and inline comments.

### Fixed

- Type safety hardening across CLI entry points.
- Cache eviction, auto-discovery, and git-history edge cases (DI refactor).
- Ruff lint errors (E501, B905) from post-v0.3.0 changes.
- Resilience coverage: coverage gates, quality gates hardened.
- Coverage on critical paths: file-discovery, scoring engine, JSON output golden tests.
- `tagesplanung/` and other workspace artifacts blocked from git push via pre-commit/pre-push hooks.

## [0.3.0] - 2026-03-20

### Added

- **Evaluation Framework**: Comprehensive precision/recall scoring system with 15-fold LOOCV validation (F1=1.000). TVS (Type Variation Signal) fixtures added.
- **Temporal Drift Analysis**: New script for analyzing drift patterns over time with score interpretation ranges and bandbreite documentation.
- **Real Repository Smoke Tests**: Expanded from single repo to 7 real-world repositories for comprehensive false-positive regression detection.
- **Major-Version Correlation Study**: Django correlation analysis across 10 years and 17 releases (1.8-6.0), demonstrating drift's effectiveness on long-term architectural evolution.
- **Score Bandbreite Documentation**: Added to smoke test findings for better signal interpretation.

### Fixed

- **Config**: Added `docs/` and `examples/` to default exclude patterns, reducing false positives from documentation.
- **CI/Dependencies**: Added `numpy` and `mistune` to dev dependencies for test collection.
- **Linting**: Fixed ruff lint errors in test suite.

### Changed

- **Test Suite**: Reorganized and expanded to validate against 7 repositories with documented score ranges.

## [0.2.0] - 2026-03-19

### Changed

- **DIA signal**: Replaced regex-based Markdown parsing with mistune AST parser. Link URLs are now skipped entirely, eliminating false positives from GitHub badges, CI links, and package registry URLs. Added URL-segment blacklist (~80 entries). Strict precision improved from 48% → 59% (+12pp), false positives reduced from 31 → 6 (−81%).
- **AVS signal**: Added Omnilayer recognition for cross-cutting directories (config/, utils/, types/, common/, shared/, etc.) — these no longer generate layer-violation findings. Hub-module dampening via NetworkX in-degree centrality (90th percentile cutoff, ×0.3 score dampening). Optional embedding-based layer inference for ambiguous modules.
- **MDS signal**: Hybrid similarity scoring (0.6 × AST Jaccard + 0.4 × cosine embedding similarity). Phase 3 semantic duplicate search via FAISS index catches renamed-variable duplicates that structural comparison alone misses.
- **Overall precision**: 80% → 85% strict (+5pp) across 269 classified findings on 5 repositories.

### Added

- `drift.embeddings` module: Central embedding service with lazy model loading (all-MiniLM-L6-v2), cosine similarity, FAISS index builder, disk-backed `EmbeddingCache`. Fully optional — all signals degrade gracefully without embedding dependencies.
- CLI flags: `--no-embeddings` (disable embedding features), `--embedding-model` (override model name). Available on both `analyze` and `check` commands.
- Config fields: `embeddings_enabled`, `embedding_model`, `embedding_batch_size`, `allowed_cross_layer` (policy patterns for AVS).
- Optional dependency group `[markdown]` for `mistune>=3.0`. DIA signal falls back to regex extraction when mistune is not installed.

### Notes

- **Knowledge‑Graph (KG) heuristics included:** v0.2.0 integrates import/relationship graph analysis and layer‑inference heuristics (e.g., import graph construction, hub‑dampening, inferred layer checks) to improve architecture‑aware detection.
- **Optional RAG-style retrieval (Embeddings + FAISS):** The new `drift.embeddings` module provides vector embeddings and optional FAISS indexing to enable semantic retrieval workflows. This supplies the retrieval component required for RAG-like setups; however, Drift remains deterministic by default and does not bundle an LLM — connecting an LLM for generation is an opt-in integration for downstream tooling.
- 36 new unit tests: `test_embeddings.py` (10), `test_avs_enhanced.py` (13), `test_dia_enhanced.py` (13).

### Fixed

- DIA: Badge/CI URL fragments (e.g., `actions/`, `workflows/`, `blob/`) no longer reported as missing directories.
- AVS: Findings below score 0.15 filtered out (reduces noise from ambiguous cross-layer references).
- Embedding cosine similarity: Normalized with L2 norm (was using raw dot product).

## [0.1.0] - 2026-02-15

Initial release with 7 detection signals: PFS, AVS, MDS, EDS, TVS, SMS, DIA.

- 80% strict precision on 291 classified findings across 5 repositories
- 86% recall on 14 controlled mutations
- CLI commands: `analyze`, `check`, `self`, `trend`, `timeline`, `patterns`, `badge`
- Output formats: rich (terminal), JSON, SARIF (GitHub Code Scanning)
- GitHub Actions integration via `drift-check.yml` template
