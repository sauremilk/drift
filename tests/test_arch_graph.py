"""Tests for the Architecture Graph module.

Phase A of the Architecture Runtime Blueprint:
Persistent, versioned architecture graph that evolves incrementally with the code.
"""

from __future__ import annotations

import json
from pathlib import Path

from drift.arch_graph import (
    ArchAbstraction,
    ArchDependency,
    ArchGraph,
    ArchHotspot,
    ArchModule,
)

# ---------------------------------------------------------------------------
# 1. Data model construction and defaults
# ---------------------------------------------------------------------------


class TestArchModule:
    def test_creation_with_defaults(self) -> None:
        m = ArchModule(path="src/api", drift_score=0.35, file_count=10, function_count=25)
        assert m.path == "src/api"
        assert m.drift_score == 0.35
        assert m.file_count == 10
        assert m.function_count == 25
        assert m.responsibility is None
        assert m.layer is None
        assert m.primary_owner is None
        assert m.stability == 1.0
        assert m.signal_scores == {}
        assert m.languages == []

    def test_creation_with_all_fields(self) -> None:
        m = ArchModule(
            path="src/api",
            drift_score=0.5,
            file_count=5,
            function_count=12,
            responsibility="HTTP request handling",
            layer="presentation",
            primary_owner="alice",
            stability=0.7,
            signal_scores={"PFS": 0.3},
            languages=["python"],
        )
        assert m.responsibility == "HTTP request handling"
        assert m.layer == "presentation"
        assert m.primary_owner == "alice"
        assert m.stability == 0.7
        assert m.signal_scores == {"PFS": 0.3}
        assert m.languages == ["python"]


class TestArchDependency:
    def test_creation(self) -> None:
        d = ArchDependency(from_module="src/api", to_module="src/db")
        assert d.from_module == "src/api"
        assert d.to_module == "src/db"
        assert d.dep_type == "import"
        assert d.weight == 1
        assert d.policy is None

    def test_with_policy(self) -> None:
        d = ArchDependency(
            from_module="src/api",
            to_module="src/db",
            dep_type="inheritance",
            weight=3,
            policy="forbidden",
        )
        assert d.dep_type == "inheritance"
        assert d.weight == 3
        assert d.policy == "forbidden"


class TestArchAbstraction:
    def test_creation_with_defaults(self) -> None:
        a = ArchAbstraction(
            symbol="validate_email",
            kind="function",
            module_path="src/utils/validators",
            file_path="src/utils/validators.py",
        )
        assert a.symbol == "validate_email"
        assert a.kind == "function"
        assert a.usage_count == 0
        assert a.consumers == []
        assert a.has_docstring is False
        assert a.is_exported is False

    def test_with_all_fields(self) -> None:
        a = ArchAbstraction(
            symbol="BaseSignal",
            kind="class",
            module_path="src/drift/signals",
            file_path="src/drift/signals/base.py",
            usage_count=24,
            consumers=["src/drift/signals/pfs", "src/drift/signals/mds"],
            has_docstring=True,
            is_exported=True,
        )
        assert a.usage_count == 24
        assert len(a.consumers) == 2
        assert a.has_docstring is True
        assert a.is_exported is True


class TestArchHotspot:
    def test_creation_with_defaults(self) -> None:
        h = ArchHotspot(path="src/api/auth.py")
        assert h.path == "src/api/auth.py"
        assert h.recurring_signals == {}
        assert h.trend == "stable"
        assert h.total_occurrences == 0

    def test_with_recurring_signals(self) -> None:
        h = ArchHotspot(
            path="src/api/auth.py",
            recurring_signals={"PFS": 3, "MDS": 2},
            trend="degrading",
            total_occurrences=5,
        )
        assert h.recurring_signals["PFS"] == 3
        assert h.trend == "degrading"
        assert h.total_occurrences == 5


# ---------------------------------------------------------------------------
# 2. ArchGraph construction and querying
# ---------------------------------------------------------------------------


