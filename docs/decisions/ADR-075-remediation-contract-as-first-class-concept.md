# ADR-075: Remediation Contract as First-Class Concept — root_cause Field on Finding

**Status:** proposed
**Date:** 2026-04-18
**Decision:** Add a `root_cause` field to `Finding` and a `_root_cause_for()` enrichment function in agent_tasks.py

## Context

Drift findings currently carry:
- `description` — what was detected (symptom)
- `fix` — what the agent should do (prescription)
- `success_criteria` / `verify_plan` — how to confirm the fix worked (verification)

What is missing is **why the problem arose** — the proximate cause that led to the symptom.
Without a root cause, agents tend to fix symptoms rather than causes, producing cosmetic
changes that satisfy the `verify_plan` but recur within a few commits.

Field-test evidence (see `benchmark_results/v2.14.0_patch_engine_feature_evidence.json`) shows
that even with a complete `verify_plan` and `success_criteria`, agent-applied fixes reproduce at
a measurable rate. The root cause information is the missing link between "detecting the symptom"
and "preventing recurrence".

### Problem statement

An agent receiving a finding today sees:
- *What*: "Broad exception monoculture — 8/12 handlers use `except Exception`"
- *What to do*: "Replace broad handlers with specific exception types"
- *How to verify*: drift_scan reports 0 findings after fix

But not:
- *Why*: "Exception handling was added hastily during initial endpoint creation — callers were
  iterated over quickly and specific exception types were not yet known"

Without the *why*, agents:
1. Fix the immediately flagged file but not the pattern that causes recurrence
2. Apply mechanical transformations (e.g. replace `except Exception` with `except ValueError`)
   without addressing the underlying design issue
3. Cannot distinguish "fix the pattern" from "fix the instance"

## Decision

1. **Add `root_cause: str | None = None`** to the `Finding` dataclass in
   `src/drift/models/_findings.py`. The field is optional (None = unknown) and backward-compatible.

2. **Add `_root_cause_for(finding: Finding) -> str | None`** in
   `src/drift/output/agent_tasks.py`. The function follows the same pattern as
   `_success_criteria_for()` and `_expected_effect_for()` — a signal-specific if/elif chain
   returning a human-readable root cause string per signal type.

3. **Wire `root_cause` into `AgentTask.metadata`** in `_finding_to_task()`:
   `task.metadata["root_cause"] = _root_cause_for(finding)` (non-breaking — metadata is
   `dict[str, Any]`; `None` entries are serialised as `null`).

4. **Expose `root_cause` in JSON output**: `src/drift/output/json_output.py`
   `_finding_to_dict()` emits `"root_cause": f.root_cause` after `"fix"`.
   `src/drift/api_helpers.py` `_finding_detailed()` emits the same.

## Rationale

### Why on Finding, not only on AgentTask?

`Finding` is the stable, serialised record. `AgentTask` is a derived view. Placing `root_cause`
on `Finding` means:
- It appears in `drift scan --format json` output (useful for CI integrations)
- It is available to any consumer of the Finding model, not only agent loops
- It is part of the durable record alongside `description` and `fix`

### Why `metadata["root_cause"]` in AgentTask instead of a typed field?

`AgentTask.metadata` is `dict[str, Any]` by design — it absorbs enrichment data without
requiring a schema change on every new enrichment. A typed field would require a model schema
bump. Given that `root_cause` is already on `Finding` (the primary model), the metadata
pass-through is the correct pattern (consistent with `logical_location`, `repair_level`,
`dependency_depth`).

### Why not compute root_cause in the signal itself?

Signals run at analysis time; root cause framing is a remediation concern. Mixing concerns
would increase signal complexity and require signals to know about agent workflows. The
`agent_tasks.py` enrichment layer is the canonical place for agent-oriented metadata.

## Consequences

### Positive
- Agents can read `root_cause` from `AgentTask.metadata` and from the JSON output, enabling
  root-cause-targeted fixes rather than symptom-targeted fixes
- Improves `fix_success_rate` KPI (finding recurrence decreases when agents address root causes)
- Zero breaking change — `root_cause: str | None = None` is backward-compatible;
  JSON output consumers encountering `"root_cause": null` are unaffected
- Consistent pattern with existing enrichment functions (`_success_criteria_for`,
  `_expected_effect_for`, `_generate_constraints`)

### Negative / Risks
- Root cause strings are manually authored per signal (25 signals) — they may not capture all
  context-specific causes. Treated as informational guidance, not deterministic truth.
- Adds ~25 string literals to agent_tasks.py; reviewed for accuracy but not ground-truth-tested

## Alternatives considered

| Alternative | Reason rejected |
|---|---|
| Infer root cause from git blame/history | Too slow for real-time analysis; out of scope for detection phase |
| Generate root cause with LLM at agent time | Increases latency; introduces hallucination risk without deterministic verification |
| Add root_cause only to AgentTask metadata | Hides the field from non-agent JSON consumers |

## References

- ADR-072: Remediation Memory — baseline for root-cause tracking across sessions
- ADR-074: Patch Engine — transactional protocol that benefits from root-cause information
- `benchmark_results/v2.14.0_patch_engine_feature_evidence.json`
- METR SWE-bench analysis (2026-03-10)
