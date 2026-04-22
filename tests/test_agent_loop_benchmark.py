"""Contract tests for the Paket 3A E2E Agent-Loop-Benchmark (ADR-089/ADR-090).

Tests:
- gate_for_contract() routing: all severity × auto_repair_eligible combinations
- run_profile() computes correct counts and creates correct action entries
- build_agent_telemetry() produces schema-2.2-compatible AgentTelemetry
- Three reference profiles pass their own assertions end-to-end
- Integration: drift.models AgentTelemetry counters match gate routing
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.contract

# ---------------------------------------------------------------------------
# Load the benchmark script as a module (it lives in scripts/, not a package)
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = _ROOT / "scripts" / "run_agent_loop_benchmark.py"


def _load_benchmark() -> types.ModuleType:
    module_name = "run_agent_loop_benchmark"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, _SCRIPT_PATH)
    assert spec is not None, f"Cannot locate script at {_SCRIPT_PATH}"
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Module-level load — fail the whole module early if the script is missing
bm = _load_benchmark()

# Convenience aliases
gate_for_contract = bm.gate_for_contract
run_profile = bm.run_profile
build_agent_telemetry = bm.build_agent_telemetry
ProfileResult = bm.ProfileResult
_assert_distribution = bm._assert_distribution
_high_quality_expected_auto = bm._high_quality_expected_auto
_load_drift_self_profile = bm._load_drift_self_profile
_HIGH_QUALITY_PROFILE = bm._HIGH_QUALITY_PROFILE
_LEGACY_SERVICE_PROFILE = bm._LEGACY_SERVICE_PROFILE
_DRIFT_SELF_ASSERTIONS = bm._DRIFT_SELF_ASSERTIONS
_LEGACY_SERVICE_ASSERTIONS = bm._LEGACY_SERVICE_ASSERTIONS


# ---------------------------------------------------------------------------
# gate_for_contract — all severity × auto_repair_eligible combinations
# ---------------------------------------------------------------------------


class TestGateForContract:
    @pytest.mark.parametrize(
        ("severity", "auto_repair", "expected_gate"),
        [
            # BLOCK — severity always overrides auto_repair
            ("critical", True,  "BLOCK"),
            ("critical", False, "BLOCK"),
            ("high",     True,  "BLOCK"),
            ("high",     False, "BLOCK"),
            # REVIEW — medium regardless of auto_repair
            ("medium",   True,  "REVIEW"),
            ("medium",   False, "REVIEW"),
            # AUTO / REVIEW split for low/info
            ("low",      True,  "AUTO"),
            ("low",      False, "REVIEW"),
            ("info",     True,  "AUTO"),
            ("info",     False, "REVIEW"),
            # Unrecognised severity treated as low (not medium/high/critical)
            ("unknown",  True,  "AUTO"),
            ("unknown",  False, "REVIEW"),
        ],
    )
    def test_gate_routing(
        self, severity: str, auto_repair: bool | None, expected_gate: str
    ) -> None:
        contract = {"severity": severity, "auto_repair_eligible": auto_repair}
        assert gate_for_contract(contract) == expected_gate

    def test_missing_severity_defaults_to_review(self) -> None:
        """Missing severity defaults to medium-like behaviour → REVIEW."""
        assert gate_for_contract({}) == "REVIEW"
        assert gate_for_contract({"auto_repair_eligible": True}) == "REVIEW"

    def test_case_insensitive_severity(self) -> None:
        assert gate_for_contract({"severity": "HIGH"}) == "BLOCK"
        assert gate_for_contract({"severity": "Critical"}) == "BLOCK"
        assert gate_for_contract({"severity": "MEDIUM"}) == "REVIEW"


# ---------------------------------------------------------------------------
# run_profile — count and action generation
# ---------------------------------------------------------------------------


class TestRunProfile:
    def _minimal_contracts(self) -> list[dict[str, Any]]:
        return [
            {"id": "c1", "severity": "low",    "auto_repair_eligible": True},   # AUTO
            {"id": "c2", "severity": "medium",  "auto_repair_eligible": True},   # REVIEW
            {"id": "c3", "severity": "high",    "auto_repair_eligible": False},  # BLOCK
        ]

    def test_count_matches_gate_routing(self) -> None:
        result = run_profile("test", self._minimal_contracts(), {})
        assert result.auto_count == 1
        assert result.review_count == 1
        assert result.block_count == 1

    def test_total_equals_contract_count(self) -> None:
        contracts = self._minimal_contracts()
        result = run_profile("test", contracts, {})
        assert result.contracts_total == len(contracts)
        assert result.auto_count + result.review_count + result.block_count == len(contracts)

    def test_actions_list_length(self) -> None:
        result = run_profile("test", self._minimal_contracts(), {})
        assert len(result.actions) == 3

    def test_action_gate_field_correct(self) -> None:
        result = run_profile("test", self._minimal_contracts(), {})
        by_id = {a["contract_id"]: a for a in result.actions}
        assert by_id["c1"]["gate"] == "AUTO"
        assert by_id["c2"]["gate"] == "REVIEW"
        assert by_id["c3"]["gate"] == "BLOCK"

    def test_action_severity_preserved(self) -> None:
        result = run_profile("test", self._minimal_contracts(), {})
        by_id = {a["contract_id"]: a for a in result.actions}
        assert by_id["c1"]["severity"] == "low"
        assert by_id["c3"]["severity"] == "high"

    def test_assertions_passed_when_correct(self) -> None:
        result = run_profile("test", self._minimal_contracts(), {"auto_exact": 1, "block_exact": 1})
        assert result.assertions_passed is True
        assert result.assertion_errors == []

    def test_assertions_fail_on_mismatch(self) -> None:
        result = run_profile("test", self._minimal_contracts(), {"auto_exact": 0})
        assert result.assertions_passed is False
        assert len(result.assertion_errors) == 1

    def test_name_is_set(self) -> None:
        result = run_profile("my-profile", self._minimal_contracts(), {})
        assert result.name == "my-profile"

    def test_empty_contracts(self) -> None:
        result = run_profile("empty", [], {"auto_exact": 0, "review_exact": 0, "block_exact": 0})
        assert result.contracts_total == 0
        assert result.assertions_passed is True


# ---------------------------------------------------------------------------
# _assert_distribution
# ---------------------------------------------------------------------------


class TestAssertDistribution:
    def test_auto_exact_pass(self) -> None:
        errors = _assert_distribution("p", 2, 3, 1, {"auto_exact": 2})
        assert errors == []

    def test_auto_exact_fail(self) -> None:
        errors = _assert_distribution("p", 2, 3, 1, {"auto_exact": 3})
        assert len(errors) == 1
        assert "auto_count" in errors[0]

    def test_block_min_pass(self) -> None:
        errors = _assert_distribution("p", 0, 0, 5, {"block_min": 3})
        assert errors == []

    def test_block_min_fail(self) -> None:
        errors = _assert_distribution("p", 0, 0, 2, {"block_min": 3})
        assert len(errors) == 1

    def test_review_max_pass(self) -> None:
        errors = _assert_distribution("p", 0, 3, 0, {"review_max": 5})
        assert errors == []

    def test_review_max_fail(self) -> None:
        errors = _assert_distribution("p", 0, 6, 0, {"review_max": 5})
        assert len(errors) == 1


# ---------------------------------------------------------------------------
# build_agent_telemetry — AgentTelemetry integration
# ---------------------------------------------------------------------------


class TestBuildAgentTelemetry:
    def _make_profile(
        self, name: str, *, auto: int, review: int, block: int
    ) -> ProfileResult:
        actions = (
            [{"contract_id": f"a{i}", "severity": "low",    "auto_repair_eligible": True,  "gate": "AUTO"}   for i in range(auto)]
            + [{"contract_id": f"r{i}", "severity": "medium", "auto_repair_eligible": False, "gate": "REVIEW"} for i in range(review)]
            + [{"contract_id": f"b{i}", "severity": "high",   "auto_repair_eligible": False, "gate": "BLOCK"}  for i in range(block)]
        )
        return ProfileResult(
            name=name,
            contracts_total=auto + review + block,
            auto_count=auto,
            review_count=review,
            block_count=block,
            actions=actions,
        )

    def test_schema_version_is_2_2(self) -> None:
        t = build_agent_telemetry(self._make_profile("x", auto=1, review=1, block=1))
        assert t["schema_version"] == "2.2"

    def test_session_id_contains_profile_name(self) -> None:
        t = build_agent_telemetry(self._make_profile("myrepo", auto=1, review=0, block=0))
        assert "myrepo" in (t.get("session_id") or "")

    def test_total_auto_correct(self) -> None:
        t = build_agent_telemetry(self._make_profile("x", auto=3, review=2, block=1))
        assert t["total_auto"] == 3

    def test_total_review_correct(self) -> None:
        t = build_agent_telemetry(self._make_profile("x", auto=0, review=4, block=0))
        assert t["total_review"] == 4

    def test_total_block_correct(self) -> None:
        t = build_agent_telemetry(self._make_profile("x", auto=0, review=0, block=5))
        assert t["total_block"] == 5

    def test_all_zeros(self) -> None:
        t = build_agent_telemetry(self._make_profile("empty", auto=0, review=0, block=0))
        assert t["total_auto"] == 0
        assert t["total_review"] == 0
        assert t["total_block"] == 0

    def test_returns_dict(self) -> None:
        t = build_agent_telemetry(self._make_profile("x", auto=1, review=1, block=1))
        assert isinstance(t, dict)


# ---------------------------------------------------------------------------
# Three reference profiles — end-to-end assertion validation
# ---------------------------------------------------------------------------


class TestReferenceProfiles:
    def test_high_quality_block_count_is_zero(self) -> None:
        result = run_profile("high_quality", _HIGH_QUALITY_PROFILE, {"block_exact": 0})
        assert result.block_count == 0
        assert result.assertions_passed is True

    def test_high_quality_has_auto_contracts(self) -> None:
        result = run_profile("high_quality", _HIGH_QUALITY_PROFILE, {})
        assert result.auto_count > 0

    def test_high_quality_auto_count_matches_expected(self) -> None:
        expected = _high_quality_expected_auto()
        result = run_profile("high_quality", _HIGH_QUALITY_PROFILE, {"auto_exact": expected})
        assert result.assertions_passed is True
        assert result.auto_count == expected

    def test_legacy_service_assertions_pass(self) -> None:
        result = run_profile("legacy_service", _LEGACY_SERVICE_PROFILE, _LEGACY_SERVICE_ASSERTIONS)
        assert result.assertions_passed is True, result.assertion_errors

    def test_legacy_service_has_all_three_gates(self) -> None:
        result = run_profile("legacy_service", _LEGACY_SERVICE_PROFILE, {})
        assert result.auto_count > 0
        assert result.review_count > 0
        assert result.block_count > 0

    def test_drift_self_assertions_pass(self) -> None:
        contracts = _load_drift_self_profile()
        result = run_profile("drift_self", contracts, _DRIFT_SELF_ASSERTIONS)
        assert result.assertions_passed is True, result.assertion_errors

    def test_drift_self_has_no_auto_contracts(self) -> None:
        """drift.intent.json has no low/info contracts — AUTO count must be 0."""
        contracts = _load_drift_self_profile()
        result = run_profile("drift_self", contracts, {})
        assert result.auto_count == 0

    def test_drift_self_has_block_contracts(self) -> None:
        """critical + high severity → at least one BLOCK."""
        contracts = _load_drift_self_profile()
        result = run_profile("drift_self", contracts, {})
        assert result.block_count > 0

    def test_drift_self_has_review_contracts(self) -> None:
        """medium contracts → at least one REVIEW."""
        contracts = _load_drift_self_profile()
        result = run_profile("drift_self", contracts, {})
        assert result.review_count > 0


# ---------------------------------------------------------------------------
# AgentTelemetry drift.models integration
# ---------------------------------------------------------------------------


class TestAgentTelemetryModelsIntegration:
    """Verifies that build_agent_telemetry uses drift.models.AgentTelemetry
    correctly (not just a plain dict shortcut)."""

    def test_telemetry_counters_match_profile_counts(self) -> None:
        contracts = [
            {"id": "t1", "severity": "low",    "auto_repair_eligible": True},
            {"id": "t2", "severity": "medium",  "auto_repair_eligible": False},
            {"id": "t3", "severity": "high",    "auto_repair_eligible": False},
        ]
        result = run_profile("integration", contracts, {})
        telemetry_dict = build_agent_telemetry(result)
        assert telemetry_dict["total_auto"]   == result.auto_count
        assert telemetry_dict["total_review"] == result.review_count
        assert telemetry_dict["total_block"]  == result.block_count

    def test_direct_agent_telemetry_properties(self) -> None:
        """Directly instantiate AgentTelemetry and verify counters after
        populating it the same way build_agent_telemetry does."""
        from drift.models import AgentAction, AgentActionType, AgentTelemetry

        actions = [
            AgentAction(action_type=AgentActionType.AUTO_FIX,       reason="low/auto", gate="AUTO",   severity="low"),
            AgentAction(action_type=AgentActionType.REVIEW_REQUEST,  reason="medium",   gate="REVIEW", severity="medium"),
            AgentAction(action_type=AgentActionType.BLOCK,           reason="high",     gate="BLOCK",  severity="high"),
        ]
        t = AgentTelemetry(session_id="benchmark-integration", agent_actions_taken=actions)
        assert t.total_auto   == 1
        assert t.total_review == 1
        assert t.total_block  == 1
        assert t.schema_version == "2.2"
