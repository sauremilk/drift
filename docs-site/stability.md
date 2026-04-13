# Stability and Release Status

This page explains why drift currently presents itself as Beta in package metadata while still recommending a conservative rollout posture.

The short version: the core Python path is stronger than the broadest product surface. The release label should reflect that difference without implying that every optional feature is equally mature.

## Current release posture

Drift currently publishes the PyPI classifier:

`Development Status :: 4 - Beta`

This is intentional.

It signals that the primary Python workflow is mature enough for serious adoption, while some optional surfaces still need more validation and narrower expectations.

## Stability matrix

| Area | Status | Interpretation |
|---|---|---|
| Core Python analysis | Stable | This is the primary product path. It has the strongest validation, the clearest CLI workflow, and the most credible production-adjacent use today. |
| CI and SARIF workflow | Stable | Teams can adopt drift safely in report-only mode and then tighten enforcement gradually. |
| TypeScript support | Experimental | Useful for early adoption and exploration, but not yet positioned as equally mature with Python support. |
| Embeddings-based parts | Optional / experimental | These are outside the deterministic core path and should not be treated as baseline functionality. |
| Benchmark methodology | Evolving | Public, reproducible, and good enough to support conservative claims, but still improving in replication depth, sampling, and interpretation rigor. |

## Why Beta is the honest label

Beta does not mean "everything is equally production-ready." In drift's case it means:

- the core workflow is ahead of the broadest feature envelope
- the primary Python CLI and CI path are stable enough for real use
- some optional or secondary surfaces are still experimental
- benchmark interpretation should remain conservative and signal-specific
- the project still wants teams to validate fit locally before turning drift into a hard gate

That is a credibility choice, not marketing inflation.

## What users can rely on today

Users can treat these areas as the most production-near parts of drift:

- deterministic core analysis for Python repositories
- local CLI usage
- `drift.api` stable public functions listed in `drift.api.STABLE_API`
- report-only CI rollout
- SARIF and JSON outputs for review workflows
- signal-by-signal interpretation backed by public artifacts

### `drift.api` deprecation promise

For stable symbols listed in `drift.api.STABLE_API`, drift does not remove
public functions silently in a SemVer minor release. Deprecations are first
announced with warnings plus changelog notes, and removals happen only in a
major release after at least one minor release with deprecation warning.

Users should treat these areas more cautiously:

- TypeScript support beyond early adoption scenarios
- embeddings-based or optional advanced paths
- broad benchmark conclusions applied unchanged to every repository shape

## What Beta does not mean

Beta should not be read as:

1. blanket evidence that every signal is equally mature
2. a recommendation to hard-gate every repository on day one
3. proof that benchmark conclusions transfer unchanged to every codebase shape
4. a claim that experimental surfaces should be evaluated like the core Python path

## What would justify stronger-than-Beta claims

Moving beyond the current posture should follow evidence, not tone. Stronger maturity claims become justified when the project can defend these claims simultaneously:

1. the primary Python path remains consistently reliable across more repositories and over time
2. the user-facing workflow is stable enough that rollout guidance changes little between releases
3. optional and experimental areas are clearly separated from the baseline experience
4. benchmark methodology has stronger replication and clearer confidence communication

Until then, Beta with an explicit stability matrix is the more credible posture.

## Related pages

- [Trust and Evidence](trust-evidence.md)
- [Benchmarking and Trust](benchmarking.md)
- [FAQ](faq.md)