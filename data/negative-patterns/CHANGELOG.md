# Negative-Pattern Library — Changelog

All notable changes to the negative-pattern dataset are documented here.
This changelog follows [Keep a Changelog](https://keepachangelog.com/) and
uses its own [SemVer](https://semver.org/) versioning independent of drift releases.

## [1.0.0] — 2026-04-09

### Added

- Initial schema definition (`schema.json`) with JSON Schema 2020-12
- 12 seed patterns bootstrapped from drift ground-truth fixtures:
  - `mutant_duplicate_001` — copy-paste with variation (MDS)
  - `mutant_duplicate_002` — near-duplicate with renamed variables (MDS)
  - `mutant_duplicate_003` — exact triple duplication (MDS)
  - `explainability_deficit_001` — opaque nested branching logic (EDS)
  - `explainability_deficit_002` — deep nested loop complexity (EDS)
  - `pattern_fragmentation_001` — inconsistent error handling (PFS)
  - `pattern_fragmentation_002` — inconsistent validation strategies (PFS)
  - `guard_clause_deficit_001` — missing guard clauses (GCD)
  - `guard_clause_deficit_002` — deep nesting without guards (GCD)
  - `broad_exception_001` — bare except pattern (BEM)
  - `broad_exception_002` — mixed broad exception handling (BEM)
  - `naming_violation_001` — misleading function name (NBV)
- Schema validation script (`scripts/validate_negative_patterns.py`)
- Regression guard script (`scripts/check_negative_patterns.py`)
- CI integration in `.github/workflows/ci.yml`
- Auto-generated `METRICS.md`
