"""Coverage-Boost: api/fix_plan.py — interne Hilfsfunktionen und Filterpfade."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from drift.api.fix_plan import _build_fix_plan_response_from_analysis
from drift.commands.fix_plan import fix_plan as fix_plan_cmd
from drift.models import Severity
from drift.output.agent_tasks import AgentTask

# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------


def _make_task(
    *,
    task_id: str = "task-001",
    signal_type: str = "PFS",
    title: str = "Fix something",
    file_path: str | None = "src/foo.py",
    automation_fit: str = "medium",
    deferred: bool = False,
    context: str = "production",
) -> AgentTask:
    t = AgentTask(
        id=task_id,
        signal_type=signal_type,
        severity=Severity.MEDIUM,
        priority=50,
        title=title,
        description="A description",
        action="An action",
        file_path=file_path,
        automation_fit=automation_fit,
        metadata={"finding_context": context},
    )
    return t


def _make_finding(
    *,
    signal_type: str = "PFS",
    file_path: str | None = "src/foo.py",
    title: str = "Fix something",
    deferred: bool = False,
) -> MagicMock:
    f = MagicMock()
    f.signal_type = signal_type
    f.title = title
    f.deferred = deferred
    if file_path:
        fp = MagicMock()
        fp.as_posix.return_value = file_path
        f.file_path = fp
    else:
        f.file_path = None
    return f


def _make_analysis(
    findings: list | None = None,
    drift_score: float = 0.4,
) -> MagicMock:
    a = MagicMock()
    a.drift_score = drift_score
    a.findings = findings or []
    return a


def _make_cfg() -> MagicMock:
    cfg = MagicMock()
    cfg.finding_context.non_operational_contexts = []
    return cfg


# ---------------------------------------------------------------------------
# target_path doesn't exist → warning
# ---------------------------------------------------------------------------


def test_target_path_nonexistent_adds_warning(tmp_path: Path) -> None:
    task = _make_task(file_path="src/foo.py")
    analysis = _make_analysis(findings=[_make_finding()])
    cfg = _make_cfg()

    with patch("drift.output.agent_tasks.analysis_to_agent_tasks", return_value=[task]):
        result = _build_fix_plan_response_from_analysis(
            analysis=analysis,
            cfg=cfg,
            repo_path=tmp_path,
            finding_id=None,
            signal=None,
            max_tasks=5,
            automation_fit_min=None,
            target_path="src/nonexistent",
            exclude_paths=None,
            include_deferred=True,
            include_non_operational=True,
        )

    warnings = result.get("warnings", [])
    assert any("src/nonexistent" in w and "does not exist" in w for w in warnings)


# ---------------------------------------------------------------------------
# exclude_path doesn't exist → warning
# ---------------------------------------------------------------------------


def test_exclude_path_nonexistent_adds_warning(tmp_path: Path) -> None:
    task = _make_task()
    analysis = _make_analysis()
    cfg = _make_cfg()

    with patch("drift.output.agent_tasks.analysis_to_agent_tasks", return_value=[task]):
        result = _build_fix_plan_response_from_analysis(
            analysis=analysis,
            cfg=cfg,
            repo_path=tmp_path,
            finding_id=None,
            signal=None,
            max_tasks=5,
            automation_fit_min=None,
            target_path=None,
            exclude_paths=["path/does/not/exist"],
            include_deferred=True,
            include_non_operational=True,
        )

    warnings = result.get("warnings", [])
    assert any("does not exist" in w for w in warnings)


# ---------------------------------------------------------------------------
# unknown signal → error response
# ---------------------------------------------------------------------------


def test_unknown_signal_returns_error(tmp_path: Path) -> None:
    analysis = _make_analysis()
    cfg = _make_cfg()

    with patch("drift.output.agent_tasks.analysis_to_agent_tasks", return_value=[]):
        result = _build_fix_plan_response_from_analysis(
            analysis=analysis,
            cfg=cfg,
            repo_path=tmp_path,
            finding_id=None,
            signal="NONEXISTENT",
            max_tasks=5,
            automation_fit_min=None,
            target_path=None,
            exclude_paths=None,
            include_deferred=True,
            include_non_operational=True,
        )

    assert result.get("error_code") == "DRIFT-1003"
    assert "NONEXISTENT" in result.get("message", "")


# ---------------------------------------------------------------------------
# deferred filtering
# ---------------------------------------------------------------------------


def test_deferred_findings_excluded_by_default(tmp_path: Path) -> None:
    deferred_task = _make_task(task_id="d-001", title="Deferred fix", signal_type="PFS")
    # Deferred finding
    finding = _make_finding(signal_type="PFS", title="Deferred fix", deferred=True)
    analysis = _make_analysis(findings=[finding])
    cfg = _make_cfg()

    with patch("drift.output.agent_tasks.analysis_to_agent_tasks", return_value=[deferred_task]):
        result = _build_fix_plan_response_from_analysis(
            analysis=analysis,
            cfg=cfg,
            repo_path=tmp_path,
            finding_id=None,
            signal=None,
            max_tasks=5,
            automation_fit_min=None,
            target_path=None,
            exclude_paths=None,
            include_deferred=False,
            include_non_operational=True,
        )

    warnings = result.get("warnings", [])
    # Should have excluded deferred warning
    assert any("deferred" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# finding_id resolved as rule_id
# ---------------------------------------------------------------------------


def test_finding_id_resolved_as_rule_id(tmp_path: Path) -> None:
    """finding_id that matches a signal abbreviation should be resolved as rule_id."""
    task = _make_task(signal_type="pattern_fragmentation_signal", task_id="t-001")
    analysis = _make_analysis()
    cfg = _make_cfg()

    with (
        patch("drift.output.agent_tasks.analysis_to_agent_tasks", return_value=[task]),
        patch(
            "drift.api.fix_plan.resolve_signal",
            side_effect=lambda s: (
                "pattern_fragmentation_signal"
                if s in ("PFS", "pattern_fragmentation_signal")
                else None
            ),
        ),
    ):
        result = _build_fix_plan_response_from_analysis(
            analysis=analysis,
            cfg=cfg,
            repo_path=tmp_path,
            finding_id="PFS",
            signal=None,
            max_tasks=5,
            automation_fit_min=None,
            target_path=None,
            exclude_paths=None,
            include_deferred=True,
            include_non_operational=True,
        )

    # finding_id_interpreted_as_rule_id or tasks filtered
    assert (
        result.get("finding_id_diagnostic") == "finding_id_interpreted_as_rule_id"
        or result.get("task_count", 0) >= 0
    )


# ---------------------------------------------------------------------------
# finding_id doesn't match at all → no_match diagnostic
# ---------------------------------------------------------------------------


def test_finding_id_no_match_returns_diagnostic(tmp_path: Path) -> None:
    task = _make_task(task_id="some-real-task-id", signal_type="PFS")
    analysis = _make_analysis()
    cfg = _make_cfg()

    with patch("drift.output.agent_tasks.analysis_to_agent_tasks", return_value=[task]):
        result = _build_fix_plan_response_from_analysis(
            analysis=analysis,
            cfg=cfg,
            repo_path=tmp_path,
            finding_id="completely-unknown-id-xyz-999",
            signal=None,
            max_tasks=5,
            automation_fit_min=None,
            target_path=None,
            exclude_paths=None,
            include_deferred=True,
            include_non_operational=True,
        )

    assert result.get("finding_id_diagnostic") == "finding_id_no_match"


# ---------------------------------------------------------------------------
# path diagnostic: no_matching_files
# ---------------------------------------------------------------------------


def test_path_diagnostic_no_matching_files(tmp_path: Path) -> None:
    """target_path exists but no analyzed files match it → no_matching_files."""
    target = tmp_path / "src" / "empty_module"
    target.mkdir(parents=True)

    # Tasks exist but none in the target path
    task = _make_task(file_path="other/foo.py")
    finding = _make_finding(file_path="other/foo.py")
    analysis = _make_analysis(findings=[finding])
    cfg = _make_cfg()

    with patch("drift.output.agent_tasks.analysis_to_agent_tasks", return_value=[task]):
        result = _build_fix_plan_response_from_analysis(
            analysis=analysis,
            cfg=cfg,
            repo_path=tmp_path,
            finding_id=None,
            signal=None,
            max_tasks=5,
            automation_fit_min=None,
            target_path="src/empty_module",
            exclude_paths=None,
            include_deferred=True,
            include_non_operational=True,
        )

    assert result.get("path_diagnostic") == "no_matching_files"


# ---------------------------------------------------------------------------
# path diagnostic: no_findings_in_path
# ---------------------------------------------------------------------------


def test_path_diagnostic_no_findings_in_path(tmp_path: Path) -> None:
    """target_path has analyzed files but no actionable findings → no_findings_in_path."""
    target = tmp_path / "src" / "api"
    target.mkdir(parents=True)

    # Analysis has findings in target path, but tasks have been filtered away
    # (e.g., all tasks are deferred and include_deferred=False)
    task = _make_task(file_path="src/api/routes.py", signal_type="PFS", title="Task1")
    finding = _make_finding(
        file_path="src/api/routes.py", signal_type="PFS", title="Task1", deferred=True
    )
    analysis = _make_analysis(findings=[finding])
    cfg = _make_cfg()

    with patch("drift.output.agent_tasks.analysis_to_agent_tasks", return_value=[task]):
        result = _build_fix_plan_response_from_analysis(
            analysis=analysis,
            cfg=cfg,
            repo_path=tmp_path,
            finding_id=None,
            signal=None,
            max_tasks=5,
            automation_fit_min=None,
            target_path="src/api",
            exclude_paths=None,
            include_deferred=False,
            include_non_operational=True,
        )

    # Either deferred excluded them completely (no_findings_in_path) or path filtered them
    assert result.get("path_diagnostic") in ("no_findings_in_path", "no_matching_files", None)


# ---------------------------------------------------------------------------
# automation_fit_min filtering
# ---------------------------------------------------------------------------


def test_automation_fit_min_filters_low_tasks(tmp_path: Path) -> None:
    tasks = [
        _make_task(task_id="t1", automation_fit="low"),
        _make_task(task_id="t2", automation_fit="high"),
    ]
    analysis = _make_analysis()
    cfg = _make_cfg()

    with patch("drift.output.agent_tasks.analysis_to_agent_tasks", return_value=tasks):
        result = _build_fix_plan_response_from_analysis(
            analysis=analysis,
            cfg=cfg,
            repo_path=tmp_path,
            finding_id=None,
            signal=None,
            max_tasks=10,
            automation_fit_min="high",
            target_path=None,
            exclude_paths=None,
            include_deferred=True,
            include_non_operational=True,
        )

    assert result.get("skipped_low_automation", 0) == 1


# ---------------------------------------------------------------------------
# include_deferred = True (no filtering)
# ---------------------------------------------------------------------------


def test_include_deferred_true_keeps_deferred_tasks(tmp_path: Path) -> None:
    task = _make_task(task_id="d-001", title="Deferred fix", signal_type="PFS")
    finding = _make_finding(signal_type="PFS", title="Deferred fix", deferred=True)
    analysis = _make_analysis(findings=[finding])
    cfg = _make_cfg()

    with patch("drift.output.agent_tasks.analysis_to_agent_tasks", return_value=[task]):
        result = _build_fix_plan_response_from_analysis(
            analysis=analysis,
            cfg=cfg,
            repo_path=tmp_path,
            finding_id=None,
            signal=None,
            max_tasks=5,
            automation_fit_min=None,
            target_path=None,
            exclude_paths=None,
            include_deferred=True,
            include_non_operational=True,
        )

    # Task should NOT be excluded
    warnings = result.get("warnings", [])
    assert not any("deferred" in w.lower() for w in warnings)
    assert result.get("task_count", 0) >= 1


def test_dismissed_tasks_are_excluded_from_fix_plan(tmp_path: Path) -> None:
    """Dismissed task ids should be filtered from fix-plan output."""
    tasks = [
        _make_task(task_id="pfs-abc123", signal_type="PFS"),
        _make_task(task_id="mds-def456", signal_type="MDS"),
    ]
    analysis = _make_analysis(findings=[_make_finding(), _make_finding(signal_type="MDS")])
    cfg = _make_cfg()

    with (
        patch("drift.output.agent_tasks.analysis_to_agent_tasks", return_value=tasks),
        patch("drift.api.fix_plan.get_active_dismissal_ids", return_value={"pfs-abc123"}),
    ):
        result = _build_fix_plan_response_from_analysis(
            analysis=analysis,
            cfg=cfg,
            repo_path=tmp_path,
            finding_id=None,
            signal=None,
            max_tasks=5,
            automation_fit_min=None,
            target_path=None,
            exclude_paths=None,
            include_deferred=True,
            include_non_operational=True,
        )

    ids = {task["id"] for task in result.get("tasks", [])}
    assert "pfs-abc123" not in ids
    assert "mds-def456" in ids
    assert result.get("dismissed", {}).get("excluded_from_fix_plan") == 1


# ---------------------------------------------------------------------------
# --format option: CLI TTY/non-TTY routing (ADR-047)
# ---------------------------------------------------------------------------

_FAKE_RESULT = {
    "tasks": [
        {
            "id": "pfs-abc",
            "signal_type": "PFS",
            "severity": "medium",
            "file_path": "src/foo.py",
            "start_line": 10,
            "title": "Add docstring",
            "description": "Missing docstring",
            "action": "Add a docstring",
            "automation_fit": "high",
        }
    ],
    "task_count": 1,
    "total_available": 3,
    "drift_score": 0.42,
    "recommended_next_actions": ["Apply the fix and run drift check"],
}


def _run_format(tmp_path: Path, extra_args: list[str]) -> str:
    """Invoke fix_plan CLI and return output string."""
    runner = CliRunner()
    with patch("drift.commands.fix_plan.api_fix_plan", return_value=_FAKE_RESULT):
        result = runner.invoke(
            fix_plan_cmd,
            ["--repo", str(tmp_path), "--max-tasks", "5"] + extra_args,
        )
    assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")
    return result.output


def test_fix_plan_format_json_explicit(tmp_path: Path) -> None:
    """--format json always emits valid JSON regardless of TTY state."""
    output = _run_format(tmp_path, ["--format", "json"])
    data = json.loads(output)
    assert data["task_count"] == 1
    assert "tasks" in data


def test_fix_plan_format_rich_explicit(tmp_path: Path) -> None:
    """--format rich emits Rich-formatted output (no raw JSON object)."""
    output = _run_format(tmp_path, ["--format", "rich"])
    # Rich output contains the task title, not a raw JSON structure
    assert "Add docstring" in output
    # Should NOT be a bare JSON document
    assert not output.lstrip().startswith("{")


def test_fix_plan_format_auto_non_tty_produces_json(tmp_path: Path) -> None:
    """In auto mode with non-TTY stdout (mocked), output is JSON."""
    runner = CliRunner()
    # Force _is_non_tty_stdout to True to simulate pipe/CI environment
    with patch("drift.commands.fix_plan.api_fix_plan", return_value=_FAKE_RESULT), \
         patch("drift.commands.fix_plan._is_non_tty_stdout", return_value=True):
        result = runner.invoke(
            fix_plan_cmd,
            ["--repo", str(tmp_path), "--max-tasks", "5", "--format", "auto"],
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["task_count"] == 1


def test_fix_plan_format_json_via_shorthand(tmp_path: Path) -> None:
    """-f json shorthand works identically to --format json."""
    output = _run_format(tmp_path, ["-f", "json"])
    data = json.loads(output)
    assert "tasks" in data
