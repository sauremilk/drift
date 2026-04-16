"""Tests for Issue #398 — path traversal rejection in resolve_scope().

Validates that scope_override values containing '..' or resolving outside
the repository root are rejected with ValueError, and that scope_aliases
with traversal targets are silently skipped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.scope_resolver import resolve_scope


class TestScopeOverrideTraversalRejection:
    def test_dotdot_in_scope_override_raises(self, tmp_path: Path) -> None:
        repo = tmp_path / "my-repo"
        repo.mkdir()
        with pytest.raises(ValueError, match="traversal"):
            resolve_scope("anything", repo, scope_override="../sibling-repo/src")

    def test_dotdot_nested_scope_override_raises(self, tmp_path: Path) -> None:
        repo = tmp_path / "my-repo"
        repo.mkdir()
        with pytest.raises(ValueError, match="traversal"):
            resolve_scope("anything", repo, scope_override="src/../../outside")

    def test_absolute_outside_repo_raises(self, tmp_path: Path) -> None:
        repo = tmp_path / "my-repo"
        repo.mkdir()
        outside = tmp_path / "other"
        outside.mkdir()
        # Relative path that resolves outside after joining is the primary
        # concern; absolute paths also get rejected via is_relative_to check.
        with pytest.raises(ValueError, match="traversal|outside"):
            resolve_scope("anything", repo, scope_override="../other")

    def test_valid_scope_override_accepted(self, tmp_path: Path) -> None:
        repo = tmp_path / "my-repo"
        src = repo / "src"
        src.mkdir(parents=True)
        scope = resolve_scope("anything", repo, scope_override="src")
        assert scope.method == "manual_override"
        assert scope.paths == ["src"]
        assert scope.confidence == 0.95

    def test_empty_scope_override_raises(self, tmp_path: Path) -> None:
        repo = tmp_path / "my-repo"
        repo.mkdir()
        with pytest.raises(ValueError):
            resolve_scope("anything", repo, scope_override="/")


class TestScopeAliasesTraversalRejection:
    def test_dotdot_alias_target_is_skipped(self, tmp_repo: Path) -> None:
        """An alias with '..' in target must be silently discarded."""
        scope = resolve_scope(
            "add payment",
            tmp_repo,
            scope_aliases={"payment": "../outside/src"},
        )
        # The traversal alias should not appear in resolved paths
        assert not any(".." in p for p in scope.paths)

    def test_valid_alias_target_is_used(self, tmp_repo: Path) -> None:
        """A valid alias pointing to an existing directory must be honoured."""
        scope = resolve_scope(
            "checkout update",
            tmp_repo,
            scope_aliases={"checkout": "services"},
        )
        assert any("services" in p for p in scope.paths)
