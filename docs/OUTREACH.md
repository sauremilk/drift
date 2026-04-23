# Outreach Texts

Copy-paste-ready texts for external platforms.
Order = recommended priority.

## Naming + Claim Guardrails

- Repo: `mick-gsk/drift`
- Package: `drift-analyzer`
- Command: `drift`
- Version: v2.5.1
- Safe signal claim: 19 scoring signals (auto-calibrated at runtime) + 5 report-only signals (TVS, TSA, CXS, CIR, DCA) = 24 total detectors.
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

19 scoring signals cover pattern fragmentation, architecture violations,
mutant duplicates, explainability deficit, system misalignment, doc-impl
drift, naming contracts, guard clauses, cohesion, coupling, exception
contracts, test polarity, bypass accumulation, security, and AI quality —
plus 5 report-only detectors for temporal volatility, TypeScript architecture,
complexity, circular imports, and dead code.

All signals are deterministic, LLM-free, fast. Uses Python's built-in `ast`
module — zero dependencies on ML infrastructure.

Key features:
- `drift init --profile vibe-coding` — zero-config onboarding with profiles
- `drift scan` / `drift diff` — agent-native JSON output for IDE integrations
- `drift mcp` — built-in MCP server for AI coding assistants
- `drift baseline` — incremental adoption, only flag new findings
- `drift timeline` / `drift trend` — track drift over time
- `drift export-context` — anti-pattern context for Copilot/Cursor rules

Package: pip install drift-analyzer
CLI:    drift analyze --repo .
CI:     uses: mick-gsk/drift@v2 (GitHub Action, report-only by default)
Hook:   pre-commit hook available

https://github.com/mick-gsk/drift
```

**Posting tips:**

- Best timing: Monday–Tuesday, 9–11 AM US Eastern
- URL: https://news.ycombinator.com/submitlink?u=https://github.com/mick-gsk/drift

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
global design. Drift detects that architectural drift with 19 scoring signals
covering pattern, architecture, consistency, security, and contract dimensions — plus
5 report-only signals for temporal volatility, TypeScript architecture,
complexity, circular imports, and dead code.

Core signals:
- Pattern Fragmentation – same thing done N ways in one module
- Architecture Violations – wrong-direction imports
- Mutant Duplicates – near-identical functions (copy-paste-then-modify)
- Explainability Deficit – complex functions without docs or types
- Temporal Volatility (report-only) – files changed by too many authors too fast
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

GitHub: https://github.com/mick-gsk/drift
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
    23 detectors covering pattern fragmentation, architecture violations, mutant
    duplicates, security signals, and more. Built-in MCP server, baseline
    management, and profiles for incremental adoption.
  homepage: https://github.com/mick-gsk/drift
  license: MIT
```

**PR title:** `Add drift – architectural drift detector for AI-accelerated Python repos`

---

## 4. awesome-python PR

**Repo:** https://github.com/vinta/awesome-python/pulls

**Section:** `Code Analysis`

**Entry:**

```
* [drift](https://github.com/mick-gsk/drift) - Deterministic architectural drift detection for AI-accelerated Python codebases. 23 detectors, MCP server, agent-native workflows.
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
19 scoring signals covering pattern fragmentation, layer violations,
near-duplicates, explainability gaps, naming contracts, cohesion, coupling,
exception contracts, test polarity, guard clauses, bypass accumulation,
security, and AI quality —
plus 5 report-only detectors for temporal volatility, TypeScript architecture,
complexity, circular imports, and dead code.

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

https://github.com/mick-gsk/drift
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
- GitHub Action: uses: mick-gsk/drift@v2

→ https://github.com/mick-gsk/drift
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

## The 24 detectors

Drift runs 19 scoring signals plus 5 report-only detectors.

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

### Remaining report-only signals

TVS remains report-only in the live model, and the remaining report-only set is
TypeScript Architecture (TSA), Cognitive Complexity (CXS), Circular Import (CIR),
and Dead Code Accumulation (DCA). These signals are visible in findings but do
not affect the composite score yet — precision validation remains in progress.

See the [signal reference](https://mick-gsk.github.io/drift/reference/signals/) for full details.

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
- uses: mick-gsk/drift@v2
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

- GitHub: [mick-gsk/drift](https://github.com/mick-gsk/drift)
- PyPI: [drift-analyzer](https://pypi.org/project/drift-analyzer/)
- Docs: [mick-gsk.github.io/drift](https://mick-gsk.github.io/drift/)
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

24 detectors (19 scoring + 5 report-only), no LLMs, fast.
Pure AST + git history analysis.

New: built-in MCP server for Copilot/Cursor, agent-native `scan`/`diff`
commands, profiles for zero-config onboarding, baseline management for
incremental adoption.

pip install -q drift-analyzer && drift init --profile vibe-coding && drift analyze --repo .

Feedback welcome: https://github.com/mick-gsk/drift
```

---

## 9. PyPI Publishing (one-time)

```bash
# 1. Configure Trusted Publisher on PyPI:
#    https://pypi.org/manage/account/publishing/
#    GitHub repo: mick-gsk/drift
#    Workflow: publish.yml
#    Environment: pypi

# 2. Then simply create a new GitHub Release:
gh release create v2.5.1 --title "v2.5.1" --generate-notes
# → GitHub Action publish.yml builds and pushes to PyPI automatically
```

