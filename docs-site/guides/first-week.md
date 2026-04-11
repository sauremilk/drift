# First Week with Drift

A 5-day path from "just installed" to "using drift daily."

---

## Day 0 — Install and configure (5 min)

```bash
pip install drift-analyzer
drift setup          # answers 3 questions, creates drift.yaml
drift status         # first health check
```

A first-run score between **0.30–0.65** is normal for most active AI-assisted projects.

---

## Day 1 — Understand your top finding (15 min)

Pick the top finding from `drift status` and look it up:

```bash
drift explain PFS                    # full signal description + example
drift explain PFS --repo-context     # examples from your own code
```

Copy the AI prompt from `drift status`, paste it into your AI assistant, and apply the fix.
Re-run `drift status` — did the score drop?

---

## Day 2 — Work through 2–3 findings

Repeat the Day 1 loop for the next 2–3 findings:

1. Read the signal: `drift explain <ABBR>`
2. Check your code: `drift explain <ABBR> --repo-context`
3. Apply the AI prompt from `drift status`
4. Re-run `drift status`

**Tip:** Fix HIGH and CRITICAL findings first. MEDIUM can wait.

---

## Day 3 — Understand your signal landscape

```bash
drift explain --list    # overview of all signals with ★ AI-signal markers
drift analyze --repo .  # full signal breakdown with module scores
```

Which signals dominate your top module? Those are your structural focus areas.

---

## Day 4 — Establish a trend baseline

After fixing at least one issue, re-run:

```bash
drift status
```

Drift compares the new score with the baseline and shows a `Δ` trend indicator.

| Indicator | Meaning |
|-----------|---------|
| `↓ improving` | Your fixes worked |
| `→ baseline` | First run, no comparison yet |
| `↑ degrading` | New code added more drift than was fixed |

---

## Day 5 — (Optional) Add to CI

```yaml
# .github/workflows/drift.yml
- name: Drift analysis
  run: drift analyze --repo . --format sarif --exit-zero
```

`--exit-zero` means CI reports findings without blocking. Switch to `--fail-on high`
when you're ready to enforce hard quality gates.

See [CI/CD Integration](../use-cases/ci-architecture-checks-sarif.md) for the full guide.

---

## Quick-reference — the 3 most useful commands

| Command | When to use |
|---------|-------------|
| `drift status` | Daily health check |
| `drift explain <ABBR> --repo-context` | Before fixing a finding |
| `drift analyze --repo . --format json` | Deep signal inspection |

---

## Top 5 signals for AI-assisted code (★)

| Signal | What it flags | Fix time |
|--------|--------------|----------|
| **PFS** | Same concept solved multiple incompatible ways | 30–90 min |
| **MDS** | Near-identical functions diverged by copy-paste | 15–60 min |
| **EDS** | Complex AI-generated functions without docs or types | 20–45 min |
| **SMS** | New code that doesn't match the module's existing style | 30–90 min |
| **BAT** | Accumulation of `# noqa`, `type: ignore`, FIXME/TODO | 30–180 min |

Run `drift explain --list` to see all signals and which ones are AI-heavy.
