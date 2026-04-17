"""Tests for the Steer API — Phase B of the Architecture Runtime Blueprint.

steer() is location-centric: given target files/modules, it returns
the architecture context that applies at that location (layer, neighbors,
reusable abstractions, hotspots, guardrails).

Key design difference from other APIs:
- brief() is task-centric (what to do)
- steer() is location-centric (what rules apply here)
- nudge() is post-edit (what went wrong)
- steer() is pre-edit (what you're allowed to do)
"""

from __future__ import annotations

import json
from pathlib import Path

from drift.arch_graph import (
    ArchAbstraction,
    ArchDependency,
    ArchGraph,
    ArchGraphStore,
    ArchHotspot,
    ArchModule,
)

# ---------------------------------------------------------------------------
# 1. SteerContext data model
# ---------------------------------------------------------------------------


class TestSteerContext:
    def test_construction_with_defaults(self) -> None:
        from drift.api.steer import SteerContext

        ctx = SteerContext(target="src/api")
        assert ctx.target == "src/api"
        assert ctx.modules == []
        assert ctx.neighbors == []
        assert ctx.abstractions == []
        assert ctx.hotspots == []
        assert ctx.layer_policies == []

    def test_to_dict(self) -> None:
        from drift.api.steer import SteerContext

        ctx = SteerContext(
            target="src/api",
            modules=[{"path": "src/api", "drift_score": 0.3, "layer": "presentation"}],
            neighbors=["src/db", "src/core"],
            abstractions=[
                {"symbol": "get_user", "kind": "function", "module_path": "src/db"}
            ],
            hotspots=[
                {"path": "src/api/auth.py", "recurring_signals": {"PFS": 3}, "trend": "degrading"}
            ],
            layer_policies=[
                {"from_module": "src/api", "to_module": "src/db", "policy": "forbidden"}
            ],
        )

        d = ctx.to_dict()
        assert d["target"] == "src/api"
        assert len(d["modules"]) == 1
        assert len(d["neighbors"]) == 2
        assert len(d["abstractions"]) == 1
        assert len(d["hotspots"]) == 1
        assert len(d["layer_policies"]) == 1


# ---------------------------------------------------------------------------
# 2. steer_from_graph — core logic (no I/O, no analysis)
# ---------------------------------------------------------------------------


def _make_test_graph() -> ArchGraph:
    """Shared test graph for steer tests."""
    return ArchGraph(
        version="abc1234",
        modules=[
            ArchModule(
                path="src/api",
                drift_score=0.3,
                file_count=5,
                function_count=10,
                layer="presentation",
                stability=0.8,
                languages=["python"],
            ),
            ArchModule(
                path="src/db",
                drift_score=0.6,
                file_count=3,
                function_count=8,
                layer="data",
                stability=0.5,
                languages=["python"],
            ),
            ArchModule(
                path="src/core",
                drift_score=0.1,
                file_count=7,
                function_count=20,
                layer="domain",
                stability=0.95,
                languages=["python"],
            ),
        ],
        dependencies=[
            ArchDependency(from_module="src/api", to_module="src/core"),
            ArchDependency(
                from_module="src/api",
                to_module="src/db",
                policy="forbidden",
            ),
            ArchDependency(from_module="src/core", to_module="src/db"),
        ],
        abstractions=[
            ArchAbstraction(
                symbol="get_user",
                kind="function",
                module_path="src/db",
                file_path="src/db/users.py",
                usage_count=5,
                is_exported=True,
                has_docstring=True,
            ),
            ArchAbstraction(
                symbol="validate_input",
                kind="function",
                module_path="src/core",
                file_path="src/core/validation.py",
                usage_count=12,
                is_exported=True,
                has_docstring=True,
            ),
            ArchAbstraction(
                symbol="BaseHandler",
                kind="class",
                module_path="src/api",
                file_path="src/api/base.py",
                usage_count=3,
                is_exported=True,
                has_docstring=True,
            ),
        ],
        hotspots=[
            ArchHotspot(
                path="src/api/auth.py",
                recurring_signals={"PFS": 3, "MDS": 2},
                trend="degrading",
                total_occurrences=5,
            ),
            ArchHotspot(
                path="src/db/queries.py",
                recurring_signals={"EDS": 4},
                trend="stable",
                total_occurrences=4,
            ),
        ],
    )


