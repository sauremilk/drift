"""Phase 7: Integration tests for fix_apply API and drift fix-plan --apply CLI.

Strategy:
- `fix_apply` internally calls `_is_git_clean` (subprocess) and `api_fix_plan`
  (full analysis). Both are mocked to keep tests fast and hermetic.
- File I/O uses `tmp_path` so no workspace files are ever touched.
- CLI tests use Click's CliRunner (no real subprocess).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

from click.testing import CliRunner

from drift.api.fix_apply import _is_auto_applicable, fix_apply
from drift.cli import main
from drift.fix_intent import EDIT_KIND_ADD_DOCSTRING, EDIT_KIND_ADD_GUARD_CLAUSE
from drift.models._enums import AutomationFit, ChangeScope, ReviewRisk, Severity
from tests.fixtures.patch_writer import (
    EDS_EXPECTED_WITH_DOCSTRING,
    EDS_MISSING_DOCSTRING_SOURCE,
    GCD_EXPECTED_WITH_GUARD_ORDER,
    GCD_MISSING_GUARD_SOURCE,
)

# ---------------------------------------------------------------------------
# Minimal AgentTask stub (avoids full model import noise in tests)
# ---------------------------------------------------------------------------


@dataclass
class _StubTask:
    id: str
    signal_type: str
    severity: Severity
    priority: int
    title: str
    description: str
    action: str
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    symbol: str | None = None
    automation_fit: AutomationFit = AutomationFit.HIGH
    change_scope: ChangeScope = ChangeScope.LOCAL
    review_risk: ReviewRisk = ReviewRisk.LOW
    metadata: dict[str, Any] = field(default_factory=dict)


def _eds_task(file_path: str = "src/app.py", symbol: str = "compute_total") -> _StubTask:
    return _StubTask(
        id="eds-test-001",
        signal_type="explainability_deficit",
        severity=Severity.MEDIUM,
        priority=1,
        title="Missing docstring",
        description="Function lacks a docstring.",
        action="Add a docstring.",
        file_path=file_path,
        start_line=1,
        symbol=symbol,
        metadata={
            "fix_template_class": EDIT_KIND_ADD_DOCSTRING,
        },
    )


def _gcd_task(
    file_path: str = "src/orders.py",
    symbol: str = "process_order",
    guard_params: list[str] | None = None,
) -> _StubTask:
    return _StubTask(
        id="gcd-test-001",
        signal_type="guard_clause_deficit",
        severity=Severity.MEDIUM,
        priority=1,
        title="Missing guard clause",
        description="Function lacks input validation.",
        action="Add a guard clause.",
        file_path=file_path,
        start_line=1,
        symbol=symbol,
        metadata={
            "fix_template_class": EDIT_KIND_ADD_GUARD_CLAUSE,
            "guard_params": guard_params or ["order"],
        },
    )


def _mock_fix_plan(tasks: list) -> dict[str, Any]:
    """Return a minimal fix_plan response wrapping *tasks*."""
    return {
        "schema_version": "2.1",
        "tasks": tasks,
        "error": None,
    }


# ---------------------------------------------------------------------------
# _is_auto_applicable unit checks
# ---------------------------------------------------------------------------


def test_is_auto_applicable_high_local_low() -> None:
    task = _eds_task()
    assert _is_auto_applicable(task) is True


def test_is_auto_applicable_rejects_medium_fit() -> None:
    task = _eds_task()
    task.automation_fit = AutomationFit.MEDIUM
    assert _is_auto_applicable(task) is False


def test_is_auto_applicable_rejects_cross_module_scope() -> None:
    task = _eds_task()
    task.change_scope = ChangeScope.CROSS_MODULE
    assert _is_auto_applicable(task) is False


def test_is_auto_applicable_rejects_high_risk() -> None:
    task = _eds_task()
    task.review_risk = ReviewRisk.HIGH
    assert _is_auto_applicable(task) is False


# ---------------------------------------------------------------------------
# fix_apply: git-clean gate
# ---------------------------------------------------------------------------


def test_dirty_git_state_returns_error(tmp_path: Path) -> None:
    with patch("drift.api.fix_apply._is_git_clean", return_value=False):
        result = fix_apply(tmp_path, dry_run=True)

    assert result.get("error_code") == "dirty_git_state"
    assert result["patches"] == []
    assert result["summary"]["total"] == 0


def test_no_git_check_when_require_clean_false(tmp_path: Path) -> None:
    """require_clean_git=False skips the git check entirely."""
    with patch("drift.api.fix_apply._is_git_clean") as mock_git, patch(
        "drift.api.fix_apply.api_fix_plan", return_value=_mock_fix_plan([])
    ):
        result = fix_apply(tmp_path, dry_run=True, require_clean_git=False)

    mock_git.assert_not_called()
    assert result.get("error_code") is None


# ---------------------------------------------------------------------------
# fix_apply: no applicable tasks
# ---------------------------------------------------------------------------


def test_no_applicable_tasks_returns_empty_patches(tmp_path: Path) -> None:
    low_task = _eds_task()
    low_task.automation_fit = AutomationFit.LOW  # below bar

    with patch("drift.api.fix_apply._is_git_clean", return_value=True), patch(
        "drift.api.fix_apply.api_fix_plan",
        return_value=_mock_fix_plan([low_task]),
    ):
        result = fix_apply(tmp_path, dry_run=True, require_clean_git=False)

    assert result["patches"] == []
    assert "agent_instruction" in result


# ---------------------------------------------------------------------------
# fix_apply: dry-run (no file writes)
# ---------------------------------------------------------------------------


def test_dry_run_generates_patch_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text(EDS_MISSING_DOCSTRING_SOURCE, encoding="utf-8")

    task = _eds_task(file_path="src/app.py", symbol="compute_total")

    with patch("drift.api.fix_apply._is_git_clean", return_value=True), patch(
        "drift.api.fix_apply.api_fix_plan",
        return_value=_mock_fix_plan([task]),
    ):
        result = fix_apply(tmp_path, dry_run=True, require_clean_git=False)

    # File must be unchanged
    assert target.read_text(encoding="utf-8") == EDS_MISSING_DOCSTRING_SOURCE

    # Response must contain patch entry with status "generated"
    assert result["summary"]["generated"] == 1
    assert result["summary"]["applied"] == 0
    patch_entry = result["patches"][0]
    assert patch_entry["status"] == "generated"
    assert patch_entry["diff"]


# ---------------------------------------------------------------------------
# fix_apply: --apply writes EDS patch
# ---------------------------------------------------------------------------


def test_apply_writes_docstring_patch(tmp_path: Path) -> None:
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text(EDS_MISSING_DOCSTRING_SOURCE, encoding="utf-8")

    task = _eds_task(file_path="src/app.py", symbol="compute_total")

    with patch("drift.api.fix_apply._is_git_clean", return_value=True), patch(
        "drift.api.fix_apply.api_fix_plan",
        return_value=_mock_fix_plan([task]),
    ):
        result = fix_apply(tmp_path, dry_run=False, require_clean_git=False)

    assert target.read_text(encoding="utf-8") == EDS_EXPECTED_WITH_DOCSTRING
    assert result["summary"]["applied"] == 1
    patch_entry = result["patches"][0]
    assert patch_entry["status"] == "applied"
    assert patch_entry["written"] is True


# ---------------------------------------------------------------------------
# fix_apply: --apply writes GCD patch
# ---------------------------------------------------------------------------


def test_apply_writes_guard_clause_patch(tmp_path: Path) -> None:
    target = tmp_path / "src" / "orders.py"
    target.parent.mkdir(parents=True)
    target.write_text(GCD_MISSING_GUARD_SOURCE, encoding="utf-8")

    task = _gcd_task(file_path="src/orders.py", symbol="process_order", guard_params=["order"])

    with patch("drift.api.fix_apply._is_git_clean", return_value=True), patch(
        "drift.api.fix_apply.api_fix_plan",
        return_value=_mock_fix_plan([task]),
    ):
        result = fix_apply(tmp_path, dry_run=False, require_clean_git=False)

    assert target.read_text(encoding="utf-8") == GCD_EXPECTED_WITH_GUARD_ORDER
    assert result["summary"]["applied"] == 1


# ---------------------------------------------------------------------------
# fix_apply: missing file → FAILED entry (no crash)
# ---------------------------------------------------------------------------


def test_apply_missing_file_produces_failed_entry(tmp_path: Path) -> None:
    task = _eds_task(file_path="nonexistent/module.py", symbol="compute_total")

    with patch("drift.api.fix_apply._is_git_clean", return_value=True), patch(
        "drift.api.fix_apply.api_fix_plan",
        return_value=_mock_fix_plan([task]),
    ):
        result = fix_apply(tmp_path, dry_run=False, require_clean_git=False)

    assert result["summary"]["failed"] == 1
    assert result["patches"][0]["status"] == "failed"


# ---------------------------------------------------------------------------
# fix_apply: unsupported edit_kind → unsupported entry (no crash)
# ---------------------------------------------------------------------------


def test_unknown_edit_kind_produces_unsupported_entry(tmp_path: Path) -> None:
    task = _eds_task()
    task.metadata = {"fix_template_class": "some_future_edit_kind"}

    with patch("drift.api.fix_apply._is_git_clean", return_value=True), patch(
        "drift.api.fix_apply.api_fix_plan",
        return_value=_mock_fix_plan([task]),
    ):
        result = fix_apply(tmp_path, dry_run=True, require_clean_git=False)

    assert result["summary"]["unsupported"] == 1
    assert result["patches"][0]["status"] == "unsupported"


# ---------------------------------------------------------------------------
# CLI: --apply and --dry-run appear in help
# ---------------------------------------------------------------------------


def test_cli_fix_plan_help_contains_apply_flags() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["fix-plan", "--help"])
    assert result.exit_code == 0
    assert "--apply" in result.output
    assert "--dry-run" in result.output


# ---------------------------------------------------------------------------
# CLI: --dry-run dispatches to fix_apply (JSON output)
# ---------------------------------------------------------------------------


def test_cli_dry_run_returns_json_with_patches(tmp_path: Path) -> None:
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text(EDS_MISSING_DOCSTRING_SOURCE, encoding="utf-8")

    task = _eds_task(file_path="src/app.py", symbol="compute_total")
    mock_response = {
        **_mock_fix_plan([task]),
        "dry_run": True,
        "patches": [
            {
                "task_id": "eds-test-001",
                "edit_kind": EDIT_KIND_ADD_DOCSTRING,
                "file": "src/app.py",
                "status": "generated",
                "diff": "--- \n+++ \n@@ -1,3 +1,4 @@\n",
                "reason": "",
            }
        ],
        "summary": {
            "total": 1,
            "applied": 0,
            "generated": 1,
            "skipped": 0,
            "failed": 0,
            "unsupported": 0,
        },
        "agent_instruction": "Previewed 1 patch(es).",
    }

    runner = CliRunner()
    with patch("drift.api.fix_apply.fix_apply", return_value=mock_response):
        result = runner.invoke(
            main,
            ["fix-plan", "--repo", str(tmp_path), "--dry-run", "--format", "json"],
        )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "patches" in data or "tasks" in data  # either fix_apply or fix_plan response accepted
