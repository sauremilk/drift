# First Week with Drift

A 5-day onboarding path from "just installed" to "using drift daily".

---

## Day 0 — Install and configure (5 minutes)

```bash
pip install drift-analyzer
drift setup          # answers 3 questions, creates drift.yaml
drift status         # first health check
```

Expected first-run score: **0.30–0.65** for most active AI-assisted projects. This is normal.

---

## Day 1 — Understand your top finding (15 minutes)

Pick the top finding from `drift status`:

```bash
drift explain PFS               # full signal description
drift explain PFS --repo-context  # examples from your own code
```

Copy the prompt from `drift status` into your AI assistant. Let it suggest a fix.
Verify the suggestion makes sense — then apply it.

Run `drift status` again. Did the score drop?

---

## Day 2 — Work through 2–3 findings

Repeat the loop from Day 1 for the next 2–3 findings:

1. Read the signal description: `drift explain <ABBR>`
2. Check in your codebase: `drift explain <ABBR> --repo-context`
3. Copy the AI prompt from `drift status`
4. Apply the fix
5. Re-run `drift status`

**Tip:** Focus on HIGH and CRITICAL findings first. MEDIUM findings can wait.

---

## Day 3 — Understand your signal landscape

```bash
drift explain --list    # overview of all signals
drift analyze --repo .  # full signal-level breakdown
```

Look at the module breakdown for your top-scoring module:

```bash
drift analyze --repo . --format json | python -m json.tool
```

Which signals are highest? Those are the structural patterns to address long-term.

---

## Day 4 — Set up a trend baseline

Run a second analysis (after fixing at least one issue):

```bash
drift status
```

Drift automatically compares this run to the baseline. You'll see a `Δ` trend indicator:

- `↓ improving` — good, your fixes worked
- `→ baseline` — first measurement, no comparison yet
- `↑ degrading` — new code introduced more drift than was fixed

---

## Day 5 — Add drift to CI (optional but recommended)

Add to your CI pipeline:

```yaml
# .github/workflows/drift.yml
- name: Run drift analysis
  run: drift analyze --repo . --format sarif --exit-zero
```

Using `--exit-zero` means CI never blocks on drift findings — it only reports them.
Switch to `--fail-on high` later when you're ready to enforce quality gates.

**Full guide:** [CI Integration](ci-integration.md)

---

## Quick reference: the 3 most useful commands

| Command | When to use |
|---------|-------------|
| `drift status` | Daily check — is my project healthy? |
| `drift explain <ABBR> --repo-context` | Before fixing a finding |
| `drift analyze --repo . --format json` | Deep dive into signal scores |

---

## What signals matter most for AI-assisted code?

| Signal | What it flags | Fix time |
|--------|--------------|----------|
| **PFS** ★ | Same problem solved 3 different ways in one module | 30–90 min |
| **MDS** ★ | Near-duplicate functions that diverged over sessions | 15–60 min |
| **EDS** ★ | Complex AI-generated functions without docs or types | 20–45 min |
| **SMS** ★ | New code that doesn't match the module's existing style | 30–90 min |
| **BAT** ★ | Accumulation of `# noqa`, `type: ignore`, TODO comments | 30–180 min |

★ = triggered especially often by AI-generated code (`drift explain --list` shows all)
