# ADR-065 — Repair Template Registry

**Status:** proposed
**Deciders:** Mick Gottschalk
**Date:** 2026-04-12
**Related:** ADR-063 (fix-intent structured contract)

---

## Context

Drift provides `drift_fix_plan` with structured `AgentTask` objects per finding.  Each task
already carries `edit_kind`, `automation_fit`, `change_scope`, and `negative_context` from
ADR-063.  However, there is no prior learning: every task is generated from heuristics alone,
ignoring what the system has already seen work or fail in previous repair sessions.

Specifically, agents asked to fix PFS, DCA, BEM, or GCD findings repeatedly encounter the same
pitfalls (e.g. renaming a duplicate without consolidating the body) while the system offers no
historical guidance.

Three design questions needed resolution:

1. **Capture source**: Where does outcome evidence come from?
2. **Format**: How is the regression reason expressed?
3. **Integration point**: Where does the learned knowledge surface to agents?

---

## Decision

### D1 — Capture source: `drift_nudge` outcome capture

Outcomes are inferred from the `direction` field of `drift_nudge` responses.  When an agent
calls `nudge()` with optional `task_signal`, `task_edit_kind`, and `task_context_class` params:

- `direction == "improving"` → recorded as a positive outcome for that `(signal, edit_kind, context_class)` triple.
- `direction == "regressing"` → recorded as a negative outcome.
- `direction == "stable"` → **not recorded** (ambiguous: could mean overly defensive fix or
  correct but partial fix that doesn't yet move the score).

Evidence accumulates in `data/repair_templates/outcomes.jsonl` (git-ignored, user-local).  A
committed seed `data/repair_templates/templates.json` provides bootstrapped values from
`benchmark_results/repair/` corpus.

**Rejected alternatives:**

| Alternative | Reason rejected |
|------------|----------------|
| Post-commit CI scan | Too slow; requires CI round-trip; misses local agent loops |
| drift_diff outcome | `drift_diff` is batch-level; too coarse for per-task granularity |
| Manual agent feedback | Cannot be automated; inconsistent capture |
| Session active-task magic | Session doesn't store "currently fixed task" — explicit params are cleaner |

### D2 — Format: closed-enum `RegressionReasonCode`, no free text

Regression reasons use a closed `StrEnum` (`RegressionReasonCode`) rather than free-text:

| Code | Meaning |
|------|---------|
| `cosmetic_only` | Fix changed only names/formatting, not structural behavior |
| `incomplete_batch` | Fix was applied to one file in a batch_eligible group |
| `side_effect_volatility` | The fix raised a different signal's score as a side effect |
| `residual_findings` | Original signal still fires post-fix (finding not resolved) |
| `wrong_scope` | Fix was applied to wrong scope (e.g. test vs production code) |
| `signaling_lag` | Score moved on next full scan but not during nudge (lag artifact) |

**Motivation:** Free text would create hallucination surface and prevent reliable classification.
Structured codes allow agents to build conditional strategies: "if `side_effect_volatility` →
check temporal_volatility findings after applying this fix".

**Rejected alternatives:**

| Alternative | Reason rejected |
|------------|----------------|
| Free-text `reason` field | Hallucination surface; not machine-processable |
| Boolean `regressed: bool` | Too coarse, no actionable guidance |
| Numerical score only | Doesn't explain *why* the regression occurred |

### D3 — Integration point: inline fields on `AgentTask`, not a separate MCP tool

Learned knowledge surfaces as two optional fields on every `AgentTask` emitted by `drift_fix_plan`:

```json
{
  "template_confidence": 0.83,
  "regression_guidance": [
    {
      "edit_kind": "rename_symbol",
      "context_feature": "body_unchanged",
      "reason_code": "cosmetic_only"
    }
  ]
}
```

- `template_confidence: float | None` — proportion of improving outcomes over
  `improving + regressing` outcomes.  `null` when fewer than 3 recorded outcomes exist
  (insufficient evidence guard).
- `regression_guidance: list[RegressionPattern]` — structured list of observed regression
  patterns for this `(signal, edit_kind, context_class)` triple.

**Rejected alternatives:**

| Alternative | Reason rejected |
|------------|----------------|
| Separate `drift_repair_guidance` MCP tool | Extra round-trip; agents would need to call it for every task |
| Free-text `hints` field | Not verifiable; hallucination surface |
| Confidence only (no patterns) | Provides calibration but no actionable "what went wrong" info |

---

## Consequences

### Positive

- Agents see confidence + regression patterns inline without extra tool calls.
- Outcome learning is continuous and session-local (no server state required).
- Minimum evidence guard (`MIN_OUTCOMES_FOR_CONFIDENCE = 3`) prevents over-trust on thin data.
- `stable` deliberately excluded from confidence computation — no ambiguity inflation.
- `outcomes.jsonl` is git-ignored → no team-private data leaks into committed state.
- Committed seed (`templates.json`) provides immediate value from benchmark corpus.

### Negative

- User-local `outcomes.jsonl` means outcomes don't propagate across machines (by design).
- Seed data is manually curated from benchmarks — may diverge from project-specific patterns.
- `signaling_lag` regression code can produce false negatives in low-sensitivity repos.
- `template_confidence = null` for rare signals until ≥ 3 outcomes are recorded.

### Neutral

- The registry is a lazy singleton, loaded at first fix_plan call.  Registry failures are
  silenced (never block task generation or nudge response).
- Seed can be rebuilt from outcomes log via `RepairTemplateRegistry.rebuild_seed()`.

---

## Implementation Notes

- **Key files:**
  - `src/drift/models.py` — `RegressionReasonCode`, `RegressionPattern`, `AgentTask` fields
  - `src/drift/repair_template_registry.py` — `RepairTemplateRegistry`, `get_registry()`
  - `src/drift/output/agent_tasks.py` — `_enrich_task_from_registry()`, `_task_to_dict()` update
  - `src/drift/api/nudge.py` — `task_signal`, `task_edit_kind`, `task_context_class` params
  - `src/drift/mcp_server.py` — `drift_nudge` tool params forwarded to `nudge()`
  - `data/repair_templates/templates.json` — committed seed
  - `data/repair_templates/outcomes.jsonl` — git-ignored outcome log

- **Test coverage:** `tests/test_repair_template_registry.py`, extended `tests/test_agent_tasks.py`

---

## Decision Trailer

```
Decision-ID: ADR-065
Status: proposed
Signal-impact: none
Scoring-impact: none
Output-format-impact: additive (new optional fields on AgentTask)
Risk-audit-update: not required (additive fields, no scoring/signal change)
```
