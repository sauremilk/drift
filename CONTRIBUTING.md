# Contributing to Drift

Drift is built by a small team, but the hardest problems — false positives no one expected, edge cases from real codebases, explanations that finally click — come from people outside the core project. **Your perspective makes Drift more credible, not just bigger.**

You do not need to understand the whole analyzer to make a useful first contribution. A well-documented false positive can be more valuable than a new feature. A clearer explanation helps every future user. A single edge-case test can prevent a class of regressions.

This guide is structured so you can start small and grow into deeper work at your own pace. The standards are strict because they protect finding quality — but first-time contributors get guidance, not gatekeeping.

## Who this page is for

- **New here?** Start with [Your first contribution](#your-first-contribution) below.
- **Using Drift and got surprised?** That's valuable — see [how to report it](#where-to-ask-what).
- **Ready for deeper work?** Jump to [Contributor ladder](#contributor-ladder) or [Adding a new signal](#adding-a-new-signal).
- **Just exploring?** Try [README.md](README.md) or the [docs quickstart](docs-site/getting-started/quickstart.md) first.

## Quick start

```bash
git clone https://github.com/mick-gsk/drift.git
cd drift
make install          # pip install -e ".[dev]" + git hooks + pre-commit
make check            # lint + typecheck + test + self-analysis
```

`make install` does three things: installs drift in editable mode with all dev dependencies, activates git hooks that enforce code quality before push, and sets up pre-commit checks. The whole setup takes about 1–2 minutes.

**On Windows without Make** (or if you prefer manual setup):

```bash
pip install -e ".[dev]"
git config core.hooksPath .githooks
pre-commit install
```

Then validate with:

```bash
ruff check src/ tests/
python -m mypy src/drift
pytest -v --tb=short
```

See [DEVELOPER.md](DEVELOPER.md) for the full developer guide (architecture, commands, conventions).

Maintainers and repeat reviewers should also use:

- [docs/MAINTAINER_RUNBOOK.md](docs/MAINTAINER_RUNBOOK.md)
- [docs/REPOSITORY_GOVERNANCE.md](docs/REPOSITORY_GOVERNANCE.md)

## Your first contribution

First contribution? Welcome. Here's the fastest path:

1. Pick a scoped issue labelled [**good first issue**](https://github.com/mick-gsk/drift/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) — each one includes affected files, a clear definition of done, and a difficulty estimate
2. Follow [Quick start](#quick-start) above to set up locally
3. Run `make test-fast` before and after your change
4. Open a focused PR and explain what changed, why, and how you validated it

Unsure whether something is worth contributing? Open a [contribution proposal](https://github.com/mick-gsk/drift/issues/new?template=contribution_proposal.md) — we'll help you scope it. If Drift surprised you with an unexpected result, that is valuable feedback even without a code fix.

## Participate in community studies

Drift runs open empirical studies to validate signal precision, measure
actionability, and understand architectural erosion patterns. Participation
is a first-class contribution — you do not need to write code.

| Level | Time | What you do | Template |
|:---:|---|---|---|
| 1 | ~15 min | Run `drift analyze` on your own repo, rate findings | [Self-analysis](https://github.com/mick-gsk/drift/issues/new?template=study_self_analysis.md) |
| 2 | ~30 min | Classify a set of findings as TP / FP / Unclear | [Finding rating](https://github.com/mick-gsk/drift/issues/new?template=study_finding_rating.md) |
| 3 | 1–3 h | Analyze a repo for a specific study (security, debt, etc.) | [Repo benchmark](https://github.com/mick-gsk/drift/issues/new?template=study_repo_benchmark.md) |

Currently open studies are documented in [STUDY.md §15–§17](docs/STUDY.md).
All studies follow the quality criteria in [POLICY.md §13](POLICY.md).

## Where to ask what

Not sure where to go? Use this routing table:

| I want to… | Go here |
|---|---|
| Ask a usage question | [GitHub Discussions](https://github.com/mick-gsk/drift/discussions) |
| Report a false positive / false negative | [FP/FN template](https://github.com/mick-gsk/drift/issues/new?template=false_positive.md) |
| Report a bug | [Bug report template](https://github.com/mick-gsk/drift/issues/new?template=bug_report.md) |
| Suggest a feature or improvement | [Feature request template](https://github.com/mick-gsk/drift/issues/new?template=feature_request.md) |
| Propose a larger contribution before coding | [Contribution proposal](https://github.com/mick-gsk/drift/issues/new?template=contribution_proposal.md) |
| Submit a small docs/typo improvement | Open a PR directly — no issue needed |
| Report a security vulnerability | [SECURITY.md](SECURITY.md) — do not open a public issue |

## Contributor ladder

Drift contributions range from 15-minute improvements to multi-day signal work. Pick the level that fits your time and familiarity:

| Level | Type | Time | Examples | Requirements |
|:---:|---|---|---|---|
| 1 | Docs / typo / example | ~15 min | Fix a typo, clarify a config example | PR only |
| 2 | FP/FN report | ~30 min | Document an unexpected finding with reproduction steps | Issue with template |
| 3 | Edge-case test | ~1 hour | Test that `drift analyze` handles a monorepo or empty repo | PR with test |
| 4 | Finding explanation | ~1–2 hours | Improve a vague `reason` string to name the specific structural problem | PR with before/after |
| 5 | Signal logic change | ~2–4 hours | Reduce false positives in EDS for `__init__` methods | PR with TP+TN tests |
| 6 | New signal proposal | ~1–2 days | Propose and implement a new detection signal | Contribution proposal first |

## How you can help — contributor types

Drift needs different kinds of contributions, and many of the most impactful ones are not code:

| Role | What you do | Why it matters |
|---|---|---|
| **User** | Run Drift on your codebase and report surprising results | Real-world repos expose blind spots that synthetic tests miss |
| **Validator** | Submit reproducible FP/FN reports with minimal examples | Directly improves precision — the project's #1 quality metric |
| **Docs contributor** | Clarify explanations, add examples, improve onboarding | Makes findings actionable for everyone, not just experts |
| **Test contributor** | Add edge-case tests, ground-truth fixtures | Prevents regressions and builds the evidence base |
| **Signal contributor** | Improve detection logic, propose new signals | Extends what Drift can see |
| **Maintainer** | Review, prioritize, release | Keeps the project moving |

> **Real-world reproduction cases directly improve Drift's credibility.** You don't need to fix a problem to make a valuable contribution — clearly documenting it is often the harder and more important part.

Check the [open issues](https://github.com/mick-gsk/drift/issues) for current priorities and [ROADMAP.md](ROADMAP.md) for what the project needs most right now.

### High-value contributions

- **False positive fixes** — signal quality improvements are always welcome
- **Reproducible fixtures** — ground-truth cases that sharpen precision/recall
- **Finding explanations** — improve `reason` and `next_action` text so findings are actionable
- **Documentation** — per-signal examples, configuration how-tos
- **Benchmarks** — run drift on new open-source repos and report findings
- **New detection signals** — see `src/drift/signals/base.py` for the interface

## How we evaluate contributions

Drift follows a strict quality hierarchy ([POLICY.md §7](POLICY.md)).
Contributions are evaluated in this order of importance:

1. **Credibility** — does it make findings more trustworthy and reproducible?
2. **Signal precision** — does it reduce false positives or false negatives?
3. **Clarity** — does it make findings easier to understand and act on?
4. **Adoptability** — does it make drift easier to set up or integrate?
5. **Trend capability** — does it improve temporal or delta analysis?
6. **Comfort features** — additional formats, UI, convenience

A contribution that improves credibility is always prioritized over one that
adds a comfort feature — even if the feature is well-implemented.

### What we prefer

- Reproducible test fixtures (ground-truth cases with expected findings)
- Improved finding explanations with concrete next actions
- False-positive/false-negative reductions backed by tests
- Per-signal documentation with code examples
- Small, focused changes over broad refactors

### What we don't accept

PRs that only produce one of the following will be closed with an explanation:

- More output without better insight
- More complexity without measurable benefit
- More surface area without better analysis
- Features whose contribution to signal quality or credibility cannot be named

This is not about gatekeeping — it protects the project from well-intentioned
work that dilutes finding quality. When in doubt, open a
[contribution proposal](https://github.com/mick-gsk/drift/issues/new?template=contribution_proposal.md) first.

## Non-code contributions are first-class

Drift is an analysis tool — its credibility depends on evidence, not just code. These contributions are **equally valued and credited** in the changelog:

| Contribution | Why it's valuable | How to submit |
|---|---|---|
| FP/FN report with reproduction | Directly feeds precision improvement — the project's top priority | [FP/FN template](https://github.com/mick-gsk/drift/issues/new?template=false_positive.md) |
| Minimal reproduction repo | Lets maintainers debug edge cases without guessing | Link in an issue or PR |
| Benchmark on a new codebase | Expands the evidence base beyond the study corpus | `drift analyze --format json` output attached to an issue |
| Finding explanation improvement | Makes Drift actionable for non-experts | PR changing `reason`/`next_action` strings |
| Docs clarification | Reduces onboarding friction | PR directly — no issue needed |
| Config example for a specific setup | Helps teams with monorepos, generated code, etc. | PR or Discussion post |

## Our commitment to contributors

- **First response within 72 hours** on issues and PRs.
- **Rejections include a reason** referencing a specific quality criterion.
- **First-time contributors get guidance**, not just pass/fail. We'll help you scope your first PR if needed.
- If a PR needs changes, we explain what and why — not just "fix this".
- **First contributions are celebrated.** We credit contributors by name in the changelog.

If you don't hear back within 72 hours, ping the thread — it's a process failure, not a signal that your work isn't valued.

> **Drift is demanding, but not exclusive.** The standards exist to protect finding quality. They do not exist to filter people out. If you're unsure whether your idea fits, open a contribution proposal or ask in Discussions — we'd rather help you shape a contribution than have you walk away.

## Adding a new signal

1. Create `src/drift/signals/your_signal.py` implementing `BaseSignal`
2. Decorate the class with `@register_signal` — auto-discovery handles the rest (no manual import in `analyzer.py` needed)
3. Add a weight entry in `src/drift/config.py` (default `0.0` until stable)
4. Write tests in `tests/test_your_signal.py` (TP + TN fixtures required)

Signals must be:

- **Deterministic** — same input always produces same output
- **LLM-free** — the core pipeline uses only AST analysis and statistics
- **Fast** — target < 500ms per 1 000 functions

## Adding ground-truth fixtures

Every signal must have ground-truth fixtures in `tests/fixtures/ground_truth.py`.
These fixtures drive automated precision/recall measurement via `drift precision`.

### Fixture kinds

| Kind | Purpose | `should_detect` |
|------|---------|-----------------|
| `POSITIVE` | Clear true-positive — signal must fire | `True` |
| `NEGATIVE` | Clear true-negative — signal must not fire | `False` |
| `BOUNDARY` | Near detection threshold — tests edge behavior | either |
| `CONFOUNDER` | Looks like a TP but isn't — tests false-positive suppression | `False` |

### Minimum coverage per signal

| Kind | Required |
|------|----------|
| Positive (TP) | ≥ 2 |
| Negative (TN) | ≥ 2 |
| Boundary | ≥ 1 |
| Confounder | ≥ 1 |

No signal should ship without at least one TN fixture to prevent FP regressions.

### Workflow

1. Define a `GroundTruthFixture` in the signal's section of `ground_truth.py`
2. Add it to the `ALL_FIXTURES` list (or the `ALL_FIXTURES.extend(...)` block)
3. Run `drift precision --signal YOUR_SIGNAL` to verify detection
4. Run `pytest tests/test_precision_recall.py -k your_fixture_name` to validate

### Using `FileHistoryOverride`

Signals that depend on git history (TVS, SMS) need explicit history data.
Use `file_history_overrides` on the fixture:

```python
GroundTruthFixture(
    name="tvs_example",
    files={"app/hot.py": "def f(): pass"},
    expected=[...],
    file_history_overrides={
        "app/hot.py": FileHistoryOverride(
            total_commits=80,
            change_frequency_30d=25.0,
        ),
    },
)
```

Fields not set in the override use sensible defaults (see `precision.py:run_fixture`).

## Negative-Pattern Library

The **negative-pattern library** under `data/negative-patterns/` is a standalone contribution path — no Rust, no analyzer internals needed. You contribute labelled code patterns that drift should detect.

### What you contribute

- A `.py` file (or directory of `.py` files) containing a minimal, self-contained anti-pattern
- A `.json` metadata file describing the pattern (validated against `data/negative-patterns/schema.json`)

### Quick-start

1. Pick a signal from the [signal list](data/negative-patterns/README.md#current-signals-covered) (or propose one not yet covered)
2. Write a minimal `.py` file exhibiting the anti-pattern — no external imports, keep it short
3. Create a matching `.json` file following the schema:
   ```json
   {
     "id": "mutant_duplicate_004",
     "signal": "mutant_duplicate",
     "origin": "ai_generated",
     "model_hint": "gpt-4o",
     "pattern_class": "copy_paste_with_variation",
     "confirmed_problematic": true,
     "severity": "medium",
     "description": "AI-generated duplicate with cosmetic renaming only",
     "tp_confirmed": true,
     "added_by": "your-github-handle",
     "drift_version": "2.7.2"
   }
   ```
4. Validate locally:
   ```bash
   python scripts/validate_negative_patterns.py
   python scripts/check_negative_patterns.py
   ```
5. Open a PR — CI will verify schema conformance and detection

### Naming conventions

- Pattern IDs: `{signal}_{nnn}` (e.g. `mutant_duplicate_004`)
- Single-file: `patterns/{id}.py` + `patterns/{id}.json`
- Multi-file: `patterns/{id}/` directory with `{id}.json` + multiple `.py` files

See [data/negative-patterns/README.md](data/negative-patterns/README.md) for full details including schema documentation.

## Code conventions

- Python 3.11+, type annotations everywhere
- `ruff check src/ tests/` must pass
- `pytest` must pass
- Private/worklog paths (for example `tagesplanung/`) must never be committed or pushed

## Public repo hygiene guard (required)

The repository enforces an additional remote guardrail via GitHub Actions:

- Workflow: `Repo Guard` (`.github/workflows/repo-guard.yml`)
- Rule source: `.github/repo-guard.blocklist`
- Root allowlist: `.github/repo-root-allowlist`
- Check logic: `scripts/check_repo_hygiene.py`
- Placement policy: `docs/ROOT_POLICY.md`

This check is designed to prevent sensitive/local-only files from entering the public repository even if local hooks are bypassed (for example with `--no-verify`).

The guard also enforces a small tracked root surface. If you introduce a new top-level entry, you must either move it into an existing directory or update the root allowlist with a clear rationale.

Recommended branch protection setup:

- Require status check: `Repo Guard / Blocked content check`
- Require pull request before merge
- Require at least one approving review for `main`
- Require CODEOWNERS review for signal, scoring, ingestion, and test changes
- Disallow force pushes on protected branches

## Pre-Merge Checklist

Every PR should pass these checks before merge:

### Tests
- [ ] `pytest` passes (all fixtures, smoke tests)
- [ ] New signal logic includes TP + TN fixtures
- [ ] Mutation benchmark rerun when changing a signal
- [ ] For a new feature: empirical evidence attached (at least one benchmark/validation artifact under `benchmark_results/` or `audit_results/`)
- [ ] For a new feature: evidence-based PR summary included (dataset, baseline, result, reproduction command)

### Architecture
- [ ] `drift self` → score ≤ previous score + 0.010
- [ ] No new module without an entry in README and docs/STUDY.md
- [ ] New signal → own file in `signals/`, implements `BaseSignal`
- [ ] Signal/ingestion/output changes → at least one audit artifact updated (POLICY §18):
	- [ ] `audit_results/fmea_matrix.md` (FP + FN entry)
	- [ ] `audit_results/stride_threat_model.md` (trust boundary)
	- [ ] `audit_results/fault_trees.md` (FT-1/FT-2/FT-3 review)
	- [ ] `audit_results/risk_register.md` (risk entry or metric)

### Code Quality
- [ ] No new function >30 LOC without a docstring
- [ ] No direct DB/Git import outside `ingestion/`
- [ ] pre-commit hooks pass (`git config core.hooksPath .githooks` set):
	- [ ] `ruff check src/ tests/` passes
	- [ ] `mypy src/drift` passes
	- [ ] `pytest` passes

## Proactive Quality Loop (Required)

Drift does not treat quality only reactively through bug reports. For every release cycle:

1. **Risk Sweep:** Define at least 3 plausible "unknown unknown" failure classes
	(for example cache corruption, subprocess injection, empty-input scoring).
2. **Executable Proof:** Add at least one reproducible test
	(regression or property test) for each failure class.
3. **Gate Integration:** A new test must run in CI; an optional test without a gate does not count.
4. **Ratchet Instead of Plateau:** Coverage/typing gates may only improve or stay flat,
	never decline without a documented reason.

Goal: Each iteration should systematically reduce the amount of untested risk surface.

## Submitting a PR

1. Open an issue first for non-trivial changes (saves everyone time)
2. Keep PRs focused — one concern per PR
3. Add tests for new behaviour
4. Update the README if you add a feature
5. Verify `drift self` score stays within SLO (Δ ≤ +0.010)
6. For new features, include empirical evidence (benchmark/validation output + reproducible command)

## Release notes labeling convention (required)

To keep GitHub release notes consistently categorized, each PR must carry exactly one `release:*` label:

- `release:feature` for user-visible new capabilities
- `release:fix` for user-visible bug fixes
- `release:maintenance` for internal technical changes (refactor, CI, deps)
- `release:docs` for documentation-only user-facing updates
- `release:skip` for changes that should not appear in release notes

Team convention:

1. Apply one release label when opening the PR.
2. If scope changes, update the release label before merge.
3. Maintainers confirm the final release label during review.

## Feature Evidence Gate (Required)

For every PR that introduces a new feature (`feat:` commits), empirical evidence is mandatory.

Minimum acceptance criteria:

1. At least one behavioral test added or updated under `tests/`.
2. At least one empirical artifact added or updated under `benchmark_results/` or `audit_results/`.
3. A short evidence summary in the PR:
	- dataset/repo scope
	- baseline vs. new result
	- interpretation of impact (precision/noise/runtime)
	- exact command used for reproduction

Without these three elements, feature work is considered unverified and must not be merged.

## Versioning

Drift follows **Semantic Versioning (SemVer)**: `MAJOR.MINOR.PATCH`

| Type              | When                                             | Example             |
| ----------------- | ------------------------------------------------ | ------------------- |
| **PATCH** `x.x.↑` | Bug fix, no new feature, no breaking change      | `v1.1.0` → `v1.1.1` |
| **MINOR** `x.↑.0` | New feature, backward compatible                 | `v1.1.0` → `v1.2.0` |
| **MAJOR** `↑.0.0` | Breaking change, incompatible API change         | `v1.1.0` → `v2.0.0` |

### Release Discipline (Required)

Releases must stay small enough to communicate one coherent user-visible step.
This rule is binding.

A release is allowed only when all of the following are true:

1. **One primary claim:** The release can be summarized in one sentence and at most 5 curated bullets.
2. **One coherent change set:** The included changes belong to one user-facing theme or one tightly related batch.
	If there are multiple unrelated themes, split them into separate releases.
3. **SemVer is explicit:** The release is clearly classified as patch, minor, or major before tagging.
4. **Changelog is curated, not dumped:** The changelog groups changes by user impact (`Added`, `Changed`, `Fixed`) instead of mirroring raw commit history.
5. **Contributors are credited:** First-time contributors are acknowledged by name in the changelog entry (e.g., `- Improved AVS clarity (#42, thanks @contributor)`).
6. **Evidence is complete:** Any feature content in the release already satisfies the feature-evidence gate.
6. **Release state is reproducible:** Version bump, changelog entry, tag, and release notes all point to the same release scope.
7. **Release scope fits one sentence:** If you can't summarize the release in one sentence plus at most 5 curated bullets, split it.

The following are not allowed:

- catch-all releases that bundle multiple unrelated themes just because enough commits accumulated
- changelog entries that simply replay commit messages without curation
- retroactively moving changes between older releases and the new release without checking the actual tagged git state
- releasing feature work without tests and empirical artifacts

Default rule: when in doubt, release earlier and smaller.
Drift should prefer two clean releases over one overloaded release.
This rule is enforced by git hook, CI, and publish validation.

### Branch Protection (Required)

To make the release discipline non-bypassable on GitHub, the default branch
`main` must be protected with these minimum settings:

1. Require a pull request before merging
2. Require status checks to pass before merging
3. Include administrators
4. Do not allow force pushes

Required status checks:

- `Version format check`
- `test`
- `Blocked content check`

If these settings are missing, local hooks and CI remain advisory for anyone
who can push directly to `main`.

### GitHub Actions Major-Version-Tag

Because Drift is a GitHub Action (`uses: mick-gsk/drift@v1`), there is one additional convention:
the **major-version tag** (`v1`, `v2`) acts as a moving pointer. This means:

- Users reference `@v1` and automatically receive all minor/patch updates
- The `v1` tag is moved to the new commit after every minor/patch release
- For a **breaking change**, `v2` is created and `@v2` becomes the new tag

The CI/CD workflow (`publish.yml`) moves the major tag **automatically** after every
GitHub release. Manual intervention is not necessary, except for unscheduled hotfixes:

```bash
git tag -f v1 && git push -f origin v1
```

### Release Process

Each meaningful, coherent commit batch (feature, fix, configuration change) must get its own
versioned release so that the changelog stays clean and users can pin specific versions.

1. Bump the version in `pyproject.toml` (for example `1.1.0` → `1.1.1`)
2. Write the changelog entry with one short summary sentence plus curated `Added` / `Changed` / `Fixed` bullets
3. Verify the release scope against the actual tagged git history, not against memory or draft notes
4. Commit the release files: `git commit -m "chore: release v1.1.1"`
5. Create the tag: `git tag v1.1.1`
6. Push the tag: `git push origin v1.1.1`
7. Create the GitHub release from the tag → CI moves `v1` automatically

## Reporting issues

Use the [issue templates](.github/ISSUE_TEMPLATE/) — they help reproduce problems quickly.

## Code of Conduct

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) in all project spaces.

## License

By contributing you agree that your contributions will be licensed under the [MIT License](LICENSE).
