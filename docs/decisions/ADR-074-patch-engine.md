# ADR-074: Patch Engine — Transaktionales Protokoll für Agentenänderungen

**Status:** proposed
**Date:** 2026-04-17
**Decision:** Introduce a transactional patch protocol for agent-driven code changes

## Context

Current agent workflows optimise for "tests pass" rather than "change is correct and reviewable".
METR research shows roughly half of SWE-bench-passing PRs would not be merged into mainline
(https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/).
Drift already provides `nudge`, `diff`, `verify`, and session-based fix loops, but there is
no single protocol that forces an agent to **declare intent before editing**, **prove scope
compliance after editing**, and **produce a machine-readable verdict** for merge readiness.

## Decision

Add a three-phase transactional layer — `patch_begin` → `patch_check` → `patch_commit` —
exposed as MCP tools, API endpoints, CLI subcommands, and A2A skills.

### Core Types

| Type | Purpose |
|------|---------|
| `PatchIntent` | Agent-declared scope, blast radius, expected outcome, constraints — **before** editing |
| `PatchVerdict` | Scope-compliance, diff metrics, architecture impact, acceptance results — **after** editing |
| `PatchStatus` | CLEAN / REVIEW_REQUIRED / ROLLBACK_RECOMMENDED |

### Enforcement Model

**Advisory (tag + warning).** Scope violations produce `REVIEW_REQUIRED`, not a hard block.
Agents decide whether to revert. CI systems can enforce hard gates by checking `PatchVerdict.status`.

### Granularity

One `PatchIntent` per `AgentTask`. A task may touch multiple files, but all must be declared upfront.

### Integration Points

- `patch_begin` records a `PatchIntent` and captures a baseline via `nudge()`
- `patch_check` validates scope against `git diff`, calls `nudge()` for architecture impact, computes verdict
- `patch_commit` produces an evidence record and marks the session task complete
- Session tracks `active_patches` and `patch_history`
- Telemetry logs `patch_begin`/`patch_check`/`patch_commit` events

### Relationship to TaskSpec

`PatchIntent` is a separate Pydantic model (has runtime state: `session_id`, `created_at`),
but bridge methods on `TaskSpec.to_patch_intent()` and `AgentTask.to_patch_intent()` map
existing fields: `scope_boundaries` → `declared_files`, `quality_constraints` → `quality_constraints`,
`change_scope` → `blast_radius`, `verify_plan` → `acceptance_criteria`.

## Consequences

### Positive

- Agents must declare intent before editing — shifts optimisation from output volume to change quality
- Machine-readable verdicts enable CI merge gates and benchmark comparisons
- Evidence records create an auditable trace of every agent patch
- Advisory model preserves agent autonomy while providing guardrails
- Builds on existing infrastructure (session, nudge, diff, verify) — low marginal complexity

### Negative

- 3 new MCP tools + API endpoints increase surface area
- Agents that don't adopt the protocol gain no benefit (opt-in)
- Scope-check relies on git diff, which requires a clean working tree baseline

### Neutral

- Existing fix-loop workflow remains unchanged (patch engine is an additional, optional path)
- No changes to signal detection, scoring, or output formats

## Alternatives Considered

1. **Hard enforcement (revert on scope violation):** Rejected — too disruptive, breaks agent autonomy
2. **Per-edit granularity:** Rejected — too noisy; per-task matches existing AgentTask abstraction
3. **New top-level model (not based on TaskSpec):** Rejected — duplicates existing fields; bridge pattern reuses validated structure
