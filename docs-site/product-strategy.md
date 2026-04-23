# Product Strategy

Drift is most credible when the product story stays narrower than the research surface around it.

## Product core

The product should read first as a practical tool:

- CLI for local analysis
- CI gate for gradual enforcement
- configuration for repository-specific calibration
- outputs teams can review and automate against

## Supporting layers

The surrounding material matters, but should remain clearly secondary to the product core:

- research and benchmark methodology
- product strategy and roadmap
- outreach and ecosystem positioning

## Positioning

The most defensible promise is not that drift proves architectural erosion with perfect certainty.

The defensible promise is that drift surfaces structural drift patterns that often appear in fast-moving and AI-assisted codebases, then gives teams a deterministic way to inspect and act on them.

## Adoption principle

For real teams, the sequence is:

1. fast trial
2. understandable findings
3. evidence of trustworthiness
4. gradual policy tightening

That means the repository should optimize for:

- a short path from install to first useful result
- visible explanation of what drift is and is not
- conservative rollout guidance
- benchmark transparency without making methodology the homepage

## Repository reading order

Recommended reading order for new users:

1. README
2. Quick Start
3. Team Rollout
4. Benchmarking and Trust
5. Deeper algorithm and study material

## Operational implication

When there is tension between adding more surface area and making findings more credible, credibility wins.

---

Update 2026-04-21: Hybrid-Positionierung per ADR-084 Option C freigegeben.
Nische bleibt Go-to-Market; agenten-native Evolution ist der explizite
Folge-Pfad. Siehe [`docs/PRODUCT_STRATEGY.md` Abschnitt "Evolutions-Perspektive (ADR-084 Option C)"](https://github.com/mick-gsk/drift/blob/main/docs/PRODUCT_STRATEGY.md) für Details.