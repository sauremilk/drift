"""Tests for ADR-073: Consolidation Opportunity Detector.

Tests ``build_consolidation_groups()`` in task_graph.py and
``ConsolidationGroup`` in models/_agent.py.
"""

from __future__ import annotations

from drift.models import Severity
from drift.models._agent import AgentTask, ConsolidationGroup
from drift.task_graph import build_consolidation_groups, build_task_graph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _batch_task(
    task_id: str,
    signal: str = "pattern_fragmentation",
    fix_template_class: str = "extract-function",
    affected_files: list[str] | None = None,
    batch_eligible: bool = True,
) -> AgentTask:
    return AgentTask(
        id=task_id,
        signal_type=signal,
        severity=Severity.MEDIUM,
        priority=1,
        title=f"Task {task_id}",
        description="desc",
        action="fix",
        file_path=(affected_files or ["a.py"])[0],
        metadata={
            "fix_template_class": fix_template_class,
            "batch_eligible": batch_eligible,
            "affected_files_for_pattern": affected_files or [],
        },
    )


# ---------------------------------------------------------------------------
# ConsolidationGroup dataclass tests
# ---------------------------------------------------------------------------


class TestConsolidationGroup:
    def test_to_api_dict(self) -> None:
        g = ConsolidationGroup(
            group_id="PFS-extract-function",
            signal="PFS",
            edit_kind="extract-function",
            instance_count=3,
            canonical_file="src/utils.py",
            affected_files=["src/a.py", "src/b.py", "src/utils.py"],
            task_ids=["t1", "t2", "t3"],
            estimated_net_finding_reduction=2,
        )
        d = g.to_api_dict()
        assert d["group_id"] == "PFS-extract-function"
        assert d["instance_count"] == 3
        assert d["canonical_file"] == "src/utils.py"
        assert d["estimated_net_finding_reduction"] == 2
        assert d["affected_files_total"] == 3
        assert len(d["task_ids"]) == 3

    def test_affected_files_capped_at_15(self) -> None:
        files = [f"file_{i}.py" for i in range(20)]
        g = ConsolidationGroup(
            group_id="test",
            signal="PFS",
            edit_kind="x",
            instance_count=2,
            affected_files=files,
            task_ids=["t1", "t2"],
        )
        d = g.to_api_dict()
        assert len(d["affected_files"]) == 15
        assert d["affected_files_total"] == 20


# ---------------------------------------------------------------------------
# build_consolidation_groups tests
# ---------------------------------------------------------------------------


class TestBuildConsolidationGroups:
    def test_empty_tasks(self) -> None:
        assert build_consolidation_groups([]) == []

    def test_single_task_no_group(self) -> None:
        """A single batch-eligible task doesn't form a group (need ≥2)."""
        tasks = [_batch_task("t1")]
        groups = build_consolidation_groups(tasks)
        assert groups == []

    def test_two_tasks_form_group(self) -> None:
        tasks = [
            _batch_task("t1", affected_files=["a.py", "common.py"]),
            _batch_task("t2", affected_files=["b.py", "common.py"]),
        ]
        groups = build_consolidation_groups(tasks)
        assert len(groups) == 1

        g = groups[0]
        assert g.instance_count == 2
        assert g.canonical_file == "common.py"  # appears twice
        assert set(g.task_ids) == {"t1", "t2"}
        assert g.estimated_net_finding_reduction == 1

    def test_back_reference_on_tasks(self) -> None:
        tasks = [
            _batch_task("t1"),
            _batch_task("t2"),
        ]
        groups = build_consolidation_groups(tasks)
        assert len(groups) == 1
        assert tasks[0].consolidation_group_id == groups[0].group_id
        assert tasks[1].consolidation_group_id == groups[0].group_id

    def test_non_batch_eligible_excluded(self) -> None:
        tasks = [
            _batch_task("t1"),
            _batch_task("t2", batch_eligible=False),
        ]
        groups = build_consolidation_groups(tasks)
        assert groups == []
        assert tasks[0].consolidation_group_id is None

    def test_different_signals_separate_groups(self) -> None:
        tasks = [
            _batch_task("t1", signal="pattern_fragmentation", affected_files=["a.py"]),
            _batch_task("t2", signal="pattern_fragmentation", affected_files=["b.py"]),
            _batch_task("t3", signal="mutant_duplicate",
                        fix_template_class="extract-function", affected_files=["c.py"]),
            _batch_task("t4", signal="mutant_duplicate",
                        fix_template_class="extract-function", affected_files=["d.py"]),
        ]
        groups = build_consolidation_groups(tasks)
        assert len(groups) == 2
        signal_set = {g.signal for g in groups}
        assert "PFS" in signal_set
        assert "MDS" in signal_set

    def test_canonical_file_most_frequent(self) -> None:
        tasks = [
            _batch_task("t1", affected_files=["rare.py", "common.py"]),
            _batch_task("t2", affected_files=["common.py"]),
            _batch_task("t3", affected_files=["other.py", "common.py"]),
        ]
        groups = build_consolidation_groups(tasks)
        assert len(groups) == 1
        assert groups[0].canonical_file == "common.py"

    def test_deduped_affected_files(self) -> None:
        tasks = [
            _batch_task("t1", affected_files=["a.py", "shared.py"]),
            _batch_task("t2", affected_files=["shared.py", "b.py"]),
        ]
        groups = build_consolidation_groups(tasks)
        assert len(groups) == 1
        # shared.py should appear only once in affected_files
        assert groups[0].affected_files.count("shared.py") == 1


# ---------------------------------------------------------------------------
# Integration with build_task_graph
# ---------------------------------------------------------------------------


class TestConsolidationInTaskGraph:
    def test_task_graph_includes_consolidation_groups(self) -> None:
        tasks = [
            _batch_task("t1", affected_files=["a.py"]),
            _batch_task("t2", affected_files=["b.py"]),
        ]
        graph = build_task_graph(tasks)
        assert len(graph.consolidation_groups) == 1

    def test_task_graph_api_dict_includes_consolidation(self) -> None:
        tasks = [
            _batch_task("t1", affected_files=["a.py"]),
            _batch_task("t2", affected_files=["b.py"]),
        ]
        graph = build_task_graph(tasks)
        api = graph.to_api_dict()
        assert "consolidation_opportunities" in api
        assert len(api["consolidation_opportunities"]) == 1
        assert api["consolidation_opportunities"][0]["instance_count"] == 2

    def test_empty_graph_has_empty_consolidation(self) -> None:
        graph = build_task_graph([])
        assert graph.consolidation_groups == []
        assert graph.to_api_dict()["consolidation_opportunities"] == []

    def test_task_api_dict_includes_consolidation_group_id(self) -> None:
        from drift.task_graph import _task_to_api_dict

        tasks = [
            _batch_task("t1", affected_files=["a.py"]),
            _batch_task("t2", affected_files=["b.py"]),
        ]
        build_consolidation_groups(tasks)  # sets consolidation_group_id
        api = _task_to_api_dict(tasks[0])
        assert "consolidation_group_id" in api
        assert api["consolidation_group_id"] is not None

    def test_task_api_dict_includes_similar_outcomes_field(self) -> None:
        from drift.task_graph import _task_to_api_dict

        task = _batch_task("t1")
        task.similar_outcomes = {
            "total_outcomes": 5, "improving": 3, "regressing": 2, "confidence": 0.6
        }
        api = _task_to_api_dict(task)
        assert api["similar_outcomes"] is not None
        assert api["similar_outcomes"]["total_outcomes"] == 5
