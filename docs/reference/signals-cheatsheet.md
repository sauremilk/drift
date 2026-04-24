# Signals Cheat Sheet

Quick reference for all drift signals — abbreviation, what it means, and how to fix it.

★ = triggered especially often by AI-generated code
`(R)` = report-only (not scored, always listed)

---

## Scored Signals (affect drift score)

| Abbr | Signal | Weight | What it flags | Fix time |
|------|--------|--------|--------------|----------|
| **PFS** ★ | Pattern Fragmentation | 0.16 | Same concept implemented multiple incompatible ways in one module | 30–90 min |
| **AVS** | Architecture Violation | 0.16 | Imports that skip layer boundaries; circular deps; blast-radius hubs | 1–4 h |
| **MDS** ★ | Mutant Duplicate | 0.13 | Near-identical functions (≥80% AST similarity) diverged by copy-paste | 15–60 min |
| **EDS** ★ | Explainability Deficit | 0.09 | Complex functions (CC>10) with no docstring, no types, AI-attributed | 20–45 min |
| **SMS** ★ | System Misalignment | 0.08 | New code introduces deps/conventions not established in the module | 30–90 min |
| **BEM** | Broad Exception Monoculture | 0.04 | Every handler catches `Exception` or bare `except:` and swallows it | 15–30 min |
| **TPD** | Test Polarity Deficit | 0.04 | Test suite has ≥5 tests but zero negative/exception/boundary tests | 30–60 min |
| **DIA** | Doc-Impl Drift | 0.04 | README/ADR claims that no longer match the actual import graph | 30–90 min |
| **NBV** | Naming Contract Violation | 0.04 | `validate_*` that never raises; `is_*` that doesn't return bool | 10–30 min |
| **GCD** | Guard Clause Deficit | 0.03 | Public functions skip input validation before business logic | 20–45 min |
| **BAT** ★ | Bypass Accumulation | 0.03 | `# noqa`, `# type: ignore`, TODO/HACK density > 5% of LOC | 30–180 min |
| **ECM** | Exception Contract Drift | 0.03 | Exception profile changed across commits; callers silently broken | 30–90 min |
| **COD** | Cohesion Deficit | 0.01 | Module/class bundles unrelated responsibilities (kitchen-sink) | 1–3 h |
| **CCC** | Co-Change Coupling | 0.005 | File pairs almost always changed together — hidden coupling | 30–90 min |
| **FOE** | Fan-Out Explosion | 0.005 | Module imports far more than the repo median | 1–3 h |
| **MAZ** | Missing Authorization | 0.02 | HTTP endpoints without auth check (CWE-862) | 15–30 min |
| **ISD** | Insecure Default | 0.01 | `DEBUG=True`, `ALLOWED_HOSTS=['*']`, etc. (CWE-1188) | 5–20 min |
| **HSC** | Hardcoded Secret | 0.01 | Credentials or tokens in source code (CWE-798) | 5–15 min |
| **PHR** | Phantom Reference | 0.02 | References to functions/modules that no longer exist | 15–30 min |

## Report-Only Signals `(R)`

| Abbr | Signal | What it flags | Fix time |
|------|--------|--------------|----------|
| **TVS** (R) | Temporal Volatility | Files changed far more often than peers (z-score anomaly) | 1–4 h |
| **TSA** (R) | TypeScript Architecture | Layer leaks and cycles in TS/JS code | 30–90 min |
| **CXS** (R) | Cognitive Complexity | Functions with excessive nesting depth | 30–90 min |
| **CIR** (R) | Circular Import | Import cycles of any length | 30–90 min |
| **DCA** (R) | Dead Code Accumulation | Defined symbols never referenced elsewhere | 15–30 min |

---

## How to explore a signal

```bash
drift explain PFS                   # full description + example + fix hint
drift explain PFS --repo-context    # examples from your own code
drift explain --list                # this table (in terminal)
```

---

## Signal relationships

| If you see... | Also check... | Why |
|--------------|--------------|-----|
| PFS | MDS, SMS | Fragmentation often co-occurs with duplication and style drift |
| AVS | COD, CCC | Layer violations often reveal coupling/cohesion problems |
| EDS | TPD, BEM | Explainability and test/error-handling quality tend to move together |
| HSC | ISD, MAZ | Security signals cluster — fix all three at once |
| BEM | ECM, TPD | Exception handling issues compound each other |

---

## Score interpretation by profile

| Profile | Typical first-run range | Score to aim for |
|---------|------------------------|-----------------|
| `vibe-coding` | 0.20–0.50 | < 0.35 |
| `default` | 0.25–0.55 | < 0.40 |
| `strict` | 0.30–0.65 | < 0.45 |

Run `drift setup` to pick the right profile for your project.
