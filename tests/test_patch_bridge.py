"""Tests for TaskSpec → PatchIntent and AgentTask → PatchIntent bridges."""

from __future__ import annotations

from drift.models._agent import AgentTask
from drift.models._enums import ChangeScope, Severity
from drift.models._patch import BlastRadius, PatchIntent
from drift.task_spec import ArchitectureLayer, TaskSpec


class TestTaskSpecToPatchIntent:
    def test_basic_bridge(self) -> None:
        spec = TaskSpec(
            goal="Add phantom-reference signal for stale imports",
            affected_layers=[ArchitectureLayer.SIGNALS, ArchitectureLayer.TESTS],
            scope_boundaries=["src/drift/signals/phantom.py", "tests/test_phantom*.py"],
            forbidden_paths=["src/drift/pipeline.py"],
            quality_constraints=["Precision >= 70%"],
            acceptance_criteria=["Signal registered"],
            requires_adr=True,
            depends_on=["ADR-045"],
        )
        intent = spec.to_patch_intent(task_id="task-001")
        assert isinstance(intent, PatchIntent)
        assert intent.task_id == "task-001"
        assert intent.declared_files == spec.scope_boundaries
        assert intent.forbidden_paths == spec.forbidden_paths
        assert intent.quality_constraints == spec.quality_constraints
        assert intent.acceptance_criteria == spec.acceptance_criteria
        assert intent.expected_outcome == spec.goal

    def test_session_id_forwarded(self) -> None:
        spec = TaskSpec(
            goal="Fix linting in output module",
            affected_layers=[ArchitectureLayer.OUTPUT],
            scope_boundaries=["src/drift/output/*.py"],
            acceptance_criteria=["ruff clean"],
            requires_adr=True,
            depends_on=["ADR-001"],
        )
        intent = spec.to_patch_intent(task_id="t-1", session_id="sess-xyz")
        assert intent.session_id == "sess-xyz"

    def test_blast_radius_default_local(self) -> None:
        spec = TaskSpec(
            goal="Fix typo in docs module",
            affected_layers=[ArchitectureLayer.DOCS],
            acceptance_criteria=["Typo fixed"],
        )
        intent = spec.to_patch_intent(task_id="t-2")
        assert intent.blast_radius == BlastRadius.LOCAL


class TestAgentTaskToPatchIntent:
    def _make_task(self, **overrides) -> AgentTask:
        defaults = {
            "id": "at-001",
            "signal_type": "pattern_fragmentation",
            "severity": Severity.MEDIUM,
            "priority": 1,
            "title": "Consolidate error handlers",
            "description": "Multiple error handling patterns found",
            "action": "Unify error handlers to canonical form",
            "file_path": "src/drift/api/scan.py",
            "change_scope": ChangeScope.LOCAL,
            "constraints": ["Do not modify pipeline.py"],
            "success_criteria": ["No new findings"],
            "verify_plan": [{"command": "pytest", "args": ["-k", "test_scan"]}],
        }
        defaults.update(overrides)
        return AgentTask(**defaults)

    def test_basic_bridge(self) -> None:
        task = self._make_task()
        intent = task.to_patch_intent()
        assert isinstance(intent, PatchIntent)
        assert intent.task_id == "at-001"
        assert "src/drift/api/scan.py" in intent.declared_files
        assert intent.constraints == ["Do not modify pipeline.py"]
        assert intent.blast_radius == BlastRadius.LOCAL
        assert intent.expected_outcome == "Consolidate error handlers"

    def test_change_scope_module(self) -> None:
        task = self._make_task(change_scope=ChangeScope.MODULE)
        intent = task.to_patch_intent()
        assert intent.blast_radius == BlastRadius.MODULE

    def test_change_scope_cross_module(self) -> None:
        task = self._make_task(change_scope=ChangeScope.CROSS_MODULE)
        intent = task.to_patch_intent()
        assert intent.blast_radius == BlastRadius.REPO

    def test_session_id(self) -> None:
        task = self._make_task()
        intent = task.to_patch_intent(session_id="s-123")
        assert intent.session_id == "s-123"

    def test_related_files_included(self) -> None:
        task = self._make_task(
            related_files=["src/drift/api/helpers.py", "tests/test_helpers.py"]
        )
        intent = task.to_patch_intent()
        assert "src/drift/api/helpers.py" in intent.declared_files
        assert "tests/test_helpers.py" in intent.declared_files

    def test_acceptance_from_success_criteria(self) -> None:
        task = self._make_task(success_criteria=["No new findings", "Tests pass"])
        intent = task.to_patch_intent()
        assert "No new findings" in intent.acceptance_criteria
        assert "Tests pass" in intent.acceptance_criteria
