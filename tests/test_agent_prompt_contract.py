"""Contract tests for the agent prompt generator (ADR-089).

These tests guard the autonomous agent regelkreis sections emitted by
``drift.intent.handoff.handoff``. They intentionally do not assert full
string equality so contract wording can evolve, but every required section
header and every severity gate row must be present.
"""

from __future__ import annotations

from typing import Any

import pytest

from drift.intent.handoff import (
    REQUIRED_SECTIONS,
    SECTION_APPROVAL_GATE,
    SECTION_FEEDBACK_LOOP,
    SECTION_REGELKREIS,
    SECTION_ROLLBACK,
    SECTION_SEVERITY_GATE,
    SECTION_TRIGGER,
    _gate_decision_for,
    handoff,
)


def _intent(contracts: list[dict[str, Any]]) -> dict[str, Any]:
    return {"category": "utility", "contracts": contracts}


class TestRequiredSections:
    def test_all_required_sections_present(self) -> None:
        result = handoff("test prompt", _intent([]))
        for header in REQUIRED_SECTIONS:
            assert header in result, f"missing section: {header}"

    def test_sections_appear_in_expected_order(self) -> None:
        result = handoff("test prompt", _intent([]))
        indices = [result.index(h) for h in REQUIRED_SECTIONS]
        assert indices == sorted(indices), "Regelkreis sections must appear in the documented order"

    def test_validation_command_is_phase4_run(self) -> None:
        """Bug-fix (ADR-089): must reference `drift intent run --phase 4`."""
        result = handoff("test prompt", _intent([]))
        assert "drift intent run --phase 4" in result
        # The incorrect legacy form must no longer appear.
        assert "drift intent --phase 4" not in result.replace("drift intent run --phase 4", "")


class TestSeverityGateMapping:
    @pytest.mark.parametrize(
        ("severity", "auto_repair", "expected"),
        [
            ("critical", True, "BLOCK"),
            ("critical", False, "BLOCK"),
            ("high", True, "BLOCK"),
            ("high", False, "BLOCK"),
            ("medium", True, "REVIEW"),
            ("medium", False, "REVIEW"),
            ("low", True, "AUTO"),
            ("low", False, "REVIEW"),
            ("info", True, "AUTO"),
            ("info", False, "REVIEW"),
        ],
    )
    def test_gate_routing(self, severity: str, auto_repair: bool, expected: str) -> None:
        contract = {
            "id": "x",
            "severity": severity,
            "auto_repair_eligible": auto_repair,
            "description_technical": "t",
        }
        assert _gate_decision_for(contract) == expected

    def test_gate_table_headers_rendered(self) -> None:
        result = handoff("test prompt", _intent([]))
        gate_idx = result.index(SECTION_SEVERITY_GATE)
        gate_section = result[gate_idx : gate_idx + 2000]
        assert "| Severity | auto_repair_eligible | Gate | Aktion |" in gate_section
        for bucket in ("`AUTO`", "`REVIEW`", "`BLOCK`"):
            assert bucket in gate_section

    def test_per_contract_routing_rendered(self) -> None:
        contracts = [
            {
                "id": "c-crit",
                "severity": "critical",
                "auto_repair_eligible": True,
                "description_technical": "x",
            },
            {
                "id": "c-low",
                "severity": "low",
                "auto_repair_eligible": True,
                "description_technical": "y",
            },
        ]
        result = handoff("p", _intent(contracts))
        assert "c-crit" in result and "`BLOCK`" in result
        assert "c-low" in result and "`AUTO`" in result


class TestTriggerAndFeedbackAnchors:
    def test_trigger_references_nudge(self) -> None:
        result = handoff("p", _intent([]))
        trigger_idx = result.index(SECTION_TRIGGER)
        regel_idx = result.index(SECTION_REGELKREIS)
        trigger_section = result[trigger_idx:regel_idx]
        assert "drift_nudge" in trigger_section

    def test_feedback_loop_references_drift_feedback(self) -> None:
        result = handoff("p", _intent([]))
        idx = result.index(SECTION_FEEDBACK_LOOP)
        section = result[idx : idx + 1000]
        assert "drift feedback" in section

    def test_approval_gate_mentions_bypass_guard(self) -> None:
        result = handoff("p", _intent([]))
        idx = result.index(SECTION_APPROVAL_GATE)
        section = result[idx : idx + 1500]
        assert "verify_gate_not_bypassed" in section
        assert "drift/approved" in section

    def test_rollback_references_revert_recommended(self) -> None:
        result = handoff("p", _intent([]))
        idx = result.index(SECTION_ROLLBACK)
        section = result[idx : idx + 1000]
        assert "revert_recommended" in section
