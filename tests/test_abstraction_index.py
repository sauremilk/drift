"""Tests for the Abstraction Index — Phase C of the Architecture Runtime Blueprint.

The Abstraction Index provides active reuse suggestions: given a description
of what an agent is about to create, it returns existing abstractions that
might already serve the purpose — shifting from "you duplicated X" (MDS)
to "use X instead of writing a new one" (proactive guidance).
"""

from __future__ import annotations

import json

from drift.arch_graph import (
    ArchAbstraction,
    ArchDependency,
    ArchGraph,
    ArchModule,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_abstractions() -> list[ArchAbstraction]:
    """Rich abstraction set for testing reuse matching."""
    return [
        ArchAbstraction(
            symbol="validate_email",
            kind="function",
            module_path="src/utils",
            file_path="src/utils/validators.py",
            usage_count=8,
            consumers=["src/api/users.py", "src/api/auth.py"],
            has_docstring=True,
            is_exported=True,
        ),
        ArchAbstraction(
            symbol="validate_url",
            kind="function",
            module_path="src/utils",
            file_path="src/utils/validators.py",
            usage_count=3,
            has_docstring=True,
            is_exported=True,
        ),
        ArchAbstraction(
            symbol="parse_config",
            kind="function",
            module_path="src/config",
            file_path="src/config/loader.py",
            usage_count=5,
            has_docstring=True,
            is_exported=True,
        ),
        ArchAbstraction(
            symbol="DatabasePool",
            kind="class",
            module_path="src/db",
            file_path="src/db/pool.py",
            usage_count=6,
            has_docstring=True,
            is_exported=True,
        ),
        ArchAbstraction(
            symbol="HTTPClient",
            kind="class",
            module_path="src/http",
            file_path="src/http/client.py",
            usage_count=4,
            has_docstring=True,
            is_exported=True,
        ),
        ArchAbstraction(
            symbol="_internal_helper",
            kind="function",
            module_path="src/utils",
            file_path="src/utils/_internal.py",
            usage_count=1,
            has_docstring=False,
            is_exported=False,
        ),
        ArchAbstraction(
            symbol="format_response",
            kind="function",
            module_path="src/api",
            file_path="src/api/helpers.py",
            usage_count=7,
            has_docstring=True,
            is_exported=True,
        ),
        ArchAbstraction(
            symbol="hash_password",
            kind="function",
            module_path="src/auth",
            file_path="src/auth/crypto.py",
            usage_count=2,
            has_docstring=True,
            is_exported=True,
        ),
    ]


def _make_graph_with_abstractions() -> ArchGraph:
    return ArchGraph(
        version="test123",
        modules=[
            ArchModule(
                path="src/utils",
                drift_score=0.2,
                file_count=4,
                function_count=10,
                layer="infrastructure",
            ),
            ArchModule(
                path="src/api",
                drift_score=0.4,
                file_count=6,
                function_count=15,
                layer="presentation",
            ),
            ArchModule(
                path="src/db",
                drift_score=0.3,
                file_count=3,
                function_count=8,
                layer="data",
            ),
            ArchModule(
                path="src/config",
                drift_score=0.1,
                file_count=2,
                function_count=5,
                layer="infrastructure",
            ),
            ArchModule(
                path="src/auth",
                drift_score=0.2,
                file_count=2,
                function_count=4,
                layer="domain",
            ),
            ArchModule(
                path="src/http",
                drift_score=0.3,
                file_count=2,
                function_count=3,
                layer="infrastructure",
            ),
        ],
        dependencies=[
            ArchDependency(from_module="src/api", to_module="src/utils"),
            ArchDependency(from_module="src/api", to_module="src/db"),
            ArchDependency(from_module="src/api", to_module="src/auth"),
        ],
        abstractions=_make_abstractions(),
        hotspots=[],
    )


# ---------------------------------------------------------------------------
# 1. ReuseSuggestion data model
# ---------------------------------------------------------------------------


class TestReuseSuggestion:
    def test_construction(self) -> None:
        from drift.arch_graph._reuse_index import ReuseSuggestion

        s = ReuseSuggestion(
            symbol="validate_email",
            kind="function",
            module_path="src/utils",
            file_path="src/utils/validators.py",
            usage_count=8,
            relevance_score=0.85,
            reason="Name matches query 'email validation'",
        )
        assert s.symbol == "validate_email"
        assert s.relevance_score == 0.85

    def test_to_dict(self) -> None:
        from drift.arch_graph._reuse_index import ReuseSuggestion

        s = ReuseSuggestion(
            symbol="validate_email",
            kind="function",
            module_path="src/utils",
            file_path="src/utils/validators.py",
            usage_count=8,
            relevance_score=0.85,
            reason="Token overlap",
        )
        d = s.to_dict()
        assert d["symbol"] == "validate_email"
        assert d["relevance_score"] == 0.85
        assert "reason" in d
        # Must be JSON-serializable
        json.dumps(d)


# ---------------------------------------------------------------------------
# 2. AbstractionIndex — building and querying
# ---------------------------------------------------------------------------


class TestAbstractionIndex:
    def test_build_from_abstractions(self) -> None:
        from drift.arch_graph._reuse_index import AbstractionIndex

        abstractions = _make_abstractions()
        index = AbstractionIndex.build(abstractions)

        # Should filter out non-exported, low-usage
        assert index.size > 0
        assert index.size <= len(abstractions)

    def test_build_filters_non_exported_low_usage(self) -> None:
        from drift.arch_graph._reuse_index import AbstractionIndex

        abstractions = _make_abstractions()
        index = AbstractionIndex.build(abstractions, min_usage=2)

        # _internal_helper (not exported, usage_count=1) must be excluded
        symbols = {e.symbol for e in index.entries}
        assert "_internal_helper" not in symbols

    def test_build_includes_exported_regardless_of_usage(self) -> None:
        from drift.arch_graph._reuse_index import AbstractionIndex

        abstractions = [
            ArchAbstraction(
                symbol="rare_but_exported",
                kind="function",
                module_path="src/core",
                file_path="src/core/rare.py",
                usage_count=0,
                is_exported=True,
            ),
        ]
        index = AbstractionIndex.build(abstractions, min_usage=2)
        symbols = {e.symbol for e in index.entries}
        assert "rare_but_exported" in symbols

    def test_search_by_name_tokens(self) -> None:
        from drift.arch_graph._reuse_index import AbstractionIndex

        abstractions = _make_abstractions()
        index = AbstractionIndex.build(abstractions)

        results = index.search("validate email address")
        assert len(results) > 0
        # validate_email should be top result
        assert results[0].symbol == "validate_email"

    def test_search_returns_sorted_by_relevance(self) -> None:
        from drift.arch_graph._reuse_index import AbstractionIndex

        abstractions = _make_abstractions()
        index = AbstractionIndex.build(abstractions)

        results = index.search("validate")
        assert len(results) >= 2
        # Scores must be descending
        for i in range(len(results) - 1):
            assert results[i].relevance_score >= results[i + 1].relevance_score

    def test_search_respects_top_k(self) -> None:
        from drift.arch_graph._reuse_index import AbstractionIndex

        abstractions = _make_abstractions()
        index = AbstractionIndex.build(abstractions)

        results = index.search("function", top_k=2)
        assert len(results) <= 2

    def test_search_with_kind_filter(self) -> None:
        from drift.arch_graph._reuse_index import AbstractionIndex

        abstractions = _make_abstractions()
        index = AbstractionIndex.build(abstractions)

        results = index.search("pool database", kind="class")
        # All results should be classes
        for r in results:
            assert r.kind == "class"

    def test_search_empty_query_returns_by_usage(self) -> None:
        from drift.arch_graph._reuse_index import AbstractionIndex

        abstractions = _make_abstractions()
        index = AbstractionIndex.build(abstractions)

        results = index.search("", top_k=3)
        # With no query tokens, should rank by usage_count desc
        assert len(results) == 3
        assert results[0].usage_count >= results[1].usage_count

    def test_search_with_scope_filter(self) -> None:
        from drift.arch_graph._reuse_index import AbstractionIndex

        abstractions = _make_abstractions()
        index = AbstractionIndex.build(abstractions)

        results = index.search("validate", scope="src/utils")
        # All results should be from src/utils
        for r in results:
            assert r.module_path == "src/utils"

    def test_empty_index_returns_empty(self) -> None:
        from drift.arch_graph._reuse_index import AbstractionIndex

        index = AbstractionIndex.build([])
        results = index.search("anything")
        assert results == []


# ---------------------------------------------------------------------------
# 3. suggest_reuse() — convenience function on ArchGraph
# ---------------------------------------------------------------------------


class TestSuggestReuse:
    def test_suggest_from_graph(self) -> None:
        from drift.arch_graph._reuse_index import suggest_reuse

        graph = _make_graph_with_abstractions()
        suggestions = suggest_reuse(graph, query="validate email")

        assert len(suggestions) > 0
        assert suggestions[0].symbol == "validate_email"

    def test_suggest_with_scope_limits_to_reachable(self) -> None:
        from drift.arch_graph._reuse_index import suggest_reuse

        graph = _make_graph_with_abstractions()
        # Scope to src/api — should prefer abstractions from
        # src/api itself or its neighbors (src/utils, src/db, src/auth)
        suggestions = suggest_reuse(
            graph, query="validate", scope="src/api"
        )
        reachable = {"src/api", "src/utils", "src/db", "src/auth"}
        for s in suggestions:
            assert s.module_path in reachable

    def test_suggest_returns_reason(self) -> None:
        from drift.arch_graph._reuse_index import suggest_reuse

        graph = _make_graph_with_abstractions()
        suggestions = suggest_reuse(graph, query="config parsing")
        assert len(suggestions) > 0
        assert suggestions[0].reason  # non-empty reason

    def test_suggest_serializable(self) -> None:
        from drift.arch_graph._reuse_index import suggest_reuse

        graph = _make_graph_with_abstractions()
        suggestions = suggest_reuse(graph, query="database pool")
        dicts = [s.to_dict() for s in suggestions]
        json.dumps(dicts)  # must not raise

    def test_suggest_max_suggestions(self) -> None:
        from drift.arch_graph._reuse_index import suggest_reuse

        graph = _make_graph_with_abstractions()
        suggestions = suggest_reuse(
            graph, query="validate", max_suggestions=1
        )
        assert len(suggestions) <= 1
