---
name: drift-session-handover-authoring
description: "Drift-specific workflow for authoring session handover artifacts before calling drift_session_end (ADR-079). Use when writing work_artifacts/session_<id>.md, preparing versioned benchmark_results evidence JSON, or drafting ADRs that pair with a session. Keywords: session handover, drift_session_end, DRIFT-6100, handover gate, work_artifacts, session_md, feature evidence, ADR draft, bypass_reason."
argument-hint: "Describe the session you are about to end (change class, touched paths, completed tasks, pending follow-ups)."
---

# Drift Session Handover Authoring

Use this skill when you are about to call `drift_session_end` and must produce
the handover artifacts required by ADR-079 and the session-handover contract in
`.github/prompts/_partials/session-handover-contract.md`.

## When To Use

- You touched files under `src/drift/` during the session.
- You completed one or more fix-plan tasks.
- You ran multiple scans / diffs / nudges and want to hand off to the next
  agent (or to the maintainer).
- `drift_session_end` returned `DRIFT-6100` and you need to fill the missing
  artifacts.

## When Not To Use

- Empty sessions (no tool calls beyond session start, no completed tasks, no
  touched files). The gate auto-exempts them.
- Pure read-only exploration that touched no code.

## Core Rules

1. **Agent writes, server validates.** You author the artifacts. The MCP
   server only checks existence, shape, placeholders (and optionally runs an
   LLM review). Do not try to satisfy the gate with generated filler.
2. **No placeholder tokens.** `TODO`, `FIXME`, `XXX`, `TBD`, `???`, `<N>`,
   `<NNN>`, `LOREM`, `IPSUM`, `FOO`, `BAR`, `BAZ` outside of ≥5-line code
   fences block the gate at L3.
3. **Cross-check session id.** The `session_id` in the Markdown frontmatter
   must match the active session exactly.
4. **SIGNAL / ARCHITECTURE classes require all three artifacts.** Evidence
   JSON, ADR draft, and session markdown.
5. **`force=true` is a last resort.** It requires an auditable
   `bypass_reason` of at least 40 characters without placeholder tokens, and
   it is logged and persisted in the session trace.

## Step 1: Policy Gate

Before writing artifacts, run the mandatory gate from
`.github/instructions/drift-policy.instructions.md`. If the underlying change
is inadmissible the gate blocks you here, not at `drift_session_end`.

## Step 2: Determine Your Change Class

Ask yourself what the session actually changed:

| Touched paths                                                   | Class          | Required artifacts                    |
|-----------------------------------------------------------------|----------------|---------------------------------------|
| `src/drift/signals/**` or `src/drift/scoring/**`                | `signal`       | evidence + ADR + session_md           |
| `src/drift/ingestion/**`, `output/**`, `api/**`, `mcp_*`, `session*` | `architecture` | evidence + ADR + session_md           |
| Other `src/drift/**`                                             | `fix`          | session_md                            |
| `docs/**`, `docs-site/**`, `.github/prompts/**`, skills, instructions | `docs`         | session_md                            |
| Only config, lockfiles, CI, tasks.json                          | `chore`        | session_md                            |

When in doubt, pick the highest-priority class that applies.

## Step 3: Author the Session Markdown

Copy `docs/session_handover_template.md` into
`work_artifacts/session_<first 8 chars of session_id>.md` and fill every
required section. Minimum length ≥ 200 bytes (the template already exceeds
this when filled meaningfully).

Required frontmatter fields:

- `session_id` (full id, matching the active session)
- `duration_seconds`
- `tool_calls`
- `tasks_completed`
- `findings_delta`
- `change_class`

Required sections:

1. `## Scope` — what you changed and what you deliberately did not.
2. `## Ergebnisse` — observable outcomes (tests, metrics, behaviour).
3. `## Offene Enden` — known follow-ups. Write "Keine offenen Enden" (no
   "TODO") if there really are none.
4. `## Next-Agent-Einstieg` — the exact first tool call and the first file
   path the next agent should open.
5. `## Evidenz` — pointers to the evidence JSON, ADR, and updated audit
   artifacts.

## Step 4: Author the Evidence JSON (signal / architecture only)

Use the `drift-evidence-artifact-authoring` skill to produce a versioned file
in `benchmark_results/`. The gate's L2 layer requires these JSON keys at
minimum:

- `version`
- `feature`
- `description`
- `tests`
- `audit_artifacts_updated` (non-empty list when the class is `signal` or
  `architecture`)

## Step 5: Author the ADR Draft (signal / architecture only)

Use the `drift-adr-workflow` skill. The gate's L2 layer requires:

- Frontmatter `status: proposed` or `accepted`.
- `## Kontext` with ≥ 120 substantive characters.
- At least two explicit "Alternative" mentions.
- `## Entscheidung` and `## Konsequenzen` sections with non-empty content.

## Step 6: Call `drift_session_end`

Pass explicit paths so the server can skip path-discovery:

```
drift_session_end(
    session_id="<sid>",
    session_md_path="work_artifacts/session_<id8>.md",
    evidence_path="benchmark_results/v<ver>_<slug>_feature_evidence.json",
    adr_path="docs/decisions/ADR-<NNN>-<slug>.md",
)
```

If the gate blocks, read the `missing_artifacts`, `shape_errors`, and
`placeholder_flags` arrays in the response and fix the specific issue before
retrying.

## Step 7: Force-Bypass (Notausgang)

Only if a release-critical hotfix makes full artifacts impossible and a
follow-up task is already queued:

```
drift_session_end(
    session_id="<sid>",
    force=True,
    bypass_reason=(
        "Hotfix-Session fuer Release-Blocker; Evidence-JSON und ADR "
        "werden im Follow-up-Task <task-id> bis <date> nachgereicht."
    ),
)
```

The reason must be specific, meaningful, and free of placeholder tokens.
`force=true` is logged at WARNING level and recorded in the session trace.
After the limit of 5 blocked retries the gate auto-unblocks if — and only if —
a valid `bypass_reason` is supplied.

## Validation

- `drift_session_end` returns `status: ok` with `handover_gate.ok=true`, or
  `handover_bypass.forced=true` with a valid reason.
- The session markdown shows up in `git status` under `work_artifacts/`.
- Evidence JSON and ADR are parseable and referenced from the session
  markdown's `## Evidenz` section.

## References

- `docs/decisions/ADR-079-session-handover-artifact-gate.md`
- `.github/prompts/_partials/session-handover-contract.md`
- `docs/session_handover_template.md`
- `src/drift/session_handover.py`
