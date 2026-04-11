"""Tests for React Hook pattern extraction (Task 5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.ingestion.ts_parser import parse_typescript_file, tree_sitter_available
from drift.models import PatternCategory

needs_tree_sitter = pytest.mark.skipif(
    not tree_sitter_available(),
    reason="tree-sitter-typescript not installed",
)

FIXTURES = Path("tests/fixtures/typescript/react_hooks")


def _hook_patterns(pr):
    return [p for p in pr.patterns if p.category == PatternCategory.REACT_HOOK]


@needs_tree_sitter
class TestMissingDependencyArray:
    def test_effect_without_deps_detected(self) -> None:
        pr = parse_typescript_file(FIXTURES / "missing_deps.tsx", Path("."), language="tsx")
        hooks = _hook_patterns(pr)
        missing = [p for p in hooks if p.variant_id == "MISSING_DEPENDENCY_ARRAY"]
        assert len(missing) >= 1
        assert missing[0].fingerprint["hook"] == "useEffect"

    def test_clean_effect_no_missing_deps(self) -> None:
        pr = parse_typescript_file(FIXTURES / "clean_effect.tsx", Path("."), language="tsx")
        hooks = _hook_patterns(pr)
        missing = [p for p in hooks if p.variant_id == "MISSING_DEPENDENCY_ARRAY"]
        assert len(missing) == 0


@needs_tree_sitter
class TestStaleClosure:
    def test_empty_deps_with_referenced_state(self) -> None:
        pr = parse_typescript_file(FIXTURES / "stale_closure.tsx", Path("."), language="tsx")
        hooks = _hook_patterns(pr)
        stale = [p for p in hooks if p.variant_id == "STALE_CLOSURE"]
        assert len(stale) >= 1
        assert stale[0].fingerprint["hook"] == "useEffect"

    def test_clean_effect_no_stale_closure(self) -> None:
        pr = parse_typescript_file(FIXTURES / "clean_effect.tsx", Path("."), language="tsx")
        hooks = _hook_patterns(pr)
        stale = [p for p in hooks if p.variant_id == "STALE_CLOSURE"]
        assert len(stale) == 0


@needs_tree_sitter
class TestHookPlacement:
    def test_custom_hook_outside_hooks_dir(self) -> None:
        pr = parse_typescript_file(FIXTURES / "services" / "auth.tsx", Path("."), language="tsx")
        hooks = _hook_patterns(pr)
        placement = [p for p in hooks if p.variant_id == "HOOK_PLACEMENT_VIOLATION"]
        assert len(placement) >= 1
        assert placement[0].fingerprint["hook_name"] == "useAuth"

    def test_non_tsx_file_no_hook_patterns(self) -> None:
        """Plain .ts files should not trigger hook extraction."""
        pr = parse_typescript_file(
            FIXTURES / "services" / "auth.tsx", Path("."), language="typescript"
        )
        hooks = _hook_patterns(pr)
        assert len(hooks) == 0


@needs_tree_sitter
class TestPatternCategory:
    def test_react_hook_category_exists(self) -> None:
        assert PatternCategory.REACT_HOOK == "react_hook"
