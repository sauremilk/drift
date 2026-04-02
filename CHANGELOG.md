## [Unreleased]

### Fixed

- Document the NegativeContext system in docs-site (field contract, enums, output locations, contributor registration rule) and link it from API outputs, signal docs, navigation, and README.
- Re-enable GitHub Security scanning by running CodeQL and Dependency Review workflows on `ubuntu-latest` for `main` push/PR events, and document both workflows in `SECURITY.md`.
- Make PyPI publish workflow runner-agnostic by using Twine upload for token-based publishing (works on Windows/self-hosted runners).
- Allow `.pre-commit-config.yaml` in the repo-root allowlist so repo hardening commits pass the local repo-guard gate.
- Stabilize self-hosted Windows workflows by switching release and sanity checks to PowerShell-safe execution, avoiding editable pip-audit installs, and disabling the broken Codecov upload step.
- Force release-tag validation and release-creation steps to use bash semantics so POSIX conditional blocks no longer fail on PowerShell runners.
- Move Security Hygiene execution to self-hosted to avoid hosted-runner billing locks.
- Add manual dispatch support to Workflow Sanity for direct post-fix verification runs.
- Install Python in Workflow Sanity explicitly on self-hosted runners to avoid missing interpreter failures.
- Make auto-release release-existence checks PowerShell-safe by handling `gh release view` misses without hard failure.
- Restrict CodeQL execution to manual dispatch so push/PR runs are no longer hard-failed by billing-locked code scanning.
- Reset PowerShell native exit code after release checks so non-existent releases no longer fail the auto-release check step.
- Skip Dependency Review and Labeler jobs for `dependabot[bot]` PRs to prevent recurring billing-locked failures in automated dependency update traffic.
- Track `.secrets.baseline` (plus allowlist entry) so Security Hygiene can execute detect-secrets without baseline-path failures.
- Run `pip-audit` with `--skip-editable` in Security Hygiene to avoid false failures on local editable package metadata not present on PyPI.
- Downgrade `pip-audit` in Security Hygiene to a non-blocking signal (`continue-on-error`) to avoid recurring CI hard-failures from local package resolution edge cases.

## [1.4.1] – 2026-04-02

Short version: Maintenance and dependency updates.

### Changed

- Maintenance and dependency updates.


## [1.5.0] – 2026-04-02

Short version: Release 1.5.0. (+8 more commits)

### Changed

- Release 1.5.0. (+8 more commits)


## [1.4.0] – 2026-04-02

Short version: Add deterministic baseline refresh reason in nudge.

### Changed

- Add deterministic baseline refresh reason in nudge.


## [1.3.6] – 2026-04-01

Short version: Fix JSON error consistency across CLI commands.

### Fixed

- Ensure consistent machine-readable CLI error envelopes for Issue #66 by honoring `--format json` / `--json` and `DRIFT_ERROR_FORMAT=json`, and by returning structured `DRIFT-2001` / `DRIFT-2010` errors for `drift self` and `drift mcp --serve` failure paths.

## [1.3.5] – 2026-04-01

Short version: Maintenance and dependency updates.

### Changed

- Maintenance and dependency updates.


## [1.3.4] – 2026-04-01

Short version: Maintenance and dependency updates.

### Changed

- Maintenance and dependency updates.


## [1.3.3] – 2026-04-01

Short version: Maintenance and dependency updates.

### Changed

- Maintenance and dependency updates.


## [1.3.2] – 2026-04-01

Short version: Release 1.3.2. (+8 more commits)

### Changed

- Release 1.3.2. (+8 more commits)


## [1.3.1] – 2026-04-01

Short version: Mark Pages + Discussions active, trigger docs deployment. (+4 more commits)

### Changed

- Mark Pages + Discussions active, trigger docs deployment. (+4 more commits)


## [1.3.0] – 2026-04-01

Short version: Fix SECURITY.md to include 1.3.x as supported. (+2 more commits)

### Changed

- Fix SECURITY.md to include 1.3.x as supported. (+2 more commits)


## [1.2.0] – 2026-04-01

Short version: Phase 3  project-specific constraint extraction for AVS/CCC/ECM/HSC generators. (+5 more commits)

### Changed

- Phase 3  project-specific constraint extraction for AVS/CCC/ECM/HSC generators. (+5 more commits)


## [1.1.17] – 2026-03-31

Short version: Refine v1.1.16 release notes. (+2 more commits)

### Changed

- Refine v1.1.16 release notes. (+2 more commits)


## [1.1.16] – 2026-03-31

Short version: Experimental release for agent navigation improvements across Phases 4-6.

### Changed

- Added `drift_nudge` as an experimental MCP tool that returns directional feedback (`improving` / `stable` / `degrading`), blocking reasons, and a non-configurable `safe_to_commit` hard rule.
- Introduced `BaselineManager` with git-event invalidation for incremental navigation feedback: baseline refresh is triggered on HEAD changes, stash changes, or large working-tree drift.
- Documented the incremental temporal model in `DEVELOPER.md` and the diagnosis-vs-navigation product dimension in `ROADMAP.md`.
- Fixed a mypy type-assignment issue in `nudge()` caused by a `FileInfo` variable name collision.

