"""Tests for scripts/risk_audit_diff.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "risk_audit_diff.py"

_spec = importlib.util.spec_from_file_location("risk_audit_diff", _SCRIPT_PATH)
assert _spec and _spec.loader
_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_script)  # type: ignore[union-attr]


def test_detects_signal_audit_requirements() -> None:
    changed = {"src/drift/signals/pfs.py"}
    required = _script.required_audit_updates(changed)
    assert any("fmea_matrix.md" in item for item in required)
    assert any("risk_register.md" in item for item in required)


def test_detects_output_audit_requirements() -> None:
    changed = {"src/drift/output/json_output.py"}
    required = _script.required_audit_updates(changed)
    assert any("stride_threat_model.md" in item for item in required)


def test_no_requirements_for_unrelated_changes() -> None:
    changed = {"README.md", "tests/test_x.py"}
    required = _script.required_audit_updates(changed)
    assert required == []
