---
name: drift-signal-development-full-lifecycle
description: "End-to-end Drift workflow for adding or materially changing a signal. Use when designing a signal, implementing BaseSignal logic, adding weights, creating fixtures, updating audits, and validating precision/recall before commit. Keywords: signal development, BaseSignal, register_signal, incremental_scope, signal design, precision recall, mutation benchmark, audit_results, ADR."
argument-hint: "Describe the signal change and whether it is a new signal, a major heuristic change, or a calibration pass."
---

# Drift Signal Development Full Lifecycle Skill

Use this skill for non-trivial signal work from decision through validation.

## When To Use

- A new signal is being added
- An existing signal changes materially
- A signal heuristic is recalibrated in a way that affects trust, precision, or recall
- A signal is being prepared for scoring readiness or report-only hardening

## Core Rules

1. **Run the Drift Policy Gate first.** Signal work that fails admissibility should stop before design begins.
2. **ADR before implementation.** Non-trivial signal work needs an ADR draft before code changes.
3. **Every signal must be explicit about scope.** Declare `incremental_scope` on the class.
4. **Evidence is mandatory.** Signal logic without fixtures, targeted tests, and audit updates is incomplete.
5. **Optimize for credibility before comfort.** Precision, reproducibility, and actionability outrank convenience or breadth.

## Step 0: Run The Drift Policy Gate

Use the gate format from `.github/instructions/drift-policy.instructions.md` before doing design or implementation work.

## Step 1: Start With Decision And Design

Before coding:

- decide whether the task is a new signal, a material heuristic change, or a calibration pass
- draft or update the ADR using the `drift-adr-workflow` skill
- use `decisions/templates/signal-design-template.md` for signal-centric decisions

If a calibration materially changes signal behavior, scoring implications, or reviewer trust expectations, treat it as ADR-worthy even when it is framed as precision/recall hardening.

The design should already state:

- the problem class
- heuristic outline
- expected FP classes
- expected FN classes
- fixture plan
- validation criterion

## Step 2: Implement The Signal Class Correctly

New signal code belongs in its own file under `src/drift/signals/`. For changes to an existing signal, keep the work in that signal's existing file unless there is a separately justified design change.

Implement the class as a `BaseSignal` subclass and register it with `@register_signal`.

Be explicit about:

- `signal_type`
- `name`
- `incremental_scope`
- `uses_embeddings` when relevant

The core method is:

```python
def analyze(
    self,
    parse_results: list[ParseResult],
    file_histories: dict[str, FileHistory],
    config: DriftConfig,
) -> list[Finding]:
```

Keep the implementation deterministic, LLM-free, and fast.

## Step 3: Wire The Signal Into Configuration Safely

Add the signal weight entry in `src/drift/config.py`.

For new signals, default to conservative rollout behavior consistent with repository practice. If the signal is not yet precision-validated, keep it report-only until evidence says otherwise.

Do not treat weight promotion as automatic. That is a separate credibility decision.

## Step 4: Build The Ground-Truth Coverage Early

Use the `drift-ground-truth-fixture-development` skill to add reproducible coverage in `tests/fixtures/ground_truth.py`.

Baseline expectation for meaningful signal work:

- at least one TP fixture
- at least one TN fixture

Add boundary and confounder fixtures when the change is threshold-sensitive or meant to reduce specific false positives or false negatives.

## Step 5: Add Direct Signal Tests

Do not rely only on the shared precision/recall suite.

Add targeted regression tests under `tests/` for:

- critical heuristics
- previously observed failure modes
- crash guards
- edge cases the fixtures alone do not isolate well

If the signal change is non-trivial, make the test names and descriptions specific enough that future reviewers understand the protected behavior quickly.

## Step 6: Update Audit Artifacts

Use the `drift-risk-audit-artifact-updates` skill whenever the signal change triggers POLICY §18.

For signal work, this usually means updating:

- `audit_results/fmea_matrix.md`
- `audit_results/fault_trees.md`
- `audit_results/risk_register.md`

If the change also alters an input/output path or trust boundary, include STRIDE updates as well.

## Step 7: Run The Right Validation Stack

The minimum validation stack depends on the change, but common checks are:

```bash
pytest tests/test_benchmark_structure.py -v
pytest tests/test_precision_recall.py -v
python scripts/check_risk_audit.py --diff-base origin/main
make test-fast
```

For signal changes, also consider:

- targeted signal tests under `tests/`
- mutation benchmark reruns when the signal logic changes materially
- `drift analyze --repo . --format json --exit-zero`
- `make check` before final handoff

## Step 8: Finish The Repository-Side Obligations

Before handoff, confirm the surrounding repo obligations are covered:

- the signal has its own file under `src/drift/signals/`
- there is a config entry in `src/drift/config.py`
- tests exist for the new behavior
- audit artifacts were updated when required
- feature evidence exists if the work is a real `feat:`
- no direct DB or Git imports were added outside `ingestion/`

For real `feat:` work, feature evidence should include a versioned artifact such as `benchmark_results/vX.Y.Z_feature_evidence.json` plus the supporting tests and summary expected by the feature-evidence gate.

If the change adds a new module or user-visible feature, also check whether README or `docs/STUDY.md` updates are expected.

## Step 9: Hand Off To Commit And Push Workflow

Once design, implementation, fixtures, audits, and validation are in place, move to the repository commit workflow through `drift-commit-push`.

Do not skip directly from local signal code to push logic.

## Review Checklist

- [ ] Policy Gate passed for the signal work
- [ ] ADR exists or was updated before implementation
- [ ] The signal class uses `BaseSignal` and `@register_signal`
- [ ] `incremental_scope` is declared explicitly
- [ ] The config entry was added or updated deliberately
- [ ] TP/TN fixture coverage exists
- [ ] Direct regression tests protect the critical heuristics
- [ ] Audit artifacts were updated where POLICY §18 requires them
- [ ] Validation commands cover both structure and behavior
- [ ] Final handoff goes through the commit/push workflow rather than bypassing it

## References

- `.github/instructions/drift-policy.instructions.md`
- `.github/instructions/drift-quality-workflow.instructions.md`
- `.github/skills/drift-adr-workflow/SKILL.md`
- `.github/skills/drift-risk-audit-artifact-updates/SKILL.md`
- `.github/skills/drift-ground-truth-fixture-development/SKILL.md`
- `.github/skills/drift-commit-push/SKILL.md`
- `decisions/templates/signal-design-template.md`
- `src/drift/signals/base.py`
- `src/drift/config.py`
- `tests/fixtures/ground_truth.py`
- `tests/test_benchmark_structure.py`
- `tests/test_precision_recall.py`
- `DEVELOPER.md`
- `CONTRIBUTING.md`