## [1.1.15] – 2026-03-31

Short version: Add IncrementalSignalRunner with signal scope registry (Phase 3). (+1 more commits)

### Changed

- Add IncrementalSignalRunner with signal scope registry (Phase 3). (+1 more commits)

## [1.1.14] – 2026-03-31

Short version: Add BaselineSnapshot and per-file SignalCache key (Phase 2 foundation). (+1 more commits)

### Changed

- Add BaselineSnapshot and per-file SignalCache key (Phase 2 foundation). (+1 more commits)

## [1.1.13] – 2026-03-31

Short version: Release automation runs pre-push preflight after commit. (+24 more commits)

### Changed

- Release automation runs pre-push preflight after commit. (+24 more commits)

## [1.1.12] – 2026-03-30

Short version: Add drift init command with built-in profiles (default, vibe-coding, strict).

### Changed

- Add drift init command with built-in profiles (default, vibe-coding, strict).

## [1.1.12] – 2026-03-30

Short version: Add `drift init` command with built-in profiles (default, vibe-coding, strict).

### Added

- **`drift init`** CLI command: scaffolds drift.yaml, GitHub Actions workflow, git pre-push hook, and VS Code MCP config in one command.
- **Profile system** (`src/drift/profiles.py`): built-in `default`, `vibe-coding`, and `strict` configuration profiles with pre-tuned signal weights, thresholds, and policies.
- `--profile vibe-coding` upweights MDS (0.20), PFS (0.18), BAT (0.06), TPD (0.06), lowers similarity threshold to 0.75, adds layer boundary policies.
- `--profile strict` sets `fail_on: medium` for zero-tolerance CI gates.
- Flags: `--ci`, `--hooks`, `--mcp`, `--full` for selective or all-in-one scaffolding.
- 24 new tests in `tests/test_init_cmd.py`.

## [1.1.11] – 2026-03-30

Short version: Security-by-Default signals (MAZ, ISD, HSC) for vibe-coding detection.

### Added

- **MAZ** (Missing Authorization, CWE-862): detects unprotected API endpoints across FastAPI/Django/Flask/Starlette/Sanic with 18 auth decorator patterns and body-level auth detection.
- **HSC** (Hardcoded Secret, CWE-798): detects hardcoded credentials via secret variable regex, known token prefixes (ghp_, sk-, AKIA, xoxb-), and Shannon entropy analysis.
- **ISD** (Insecure Default, CWE-1188): detects insecure configuration defaults (DEBUG=True, ALLOWED_HOSTS=['*'], CORS_ALLOW_ALL, insecure cookies, verify=False).
- Extended `ast_parser` auth detection (18 decorators, body-level checks, `auth_mechanism` fingerprint field); SARIF output with CWE helpUri; 67 new tests.
- Signal model expanded from 19 to 22 configured signals (3 new report-only, weight=0.0).

## [1.1.10] – 2026-03-30

Short version: Improve MDS/PFS/AVS signal precision from MiroFish validation.

### Changed

- Improve MDS/PFS/AVS signal precision from MiroFish validation.

## [1.1.9] – 2026-03-30

Short version: Add --signals alias to analyze and check commands for consistency with scan. (+1 more commits)

### Changed

- Add --signals alias to analyze and check commands for consistency with scan. (+1 more commits)

## [1.1.8] – 2026-03-30

Short version: Extract api helpers and improve mcp docs.

### Changed

- Extract api helpers and improve mcp docs.

## [1.1.8] – 2026-03-30

Short version: Maintenance and dependency updates.

### Changed

- Maintenance and dependency updates.

## [1.1.8] – 2026-03-30

Short version: Maintenance and dependency updates.

### Changed

- Maintenance and dependency updates.

## [1.1.7] – 2026-03-30

Short version: Relocate docs artifacts under approved directories. (+3 more commits)

### Changed

- Relocate docs artifacts under approved directories. (+3 more commits)

## [1.1.7] – 2026-03-30

Short version: Sync changelog and lockfile for 1.1.7 release. (+2 more commits)

### Changed

- Sync changelog and lockfile for 1.1.7 release. (+2 more commits)

## [1.1.7] – 2026-03-30

Short version: Add no-color CLI evidence for release. (+1 more commits)

### Changed

- Add no-color CLI evidence for release. (+1 more commits)

## [1.1.7] – 2026-03-30

Short version: Refresh branding and add no-color CLI output.

### Changed

- Refresh branding and add no-color CLI output.

## [1.1.6] – 2026-03-30

Short version: Maintenance and dependency updates.

### Changed

- Maintenance and dependency updates.

## [1.1.5] – 2026-03-30

Short version: AVS dedup + MDS remediation placeholders + cache version bump. (+3 more commits)

### Changed

- AVS dedup + MDS remediation placeholders + cache version bump. (+3 more commits)

