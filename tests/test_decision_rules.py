"""Tests for Decision Rules — Phase D of the Architecture Runtime Blueprint.

ArchDecision provides machine-readable architecture decisions that constrain
code generation.  Decisions are stored in the ArchGraph and matched by scope
(glob patterns) against target paths in steer().
"""

from __future__ import annotations

import json
from pathlib import Path

from drift.arch_graph import (
    ArchDependency,
    ArchGraph,
    ArchGraphStore,
    ArchModule,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_decisions() -> list:
    """Import-safe: returns ArchDecision objects."""
    from drift.arch_graph._models import ArchDecision

    return [
        ArchDecision(
            id="DEC-001",
            scope="src/api/**",
            rule="All mutations must go through the service layer",
            enforcement="warn",
            source="decisions/ADR-036.md",
        ),
        ArchDecision(
            id="DEC-002",
            scope="src/signals/**",
            rule="New signals must inherit BaseSignal and use @register_signal",
            enforcement="block",
            source="decisions/ADR-013.md",
        ),
        ArchDecision(
            id="DEC-003",
            scope="src/db/**",
            rule="No direct SQL queries — use the query builder",
            enforcement="warn",
        ),
        ArchDecision(
            id="DEC-004",
            scope="**/*.py",
            rule="All public functions must have docstrings",
            enforcement="info",
        ),
        ArchDecision(
            id="DEC-005",
            scope="src/api/auth.py",
            rule="Auth endpoints require security review",
            enforcement="block",
            active=False,  # disabled
        ),
    ]


def _make_graph_with_decisions() -> ArchGraph:

    return ArchGraph(
        version="dec-test",
        modules=[
            ArchModule(
                path="src/api",
                drift_score=0.3,
                file_count=5,
                function_count=10,
                layer="presentation",
            ),
            ArchModule(
                path="src/signals",
                drift_score=0.2,
                file_count=8,
                function_count=20,
                layer="domain",
            ),
            ArchModule(
                path="src/db",
                drift_score=0.4,
                file_count=3,
                function_count=8,
                layer="data",
            ),
        ],
        dependencies=[
            ArchDependency(from_module="src/api", to_module="src/signals"),
        ],
        abstractions=[],
        hotspots=[],
        decisions=_make_decisions(),
    )


# ---------------------------------------------------------------------------
# 1. ArchDecision data model
# ---------------------------------------------------------------------------


class TestArchDecision:
    def test_construction_with_defaults(self) -> None:
        from drift.arch_graph._models import ArchDecision

        d = ArchDecision(
            id="DEC-001",
            scope="src/**",
            rule="Test rule",
            enforcement="warn",
        )
        assert d.id == "DEC-001"
        assert d.source is None
        assert d.active is True

    def test_construction_full(self) -> None:
        from drift.arch_graph._models import ArchDecision

        d = ArchDecision(
            id="DEC-002",
            scope="src/api/**",
            rule="All endpoints must validate input",
            enforcement="block",
            source="decisions/ADR-015.md",
            active=False,
        )
        assert d.enforcement == "block"
        assert d.source == "decisions/ADR-015.md"
        assert d.active is False

    def test_enforcement_values(self) -> None:
        from drift.arch_graph._models import ArchDecision

        for level in ("info", "warn", "block"):
            d = ArchDecision(
                id="X", scope="**", rule="r", enforcement=level
            )
            assert d.enforcement == level


# ---------------------------------------------------------------------------
# 2. ArchGraph serialization with decisions
# ---------------------------------------------------------------------------


class TestArchGraphDecisionSerialization:
    def test_to_dict_includes_decisions(self) -> None:
        graph = _make_graph_with_decisions()
        d = graph.to_dict()

        assert "decisions" in d
        assert len(d["decisions"]) == 5
        assert d["decisions"][0]["id"] == "DEC-001"

    def test_from_dict_restores_decisions(self) -> None:
        from drift.arch_graph._models import ArchDecision

        graph = _make_graph_with_decisions()
        d = graph.to_dict()
        restored = ArchGraph.from_dict(d)

        assert len(restored.decisions) == 5
        assert isinstance(restored.decisions[0], ArchDecision)
        assert restored.decisions[0].id == "DEC-001"
        assert restored.decisions[4].active is False

    def test_from_dict_without_decisions_defaults_empty(self) -> None:
        data = {
            "version": "v1",
            "modules": [],
            "dependencies": [],
            "abstractions": [],
            "hotspots": [],
        }
        graph = ArchGraph.from_dict(data)
        assert graph.decisions == []

    def test_round_trip_json(self) -> None:
        graph = _make_graph_with_decisions()
        json_str = json.dumps(graph.to_dict())
        restored = ArchGraph.from_dict(json.loads(json_str))

        assert len(restored.decisions) == len(graph.decisions)
        for orig, rest in zip(graph.decisions, restored.decisions, strict=True):
            assert orig.id == rest.id
            assert orig.scope == rest.scope
            assert orig.enforcement == rest.enforcement


# ---------------------------------------------------------------------------
# 3. match_decisions — scope-based matching
# ---------------------------------------------------------------------------


class TestMatchDecisions:
    def test_match_module_scope(self) -> None:
        from drift.arch_graph._decisions import match_decisions

        decisions = _make_decisions()
        matched = match_decisions(decisions, target="src/api/users.py")

        ids = {d.id for d in matched}
        assert "DEC-001" in ids  # src/api/**
        assert "DEC-004" in ids  # **/*.py

    def test_no_match_for_unrelated_target(self) -> None:
        from drift.arch_graph._decisions import match_decisions

        decisions = _make_decisions()
        matched = match_decisions(decisions, target="lib/external/tool.rs")

        # Only DEC-004 (**/*.py) would match .py files but .rs won't
        ids = {d.id for d in matched}
        assert "DEC-001" not in ids
        assert "DEC-002" not in ids
        assert "DEC-003" not in ids

    def test_inactive_decisions_excluded(self) -> None:
        from drift.arch_graph._decisions import match_decisions

        decisions = _make_decisions()
        # DEC-005 scope matches src/api/auth.py but it's inactive
        matched = match_decisions(decisions, target="src/api/auth.py")

        ids = {d.id for d in matched}
        assert "DEC-005" not in ids

    def test_include_inactive_when_requested(self) -> None:
        from drift.arch_graph._decisions import match_decisions

        decisions = _make_decisions()
        matched = match_decisions(
            decisions, target="src/api/auth.py", include_inactive=True
        )

        ids = {d.id for d in matched}
        assert "DEC-005" in ids

    def test_enforcement_filter(self) -> None:
        from drift.arch_graph._decisions import match_decisions

        decisions = _make_decisions()
        matched = match_decisions(
            decisions,
            target="src/signals/new_signal.py",
            enforcement="block",
        )

        # Only DEC-002 (block) should match — DEC-004 is info
        assert all(d.enforcement == "block" for d in matched)

    def test_match_exact_file_path(self) -> None:
        from drift.arch_graph._decisions import match_decisions

        decisions = _make_decisions()
        matched = match_decisions(decisions, target="src/db/queries.py")

        ids = {d.id for d in matched}
        assert "DEC-003" in ids  # src/db/**
        assert "DEC-004" in ids  # **/*.py

    def test_match_module_path(self) -> None:
        from drift.arch_graph._decisions import match_decisions

        decisions = _make_decisions()
        # Module path without file extension
        matched = match_decisions(decisions, target="src/api/routes")

        ids = {d.id for d in matched}
        assert "DEC-001" in ids  # src/api/**


# ---------------------------------------------------------------------------
# 4. format_decision_constraints — for steer() output
# ---------------------------------------------------------------------------


class TestFormatDecisionConstraints:
    def test_format_basic(self) -> None:
        from drift.arch_graph._decisions import format_decision_constraints

        decisions = _make_decisions()[:2]  # DEC-001 (warn) + DEC-002 (block)
        result = format_decision_constraints(decisions)

        assert len(result) == 2
        # Sorted by enforcement: block first, then warn
        assert result[0]["id"] == "DEC-002"
        assert result[0]["enforcement"] == "block"
        assert result[1]["id"] == "DEC-001"
        assert result[1]["enforcement"] == "warn"
        assert "rule" in result[0]
        assert "source" in result[0]

    def test_format_sorted_by_enforcement(self) -> None:
        from drift.arch_graph._decisions import format_decision_constraints

        decisions = _make_decisions()[:4]
        result = format_decision_constraints(decisions)

        # block > warn > info
        enforcements = [r["enforcement"] for r in result]
        expected_order = {"block": 0, "warn": 1, "info": 2}
        for i in range(len(enforcements) - 1):
            assert expected_order[enforcements[i]] <= expected_order[enforcements[i + 1]]

    def test_format_json_serializable(self) -> None:
        from drift.arch_graph._decisions import format_decision_constraints

        decisions = _make_decisions()
        result = format_decision_constraints(decisions)
        json.dumps(result)  # must not raise

    def test_format_empty(self) -> None:
        from drift.arch_graph._decisions import format_decision_constraints

        result = format_decision_constraints([])
        assert result == []


# ---------------------------------------------------------------------------
# 5. steer() integration with decisions
# ---------------------------------------------------------------------------


class TestSteerDecisionIntegration:
    def test_steer_returns_decision_constraints(self, tmp_path: Path) -> None:
        from drift.api.steer import steer

        graph = _make_graph_with_decisions()
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = steer(
            path=str(tmp_path),
            target="src/api/users.py",
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        assert result["status"] == "ok"
        assert "decision_constraints" in result
        assert len(result["decision_constraints"]) > 0

        # DEC-001 should be present (src/api/**)
        ids = {c["id"] for c in result["decision_constraints"]}
        assert "DEC-001" in ids

    def test_steer_without_decisions_returns_empty(self, tmp_path: Path) -> None:
        from drift.api.steer import steer

        # Graph without decisions
        graph = ArchGraph(
            version="no-dec",
            modules=[
                ArchModule(
                    path="src/api",
                    drift_score=0.2,
                    file_count=3,
                    function_count=5,
                ),
            ],
            dependencies=[],
            abstractions=[],
            hotspots=[],
        )
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = steer(
            path=str(tmp_path),
            target="src/api/test.py",
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        assert result["decision_constraints"] == []

    def test_steer_block_decisions_in_agent_instruction(
        self, tmp_path: Path
    ) -> None:
        from drift.api.steer import steer

        graph = _make_graph_with_decisions()
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = steer(
            path=str(tmp_path),
            target="src/signals/new_signal.py",
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        # DEC-002 is a block-level decision for src/signals/**
        assert "BLOCK" in result["agent_instruction"]
