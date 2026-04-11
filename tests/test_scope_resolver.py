"""Tests for scope_resolver — deterministic scope resolution from task strings."""

from __future__ import annotations

from pathlib import Path

from drift.scope_resolver import (
    ResolvedScope,
    _collect_symbols,
    _extract_paths,
    _levenshtein,
    _tokenize_task,
    expand_scope_imports,
    resolve_scope,
)

# ---------------------------------------------------------------------------
# Unit tests — path extraction
# ---------------------------------------------------------------------------


class TestExtractPaths:
    def test_explicit_python_path(self) -> None:
        paths = _extract_paths("fix bug in src/checkout/handlers.py")
        assert any("src/checkout/handlers.py" in p for p in paths)

    def test_directory_path(self) -> None:
        paths = _extract_paths("refactor the src/api/ module")
        assert any("src/api" in p for p in paths)

    def test_relative_path(self) -> None:
        paths = _extract_paths("check ./services/payment.py")
        assert any("services/payment.py" in p for p in paths)

    def test_no_paths(self) -> None:
        paths = _extract_paths("add caching to the checkout module")
        # No file-system style paths in this text
        assert isinstance(paths, list)

    def test_multiple_paths(self) -> None:
        paths = _extract_paths("merge src/a.py and src/b.py")
        assert len(paths) >= 2


# ---------------------------------------------------------------------------
# Unit tests — tokenization
# ---------------------------------------------------------------------------


class TestTokenizeTask:
    def test_stop_word_removal(self) -> None:
        tokens = _tokenize_task("add the payment integration to checkout")
        assert "add" not in tokens
        assert "the" not in tokens
        assert "to" not in tokens
        assert "payment" in tokens
        assert "checkout" in tokens
        assert "integration" in tokens

    def test_separator_handling(self) -> None:
        tokens = _tokenize_task("refactor auth-service, update config")
        assert "auth" in tokens
        assert "service" in tokens  # split on hyphen
        assert "config" in tokens

    def test_empty_string(self) -> None:
        assert _tokenize_task("") == []


# ---------------------------------------------------------------------------
# Integration tests — resolve_scope with tmp_repo fixture
# ---------------------------------------------------------------------------


class TestResolveScope:
    def test_keyword_matches_directory(self, tmp_repo: Path) -> None:
        """'services' keyword should match the services/ directory."""
        scope = resolve_scope("refactor the services layer", tmp_repo)
        assert scope.method == "keyword_match"
        assert scope.confidence > 0.5
        assert any("services" in p for p in scope.paths)

    def test_keyword_matches_api(self, tmp_repo: Path) -> None:
        scope = resolve_scope("update api routes", tmp_repo)
        assert scope.method == "keyword_match"
        assert any("api" in p for p in scope.paths)

    def test_manual_override(self, tmp_repo: Path) -> None:
        scope = resolve_scope(
            "anything",
            tmp_repo,
            scope_override="services/",
        )
        assert scope.method == "manual_override"
        assert scope.confidence == 0.95
        assert "services" in scope.paths[0]

    def test_fallback_for_vague_task(self, tmp_repo: Path) -> None:
        scope = resolve_scope("improve performance", tmp_repo)
        # No matching directories for these generic terms
        assert scope.method == "fallback"
        assert scope.confidence == 0.0
        assert scope.paths == []

    def test_substring_match(self, tmp_repo: Path) -> None:
        """Token 'payment' should substring-match a directory containing it."""
        # Create a payment directory for this test
        pay_dir = tmp_repo / "payment"
        pay_dir.mkdir()
        (pay_dir / "__init__.py").write_text("")

        scope = resolve_scope("add payment integration", tmp_repo)
        assert scope.method == "keyword_match"
        assert any("payment" in p for p in scope.paths)

    def test_explicit_path_in_task(self, tmp_repo: Path) -> None:
        """Path in task string should be detected via regex."""
        # Create the target file
        checkout = tmp_repo / "src" / "checkout"
        checkout.mkdir(parents=True)
        (checkout / "handlers.py").write_text("def handle(): pass\n")

        scope = resolve_scope(
            "fix bug in src/checkout/handlers.py",
            tmp_repo,
        )
        assert scope.method == "path_match"
        assert scope.confidence == 0.95

    def test_empty_task_returns_fallback(self, tmp_repo: Path) -> None:
        scope = resolve_scope("", tmp_repo)
        assert scope.method == "fallback"
        assert scope.confidence == 0.0

    def test_layer_names_from_config(self, tmp_repo: Path) -> None:
        """Layer names should act as keyword aliases."""
        scope = resolve_scope(
            "fix the db layer",
            tmp_repo,
            layer_names=["api", "services", "db"],
        )
        assert scope.method == "keyword_match"
        assert any("db" in p for p in scope.paths)


# ---------------------------------------------------------------------------
# Import-graph scope expansion tests
# ---------------------------------------------------------------------------


