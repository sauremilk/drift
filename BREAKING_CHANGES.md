# Breaking Changes

This document lists every user-visible breaking change in drift releases.

## How breaking changes are versioned

Drift uses [python-semantic-release](https://github.com/python-semantic-release/python-semantic-release)
and [Conventional Commits](https://www.conventionalcommits.org/).
A commit with a `BREAKING CHANGE:` footer trailer triggers an automatic MAJOR
version bump in CI.

New major or minor versions that include a breaking change are listed below with
migration guidance.

---

## [2.26.0] — `agent.strict_guardrails` default flipped (2026-04-22)

**Signal / Config change**

`agent.strict_guardrails` was previously `false` by default.
Starting with v2.26.0 it defaults to `true` (ADR-080).

### Impact

- `drift_fix_apply` and `drift_patch_begin` are now blocked when the last brief
  raised low scope confidence (`scope.confidence < 0.5`), or when the brief is
  stale (score drift > 0.1, > 20 tool calls since last brief, or > 30 minutes
  elapsed).
- Commits are blocked via the pre-commit `nudge_gate` when the last nudge
  recommended `REVERT` and flagged files are unchanged.

### Migration

Add the following to your `drift.yaml` to restore the v2.25.0 behaviour:

```yaml
agent:
  strict_guardrails: false
```

---

## [2.9.13] — CSV output: `signal_label` column added (2026-04-12)

**Output format change**

The `--format csv` output gained a new `signal_label` column (a human-readable
name for the signal). This column is inserted at position 2, shifting all
existing columns at index ≥ 2 by one position.

### Impact

Any script or pipeline that accesses CSV output by column *index* (e.g., `awk -F,
'{print $3}'`) will read from the wrong column after upgrading.

### Migration

- Switch from positional column references to **named column references** using
  the CSV header row (all parsers that support named columns are unaffected).
- Or update your column-index references: add 1 to every index ≥ 2.

New column order (from v2.9.13):

| Index | Column |
|-------|--------|
| 0 | `file` |
| 1 | `signal` |
| **2** | **`signal_label`** *(new)* |
| 3 | `severity` *(was 2)* |
| 4 | `score` *(was 3)* |
| … | … |

---

## [2.0.0] — Release automation migrated to python-semantic-release (2026-04-02)

**Internal tooling change (no user-facing API change)**

The v2.0.0 major version bump was triggered by the migration from a manual
`chore: Release`-gated workflow to
[python-semantic-release](https://github.com/python-semantic-release/python-semantic-release)
in CI.

No user-facing CLI, config-schema, output-format, or Python API changes were
made in this release.