class TestArchGraph:
    def _make_graph(self) -> ArchGraph:
        return ArchGraph(
            version="abc1234",
            modules=[
                ArchModule(path="src/api", drift_score=0.3, file_count=5, function_count=10),
                ArchModule(
                    path="src/db",
                    drift_score=0.6,
                    file_count=3,
                    function_count=8,
                    layer="data",
                ),
            ],
            dependencies=[
                ArchDependency(from_module="src/api", to_module="src/db"),
            ],
            abstractions=[
                ArchAbstraction(
                    symbol="get_user",
                    kind="function",
                    module_path="src/db",
                    file_path="src/db/users.py",
                    usage_count=5,
                    is_exported=True,
                ),
            ],
            hotspots=[
                ArchHotspot(
                    path="src/api/auth.py",
                    recurring_signals={"PFS": 3},
                    trend="degrading",
                    total_occurrences=3,
                ),
            ],
        )

    def test_construction(self) -> None:
        g = self._make_graph()
        assert g.version == "abc1234"
        assert len(g.modules) == 2
        assert len(g.dependencies) == 1
        assert len(g.abstractions) == 1
        assert len(g.hotspots) == 1
        assert g.updated_at > 0

    def test_get_module(self) -> None:
        g = self._make_graph()
        m = g.get_module("src/api")
        assert m is not None
        assert m.drift_score == 0.3

        assert g.get_module("nonexistent") is None

    def test_neighbors(self) -> None:
        g = self._make_graph()
        n = g.neighbors("src/api")
        assert "src/db" in n

        n2 = g.neighbors("src/db")
        assert "src/api" in n2

    def test_hotspots_for_path(self) -> None:
        g = self._make_graph()
        h = g.hotspots_for("src/api")
        assert len(h) == 1
        assert h[0].path == "src/api/auth.py"

        h2 = g.hotspots_for("src/db")
        assert len(h2) == 0

    def test_abstractions_in_module(self) -> None:
        g = self._make_graph()
        a = g.abstractions_in("src/db")
        assert len(a) == 1
        assert a[0].symbol == "get_user"


# ---------------------------------------------------------------------------
# 3. Serialization round-trip
# ---------------------------------------------------------------------------


class TestArchGraphSerialization:
    def test_to_dict_and_back(self) -> None:
        original = ArchGraph(
            version="abc1234",
            modules=[
                ArchModule(path="src/api", drift_score=0.3, file_count=5, function_count=10),
            ],
            dependencies=[
                ArchDependency(from_module="src/api", to_module="src/db"),
            ],
            abstractions=[
                ArchAbstraction(
                    symbol="foo",
                    kind="function",
                    module_path="src/api",
                    file_path="src/api/foo.py",
                ),
            ],
            hotspots=[],
        )

        d = original.to_dict()
        restored = ArchGraph.from_dict(d)

        assert restored.version == original.version
        assert len(restored.modules) == 1
        assert restored.modules[0].path == "src/api"
        assert restored.modules[0].drift_score == 0.3
        assert len(restored.dependencies) == 1
        assert restored.dependencies[0].from_module == "src/api"
        assert len(restored.abstractions) == 1
        assert restored.abstractions[0].symbol == "foo"

    def test_json_round_trip(self) -> None:
        original = ArchGraph(
            version="def5678",
            modules=[
                ArchModule(path="src/core", drift_score=0.1, file_count=2, function_count=4),
            ],
            dependencies=[],
            abstractions=[],
            hotspots=[],
        )

        json_str = json.dumps(original.to_dict(), indent=2)
        parsed = json.loads(json_str)
        restored = ArchGraph.from_dict(parsed)

        assert restored.version == "def5678"
        assert restored.modules[0].drift_score == 0.1


# ---------------------------------------------------------------------------
# 4. Graph persistence (disk-backed)
# ---------------------------------------------------------------------------


class TestArchGraphPersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        from drift.arch_graph import ArchGraphStore

        store = ArchGraphStore(cache_dir=tmp_path)
        graph = ArchGraph(
            version="abc1234",
            modules=[
                ArchModule(path="src/api", drift_score=0.3, file_count=5, function_count=10),
            ],
            dependencies=[],
            abstractions=[],
            hotspots=[],
        )

        store.save(graph)
        loaded = store.load()

        assert loaded is not None
        assert loaded.version == "abc1234"
        assert len(loaded.modules) == 1

    def test_load_returns_none_when_missing(self, tmp_path: Path) -> None:
        from drift.arch_graph import ArchGraphStore

        store = ArchGraphStore(cache_dir=tmp_path)
        assert store.load() is None

    def test_schema_version_mismatch_returns_none(self, tmp_path: Path) -> None:
        from drift.arch_graph import ArchGraphStore

        store = ArchGraphStore(cache_dir=tmp_path)
        graph = ArchGraph(
            version="abc1234",
            modules=[],
            dependencies=[],
            abstractions=[],
            hotspots=[],
        )
        store.save(graph)

        # Tamper with schema version
        graph_path = tmp_path / "arch_graph.json"
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        data["_schema_v"] = -1
        graph_path.write_text(json.dumps(data), encoding="utf-8")

        assert store.load() is None

    def test_corrupted_json_returns_none(self, tmp_path: Path) -> None:
        from drift.arch_graph import ArchGraphStore

        store = ArchGraphStore(cache_dir=tmp_path)
        graph_path = tmp_path / "arch_graph.json"
        graph_path.write_text("not valid json {{{", encoding="utf-8")

        assert store.load() is None


# ---------------------------------------------------------------------------
# 5. Graph seeding from drift analysis data
# ---------------------------------------------------------------------------


