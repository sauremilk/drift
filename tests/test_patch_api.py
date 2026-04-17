"""Tests for patch engine API: patch_begin, patch_check, patch_commit."""

from __future__ import annotations

from unittest.mock import patch

from drift.api.patch import patch_begin, patch_check, patch_commit


class TestPatchBegin:
    def test_creates_intent_and_returns_dict(self) -> None:
        result = patch_begin(
            task_id="task-001",
            declared_files=["src/drift/api/patch.py"],
            expected_outcome="Add patch_begin endpoint",
        )
        assert result["task_id"] == "task-001"
        assert "intent" in result
        assert result["intent"]["task_id"] == "task-001"
        assert result["intent"]["blast_radius"] == "local"
        assert "agent_instruction" in result

    def test_with_session_id(self) -> None:
        result = patch_begin(
            task_id="task-002",
            declared_files=["a.py"],
            expected_outcome="Test",
            session_id="sess-abc",
        )
        assert result["intent"]["session_id"] == "sess-abc"

    def test_with_full_params(self) -> None:
        result = patch_begin(
            task_id="task-003",
            declared_files=["a.py", "b.py"],
            expected_outcome="Full test",
            blast_radius="module",
            forbidden_paths=["pipeline.py"],
            max_diff_lines=100,
            quality_constraints=["Precision >= 70%"],
            acceptance_criteria=["Tests pass"],
            constraints=["No pipeline changes"],
        )
        intent = result["intent"]
        assert intent["blast_radius"] == "module"
        assert intent["forbidden_paths"] == ["pipeline.py"]
        assert intent["max_diff_lines"] == 100


class TestPatchCheck:
    def test_clean_verdict_no_scope_violations(self) -> None:
        """When all changed files are within declared scope → CLEAN."""
        with patch("drift.api.patch._get_changed_files") as mock_git:
            mock_git.return_value = ["src/drift/api/patch.py"]
            result = patch_check(
                task_id="task-001",
                declared_files=["src/drift/api/patch.py"],
                path=".",
            )
        assert result["status"] == "clean"
        assert result["scope_compliance"] is True
        assert result["merge_readiness"] == "ready"

    def test_review_required_scope_violation(self) -> None:
        """When files outside declared scope are changed → REVIEW_REQUIRED."""
        with patch("drift.api.patch._get_changed_files") as mock_git:
            mock_git.return_value = ["src/drift/api/patch.py", "src/drift/pipeline.py"]
            result = patch_check(
                task_id="task-002",
                declared_files=["src/drift/api/patch.py"],
                path=".",
            )
        assert result["status"] == "review_required"
        assert result["scope_compliance"] is False
        assert "src/drift/pipeline.py" in result["scope_violations"]
        assert result["merge_readiness"] == "manual_review"

    def test_review_required_forbidden_path(self) -> None:
        """When a changed file matches a forbidden path → REVIEW_REQUIRED."""
        with patch("drift.api.patch._get_changed_files") as mock_git:
            mock_git.return_value = ["src/drift/pipeline.py"]
            result = patch_check(
                task_id="task-003",
                declared_files=["src/drift/pipeline.py"],
                forbidden_paths=["src/drift/pipeline.py"],
                path=".",
            )
        assert result["status"] == "review_required"
        assert "forbidden path" in result["reasons"][0].lower() or (
            "forbidden" in str(result["reasons"]).lower()
        )

    def test_clean_when_no_changes(self) -> None:
        """When git reports no changes → CLEAN (nothing happened)."""
        with patch("drift.api.patch._get_changed_files") as mock_git:
            mock_git.return_value = []
            result = patch_check(
                task_id="task-004",
                declared_files=["a.py"],
                path=".",
            )
        assert result["status"] == "clean"

    def test_diff_metrics_present(self) -> None:
        """Verdict includes diff metrics."""
        with patch("drift.api.patch._get_changed_files") as mock_git:
            mock_git.return_value = ["a.py"]
            with patch("drift.api.patch._compute_diff_metrics") as mock_diff:
                mock_diff.return_value = {
                    "lines_added": 10,
                    "lines_removed": 5,
                    "files_changed": 1,
                }
                result = patch_check(
                    task_id="task-005",
                    declared_files=["a.py"],
                    path=".",
                )
        assert "diff_metrics" in result
        assert result["diff_metrics"]["files_changed"] >= 0

    def test_max_diff_lines_exceeded(self) -> None:
        """When diff exceeds max_diff_lines → REVIEW_REQUIRED."""
        with patch("drift.api.patch._get_changed_files") as mock_git:
            mock_git.return_value = ["a.py"]
            with patch("drift.api.patch._compute_diff_metrics") as mock_diff:
                mock_diff.return_value = {
                    "lines_added": 200,
                    "lines_removed": 50,
                    "files_changed": 1,
                }
                result = patch_check(
                    task_id="task-006",
                    declared_files=["a.py"],
                    max_diff_lines=100,
                    path=".",
                )
        assert result["status"] == "review_required"


class TestPatchCommit:
    def test_produces_evidence_record(self) -> None:
        with patch("drift.api.patch._get_changed_files") as mock_git:
            mock_git.return_value = ["a.py"]
            result = patch_commit(
                task_id="task-001",
                declared_files=["a.py"],
                expected_outcome="Test evidence",
                path=".",
            )
        assert "evidence" in result
        assert result["evidence"]["task_id"] == "task-001"
        assert "intent" in result["evidence"]
        assert "verdict" in result["evidence"]
        assert "merge_readiness" in result

    def test_uses_existing_verdict(self) -> None:
        """When verdict_override is passed, skip re-check."""
        verdict_data = {
            "task_id": "task-002",
            "status": "clean",
            "scope_compliance": True,
            "scope_violations": [],
            "diff_metrics": {
                "lines_added": 5,
                "lines_removed": 2,
                "files_changed": 1,
                "files_outside_scope": [],
            },
            "architecture_impact": [],
            "test_passed": None,
            "acceptance_met": [],
            "reasons": ["OK"],
            "evidence": {},
            "merge_readiness": "ready",
        }
        result = patch_commit(
            task_id="task-002",
            declared_files=["a.py"],
            expected_outcome="Test",
            path=".",
            verdict_override=verdict_data,
        )
        assert result["merge_readiness"] == "ready"
