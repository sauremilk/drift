# CI Architecture Checks with SARIF

Drift is designed to fit a conservative rollout path in CI: first visibility, then selective enforcement.

This page is for teams that want architectural findings in pull requests or code scanning without turning drift into a hard gate on day one.

## What drift gives you in CI

- report-only architectural findings
- JSON and SARIF output for automation
- GitHub Action support
- gradual enforcement through `fail-on`

The most useful first step is to surface findings before you start blocking builds.

## Recommended first setup

Use the GitHub Action in report-only mode:

```yaml
name: Drift

on: [push, pull_request]

jobs:
  drift:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: mick-gsk/drift@v2
        with:
          fail-on: none
          upload-sarif: "true"
```

This keeps CI useful without forcing the team to trust every signal immediately.

## When to tighten the gate

Move to `fail-on: high` only after the team has reviewed real output and understands which findings consistently lead to action.

For the full sequence, see [Team Rollout](../getting-started/team-rollout.md).

## Why SARIF matters here

SARIF makes architectural findings easier to review in normal developer workflows:

- findings can appear in GitHub code scanning
- teams can store and compare machine-readable results over time
- the same output can feed downstream tooling

## What to validate before gating

- are the top findings actionable in your repository shape
- are generated or exceptional directories excluded
- does the team agree on which classes of findings warrant intervention

## Related pages

- [Quick Start](../getting-started/quickstart.md)
- [Team Rollout](../getting-started/team-rollout.md)
- [Trust and Evidence](../trust-evidence.md)
- [Drift vs Semgrep and CodeQL](../comparisons/drift-vs-semgrep-codeql.md)