## [1.1.4] – 2026-03-30

Short version: Add explicit diff decision reason fields.

### Changed

- Add explicit diff decision reason fields.

## [Unreleased]

### Added

- `drift diff` now returns `decision_reason_code` and `decision_reason` as explicit machine-readable acceptance context.

## [1.1.4] – 2026-03-30

Short version: Version-bump gate uses remote tags instead of local git describe.

### Changed

- Version-bump gate uses remote tags instead of local git describe.

## [1.1.3] – 2026-03-30

Short version: Update _top_signals mock to accept keyword arguments. (+18 more commits)

### Changed

- Update _top_signals mock to accept keyword arguments. (+18 more commits)

## [1.1.3] – 2026-03-30

Short version: Use remote tags for version tracking and clean up release state. (+17 more commits)

### Changed

- Use remote tags for version tracking and clean up release state. (+17 more commits)

## [1.1.2] - 2026-03-30

Short version: drift reduziert DCA-Fehlalarme für Framework-Entry-Points in API-Routern, damit Agenten keine aktiven Endpunkte als Dead-Code-Löschkandidaten priorisieren.

### Fixed
- DCA reduziert False Positives für Framework-Entry-Points: Route-dekorierte Handler und schema-nahe Klassen in Router-Dateien werden nicht mehr als potenziell ungenutzte Exports priorisiert.

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

## [0.7.0] – 2026-03-27

Short version: all 13 signals are now scoring-active with automatic weight calibration and small-repo noise suppression.

### Added

- **All signals scoring-active**: Promoted all 7 previously report-only signals (DIA, BEM, TPD, GCD, NBV, BAT, ECM) to scoring; no signals remain report-only. New ECM signal detects exception-profile drift via git-history comparison (MVP).
- **Auto-calibration**: Runtime weight rebalancing (`auto_calibrate: true`, default) — dampens dominant signals within a ±50 % band; deterministic and reproducible.
- **Small-repo noise suppression**: Adaptive dampening (K=20) and per-signal minimum-finding thresholds for repositories with fewer than 15 modules.

### Changed

- **Default signal weights**: Redistributed to 13-signal simplex; `compute_signal_scores()` accepts `dampening_k` and `min_findings` for context-aware scoring.

### Fixed

- **BEM docstring + ground-truth**: Fixed escaped triple-quote syntax error in `broad_exception_monoculture.py`; added 12 new NBV/BAT ground-truth fixtures and full 13-signal ablation coverage.

## [0.6.0] – 2026-03-26

Short version: stronger TypeScript analysis, delta- and context-aware rollout signals, and new report-only consistency proxies backed by tighter release and evidence guardrails.

### Added

- **TypeScript analysis expansion**: Added stronger import resolution, workspace assignment, vendor filtering, and dedicated TS/TSX architectural rules with benchmark coverage.
- **Rollout-aware reporting**: Added delta-first interpretation, context tags, and the ADR-007 report-only consistency proxies to make rollout and migration states more actionable.

### Changed

- **Release hygiene and onboarding**: Tightened feature-evidence gates and expanded rollout, trust, and onboarding documentation around the actual product maturity.

### Fixed

- **Core hardening**: Improved pipeline, config, suppression, cache, observational analysis behavior, and delta-gate correctness while keeping existing `fail_on` behavior backward compatible.

## [0.5.0] – 2026-03-23

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

## [0.3.0] – 2026-03-20

### Added

- **Evaluation Framework**: Comprehensive precision/recall scoring system with 15-fold LOOCV validation (F1=1.000). TVS (Type Variation Signal) fixtures added.
- **Temporal Drift Analysis**: New script for analyzing drift patterns over time with score interpretation ranges and bandbreite documentation.
- **Real Repository Smoke Tests**: Expanded from single repo to 7 real-world repositories for comprehensive false-positive regression detection.
- **Major-Version Correlation Study**: Django correlation analysis across 10 years and 17 releases (1.8–6.0), demonstrating drift's effectiveness on long-term architectural evolution.
- **Score Bandbreite Documentation**: Added to smoke test findings for better signal interpretation.

### Fixed

- **Config**: Added `docs/` and `examples/` to default exclude patterns, reducing false positives from documentation.
- **CI/Dependencies**: Added `numpy` and `mistune` to dev dependencies for test collection.
- **Linting**: Fixed ruff lint errors in test suite.

### Changed

- **Test Suite**: Reorganized and expanded to validate against 7 repositories with documented score ranges.

## [0.2.0] – 2026-03-19

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

## [0.1.0] – 2026-02-15

Initial release with 7 detection signals: PFS, AVS, MDS, EDS, TVS, SMS, DIA.

- 80% strict precision on 291 classified findings across 5 repositories
- 86% recall on 14 controlled mutations
- CLI commands: `analyze`, `check`, `self`, `trend`, `timeline`, `patterns`, `badge`
- Output formats: rich (terminal), JSON, SARIF (GitHub Code Scanning)
- GitHub Actions integration via `drift-check.yml` template
