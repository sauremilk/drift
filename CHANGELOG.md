# Changelog

All notable changes to drift-analyzer are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.6.0] – 2026-03-26

### Added

- **Expanded TypeScript analysis**: Added full-semantic TypeScript support with improved import resolution, workspace assignment, vendor filtering, and dedicated TS/TSX architectural rules with benchmark coverage.
- **Delta-first interpretation and context tags**: Added ADR-005 delta-first score interpretation and ADR-006 context tagging so score changes and migration phases are visible and actionable in CLI and JSON output.
- **3 Consistency Proxy Signals (ADR-007)**: BEM (Broad Exception Monoculture), TPD (Test Polarity Deficit), and GCD (Guard Clause Deficit) added as report-only findings with weight `0.00` plus empirical validation artifacts.
- **Adoption and trust material**: Added report-only CI onboarding guidance, concrete example findings, a central start-here path, and expanded trust/evidence documentation for safer rollout.

### Changed

- **Release hygiene and feature evidence**: Strengthened pre-push quality checks and enforced tests plus empirical artifacts for `feat:` work.
- **Public docs and onboarding**: Expanded README, comparisons, integrations, FAQ, use cases, and rollout guidance to align public messaging with actual maturity.
- **TypeScript performance and discovery**: Reduced redundant discovery work and improved workspace-boundary handling in TS analysis.

### Fixed

- **Core analysis hardening**: Improved pipeline, config, suppression, cache, and observational analysis behavior to reduce rollout surprises.
- **Delta gate correctness**: Tightened typing and snapshot handling for delta-based checks while keeping existing `fail_on` behavior backward compatible.
- **Trust and rollout defaults**: Aligned defaults and messaging around conservative report-only rollout.

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
