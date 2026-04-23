## [Unreleased]

### Fixed

- **shellcheck SC1017/SC1134 auf Windows-Runner.** Normalisierung auf Binary-Modus umgestellt; `.gitattributes` mit `eol=lf` fuer alle Text-Dateien ergaenzt.
- **Vendored Shell-Skripte von shellcheck excludiert.** Exclude-Pattern in `.pre-commit-config.yaml` um `demos/.tools/` erweitert.
- **Baseline-Test Rich word-wrap.** `soft_wrap=True` in `baseline.py` verhindert mid-word-Umbruch bei langen Pfaden.

## [2.34.1] – 2026-04-23

Short version: Workflow-Dokumentation aktualisiert (neue Action- und CLI-Workflows in README).

### Changed

- Dokumentation: Workflow-Tabelle in `.github/workflows/README.md` um neue Workflows ergänzt (`release-action.yml`, `action-smoke.yml`, `doc-consistency.yml`, `drift-baseline-persist.yml`, `self-improvement-loop.yml`, u.a.); neue "Action vs CLI"-Testmatrix hinzugefügt.

## [2.34.0] – 2026-04-23

Short version: Drift Self-Improvement Loop (ADR-097), CI/security-hygiene stabilization for context mapping import + Bandit/model-consistency reliability.

### Added

- **Drift Self-Improvement Loop / DSOL (ADR-097).** Nie endender, sich selbst verstärkender Optimierungs-Loop für drift selbst, vollständig POLICY-konform (kein Auto-Merge, kein PR-Kommentar, kein Push). Neues Modul `src/drift/self_improvement/` (`engine.py`, `__init__.py`) mit Pydantic-Modellen `ImprovementProposal`/`ImprovementReport`/`CycleLedgerEntry` (alle frozen). Sechs-Phasen-Zyklus: **OBSERVE** (lädt `benchmark_results/drift_self.json` und `benchmark_results/kpi_trend.jsonl` mit grazilem Fallback) → **DIAGNOSE** (regressive KPI-Slopes < `-0.005`, Hotspot-Findings via `severity_weight × score` mit Per-Signal-Cap = `max_items // 3`, stale Audits ≥ 14 Tage) → **PROPOSE** (Frozen-Pydantic-Records mit `proposal_id`, `score`, `rationale`, `recurrence`) → **EMIT** (deterministische Artefakte unter `work_artifacts/self_improvement/<cycle_ts>/proposals.json`+`summary.md`) → **TRACK** (Append-only-Ledger `.drift/self_improvement_ledger.jsonl` macht wiederkehrende Findings über `recurrence=2` priorisiert) → **WAIT** (Cron-Tick). Neuer CLI-Group `drift self-improve` mit Subcommands `run` (Optionen `--repo`, `--max-proposals` Default 10, `--trend-window` Default 5, `--format text|json`) und `ledger` (read-only Anzeige der letzten 20 Cycles). Neuer Workflow `.github/workflows/self-improvement-loop.yml` (Cron `17 4 * * 0` = wöchentlich Sonntag, `workflow_dispatch` mit `max-proposals`-Input, `permissions: contents: read` only, lädt Cycle-Artefakt 365 Tage, schreibt `summary.md` in `$GITHUB_STEP_SUMMARY`, **kein** Issue/PR-Kommentar). Hard Guardrails: `DEFAULT_MAX_PROPOSALS=10` als Flood-Guard, Per-Signal-Dominance-Cap, Loop steuert nie selbst Scoring-Gewichte (Observation-Behavior-Coupling explizit ausgeschlossen). Tests: `tests/test_self_improvement_loop.py` (11 pass — Cap-Enforcement, Per-Signal-Dominance, Recurrence-Compounding, Negative-Slope-Detection, Stable-Metric-No-Op, Stale-Audit, Determinismus, CLI-Wiring `run`+`ledger`, Frozen-Model). Audit-Artefakte FMEA und Risk-Register aktualisiert (Loop-Runaway, Metric-Gaming, Ledger-Korruption, Push-Without-Consent).

### Fixed

- **CI/Security-Hygiene Stabilisierung.** `_context_mapping` ist jetzt explizit tracked (`.gitignore` Ausnahme + `scripts/_context_mapping.py`), wodurch der Import in `tests/test_context_mapping.py` auf GitHub Actions stabil funktioniert. Bandit-Hotspots (SHA1/B324, `urlopen`/B310) wurden auf SHA256 bzw. begründete `# nosec B310`-Markierungen umgestellt. Zusätzlich wurde die Model-Consistency auf `2.34.0` synchronisiert (`SECURITY.md`) und ein flakiger Hypothesis-Deadline-Fall in `tests/test_property_based.py` entschärft (`deadline=None`).

## [2.33.0] – 2026-04-22

Short version: llms.txt deterministic autogen (ADR-092), Baseline-Ratchet Pre-Commit-Gate (ADR-093), Human-Approval-Gate Workflow (ADR-094), Opt-in Issue-Auto-Filing (ADR-095), Automation-Hardening (ADR-096).