---

## 10. pre-commit.ci (automatic indexing)

After pushing `.pre-commit-hooks.yaml`, drift is automatically indexed at
https://pre-commit.ci. No further action needed.

---

## 11. Blog-Post Outlines (distribution-phase content)

Three ready-to-draft articles targeting the competitive landscape from the
Q2 2026 analysis. Each has a confirmed angle, target audience, platform, and
key claims.

---

### Article A — "drift vs SonarQube: What your SAST tool doesn't see"

**Platform:** Dev.to, Hashnode
**Tags:** `python`, `architecture`, `static-analysis`, `sonarqube`
**Target audience:** teams already running SonarQube who wonder if they have
a structural coherence gap

**Outline:**

1. **Hook:** You run SonarQube. Your security score is green. So why does your
   codebase resist change more every quarter?
2. **The gap:** SonarQube finds known-bad patterns. Drift finds structural erosion
   — the same problem solved four different ways, modules that shouldn't know
   about each other, the architectural shape of your repo changing silently.
3. **Concrete example:** MDS finding on a 50-file codebase that SonarQube would
   pass. Side-by-side: SonarQube report (clean), drift report (3 MDS findings,
   1 PFS finding).
4. **The temporal layer:** SonarQube sees the current snapshot. Drift sees the
   trajectory. Co-Change Coupling and Temporal Volatility only exist in the git
   history — no scanner without history analysis can find them.
5. **Setup CLI:** `pip install drift-analyzer && drift analyze --repo .` in 30s.
6. **Call to action:** Add drift alongside SonarQube. Not instead.

**Key claims (safe to publish):**
- Drift runs in seconds locally with zero server setup
- Bayesian per-repo calibration adapts signal weights to observed repair outcomes
- SARIF output integrates with GitHub Code Scanning alongside CodeQL findings

---

### Article B — "Why deterministic analysis outperforms LLM-based code review"

**Platform:** r/Python, Hacker News, r/ExperiencedDevs
**Tags:** `python`, `ai`, `code-quality`, `architecture`
**Target audience:** teams evaluating DeepSource, AI-based review tools, or
considering `git ls-files | xargs cat | claude "..."` workflows

**Outline:**

1. **Hook:** LLM-based code review is impressive. It is also non-reproducible.
   The same code produces different results on different runs — that is a
   fundamental property of any LLM-based system.
2. **The compliance problem:** For FinTech, HealthTech, or any team that needs
   audit trails, non-reproducible findings are not findings — they are opinions.
3. **What determinism buys you:**
   - Same input → same output on every run, every developer, every CI agent
   - Exit codes that CI gates can rely on
   - SARIF output that tools can track and compare over time
   - Trend lines that reflect reality, not model variance
4. **Concrete comparison:** DeepSource autofix (stochastic) vs drift finding
   (deterministic). The DeepSource result is plausible. The drift result is
   the same every time.
5. **When LLM review is genuinely better:** Ad-hoc exploration, single-developer
   projects, reviews that need natural language explanation. Drift does not try
   to compete here.
6. **Call to action:** Determinism and CI-grade output for team environments.
   LLM reviews for personal exploration. Both have a place — knowing which
   question you're asking determines which tool to use.

**Key claims (safe to publish):**
- Drift uses Python's built-in `ast` module and statistical comparison — zero ML
- No API keys, no external service calls, no flaky results
- Bayesian calibration uses observed repair data, not LLM judgment

---

### Article C — "Pre-task guardrails: How drift works before GitHub Copilot Code Review"

**Platform:** LinkedIn, Dev.to
**Tags:** `ai`, `copilot`, `architecture`, `developer-workflow`
**Target audience:** developers and engineering leads using GitHub Copilot who
are evaluating their AI-assisted workflow quality

**Outline:**

1. **Hook:** GitHub Copilot Code Review (GA March 2026) reviews your PR. It is
   useful. But by the time your PR exists, your architecture has already been
   shaped.
2. **The workflow gap:** Copilot Review operates at the post-task stage. There
   is no tool in the standard workflow that operates at the pre-task stage —
   before the agent starts generating code.
3. **drift brief:** `drift brief --task "add payment integration"` analyzes the
   affected scope, identifies elevated signals, and returns concrete guardrails
   for the agent to follow. This runs before any code is written.
4. **drift nudge:** During the session, `drift nudge` via MCP gives directional
   feedback after each file edit — is the change improving or degrading
   structural coherence? Fast enough for inner-loop use.
5. **The combined workflow:**
   ```
   drift brief → agent task → drift nudge (during) → Copilot Review (on PR)
   ```
   Prevention at the start. Verification at the end.
6. **Call to action:** Add `drift mcp` to your Cursor or Claude Code config.
   Start with `drift brief` on your next agent task.

**Key claims (safe to publish):**
- `drift brief` returns UP TO 50 guardrails scoped to the task description
- `drift nudge` runs file-local signals in < 200ms for inner-loop use
- MCP server: 17 tools covering the full agent workflow

---

**Publication notes:**
- All articles reference [Comparison Hub](https://mick-gsk.github.io/drift/comparisons/)
  for citation-level accuracy
- Safe factual claims sourced from `docs-site/product/press-brand.md`
- Do not claim specific competitor precision/recall numbers without a link to
  their published benchmarks

The icon then appears on the pre-commit.ci page and in their search.
