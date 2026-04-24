---
name: drift-risk-audit-artifact-updates
description: "Drift-specific workflow for updating required audit artifacts after signal, ingestion, output, or architecture changes. Use when FMEA, fault trees, STRIDE, or the risk register must be updated to satisfy POLICY §18 and pre-push gates. Keywords: risk audit, FMEA, STRIDE, fault tree, risk register, Policy 18, audit_results, signal change, trust boundary, precision recall."
argument-hint: "Describe the code change and whether it affects a signal, an input/output path, or measurable precision/recall."
---

# Drift Risk Audit Artifact Updates Skill

Use this skill when a Drift change requires explicit updates to the audit stack under `audit_results/`.

## When To Use

- A file under `src/drift/signals/` changes materially
- A file under `src/drift/ingestion/` changes materially
- A file under `src/drift/output/` changes materially
- An input path, output path, or trust boundary changes
- Precision or recall changes by more than 5 percentage points
- A push would otherwise fail the risk-audit gate

## Core Rules

1. **Run the Drift Policy Gate first.** Audit updates do not rescue inadmissible work.
2. **Treat audit artifacts as contracts, not optional docs.** POLICY §18 makes them mandatory.
3. **Update the right artifact for the change type.** Any audit file is not enough.
4. **Never delete the four protected audit artifacts.** The gate checks existence.
5. **Use bypasses only with explicit maintainer approval and a documented emergency reason.**

## Step 0: Run The Drift Policy Gate

Before touching the audit stack, use the gate format from `.github/instructions/drift-policy.instructions.md`.

## Step 1: Classify The Change

Sort the implementation into one of these categories:

### A. Signal changed

Examples:

- new signal
- materially changed heuristic
- changed finding criteria
- changed scoring-readiness behavior

Treat a change as material when it changes detection scope, improves or worsens precision/recall in a meaningful way, alters actionable output, or changes what reviewers must trust about the signal.

### B. Input/output or trust boundary changed

Examples:

- new ingestion path
- new output channel
- changed output contract or trust boundary

### C. Precision/recall shifted by more than 5 percentage points

Examples:

- threshold tuning
- strong FP reduction
- recall hardening with measurable delta

If more than one category applies, update the union of required artifacts.

## Step 2: Map The Change To Required Artifacts

Use this mapping exactly:

- **Signal changed**
  update `audit_results/fmea_matrix.md`, `audit_results/fault_trees.md`, and `audit_results/risk_register.md`
- **Input/output or trust boundary changed**
  update `audit_results/stride_threat_model.md` and `audit_results/risk_register.md`
- **Precision/recall delta > 5%**
  update `audit_results/fmea_matrix.md` and `audit_results/risk_register.md`

The machine gate in `scripts/check_risk_audit.py` checks for the presence of audit updates. POLICY §18 still requires the correct artifact combination for the specific change type, so update the full required set for your case.

## Step 3: Update The FMEA Matrix Correctly

Use `audit_results/fmea_matrix.md` for failure-mode thinking.

At minimum, capture:

- signal
- failure mode
- cause
- effect
- detection
- mitigation
- `S`, `O`, `D`, and `RPN`

Use the same scale and table style already present in `audit_results/fmea_matrix.md`. `RPN` must be calculated as `S x O x D`.

For signal changes, add at least one expected false-positive mode and one expected false-negative mode.

Keep the mitigation specific enough that a reviewer can connect it to tests, heuristics, or evidence.

## Step 4: Update Fault Trees Or STRIDE As Needed

Use `audit_results/fault_trees.md` when the change affects causal failure paths for signal quality.

Use `audit_results/stride_threat_model.md` when the change introduces or alters an input path, output path, or trust boundary.

Do not write generic text. The artifact should name the concrete path, component, or causal chain that changed.

## Step 5: Update The Risk Register

Every relevant audit update should leave an operational trace in `audit_results/risk_register.md`.

Capture:

- risk ID
- affected component
- type of risk
- description
- trigger examples
- impact
- mitigation
- verification
- residual risk

Trigger examples should be concrete enough to recognize the failure mode again.

## Step 6: Tie Audit Updates To Evidence

Audit text without verification is weak. Reference the concrete checks that support the update, for example:

```bash
pytest tests/test_precision_recall.py -v
pytest tests/test_mutant_duplicates_edge_cases.py -q --maxfail=1
python scripts/check_risk_audit.py --diff-base origin/main
```

If the change claims a precision or recall shift, the audit entry should say how that delta was observed.

## Step 7: Validate Before Push

Use the local checker to confirm the push is not blocked:

```bash
python scripts/check_risk_audit.py --diff-base origin/main
```

Also ensure the four protected files still exist:

- `audit_results/fmea_matrix.md`
- `audit_results/stride_threat_model.md`
- `audit_results/fault_trees.md`
- `audit_results/risk_register.md`

## Step 8: Handle Exceptions Conservatively

If an emergency bypass is considered, prefer the narrowest gate bypass and document the reason. For this gate, that usually means `DRIFT_SKIP_RISK_AUDIT=1` rather than `DRIFT_SKIP_HOOKS=1`.

## Review Checklist

- [ ] Policy Gate passed for the underlying change
- [ ] The change type was classified correctly
- [ ] The correct audit artifact set was updated
- [ ] FMEA entries include FP/FN thinking where required
- [ ] Fault-tree or STRIDE updates are concrete rather than generic
- [ ] Risk Register entry includes trigger examples and verification
- [ ] Verification commands are named explicitly
- [ ] The local risk-audit checker is expected to pass
- [ ] No protected audit artifact was removed

## References

- `.github/instructions/drift-policy.instructions.md`
- `.github/instructions/drift-push-gates.instructions.md`
- `.github/instructions/drift-quality-workflow.instructions.md`
- `.github/skills/drift-commit-push/SKILL.md`
- `scripts/check_risk_audit.py`
- `audit_results/fmea_matrix.md`
- `audit_results/fault_trees.md`
- `audit_results/stride_threat_model.md`
- `audit_results/risk_register.md`
- `CONTRIBUTING.md`
