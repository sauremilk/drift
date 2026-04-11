# Negative-Pattern Library

A versioned, labelled dataset of code patterns that [drift](https://github.com/mick-gsk/drift) identifies as architecturally problematic — with a focus on patterns commonly produced by AI-assisted development.

## Purpose

This library serves three goals:

1. **Regression guard** — CI fails if drift stops detecting a confirmed pattern
2. **Precision measurement** — each pattern is verified as a true positive, providing empirical evidence for signal quality
3. **Community contribution path** — a structured way to submit new anti-patterns without touching analyzer internals

## Structure

```
data/negative-patterns/
├── schema.json           # JSON Schema for pattern metadata
├── CHANGELOG.md          # Dataset versioning (independent of drift releases)
├── METRICS.md            # Auto-generated detection metrics
├── README.md             # This file
└── patterns/
    ├── mutant_duplicate_001/       # Multi-file pattern (directory)
    │   ├── mutant_duplicate_001.json
    │   ├── formatters.py
    │   └── money.py
    ├── explainability_deficit_001.json   # Single-file pattern
    ├── explainability_deficit_001.py
    └── ...
```

## Schema

Each pattern has a `.json` metadata file validated against [`schema.json`](schema.json).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✓ | Unique identifier, matches filename prefix |
| `signal` | string | ✓ | The drift signal this pattern targets (e.g. `mutant_duplicate`) |
| `origin` | enum | ✓ | `human`, `ai_assisted`, or `ai_generated` |
| `model_hint` | string | | Best-effort hint about which AI model produced this pattern |
| `pattern_class` | string | ✓ | Classification of the anti-pattern (e.g. `copy_paste_with_variation`) |
| `confirmed_problematic` | boolean | ✓ | Manually confirmed as genuinely problematic |
| `severity` | enum | ✓ | `low`, `medium`, or `high` |
| `description` | string | ✓ | Why this pattern is problematic (≥10 chars) |
| `tp_confirmed` | boolean | ✓ | Drift correctly detects this pattern |
| `added_by` | string | ✓ | Who added this pattern |
| `drift_version` | string | ✓ | Drift version against which this was verified |

## What is a "confirmed AI pattern"?

A pattern is considered a **confirmed AI pattern** when:

1. The code exhibits a structural anti-pattern that drift detects (`tp_confirmed: true`)
2. The pattern is typical of AI-assisted or AI-generated code (`origin: ai_assisted` or `ai_generated`)
3. A human has verified that the pattern is genuinely problematic (`confirmed_problematic: true`)

## How to read a pattern

**Single-file patterns** have two files side by side:
- `naming_violation_001.py` — the problematic code
- `naming_violation_001.json` — metadata explaining what's wrong and which signal detects it

**Multi-file patterns** use a directory:
- `mutant_duplicate_001/` — contains multiple `.py` files that together exhibit the pattern
- `mutant_duplicate_001/mutant_duplicate_001.json` — metadata

## How to add a new pattern

1. Create your `.py` file(s) under `patterns/` — minimal, self-contained, no external imports
2. Create a matching `.json` metadata file following the schema
3. Run validation locally:
   ```bash
   python scripts/validate_negative_patterns.py
   python scripts/check_negative_patterns.py
   ```
4. Verify your pattern appears in the generated `METRICS.md`
5. Open a PR — CI will validate schema conformance and detection

See [CONTRIBUTING.md](../../CONTRIBUTING.md#negative-pattern-library) for the full contribution guide.

## Versioning

This dataset follows its own [SemVer](https://semver.org/) versioning independent of drift releases. See [CHANGELOG.md](CHANGELOG.md).

- **MAJOR** — breaking schema changes
- **MINOR** — new patterns added
- **PATCH** — metadata corrections, description improvements

## Current signals covered

| Signal | Patterns | Description |
|--------|----------|-------------|
| `mutant_duplicate` | 3 | Copy-paste code with cosmetic variations |
| `explainability_deficit` | 2 | Complex logic without documentation |
| `pattern_fragmentation` | 2 | Inconsistent strategies within a module |
| `guard_clause_deficit` | 2 | Missing input validation on public functions |
| `broad_exception_monoculture` | 2 | Uniformly broad exception handling |
| `naming_contract_violation` | 1 | Function names that mislead about behavior |
