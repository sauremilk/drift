"""Tests for output_mode='mirror' — prescriptive field stripping."""

from __future__ import annotations

import copy

from drift.response_shaping import apply_output_mode


def _sample_response() -> dict:
    """Build a realistic response dict with prescriptive + diagnostic keys."""
    return {
        "schema_version": "2.1",
        "status": "ok",
        "type": "scan",
        # Diagnostic (should survive mirror mode)
        "drift_score": 42.5,
        "severity": "medium",
        "finding_count": 3,
        "findings": [
            {"signal": "PFS", "file": "foo.py", "severity": "high"},
        ],
        "top_signals": [{"signal": "PFS", "count": 2}],
        "trend": {"direction": "degrading"},
        "score_delta": 1.2,
        "safe_to_commit": False,
        # Prescriptive top-level (should be stripped in mirror mode)
        "agent_instruction": "Run drift_fix_plan next.",
        "next_tool_call": {"tool": "drift_fix_plan", "params": {}},
        "fallback_tool_call": {"tool": "drift_scan", "params": {}},
        "done_when": "score < 30",
        "workflow_plan": ["step1", "step2"],
        "recommended_next_actions": ["fix PFS"],
        "guardrails": ["no new PFS"],
        "guardrails_prompt_block": "Do not introduce...",
        "negative_context": ["avoid pattern X"],
        # Tasks with prescriptive sub-keys
        "tasks": [
            {
                "id": "task-1",
                "title": "Fix pattern_fragmentation in foo.py",
                "signal": "PFS",
                "file": "foo.py",
                "severity": "high",
                "automation_fitness": 0.8,
                # Prescriptive task keys (should be stripped)
                "action": "Consolidate duplicate implementations.",
                "constraints": ["Do not break imports"],
                "success_criteria": "No PFS findings remain.",
                "verify_plan": "Run drift_nudge after fix.",
                "expected_effect": "PFS count drops to 0.",
                "negative_context": "Avoid introducing new coupling.",
                "regression_guidance": "Check AVS after merge.",
                "repair_exemplar": "See fix in bar.py",
                "fix_intent": "consolidate",
                "fix_template_class": "merge_duplicates",
                "repair_maturity": "proven",
            },
        ],
    }


# -- Full mode: passthrough ------------------------------------------------


def test_full_mode_returns_all_keys():
    resp = _sample_response()
    original_keys = set(resp.keys())
    result = apply_output_mode(resp, "full")
    assert result["output_mode"] == "full"
    # All original keys plus output_mode should be present
    assert original_keys | {"output_mode"} == set(result.keys())


def test_full_mode_preserves_task_keys():
    resp = _sample_response()
    result = apply_output_mode(resp, "full")
    task = result["tasks"][0]
    assert "action" in task
    assert "constraints" in task
    assert "fix_intent" in task


# -- Mirror mode: prescriptive stripping -----------------------------------


def test_mirror_mode_strips_prescriptive_top_keys():
    resp = _sample_response()
    result = apply_output_mode(resp, "mirror")
    assert result["output_mode"] == "mirror"
    for key in (
        "agent_instruction",
        "next_tool_call",
        "fallback_tool_call",
        "done_when",
        "workflow_plan",
        "recommended_next_actions",
        "guardrails",
        "guardrails_prompt_block",
        "negative_context",
    ):
        assert key not in result, f"prescriptive key '{key}' should be stripped"


def test_mirror_mode_retains_diagnostic_keys():
    resp = _sample_response()
    result = apply_output_mode(resp, "mirror")
    for key in (
        "schema_version",
        "status",
        "type",
        "drift_score",
        "severity",
        "finding_count",
        "findings",
        "top_signals",
        "trend",
        "score_delta",
        "safe_to_commit",
    ):
        assert key in result, f"diagnostic key '{key}' should survive mirror mode"


def test_mirror_mode_strips_prescriptive_task_keys():
    resp = _sample_response()
    result = apply_output_mode(resp, "mirror")
    task = result["tasks"][0]
    for key in (
        "action",
        "constraints",
        "success_criteria",
        "verify_plan",
        "expected_effect",
        "negative_context",
        "regression_guidance",
        "repair_exemplar",
        "fix_intent",
        "fix_template_class",
        "repair_maturity",
    ):
        assert key not in task, f"prescriptive task key '{key}' should be stripped"


def test_mirror_mode_retains_diagnostic_task_keys():
    resp = _sample_response()
    result = apply_output_mode(resp, "mirror")
    task = result["tasks"][0]
    for key in ("id", "title", "signal", "file", "severity", "automation_fitness"):
        assert key in task, f"diagnostic task key '{key}' should survive mirror mode"


# -- Edge cases ------------------------------------------------------------


def test_mirror_mode_no_tasks_key():
    """Response without a tasks key should not error."""
    resp = {"status": "ok", "drift_score": 10}
    result = apply_output_mode(resp, "mirror")
    assert result["output_mode"] == "mirror"
    assert "tasks" not in result


def test_mirror_mode_empty_tasks():
    resp = {"status": "ok", "tasks": []}
    result = apply_output_mode(resp, "mirror")
    assert result["tasks"] == []


def test_mirror_mode_idempotent():
    """Applying mirror twice should be the same as once."""
    resp = _sample_response()
    once = apply_output_mode(copy.deepcopy(resp), "mirror")
    twice = apply_output_mode(copy.deepcopy(once), "mirror")
    assert once == twice


def test_mirror_mode_strips_nudge_text():
    resp = {"status": "ok", "nudge": "Run drift_fix_plan now."}
    result = apply_output_mode(resp, "mirror")
    assert "nudge" not in result


def test_unknown_mode_treated_as_full():
    """Unknown mode is treated as full (passthrough)."""
    resp = _sample_response()
    result = apply_output_mode(resp, "something_else")
    # Should behave like full — all keys present
    assert "agent_instruction" in result
