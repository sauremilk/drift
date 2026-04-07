---
name: drift-ground-truth-fixture-development
description: "Drift-specific workflow for creating, extending, and validating ground-truth fixtures for signal precision and recall. Use when adding TP/TN fixtures, confounders, boundary cases, or file_history_overrides in tests/fixtures/ground_truth.py. Keywords: ground truth, fixture, precision recall, TP, TN, confounder, boundary, file_history_overrides, ALL_FIXTURES."
argument-hint: "Describe the signal and whether you need a TP fixture, TN fixture, boundary case, confounder, or history-aware fixture."
---

# Drift Ground-Truth Fixture Development Skill

Use this skill when Drift needs reproducible fixture coverage for signal behavior.

## When To Use

- A new signal needs baseline TP and TN coverage
- A false positive or false negative needs to become a regression fixture
- A threshold or calibration change needs boundary coverage
- A benign lookalike case needs a confounder fixture
- A signal depends on history-like data and needs `file_history_overrides`

## Core Rules

1. **Run the Drift Policy Gate first.** Fixtures should validate admissible work, not justify inadmissible work.
2. **Keep fixtures minimal and deterministic.** No external dependencies, no hidden runtime assumptions.
3. **Every fixture needs explicit expectations.** Empty fixtures are invalid.
4. **Prefer source-like realism over size.** Small but representative beats large and noisy.
5. **Use fixture kinds intentionally.** TP/TN are the baseline; boundary and confounder cases are for calibration and trust hardening.

## Step 0: Run The Drift Policy Gate

Before adding or changing fixtures, use the gate format from `.github/instructions/drift-policy.instructions.md`.

## Step 1: Choose The Right Fixture Type

Use these types deliberately:

- **positive**
  the signal must fire
- **negative**
  the signal must not fire
- **boundary**
  the case sits near a threshold or decision edge
- **confounder**
  the case looks like a real finding but is intentionally benign

For new signal logic, start with at least one TP and one TN fixture. Add boundary or confounder fixtures when the change is calibration-sensitive or specifically aims to reduce false positives or false negatives.

## Step 2: Model The Fixture With The Existing Dataclasses

Fixtures live in `tests/fixtures/ground_truth.py` and are built from these pieces:

- `GroundTruthFixture`
- `ExpectedFinding`
- `FixtureKind`
- `FileHistoryOverride`

The essential fields are:

- `name`
- `description`
- `files`
- `expected`

Use `kind=` explicitly for boundary and confounder fixtures.

## Step 3: Keep File Layout And Expectations Concrete

Write the smallest file tree that expresses the behavior under test.

Good fixture design means:

- file paths match what the signal actually reasons about
- content is easy to inspect
- the expected file path points to the real detection target
- each `ExpectedFinding` says whether detection should happen

Avoid giant fixtures that mix multiple concerns unless the signal truly depends on that interaction.

## Step 4: Use History Overrides Only When The Signal Needs Them

`file_history_overrides` exists for signals that depend on churn or recency semantics.

Use it when a signal needs non-default history behavior, for example:

- churn-sensitive signals such as temporal volatility
- system misalignment cases using recency
- any test that needs controlled commit-count or frequency assumptions

When using overrides:

- match the override key to a real file in `files`
- override only the fields you need
- keep the values interpretable by a reviewer

## Step 5: Register The Fixture Correctly

Add the fixture to `ALL_FIXTURES` in `tests/fixtures/ground_truth.py`.

Use a short, unique, signal-oriented fixture name consistent with existing repository practice, for example `pfs_tp`, `avs_tn`, or `dia_boundary_tp`.

Do not forget that the derived indexes are built from `ALL_FIXTURES`:

- `FIXTURES_BY_SIGNAL`
- `FIXTURES_BY_KIND`

The signal and kind indexes are populated from fixture expectations and inferred kinds, so fixture naming and explicit `kind=` values matter.

## Step 6: Validate Structure Before Semantics

The structural benchmark tests catch common fixture mistakes:

```bash
pytest tests/test_benchmark_structure.py -v
```

This protects against problems like:

- duplicate fixture names
- empty expectation lists
- missing TP coverage
- missing TN coverage
- missing boundary or confounder coverage in the overall suite

## Step 7: Validate Behavior With Precision/Recall Tests

Run the relevant evaluation path after structural validation:

```bash
pytest tests/test_precision_recall.py -v
```

For a narrower loop, run only the affected fixture or signal-focused subset when available, then rerun the broader precision/recall suite before concluding the work is stable.

## Step 8: Capture Common Failure Modes Early

Watch specifically for these mistakes:

- fixture name collisions
- expectations targeting the wrong path
- forgetting to add the fixture to `ALL_FIXTURES`
- mismatch between `kind` and expectations
- `file_history_overrides` keys that do not match real files
- confounders that are actually true positives or negatives in disguise

If the fixture exists to lock a false-positive or false-negative regression, say that explicitly in the description.

## Review Checklist

- [ ] Policy Gate passed for the underlying task
- [ ] The chosen fixture type matches the test intent
- [ ] The fixture is minimal, deterministic, and readable
- [ ] Every fixture has explicit expectations
- [ ] TP/TN coverage exists where required
- [ ] Boundary/confounder cases are used intentionally, not decoratively
- [ ] Any `file_history_overrides` keys match real files in the fixture
- [ ] The fixture was added to `ALL_FIXTURES`
- [ ] Structural tests and precision/recall checks are named explicitly

## References

- `.github/instructions/drift-policy.instructions.md`
- `.github/instructions/drift-quality-workflow.instructions.md`
- `tests/fixtures/ground_truth.py`
- `tests/test_benchmark_structure.py`
- `tests/test_precision_recall.py`
- `DEVELOPER.md`
- `CONTRIBUTING.md`