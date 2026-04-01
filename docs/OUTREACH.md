# Outreach Texts

Copy-paste-ready texts for external platforms.
Order = recommended priority.

## Naming + Claim Guardrails

- Repo: `sauremilk/drift`
- Package: `drift-analyzer`
- Command: `drift`
- Version: v1.3.0
- Safe signal claim: 15 scoring signals (auto-calibrated at runtime) + 7 report-only signals (security & complexity) = 22 total detectors.
- Safe CLI claim: 18 commands — `analyze`, `init`, `scan`, `diff`, `baseline`, `mcp`, `export-context`, `copilot-context`, `timeline`, `trend`, `patterns`, `badge`, `check`, `config`, `explain`, `fix-plan`, `self`, `validate`.
- Safe rollout claim: `drift init --profile vibe-coding` for zero-config start, then baseline + incremental adoption.
- Execution assets: see `docs/distribution/README.md` for awesome submissions, article draft, IDE MVP spec, and week-1 runbook.

---

## 1. Show HN (Hacker News)

**Title:**

```
Show HN: Drift – Deterministic architectural drift detection for AI-accelerated Python codebases
```

**Text (comment field):**

```
I built a static analyzer for deterministic architectural drift detection in
AI-accelerated Python codebases.

The problem: Copilot, Cursor, and ChatGPT optimize for the prompt context, not
the codebase context. The result is code that works but doesn't fit — error
handling fragments across 4 different patterns, import boundaries erode, and
near-identical functions accumulate with subtle differences.

Drift doesn't detect bugs. It detects the loss of design intent.

15 scoring signals cover pattern fragmentation, architecture violations,
mutant duplicates, explainability deficit, temporal volatility, system
misalignment, doc-impl drift, naming contracts, guard clauses, cohesion,
coupling, and more. 7 additional report-only signals cover security
(missing auth, hardcoded secrets, insecure defaults) and complexity.

All signals are deterministic, LLM-free, fast. Uses Python's built-in `ast`
module — zero dependencies on ML infrastructure.

New in v1.3.0:
- `drift init --profile vibe-coding` — zero-config onboarding with profiles
- `drift scan` / `drift diff` — agent-native JSON output for IDE integrations
- `drift mcp` — built-in MCP server for AI coding assistants
- `drift baseline` — incremental adoption, only flag new findings
- `drift timeline` / `drift trend` — track drift over time
- `drift export-context` — anti-pattern context for Copilot/Cursor rules

Package: pip install drift-analyzer
CLI:    drift analyze --repo .
CI:     uses: sauremilk/drift@v1 (GitHub Action, report-only by default)
Hook:   pre-commit hook available

https://github.com/sauremilk/drift
```

**Posting tips:**

- Best timing: Monday–Tuesday, 9–11 AM US Eastern
- URL: https://news.ycombinator.com/submitlink?u=https://github.com/sauremilk/drift

---

## 2. Reddit r/Python

**Title:**

```
I built drift – deterministic architectural drift detection for AI-accelerated Python repos
```

**Text:**

```
TL;DR: `pip install -q drift-analyzer && drift init --profile vibe-coding && drift analyze --repo .`

Copilot and Cursor write code that solves local tasks correctly but weakens
global design. Drift detects that architectural drift with 15 scoring signals
covering pattern, architecture, consistency, and contract dimensions — plus
7 report-only security signals.

Core signals:
- Pattern Fragmentation – same thing done N ways in one module
- Architecture Violations – wrong-direction imports
- Mutant Duplicates – near-identical functions (copy-paste-then-modify)
- Explainability Deficit – complex functions without docs or types
- Temporal Volatility – files changed by too many authors too fast
- System Misalignment – patterns foreign to their target module

Plus: doc-impl drift, naming contracts, guard clauses, cohesion, coupling,
exception contracts, bypass accumulation, test polarity, co-change coupling.

No LLMs in the detection pipeline. Pure AST analysis + statistics.
Outputs: rich terminal dashboard, JSON, or SARIF for GitHub Code Scanning.

Key features:
- `drift init --profile vibe-coding` — zero-config onboarding
- `drift baseline` — incremental adoption, only flag new findings
- `drift scan` / `drift diff` — agent-native JSON for IDE integrations
- `drift mcp` — built-in MCP server for AI coding assistants
- `drift timeline` / `drift trend` — track architectural drift over time

GitHub: https://github.com/sauremilk/drift
```

