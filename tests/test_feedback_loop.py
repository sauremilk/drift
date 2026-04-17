"""Tests for Feedback Loop — Phase E of the Architecture Runtime Blueprint.

The feedback loop detects recurring drift patterns in ArchGraph hotspots
and proposes new ArchDecision rules to prevent future occurrences.
"""

from __future__ import annotations

import json
from pathlib import Path

from drift.arch_graph._models import (
    ArchDecision,
    ArchDependency,
    ArchGraph,
    ArchHotspot,
    ArchModule,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_graph_with_hotspots() -> ArchGraph:
    """Graph with realistic hotspots for pattern detection."""
    return ArchGraph(
        version="feedback-test",
        modules=[
            ArchModule(
                path="src/api",
                drift_score=0.6,
                file_count=5,
                function_count=12,
                layer="presentation",
            ),
            ArchModule(
                path="src/signals",
                drift_score=0.3,
                file_count=8,
                function_count=20,
                layer="domain",
            ),
            ArchModule(
                path="src/db",
                drift_score=0.2,
                file_count=3,
                function_count=8,
                layer="data",
            ),
        ],
        dependencies=[
            ArchDependency(from_module="src/api", to_module="src/signals"),
            ArchDependency(from_module="src/api", to_module="src/db"),
        ],
        abstractions=[],
        hotspots=[
            # High-recurrence: pattern_fragmentation in api
            ArchHotspot(
                path="src/api/handlers.py",
                recurring_signals={"pattern_fragmentation": 8, "naming_contract_violation": 3},
                trend="degrading",
                total_occurrences=11,
            ),
            # High-recurrence: architecture_violation in api
            ArchHotspot(
                path="src/api/auth.py",
                recurring_signals={"architecture_violation": 6},
                trend="degrading",
                total_occurrences=6,
            ),
            # Moderate but stable — should NOT trigger proposal
            ArchHotspot(
                path="src/signals/base.py",
                recurring_signals={"doc_impl_drift": 2},
                trend="stable",
                total_occurrences=2,
            ),
            # Low count — below threshold
            ArchHotspot(
                path="src/db/models.py",
                recurring_signals={"naming_contract_violation": 1},
                trend="stable",
                total_occurrences=1,
            ),
        ],
        decisions=[
            # Existing decision — should not be duplicated
            ArchDecision(
                id="DEC-001",
                scope="src/api/**",
                rule="All mutations must go through service layer",
                enforcement="warn",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# 1. PatternProposal data model
# ---------------------------------------------------------------------------


class TestPatternProposal:
    def test_construction_with_defaults(self) -> None:
        from drift.arch_graph._models import PatternProposal

        p = PatternProposal(
            pattern_type="recurring_signal",
            module_path="src/api",
            signal_id="pattern_fragmentation",
            occurrences=8,
            proposed_decision=ArchDecision(
                id="PROP-001",
                scope="src/api/**",
                rule="Refactor duplicated patterns in api module",
                enforcement="warn",
            ),
            confidence=0.85,
        )
        assert p.status == "proposed"
        assert p.confidence == 0.85
        assert p.proposed_decision.id == "PROP-001"

    def test_construction_full(self) -> None:
        from drift.arch_graph._models import PatternProposal

        p = PatternProposal(
            pattern_type="boundary_violation",
            module_path="src/api",
            signal_id="architecture_violation",
            occurrences=6,
            proposed_decision=ArchDecision(
                id="PROP-002",
                scope="src/api/**",
                rule="No direct db access from api layer",
                enforcement="block",
            ),
            confidence=0.92,
            status="accepted",
            evidence_files=["src/api/auth.py"],
        )
        assert p.status == "accepted"
        assert p.evidence_files == ["src/api/auth.py"]

    def test_to_dict(self) -> None:
        from drift.arch_graph._models import PatternProposal

        p = PatternProposal(
            pattern_type="recurring_signal",
            module_path="src/api",
            signal_id="pattern_fragmentation",
            occurrences=5,
            proposed_decision=ArchDecision(
                id="PROP-003",
                scope="src/api/**",
                rule="Test rule",
                enforcement="info",
            ),
            confidence=0.7,
        )
        d = p.to_dict()
        assert d["pattern_type"] == "recurring_signal"
        assert d["proposed_decision"]["id"] == "PROP-003"
        assert d["status"] == "proposed"
        # JSON-safe
        json.dumps(d)


# ---------------------------------------------------------------------------
# 2. detect_recurring_patterns
# ---------------------------------------------------------------------------


class TestDetectRecurringPatterns:
    def test_detects_degrading_hotspots(self) -> None:
        from drift.arch_graph._feedback import detect_recurring_patterns

        graph = _make_graph_with_hotspots()
        patterns = detect_recurring_patterns(graph)

        # Should find patterns for degrading hotspots with high recurrence
        assert len(patterns) >= 1
        signal_ids = {p.signal_id for p in patterns}
        assert "pattern_fragmentation" in signal_ids

    def test_respects_min_occurrences(self) -> None:
        from drift.arch_graph._feedback import detect_recurring_patterns

        graph = _make_graph_with_hotspots()
        # With high threshold, fewer patterns
        patterns_high = detect_recurring_patterns(graph, min_occurrences=10)
        patterns_low = detect_recurring_patterns(graph, min_occurrences=3)

        assert len(patterns_high) < len(patterns_low)

    def test_excludes_stable_low_count(self) -> None:
        from drift.arch_graph._feedback import detect_recurring_patterns

        graph = _make_graph_with_hotspots()
        patterns = detect_recurring_patterns(graph, min_occurrences=3)

        # src/db/models.py has only 1 naming_contract_violation — too low
        module_signals = {(p.module_path, p.signal_id) for p in patterns}
        assert ("src/db", "naming_contract_violation") not in module_signals

    def test_empty_hotspots_returns_empty(self) -> None:
        from drift.arch_graph._feedback import detect_recurring_patterns

        graph = ArchGraph(version="empty", hotspots=[])
        patterns = detect_recurring_patterns(graph)
        assert patterns == []

    def test_degrading_trend_boosts_confidence(self) -> None:
        from drift.arch_graph._feedback import detect_recurring_patterns

        graph = _make_graph_with_hotspots()
        patterns = detect_recurring_patterns(graph, min_occurrences=3)

        # Find the pattern for the degrading hotspot
        degrading = [p for p in patterns if p.signal_id == "pattern_fragmentation"]
        stable = [
            p for p in patterns
            if p.signal_id == "naming_contract_violation" and p.module_path == "src/api"
        ]

        if degrading and stable:
            assert degrading[0].confidence >= stable[0].confidence

    def test_aggregates_by_module(self) -> None:
        from drift.arch_graph._feedback import detect_recurring_patterns

        graph = _make_graph_with_hotspots()
        patterns = detect_recurring_patterns(graph, min_occurrences=3)

        # pattern_fragmentation appears only in src/api/handlers.py
        # Should be aggregated to module src/api
        pf_patterns = [p for p in patterns if p.signal_id == "pattern_fragmentation"]
        assert len(pf_patterns) == 1
        assert pf_patterns[0].module_path == "src/api"


# ---------------------------------------------------------------------------
# 3. propose_decisions — converts patterns to ArchDecision proposals
# ---------------------------------------------------------------------------


class TestProposeDecisions:
    def test_generates_proposals(self) -> None:
        from drift.arch_graph._feedback import propose_decisions

        graph = _make_graph_with_hotspots()
        proposals = propose_decisions(graph)

        assert len(proposals) >= 1
        for p in proposals:
            assert p.status == "proposed"
            assert p.proposed_decision.scope.endswith("**")
            assert p.proposed_decision.active is True

    def test_skips_already_covered_scopes(self) -> None:
        from drift.arch_graph._feedback import propose_decisions

        graph = _make_graph_with_hotspots()
        proposals = propose_decisions(graph)

        # graph already has DEC-001 for src/api/** — proposals for src/api
        # should still be generated (different signal_id means different concern)
        # but verify no exact-duplicate rule text
        existing_rules = {d.rule for d in graph.decisions}
        for p in proposals:
            assert p.proposed_decision.rule not in existing_rules

    def test_proposal_ids_are_unique(self) -> None:
        from drift.arch_graph._feedback import propose_decisions

        graph = _make_graph_with_hotspots()
        proposals = propose_decisions(graph)

        ids = [p.proposed_decision.id for p in proposals]
        assert len(ids) == len(set(ids))

    def test_enforcement_based_on_severity(self) -> None:
        from drift.arch_graph._feedback import propose_decisions

        graph = _make_graph_with_hotspots()
        proposals = propose_decisions(graph)

        # architecture_violation with 6 occurrences + degrading trend
        avs = [p for p in proposals if p.signal_id == "architecture_violation"]
        if avs:
            # High-severity recurring boundary violations → warn or block
            assert avs[0].proposed_decision.enforcement in ("warn", "block")

    def test_empty_graph_returns_empty(self) -> None:
        from drift.arch_graph._feedback import propose_decisions

        graph = ArchGraph(version="empty", hotspots=[])
        proposals = propose_decisions(graph)
        assert proposals == []


# ---------------------------------------------------------------------------
# 4. suggest_rules() API endpoint
# ---------------------------------------------------------------------------


class TestSuggestRulesAPI:
    def test_returns_ok_with_proposals(self, tmp_path: Path) -> None:
        from drift.api.suggest_rules import suggest_rules
        from drift.arch_graph import ArchGraphStore

        graph = _make_graph_with_hotspots()
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = suggest_rules(
            path=str(tmp_path),
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        assert result["status"] == "ok"
        assert "proposals" in result
        assert len(result["proposals"]) >= 1
        assert "agent_instruction" in result

    def test_no_graph_returns_error(self, tmp_path: Path) -> None:
        from drift.api.suggest_rules import suggest_rules

        result = suggest_rules(
            path=str(tmp_path),
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        assert result.get("status") == "error" or result.get("type") == "error"

    def test_no_proposals_returns_ok(self, tmp_path: Path) -> None:
        from drift.api.suggest_rules import suggest_rules
        from drift.arch_graph import ArchGraphStore

        # Graph with no hotspots
        graph = ArchGraph(
            version="clean",
            modules=[
                ArchModule(
                    path="src/core",
                    drift_score=0.1,
                    file_count=3,
                    function_count=5,
                ),
            ],
        )
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = suggest_rules(
            path=str(tmp_path),
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        assert result["status"] == "ok"
        assert result["proposals"] == []

    def test_min_occurrences_parameter(self, tmp_path: Path) -> None:
        from drift.api.suggest_rules import suggest_rules
        from drift.arch_graph import ArchGraphStore

        graph = _make_graph_with_hotspots()
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result_strict = suggest_rules(
            path=str(tmp_path),
            cache_dir=str(tmp_path / ".drift-cache"),
            min_occurrences=10,
        )
        result_loose = suggest_rules(
            path=str(tmp_path),
            cache_dir=str(tmp_path / ".drift-cache"),
            min_occurrences=3,
        )

        assert len(result_strict["proposals"]) <= len(result_loose["proposals"])

    def test_proposals_json_serializable(self, tmp_path: Path) -> None:
        from drift.api.suggest_rules import suggest_rules
        from drift.arch_graph import ArchGraphStore

        graph = _make_graph_with_hotspots()
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = suggest_rules(
            path=str(tmp_path),
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        json.dumps(result)  # must not raise

    def test_agent_instruction_mentions_proposals(self, tmp_path: Path) -> None:
        from drift.api.suggest_rules import suggest_rules
        from drift.arch_graph import ArchGraphStore

        graph = _make_graph_with_hotspots()
        store = ArchGraphStore(cache_dir=tmp_path / ".drift-cache")
        store.save(graph)

        result = suggest_rules(
            path=str(tmp_path),
            cache_dir=str(tmp_path / ".drift-cache"),
        )

        assert "proposal" in result["agent_instruction"].lower() or \
               "rule" in result["agent_instruction"].lower()
