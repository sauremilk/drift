# Contributing to Drift

Thanks for your interest in contributing! Drift is under active development and welcomes bug fixes, new signals, and documentation improvements.

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

## Pre-Merge Checklist

Every PR should pass these checks before merge:

### Tests
- [ ] `pytest` grün (alle Fixtures, Smoke Tests)
- [ ] Neue Signal-Logik hat TP + TN Fixture
- [ ] Mutations-Benchmark bei Signal-Änderung neu ausgeführt
- [ ] Bei neuem Feature: empirischer Nachweis beigefügt (mindestens 1 Benchmark/Validation-Artefakt unter `benchmark_results/` oder `audit_results/`)
- [ ] Bei neuem Feature: evidenzbasierte Zusammenfassung in PR (Datensatz, Baseline, Ergebnis, Reproduktionsbefehl)

### Architektur
- [ ] `drift self` → Score ≤ vorheriger Score + 0.010
- [ ] Kein neues Modul ohne Eintrag in README/STUDY.md
- [ ] Neues Signal → eigene Datei in `signals/`, implementiert `BaseSignal`

### Code-Qualität
- [ ] Keine neue Funktion >30 LOC ohne Docstring
- [ ] Kein direkter DB/Git-Import außerhalb von `ingestion/`
- [ ] pre-commit hooks laufen durch (`git config core.hooksPath .githooks` gesetzt):
	- [ ] `ruff check src/ tests/` grün
	- [ ] `mypy src/drift` grün
	- [ ] `pytest` grün

## Proactive Quality Loop (Required)

Drift behandelt Qualität nicht nur reaktiv über Bug-Reports. Für jede Release-Runde gilt:

1. **Risk Sweep:** Definiere mindestens 3 plausible "unknown unknown"-Fehlerklassen
	(z. B. Cache-Korruption, subprocess-Injection, Empty-Input-Scoring).
2. **Executable Proof:** Für jede Fehlerklasse mindestens einen reproduzierbaren Test
	(Regression oder Property-Test) hinzufügen.
3. **Gate Integration:** Neuer Test muss in CI laufen; optionaler Test ohne Gate zählt nicht.
4. **Ratchet statt Plateau:** Coverage/Typing-Gates dürfen nur steigen oder gleich bleiben,
	nie absinken ohne dokumentierten Grund.

Ziel: Jede Iteration reduziert die Menge ungetesteter Risikoflächen systematisch.

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

| Typ               | Wann                                             | Beispiel            |
| ----------------- | ------------------------------------------------ | ------------------- |
| **PATCH** `x.x.↑` | Bugfix, kein neues Feature, kein Breaking Change | `v1.1.0` → `v1.1.1` |
| **MINOR** `x.↑.0` | Neues Feature, rückwärtskompatibel               | `v1.1.0` → `v1.2.0` |
| **MAJOR** `↑.0.0` | Breaking Change, inkompatible API-Änderung       | `v1.1.0` → `v2.0.0` |

### GitHub Actions Major-Version-Tag

Da Drift eine GitHub Action ist (`uses: sauremilk/drift@v1`), gibt es eine zusätzliche Konvention:
den **Major-Version-Tag** (`v1`, `v2`) als beweglichen Zeiger. Das bedeutet:

- Nutzer referenzieren `@v1` und bekommen automatisch alle Minor/Patch-Updates
- Der `v1`-Tag wird nach jedem Minor/Patch-Release auf den neuen Commit verschoben
- Bei einem **Breaking Change** wird `v2` erstellt und `@v2` zum neuen Tag

Der CI/CD-Workflow (`publish.yml`) verschiebt den Major-Tag **automatisch** nach jedem
GitHub-Release. Manuell ist das nicht nötig – außer bei außerplanmäßigen Hotfixes:

```bash
git tag -f v1 && git push -f origin v1
```

### Release-Prozess

Jeder sinnvolle Commit-Batch (Feature, Fix, Konfigurationsänderung) sollte einen eigenen
versionierten Release bekommen, damit das Changelog sauber bleibt und Nutzer auf bestimmte
Versionen pinnen können.

1. Version in `pyproject.toml` erhöhen (z. B. `1.1.0` → `1.1.1`)
2. Commit: `git commit -m "chore: bump version to v1.1.1"`
3. Tag erstellen: `git tag v1.1.1`
4. Push tag: `git push origin v1.1.1`
5. GitHub Release aus dem Tag erstellen → CI verschiebt `v1` automatisch

## Reporting issues

Use the [issue templates](.github/ISSUE_TEMPLATE/) — they help reproduce problems quickly.

## Code of Conduct

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) in all project spaces.

## License

By contributing you agree that your contributions will be licensed under the [MIT License](LICENSE).