**Subreddits (post all):**

- r/Python
- r/programming
- r/softwarearchitecture
- r/devops

---

## 3. awesome-static-analysis PR

**Repo:** https://github.com/analysis-tools-dev/static-analysis/pulls

**File:** `data/tools/python.yml` (or similar, depending on repo structure)

**Entry:**

```yaml
- name: drift
  categories: [code-quality, architecture]
  languages: [python]
  description: >
    Deterministic architectural drift detection for AI-accelerated Python codebases.
    22 detectors covering pattern fragmentation, architecture violations, mutant
    duplicates, security signals, and more. Built-in MCP server, baseline
    management, and profiles for incremental adoption.
  homepage: https://github.com/sauremilk/drift
  license: MIT
```

**PR title:** `Add drift – architectural drift detector for AI-accelerated Python repos`

---

## 4. awesome-python PR

**Repo:** https://github.com/vinta/awesome-python/pulls

**Section:** `Code Analysis`

**Entry:**

```
* [drift](https://github.com/sauremilk/drift) - Deterministic architectural drift detection for AI-accelerated Python codebases. 22 detectors, MCP server, agent-native workflows.
```

**PR title:** `Add drift to Code Analysis section`

---

## 5. Reddit r/ExperiencedDevs

**Title:**

```
How do you detect architectural drift in AI-accelerated codebases?
```

**Text:**

```
I've been working on a problem that I think many experienced teams are quietly
dealing with: AI coding assistants produce code that works, passes review, and
solves the immediate task — but slowly fragments the architecture.

The patterns are subtle:
- Error handling that was once unified now has 4 implementations across modules
- Import boundaries that used to be clean now leak across layers
- Functions that look original but are near-duplicates of code elsewhere

These aren't bugs. Linters won't flag them. They compound silently until the
codebase resists change.

I built drift, a static analyzer focused specifically on this problem. It runs
15 scoring signals covering pattern fragmentation, layer violations,
near-duplicates, explainability gaps, naming contracts, cohesion, coupling,
exception contracts, and more — plus 7 report-only detectors for security
(missing auth, hardcoded secrets, insecure defaults) and complexity.

Key design decisions:
- No LLMs in the pipeline. Deterministic, reproducible, fast.
- Designed for CI integration, not as a one-shot audit tool.
- Outputs SARIF for GitHub Code Scanning integration.
- `drift init --profile vibe-coding` for zero-config onboarding.
- `drift baseline` for incremental adoption — only flag new findings.
- Built-in MCP server (`drift mcp`) for AI assistant integration.
- `drift scan` / `drift diff` for agent-native workflows.
- `drift timeline` / `drift trend` to track drift over time.

Not a pitch — genuinely curious how other teams track this kind of drift, and
whether deterministic static analysis is the right abstraction.

https://github.com/sauremilk/drift
```

**Posting note:** Experience-based discussion tone. No "I built X" spam.

---

## 6. Twitter / X Thread (5 Tweets)

**Thread:**

```
🧵 1/5
AI coding tools optimize for the prompt, not the project.

The result: code that works locally but fragments your architecture globally.

I built an open-source tool to detect this — deterministic, LLM-free, and now
with built-in MCP server for AI assistant integration. ↓
```

```
2/5
The problem has a name: architectural drift.

- Error handling done 4 different ways in one module
- DB imports leaking into the API layer
- Copy-paste functions that diverged into near-duplicates

These aren't bugs. Linters won't catch them. But they compound.
```

