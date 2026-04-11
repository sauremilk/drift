# Signals Cheat Sheet

Quick reference for all drift signals.

★ = triggered especially often by AI-generated code  
`(R)` = report-only signal (not included in drift score)

---

## Scored Signals

| Abbr | Signal | Weight | What it flags | Fix time |
|------|--------|--------|--------------|----------|
| **PFS** ★ | Pattern Fragmentation | 0.16 | Same concept implemented multiple incompatible ways in one module | 30–90 min |
| **AVS** | Architecture Violation | 0.16 | Imports that skip layer boundaries; circular deps; blast-radius hubs | 1–4 h |
| **MDS** ★ | Mutant Duplicate | 0.13 | Near-identical functions (≥80% AST similarity) changed by copy-paste | 15–60 min |
| **EDS** ★ | Explainability Deficit | 0.09 | Complex functions (CC > 10) with no docstring, partial types, AI-attributed | 20–45 min |
| **SMS** ★ | System Misalignment | 0.08 | New code introduces deps/conventions not established in the module | 30–90 min |
| **BEM** | Broad Exception Monoculture | 0.04 | Every handler catches `Exception` / bare `except:` and swallows it | 15–30 min |
| **TPD** | Test Polarity Deficit | 0.04 | ≥ 5 tests but zero negative / exception / boundary tests | 30–60 min |
| **DIA** | Doc-Impl Drift | 0.04 | README/ADR claims that no longer match the actual import graph | 30–90 min |
| **NBV** | Naming Contract Violation | 0.04 | `validate_*` that never raises; `is_*` that doesn't return bool | 10–30 min |
| **GCD** | Guard Clause Deficit | 0.03 | Public functions skip input validation before business logic | 20–45 min |
| **BAT** ★ | Bypass Accumulation | 0.03 | `# noqa`, `# type: ignore`, TODO/HACK density > 5 % of LOC | 30–180 min |
| **ECM** | Exception Contract Drift | 0.03 | Exception profile changed across commits; callers silently broken | 30–90 min |
| **COD** | Cohesion Deficit | 0.01 | Module/class bundles unrelated responsibilities | 1–3 h |
| **CCC** | Co-Change Coupling | 0.005 | File pairs almost always changed together — hidden coupling | 30–90 min |

## Report-Only Signals

| Abbr | Signal | What it flags | Fix time |
|------|--------|--------------|----------|
| **TVS** (R) | Temporal Volatility | Files with z-score change frequency far above peers | 1–4 h |
| **TSA** (R) | TypeScript Architecture | Layer leaks and cycles in TS/JS code | 30–90 min |
| **CXS** (R) | Cognitive Complexity | Functions with excessive nesting depth | 30–90 min |
| **FOE** (R) | Fan-Out Explosion | Module imports far more than the repo median | 1–3 h |
| **CIR** (R) | Circular Import | Import cycles of any length | 30–90 min |
| **DCA** (R) | Dead Code Accumulation | Defined symbols never referenced elsewhere | 15–30 min |
| **MAZ** (R) | Missing Authorization | HTTP endpoints without auth check (CWE-862) | 15–30 min |
| **ISD** (R) | Insecure Default | `DEBUG=True`, `ALLOWED_HOSTS=['*']` etc. (CWE-1188) | 5–20 min |
| **HSC** (R) | Hardcoded Secret | Credentials or tokens in source code (CWE-798) | 5–15 min |
| **PHR** (R) | Phantom Reference | References to functions/modules that no longer exist | 15–30 min |

---

## Exploring a signal

```bash
drift explain PFS                    # description + example + fix hint
drift explain PFS --repo-context     # examples from your own codebase
drift explain --list                 # this table in the terminal
```

---

## Related signals

| If you see… | Also check… | Reason |
|-------------|-------------|--------|
| PFS | MDS, SMS | Fragmentation clusters with duplication and style drift |
| AVS | COD, CCC | Layer violations reveal cohesion and coupling problems |
| EDS | TPD, BEM | Explainability and test/error-handling quality move together |
| HSC | ISD, MAZ | Security signals cluster — fix all three at once |
| BEM | ECM, TPD | Exception handling issues compound each other |

---

## Score context by profile

| Profile | Typical first-run range | Healthy target |
|---------|------------------------|----------------|
| `vibe-coding` | 0.20–0.50 | < 0.35 |
| `default` | 0.25–0.55 | < 0.40 |
| `strict` | 0.30–0.65 | < 0.45 |

Run `drift setup` to activate the right profile for your project.
