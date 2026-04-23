# Test Suite — Navigation Guide

The `tests/` directory contains ~370 test files. This guide explains the naming
conventions so contributors can find and add tests efficiently.

## Naming Conventions

| Pattern | What it covers | Example |
|---|---|---|
| `test_<module>.py` | Unit test for a specific module | `test_scoring_engine.py` |
| `test_<module>_extra.py` / `test_<module>_extended.py` | Additional cases for a module (edge cases, error paths) | `test_scoring_engine_extra.py` |
| `test_issue_NNN_*.py` | Regression test for a specific GitHub issue | `test_issue_301_eds_qa_lab_mock_server.py` |
| `test_dx_*.py` | Developer-experience / CLI ergonomics tests | `test_dx_features.py` |
| `test_smoke_*.py` | Smoke tests against real repos (slow, excluded from quick runs) | `test_smoke_real_repos.py` |
| `test_precision_recall.py` | Signal quality gate (precision/recall thresholds) | — |
| `test_ablation.py` | Signal ablation study | — |

## Test Categories

### Unit Tests
Cover individual modules in `src/drift/`. Run with:
```bash
pytest tests/ -m "not slow" --ignore=tests/test_smoke_real_repos.py -q
```

### Regression Tests (`test_issue_NNN_*`)
Each file corresponds to a GitHub issue and ensures the reported bug stays fixed.
When filing a new fix, add a `test_issue_<NNN>_<short_description>.py` file.

### Slow / Integration Tests
Marked with `@pytest.mark.slow` or in `test_smoke_real_repos.py`. Run explicitly:
```bash
pytest tests/test_smoke_real_repos.py -v
pytest tests/ -m slow -v
```

### Fixtures
Fixture data lives in `tests/fixtures/`. Sub-directories are named after the
TypeScript/JS scenario they represent (e.g. `tsjs_barrel_resolution/`).

## Quick Test Run
```bash
# Fast (no smoke, no slow):
make check   # runs lint + typecheck + quick pytest

# Or directly:
pytest tests/ --ignore=tests/test_smoke_real_repos.py -m "not slow" -q -n auto
```

## Adding Tests
- **New signal**: add `test_<signal_name>.py` (unit) + a fixture in `tests/fixtures/` if file-based input is needed.
- **Bug fix**: add `test_issue_<NNN>_<short_description>.py` where NNN is the GitHub issue number.
- **Edge case for existing module**: add to the existing `test_<module>_extra.py` or create one if it doesn't exist.
- **Do not** add files named `test_coverage_boost_*.py` or similar metric-optimizing names — name by module/behavior instead.