### Added

- **`llms.txt` deterministic autogen (Paket 1C, ADR-092).** Neuer Generator `scripts/generate_llms_txt.py` rendert `llms.txt` vollständig aus `pyproject.toml` (Version) und `src/drift/signal_registry.py` (Signale). Deterministische Sortierung (Gewicht ↓ / Abkürzung ↑), SEO-Overrides (CWE-Tags für MAZ/HSC/ISD, AI-Attribution für PHR) in `_DOC_OVERRIDES`. Modi: `--write` (Default) und `--check` (exit 1 + unified diff). Pre-Push-Hook Schritt `[0/6]` regeneriert und committet bei Drift still (`chore: sync version refs`); Release-Workflow amend+re-tagt; `scripts/check_model_consistency.py` Checks 5+6 delegieren an `--check` (ersetzt 15-Signal-`code_to_key`-Tabelle, deckt jetzt alle 25 Kern-Signale ab). Erste Regeneration nimmt `TSB` (Type Safety Bypass) in die Report-only-Liste auf, das bisher still unterschlagen wurde. Tests: `tests/test_llms_txt_generator.py` (7 pass). Audit-Artefakte FMEA und Risk-Register aktualisiert.

- **Baseline-Ratchet Pre-Commit-Gate (Paket 2A, ADR-093).** `drift baseline diff` bekommt neues Flag `--fail-on-new N` (Exit 1, wenn neue Findings > N; rückwärtskompatibel, Default unverändert). Neuer Subcommand `drift baseline update --confirm` als expliziter, reviewbarer Alias für `baseline save` (ohne `--confirm` → Exit 2). Neuer Pre-Commit-Hook-Eintrag `drift-baseline-check` in `.pre-commit-hooks.yaml` (`drift baseline diff --fail-on-new 0`). Verhindert stille Baseline-Erosion durch Agenten oder Shell-History. Tests: `tests/test_baseline.py::TestBaselineRatchetADR093` (5 pass). Audit-Artefakte FMEA und Risk-Register aktualisiert.

- **Human-Approval-Gate Workflow (Paket 2B, ADR-094).** Neuer GitHub-Actions-Workflow `.github/workflows/drift-agent-gate.yml` triggert auf `pull_request`-Events gegen `main` (Pfad-Filter: `src/**`, `tests/**`, Agent-Prompt, Schema-Dateien, `decisions/**`). Parst JSON-Output von `drift analyze` auf BLOCK-Actions (`agent_telemetry.agent_actions_taken[*].gate == "BLOCK"`) und Severity-Findings (`critical`/`high`); failt mit Exit 1, wenn BLOCK-Signal vorhanden und PR-Label `drift/approved` nicht gesetzt ist. Token-Permissions bewusst read-only (`contents:read`, `pull-requests:read`) — Workflow kann sich nicht selbst freigeben. Letzter Step ruft `scripts/verify_gate_not_bypassed.py --all-artifacts` (Soft-Fail bei Exit 2) als Tampering-Check. `.github/CODEOWNERS` um Section "Agent-critical files" erweitert. Tests: `tests/test_drift_agent_gate_workflow.py` (13 pass). Audit-Artefakte aktualisiert.

- **Opt-in Issue-Auto-Filing (Paket 2C, ADR-095).** Die drift GitHub Action bekommt zwei neue Inputs `create-issue` (default `false`) und `issue-labels` (default `drift,agent-block`). Bei `create-issue: true` filt ein neuer Step am Ende der Action für jedes BLOCK-Finding ein GitHub-Issue. Dedup via stabilem HTML-Marker `<!-- drift-finding-id: ... -->`. Neues `scripts/gh_issue_dedup.py`. Tests: `tests/test_gh_issue_dedup.py` (12 pass) + `tests/test_action_yml_paket_2c.py` (6 pass). Audit-Artefakte aktualisiert.

- **Automation-Hardening für Pakete 2A/2B/2C (ADR-096).** `drift baseline status --format rich|json`, `actions/setup-python@v5` mit `cache: pip`, `--max-issues N` Flood-Guard, `workflow_call:` Trigger. Tests: `tests/test_baseline_status.py` (4) + `tests/test_automation_enhancements.py` (7) — 11 pass.

## [2.32.0] – 2026-04-22

Short version: Drift-Retrieval-RAG MVP (ADR-091), Agent-Telemetry Schema 2.2 (ADR-090), QA 2026 Pakete 1A/1B/2B/3A (ADR-089), K2 Outcome-Feedback-Ledger (ADR-088), K1 Blast-Radius-Engine (ADR-087), agent-workflow shortcuts.

### Added

