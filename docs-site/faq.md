# FAQ

## Who built this?

I'm [Mick Gottschalk](https://github.com/mick-gsk). I built drift as a solo open-source project because I couldn't find a tool that detects the structural problems AI coding tools leave behind. I use it on my own codebases every day.

## Is this a startup or a side project?

Neither — it's a focused open-source tool. No VC funding, no enterprise upsell, no cloud backend. I maintain it because I need it and because the problem is real.

## How can I reach the maintainer?

Open a [GitHub issue](https://github.com/mick-gsk/drift/issues) or start a [discussion](https://github.com/mick-gsk/drift/discussions). I read and respond to everything. False positive reports are especially welcome — they directly improve signal quality.

## Why should I trust a tool that's still in Beta?

Because I run it on this repository every day, the precision numbers are public and reproducible, and every false positive you report gets fixed. The Beta label reflects that some optional surfaces (TypeScript, embeddings) are still experimental — the core Python analysis is stable and tested against 15+ real-world repos.

## Is drift a bug finder or security scanner?

No. Drift is not positioned as a bug finder, a security scanner, or a type checker.

For those problems, use the dedicated tools already built for them.

## Why would a team use drift next to Ruff, Semgrep, or CodeQL?

Because those tools do not primarily model cross-file architectural coherence.

See [Drift vs Ruff](comparisons/drift-vs-ruff.md) and [Drift vs Semgrep and CodeQL](comparisons/drift-vs-semgrep-codeql.md).

## When should a team not use drift?

Avoid using drift as a first-day hard gate on tiny repositories or when the real need is bug detection, security review, or type-safety enforcement.

## How precise are drift's findings?

The conservative public benchmark claim on this site is 77% strict precision / 95% lenient on the historical v0.5 six-signal baseline (286 findings, 5 repositories, score-weighted sample, single-rater classification with 51 disputed cases).

Precision has not yet been fully revalidated for the current 24-signal composite model (19 scoring-active), so treat the 77%/95% figure as a historical reference point from the v0.5 six-signal baseline, not as a blanket claim for every signal or every repository. Several core signals have maintained stable precision since that study, but the full composite has not been re-benchmarked as a unit since ADR-039 expanded the scoring set.

See [Trust and Evidence](trust-evidence.md), [Benchmarking and Trust](benchmarking.md), and [STUDY.md](https://github.com/mick-gsk/drift/blob/main/docs/STUDY.md).

## How should a team introduce drift?

Start locally, then move to report-only CI, then gate only on `high` findings after reviewing real output.

See [Team Rollout](getting-started/team-rollout.md).

## Why does PyPI classify drift as Beta if some product areas are still experimental?

Because the current package metadata reflects the maturity of the primary Python path, not a claim that every optional surface is equally mature.

The core Python analysis and the CI/SARIF rollout path are the most stable parts of drift today, but TypeScript support remains experimental, embeddings-based parts are optional and experimental, and the benchmark methodology is still evolving.

See [Stability and Release Status](stability.md).

## How do I reduce false positives?

1. **Configure `path_overrides`** to exclude known-noisy paths (tests, migrations, generated code)
2. **Use `# drift:context deliberate-variant`** comments for intentional polymorphism
3. **Report FPs** via the [FP/FN template](https://github.com/mick-gsk/drift/issues/new?template=false_positive.md) — they directly improve signal quality

See [Troubleshooting](getting-started/troubleshooting.md).

## Does drift use an LLM in the detector pipeline?

No. The detector path is deterministic.

See [Trust and Evidence](trust-evidence.md) and [Benchmarking and Trust](benchmarking.md).

## What does a high drift score mean?

A high score (closer to 1.0) indicates more structural entropy — inconsistent patterns, boundary violations, or accumulated duplicates. It does not mean the code is broken or buggy.

Interpret score *changes* over time (`drift trend`), not isolated snapshots. A rising score after AI-assisted development often signals pattern fragmentation that should be reviewed.

See [Interpreting the Score](trust-evidence.md).

## What is the drift composite score?

A weighted aggregate of the 19 currently scoring-active signal scores that produces a single number between 0 and 1. Higher values indicate more structural erosion. Auto-calibration rebalances weights at runtime based on finding distribution.

See [Scoring Model](algorithms/scoring.md).

## What is drift?

Drift is a deterministic static analyzer for architectural erosion and cross-file coherence problems in Python repositories.

## What does drift detect?

Drift detects 24 signal families across structural, architectural, temporal, and security-by-default dimensions. 19 signals are currently scoring-active in the composite score: pattern fragmentation (PFS), architecture violations (AVS), mutant duplicates (MDS), explainability deficit (EDS), system misalignment (SMS), DIA, BEM, TPD, GCD, NBV, BAT, ECM, COD, CCC, FOE, MAZ, ISD, HSC, and PHR.

5 additional signals currently run in report-only mode pending validation or re-validation: TVS, TSA, CXS, CIR, and DCA.

See [Signal Reference](algorithms/signals.md).

## Can drift detect dependency cycles in Python?

Yes. The AVS signal detects circular dependencies (A→B→C→A) and upward imports that cross inferred or configured layer boundaries.

## Does drift support monorepos?

Yes. Drift analyzes any Python repository structure. For monorepos, you can use `--path` to restrict analysis to a subdirectory or configure `include`/`exclude` patterns in `drift.yaml`.

See [Monorepo Configuration Examples](getting-started/configuration.md#monorepo-configuration-examples) for copy-paste-ready setups covering single-package scans, multi-package shared config, and per-package policy overrides.

## How does drift compare to SonarQube, pylint, or Semgrep?

Drift complements those tools. Linters catch style violations, type checkers catch type errors, security scanners catch vulnerabilities. Drift catches cross-file architectural coherence problems that none of those tools model.

See [Comparisons](comparisons/index.md).

## How long does analysis take?

Typical runtime is 2–5 seconds on Python projects with up to a few hundred files. The Django study corpus (2,890 files, 31 k functions, full-clone default config) completes in about 36 seconds; a `src/`-scoped shallow-clone analysis of smaller repositories like FastAPI (664 files) finishes in about 13 seconds. Drift uses Python’s built-in `ast` module — no ML inference, no server, no network calls. See [Performance](reference/performance.md) for the full timing matrix.

For very large repositories (> 5,000 files), you can restrict analysis to a subdirectory with `--path src/` or cap file discovery via `thresholds.max_discovery_files` in `drift.yaml`.

## How do I ignore generated code or vendor directories?

Add `exclude` patterns to `drift.yaml`:

```yaml
exclude:
  - "**/generated/**"
  - "**/vendor/**"
  - "**/migrations/**"
```

Or use the CLI flag: `drift analyze --repo . --exclude "**/generated/**"`.

See [Configuration](getting-started/configuration.md).

## What is the difference between scoring signals and report-only signals?

**Scoring signals** (19) contribute to the composite drift score and severity.

**Report-only signals** (5) detect real patterns but are not yet included in the composite score. They appear in findings output tagged as `report_only: true`. Report-only signals graduate to scoring-active once they pass validation thresholds.

See [Signal Reference](algorithms/signals.md).

## Does drift need git history?

Git history is optional. Without it, temporal signals (TVS, ECM) are skipped automatically, and the remaining signals work normally. Shallow clones (`--depth 1`) also work — temporal signals are skipped with a warning.

For full temporal analysis, use `fetch-depth: 0` in CI or a full clone locally.

## Can I run drift on a single file or directory?

Yes. Use `--path` to restrict analysis:

```bash
drift analyze --repo . --path src/api/
```

This analyzes only the specified subtree while still resolving cross-file dependencies within it.

## Can drift work with Copilot, Cursor, or Claude?

Yes. Drift has a built-in MCP server (`drift mcp --serve`) that integrates with MCP-capable editors. It also provides `drift export-context` and `drift copilot-context` commands that generate anti-pattern rules for AI assistants.

For Cursor, see the dedicated **[Cursor MCP Setup Guide](guides/cursor-mcp-setup.md)** with step-by-step setup, tool catalog, and workflow examples.

See also [Integrations](integrations.md) and [Vibe-Coding Guide](https://github.com/mick-gsk/drift/tree/main/examples/vibe-coding).
