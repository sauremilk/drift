from __future__ import annotations

import pytest

from drift.models import AgentTask, Severity, SignalType
from drift.next_step_contract import (
    DONE_SAFE_TO_COMMIT,
    _error_response,
    _next_step_contract,
    _tool_call,
)
from drift.response_shaping import _base_response, build_drift_score_scope, shape_for_profile
from drift.task_graph import (
    _derive_task_contract,
    _task_to_api_dict,
    build_task_graph,
    build_workflow_plan,
    validate_plan,
)


def _task(
    tid: str,
    *,
    depends_on: list[str] | None = None,
    signal: SignalType = SignalType.PATTERN_FRAGMENTATION,
    batch_eligible: bool = False,
    fix_template_class: str = "",
) -> AgentTask:
    return AgentTask(
        id=tid,
        signal_type=signal,
        severity=Severity.HIGH,
        priority=1,
        title=f"Task {tid}",
        description=f"Fix task {tid}",
        action=f"Apply fix for {tid}",
        file_path=f"src/pkg/{tid}.py",
        start_line=10,
        symbol=f"sym_{tid}",
        related_files=[f"src/pkg/{tid}_helper.py"],
        depends_on=depends_on or [],
        expected_score_delta=-0.02,
        metadata={
            "batch_eligible": batch_eligible,
            "fix_template_class": fix_template_class,
            "finding_context": "production",
            "affected_files_for_pattern": [f"src/pkg/{tid}.py"],
            "pattern_instance_count": 2,
        },
    )


def test_next_step_contract_helpers_build_expected_shape() -> None:
    tool = _tool_call("drift_fix_plan", {"path": "."})
    assert tool == {"tool": "drift_fix_plan", "params": {"path": "."}}

    contract = _next_step_contract(
        next_tool="drift_nudge",
        next_params={"session_id": "s1"},
        done_when=DONE_SAFE_TO_COMMIT,
        fallback_tool="drift_diff",
        fallback_params={"uncommitted": True},
    )
    assert contract["next_tool_call"]["tool"] == "drift_nudge"
    assert contract["fallback_tool_call"]["tool"] == "drift_diff"
    assert contract["done_when"] == DONE_SAFE_TO_COMMIT


def test_error_response_contains_contract_fields() -> None:
    response = _error_response(
        "DRIFT-1001",
        "invalid config",
        invalid_fields=[{"field": "weights.pfs", "reason": "out of range"}],
        suggested_fix={"set": "weights.pfs", "to": 0.2},
        recoverable=True,
        recovery_tool_call={"tool": "drift_validate", "params": {"path": "."}},
    )
    assert response["schema_version"]
    assert response["type"] == "error"
    assert response["error_code"] == "DRIFT-1001"
    assert response["recoverable"] is True
    assert response["recovery_tool_call"]["tool"] == "drift_validate"


def test_build_task_graph_and_workflow_plan_smoke() -> None:
    t1 = _task("a", batch_eligible=True, fix_template_class="extract")
    t2 = _task("b", depends_on=["a"], batch_eligible=True, fix_template_class="extract")
    t3 = _task("c", depends_on=["b"])

    graph = build_task_graph([t3, t1, t2])

    assert [t.id for t in graph.tasks] == ["a", "b", "c"]
    assert graph.execution_phases == [["a"], ["b"], ["c"]]
    assert graph.critical_path == ["a", "b", "c"]
    assert graph.total_estimated_delta < 0

    plan = build_workflow_plan(graph, session_id="sid-1", repo_path=".")
    assert plan.steps
    assert plan.steps[-1].tool == "drift_nudge"
    assert plan.success_criteria == DONE_SAFE_TO_COMMIT
    assert plan.plan_fingerprint
    assert plan.depended_on_repo_state


def test_validate_plan_detects_hard_repo_state_change(monkeypatch: pytest.MonkeyPatch) -> None:
    t1 = _task("a")
    graph = build_task_graph([t1])
    plan = build_workflow_plan(graph, session_id="sid-1", repo_path=".")

    def fake_git_cmd(_repo: str, *args: str) -> str:
        cmd = tuple(args)
        if cmd == ("rev-parse", "HEAD"):
            return "new-head"
        if cmd == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "feature-branch"
        if cmd == ("diff", "--name-only"):
            return "src/pkg/a.py\n"
        return ""

    monkeypatch.setattr("drift.task_graph._git_cmd", fake_git_cmd)

    result = validate_plan(plan, ".")
    assert result.valid is False
    assert result.recommendation == "re_plan"
    assert "head_commit_changed" in result.triggered
    assert "branch_changed" in result.triggered


def test_validate_plan_handles_legacy_and_invalidated_plan() -> None:
    t1 = _task("a")
    graph = build_task_graph([t1])
    plan = build_workflow_plan(graph, session_id="sid-1", repo_path=".")

    plan.depended_on_repo_state = {}
    legacy = validate_plan(plan, ".")
    assert legacy.valid is True
    assert legacy.reason == "legacy_plan_no_state"

    plan.invalidated = True
    plan.invalidation_reason = "manual override"
    invalidated = validate_plan(plan, ".")
    assert invalidated.valid is False
    assert invalidated.recommendation == "re_plan"
    assert invalidated.triggered == ["explicit_invalidation"]


def test_task_to_api_dict_emits_contract_and_refs() -> None:
    task = _task("a")
    task.metadata["canonical_exemplar"] = "src/canonical/a.py"
    # Lightweight negative-context compatible stub
    task.negative_context = [
        type("NC", (), {"canonical_alternative": "# use helper\n# and small wrapper"})()
    ]

    payload = _task_to_api_dict(task)

    assert payload["signal"] == "PFS"
    assert "signal_abbrev" not in payload
    assert payload["canonical_refs"]
    assert payload["completion_evidence"]["tool"] == "drift_nudge"
    assert "src/pkg/a.py" in payload["allowed_files"]


def test_derive_task_contract_builds_allowed_files() -> None:
    contract = _derive_task_contract(
        {
            "file": "src/mod/core.py",
            "related_files": ["src/mod/helpers.py", "src/mod/core.py"],
            "signal": "PFS",
        }
    )

    assert contract["allowed_files"] == ["src/mod/core.py", "src/mod/helpers.py"]
    assert "forbidden_files" not in contract
    assert "max_files_changed" not in contract


def test_types_module_is_importable_and_exposes_aliases() -> None:
    import drift.types as drift_types

    # Runtime-visible aliases/protocol symbols should be importable.
    assert drift_types.JsonDict == dict[str, object]
    assert drift_types.JsonList == list[object]
    assert drift_types.SyncCallable.__name__ == "SyncCallable"


def test_response_shaping_helpers_cover_base_and_profile_filtering() -> None:
    scope = build_drift_score_scope(
        context="scan",
        path="/src/drift/",
        signal_scope="core",
        baseline_filtered=True,
    )
    assert scope == "context:scan,signals:core,path:src/drift,baseline:filtered"

    base = _base_response(status="ok", extra=1)
    assert base["schema_version"]
    assert base["status"] == "ok"

    shaped = shape_for_profile(
        {
            "schema_version": "2.1",
            "status": "ok",
            "agent_instruction": "next",
            "tasks": ["t1"],
            "noise": "drop-me",
        },
        "planner",
    )
    assert "tasks" in shaped
    assert "noise" not in shaped
    assert shaped["response_profile"] == "planner"

    full = shape_for_profile({"status": "ok"}, "unknown")
    assert full["response_profile"] == "full"