class TestExpandScopeImports:
    def test_expands_to_imported_directory(self, tmp_repo: Path) -> None:
        """Scope on api/ should expand to include services/ (imported)."""
        scope = ResolvedScope(
            paths=["api"],
            confidence=0.7,
            method="keyword_match",
        )
        expanded = expand_scope_imports(scope, tmp_repo)
        assert any("services" in p for p in expanded)

    def test_no_expansion_for_empty_scope(self, tmp_repo: Path) -> None:
        """Fallback scope (no paths) should return empty expansion."""
        scope = ResolvedScope(
            paths=[],
            confidence=0.0,
            method="fallback",
        )
        expanded = expand_scope_imports(scope, tmp_repo)
        assert expanded == []

    def test_no_self_reference(self, tmp_repo: Path) -> None:
        """Expanded paths should not include paths already in scope."""
        scope = ResolvedScope(
            paths=["api"],
            confidence=0.7,
            method="keyword_match",
        )
        expanded = expand_scope_imports(scope, tmp_repo)
        assert "api" not in expanded

    def test_resolves_intra_repo_imports_only(self, tmp_repo: Path) -> None:
        """External imports (stdlib, third-party) should not appear."""
        scope = ResolvedScope(
            paths=["services"],
            confidence=0.7,
            method="keyword_match",
        )
        expanded = expand_scope_imports(scope, tmp_repo)
        # Should not contain stdlib paths like 'os' or 'pathlib'
        for p in expanded:
            assert p not in ("os", "pathlib", "typing")


# ---------------------------------------------------------------------------
# Levenshtein distance
# ---------------------------------------------------------------------------


class TestLevenshtein:
    def test_identical_strings(self) -> None:
        assert _levenshtein("abc", "abc") == 0

    def test_single_insertion(self) -> None:
        assert _levenshtein("abc", "abcd") == 1

    def test_single_deletion(self) -> None:
        assert _levenshtein("abcd", "abc") == 1

    def test_single_substitution(self) -> None:
        assert _levenshtein("abc", "aXc") == 1

    def test_empty_strings(self) -> None:
        assert _levenshtein("", "") == 0
        assert _levenshtein("abc", "") == 3

    def test_two_edits(self) -> None:
        assert _levenshtein("kitten", "sittin") == 2

    def test_swap_order_does_not_matter(self) -> None:
        assert _levenshtein("short", "longerstring") == _levenshtein("longerstring", "short")

    def test_empty_b_returns_len_a(self) -> None:
        assert _levenshtein("hello", "") == 5


# ---------------------------------------------------------------------------
# Symbol-based scope resolution
# ---------------------------------------------------------------------------


class TestCollectSymbols:
    def test_finds_classes(self, tmp_repo: Path) -> None:
        symbols = _collect_symbols(tmp_repo)
        assert "user" in symbols
        assert "payment" in symbols

    def test_finds_functions(self, tmp_repo: Path) -> None:
        symbols = _collect_symbols(tmp_repo)
        # process_payment is a public function in services/payment_service.py
        assert "process_payment" in symbols

    def test_skips_private(self, tmp_repo: Path) -> None:
        symbols = _collect_symbols(tmp_repo)
        # Private symbols (prefixed with _) should be excluded
        for key in symbols:
            assert not key.startswith("_")


class TestSymbolBasedResolution:
    def test_class_name_resolves_scope(self, tmp_repo: Path) -> None:
        """Task mentioning 'PaymentError' should resolve to services/."""
        scope = resolve_scope("fix PaymentError handling", tmp_repo)
        assert scope.method == "keyword_match"
        assert any("services" in p for p in scope.paths)

    def test_function_name_resolves_scope(self, tmp_repo: Path) -> None:
        """Task mentioning 'PaymentService' maps to services/ via symbols."""
        # Create a class PaymentService in services/
        svc_file = tmp_repo / "services" / "payment_service.py"
        content = svc_file.read_text()
        svc_file.write_text(content + "\nclass PaymentService:\n    pass\n")

        scope = resolve_scope(
            "improve PaymentService logic",
            tmp_repo,
        )
        assert scope.method == "keyword_match"
        assert any("services" in p for p in scope.paths)

    def test_fuzzy_match_typo(self, tmp_repo: Path) -> None:
        """Typo 'servces' (1 edit from 'services') should still match."""
        scope = resolve_scope("refactor servces layer", tmp_repo)
        # Should match via fuzzy (Levenshtein ≤ 2) on directory or symbol
        assert scope.method == "keyword_match"


# ---------------------------------------------------------------------------
# Configurable keyword aliases
# ---------------------------------------------------------------------------


class TestScopeAliases:
    def test_alias_resolves_scope(self, tmp_repo: Path) -> None:
        """User-defined alias 'billing' → 'services' should work."""
        scope = resolve_scope(
            "update billing module",
            tmp_repo,
            scope_aliases={"billing": "services"},
        )
        assert scope.method == "keyword_match"
        assert any("services" in p for p in scope.paths)

    def test_alias_takes_precedence_over_substring(self, tmp_repo: Path) -> None:
        """Alias exact match should resolve even if no directory substring matches."""
        scope = resolve_scope(
            "fix auth logic",
            tmp_repo,
            scope_aliases={"auth": "api"},
        )
        assert scope.method == "keyword_match"
        assert any("api" in p for p in scope.paths)

    def test_empty_aliases_no_effect(self, tmp_repo: Path) -> None:
        """Passing empty aliases should not change resolution."""
        scope_a = resolve_scope("update services layer", tmp_repo)
        scope_b = resolve_scope(
            "update services layer",
            tmp_repo,
            scope_aliases={},
        )
        assert scope_a.paths == scope_b.paths