- **Drift-Retrieval-RAG MVP (ADR-091).** Neues Paket `src/drift/retrieval/` plus zwei MCP-Tools `drift_retrieve` und `drift_cite`, die Coding-Agenten zwingen, Aussagen über drift selbst (Policy, Signale, ADRs, Audit-Artefakte, Signal-Rationale, Benchmark-Evidence) gegen einen verifizierten, SHA-verankerten Fact-Korpus zu grounden. Lexical BM25 Okapi (`k1=1.5`, `b=0.75`, deterministischer Tie-Break nach `fact_id`), keine Embeddings, keine Netz-I/O, keine LLMs — 1318 Chunks über 164 Sources werden auf MVP-Corpus (drift selbst) in Cold-Start ~142 ms indexiert, Warm-Retrieve p50 = 0.35 ms. Stabile Fact-IDs (`POLICY#S<n>.p<m>`, `ADR-<nnn>#<section>`, `AUDIT/<file>#<row>`, `SIGNAL/<id>#<field>`, `EVIDENCE/v<version>#<key>`) mit append-only Migration-Registry `decisions/fact_id_migrations.jsonl` für zyklus-sichere transitive Auflösung. `corpus_sha256` in jeder Response als Reproduzierbarkeits-Anker; 3-Layer-Cache (Memory → Disk → Rebuild) unter `.drift-cache/retrieval/` mit mtime- und SHA-Vergleich. Grounding-Contract als Instruction `.github/instructions/drift-rag-grounding.instructions.md` (soft gate, Phase-4 demarkiert für harte CI-Erzwingung). Tests: `tests/test_retrieval_corpus.py` (12), `tests/test_retrieval_search.py` (8), `tests/test_mcp_retrieval_tools.py` (8) — 27 pass, 1 skip. Gold-Set Precision@5 = 100% (15/15 Queries, Threshold ≥ 80%). Feature-Evidence: `benchmark_results/v_next_drift_retrieval_rag_feature_evidence.json`. Audit-Artefakte FMEA, Risk-Register, STRIDE und Fault-Trees aktualisiert gemäß POLICY §18.

- **Agent-Telemetry Schema 2.2 (Paket 1B, ADR-090).** JSON-Output bekommt einen additiven Top-Level-Block `agent_telemetry`, der als Audit-Trail für autonome Agent-Loops (ADR-089) dient. Neuer Block enthält `schema_version` (Pflicht, pinned auf `"2.2"`), optionales `session_id`, drei berechnete Counter (`total_auto`, `total_review`, `total_block`) und eine geordnete `agent_actions_taken`-Liste mit `AgentActionType`-Enum (`auto_fix`, `review_request`, `block`, `revert`, `feedback`, `nudge`), `reason`, optional `finding_id`, `severity`, `gate` (`AUTO`/`REVIEW`/`BLOCK`/null), `safe_to_commit`, `feedback_mark`, `timestamp`, `metadata`. Default-Serialisierung ist explizites JSON-`null` — bestehende Konsumenten ohne Agent-Loop brechen nicht (additive Minor-Bump 2.1 → 2.2). `drift.output.schema.json` via `scripts/generate_output_schema.py` regeneriert; neuer CI-Drift-Gate `tests/test_output_schema_drift.py` (9 Tests) ruft `--check` per Subprocess auf, verifiziert Enum-Sync zwischen `AgentActionType` StrEnum und Schema-Enum, und validiert echte `analysis_to_json`-Ausgaben positiv und negativ (invalider `gate`-Wert). Audit-Artefakte FMEA, Risk-Register, STRIDE und Fault-Trees aktualisiert gemäß POLICY §18.

- **K2 — Outcome-Feedback-Ledger MVP (ADR-088).** Neues Paket `src/drift/outcome_ledger/` plus API `drift.api.analyze_commit_pair` und Ops-Runner `scripts/ops_outcome_trajectory_cycle.py`. Der Runner enumeriert Merge-Commits der first-parent History, rescored parent und merge in isolierten **detached `git worktree`**-Ordnern (Haupt-Worktree wird nie verändert) und schreibt append-only `MergeTrajectory`-Einträge nach `.drift/outcome_ledger.jsonl`. Aggregat-Reports (Direction, Author-Split Human/AI/Mixed, Per-Signal-Delta, Staleness-Buckets <=90d/90-180d/>180d) landen als JSON + Markdown unter `.drift/reports/<ts>/`. MVP-Scope: **nur Ledger + Report**, keine automatische Anpassung von Scoring-Gewichten (explizit für Phase 3 abgegrenzt). Frozen Pydantic-Modelle mit `schema_version=1`. Tests: `tests/test_outcome_ledger.py` (12 pass, 2 skipped — Worktree-Integration). Audit-Artefakte FMEA, STRIDE, Fault-Trees und Risk-Register aktualisiert.
- **K1 — Blast-Radius-Engine (ADR-087).** Neue deterministische Engine unter `src/drift/blast_radius/**`, die vor strukturellen Änderungen berechnet, welche ADRs, Guard-Skills, Arch-Module und Policy-Gates invalidiert würden. Exponiert als MCP-Tool `blast_radius` via A2A-Router und als Pre-Push-Gate 9 (`scripts/check_blast_radius_gate.py`). Reports werden als versionierte Artefakte unter `blast_reports/<timestamp>_<sha>.json` persistiert; kritische Impacts (`criticality: critical`) erfordern eine Maintainer-Ack-Datei unter `blast_reports/acks/<sha>.yaml`, andernfalls blockiert der Push. Bypass via `DRIFT_SKIP_BLAST_GATE=1`, Live-Generierung via `DRIFT_BLAST_LIVE=1`. Optionale ADR-Frontmatter-Felder `scope:` und `criticality:` plus Validator `scripts/validate_adr_frontmatter.py`. Text-Fallback für ADRs ohne Frontmatter und Namenskonvention für Guard-Skills ohne `applies_to:` erhalten Migrations-Kompatibilität. Tests: `tests/test_blast_radius_core.py` (8) + `tests/test_blast_radius_mcp.py` (4), alle grün. Audit-Artefakte FMEA, Risk-Register und Fault-Trees aktualisiert.