class TestSteerFromGraph:
    """Test the core steer logic that queries an ArchGraph."""

    def test_basic_module_context(self) -> None:
        from drift.api.steer import steer_from_graph

        graph = _make_test_graph()
        ctx = steer_from_graph(graph, target="src/api")

        assert ctx.target == "src/api"
        assert len(ctx.modules) == 1
        assert ctx.modules[0]["path"] == "src/api"
        assert ctx.modules[0]["layer"] == "presentation"

    def test_neighbors_are_resolved(self) -> None:
        from drift.api.steer import steer_from_graph

        graph = _make_test_graph()
        ctx = steer_from_graph(graph, target="src/api")

        # src/api connects to src/core and src/db
        assert set(ctx.neighbors) == {"src/core", "src/db"}

    def test_abstractions_from_neighbors(self) -> None:
        from drift.api.steer import steer_from_graph

        graph = _make_test_graph()
        ctx = steer_from_graph(graph, target="src/api")

        # Should include abstractions from neighbor modules (src/core, src/db)
        # and from the target module itself (src/api)
        symbols = {a["symbol"] for a in ctx.abstractions}
        assert "get_user" in symbols  # from src/db (neighbor)
        assert "validate_input" in symbols  # from src/core (neighbor)
        assert "BaseHandler" in symbols  # from src/api (self)

    def test_hotspots_filtered_to_target(self) -> None:
        from drift.api.steer import steer_from_graph

        graph = _make_test_graph()
        ctx = steer_from_graph(graph, target="src/api")

        # Only hotspots within src/api should be returned
        assert len(ctx.hotspots) == 1
        assert ctx.hotspots[0]["path"] == "src/api/auth.py"

    def test_layer_policies_extracted(self) -> None:
        from drift.api.steer import steer_from_graph

        graph = _make_test_graph()
        ctx = steer_from_graph(graph, target="src/api")

        # src/api -> src/db has policy "forbidden"
        forbidden = [p for p in ctx.layer_policies if p["policy"] == "forbidden"]
        assert len(forbidden) == 1
        assert forbidden[0]["from_module"] == "src/api"
        assert forbidden[0]["to_module"] == "src/db"

    def test_target_file_resolves_to_module(self) -> None:
        from drift.api.steer import steer_from_graph

        graph = _make_test_graph()
        # Target is a file path, should resolve to parent module
        ctx = steer_from_graph(graph, target="src/api/auth.py")

        assert len(ctx.modules) == 1
        assert ctx.modules[0]["path"] == "src/api"

    def test_unknown_target_returns_empty_context(self) -> None:
        from drift.api.steer import steer_from_graph

        graph = _make_test_graph()
        ctx = steer_from_graph(graph, target="src/nonexistent")

        assert ctx.modules == []
        assert ctx.neighbors == []
        assert ctx.hotspots == []

    def test_max_abstractions_limits_result(self) -> None:
        from drift.api.steer import steer_from_graph

        graph = _make_test_graph()
        ctx = steer_from_graph(graph, target="src/api", max_abstractions=1)

        assert len(ctx.abstractions) <= 1

    def test_to_dict_is_json_serializable(self) -> None:
        from drift.api.steer import steer_from_graph

        graph = _make_test_graph()
        ctx = steer_from_graph(graph, target="src/api")

        d = ctx.to_dict()
        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert isinstance(json_str, str)

    def test_db_target_context(self) -> None:
        from drift.api.steer import steer_from_graph

        graph = _make_test_graph()
        ctx = steer_from_graph(graph, target="src/db")

        assert len(ctx.modules) == 1
        assert ctx.modules[0]["layer"] == "data"
        # src/db connects to src/api (reverse) and src/core (reverse)
        assert "src/api" in ctx.neighbors or "src/core" in ctx.neighbors
        # Hotspot in src/db
        assert len(ctx.hotspots) == 1
        assert ctx.hotspots[0]["path"] == "src/db/queries.py"


# ---------------------------------------------------------------------------
# 3. steer() full API endpoint (with persistence)
# ---------------------------------------------------------------------------


class TestSteerAPI:
    def test_steer_with_cached_graph(self, tmp_path: Path) -> None:
        from drift.api.steer import steer

        # Pre-populate graph cache
        graph = _make_test_graph()
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = steer(
            path=str(tmp_path),
            target="src/api",
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        assert result["status"] == "ok"
        assert result["target"] == "src/api"
        assert "modules" in result
        assert "neighbors" in result
        assert "abstractions" in result
        assert "hotspots" in result
        assert "layer_policies" in result
        assert "agent_instruction" in result

    def test_steer_without_graph_returns_empty(self, tmp_path: Path) -> None:
        from drift.api.steer import steer

        result = steer(
            path=str(tmp_path),
            target="src/api",
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        assert result["status"] == "ok"
        assert result["modules"] == []
        assert result["graph_available"] is False

    def test_steer_response_has_next_step(self, tmp_path: Path) -> None:
        from drift.api.steer import steer

        graph = _make_test_graph()
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = steer(
            path=str(tmp_path),
            target="src/api",
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        assert "next_tool_call" in result
        assert "done_when" in result

    def test_steer_with_file_target(self, tmp_path: Path) -> None:
        from drift.api.steer import steer

        graph = _make_test_graph()
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = steer(
            path=str(tmp_path),
            target="src/api/auth.py",
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        assert result["status"] == "ok"
        assert len(result["modules"]) == 1
        assert result["modules"][0]["path"] == "src/api"

    def test_steer_with_include_reuse(self, tmp_path: Path) -> None:
        from drift.api.steer import steer

        graph = _make_test_graph()
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = steer(
            path=str(tmp_path),
            target="src/api",
            cache_dir=str(tmp_path / ".drift-cache"),
            include_reuse=True,
            reuse_query="validate input data",
        )

        assert result["status"] == "ok"
        assert "reuse_suggestions" in result
        assert len(result["reuse_suggestions"]) > 0
        # Each suggestion has expected keys
        first = result["reuse_suggestions"][0]
        assert "symbol" in first
        assert "relevance_score" in first
        assert "reason" in first

    def test_steer_without_include_reuse_has_empty_suggestions(
        self, tmp_path: Path
    ) -> None:
        from drift.api.steer import steer

        graph = _make_test_graph()
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = steer(
            path=str(tmp_path),
            target="src/api",
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        assert result["reuse_suggestions"] == []

    def test_steer_reuse_agent_instruction_mentions_suggestion(
        self, tmp_path: Path
    ) -> None:
        from drift.api.steer import steer

        graph = _make_test_graph()
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = steer(
            path=str(tmp_path),
            target="src/api",
            cache_dir=str(tmp_path / ".drift-cache"),
            include_reuse=True,
            reuse_query="validate input data",
        )

        assert "REUSE SUGGESTION" in result["agent_instruction"]
