# Finding Triage

The fastest way to lose trust in a structural analyzer is to treat every finding as equally important.

Use this page to triage findings by actionability, not just by count.

## Start with these questions

For each finding, ask:

1. Why does drift consider this suspicious?
2. Why is it relevant in this repository?
3. What is the smallest useful improvement?
4. Is there enough supporting evidence to act now?

## Practical prioritization order

Prioritize findings that have all four properties:

- clear architectural meaning
- multiple supporting locations
- obvious maintenance cost if ignored
- a small next step that can be executed safely

Typical examples:

- a database import in an API layer
- four variants of error handling in one module
- six near-identical helper functions that should be extracted

## How to read the output conservatively

Use the fields as practical proxies:

- severity: urgency signal
- score: strength of the specific finding
- locations: breadth of supporting evidence
- signal type: what kind of structural problem is being suggested

Until every finding carries richer metadata, treat `score + signal + locations` as your working confidence model.

## By-signal heuristics

### Pattern Fragmentation (`PFS`)

High-confidence when:

- the same concern appears in several variants inside one module
- there is an obvious dominant pattern already used elsewhere

Good next step:

- standardize on the dominant pattern and remove the exceptions

### Architecture Violations (`AVS`)

High-confidence when:

- the repository has explicit layers or boundaries
- the violating import is easy to explain in architecture terms

Good next step:

- move the dependency behind an interface or relocate code to the correct layer

### Mutant Duplicates (`MDS`)

High-confidence when:

- the duplicate logic is semantically the same and only differs in small details
- extracting shared behavior would reduce future divergence risk

Good next step:

- extract a shared helper or parameterize the repeated implementation

### Explainability Deficit (`EDS`)

High-confidence when:

- a function is complex and missing multiple explanation signals at once
- the surrounding module is already difficult to reason about

Good next step:

- add the missing explanation artifact with the best payoff first: docstring, type information, or test

### Temporal Volatility (`TVS`)

High-confidence when:

- frequent changes and many authors correlate with known instability
- the hotspot repeatedly appears in reviews or incidents

Good next step:

- clarify ownership, split the module, or narrow the responsibility surface

### System Misalignment (`SMS`)

High-confidence when:

- a module imports or uses patterns that are clearly foreign to its neighbors
- the change looks accidental rather than intentional

Good next step:

- align with the local module conventions or explicitly document the exception

## A simple triage loop

1. Review only the top handful of findings.
2. Mark each as `act now`, `watch`, or `ignore for now`.
3. Fix the smallest high-confidence issue first.
4. Tune config only after recurring evidence, not after one annoying result.

## What not to do

- do not treat the drift score as a release gate by itself
- do not chase every low-severity finding
- do not tune the analyzer before you understand your real hotspots

## Next steps

- [Team Rollout](team-rollout.md)
- [Benchmarking and Trust](../benchmarking.md)