### Fixed

- **Add `@needs_tree_sitter` skip guard for TSB issue-318–325 tests.** Six additional TSB regression test files (issues 318, 319, 322, 323, 324, 325) were missing the tree-sitter skip guard on their `analyze`-dependent tests, causing CI failures on matrix entries without `tree-sitter-typescript`. Added skip decorator to all affected tests.

## [2.30.0] – 2026-04-22

Short version: Regression fixes for Windows CI runners — repair PowerShell em-dash in release workflow and add missing `@needs_tree_sitter` skip guard to TSB signal regression tests.

### Fixed

- **Repair PowerShell em-dash terminator in release workflow.** The `Sync version refs` step in `.github/workflows/release.yml` contained a Unicode em-dash (`—`) in a `Write-Output` string that caused a `TerminatorExpectedAtEndOfString` error on Windows runners. Replaced with ASCII hyphen.
- **Add `@needs_tree_sitter` skip guard for TSB issue-317 test.** `test_issue_317_tsb_message_handler_test_support.py` called `TypeSafetyBypassSignal().analyze(...)` without a skip guard; CI matrix entries without `tree-sitter-typescript` produced 0 findings, causing `assert 0 == 1`. Added skip decorator mirroring the pattern from `test_issue_298`.

## [2.29.0] – 2026-04-22

Short version: Agent-workflow shortcuts (Makefile targets, companion scripts), `drift adr` subcommand, `TaskSpec.to_patch_intent()`, release version-sync CI step; plus Trend-Gate Enforcement, Fingerprint v2, and queue/session improvements.

### Added

- **Agent-Workflow Shortcuts.** New `make` targets (`feat-start`, `fix-start`, `catalog`, `gate-check`, `handover`, `changelog-entry`, `audit-diff`) and companion scripts (`catalog.py`, `gate_check.py`, `generate_changelog_entry.py`, `risk_audit_diff.py`, `session_handover.py`, `sync_version.py`) codify agent-driven development workflows. `drift adr` CLI subcommand lists ADRs with optional task-relevance filter. `TaskSpec.to_patch_intent()` converts a TaskSpec to PatchIntent for patch-engine integration.
- **Trend-Gate Enforcement (ADR-086).** `drift check` and `drift ci` support an optional `gate.trend` block that blocks on persistent score degradation over a commit window; configurable via `enabled`, `window_commits`, `delta_threshold`, `require_remediation_activity`; CLI overrides `--trend-gate/--no-trend-gate`.
- **Fingerprint v2 + Fuzzy HEAD-subtraction (ADR-082, ADR-083).** `finding_fingerprint()` now hashes `(signal_type, file, symbol_identity, stable_title)` — line numbers excluded, renames/refactors stable. `drift_diff` falls back to fuzzy `(signal, file, stable_title)` key for symbol-less findings. Baseline schema v2 writes `fingerprint_v1` alias for two release cycles.
- **ADR-081 Queue/Session Hardening (Q1-Q5).** SG-008/SG-009 gate `drift_fix_apply`/`drift_patch_begin` on non-empty `selected_tasks`; concurrent-writer advisory lockfile; plan-staleness surfacing with auto-redirect to `drift_fix_plan`; `drift_session_start` resumes with `next_tool_call` pointing to first pending task. Persistent fix-plan queue survives MCP session restarts via append-only `queue.jsonl`; `fresh_start=True` opts out of replay.
- **`drift_nudge` cold-start latency −3.5 s (ADR-085).** Eliminated redundant post-analysis file-hash pass; `file_hashes_out` parameter surfaces hashes from `IngestionPhase` to callers.

## [2.28.1] – 2026-04-22

Short version: Skip `os.utime follow_symlinks=False` on Windows in test suite to fix Codecov 0% badge; simplify issue-317 TSB fixture to fix Python 3.13 CI failure.

### Fixed

