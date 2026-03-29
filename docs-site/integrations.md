# Integrations

Drift is easiest to adopt when teams do not have to invent a workflow around it.

This page collects the current integration surfaces that make drift useful in local checks, CI, code scanning, and machine-readable review flows.

## GitHub Action

Drift ships a GitHub Action that supports report-only rollout, configurable severity gating, and SARIF upload for code scanning.

Use this when you want findings in pull requests before you enforce anything.

Key inputs:

- `fail-on`
- `since`
- `format`
- `config`
- `upload-sarif`

See [CI Architecture Checks with SARIF](use-cases/ci-architecture-checks-sarif.md) for rollout posture.

## CLI

The CLI is the fastest integration path for local analysis and simple automation.

Common entry points:

- `drift analyze --repo .`
- `drift check --fail-on none`
- `drift check --fail-on high`
- `drift analyze --format json`
- `drift analyze --format sarif`
- `drift trend --last 90`

See [Quick Start](getting-started/quickstart.md) for first-run guidance.

## pre-commit

Drift provides two pre-commit hooks so you can add architectural checks to any repository without installing drift globally.

### Recommended: remote hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/sauremilk/drift
    rev: v0.9.0
    hooks:
      - id: drift-check          # blocks on high-severity findings
      # - id: drift-report        # report-only (start here, then switch)
```

**`drift-check`** runs `drift check --fail-on high` and blocks the commit if any high-severity finding is detected.

**`drift-report`** runs `drift check --fail-on none` and prints findings without blocking. Use this during the first week, then switch to `drift-check` once the team is comfortable with the signal quality.

### Alternative: local hook

Use this if drift is already installed in your environment:

```yaml
repos:
  - repo: local
    hooks:
      - id: drift
        name: drift
        entry: drift check --fail-on high
        language: system
        pass_filenames: false
        always_run: true
```

### Progressive rollout

1. Start with `drift-report` (report-only) to see findings without disruption
2. Review findings for 1–2 weeks alongside normal code review
3. Switch to `drift-check` (`--fail-on high`) once the team trusts the signal
4. Optionally tighten to `--fail-on medium` for stricter gating

## SARIF and JSON outputs

Drift supports machine-readable outputs for review and automation:

- SARIF for GitHub code scanning and related workflows
- JSON for CI artifacts, downstream scripts, and historical comparison

See [API and Outputs](reference/api-outputs.md) for the documented surfaces.

## Python API

Teams that want to integrate drift programmatically can use the Python entry points already exposed by the project.

Current documented public analysis entry points include:

- `analyze_repo(...)`
- `analyze_diff(...)`

These are most useful when you want a custom orchestration layer without wrapping shell commands.

## Example workflow assets in the repository

- `action.yml` for the GitHub Action implementation
- `examples/drift-check.yml` for a ready-to-copy workflow
- `examples/demo-project/` for an intentionally drifted demo repository

## Recommended adoption order

1. CLI locally
2. report-only CI
3. SARIF visibility in pull requests
4. selective gating on `high`
5. deeper automation with JSON or Python API only where justified

## Related pages

- [Quick Start](getting-started/quickstart.md)
- [Team Rollout](getting-started/team-rollout.md)
- [CI Architecture Checks with SARIF](use-cases/ci-architecture-checks-sarif.md)
- [Trust and Evidence](trust-evidence.md)

## GitLab CI

Drift works in any CI environment that supports Python. Here is a minimal GitLab CI template:

```yaml
drift-check:
  image: python:3.12-slim
  stage: test
  script:
    - pip install -q drift-analyzer
    - drift check --fail-on none --format json > drift-report.json
    - drift check --fail-on high
  artifacts:
    paths:
      - drift-report.json
    when: always
    expire_in: 30 days
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### Progressive rollout in GitLab

1. **Report-only** (first week): `--fail-on none` — collect artifacts, no pipeline failures
2. **Gate on critical**: change to `--fail-on critical` after reviewing initial findings
3. **Gate on high**: tighten to `--fail-on high` when the team is confident in signal quality

### SARIF output for GitLab

GitLab does not natively consume SARIF, but you can archive it as an artifact or convert it using third-party tools:

```yaml
drift-sarif:
  image: python:3.12-slim
  stage: test
  script:
    - pip install -q drift-analyzer
    - drift analyze --format sarif > gl-code-quality-report.sarif
  artifacts:
    paths:
      - gl-code-quality-report.sarif
    when: always
```

### Diff-only analysis

For merge request pipelines, use diff mode for fast incremental checks:

```yaml
drift-check:
  image: python:3.12-slim
  stage: test
  script:
    - pip install -q drift-analyzer
    - git fetch origin $CI_MERGE_REQUEST_TARGET_BRANCH_NAME
    - drift check --diff origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME --fail-on high
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```