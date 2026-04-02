# Contributing

See [CONTRIBUTING.md](https://github.com/sauremilk/drift/blob/main/CONTRIBUTING.md) for the full contributing guide
and [ROADMAP.md](https://github.com/sauremilk/drift/blob/main/ROADMAP.md) for current priorities.

## Who this page is for

This page is for contributors and maintainers rather than first-time evaluators.

- If you want to try drift quickly, start with [Quick Start](getting-started/quickstart.md).
- If you are assessing whether drift is credible for your team, read [Example Findings](product/example-findings.md), [Trust and Evidence](trust-evidence.md), and [Stability and Release Status](stability.md) first.
- If you are ready to contribute code or docs, continue into the contributing guide.

The project keeps strict contribution standards because they protect reproducibility, signal quality, and trust in findings.

Maintainers and repeat reviewers can use the repository operations docs on GitHub:
[Maintainer Runbook](https://github.com/sauremilk/drift/blob/main/docs/MAINTAINER_RUNBOOK.md) and
[Repository Governance](https://github.com/sauremilk/drift/blob/main/docs/REPOSITORY_GOVERNANCE.md).

## Quick Start

```bash
git clone https://github.com/sauremilk/drift.git
cd drift
make install          # pip install -e ".[dev]" + git hooks
make test-fast        # confirm everything passes
```

## Good First Issues

Look for issues labelled [`good first issue`](https://github.com/sauremilk/drift/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) — these are scoped to be completable in a few hours.

## How we evaluate contributions

Contributions are evaluated in this order of importance:

1. **Credibility** — does it make findings more trustworthy and reproducible?
2. **Signal precision** — does it reduce false positives or false negatives?
3. **Clarity** — does it make findings easier to understand and act on?
4. **Adoptability** — does it make drift easier to set up or integrate?

**What we prefer:** reproducible fixtures, improved finding explanations, FP/FN reductions, per-signal documentation with code examples.\
**What we don't accept:** more output without insight, more complexity without benefit, features whose contribution to quality cannot be named.

## Typical first contributions

| Contribution | Difficulty | Example |
|---|---|---|
| Ground-truth fixture | Easy | Add a minimal code sample that should (or should not) trigger PFS |
| FP/FN report | Easy | Document a case where drift gives the wrong result |
| Finding explanation | Easy | Improve a vague `reason` string to name the specific problem |
| Edge-case test | Easy | Test that `drift analyze` handles an empty repo without crashing |
| Signal documentation | Easy–Medium | Write a docs page for TVS or SMS with concrete code |

Contributions that are **not code** are equally valuable: well-documented false positives, minimal reproduction repos, and signal documentation.

## Adding a New Signal

1. Create `src/drift/signals/your_signal.py` implementing `BaseSignal`
2. Decorate the class with `@register_signal` — auto-discovery handles the rest
3. Add a weight entry in `src/drift/config.py` (default `0.0` until stable)
4. Write tests in `tests/test_your_signal.py` (TP + TN fixtures required)

Signals must be deterministic, LLM-free, and fast (< 500ms per 1,000 functions).

## Maintainer feedback commitment

- First response within 72 hours on issues and PRs.
- Rejections include a reason referencing a specific quality criterion.
- First-time contributors get guidance, not just pass/fail.
