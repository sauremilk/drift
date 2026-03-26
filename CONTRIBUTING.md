# Contributing to Drift

Thanks for your interest in contributing! Drift is under active development and welcomes bug fixes, new signals, and documentation improvements.

## Who this page is for

This page is for contributors and maintainers.

- If you want to try drift as a user, start in [README.md](README.md) or the docs quickstart instead of this governance-heavy path.
- If you are evaluating drift for adoption, review the example findings, trust material, and release status first.
- If you are ready to contribute code or docs, continue here.

The standards below stay intentionally strict because they protect result credibility, signal quality, and release hygiene.

## Quick start

```bash
git clone https://github.com/sauremilk/drift.git
cd drift
make install          # pip install -e ".[dev]" + git hooks
make check            # lint + typecheck + test + self-analysis
```

See [DEVELOPER.md](DEVELOPER.md) for the full developer guide (architecture, commands, conventions).

<details>
<summary>Without Make</summary>

```bash
pip install -e ".[dev]"
git config core.hooksPath .githooks
ruff check src/ tests/
python -m mypy src/drift
pytest -v --tb=short
```
</details>

## Good First Issues

New to the project? Look for issues labelled **[`good first issue`](https://github.com/sauremilk/drift/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)** — these are scoped to be completable in a few hours and have clear acceptance criteria.

**Examples of good first contributions:**

| Area | Difficulty | Example |
|---|---|---|
| False positive fix | Easy | Reduce noise in EDS for `__init__` methods |
| Documentation | Easy | Add configuration examples for monorepo setups |
| Test coverage | Easy | Add edge-case tests for empty repos / single-file projects |
| Signal improvement | Medium | Improve PFS fingerprint normalization for decorator variants |
| New output format | Medium | Add CSV output formatter |

## What to work on

Check the [open issues](https://github.com/sauremilk/drift/issues) for current priorities.

High-value contributions:

- **New detection signals** — see `src/drift/signals/base.py` for the interface
- **TypeScript support** — tree-sitter integration (see roadmap in README)
- **False positive fixes** — signal quality improvements are always welcome
- **Documentation** — usage examples, configuration how-tos
- **Benchmarks** — run drift on new open-source repos and report findings

## Adding a new signal

1. Create `src/drift/signals/your_signal.py` implementing `BaseSignal`
2. Decorate the class with `@register_signal` — auto-discovery handles the rest (no manual import in `analyzer.py` needed)
3. Add a weight entry in `src/drift/config.py` (default `0.0` until stable)
4. Write tests in `tests/test_your_signal.py` (TP + TN fixtures required)

Signals must be:

- **Deterministic** — same input always produces same output
- **LLM-free** — the core pipeline uses only AST analysis and statistics
- **Fast** — target < 500ms per 1 000 functions

## Code conventions

- Python 3.11+, type annotations everywhere
- `ruff check src/ tests/` must pass
- `pytest` must pass
- Private/worklog paths (for example `tagesplanung/`) must never be committed or pushed

## Public repo hygiene guard (required)

The repository enforces an additional remote guardrail via GitHub Actions:

- Workflow: `Repo Guard` (`.github/workflows/repo-guard.yml`)
- Rule source: `.github/repo-guard.blocklist`
- Check logic: `scripts/check_repo_hygiene.py`

This check is designed to prevent sensitive/local-only files from entering the public repository even if local hooks are bypassed (for example with `--no-verify`).

Recommended branch protection setup:

- Require status check: `Repo Guard / Blocked content check`
- Require pull request before merge
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
- [ ] No new module without an entry in README/STUDY.md
- [ ] New signal → own file in `signals/`, implements `BaseSignal`

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

1. **One primary claim:** The release can be summarized in one sentence and at most 3 to 5 bullets.
2. **One coherent change set:** The included changes belong to one user-facing theme or one tightly related batch.
	If there are multiple unrelated themes, split them into separate releases.
3. **SemVer is explicit:** The release is clearly classified as patch, minor, or major before tagging.
4. **Changelog is curated, not dumped:** The changelog groups changes by user impact (`Added`, `Changed`, `Fixed`) instead of mirroring raw commit history.
5. **Evidence is complete:** Any feature content in the release already satisfies the feature-evidence gate.
6. **Release state is reproducible:** Version bump, changelog entry, tag, and release notes all point to the same release scope.

The following are not allowed:

- catch-all releases that bundle multiple unrelated themes just because enough commits accumulated
- changelog entries that simply replay commit messages without curation
- retroactively moving changes between older releases and the new release without checking the actual tagged git state
- releasing feature work without tests and empirical artifacts

Default rule: when in doubt, release earlier and smaller.
Drift should prefer two clean releases over one overloaded release.

### GitHub Actions Major-Version-Tag

Because Drift is a GitHub Action (`uses: sauremilk/drift@v1`), there is one additional convention:
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
