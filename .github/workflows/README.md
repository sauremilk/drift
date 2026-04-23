# Workflows overview

This repository currently uses multiple focused workflows instead of one monolithic pipeline.
The table below documents purpose and when to look at each workflow.

| Workflow | Primary purpose | Typical trigger |
|---|---|---|
| ci.yml | Core quality gate (lint, types, tests, drift self-check) | push, pull_request |
| release.yml | Semantic release automation and PyPI publish | push to main, manual dispatch |
| release-action.yml | Keep major version tag (e.g. v2) updated after each semver release | push tag vX.Y.Z |
| docs.yml | Documentation build/deploy checks | docs-related updates |
| codeql.yml | Code scanning and security analysis | scheduled / push / pull_request |
| dependency-review.yml | Dependency risk review on PRs | pull_request |
| security-hygiene.yml | Security hygiene checks | scheduled / manual |
| validate-release.yml | Release metadata/process validation | release-related changes |
| publish.yml | Manual/auxiliary publish path | manual dispatch |
| install-smoke.yml | Package install smoke test after a PyPI release | release / manual |
| action-smoke.yml | Smoke-test action.yml via `uses: ./` — outputs, badge, fail-on wiring | action.yml changes / weekly / manual |
| package-kpis.yml | Package-level KPI generation | scheduled |
| repo-guard.yml | Repository policy/guardrail checks | push, pull_request |
| workflow-sanity.yml | Validate workflow file hygiene (tabs, merge markers, etc.) | workflow file changes |
| welcome.yml | First-time contributor greeting | issues, pull requests |
| stale.yml | Mark stale issues and pull requests | scheduled |
| labeler.yml | Auto-label pull requests | pull_request_target |
| labels-sync.yml | Sync issue/PR label definitions from config | manual / labels config changes |
| doc-consistency.yml | Check docs against DIA signal; catch stale references | push, pull_request |
| docker.yml | Build and verify the drift Docker image | manual / release tags |
| drift-baseline-persist.yml | Snapshot drift score to `drift-history` branch after each merge | push to main |
| drift-brief-on-issue.yml | Post `drift brief` as a comment when an issue is assigned | issue assigned |
| drift-label-feedback.yml | Translate PR labels into drift feedback verdicts; trigger calibration | pull_request label events |
| fp-oracle-audit.yml | False-positive oracle audit against ground-truth fixtures | scheduled / manual |
| mutation-testing.yml | Mutation benchmark for signal recall | scheduled / manual |
| perf-regression-loop.yml | Performance regression checks on critical paths | scheduled / manual |
| proactive-qa.yml | Proactive QA checks triggered on code changes | push, pull_request |
| issue-claim.yml | Reserve an issue for a contributor | issue comment |
| issue-claim-timeout.yml | Release unclaimed issues after timeout | scheduled |

## Why not collapse immediately?

Several workflows have different permissions, schedules, and trust boundaries.
A direct merge into 3-5 files can accidentally weaken security boundaries or break release reliability.

## Consolidation path

If consolidation is desired, do it in phases:
1. Merge low-risk maintenance workflows first (for example repo-guard + workflow-sanity).
2. Keep release/publish and security workflows isolated.
3. Re-measure runtime and failure modes before further merges.

## Action vs CLI — which is tested where?

| What is tested | Where |
|---|---|
| `drift` CLI (dev version from workspace) | ci.yml, doc-consistency.yml |
| `drift` CLI (PyPI release) | install-smoke.yml |
| `action.yml` composite action via `uses: ./` | **action-smoke.yml** |
| `action.yml` major-version tag management | release-action.yml |
