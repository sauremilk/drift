## Summary

<!-- What changed and why? -->

## Related issue

<!-- Use: Closes #123 / Fixes #123 / Related #123 -->

## Policy criterion served

<!-- Which quality goal does this PR advance? Check at least one. -->

- [ ] Credibility (reproducibility, determinism)
- [ ] Signal precision (fewer false positives/negatives)
- [ ] Finding clarity (better explanations, actionable next steps)
- [ ] Adoptability (easier setup, onboarding, docs)
- [ ] Trend capability (temporal analysis, delta tracking)
- [ ] None of the above — explain why this is still valuable:

## First contribution?

- [ ] This is my first contribution to drift

<!-- First-time contributors: don't worry about getting everything perfect.
     Maintainers will guide you through the review process. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor
- [ ] Documentation
- [ ] Test-only change
- [ ] CI/Build change

## Validation

- [ ] `pytest` passes locally
- [ ] `ruff check src/ tests/` passes locally
- [ ] `mypy src/drift` passes locally
- [ ] `drift self` delta checked (target: <= +0.010)
- [ ] Added/updated tests for behavioral changes

## Empirical evidence (required for new features)

- [ ] This PR introduces no new feature (skip section)
- [ ] OR: empirical artifact added/updated in `benchmark_results/` or `audit_results/`
- [ ] OR: feature has benchmark/validation output attached in PR description

Evidence summary (required when feature is introduced):

- Scope / dataset:
- Baseline result:
- New result:
- Reproduction command:
- Interpretation (precision/noise/runtime impact):

## Checklist

- [ ] PR is focused on one concern
- [ ] Public docs updated (README/docs-site) if needed
- [ ] Changelog entry added if user-visible
- [ ] If version/changelog changed: top release entry still fits one short summary plus at most 5 curated bullets
- [ ] No unrelated files included

## Risk Audit (POLICY §18 — required for signal/architecture changes)

- [ ] This PR does **not** touch `src/drift/signals/`, `src/drift/ingestion/`, or `src/drift/output/` (skip section)
- [ ] OR: `audit_results/fmea_matrix.md` updated (FP + FN entry for affected signal)
- [ ] OR: `audit_results/stride_threat_model.md` updated (new/changed trust boundary)
- [ ] OR: `audit_results/fault_trees.md` reviewed (FT-1/FT-2/FT-3 paths checked)
- [ ] OR: `audit_results/risk_register.md` updated (new risk entry or metric update)
- [ ] All four audit artifacts still exist and are not deleted

## Notes for reviewers

<!-- Anything that needs special attention during review -->