- **Skip `os.utime follow_symlinks=False` on Windows in test suite.** `TestMtimeFingerprint::test_symlink_excluded_from_fingerprint` raised `NotImplementedError` on Windows runners, causing pytest to abort before generating `coverage.xml` and resulting in a 0% Codecov badge.
- **Simplify issue-317 TSB fixture to fix Python 3.13 CI failure.** The `test_issue_317` fixture used `vi.fn(async () => null)` which caused `_count_bypasses` to produce no findings under Python 3.13 due to tree-sitter grammar differences. Replaced with straightforward `{} as unknown as T` patterns.

## [2.27.0] – 2026-04-21

Short version: Release 2.27.0.

## [2.26.2] – 2026-04-22

Short version: Forward `--yes` flag to `require_clean_git` in `fix_plan` CLI; remove unused `yes` parameter from `fix_apply` public API.

### Fixed

- `fix_plan` CLI `--yes` flag now forwarded as `require_clean_git=not yes` to `api_fix_apply`; removed unused `yes` parameter from `fix_apply` public API.

## [2.26.1] – 2026-04-22

Short version: Vulture dead-code fix; yes flag now forwarded to require_clean_git in fix_plan CLI.

### Fixed

- `fix_plan` CLI `--yes` flag now forwarded as `require_clean_git=not yes` to `api_fix_apply`; removed unused `yes` parameter from `fix_apply` public API. Fixes vulture dead-code CI failure.

## [2.26.0] – 2026-04-22

Short version: Strict MCP guardrails default true (ADR-080); SG-007 scope-gate; SG-005a/SG-006a brief staleness; nudge `revert_recommended` hardening + pre-commit gate; brief anti-patterns; enriched ADR relevance; cross-file hint.

### BREAKING behavior

- `agent.strict_guardrails` default flipped from `false` to `true` (ADR-080). Set `agent.strict_guardrails: false` in `drift.yaml` to restore v2.25.0 behaviour.

### Added

- **SG-007 / SG-005a / SG-006a guardrails**: `drift_fix_apply` / `drift_patch_begin` blocked when last brief raised low scope confidence (SG-007) or brief is stale — score drift > 0.1, > 20 tool calls, or > 30 min (SG-005a/SG-006a).
- `drift_brief` raises active `scope_gate` block on `scope.confidence < 0.5`; surfaces top-3 negative-context anti-patterns in JSON response and prompt block.
- `drift_nudge` persists `.drift-cache/last_nudge.json` (schema_version=1); `scripts/nudge_gate.py` + pre-commit hook blocks commits when last nudge recommended REVERT and flagged files are unchanged. ADR-080 added.

### Changed

- `drift_nudge.revert_recommended` tightened; `cross_file_hint` added on non-fast-path runs; `adr_scanner` uses 2000-char relevance window and skips alternatives headings; `guard_contract._find_related_tests` greps import patterns in test files.

### Fixed

- `tool_calls_since_brief` counter now increments via `begin_call` once a brief has been recorded.

## [2.25.0] – 2026-04-21

### Added

- Session tracks `last_brief_at`, `last_brief_score`, `last_scan_score`, `tool_calls_since_brief`; `_brief_staleness_reason()` detects stale briefs by score delta, time, or call count.
- SG-005/SG-006 enforcement hardened: `drift_fix_apply` and `drift_patch_begin` now also reset brief-staleness counters.

### Fixed

- Mypy: correct `prepared_exclude` type annotations in `file_discovery`; `getattr` fallback for `repo_path` in `session_handover`.
- Ruff: simplify conditionals in `session_handover`; break overlong line in `nudge.py`.

## [2.25.0] – 2026-04-21

Short version: Handover-artifact gate at `drift_session_end` (ADR-079); deterministic L1–L3 validation (existence, shape, placeholder denylist) with optional L4 LLM-review hook; `force`/`bypass_reason` escape hatch with auditable logging and bounded retries.

### Added

- `drift.session_handover` module: `ChangeClass`, `RequiredArtifact`, `ShapeError`, `PlaceholderFlag`, `ValidationResult`, `classify_session`, `required_artifacts`, `validate`, `validate_bypass_reason`.
- `drift_session_end(force=..., bypass_reason=..., session_md_path=..., evidence_path=..., adr_path=...)` parameters; agent-provided paths skip server-side discovery.
- Error codes `DRIFT-6100` (handover artifacts missing/invalid, session remains alive for retry) and `DRIFT-6101` (force=true with invalid/placeholder bypass reason).
- `DriftSession.handover_retries` counter; `MAX_HANDOVER_RETRIES=5` bound on retries before bypass becomes mandatory.
- Opt-in L4 LLM-review hook via `DRIFT_SESSION_END_LLM_REVIEW=1` or injected `llm_reviewer` callable; fails closed on reviewer exception.
- ADR-079, session-handover contract partial, Markdown handover template, `drift-session-handover-authoring` skill.

### Changed

- Audit artifacts updated per Policy §18: new FMEA rows, risk-register entry, and fault tree for handover-gate bypass and false-accept paths.
- `drift_session_end` now classifies touched files via git diff against `git_head_at_plan` (fallback: trace metadata); empty sessions (no tool work, no completed tasks, CHORE class) are exempted to preserve read-only exploration.

