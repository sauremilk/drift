---
name: drift-adr-workflow
description: "Drift-specific ADR workflow for signal, scoring, output, and architecture decisions. Use when creating, updating, or validating ADRs before implementation. Keywords: ADR, decision record, proposed, signal design, scoring change, architecture boundary, output format, Decision trailer."
argument-hint: "Describe the planned change and whether you need a new ADR, an ADR update, or validation of an existing draft."
---

# Drift ADR Workflow Skill

Use this skill when a Drift change needs a documented architectural or product decision before implementation.

## When To Use

- A signal is added or materially changed
- Scoring logic or weights are changed
- Output formats or output contracts are changed
- An architecture boundary, trust boundary, input path, or output path changes
- An existing ADR draft must be completed or validated

## Core Rules

1. **Run the Drift Policy Gate first.** If the task is not admissible, stop.
2. **ADR first, implementation second.** For signal, scoring, output-format, or architecture-boundary changes, prepare the ADR before coding.
3. **Agents may draft, not accept.** Agents may create or update ADRs with status `proposed`; only the maintainer changes status to `accepted` or `rejected`.
4. **Validation must be testable.** Every ADR needs a concrete validation section with measurable checks or outcomes.
5. **Do not blur bugfixes and architectural decisions.** Pure bugfixes and pure refactorings do not automatically require a new ADR.

## Step 0: Run The Drift Policy Gate

Before drafting an ADR, use the mandatory gate format from `.github/instructions/drift-policy.instructions.md`.

If the task fails the gate, do not create an ADR to legitimize inadmissible work.

## Step 1: Decide Whether An ADR Is Required

Create or update an ADR when the change affects one of these categories:

- signal design or signal behavior
- scoring or prioritization logic
- output schema or result format
- architecture or trust boundaries

Do not force a new ADR for:

- typo fixes
- isolated test-only work
- pure refactors without behavior change
- contained bugfixes that preserve the existing design decision without materially changing signal behavior, scoring logic, output contracts, or trust assumptions

If unsure, prefer a draft ADR that states the uncertainty explicitly.

## Step 2: Choose The Right Template

Use the general template in `docs/decisions/templates/adr-template.md` for broad architecture or workflow decisions.

When the decision is primarily about a signal, you must use `docs/decisions/templates/signal-design-template.md` and complete its signal-specific fields. That template already forces the critical fields:

- problem class
- heuristic
- scope
- expected FP classes
- expected FN classes
- fixture plan
- FMEA pre-entry
- validation criterion

## Step 3: Create Or Update The ADR File

Create the next ADR under `docs/decisions/` using the repository numbering sequence:

```text
docs/decisions/ADR-NNN-short-slug.md
```

Required YAML frontmatter fields at the top of the file:

- `id`
- `status: proposed`
- `date`
- `supersedes`

Signal-design ADRs must also carry:

- `type: signal-design`
- `signal_id`

Do not invent custom status values.

## Step 4: Write The Decision Clearly

The ADR body must answer all of these questions:

- What problem or uncertainty is being addressed?
- What is being done?
- What is explicitly not being done?
- Why was this option chosen over alternatives?
- What trade-offs or consequences are accepted?
- How will the decision be validated?

For signal-related ADRs, be explicit about:

- why the problem maps to Drift's product purpose
- whether the signal is `file_local`, `cross_file`, or `git_dependent`
- expected false-positive and false-negative classes
- what minimal fixtures must exist before implementation is considered credible

## Step 5: Connect The ADR To Evidence

An ADR is not complete if it floats without validation hooks.

Reference the concrete artifacts the later implementation must touch, for example:

- tests under `tests/`
- fixture definitions under `tests/fixtures/ground_truth.py`
- audit artifacts under `audit_results/`
- evidence artifacts under `benchmark_results/`

If the decision changes a signal or architecture boundary, state which audit artifacts must be updated alongside the implementation.

## Step 6: Define Validation And Outcome Semantics

The `Validation` section must contain concrete checks, for example:

```bash
pytest tests/test_precision_recall.py -v
python scripts/check_risk_audit.py --diff-base origin/main
drift analyze --repo . --format json --exit-zero
```

Also state the expected learning-cycle result using the policy vocabulary used in Drift decision review:

- `bestaetigt`
- `widerlegt`
- `unklar`
- `zurueckgestellt`

## Step 7: Prepare Commit Linkage

When implementation follows the ADR, the commit body should carry the decision trailer:

```text
Decision: ADR-NNN
```

Do not change ADR status to `accepted` as part of the agent workflow.

## Review Checklist

- [ ] Policy Gate passed for the underlying task
- [ ] ADR requirement was correctly identified
- [ ] The right template was used
- [ ] Status is `proposed`
- [ ] Decision and non-goals are explicit
- [ ] Validation is concrete and testable
- [ ] Signal-related ADRs name FP/FN classes, scope, and fixture plan
- [ ] References to tests, audit artifacts, or evidence files are concrete
- [ ] Maintainer-only status boundaries are respected

## References

- `.github/instructions/drift-policy.instructions.md`
- `.github/instructions/drift-quality-workflow.instructions.md`
- `.github/skills/drift-commit-push/SKILL.md`
- `docs/decisions/templates/adr-template.md`
- `docs/decisions/templates/signal-design-template.md`
- `DEVELOPER.md`
- `CONTRIBUTING.md`