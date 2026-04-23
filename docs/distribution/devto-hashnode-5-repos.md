# Draft: I Ran Drift on 5 Real Repos. Here Is What I Found.

Use this as the base article for dev.to and Hashnode.

## Working Title

I Ran Drift on 5 Real Repos. Here Is What I Found.

## Subtitle

Deterministic architecture erosion signals in production Python codebases, and what teams can fix first.

## Draft

If you use AI coding assistants every day, your code often stays locally correct while global structure slowly drifts.

Tests still pass. Linters still pass. But architecture coherence starts to erode: the same concern gets implemented in multiple styles, boundaries blur, and near-duplicates spread.

I built drift to measure this deterministically in Python repositories, without an LLM in the analysis pipeline. Then I ran it on five real-world projects.

### Method in one minute

- Tool: `drift-analyzer`
- Mode: static analysis with deterministic signals
- Output: findings plus a composite drift score
- Purpose: identify architectural erosion early enough to be fixable

This is not a bug scanner. It is a coherence scanner.

### Repo 1: fastapi/fastapi

- Finding highlight: [499 near-duplicate test functions](https://mick-gsk.github.io/drift/case-studies/fastapi/) (MDS signal, confidence 0.85)
- Interpretation: duplication drift at scale, likely copy-modify patterns
- Actionable next step: consolidate with parameterized fixtures and shared test helpers

### Repo 2: django/django

- Finding highlight: score remained stable across many releases, then dropped after deprecation cleanup
- Interpretation: score tracks structural coherence over time, not just size
- Actionable next step: monitor trend deltas per release, not only absolute score

### Repo 3: pydantic/pydantic

- Finding highlight: [117 underdocumented high-complexity internal functions](https://mick-gsk.github.io/drift/case-studies/pydantic/) (EDS signal)
- Interpretation: maintainability risk concentrates in internal complexity hot spots
- Actionable next step: document top complexity functions first for highest leverage

### Repo 4: paramiko/paramiko

- Finding highlight: [5 god-module candidates and 18 circular import chains](https://mick-gsk.github.io/drift/case-studies/paramiko/) (AVS + CIR signals)
- Interpretation: long-lived protocol libraries accumulate architecture stress in stable core files — `transport.py` alone has 38 coupling connections
- Actionable next step: extract protocol state management from `transport.py` and break the longest import cycles with a shared types module

### Disclosure: drift self-analysis

As a transparency note — I also run drift on its own codebase:

- Finding highlight: score of 0.514 (MEDIUM), 80 findings, stable short-term trend with visible sensitivity to focused refactors
- Interpretation: deterministic signals are usable in day-to-day CI if tuned to report-only first
- This is dogfooding, not external proof. The four repos above are the independent evidence.

## What surprised me most

1. The highest-value findings were not stylistic. They were structural and repeatedly actionable.
2. Trend stability mattered more than one-off snapshots.
3. Teams get better results when they treat findings as architecture work items, not lint noise.

## Practical rollout that worked

Start with a non-blocking phase:

```yaml
- uses: mick-gsk/drift@v2
  with:
    fail-on: none
    upload-sarif: "true"
```

Then tighten only after calibration:

```yaml
- uses: mick-gsk/drift@v2
  with:
    fail-on: high
    upload-sarif: "true"
```

For pre-commit style checks, you can also use `drift diff --staged-only`.

## Try it yourself

```bash
pip install drift-analyzer
drift analyze --repo .
```

Want to evaluate the evidence first? [Start here](https://mick-gsk.github.io/drift/start-here/) — three paths depending on whether you want to try it, check the evidence, or plan a team rollout.

## Closing

AI-assisted velocity is real. Architectural drift is also real.

The teams that benefit most are not the ones with perfect code. They are the ones that detect coherence erosion early and fix it while changes are still small.

## Channel Adaption Notes

- dev.to: keep the narrative personal, include short code blocks, add 3 tags: python, architecture, ai.
- Hashnode: keep stronger technical framing, include one figure or table from case-study evidence.
- Keep title identical for attribution continuity.
