# Drift — Developer Task Runner
# Usage: make help
#
# On Windows: use via Git Bash, WSL, or install GNU Make.
# All targets mirror the pre-push hook / CI pipeline steps.

.DEFAULT_GOAL := help

PYTHON   ?= python
PYTEST   ?= pytest
RUFF     ?= ruff
MYPY     ?= $(PYTHON) -m mypy

SRC      := src/
TESTS    := tests/

.PHONY: help install lint lint-fix typecheck test test-fast test-contract test-all coverage check self ci markdown-lint package-kpis-github-usage package-kpis-downloads package-kpis-real-public package-kpis-example clean

help:  ## Show all available commands
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Dev install (editable + all dev extras) and activate git hooks
	pip install -e ".[dev]"
	git config core.hooksPath .githooks
	@command -v pre-commit >/dev/null 2>&1 && pre-commit install --install-hooks || echo "  (pre-commit not found — skipping hook install)"

lint:  ## Run ruff linter
	$(RUFF) check $(SRC) $(TESTS)

lint-fix:  ## Run ruff with auto-fix
	$(RUFF) check --fix $(SRC) $(TESTS)

typecheck:  ## Run mypy type checker
	$(MYPY) src/drift

test:  ## Run tests (skip slow smoke tests)
	$(PYTEST) -v --tb=short --ignore=tests/test_smoke_real_repos.py

test-fast:  ## Fast unit tests — stop on first failure
	$(PYTEST) -v --tb=short -m "not slow" -x --ignore=tests/test_smoke_real_repos.py

test-contract:  ## SARIF/JSON contract tests only
	$(PYTEST) -v --tb=short -m contract

test-all:  ## All tests including slow smoke tests
	$(PYTEST) -v --tb=short

coverage:  ## Tests with coverage report
	$(PYTEST) -v --tb=short --cov=drift --cov-report=term-missing --ignore=tests/test_smoke_real_repos.py

check:  ## Run all checks: lint + typecheck + tests + self-analysis
	@echo ">>> [1/4] Lint..."
	@$(MAKE) --no-print-directory lint
	@echo ">>> [2/4] Type check..."
	@$(MAKE) --no-print-directory typecheck
	@echo ">>> [3/4] Tests + coverage..."
	@$(MAKE) --no-print-directory coverage
	@echo ">>> [4/4] Self-analysis..."
	@$(MAKE) --no-print-directory self
	@echo ">>> All checks passed."

markdown-lint:  ## Lint Markdown docs
	npx markdownlint-cli2

self:  ## Drift self-analysis
	drift analyze --repo . --format json > /dev/null

package-kpis-github-usage:  ## Derive usage events from public GitHub dependency declarations
	$(PYTHON) scripts/fetch_github_usage.py \
		--package drift-analyzer \
		--max-pages 5 \
		--output benchmark_results/package_kpis/github_usage_events.csv

package-kpis-downloads:  ## Fetch real monthly PyPI downloads to CSV
	$(PYTHON) scripts/fetch_pypistats.py \
		--package drift-analyzer \
		--months 12 \
		--output benchmark_results/package_kpis/pypi_downloads_monthly.csv

package-kpis-real-public:  ## Build KPI report from public GitHub usage + PyPI downloads
	$(MAKE) --no-print-directory package-kpis-github-usage
	$(MAKE) --no-print-directory package-kpis-downloads
	$(PYTHON) scripts/package_kpis.py \
		--package drift-analyzer \
		--usage-csv benchmark_results/package_kpis/github_usage_events.csv \
		--downloads-csv benchmark_results/package_kpis/pypi_downloads_monthly.csv \
		--thresholds-json examples/package-kpis/kpi-thresholds.json \
		--months 12 \
		--output benchmark_results/package_kpis/package_kpis_real.json

package-kpis-example:  ## Generate monthly package KPI example report JSON
	$(PYTHON) scripts/package_kpis.py \
		--package drift-analyzer \
		--usage-csv examples/package-kpis/usage.csv \
		--defects-csv examples/package-kpis/defects.csv \
		--currency-versions 1.4.1,1.4.0 \
		--thresholds-json examples/package-kpis/kpi-thresholds.json \
		--months 12 \
		--output benchmark_results/package_kpis_example.json

ci:  ## Replicate full CI pipeline locally
	$(PYTHON) scripts/check_version.py --check-semver
	$(MAKE) check

clean:  ## Remove caches and build artifacts
	rm -rf .drift-cache .pytest_cache .ruff_cache .mypy_cache htmlcov dist build
	rm -f .coverage out.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
