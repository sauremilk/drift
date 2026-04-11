"""Tests for drift session-report command (C2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner


class TestSessionReportCommand:
    """Test the session-report CLI command."""

    def test_no_session_files_exits_with_message(self, tmp_path: Path) -> None:
        from drift.commands.session_report import session_report

        runner = CliRunner()
        result = runner.invoke(session_report, ["--repo", str(tmp_path)])
        assert result.exit_code != 0
        assert "No session files" in result.output

    def test_load_and_render_session_file(self, tmp_path: Path) -> None:
        from drift.commands.session_report import session_report

        session_data = {
            "session_id": "abc12345-1234-1234-1234-123456789abc",
            "repo_path": str(tmp_path),
            "phase": "fix-loop",
            "tool_calls": 12,
            "created_at": 1000000.0,
            "last_activity": 1000300.0,
            "score_at_start": 0.54,
            "last_scan_score": 0.42,
            "selected_tasks": [{"id": "t1"}, {"id": "t2"}],
            "completed_task_ids": ["t1"],
            "failed_task_ids": [],
            "metrics": {
                "plans_created": 1,
                "tasks_claimed": 2,
                "tasks_completed": 1,
                "tasks_failed": 0,
                "tasks_released": 0,
                "tasks_expired": 0,
                "nudge_checks": 5,
                "nudge_improving": 3,
                "nudge_degrading": 1,
                "nudge_stable": 1,
                "verification_failures": 0,
                "total_findings_seen": 10,
                "findings_acted_on": 4,
                "findings_suppressed": 2,
                "verification_runs": 3,
                "changed_files_total": 5,
                "loc_changed_total": 200,
                "resolved_findings_total": 4,
                "new_findings_total": 1,
                "relocated_findings_total": 1,
            },
        }

        session_file = tmp_path / ".drift-session-abc12345.json"
        session_file.write_text(json.dumps(session_data), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            session_report, ["--repo", str(tmp_path), "--latest"]
        )
        assert result.exit_code == 0
        assert "Session Report" in result.output
        assert "abc12345" in result.output

    def test_json_output(self, tmp_path: Path) -> None:
        from drift.commands.session_report import session_report

        session_data = {
            "session_id": "def12345-1234-1234-1234-123456789abc",
            "repo_path": str(tmp_path),
            "phase": "done",
            "tool_calls": 5,
            "metrics": {},
        }

        session_file = tmp_path / ".drift-session-def12345.json"
        session_file.write_text(json.dumps(session_data), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            session_report,
            ["--file", str(session_file), "--json"],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["session_id"] == "def12345-1234-1234-1234-123456789abc"

    def test_invalid_session_file(self, tmp_path: Path) -> None:
        from drift.commands.session_report import session_report

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(session_report, ["--file", str(bad_file)])
        assert result.exit_code != 0

    def test_invalid_session_payload_shape(self, tmp_path: Path) -> None:
        from drift.commands.session_report import session_report

        invalid_payload = tmp_path / "invalid-shape.json"
        invalid_payload.write_text(json.dumps([{"not": "a-session-dict"}]), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(session_report, ["--file", str(invalid_payload)])
        assert result.exit_code != 0
        assert "Invalid session file format" in result.output

    def test_invalid_session_payload_shape_direct_callback(self, tmp_path: Path) -> None:
        from drift.commands.session_report import session_report

        invalid_payload = tmp_path / "invalid-shape-direct.json"
        invalid_payload.write_text(json.dumps([{"not": "a-session-dict"}]), encoding="utf-8")

        with pytest.raises(SystemExit):
            session_report.callback(
                repo=tmp_path,
                session_file=invalid_payload,
                output_json=False,
                latest=False,
            )

    def test_multiple_sessions_shows_list(self, tmp_path: Path) -> None:
        from drift.commands.session_report import session_report

        for i in range(3):
            f = tmp_path / f".drift-session-{i:08d}.json"
            f.write_text(
                json.dumps({"session_id": f"sid-{i}", "repo_path": str(tmp_path)}),
                encoding="utf-8",
            )

        runner = CliRunner()
        result = runner.invoke(session_report, ["--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "Available session files" in result.output


class TestSessionRenderer:
    """Test the session renderer directly."""

    def test_render_minimal_session(self) -> None:
        from io import StringIO

        from rich.console import Console

        from drift.output.session_renderer import render_session_report

        data = {
            "session_id": "test-1234",
            "repo_path": ".",
            "phase": "init",
            "tool_calls": 0,
            "metrics": {},
        }
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        render_session_report(data, console)
        output = buf.getvalue()
        assert "test-123" in output  # truncated to 8 chars

    def test_render_with_score_delta(self) -> None:
        from io import StringIO

        from rich.console import Console

        from drift.output.session_renderer import render_session_report

        data = {
            "session_id": "test-5678",
            "repo_path": ".",
            "phase": "done",
            "tool_calls": 10,
            "score_at_start": 0.6,
            "last_scan_score": 0.4,
            "metrics": {
                "nudge_checks": 3,
                "nudge_improving": 2,
                "nudge_degrading": 0,
                "nudge_stable": 1,
            },
        }
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        render_session_report(data, console)
        output = buf.getvalue()
        assert "Score" in output

    def test_effectiveness_warnings(self) -> None:
        from drift.output.session_renderer import _compute_warnings

        # High churn, zero resolved
        warnings = _compute_warnings(
            {"changed_files_total": 10, "resolved_findings_total": 0, "new_findings_total": 5},
            {},
        )
        assert any("churn" in w.lower() for w in warnings)

        # Net regression
        warnings = _compute_warnings(
            {"changed_files_total": 5, "resolved_findings_total": 2, "new_findings_total": 5},
            {},
        )
        assert any("regression" in w.lower() for w in warnings)