## [2.24.0] – 2026-04-21

Short version: ADR scanner; enriched `brief` API (layer_contract, relevant_tests, active_adrs); nudge post-edit regression detector; MCP strict guardrail rules SG-005/SG-006.

### Added

- `adr_scanner`: stdlib-only parser for `decisions/*.md`; returns active ADRs (accepted/proposed) filtered by scope paths and task keywords.
- `brief` API: response now includes `layer_contract`, `relevant_tests`, `active_adrs`; prompt block extended with Layer Constraints and Active ADR Constraints sections.
- Nudge regression detector: `timeout_ms` param (default 1000 ms); new fields `revert_recommended`, `latency_ms`, `latency_exceeded`, `auto_fast_path`; explicit REVERT directive on degrading+unsafe edits.
- MCP SG-005/SG-006: `drift_fix_apply` and `drift_patch_begin` require prior `drift_brief` in strict sessions.

### Changed

- `copilot-instructions.md`: mandatory Post-Edit Drift-Nudge section; `drift.yaml`: `doc_impl_drift` excluded from `decisions/*`.

## [2.22.0] – 2026-04-20

Short version: eight new MCP tools (intent-loop, fix-apply, steer, compile-policy, suggest-rules, generate-skills); bounded-context router modules; CXS batch refactoring of CLI commands.

### Added

- `drift_capture_intent`, `drift_verify_intent`, `drift_feedback_for_agent`: intent-loop MCP tools backed by `mcp_router_intent`.
- `drift_fix_apply`, `drift_steer`, `drift_compile_policy`, `drift_suggest_rules`, `drift_generate_skills`: fix-apply, architecture steering, policy compilation, rule suggestion, and skill generation tools.
- `mcp_router_intent.py`, `mcp_router_architecture.py`: bounded-context modules for intent-loop and architecture-steering logic.

### Changed

- CLI commands refactored (CXS batch) for lower cognitive complexity.
- `diff.py`, `drift_map_api.py`, `validate.py`, `github_correlator.py`, `outcome_correlator.py`: API and calibration layer cleanup.

## [2.21.0] – 2026-04-20

Short version: intent-capture system for structured planning; `lang` module with multilingual plain-language messages; `--audience` and `--language` CLI flags; A2A endpoints for intent/feedback loop.

### Added

- `drift intent` command and `drift.intent` module: intent capture with LLM/keyword classification, YAML contract storage, classify/formalize/repair/validate/verify pipeline. Optional `[llm]` extra (`litellm>=1.0`).
- `drift.lang` module: multilingual plain-language message catalog; `--audience` and `--language` flags on `drift analyze` for non-technical stakeholders.
- A2A router: `capture_intent`, `verify_intent`, `feedback_for_agent` endpoints exposed via `drift.api`.

### Fixed

- Security hygiene: `# pragma: allowlist secret` annotations on test-fixture strings; `.secrets.baseline` refreshed for new files (`skills-lock.json`, `eval-viewer/viewer.html`).
- mypy: resolved `no-any-return`, `import-untyped`, `no-redef` and `typeddict-item` errors in `drift.intent` and `drift.lang`.

## [2.20.0] – 2026-04-20

Short version: guard_contract API and `drift context` CLI for pre-edit architectural constraints; nudge finding cluster summary and dynamic agent_instruction; enriched feedback response.

### Added

- `guard_contract()` API and `drift_guard_contract` MCP tool: returns a machine-readable pre-edit contract (layer, invariants, forbidden imports, public API surface, optional findings) to prevent architectural drift before edits. Closes #427.
- `drift context --target <path> [--for-agent] [--include-findings]` CLI command for generating guard contracts for AI agents and humans. ADR-078.
- Nudge: `finding_cluster_summary` field (`total_new`, `by_signal`) in nudge response for richer agent observability.
- Nudge: dynamic `agent_instruction` based on direction — degrading state triggers `drift_brief` recommendation, safe-to-commit state triggers verification guidance.
- Feedback: enriched response includes `pending_fp_count`, `next_tool_call: {drift_calibrate}`, and `agent_instruction` to guide agents through the calibration loop.

## [2.19.1] – 2026-04-20

Short version: MCP tools startup assertion, SECURITY.md and llms.txt consistency fixes.

### Fixed

- `mcp_server.py`: `_assert_mcp_tools_registered()` verifies all exported MCP tools are present in the FastMCP runtime registry at startup.
- `SECURITY.md`: added 2.19.x as supported release line.
- `llms.txt`: updated release status to v2.19.1.

## [2.19.0] – 2026-04-20

Short version: MCP startup verification, SECURITY.md and llms.txt consistency fixes for v2.19.0.

### Fixed

- `mcp_server.py`: `_assert_mcp_tools_registered()` verifies all exported MCP tools are present in the FastMCP runtime registry at startup; raises `RuntimeError` with actionable message on missing tools to surface silent schema-generation failures.
- `SECURITY.md`: added 2.19.x as supported release line.
- `llms.txt`: updated release status to v2.19.0.

