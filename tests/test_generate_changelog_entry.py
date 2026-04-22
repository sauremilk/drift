"""Tests for scripts/generate_changelog_entry.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "generate_changelog_entry.py"

_spec = importlib.util.spec_from_file_location("generate_changelog_entry", _SCRIPT_PATH)
assert _spec and _spec.loader
_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_script)  # type: ignore[union-attr]


def test_build_entry_for_feat() -> None:
    entry = _script.build_entry(commit_type="feat", message="Add gate checker", version="2.27.0")
    assert "## [2.27.0]" in entry
    assert "### Added" in entry
    assert "Add gate checker" in entry


def test_build_entry_for_fix() -> None:
    entry = _script.build_entry(commit_type="fix", message="Handle empty diff", version="2.27.0")
    assert "### Fixed" in entry


def test_detect_current_version() -> None:
    version = _script.read_pyproject_version()
    assert version.count(".") == 2
