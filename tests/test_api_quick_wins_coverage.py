"""Coverage tests for api/diff, api/nudge, api/fix_plan, and alias_resolver helpers."""

from __future__ import annotations

from types import SimpleNamespace

from drift.analyzers.typescript.alias_resolver import (
    _expand_target_pattern,
    _match_alias_pattern,
)
from drift.api.diff import (
    _diff_decision_reason,
    _diff_next_actions,
    _diff_next_step_contract,
)
from drift.api.fix_plan import (
    _fix_plan_agent_instruction,
    _fix_plan_next_step_contract,
)
from drift.api.nudge import (
    _is_derived_cache_artifact,
    _nudge_next_step_contract,
)

# ── _diff_decision_reason ────────────────────────────────────────


class TestDiffDecisionReason:
    def test_accepted(self):
        code, text = _diff_decision_reason(
            accept_change=True,
            in_scope_accept=True,
            has_out_of_scope_noise=False,
        )
        assert code == "accepted_no_blockers"

    def test_rejected_in_scope(self):
        code, _ = _diff_decision_reason(
            accept_change=False,
            in_scope_accept=False,
            has_out_of_scope_noise=False,
        )
        assert code == "rejected_in_scope_blockers"

    def test_rejected_out_of_scope_noise(self):
        code, _ = _diff_decision_reason(
            accept_change=False,
            in_scope_accept=True,
            has_out_of_scope_noise=True,
        )
        assert code == "rejected_out_of_scope_noise_only"

    def test_rejected_unknown(self):
        code, _ = _diff_decision_reason(
            accept_change=False,
            in_scope_accept=True,
            has_out_of_scope_noise=False,
        )
        assert code == "rejected_unknown"


# ── _diff_next_actions ───────────────────────────────────────────


def _mock_finding(severity_value: str = "medium"):
    return SimpleNamespace(severity=SimpleNamespace(value=severity_value))


class TestDiffNextActions:
    def test_degraded(self):
        actions = _diff_next_actions(
            [],
            "degraded",
            [],
            in_scope_accept=False,
        )
        assert any("fix_plan" in a for a in actions)

    def test_high_severity(self):
        actions = _diff_next_actions(
            [_mock_finding("critical")],
            "stable",
            [],
        )
        assert any("explain" in a for a in actions)

    def test_baseline_recommended(self):
        actions = _diff_next_actions(
            [],
            "stable",
            [],
            has_baseline=False,
            baseline_recommended=True,
            baseline_reason="noise",
        )
        assert any("baseline save" in a for a in actions)

    def test_improved(self):
        actions = _diff_next_actions(
            [],
            "improved",
            [],
        )
        assert any("improving" in a for a in actions)

    def test_no_action(self):
        actions = _diff_next_actions(
            [],
            "stable",
            [],
        )
        assert actions == ["No immediate action required"]

    def test_out_of_scope_noise_in_scope_accept(self):
        actions = _diff_next_actions(
            [],
            "stable",
            ["out_of_scope_diff_noise"],
            in_scope_accept=True,
        )
        assert any("in_scope_accept" in a for a in actions)


# ── _diff_next_step_contract ─────────────────────────────────────


def _next_tool(result):
    """Extract tool name from next_step_contract."""
    call = result.get("next_tool_call")
    return call["tool"] if call else None


class TestDiffNextStepContract:
    def test_no_staged(self):
        result = _diff_next_step_contract(
            status="stable",
            accept_change=False,
            no_staged_files=True,
            decision_reason_code="accepted_no_blockers",
            batch_targets=[],
        )
        assert _next_tool(result) is None

    def test_accepted(self):
        result = _diff_next_step_contract(
            status="stable",
            accept_change=True,
            no_staged_files=False,
            decision_reason_code="accepted_no_blockers",
            batch_targets=[],
        )
        assert _next_tool(result) is None

    def test_accepted_improved_with_batch(self):
        result = _diff_next_step_contract(
            status="improved",
            accept_change=True,
            no_staged_files=False,
            decision_reason_code="accepted_no_blockers",
            batch_targets=[{"signal": "PFS"}],
        )
        assert _next_tool(result) == "drift_fix_plan"

    def test_rejected_out_of_scope(self):
        result = _diff_next_step_contract(
            status="degraded",
            accept_change=False,
            no_staged_files=False,
            decision_reason_code="rejected_out_of_scope_noise_only",
            batch_targets=[],
        )
        assert _next_tool(result) == "drift_diff"

    def test_rejected_default(self):
        result = _diff_next_step_contract(
            status="degraded",
            accept_change=False,
            no_staged_files=False,
            decision_reason_code="rejected_in_scope_blockers",
            batch_targets=[],
        )
        assert _next_tool(result) == "drift_fix_plan"