## [2.18.1] – 2026-04-20

Short version: Nudge baseline TTL configurable, drift analyze --no-cache and drift cache clear, cohesion deficit FP reduction for private helpers, A2A scan param forwarding.

### Added

- `nudge_baseline_ttl_seconds` config field (default 900) to tune baseline snapshot validity; replaces persisted TTL on warm load. Closes #421.
- `drift analyze --no-cache` and `drift cache clear` (with `--parse-only`/`--signal-only`/`--dry-run`): per-run cache bypass and manual cache invalidation. Closes #424.
- Auto-update drift score badge in `README.md` on main-branch CI pushes.

### Fixed

- `cohesion_deficit`: private (`_`-prefixed) functions excluded from semantic unit counting to reduce false positives after helper extraction refactors.
- `a2a_router`: forward `target_path`, `max_findings`, and `strategy` to `scan()` handler.

## [2.18.0] – 2026-04-20

Short version: Suppression insert/list commands, diff --auto feedback loop, explain --from-file, interactive review, and staleness detection for inline suppressions.

### Added

- `suppression.py` + `commands/suppress.py`: `insert_suppression_comment()` writes `drift:ignore` comments (Python/TS/JS); `drift suppress list --check-stale` flags stale suppressions via embedded `hash:` tag; `include_hash` kwarg embeds hash at creation.
- `drift diff --auto`: post-fix feedback loop auto-saves scan snapshot to `.drift-cache/last_scan.json`; reruns and renders score delta without specifying commit hashes. (`commands/_last_scan.py` helper added.)
- `drift explain FINGERPRINT --from-file analysis.json`: resolve findings from a cached JSON without re-running a live scan.
- `output/interactive_review.py`: interactive per-finding TP/FP review session appending verdicts to `.drift/feedback.jsonl` for calibration (`drift analyze --review`).

### Fixed

- `suppression.py`: `InlineSuppression` gains `stored_hash` / `current_hash`; `collect_inline_suppressions()` computes current line-content hash for staleness detection.

## [2.17.2] – 2026-04-19

Short version: Docs-only — update drift score badge and self-analysis result to 0.36.

### Changed

- README: drift score badge updated from 0.44 to 0.36 (Grade B).
- `benchmark_results/drift_self.json`: refreshed self-analysis at v2.17.1.

## [2.17.1] – 2026-04-19

Short version: CI stabilization — ruff, detect-secrets, and test-fixture fixes.

### Fixed

- Ruff unused-import / import-order issues in `test_patch_writer_gcd.py` resolved.
- detect-secrets false positive for 17-character hex test fixture suppressed via pragma.

## [2.17.0] – 2026-04-18

Short version: PatchWriter auto-apply for add_docstring + add_guard_clause (ADR-076), EDS micro-helper dampening (ADR-077), contextlib.suppress cleanup, and test fixes.

### Added

- **PatchWriter auto-apply (ADR-076)**: `PatchWriter` ABC + registry; `AddDocstringWriter` and `AddGuardClauseWriter` generate executable libcst-based patches; `drift.api.fix_apply()` applies patches for HIGH/LOCAL/LOW tasks with clean git state.
- **EDS micro-helper dampening (ADR-077)**: Raised EDS threshold for private micro-helpers (single-underscore prefix, <5 lines, <3 parameters) to reduce false positives on trivial helpers.

### Fixed

- `contextlib.suppress` replaces bare `try/except/pass` in `analyzer.py` (SIM105).
- Stale `_priority_rank` monkeypatch removed from test after unused import cleanup.
- Workflow stability: ruff unused-import / import-order issues in test files resolved; detect-secrets false positive suppressed via pragma; `release.yml` guards against amending an existing HEAD tag causing non-fast-forward; `validate-release.yml` PS5.1 `NativeCommandError` on `gh release view` resolved.

## [2.15.1] – 2026-04-18

Short version: Patch Engine (ADR-074), ArchGraph layer, root_cause field on Finding (ADR-075), CLI-UX polish, and per-signal timing telemetry.

### Added

- **root_cause field on Finding (ADR-075)**: `Finding.root_cause` explains *why* a problem arose; `_root_cause_for()` covers all six signal types; exposed via `AgentTask`, JSON, and Rich output so agents address causes rather than symptoms.
- **CLI-UX polish**: `drift status` shows an animated spinner, profile-fallback warning, `✓ Clean – N files / M signals checked` output, and baseline-delta line; `docs/ux/cli-ux-quality-matrix.md` documents the UX assessment.
- **Patch Engine (ADR-074) + ArchGraph integration**: Three-phase `patch_begin → patch_check → patch_commit` protocol; `PatchIntent`/`PatchVerdict` models; `ArchGraphStore` with decision constraints and reuse index; available via API, MCP, CLI, and A2A.
- **Observability additions**: `_refine_edit_kind()` extended for `ARCHITECTURE_VIOLATION`; `TaskGraph.to_summary_text()` for token-efficient agent briefings; `SignalPhase` per-signal wall-clock timing in `phase_timings.per_signal`.

