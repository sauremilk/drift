"""Tests for scripts/_context_mapping.py — contract and file existence."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _context_mapping as ctx  # noqa: E402


def test_every_valid_task_type_has_entry() -> None:
    for task_type in ctx.VALID_TASK_TYPES:
        assert task_type in ctx.CONTEXT_PATHS
        assert ctx.CONTEXT_PATHS[task_type], f"empty context for {task_type}"


def test_no_entry_exceeds_budget() -> None:
    for task_type, paths in ctx.CONTEXT_PATHS.items():
        assert len(paths) <= ctx.MAX_PATHS_PER_TYPE, f"{task_type} exceeds budget"


@pytest.mark.parametrize("task_type", ctx.VALID_TASK_TYPES)
def test_all_referenced_paths_exist(task_type: str) -> None:
    """Every referenced path must resolve to an existing file — catches renames."""
    for rel_path in ctx.CONTEXT_PATHS[task_type]:
        full = REPO_ROOT / rel_path
        assert full.is_file(), f"missing file referenced by {task_type!r}: {rel_path}"


def test_context_for_rejects_unknown_type() -> None:
    with pytest.raises(KeyError):
        ctx.context_for("nonsense")


def test_no_policy_text_leaks_into_mapping() -> None:
    """Regression guard: mapping values must be paths only, not prose."""
    for paths in ctx.CONTEXT_PATHS.values():
        for path in paths:
            assert path.endswith(".md"), f"non-md path leaks policy ambiguity: {path}"
            assert " " not in path, f"path contains space (likely prose): {path!r}"
            assert len(path) < 200, f"path suspiciously long: {path!r}"