# ── _is_derived_cache_artifact ───────────────────────────────────


class TestIsDerivedCacheArtifact:
    def test_cache_dir(self):
        assert _is_derived_cache_artifact(".drift-cache/foo.json") is True

    def test_normal_file(self):
        assert _is_derived_cache_artifact("src/drift/foo.py") is False

    def test_backslash(self):
        assert _is_derived_cache_artifact(".drift-cache\\bar.json") is True


# ── _nudge_next_step_contract ────────────────────────────────────


class TestNudgeNextStepContract:
    def test_safe(self):
        result = _nudge_next_step_contract(safe_to_commit=True)
        assert _next_tool(result) == "drift_diff"

    def test_not_safe(self):
        result = _nudge_next_step_contract(safe_to_commit=False)
        assert _next_tool(result) == "drift_fix_plan"


# ── _fix_plan_agent_instruction ──────────────────────────────────


class TestFixPlanAgentInstruction:
    def test_with_batch(self):
        tasks = [SimpleNamespace(metadata={"batch_eligible": True})]
        result = _fix_plan_agent_instruction(tasks)
        assert "batch_eligible" in result

    def test_without_batch(self):
        tasks = [SimpleNamespace(metadata={})]
        result = _fix_plan_agent_instruction(tasks)
        assert "nudge" in result.lower()

    def test_empty(self):
        result = _fix_plan_agent_instruction([])
        assert "nudge" in result.lower()


# ── _fix_plan_next_step_contract ─────────────────────────────────


class TestFixPlanNextStepContract:
    def test_with_batch(self):
        tasks = [SimpleNamespace(metadata={"batch_eligible": True})]
        result = _fix_plan_next_step_contract(tasks)
        assert _next_tool(result) == "drift_diff"

    def test_without_batch(self):
        tasks = [SimpleNamespace(metadata={})]
        result = _fix_plan_next_step_contract(tasks)
        assert _next_tool(result) == "drift_nudge"


# ── _match_alias_pattern ─────────────────────────────────────────


class TestMatchAliasPattern:
    def test_exact_match(self):
        assert _match_alias_pattern("lodash", "lodash") == ""

    def test_exact_no_match(self):
        assert _match_alias_pattern("lodash", "react") is None

    def test_wildcard_match(self):
        result = _match_alias_pattern("@app/*", "@app/utils")
        assert result == "utils"

    def test_wildcard_no_match(self):
        assert _match_alias_pattern("@app/*", "@other/foo") is None

    def test_wildcard_with_suffix(self):
        result = _match_alias_pattern("@app/*.js", "@app/utils.js")
        assert result == "utils"

    def test_multi_wildcard(self):
        assert _match_alias_pattern("@app/*/*.js", "@app/foo/bar.js") is None

    def test_no_wildcard_no_match(self):
        assert _match_alias_pattern("react", "vue") is None


# ── _expand_target_pattern ───────────────────────────────────────


class TestExpandTargetPattern:
    def test_no_wildcard(self):
        assert _expand_target_pattern("./src/index", "") == "./src/index"

    def test_no_wildcard_with_capture(self):
        assert _expand_target_pattern("./src/index", "utils") is None

    def test_wildcard(self):
        assert _expand_target_pattern("./src/*", "utils") == "./src/utils"

    def test_multi_wildcard(self):
        assert _expand_target_pattern("./src/*/*", "a") is None
