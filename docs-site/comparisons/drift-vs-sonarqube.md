# Drift vs SonarQube

SonarQube and drift address different layers of code quality. The right framing
is not "which one" but "which question each one answers".

## Short answer

SonarQube answers: "Does this code have security vulnerabilities, code smells,
or policy violations?"

Drift answers: "Is this codebase slowly becoming harder to reason about
structurally — and is that trend accelerating?"

## Scope comparison

SonarQube is a general-purpose code quality platform. It covers security
vulnerability detection (SAST), code smells, style issues, test coverage
integration, and compliance policies across 25+ languages. It is the right
choice for any team that needs security governance or enterprise compliance.

Drift is a structural coherence analyzer focused on AI-generated code. It
detects architecture erosion that passes all linters, tests, and security
scanners: the same problem solved four different ways, database logic leaking
into the API layer, near-duplicate scaffolding accumulating silently. Drift
is the right choice for teams that need to know whether their codebase is
fragmenting structurally — not whether it has known vulnerability patterns.

## What SonarQube does not cover

These are first-class drift signals with no equivalent in SonarQube:

| Signal | Abbrev | What it finds |
|---|---|---|
| Pattern Fragmentation | PFS | N different implementations of the same concept in one module |
| Mutant Duplicate | MDS | Near-identical functions accumulating across files (AST-level, not text) |
| System Misalignment | SMS | Code that introduces patterns foreign to its target module |
| Temporal Volatility | TVS | Files accumulating churn from too many authors too fast |
| Co-Change Coupling | CCC | Files that change together despite living in separate modules |
| Test Polarity Deficit | TPD | Test suites that test happy-path only, no adversarial cases |
| Bayesian calibration | — | Per-repo signal weights that adapt to observed repair outcomes |

None of these are in SonarQube's design scope. They require cross-file pattern
comparison, git history analysis, or AST-structural similarity — not rule-based
single-file analysis.

## What drift does not cover

Drift has no security-first signals. For security, SonarQube (or Semgrep, CodeQL)
is the right tool:

- SQL injection, XSS, SSRF detection
- Secret detection (drift has a basic hardcoded-secret signal, but not exhaustive)
- Dependency vulnerability analysis
- Compliance policies (OWASP, CWE mappings at enterprise scale)
- 25+ language support

## Setup comparison

| Dimension | SonarQube | Drift |
|---|---|---|
| Setup | Server required (SonarQube Server or SonarCloud) | `pip install drift-analyzer` |
| Config | Project key, token, sonar-project.properties | Optional `drift.yaml` (zero-config works) |
| First run | Minutes to hours | `drift analyze --repo .` in seconds |
| CI integration | sonarqube-scan GitHub Action | `uses: mick-gsk/drift@v2` |
| Output formats | Web UI, PR decoration | Rich terminal, JSON, SARIF, JUnit, CSV, markdown |
| Deterministic | Yes | Yes |
| LLM in pipeline | No | No |

## MCP integration comparison

Both SonarQube (since 2026) and drift have MCP servers for AI coding assistants.

SonarQube's MCP server exposes existing analysis results and allows agents to
query findings from completed scans.

Drift's MCP server has 17 tools across the full agent workflow:
- `drift_brief` — pre-task guardrails before any code is generated
- `drift_nudge` — fast directional feedback after each file edit (< 200ms)
- `drift_fix_plan` — prioritized repair tasks with constraints and verification plans
- `drift_session_start/end` — stateful multi-task sessions with autopilot
- `drift_shadow_verify` — speculative fix verification without committing

The scope difference applies here too: SonarQube's MCP helps agents avoid
known-bad patterns. Drift's MCP helps agents avoid architectural fragmentation.

## Recommended combined use

```
SonarQube or Semgrep:  security + policy + enterprise compliance
drift:                 structural coherence + temporal signals + AI-specific erosion
```

These tools measure different things and fail in different directions. Both
can be active in the same CI pipeline without conflict — drift outputs SARIF,
which integrates natively with GitHub Code Scanning alongside SonarQube and
CodeQL findings.

## Where to go next

- [CI Architecture Checks with SARIF](../use-cases/ci-architecture-checks-sarif.md)
- [Drift vs Semgrep and CodeQL](drift-vs-semgrep-codeql.md)
- [Trust and Evidence](../trust-evidence.md)
- [Case Studies](../case-studies/index.md)
