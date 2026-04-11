"""Tests for drift.tool_metadata — static tool cost/context catalog.

Decision: ADR-029
"""

from __future__ import annotations

from drift.tool_metadata import (
    SESSION_PHASES,
    TOOL_CATALOG,
    ToolContextHint,
    ToolCostMetadata,
    ToolMetadataEntry,
    metadata_as_dict,
    tools_for_phase,
)


class TestToolCatalog:
    def test_catalog_has_all_tools(self):
        expected_tools = {
            "drift_scan",
            "drift_diff",
            "drift_explain",
            "drift_fix_plan",
            "drift_validate",
            "drift_nudge",
            "drift_brief",
            "drift_negative_context",
            "drift_session_start",
            "drift_session_status",
            "drift_session_update",
            "drift_session_end",
            "drift_task_claim",
            "drift_task_renew",
            "drift_task_release",
            "drift_task_complete",
            "drift_task_status",
        }
        assert expected_tools.issubset(set(TOOL_CATALOG.keys()))

    def test_every_entry_has_cost(self):
        for name, entry in TOOL_CATALOG.items():
            assert entry.cost.cost in ("low", "medium", "high"), f"{name}: bad cost"
            assert entry.cost.risk in ("none", "low", "medium"), f"{name}: bad risk"
            assert entry.cost.typical_latency_ms > 0, f"{name}: bad latency"
            assert entry.cost.token_estimate > 0, f"{name}: bad token est"

    def test_every_entry_has_context_hint(self):
        for name, entry in TOOL_CATALOG.items():
            assert entry.context.when_to_use, f"{name}: missing when_to_use"

    def test_phases_defined(self):
        assert "init" in SESSION_PHASES
        assert "done" in SESSION_PHASES


class TestToolsForPhase:
    def test_init_phase(self):
        tools = tools_for_phase("init")
        assert "drift_validate" in tools
        assert "drift_session_start" in tools
        # drift_nudge should NOT be in init
        assert "drift_nudge" not in tools

    def test_fix_phase(self):
        tools = tools_for_phase("fix")
        assert "drift_nudge" in tools
        assert "drift_task_claim" in tools

    def test_verify_phase(self):
        tools = tools_for_phase("verify")
        assert "drift_diff" in tools

    def test_unknown_phase_returns_all(self):
        tools = tools_for_phase("unknown_phase")
        assert len(tools) == len(TOOL_CATALOG)


class TestMetadataAsDict:
    def test_serialisation(self):
        entry = ToolMetadataEntry(
            name="test_tool",
            cost=ToolCostMetadata("low", "none", 100, 50),
            context=ToolContextHint(
                when_to_use="Testing.",
                when_not_to_use="Never in prod.",
                prerequisite_tools=("drift_validate",),
                follow_up_tools=("drift_scan",),
            ),
            phases=("init",),
        )
        d = metadata_as_dict(entry)
        assert d["name"] == "test_tool"
        assert d["cost"] == "low"
        assert d["risk"] == "none"
        assert d["typical_latency_ms"] == 100
        assert d["prerequisite_tools"] == ["drift_validate"]
        assert d["phases"] == ["init"]