class TestArchGraphSeeding:
    def test_seed_from_modules_and_dependencies(self) -> None:
        from drift.arch_graph import seed_graph

        drift_map_result = {
            "modules": [
                {"path": "src/api", "files": 5, "functions": 10, "classes": 2,
                 "lines": 500, "languages": ["python"]},
                {"path": "src/db", "files": 3, "functions": 8, "classes": 1,
                 "lines": 300, "languages": ["python"]},
            ],
            "dependencies": [
                {"from": "src/api", "to": "src/db"},
            ],
        }

        graph = seed_graph(
            drift_map_result=drift_map_result,
            version="abc1234",
        )

        assert graph.version == "abc1234"
        assert len(graph.modules) == 2
        assert graph.get_module("src/api") is not None
        assert graph.get_module("src/api").file_count == 5
        assert graph.get_module("src/api").languages == ["python"]
        assert len(graph.dependencies) == 1
        assert graph.dependencies[0].from_module == "src/api"
        assert graph.dependencies[0].to_module == "src/db"

    def test_seed_with_module_scores(self) -> None:
        from drift.arch_graph import seed_graph

        drift_map_result = {
            "modules": [
                {"path": "src/api", "files": 5, "functions": 10, "classes": 2,
                 "lines": 500, "languages": ["python"]},
            ],
            "dependencies": [],
        }

        module_scores = {
            "src/api": {"drift_score": 0.4, "signal_scores": {"PFS": 0.3, "AVS": 0.1}},
        }

        graph = seed_graph(
            drift_map_result=drift_map_result,
            version="abc1234",
            module_scores=module_scores,
        )

        m = graph.get_module("src/api")
        assert m is not None
        assert m.drift_score == 0.4
        assert m.signal_scores == {"PFS": 0.3, "AVS": 0.1}

    def test_seed_with_parse_results_extracts_abstractions(self) -> None:
        from drift.arch_graph import seed_graph
        from drift.models import ClassInfo, FunctionInfo, ParseResult

        parse_results = [
            ParseResult(
                file_path=Path("src/api/handlers.py"),
                language="python",
                functions=[
                    FunctionInfo(
                        name="handle_request",
                        file_path=Path("src/api/handlers.py"),
                        start_line=10,
                        end_line=30,
                        language="python",
                        has_docstring=True,
                        is_exported=True,
                    ),
                    FunctionInfo(
                        name="_helper",
                        file_path=Path("src/api/handlers.py"),
                        start_line=32,
                        end_line=40,
                        language="python",
                        is_exported=False,
                    ),
                ],
                classes=[
                    ClassInfo(
                        name="RequestHandler",
                        file_path=Path("src/api/handlers.py"),
                        start_line=1,
                        end_line=50,
                        language="python",
                        has_docstring=True,
                        is_exported=True,
                    ),
                ],
            ),
        ]

        drift_map_result = {
            "modules": [
                {"path": "src/api", "files": 1, "functions": 2, "classes": 1,
                 "lines": 50, "languages": ["python"]},
            ],
            "dependencies": [],
        }

        graph = seed_graph(
            drift_map_result=drift_map_result,
            version="abc1234",
            parse_results=parse_results,
        )

        # Only exported symbols become abstractions
        exported = [a for a in graph.abstractions if a.is_exported]
        assert len(exported) == 2  # handle_request + RequestHandler
        symbols = {a.symbol for a in exported}
        assert "handle_request" in symbols
        assert "RequestHandler" in symbols
        assert "_helper" not in symbols

    def test_seed_with_layer_boundaries(self) -> None:
        from drift.arch_graph import seed_graph

        drift_map_result = {
            "modules": [
                {"path": "src/api", "files": 5, "functions": 10, "classes": 2,
                 "lines": 500, "languages": ["python"]},
                {"path": "src/db", "files": 3, "functions": 8, "classes": 1,
                 "lines": 300, "languages": ["python"]},
            ],
            "dependencies": [
                {"from": "src/api", "to": "src/db"},
            ],
        }

        layer_boundaries = [
            {"name": "api_no_db", "from": "src/api", "deny_import": ["src/db"]},
        ]

        graph = seed_graph(
            drift_map_result=drift_map_result,
            version="abc1234",
            layer_boundaries=layer_boundaries,
        )

        # Dependency should have policy annotation
        dep = graph.dependencies[0]
        assert dep.policy == "forbidden"

    def test_seed_empty_map(self) -> None:
        from drift.arch_graph import seed_graph

        graph = seed_graph(
            drift_map_result={"modules": [], "dependencies": []},
            version="abc1234",
        )

        assert len(graph.modules) == 0
        assert len(graph.dependencies) == 0
        assert len(graph.abstractions) == 0
