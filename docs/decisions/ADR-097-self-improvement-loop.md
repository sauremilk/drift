# ADR-097 — Drift Self-Improvement Loop (DSOL)

- Status: proposed
- Date: 2025-11-23
- Supersedes: —
- Related: ADR-096 (Automation-Hardening), POLICY.md §6, §8, §16

## Context

The user requirement is verbatim:

> "ich spreche von einem Loop der nie endet und das System immer immer
> weiter optimiert."

The existing toolchain has many one-shot quality gates (lint, tests,
audit-diff, push gates) and several scheduled jobs (calibration cycle,
mutation benchmark), but no compounding feedback loop that:

1. observes drift's own quality continuously,
2. converts observations into prioritized improvement proposals,
3. remembers what it has already proposed so unresolved issues climb
   in priority over time, and
4. never auto-merges, never comments unsolicited on issues, never
   pushes — strictly POLICY-compliant.

Without such a loop, optimization pressure depends entirely on
maintainer attention. A drop in `aggregate_f1` or a hotspot signal can
remain invisible until somebody notices.

## Decision

Introduce a never-ending **Drift Self-Improvement Loop (DSOL)** as a
five-stage process, runnable both locally (`drift self-improve run`)
and on a weekly cron workflow (`.github/workflows/self-improvement-loop.yml`):

1. **OBSERVE** — load the latest `benchmark_results/drift_self.json`
   and `benchmark_results/kpi_trend.jsonl` if present (graceful no-op
   otherwise).
2. **DIAGNOSE** — derive three classes of signals:
   - regressive KPI slopes (e.g. `aggregate_f1`, `mutation_recall`,
     `precision_recall_mean`) below a configurable negative slope
     threshold (`-0.005` per snapshot by default);
   - hotspot findings ranked by `severity_weight × score` with a
     per-signal cap so one noisy signal cannot dominate;
   - stale audit artefacts (signal source files newer than
     `audit_results/*.md` by ≥14 days).
3. **PROPOSE** — emit `ImprovementProposal` records (frozen pydantic
   models) with `proposal_id`, `score`, `rationale`,
   `suggested_action`, `recurrence`. Hard cap `--max-proposals`
   (default 10) acts as flood guard.
4. **EMIT** — write deterministic artefacts under
   `work_artifacts/self_improvement/<cycle_ts>/`:
   - `proposals.json`,
   - `summary.md` (human-reviewable Markdown).
5. **TRACK** — append one JSON line per cycle to
   `.drift/self_improvement_ledger.jsonl`. The next cycle reads this
   ledger; previously seen `proposal_id`s get `recurrence=2`, which
   sorts them ahead of fresh ones.
6. **WAIT** — control returns to the cron tick. The compounding ledger
   means *every cycle is informed by every previous cycle*, so the
   loop "never ends and always optimizes further" without unbounded
   resource use.

### Hard guardrails (POLICY-aligned)

| Concern                          | Mitigation                                                         |
| -------------------------------- | ------------------------------------------------------------------ |
| Loop runaway / proposal flood    | `DEFAULT_MAX_PROPOSALS=10`, per-signal cap = `max_items // 3`      |
| Auto-merge risk                  | DSOL never opens PRs, never patches code, never edits config       |
| Unsolicited comments on issues   | Workflow uploads artefact + writes job summary only                |
| Metric gaming                    | All proposals require human review; status defaults to `proposed`  |
| Ledger corruption / partial JSON | `_safe_load_jsonl` skips malformed lines silently                  |
| Push without consent             | Workflow has `permissions: contents: read` only                    |

## Consequences

Positive:
- Continuous, compounding optimization pressure with bounded blast radius.
- Maintainer always retains final authority — the loop only proposes.
- Long-standing issues automatically surface higher each week.
- Works offline (CLI) and in CI (cron) with identical semantics.

Negative:
- Requires periodic ledger pruning if proposals accumulate
  indefinitely (out of scope; addressed in a future ADR if needed).
- Adds one weekly Actions run (~2-3 minutes).

## Out of scope

- Auto-merging, auto-commenting, auto-PR creation.
- Modifying signal scoring weights based on DSOL output (would couple
  observation and behavior — explicitly forbidden).
- Cross-repo DSOL execution.
- Write-Back mit Score-Gate und Convergence-Gate: ADR-098.
