"""Tests for task-dependency graph builder (ADR-025 Phase A)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pytest

from drift.api_helpers import (
    TaskGraph,
    build_task_graph,
    build_workflow_plan,
    shape_for_profile,
)
from drift.models import AgentTask, Severity, SignalType
from drift.task_graph import _task_graph_critical_path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _task(
    tid: str,
    *,
    signal: SignalType = SignalType.PATTERN_FRAGMENTATION,
    depends_on: list[str] | None = None,
    delta: float = -0.01,
    batch_eligible: bool = False,
    fix_template_class: str = "",
) -> AgentTask:
    return AgentTask(
        id=tid,
        signal_type=signal,
        severity=Severity.HIGH,
        priority=1,
        title=f"Task {tid}",
        description=f"Fix {tid}",
        action=f"Do {tid}",
        depends_on=depends_on or [],
        expected_score_delta=delta,
        metadata={
            "batch_eligible": batch_eligible,
            "fix_template_class": fix_template_class,
        },
    )


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


class TestEmptyTaskGraph:
    def test_empty_list_returns_empty_graph(self) -> None:
        g = build_task_graph([])
        assert g.tasks == []
        assert g.batch_groups == {}
        assert g.execution_phases == []
        assert g.critical_path == []
        assert g.total_estimated_delta == 0.0

    def test_empty_graph_api_dict(self) -> None:
        d = build_task_graph([]).to_api_dict()
        assert d["batch_groups"] == {}
        assert d["execution_phases"] == []
        assert d["critical_path"] == []
        assert d["total_estimated_delta"] == 0.0

    def test_empty_graph_to_text_summary(self) -> None:
        text = build_task_graph([]).to_text()
        assert "TaskGraph: 0 tasks, 0 phases, delta=+0.0000" in text
        assert "Critical path: none" in text


# ---------------------------------------------------------------------------
# Single task
# ---------------------------------------------------------------------------


class TestSingleTask:
    def test_one_task_graph(self) -> None:
        t = _task("a")
        g = build_task_graph([t])
        assert len(g.tasks) == 1
        assert g.tasks[0].id == "a"
        assert g.tasks[0].preferred_order == 0
        assert g.tasks[0].blocks == []
        assert g.tasks[0].parallel_with == []
        assert g.execution_phases == [["a"]]
        assert g.critical_path == ["a"]


# ---------------------------------------------------------------------------
# Topological sort — linear chain
# ---------------------------------------------------------------------------


class TestLinearChain:
    """A → B → C: strict sequential dependency."""

    def test_topo_sort_order(self) -> None:
        a = _task("a")
        b = _task("b", depends_on=["a"])
        c = _task("c", depends_on=["b"])
        # Pass in reverse order to prove sorting works
        g = build_task_graph([c, a, b])
        ids = [t.id for t in g.tasks]
        assert ids == ["a", "b", "c"]

    def test_preferred_order(self) -> None:
        a = _task("a")
        b = _task("b", depends_on=["a"])
        c = _task("c", depends_on=["b"])
        g = build_task_graph([a, b, c])
        assert g.tasks[0].preferred_order == 0
        assert g.tasks[1].preferred_order == 1
        assert g.tasks[2].preferred_order == 2

    def test_blocks_inverse(self) -> None:
        a = _task("a")
        b = _task("b", depends_on=["a"])
        c = _task("c", depends_on=["b"])
        g = build_task_graph([a, b, c])
        assert g.tasks[0].blocks == ["b"]  # a blocks b
        assert g.tasks[1].blocks == ["c"]  # b blocks c
        assert g.tasks[2].blocks == []  # c blocks nothing

    def test_execution_phases_sequential(self) -> None:
        a = _task("a")
        b = _task("b", depends_on=["a"])
        c = _task("c", depends_on=["b"])
        g = build_task_graph([a, b, c])
        assert g.execution_phases == [["a"], ["b"], ["c"]]

    def test_critical_path_is_full_chain(self) -> None:
        a = _task("a")
        b = _task("b", depends_on=["a"])
        c = _task("c", depends_on=["b"])
        g = build_task_graph([a, b, c])
        assert g.critical_path == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Parallel tasks (diamond pattern)
# ---------------------------------------------------------------------------


class TestParallelTasks:
    """A → {B, C} → D: B and C can run in parallel."""

    def _build(self) -> TaskGraph:
        a = _task("a")
        b = _task("b", depends_on=["a"])
        c = _task("c", depends_on=["a"])
        d = _task("d", depends_on=["b", "c"])
        return build_task_graph([d, b, a, c])

    def test_parallel_detection(self) -> None:
        g = self._build()
        task_b = next(t for t in g.tasks if t.id == "b")
        task_c = next(t for t in g.tasks if t.id == "c")
        assert "c" in task_b.parallel_with
        assert "b" in task_c.parallel_with

    def test_execution_phases_diamond(self) -> None:
        g = self._build()
        assert len(g.execution_phases) == 3
        assert g.execution_phases[0] == ["a"]
        assert sorted(g.execution_phases[1]) == ["b", "c"]
        assert g.execution_phases[2] == ["d"]

    def test_critical_path_diamond(self) -> None:
        g = self._build()
        # Both paths a→b→d and a→c→d are length 3, either is valid
        assert len(g.critical_path) == 3
        assert g.critical_path[0] == "a"
        assert g.critical_path[-1] == "d"

    def test_to_text_includes_phase_and_dependency_view(self) -> None:
        g = self._build()
        text = g.to_text()

        assert "TaskGraph: 4 tasks, 3 phases" in text
        assert "Phase 1 [parallel]: b, c" in text
        assert "Dependencies:" in text
        assert "b <- a" in text
        assert "d <- b, c" in text
        assert "Critical path:" in text


# ---------------------------------------------------------------------------
# Independent tasks (fully parallel)
# ---------------------------------------------------------------------------


class TestIndependentTasks:
    def test_all_in_one_phase(self) -> None:
        a = _task("a")
        b = _task("b")
        c = _task("c")
        g = build_task_graph([c, a, b])
        assert len(g.execution_phases) == 1
        assert sorted(g.execution_phases[0]) == ["a", "b", "c"]

    def test_parallel_with_all(self) -> None:
        a = _task("a")
        b = _task("b")
        c = _task("c")
        g = build_task_graph([a, b, c])
        for t in g.tasks:
            assert len(t.parallel_with) == 2


# ---------------------------------------------------------------------------
# Topological sort determinism (issue #391)
# ---------------------------------------------------------------------------


class TestTopologicalSortDeterminism:
    def test_execution_phases_stable_regardless_of_input_order(self) -> None:
        """execution_phases must be identical for the same task set
        regardless of the order the tasks are passed to build_task_graph."""
        tasks_fwd = [_task("a"), _task("b"), _task("c"), _task("d")]
        tasks_rev = list(reversed(tasks_fwd))

        g_fwd = build_task_graph(tasks_fwd)
        g_rev = build_task_graph(tasks_rev)

        assert g_fwd.execution_phases == g_rev.execution_phases

    def test_preferred_order_stable_regardless_of_input_order(self) -> None:
        """preferred_order on each task must be the same no matter the input order."""
        tasks_fwd = [_task("x"), _task("y"), _task("z")]
        tasks_rev = list(reversed(tasks_fwd))

        g_fwd = build_task_graph(tasks_fwd)
        g_rev = build_task_graph(tasks_rev)

        order_fwd = {t.id: t.preferred_order for t in g_fwd.tasks}
        order_rev = {t.id: t.preferred_order for t in g_rev.tasks}
        assert order_fwd == order_rev

    def test_sequential_chain_stable(self) -> None:
        """A linear dependency chain must always resolve in dependency order."""
        a = _task("a")
        b = _task("b", depends_on=["a"])
        c = _task("c", depends_on=["b"])

        g1 = build_task_graph([a, b, c])
        g2 = build_task_graph([c, b, a])

        assert g1.execution_phases == [["a"], ["b"], ["c"]]
        assert g2.execution_phases == [["a"], ["b"], ["c"]]


# ---------------------------------------------------------------------------
# Critical-path edge cases (issue #393)
# ---------------------------------------------------------------------------


class TestCriticalPathEdgeCases:
    """Regression tests for _task_graph_critical_path(): empty input and tie-breaking."""

    def test_empty_sorted_ids_returns_empty_list(self) -> None:
        result = _task_graph_critical_path([], defaultdict(list), set())
        assert result == []

    def test_tie_breaking_is_deterministic_lexicographic(self) -> None:
        """Two independent tasks with equal dist: lexicographically smallest wins."""
        children: dict = defaultdict(list)
        task_ids = {"task-a", "task-b"}

        path_a = _task_graph_critical_path(["task-b", "task-a"], children, task_ids)
        path_b = _task_graph_critical_path(["task-a", "task-b"], children, task_ids)

        assert path_a == path_b
        assert path_a == ["task-a"]

    def test_tie_breaking_prefers_smallest_id(self) -> None:
        """Three independent tasks: lexicographically smallest end_node selected."""
        children: dict = defaultdict(list)
        task_ids = {"z", "a", "m"}
        result = _task_graph_critical_path(["z", "m", "a"], children, task_ids)
        assert result == ["a"]

    def test_build_task_graph_empty_critical_path(self) -> None:
        """build_task_graph([]) must still return critical_path == []."""
        g = build_task_graph([])
        assert g.critical_path == []

    def test_duplicate_ids_raise_value_error(self) -> None:
        """build_task_graph must raise ValueError on duplicate task IDs (#404)."""
        t1 = _task("task-a")
        t2 = _task("task-a")
        with pytest.raises(ValueError, match="task-a"):
            build_task_graph([t1, t2])

    def test_duplicate_ids_lists_all_duplicates(self) -> None:
        """ValueError message must list every duplicate ID."""
        tasks = [_task("x"), _task("x"), _task("y"), _task("y"), _task("z")]
        with pytest.raises(ValueError, match="x") as exc_info:
            build_task_graph(tasks)
        msg = str(exc_info.value)
        assert "x" in msg
        assert "y" in msg
        assert "z" not in msg  # z appears only once — not a duplicate





class TestBatchGroups:
    def test_batch_group_from_template_and_signal(self) -> None:
        a = _task("a", batch_eligible=True, fix_template_class="extract_function")
        b = _task("b", batch_eligible=True, fix_template_class="extract_function")
        c = _task("c", batch_eligible=False, fix_template_class="extract_function")
        g = build_task_graph([a, b, c])
        assert "PFS-extract_function" in g.batch_groups
        assert sorted(g.batch_groups["PFS-extract_function"]) == ["a", "b"]
        # c is not batch_eligible
        assert a.batch_group == "PFS-extract_function"
        assert b.batch_group == "PFS-extract_function"
        assert c.batch_group is None

    def test_different_signals_different_groups(self) -> None:
        a = _task(
            "a",
            signal=SignalType.PATTERN_FRAGMENTATION,
            batch_eligible=True,
            fix_template_class="inline",
        )
        b = _task(
            "b",
            signal=SignalType.ARCHITECTURE_VIOLATION,
            batch_eligible=True,
            fix_template_class="inline",
        )
        g = build_task_graph([a, b])
        assert len(g.batch_groups) == 0  # each group has only 1 member → filtered

    def test_singleton_group_filtered(self) -> None:
        a = _task("a", batch_eligible=True, fix_template_class="rename")
        g = build_task_graph([a])
        assert g.batch_groups == {}
        assert a.batch_group is None

    def test_no_template_no_group(self) -> None:
        a = _task("a", batch_eligible=True, fix_template_class="")
        b = _task("b", batch_eligible=True, fix_template_class="")
        g = build_task_graph([a, b])
        assert g.batch_groups == {}


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


class TestCycleDetection:
    def test_simple_cycle_raises(self) -> None:
        a = _task("a", depends_on=["b"])
        b = _task("b", depends_on=["a"])
        with pytest.raises(ValueError, match="Dependency cycle"):
            build_task_graph([a, b])

    def test_three_node_cycle_raises(self) -> None:
        a = _task("a", depends_on=["c"])
        b = _task("b", depends_on=["a"])
        c = _task("c", depends_on=["b"])
        with pytest.raises(ValueError, match="Dependency cycle"):
            build_task_graph([a, b, c])

    def test_cycle_error_lists_members(self) -> None:
        a = _task("a", depends_on=["b"])
        b = _task("b", depends_on=["a"])
        with pytest.raises(ValueError, match="'a'.*'b'|'b'.*'a'"):
            build_task_graph([a, b])


# ---------------------------------------------------------------------------
# Unknown depends_on references (graceful handling)
# ---------------------------------------------------------------------------


class TestUnknownDependencies:
    def test_unknown_dep_emits_warning(self) -> None:
        a = _task("a", depends_on=["nonexistent"])
        with pytest.warns(UserWarning, match=r"nonexistent"):
            g = build_task_graph([a])
        assert len(g.tasks) == 1
        assert g.tasks[0].preferred_order == 0

    def test_unknown_dep_still_builds_graph(self) -> None:
        a = _task("a", depends_on=["does-not-exist"])
        b = _task("b", depends_on=[])
        with pytest.warns(UserWarning):
            g = build_task_graph([a, b])
        assert len(g.tasks) == 2
        # Both tasks are in phase 0 because dependency was unresolvable
        assert len(g.execution_phases) == 1

    def test_multiple_unknown_deps_each_warn(self) -> None:
        a = _task("a", depends_on=["x", "y"])
        with pytest.warns(UserWarning) as record:
            build_task_graph([a])
        messages = [str(w.message) for w in record]
        assert any("x" in m for m in messages)
        assert any("y" in m for m in messages)


# ---------------------------------------------------------------------------
# Total estimated delta
# ---------------------------------------------------------------------------


class TestEstimatedDelta:
    def test_total_delta_summed(self) -> None:
        a = _task("a", delta=-0.05)
        b = _task("b", delta=-0.03)
        c = _task("c", delta=-0.02)
        g = build_task_graph([a, b, c])
        assert abs(g.total_estimated_delta - (-0.10)) < 1e-9


# ---------------------------------------------------------------------------
# API dict serialization
# ---------------------------------------------------------------------------


class TestApiDict:
    def test_api_dict_structure(self) -> None:
        a = _task("a")
        b = _task("b", depends_on=["a"])
        g = build_task_graph([a, b])
        d = g.to_api_dict()
        assert "batch_groups" in d
        assert "execution_phases" in d
        assert "critical_path" in d
        assert "total_estimated_delta" in d
        assert isinstance(d["execution_phases"], list)

    def test_api_dict_delta_rounded(self) -> None:
        a = _task("a", delta=-0.00001234)
        g = build_task_graph([a])
        d = g.to_api_dict()
        # Should be rounded to 4 decimal places
        assert d["total_estimated_delta"] == round(-0.00001234, 4)

    def test_api_dict_roundtrip_reconstructs_task_graph(self) -> None:
        a = _task("a")
        b = _task("b", depends_on=["a"])
        original = build_task_graph([b, a])

        payload = original.to_api_dict()
        restored = TaskGraph.from_api_dict(payload)

        assert [t.id for t in restored.tasks] == ["a", "b"]
        assert restored.tasks[1].depends_on == ["a"]
        assert restored.batch_groups == original.batch_groups
        assert restored.execution_phases == original.execution_phases
        assert restored.critical_path == original.critical_path
        assert restored.total_estimated_delta == original.total_estimated_delta


# ---------------------------------------------------------------------------
# Response profile shaping (ADR-025 Phase B)
# ---------------------------------------------------------------------------


class TestShapeForProfile:
    """Unit tests for shape_for_profile()."""

    @pytest.fixture()
    def full_result(self) -> dict[str, Any]:
        return {
            "schema_version": "2.2",
            "status": "ok",
            "agent_instruction": "Do X",
            "drift_score": 3.5,
            "severity": "medium",
            "findings": [{"id": "f1"}],
            "finding_count": 1,
            "top_signals": [{"signal": "PFS"}],
            "tasks": [{"id": "t1"}],
            "task_graph": {"phases": [[]]},
            "execution_phases": [["t1"]],
            "next_tool_call": {"tool": "drift_fix_plan"},
            "fallback_tool_call": None,
            "done_when": "score == 0",
            "trend": {"direction": "improving"},
            "warnings": [],
            "safe_to_commit": True,
            "score_delta": -0.5,
            "negative_context": [{"pattern": "bad"}],
            "session": {"session_id": "abc"},
        }

    def test_none_profile_returns_full(self, full_result: dict[str, Any]) -> None:
        shaped = shape_for_profile(full_result, None)
        assert shaped["response_profile"] == "full"
        assert "findings" in shaped
        assert "tasks" in shaped

    def test_unknown_profile_returns_full(self, full_result: dict[str, Any]) -> None:
        shaped = shape_for_profile(full_result, "unknown")
        assert shaped["response_profile"] == "full"

    def test_planner_keeps_tasks(self, full_result: dict[str, Any]) -> None:
        shaped = shape_for_profile(full_result, "planner")
        assert shaped["response_profile"] == "planner"
        assert "tasks" in shaped
        assert "task_graph" in shaped
        assert "drift_score" in shaped
        # Planner strips findings
        assert "findings" not in shaped

    def test_coder_keeps_findings(self, full_result: dict[str, Any]) -> None:
        shaped = shape_for_profile(full_result, "coder")
        assert shaped["response_profile"] == "coder"
        assert "findings" in shaped
        assert "tasks" in shaped
        assert "negative_context" in shaped
        # Coder strips trend
        assert "trend" not in shaped

    def test_verifier_keeps_deltas(self, full_result: dict[str, Any]) -> None:
        shaped = shape_for_profile(full_result, "verifier")
        assert shaped["response_profile"] == "verifier"
        assert "safe_to_commit" in shaped
        assert "score_delta" in shaped
        assert "done_when" in shaped
        # Verifier strips top_signals
        assert "top_signals" not in shaped

    def test_merge_readiness_minimal(self, full_result: dict[str, Any]) -> None:
        shaped = shape_for_profile(full_result, "merge_readiness")
        assert shaped["response_profile"] == "merge_readiness"
        assert "drift_score" in shaped
        assert "severity" in shaped
        assert "trend" in shaped
        # Merge readiness strips findings and tasks
        assert "findings" not in shaped
        assert "tasks" not in shaped

    def test_always_keeps_envelope(self, full_result: dict[str, Any]) -> None:
        for profile in ("planner", "coder", "verifier", "merge_readiness"):
            shaped = shape_for_profile(full_result, profile)
            assert "schema_version" in shaped
            assert "status" in shaped
            assert "agent_instruction" in shaped
            assert "response_profile" in shaped


# ---------------------------------------------------------------------------
# Workflow plans (ADR-025 Phase C)
# ---------------------------------------------------------------------------


class TestBuildWorkflowPlan:
    """Unit tests for build_workflow_plan()."""

    def test_empty_graph(self) -> None:
        g = build_task_graph([])
        plan = build_workflow_plan(g)
        # Only the verification step
        assert len(plan.steps) == 1
        assert plan.steps[0].tool == "drift_nudge"

    def test_single_task_plan(self) -> None:
        a = _task("a")
        g = build_task_graph([a])
        plan = build_workflow_plan(g)
        # 1 fix step + 1 verify step
        assert len(plan.steps) == 2
        assert plan.steps[0].task_ids == ["a"]
        assert plan.steps[1].tool == "drift_nudge"

    def test_batch_tasks_grouped(self) -> None:
        a = _task("a", batch_eligible=True, fix_template_class="T1")
        b = _task("b", batch_eligible=True, fix_template_class="T1")
        g = build_task_graph([a, b])
        plan = build_workflow_plan(g)
        # Batch step + verify
        batch_steps = [s for s in plan.steps if s.parallel]
        assert len(batch_steps) == 1
        assert sorted(batch_steps[0].task_ids) == ["a", "b"]

    def test_step_numbering_sequential(self) -> None:
        a = _task("a")
        b = _task("b", depends_on=["a"])
        g = build_task_graph([a, b])
        plan = build_workflow_plan(g)
        for i, step in enumerate(plan.steps, 1):
            assert step.step == i

    def test_session_id_in_params(self) -> None:
        a = _task("a")
        g = build_task_graph([a])
        plan = build_workflow_plan(g, session_id="s1")
        for step in plan.steps:
            assert step.params.get("session_id") == "s1"

    def test_no_session_id_omitted(self) -> None:
        a = _task("a")
        g = build_task_graph([a])
        plan = build_workflow_plan(g)
        for step in plan.steps:
            assert "session_id" not in step.params

    def test_success_criteria_set(self) -> None:
        g = build_task_graph([])
        plan = build_workflow_plan(g)
        assert "safe_to_commit" in plan.success_criteria

    def test_abort_criteria_set(self) -> None:
        g = build_task_graph([])
        plan = build_workflow_plan(g)
        assert "degrading" in plan.abort_criteria

    def test_estimated_delta_from_graph(self) -> None:
        a = _task("a", delta=-1.5)
        b = _task("b", delta=-0.5)
        g = build_task_graph([a, b])
        plan = build_workflow_plan(g)
        assert plan.estimated_score_delta == pytest.approx(-2.0)

    def test_api_dict_roundtrip(self) -> None:
        a = _task("a")
        g = build_task_graph([a])
        plan = build_workflow_plan(g)
        d = plan.to_api_dict()
        assert "steps" in d
        assert "success_criteria" in d
        assert "abort_criteria" in d
        assert "estimated_score_delta" in d
        assert "default_step_timeout_seconds" in d
        assert isinstance(d["steps"], list)
        assert len(d["steps"]) == 2  # fix + verify

    def test_default_step_timeout_is_exposed(self) -> None:
        a = _task("a")
        g = build_task_graph([a])
        plan = build_workflow_plan(g)

        assert plan.default_step_timeout_seconds == 300.0
        assert plan.to_api_dict()["default_step_timeout_seconds"] == 300.0

    def test_step_timeout_is_exposed(self) -> None:
        a = _task("a")
        g = build_task_graph([a])
        plan = build_workflow_plan(g)

        for step in plan.steps:
            assert "timeout_seconds" in step.to_api_dict()
            assert step.to_api_dict()["timeout_seconds"] is None

    def test_preconditions_first_phase_empty(self) -> None:
        a = _task("a")
        g = build_task_graph([a])
        plan = build_workflow_plan(g)
        # First fix step has no preconditions
        assert plan.steps[0].preconditions == []

    def test_preconditions_later_phase_populated(self) -> None:
        a = _task("a")
        b = _task("b", depends_on=["a"])
        g = build_task_graph([a, b])
        plan = build_workflow_plan(g)
        fix_steps = [s for s in plan.steps if s.tool == "drift_fix_plan"]
        # Second fix step should have a precondition
        assert len(fix_steps) == 2
        assert len(fix_steps[1].preconditions) > 0