### Fixed

- **Validation, CI stability + PFS precision**: `TaskSpec` frozen after validation; executor timeouts enforced; `save_history()` retries on Windows `PermissionError`; detect-secrets false positive resolved. PFS error_handling FP rate reduced: `ast.Continue` maps to `loop_skip`; exception types stripped before variant comparison; propagation-only handlers excluded from fragmentation count. `propagation_excluded_count` added to finding metadata (Issue #526).

## [2.11.0] - 2026-04-17

Short version: generate_skills API for agent-driven SKILL.md briefings, configurable quality-gate tolerances, LLM output max-findings cap, and singleton thread-safety fix.

### Added

- **`generate_skills` API**: `drift.api.generate_skills()` and `drift.arch_graph.SkillBriefing` — analyses the persisted `ArchGraph` and returns structured per-module briefings an AI agent uses to create `.github/skills/<name>/SKILL.md` files; filters by `min_occurrences` and `min_confidence`; enriches briefings with matched ADR/decision constraints.
- **Configurable quality-gate tolerances**: quality-gate thresholds tunable via `drift.yaml` `quality:` section without code changes.

### Fixed

- **LLM format findings cap**: `llm` output format now respects `--max-findings` to avoid token overflow.
- **`BaselineManager` singleton thread safety**: double-checked locking replaced with `threading.Lock` guard to prevent race conditions under concurrent access.
- **CI stability**: TypeScript CXS ground-truth fixture now skips gracefully when `tree-sitter-typescript` is not installed; `.secrets.baseline` updated for new source files; release workflow PSR step now exits 0 on successful tag creation even when PSR returns a non-zero exit code on Windows.

## [2.12.1] - 2026-04-17

Short version: Patch — detect-secrets false positive suppression and validate-release PowerShell fix.

### Fixed

- **detect-secrets false positives**: added `# pragma: allowlist secret` to intentional secret-like test fixtures to suppress security-hygiene CI failures.
- **validate-release PowerShell**: fixed error handling in the validate-release script for Windows PowerShell compatibility.

## [2.12.0] - 2026-04-17

Short version: Arch-graph API, remediation memory (ADR-072), consolidation opportunity detector (ADR-073), and enriched repair outcome tracking.

### Added

- **Arch-graph API + ADR-072 + ADR-073**: `drift.arch_graph` module (ArchGraph, ArchGraphStore, decision constraints, feedback-loop, reuse index, seeding); `drift.api.steer` and `drift.api.suggest_rules` entry points; `RepairTemplateRegistry.similar_outcomes()` and `fix_plan`-level `similar_outcomes` enrichment (ADR-072); `build_consolidation_groups()` + `TaskGraph.consolidation_opportunities` + per-task `consolidation_group_id` (ADR-073); `record_outcome` enriched with `task_id`, `new_findings_count`, `resolved_count`.

### Fixed

- **Negative-context registry coverage gate (#472)**: registry-based policy assertion added; `type_safety_bypass` declared fallback-only.
- **Telemetry path sanitization (#464)**: home-directory path prefixes masked to `~` to prevent OS username leakage.
- **Error messages and test alignment**: `DRIFT-1001`/`DRIFT-1002` now reference `drift config validate`; JSON snapshot and stubs aligned; ruff/mypy cleanup.

### Docs

- Added inline quick-start comments to `action.yml` and `.pre-commit-hooks.yaml`; translated ROADMAP to English; clarified optional-dep descriptions in `pyproject.toml`.

## [2.11.1] - 2026-04-16

Short version: Precision and stability fixes across signals, MCP session management, incremental analysis, and output visibility.

### Added

- **Defect corpus benchmark** and **agent workflow skills**: ground-truth recall benchmark (`scripts/defect_corpus_benchmark.py`) and `.github/skills/` files for brainstorming, debugging, TDD, and planning.

### Fixed

- **Signal and discovery coverage** (#521, #522): file discovery includes `.pyi/.mjs/.cjs/.mts/.cts`; scan warns when active signal filters match no registered signal.
- **Incremental and suppression correctness** (#511, #513, #514, #516): nudge warns on cross-file blind spots; incremental prunes deleted-file stale findings; expired `until:` suppressions auto-reactivate; TS/JS skip visibility restored.
- **MCP session stability** (#487, #488, #494, #495, #496): strict-guardrails cache invalidated per call; `get_running_loop()` modernization; session pool cap (50); non-autopilot enrichment; catalog import fallback.
- **Output and API fixes** (#369, #374, #388, #389, #391, #393, #474, #476, #477, #478, #479, #485, #486, #512): rich output surfaces parser failures; finding IDs in concise/detailed; fix-plan fast-path pending filter; CI format deprecation warnings; `drift validate` exit code; annotations newline encoding; signal label additions.

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