```
3/5
drift runs 15 deterministic scoring signals:

• Pattern Fragmentation
• Architecture Violations
• Mutant Duplicates
• Explainability Deficit
• Temporal Volatility
• System Misalignment
• Doc-Impl Drift, Naming Contracts, Guard Clauses
• Cohesion, Coupling, Exception Contracts
+ 7 report-only security & complexity detectors

No LLMs. Pure AST analysis. Reproducible.
```

```
4/5
On FastAPI (664 files): drift score 0.62, 360 findings.
On Django (2890 files): drift score 0.60, 969 findings.
On Frappe (1179 files): drift score 0.54, 913 findings.

Not a quality judgment — a coherence signal.
```

```
5/5
pip install -q drift-analyzer
drift init --profile vibe-coding
drift analyze --repo .

- Rich terminal dashboard, JSON + SARIF output
- `drift mcp` — MCP server for Copilot/Cursor/Claude
- `drift scan` / `drift diff` — agent-native workflows
- `drift baseline` — incremental adoption
- `drift timeline` / `drift trend` — track drift over time
- GitHub Action: uses: sauremilk/drift@v1

→ https://github.com/sauremilk/drift
```

---

## 7. dev.to / Hashnode Article

**Title:**

```
How Copilot silently fragments your architecture — and how to detect it with drift
```

**Tags:** `python`, `architecture`, `static-analysis`, `ai`

**Article:**

````markdown
## The problem nobody talks about

AI coding assistants are fast. They pass tests. They get approved in review.
But they optimize for one thing: the immediate prompt context.

They don't know your architecture. They don't know you already have a
`handle_auth_error()` function. They don't know that `src/db/` shouldn't import
from `src/api/`.

The result is a slow, invisible rot. Not bugs — erosion. Your codebase still
works, but it resists change more every week.

## What architectural drift looks like

Here's what drift found when I ran it on FastAPI (664 files, 3,902 functions):

- **Drift Score: 0.62** (high severity)
- **360 findings** across all signal families
- Top signal: System Misalignment — novel dependency patterns in multiple modules

On Django (2,890 files):
- **Drift Score: 0.60** — 969 findings
- Top signals: Explainability Deficit in admin module (complex functions without docs)

On Frappe (1,179 files):
- **Drift Score: 0.54** — 913 findings
- 92 error handling variants in `frappe/utils/` alone

This isn't "bad code." It's code that grew without coherent design pressure.

## The 22 detectors

Drift runs 15 scoring signals plus 7 report-only detectors.

### Core signals (ablation-validated)

**1. Pattern Fragmentation (PFS)**
Same concern implemented N different ways in the same module. Classic example:
error handling done with `try/except`, `if/else`, early returns, and custom
exceptions — all in the same package.

**2. Architecture Violations (AVS)**
Imports crossing layer boundaries. Database models imported in API routes.
Presentation logic reaching into domain internals.

**3. Mutant Duplicates (MDS)**
Functions that are 80–95% identical — the signature of copy-paste-then-modify.
Individually fine, collectively a maintenance burden.

**4. Explainability Deficit (EDS)**
Complex functions (high cyclomatic complexity, deep nesting) with no
docstrings, no type annotations, and no tests. Not wrong — but unexplainable.

**5. Temporal Volatility (TVS)**
Files changed by too many authors in too short a time. Hotspots where
ownership is unclear and merge conflicts are likely.

**6. System Misalignment (SMS)**
Recently introduced patterns that are foreign to their target module.
The function works, but its style doesn't match anything around it.

### Consistency & contract signals

**7–15:** Doc-Impl Drift (DIA), Broad Exception Monoculture (BEM), Test
Polarity Deficit (TPD), Guard Clause Deficit (GCD), Naming Contract Violation
(NBV), Bypass Accumulation (BAT), Exception Contract Drift (ECM), Cohesion
Deficit (COD), Co-Change Coupling (CCC). All scoring-active with conservative
weights, auto-calibrated at runtime.

### Report-only signals (security & complexity)

