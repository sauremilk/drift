# Team Rollout

This guide is optimized for small teams first.

The goal is not to turn drift into a hard gate on day one. The goal is to build trust, identify high-value findings, and only then tighten enforcement.

## Recommended rollout path

### Phase 1: Local exploration

Start locally and inspect the top findings before any CI policy change.

```bash
drift analyze --repo .
```

What to look for:

- repeated patterns inside one module
- findings that clearly point to architectural boundaries
- clusters with multiple supporting locations

Avoid tuning configuration before you have seen a few real results.

### Phase 2: CI visibility without blocking

Add drift to CI, but use it as a reporting signal first.

**Week 1 — report-only GitHub Action:**

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
          fail-on: none           # report-only, no build failures
          upload-sarif: "true"    # findings appear as PR annotations
```

This gives the team visibility into architectural patterns without blocking any PR.

Recommended posture:

- review findings in pull requests and weekly maintenance windows
- record which signals feel high-trust and which need tuning
- discuss top findings in team syncs before enforcing anything

### Phase 3: Block only high-confidence problems

Once the team understands the output, begin with a narrow gate:

**Week 3+ — gate on high-severity only:**

```yaml
      - uses: mick-gsk/drift@v2
        with:
          fail-on: high           # block only high-severity findings
          upload-sarif: "true"
```

Or from the CLI:

```bash
drift check --fail-on high
```

Why `high` first:

- it minimizes team frustration
- it forces attention on the most structural issues
- it gives space to calibrate lower-severity findings later

!!! note "Severity vs. finding score"
    `--fail-on high` filters by **severity level** (critical / high / medium / low), not by the numeric finding score. Severity is derived from the finding score and signal type but represents a coarser classification. The numeric score is useful for manual triage; the severity level is what CI gates operate on.

### Phase 4: Tune by repo shape

Only after reviewing real findings should you adjust policies or weights.

Typical tuning decisions:

- reduce weight on a noisy signal for your repository shape
- add architecture boundary rules where layers are explicit
- exclude generated or vendor-like code that distorts the signal

## Safe default policy

For many teams, this is the least risky adoption path:

1. Run `drift analyze` locally.
2. Add CI reporting.
3. Gate on `high` only.
4. Review noise after two or three real pull requests.
5. Tighten config only where evidence justifies it.

## How to avoid false-positive fatigue

- do not start with `medium` or `low` gates
- treat the first scans as calibration, not judgment
- prefer patterns with multiple corroborating locations over isolated weak signals
- document team-specific exclusions instead of arguing with every individual finding

## Suggested team policy

Use drift when:

- reviewing fast-moving modules
- integrating AI-assisted coding into an existing architecture
- checking whether new code matches established patterns

Do not rely on drift alone when:

- validating correctness
- enforcing security requirements
- replacing architectural review on critical changes

## Next steps

- [Finding Triage](finding-triage.md)
- [Configuration](configuration.md)
- [Benchmarking and Trust](../benchmarking.md)

## Measuring rollout success

Without a feedback loop, you can't tell whether drift is adding value. Here are practical, privacy-preserving ways to measure adoption:

**CI-level signals (no telemetry required):**

- track how many repositories have the drift GitHub Action enabled
- monitor how often `drift check` runs succeed vs. fail in CI logs
- compare the number of high-severity findings per sprint over time

**Team-level signals:**

- count how many drift findings led to a code change (triage → action rate)
- track whether high-churn modules identified by drift stabilize over sprints
- ask in retros: "Did drift surface something we would have missed?"

**Artifact-based tracking:**

- save `drift analyze --format json` output as a CI artifact each week
- compare drift scores across sprints to measure trend direction
- use `drift trend --last 90` locally to visualize score trajectory

The goal is not to maximize coverage, but to know whether findings translate into architectural decisions.