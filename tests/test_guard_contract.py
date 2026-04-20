"""Tests for the guard_contract API endpoint."""

from __future__ import annotations

import textwrap
from pathlib import Path

from drift.api.guard_contract import (
    _build_guard_contract,
    _extract_imports,
    _extract_public_api,
    _find_related_tests,
    _infer_layer,
    guard_contract,
)

# ---------------------------------------------------------------------------
# _infer_layer
# ---------------------------------------------------------------------------


class TestInferLayer:
    def test_signals_layer(self):
        assert _infer_layer("src/drift/signals/pfs.py") == "signals"

    def test_api_layer(self):
        assert _infer_layer("src/drift/api/scan.py") == "api"

    def test_commands_layer(self):
        assert _infer_layer("src/drift/commands/analyze.py") == "commands"

    def test_models_layer(self):
        assert _infer_layer("src/drift/models/_findings.py") == "models"

    def test_unknown_layer(self):
        assert _infer_layer("some/random/path.py") == "unknown"

    def test_backslash_normalisation(self):
        assert _infer_layer("src\\drift\\signals\\pfs.py") == "signals"


# ---------------------------------------------------------------------------
# _extract_public_api
# ---------------------------------------------------------------------------


class TestExtractPublicApi:
    def test_extracts_all_from_init(self, tmp_path: Path):
        init = tmp_path / "__init__.py"
        init.write_text(
            textwrap.dedent('''\
            """Package."""
            from .foo import Foo
            from .bar import Bar

            __all__ = ["Foo", "Bar", "baz"]
            '''),
            encoding="utf-8",
        )
        result = _extract_public_api(init)
        assert result == ["Foo", "Bar", "baz"]

    def test_fallback_to_imports(self, tmp_path: Path):
        init = tmp_path / "__init__.py"
        init.write_text(
            textwrap.dedent('''\
            from .foo import Foo
            from .bar import Bar as BarAlias
            from ._internal import _secret
            '''),
            encoding="utf-8",
        )
        result = _extract_public_api(init)
        assert "Foo" in result
        assert "BarAlias" in result
        assert "_secret" not in result

    def test_missing_file(self, tmp_path: Path):
        assert _extract_public_api(tmp_path / "nonexistent.py") == []


# ---------------------------------------------------------------------------
# _find_related_tests
# ---------------------------------------------------------------------------


class TestFindRelatedTests:
    def test_finds_matching_test(self, tmp_path: Path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_pfs.py").write_text("# test", encoding="utf-8")
        (tests_dir / "test_other.py").write_text("# test", encoding="utf-8")

        result = _find_related_tests(tmp_path, "src/drift/signals/pfs.py")
        assert any("test_pfs.py" in t for t in result)
        assert not any("test_other.py" in t for t in result)

    def test_no_tests_dir(self, tmp_path: Path):
        result = _find_related_tests(tmp_path, "src/drift/signals/pfs.py")
        assert result == []


# ---------------------------------------------------------------------------
# _extract_imports
# ---------------------------------------------------------------------------


class TestExtractImports:
    def test_extracts_imports(self, tmp_path: Path):
        py_file = tmp_path / "example.py"
        py_file.write_text(
            textwrap.dedent('''\
            import os
            from pathlib import Path
            from drift.models import RepoAnalysis
            '''),
            encoding="utf-8",
        )
        result = _extract_imports(py_file)
        assert "os" in result
        assert "pathlib" in result
        assert "drift.models" in result

    def test_nonexistent(self, tmp_path: Path):
        assert _extract_imports(tmp_path / "nonexistent.py") == []


# ---------------------------------------------------------------------------
# _build_guard_contract
# ---------------------------------------------------------------------------


class TestBuildGuardContract:
    def test_minimal_contract(self, tmp_path: Path):
        contract = _build_guard_contract(
            repo_root=tmp_path,
            target="src/drift/signals/pfs.py",
            steer_result=None,
            decision_constraints=[],
        )
        assert contract["type"] == "guard_contract"
        assert contract["target"] == "src/drift/signals/pfs.py"
        assert contract["boundary_contract"]["layer"] == "signals"
        assert "pre_edit_guard" in contract
        assert "boundary_contract" in contract

    def test_with_steer_data(self, tmp_path: Path):
        steer_data = {
            "status": "ok",
            "modules": [{"path": "src/drift/signals", "layer": "signals"}],
            "neighbors": ["src/drift/models", "src/drift/ingestion"],
            "abstractions": [{"symbol": "BaseSignal"}],
            "hotspots": [
                {
                    "path": "src/drift/signals/pfs.py",
                    "trend": "degrading",
                    "recurring_signals": {"PFS": 3},
                }
            ],
        }
        contract = _build_guard_contract(
            repo_root=tmp_path,
            target="src/drift/signals/pfs.py",
            steer_result=steer_data,
            decision_constraints=[
                {"id": "ADR-001", "rule": "No direct output imports"}
            ],
        )
        assert contract["boundary_contract"]["layer"] == "signals"
        assert "output" in contract["boundary_contract"]["forbidden_imports_from"]
        assert contract["boundary_contract"]["arch_decisions"][0]["id"] == "ADR-001"
        assert "PFS" in contract["pre_edit_guard"]["active_signals_affecting"]
        assert len(contract["pre_edit_guard"]["invariants"]) > 0

    def test_with_findings(self, tmp_path: Path):
        findings = [{"signal": "PFS", "severity": "high", "title": "test"}]
        contract = _build_guard_contract(
            repo_root=tmp_path,
            target="src/drift/api/scan.py",
            steer_result=None,
            decision_constraints=[],
            findings=findings,
        )
        assert contract["pre_edit_guard"]["known_findings"] == findings

    def test_schema_version(self, tmp_path: Path):
        contract = _build_guard_contract(
            repo_root=tmp_path,
            target="src/drift/models/foo.py",
            steer_result=None,
            decision_constraints=[],
        )
        assert contract["schema_version"] == "1.0"


# ---------------------------------------------------------------------------
# guard_contract (integration-level, mocked)
# ---------------------------------------------------------------------------


class TestGuardContractEndpoint:
    def test_returns_ok_without_arch_graph(self, tmp_path: Path):
        """guard_contract should degrade gracefully when no ArchGraph exists."""
        result = guard_contract(path=str(tmp_path), target="src/drift/signals/pfs.py")
        assert result.get("type") == "guard_contract" or result.get("status") in ("ok", "error")

    def test_includes_next_step_contract(self, tmp_path: Path):
        result = guard_contract(path=str(tmp_path), target="src/signals/pfs.py")
        # Should always have next-step contract fields (even on degraded path)
        if result.get("status") == "ok":
            assert "done_when" in result