**16–22:** Cognitive Complexity (CXS), Fan-Out Explosion (FOE), Circular
Import (CIR), Dead Code Accumulation (DCA), Missing Authorization (MAZ),
Insecure Default (ISD), Hardcoded Secret (HSC). These are visible in findings
but don't affect the composite score yet — precision validation in progress.

See the [signal reference](https://sauremilk.github.io/drift/reference/signals/) for full details.

## No LLMs. Deterministic. Fast.

Drift uses Python's built-in `ast` module, git history analysis, and
statistical comparison. No model calls, no API keys, no flaky results.

The same input always produces the same output. That's the foundation
for trust: reproducibility.

## Getting started in 30 seconds

```bash
pip install -q drift-analyzer
drift init --profile vibe-coding
drift analyze --repo .
```

`drift init` creates a `.drift.yaml` config with sensible defaults. Three
profiles are available:
- **default** — balanced for most projects
- **vibe-coding** — tuned for AI-heavy development workflows
- **strict** — maximum sensitivity for critical codebases

## Agent & IDE integration

Drift is built for AI-assisted workflows, not just humans:

```bash
# MCP server for Copilot, Cursor, Claude, etc.
drift mcp

# Agent-native JSON output
drift scan --repo .             # full analysis, structured JSON
drift diff --repo .             # only findings in changed files

# Export anti-pattern context for AI coding assistants
drift export-context --repo .   # generates rules for Copilot/Cursor
drift copilot-context --repo .  # .github/copilot-instructions.md format
```

## Incremental adoption

You don't have to fix 300 findings on day one:

```bash
# Set a baseline — all current findings are "known"
drift baseline --repo . --save

# Only new findings are flagged from now on
drift analyze --repo . --baseline
```

## Track drift over time

```bash
drift timeline --repo . --module src/api/
drift trend --repo .
```

## CI integration

```yaml
- uses: sauremilk/drift@v1
  with:
    fail-on: none
    upload-sarif: "true"
```

## What drift is not

- Not a linter (doesn't check style or formatting)
- Not a security scanner (the security signals are a bonus, not the focus)
- Not a test coverage tool

It's a structural coherence analyzer. Think of it as a code review assistant
that reads the whole codebase instead of just the diff.

## Links

- GitHub: [sauremilk/drift](https://github.com/sauremilk/drift)
- PyPI: [drift-analyzer](https://pypi.org/project/drift-analyzer/)
- Docs: [sauremilk.github.io/drift](https://sauremilk.github.io/drift/)
````

---

## 8. Discord

**Recommended servers:**
- Python Discord (`#showcase` channel)
- The Programmer's Hangout
- AI Engineer Discord

**Example post:**

```
Built an open-source static analyzer for architectural drift — the kind of
structural erosion that happens when AI coding tools fragment your patterns,
cross layer boundaries, and accumulate near-duplicates.

22 detectors (15 scoring + 7 security/complexity), no LLMs, fast.
Pure AST + git history analysis.

New: built-in MCP server for Copilot/Cursor, agent-native `scan`/`diff`
commands, profiles for zero-config onboarding, baseline management for
incremental adoption.

pip install -q drift-analyzer && drift init --profile vibe-coding && drift analyze --repo .

Feedback welcome: https://github.com/sauremilk/drift
```

---

## 9. PyPI Publishing (one-time)

```bash
# 1. Configure Trusted Publisher on PyPI:
#    https://pypi.org/manage/account/publishing/
#    GitHub repo: sauremilk/drift
#    Workflow: publish.yml
#    Environment: pypi

# 2. Then simply create a new GitHub Release:
gh release create v1.3.0 --title "v1.3.0" --generate-notes
# → GitHub Action publish.yml builds and pushes to PyPI automatically
```

---

## 10. pre-commit.ci (automatic indexing)

After pushing `.pre-commit-hooks.yaml`, drift is automatically indexed at
https://pre-commit.ci. No further action needed.

The icon then appears on the pre-commit.ci page and in their search.
