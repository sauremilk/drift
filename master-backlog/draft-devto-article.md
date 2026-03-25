# Detecting Architectural Erosion in Python Projects with drift

*Draft for dev.to / Hashnode — based on verified data from STUDY.md and benchmark_results/*

---

AI coding assistants are fast. They pass tests. They get approved in review.
But they optimize for one thing: the immediate prompt context.

They don't know your architecture. They don't know you already have a
`handle_auth_error()` function. They don't know that `src/db/` shouldn't import
from `src/api/`.

The result is a slow, invisible rot. Not bugs — erosion. Your codebase still
works, but it resists change more every week.

## What architectural drift looks like

Here's what drift found when run on real-world open-source repositories
(default configuration, no tuning):

| Repository | Files | Drift Score | Severity | Findings |
|---|---:|---:|---|---:|
| Django | 2 890 | 0.596 | MEDIUM | 969 |
| FastAPI | 664 | 0.624 | HIGH | 360 |
| Pydantic | 403 | 0.577 | MEDIUM | 283 |
| Celery | 371 | 0.578 | MEDIUM | 282 |
| Flask | 65 | 0.358 | LOW | 18 |

These aren't quality judgments — they're coherence signals. A higher score means
more structural fragmentation, not "worse code."

## The 6 signals

Drift measures six families of architectural erosion:

**1. Pattern Fragmentation (PFS)** — Same concern implemented N different ways
in the same module. Example: error handling done with `try/except`, `if/else`,
early returns, and custom exceptions — all in the same package.

**2. Architecture Violations (AVS)** — Imports crossing layer boundaries.
Database models importing from the API layer, API routes reaching into
infrastructure modules.

**3. Mutant Duplicates (MDS)** — Near-identical functions that diverged after
copy-paste. AI tools are particularly prone to this: they generate a new
validator instead of finding the existing one.

**4. Explainability Deficit (EDS)** — Complex functions (high parameter count,
deep nesting) without documentation or type annotations.

**5. Temporal Volatility (TVS)** — Files changed by too many authors too fast.
High churn correlates with unclear ownership and structure.

**6. System Misalignment (SMS)** — Modules whose dependency patterns diverge
from the project norm. Recently introduced code that doesn't fit.

## What makes drift different

**Deterministic.** No LLM in the detection pipeline. The same input always
produces the same output. Reproducible in CI, reproducible in review.

**Composite score as a KPI.** The six signals are combined into a single score
(0–1) designed for time-series tracking. Run weekly, observe the trend.

**Zero infrastructure.** CLI tool. No server, no database, no cloud account.
`pip install drift-analyzer && drift analyze --repo .`

**Precision-validated.** 97.3% strict precision on 263 ground-truth-labeled
findings across 15 repositories. All false positives came from a single signal
(DIA) that carries zero scoring weight.

## A concrete example

Running drift on a codebase with AI-generated Celery task files revealed
6 identical copies of the same `_run_async()` function across separate task
modules. Each was generated independently by an AI assistant that lacked
cross-file context.

The fix — extracting the function into `tasks/utils.py` — took 2 minutes.
Finding it without drift would have required a manual codebase audit.

## How to try it

```bash
pip install drift-analyzer   # Python 3.11+
drift analyze --repo .
```

For CI integration:

```yaml
- uses: sauremilk/drift@v1
  with:
    fail-on: none           # report-only to start
    upload-sarif: "true"    # findings as PR annotations
```

## What drift is not

- Not a bug finder. Use your test suite.
- Not a security scanner. Use Semgrep or CodeQL.
- Not a type checker. Use mypy.
- Not a replacement for code review judgment.

Drift is the coherence layer between your linter and your architecture
documentation. It catches the structural erosion that passes every other check.

---

**Repository:** [github.com/sauremilk/drift](https://github.com/sauremilk/drift)
**Package:** [pypi.org/project/drift-analyzer](https://pypi.org/project/drift-analyzer/)
**Study:** [STUDY.md — 15-repository benchmark](https://github.com/sauremilk/drift/blob/master/STUDY.md)
**License:** MIT
