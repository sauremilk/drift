"""Tests for PatchIntent, PatchVerdict and related patch engine models."""

from __future__ import annotations

import datetime as _dt

from drift.models._patch import (
    AcceptanceResult,
    BlastRadius,
    DiffMetrics,
    PatchIntent,
    PatchStatus,
    PatchVerdict,
)


class TestPatchStatus:
    def test_values(self) -> None:
        assert PatchStatus.CLEAN == "clean"
        assert PatchStatus.REVIEW_REQUIRED == "review_required"
        assert PatchStatus.ROLLBACK_RECOMMENDED == "rollback_recommended"

    def test_is_str_enum(self) -> None:
        assert isinstance(PatchStatus.CLEAN, str)


class TestBlastRadius:
    def test_values(self) -> None:
        assert BlastRadius.LOCAL == "local"
        assert BlastRadius.MODULE == "module"
        assert BlastRadius.REPO == "repo"


class TestDiffMetrics:
    def test_creation(self) -> None:
        dm = DiffMetrics(
            lines_added=10,
            lines_removed=5,
            files_changed=2,
            files_outside_scope=["extra.py"],
        )
        assert dm.lines_added == 10
        assert dm.lines_removed == 5
        assert dm.files_changed == 2
        assert dm.files_outside_scope == ["extra.py"]

    def test_defaults(self) -> None:
        dm = DiffMetrics(lines_added=0, lines_removed=0, files_changed=0)
        assert dm.files_outside_scope == []


class TestAcceptanceResult:
    def test_met(self) -> None:
        ar = AcceptanceResult(criterion="No new findings", met=True, evidence="nudge clean")
        assert ar.met is True

    def test_unknown(self) -> None:
        ar = AcceptanceResult(criterion="Precision >= 70%", met=None, evidence="not measurable")
        assert ar.met is None


class TestPatchIntent:
    def test_minimal_creation(self) -> None:
        intent = PatchIntent(
            task_id="task-001",
            declared_files=["src/drift/api/patch.py"],
            expected_outcome="Add patch_begin endpoint",
        )
        assert intent.task_id == "task-001"
        assert intent.session_id is None
        assert intent.blast_radius == BlastRadius.LOCAL
        assert intent.forbidden_paths == []
        assert intent.quality_constraints == []
        assert intent.acceptance_criteria == []
        assert intent.constraints == []
        assert intent.max_diff_lines is None
        assert isinstance(intent.created_at, _dt.datetime)

    def test_full_creation(self) -> None:
        intent = PatchIntent(
            task_id="task-002",
            session_id="sess-abc",
            declared_files=["src/drift/api/patch.py", "tests/test_patch_api.py"],
            forbidden_paths=["src/drift/pipeline.py"],
            expected_outcome="Implement patch_check with scope validation",
            blast_radius=BlastRadius.MODULE,
            max_diff_lines=200,
            quality_constraints=["Precision >= 70%"],
            acceptance_criteria=["No new high findings", "All tests pass"],
            constraints=["Do not modify pipeline.py"],
        )
        assert intent.blast_radius == BlastRadius.MODULE
        assert intent.max_diff_lines == 200
        assert len(intent.acceptance_criteria) == 2

    def test_serialization_roundtrip(self) -> None:
        intent = PatchIntent(
            task_id="task-003",
            declared_files=["a.py"],
            expected_outcome="Test roundtrip",
        )
        d = intent.model_dump(mode="json")
        assert d["task_id"] == "task-003"
        assert "created_at" in d
        restored = PatchIntent.model_validate(d)
        assert restored.task_id == intent.task_id

    def test_to_api_dict(self) -> None:
        intent = PatchIntent(
            task_id="task-004",
            declared_files=["x.py"],
            expected_outcome="API dict test",
            blast_radius=BlastRadius.REPO,
        )
        d = intent.to_api_dict()
        assert d["task_id"] == "task-004"
        assert d["blast_radius"] == "repo"
        assert "created_at" in d


class TestPatchVerdict:
    def test_clean_verdict(self) -> None:
        verdict = PatchVerdict(
            task_id="task-001",
            status=PatchStatus.CLEAN,
            scope_compliance=True,
            diff_metrics=DiffMetrics(lines_added=5, lines_removed=2, files_changed=1),
            reasons=["All checks passed"],
        )
        assert verdict.status == PatchStatus.CLEAN
        assert verdict.scope_compliance is True
        assert verdict.scope_violations == []
        assert verdict.architecture_impact == []
        assert verdict.test_passed is None
        assert verdict.acceptance_met == []
        assert verdict.evidence == {}
        assert verdict.merge_readiness == "ready"
        assert isinstance(verdict.checked_at, _dt.datetime)

    def test_review_required_verdict(self) -> None:
        verdict = PatchVerdict(
            task_id="task-002",
            status=PatchStatus.REVIEW_REQUIRED,
            scope_compliance=False,
            scope_violations=["extra.py"],
            diff_metrics=DiffMetrics(
                lines_added=50,
                lines_removed=10,
                files_changed=3,
                files_outside_scope=["extra.py"],
            ),
            architecture_impact=[{"signal": "PFS", "severity": "medium"}],
            reasons=["Scope violation: extra.py not declared"],
            merge_readiness="manual_review",
        )
        assert verdict.status == PatchStatus.REVIEW_REQUIRED
        assert len(verdict.scope_violations) == 1
        assert verdict.merge_readiness == "manual_review"

    def test_rollback_verdict(self) -> None:
        verdict = PatchVerdict(
            task_id="task-003",
            status=PatchStatus.ROLLBACK_RECOMMENDED,
            scope_compliance=False,
            scope_violations=["core.py"],
            diff_metrics=DiffMetrics(lines_added=100, lines_removed=80, files_changed=5),
            reasons=["Degrading architecture impact", "Critical new findings"],
            merge_readiness="blocked",
        )
        assert verdict.status == PatchStatus.ROLLBACK_RECOMMENDED
        assert verdict.merge_readiness == "blocked"

    def test_serialization_roundtrip(self) -> None:
        verdict = PatchVerdict(
            task_id="task-004",
            status=PatchStatus.CLEAN,
            scope_compliance=True,
            diff_metrics=DiffMetrics(lines_added=1, lines_removed=0, files_changed=1),
            reasons=["OK"],
        )
        d = verdict.model_dump(mode="json")
        assert d["status"] == "clean"
        restored = PatchVerdict.model_validate(d)
        assert restored.task_id == verdict.task_id

    def test_to_api_dict(self) -> None:
        verdict = PatchVerdict(
            task_id="task-005",
            status=PatchStatus.REVIEW_REQUIRED,
            scope_compliance=False,
            scope_violations=["z.py"],
            diff_metrics=DiffMetrics(lines_added=10, lines_removed=3, files_changed=2),
            acceptance_met=[
                AcceptanceResult(criterion="Tests pass", met=True, evidence="pytest green"),
            ],
            reasons=["Scope violation"],
            merge_readiness="manual_review",
        )
        d = verdict.to_api_dict()
        assert d["status"] == "review_required"
        assert d["scope_compliance"] is False
        assert len(d["acceptance_met"]) == 1
        assert d["acceptance_met"][0]["criterion"] == "Tests pass"
