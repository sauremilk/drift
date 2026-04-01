# Negative Context

Negative context is drift's deterministic anti-pattern feed for coding agents.
It tells agents what patterns should not be reproduced when generating code.

The feature was introduced in the v1.2.x line and is emitted in both analysis
JSON output and agent task output.

## Why it exists

A finding explains what is wrong.
Negative context goes one step further for automation by providing:

- a concrete forbidden pattern
- a concrete canonical alternative
- a stable anti-pattern id for deduplication
- a machine-readable category and scope

This reduces repeated regressions where an agent fixes one issue but introduces
an already known anti-pattern elsewhere.

## Data model

`NegativeContextCategory` values:

- `security`
- `error_handling`
- `architecture`
- `testing`
- `naming`
- `complexity`
- `completeness`

`NegativeContextScope` values:

- `file`
- `module`
- `repo`

Serialized `NegativeContext` fields:

- `anti_pattern_id`
- `category`
- `source_signal`
- `severity`
- `scope`
- `description`
- `forbidden_pattern`
- `canonical_alternative`
- `affected_files`
- `confidence`
- `rationale`
- `metadata`

## Where it appears

### 1) Analysis JSON

`drift analyze --format json` may include a top-level `negative_context` array.

### 2) Agent task output

Agent task output includes `negative_context` on each task item so agents can
apply fixes while preserving known architectural and security constraints.

## Current signal coverage

As of now, generators are registered for:

- PFS
- AVS
- MDS
- EDS
- BEM
- TPD
- GCD
- NBV
- BAT
- ECM
- CCC
- COD
- CXS
- FOE
- CIR
- DCA
- MAZ
- ISD
- HSC
- DIA

## Contributor rule for new signals

When adding or promoting a signal, decide explicitly whether it should emit
negative context.

If yes, update both locations in `src/drift/negative_context.py`:

1. `_SIGNAL_CATEGORY` mapping with the correct category
2. `@_register(SignalType.XXX)` generator that emits one or more items

If no, document the reason in PR notes so the omission is intentional and
reviewable.

## Related references

- [API and Outputs](api-outputs.md)
- [Signal Reference](../algorithms/signals.md)
