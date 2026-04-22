"""Tests for scripts/gate_check.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "gate_check.py"

_spec = importlib.util.spec_from_file_location("gate_check", _SCRIPT_PATH)
assert _spec and _spec.loader
_gate_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gate_check)  # type: ignore[union-attr]


def test_eval_feat_requires_all_feature_artifacts() -> None:
    results = _gate_check.evaluate_gates(
        changed_files={"src/drift/api/scan.py"},
        commit_type="feat",
        gate6_ok=True,
        head_sha="abc",
        last_success_sha="abc",
    )

    by_gate = {result.gate: result for result in results}
    assert by_gate[2].status == "MISSING"
    assert by_gate[3].status == "MISSING"
    assert by_gate[8].status == "OK"


def test_eval_feat_passes_with_required_files() -> None:
    results = _gate_check.evaluate_gates(
        changed_files={
            "tests/test_demo.py",
            "benchmark_results/v2.99.0_demo_feature_evidence.json",
            "CHANGELOG.md",
            "docs/STUDY.md",
            "src/drift/api/scan.py",
        },
        commit_type="feat",
        gate6_ok=True,
        head_sha="abc",
        last_success_sha="abc",
    )

    by_gate = {result.gate: result for result in results}
    assert by_gate[2].status == "OK"
    assert by_gate[3].status == "OK"
    assert by_gate[6].status == "OK"
    assert by_gate[8].status == "OK"


def test_eval_signal_change_requires_audit_update() -> None:
    results = _gate_check.evaluate_gates(
        changed_files={"src/drift/signals/pfs.py"},
        commit_type="chore",
        gate6_ok=True,
        head_sha="abc",
        last_success_sha="abc",
    )

    by_gate = {result.gate: result for result in results}
    assert by_gate[7].active is True
    assert by_gate[7].status == "MISSING"


def test_eval_signal_change_with_audit_update_is_ok() -> None:
    results = _gate_check.evaluate_gates(
        changed_files={
            "src/drift/output/rich_output.py",
            "audit_results/fmea_matrix.md",
        },
        commit_type="fix",
        gate6_ok=True,
        head_sha="abc",
        last_success_sha="abc",
    )

    by_gate = {result.gate: result for result in results}
    assert by_gate[7].status == "OK"


def test_public_api_docstring_check_detects_missing_docstring() -> None:
    diff_text = """
+++ b/src/drift/example.py
+def public_fn(x):
+    return x
"""
    ok, missing = _gate_check.check_public_api_docstrings_diff(diff_text)
    assert ok is False
    assert "src/drift/example.py" in missing


def test_public_api_docstring_check_passes_with_added_docstring() -> None:
    diff_text = """
+++ b/src/drift/example.py
+def public_fn(x):
+    \"\"\"Explain function.\"\"\"
+    return x
"""
    ok, missing = _gate_check.check_public_api_docstrings_diff(diff_text)
    assert ok is True
    assert missing == []
