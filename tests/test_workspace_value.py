"""Tests for workspace-value benchmark infrastructure.

Validates signal-coverage-matrix generation, corpus integrity,
and agent-loop benchmark scenarios.
"""

from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.performance

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
BENCHMARKS_CORPUS = ROOT / "benchmarks" / "corpus"
MANIFEST_PATH = BENCHMARKS_CORPUS / "manifest.json"
MATRIX_SCRIPT = ROOT / "scripts" / "signal_coverage_matrix.py"


def _load_script(name: str, path: Path) -> types.ModuleType:
    """Load a script as a module."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Signal Coverage Matrix ────────────────────────────────────────────────


class TestSignalCoverageMatrix:
    """Tests for scripts/signal_coverage_matrix.py."""

    @pytest.fixture(scope="class")
    def matrix_mod(self) -> types.ModuleType:
        return _load_script("signal_coverage_matrix", MATRIX_SCRIPT)

    def test_build_matrix_returns_valid_structure(self, matrix_mod):
        """build_matrix() returns dict with required keys."""
        data = matrix_mod.build_matrix()
        assert "milestones" in data
        assert "signals" in data
        assert "matrix" in data
        assert "introduced_in" in data
        assert "totals" in data
        assert "current_total" in data

    def test_baseline_version_has_7_signals(self, matrix_mod):
        """v0.5.0 should have exactly 7 signals."""
        data = matrix_mod.build_matrix()
        assert data["totals"]["v0.5.0"] == 7

    def test_latest_version_has_at_least_20_signals(self, matrix_mod):
        """Latest milestone should have >= 20 signals."""
        data = matrix_mod.build_matrix()
        assert data["current_total"] >= 20

    def test_all_signals_have_introduction_version(self, matrix_mod):
        """Every signal must have an introduction version."""
        data = matrix_mod.build_matrix()
        for sig in data["signals"]:
            assert sig in data["introduced_in"], f"{sig} missing introduction"

    def test_markdown_table_renders(self, matrix_mod):
        """render_markdown_table() should produce non-empty output."""
        data = matrix_mod.build_matrix()
        table = matrix_mod.render_markdown_table(data)
        assert "PFS" in table
        assert "v0.5.0" in table
        assert "✓" in table


# ── Benchmark Corpus Integrity ────────────────────────────────────────────


class TestBenchmarkCorpus:
    """Validate the static benchmark corpus."""

    def test_manifest_exists(self):
        """manifest.json must exist."""
        assert MANIFEST_PATH.exists()

    def test_manifest_valid_json(self):
        """manifest.json must be valid JSON."""
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assert "expectations" in data
        assert "total_expected" in data

    def test_manifest_expectations_sum(self):
        """Total expected must match sum of per-signal expectations."""
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        expected_sum = sum(data["expectations"].values())
        assert data["total_expected"] == expected_sum

    def test_corpus_has_python_files(self):
        """Corpus should contain Python source files."""
        py_files = list(BENCHMARKS_CORPUS.rglob("*.py"))
        assert len(py_files) >= 10, f"Only {len(py_files)} .py files found"

    def test_corpus_has_readme(self):
        """Corpus should have a README for DIA detection."""
        readme = BENCHMARKS_CORPUS / "README.md"
        assert readme.exists()
        content = readme.read_text(encoding="utf-8")
        # DIA target: references non-existent directories.
        assert "views" in content.lower() or "middleware" in content.lower()

    @pytest.mark.parametrize(
        "path",
        [
            "src/myapp/service_a.py",  # MDS
            "src/myapp/service_b.py",  # MDS
            "src/myapp/handler_v1.py",  # MDS
            "src/myapp/handler_v2.py",  # MDS
            "src/myapp/handlers/auth.py",  # PFS
            "src/myapp/handlers/orders.py",  # PFS
            "src/myapp/handlers/payments.py",  # PFS
            "src/myapp/handlers/shipping.py",  # PFS
            "src/myapp/models/enriched.py",  # AVS
            "src/myapp/utils/helpers.py",  # AVS
            "src/myapp/outlier_module.py",  # SMS
            "src/myapp/connectors/db.py",  # BEM
            "src/myapp/processors/pricing.py",  # EDS
            "src/myapp/processors/transform.py",  # EDS
            "src/myapp/processors/validator.py",  # GCD
            "tests/test_api.py",  # TPD
            "src/myapp/utils/naming.py",  # NBV
        ],
    )
    def test_corpus_file_exists(self, path):
        """Each expected corpus file must exist."""
        assert (BENCHMARKS_CORPUS / path).exists(), f"Missing: {path}"

    def test_mds_duplicates_are_identical(self):
        """service_a.py and service_b.py should have identical functions."""
        a = (BENCHMARKS_CORPUS / "src/myapp/service_a.py").read_text()
        b = (BENCHMARKS_CORPUS / "src/myapp/service_b.py").read_text()
        # Extract function bodies (skip module docstring).
        a_funcs = [
            line for line in a.splitlines() if line.startswith("def ") or line.startswith("    ")
        ]
        b_funcs = [
            line for line in b.splitlines() if line.startswith("def ") or line.startswith("    ")
        ]
        assert a_funcs == b_funcs


# ── Agent-Loop Benchmark (smoke) ──────────────────────────────────────────


class TestAgentLoopBenchmark:
    """Smoke tests for agent-loop benchmark scenarios."""

    @pytest.fixture(scope="class")
    def workspace(self, tmp_path_factory):
        """Create a minimal workspace from corpus for API testing."""
        import shutil

        ws = tmp_path_factory.mktemp("agent_loop_ws") / "ws"
        shutil.copytree(BENCHMARKS_CORPUS, ws)
        # Init git.
        import os
        import subprocess

        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_COMMITTER_NAME": "test",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_EMAIL": "t@t",
        }
        subprocess.run(
            ["git", "init"],
            cwd=str(ws),
            capture_output=True,
            env=env,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=str(ws),
            capture_output=True,
            env=env,
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(ws),
            capture_output=True,
            env=env,
        )
        return ws

    def test_scan_finds_patterns(self, workspace):
        """scan() on corpus should find multiple findings."""
        from drift.api import scan

        result = scan(path=str(workspace), max_findings=50)
        assert result["drift_score"] > 0
        assert len(result.get("findings", [])) > 0

    def test_nudge_returns_decision(self, workspace):
        """nudge() should return safe_to_commit boolean."""
        from drift.api import nudge

        result = nudge(path=str(workspace))
        assert "safe_to_commit" in result
        assert isinstance(result["safe_to_commit"], bool)

    def test_fix_plan_returns_result(self, workspace):
        """fix_plan() should return a result with drift_score."""
        from drift.api import fix_plan

        result = fix_plan(path=str(workspace), max_tasks=5)
        assert "drift_score" in result
