"""Tests for Issue #203 diagnostic hypothesis contract in MCP fix workflow."""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

import pytest


def _run_tool(result: object) -> object:
    """Transparently await async MCP tool results in sync test context."""
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


@pytest.fixture(autouse=True)
def _reset_sessions() -> None:
    from drift.session import SessionManager

    SessionManager.reset_instance()
    yield
    SessionManager.reset_instance()


def _start_fix_context_session(tmp_path: Path) -> str:
    """Start a session and force it into batch-fix context."""
    from drift import mcp_server
    from drift.session import SessionManager

    start = json.loads(_run_tool(mcp_server.drift_session_start(path=str(tmp_path))))
    session_id = start["session_id"]
    session = SessionManager.instance().get(session_id)
    assert session is not None
    session.phase = "fix"
    session.selected_tasks = [
        {
            "id": "T-1",
            "title": "hypothesis contract task",
            "batch_eligible": True,
        }
    ]
    return session_id


class TestDiagnosticHypothesisBlocking:
    def test_nudge_not_blocked_without_batch_eligible_context(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        from drift import mcp_server
        from drift.session import SessionManager

        start = json.loads(_run_tool(mcp_server.drift_session_start(path=str(tmp_path))))
        session_id = start["session_id"]
        session = SessionManager.instance().get(session_id)
        assert session is not None
        session.phase = "fix"
        session.selected_tasks = [{"id": "T-1", "batch_eligible": False}]

        monkeypatch.setattr(
            "drift.api.nudge",
            lambda *_a, **_kw: {
                "direction": "stable",
                "score": 0.0,
                "safe_to_commit": True,
                "blocking_reasons": [],
                "changed_files": ["src/a.py"],
            },
        )

        result = json.loads(
            _run_tool(mcp_server.drift_nudge(session_id=session_id, changed_files="src/a.py"))
        )

        assert result.get("error_code") != "DRIFT-6003"
        assert result["safe_to_commit"] is True

    def test_nudge_blocks_when_hypothesis_missing(self, tmp_path: Path) -> None:
        from drift import mcp_server

        session_id = _start_fix_context_session(tmp_path)

        raw = _run_tool(mcp_server.drift_nudge(session_id=session_id, changed_files="src/a.py"))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-6003"
        assert result["blocked_tool"] == "drift_nudge"
        assert result["diagnostic_hypothesis_reason"] == "missing_diagnostic_hypothesis"
        assert result["session_id"] == session_id

    def test_nudge_blocks_when_hypothesis_invalid(self, tmp_path: Path) -> None:
        from drift import mcp_server

        session_id = _start_fix_context_session(tmp_path)

        raw = _run_tool(
            mcp_server.drift_nudge(
                session_id=session_id,
                changed_files="src/a.py",
                diagnostic_hypothesis={"affected_files": ["src/a.py"]},
            )
        )
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-6003"
        assert result["diagnostic_hypothesis_reason"] == "invalid_diagnostic_hypothesis"
        errors = result.get("suggested_fix", {}).get("validation_errors", [])
        assert any("suspected_root_cause" in err for err in errors)
        assert any("minimal_intended_change" in err for err in errors)
        assert any("non_goals" in err for err in errors)


class TestDiagnosticHypothesisTraceability:
    def test_nudge_accepts_valid_hypothesis_and_emits_evidence(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        from drift import mcp_server

        session_id = _start_fix_context_session(tmp_path)

        monkeypatch.setattr(
            "drift.api.nudge",
            lambda *_a, **_kw: {
                "direction": "improving",
                "score": 10.0,
                "safe_to_commit": True,
                "blocking_reasons": [],
                "changed_files": ["src/a.py"],
            },
        )

        payload = {
            "affected_files": ["src/a.py"],
            "suspected_root_cause": "Missing early guard caused cascading findings",
            "minimal_intended_change": "Add guard clause in parser entry point",
            "non_goals": ["No refactor", "No scoring changes"],
        }
        raw = _run_tool(
            mcp_server.drift_nudge(
                session_id=session_id,
                changed_files="src/a.py",
                diagnostic_hypothesis=payload,
            )
        )
        result = json.loads(raw)

        assert result["hypothesis_id"].startswith("hyp-")
        assert result["verification_evidence"]["tool"] == "drift_nudge"
        assert result["verification_evidence"]["safe_to_commit"] is True

        trace_raw = _run_tool(mcp_server.drift_session_trace(session_id=session_id, last_n=10))
        trace = json.loads(trace_raw)["trace"]
        nudge_entries = [e for e in trace if e.get("tool") == "drift_nudge"]
        assert nudge_entries
        assert nudge_entries[-1].get("hypothesis_id") == result["hypothesis_id"]
        assert nudge_entries[-1].get("verification_evidence", {}).get("tool") == "drift_nudge"

    def test_diff_reuses_registered_hypothesis_id(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        from drift import mcp_server

        session_id = _start_fix_context_session(tmp_path)

        monkeypatch.setattr(
            "drift.api.nudge",
            lambda *_a, **_kw: {
                "direction": "stable",
                "score": 10.0,
                "safe_to_commit": False,
                "blocking_reasons": ["x"],
                "changed_files": ["src/a.py"],
            },
        )
        monkeypatch.setattr(
            "drift.api.diff",
            lambda *_a, **_kw: {
                "status": "ok",
                "accept_change": False,
                "blocking_reasons": ["y"],
            },
        )

        payload = {
            "affected_files": ["src/a.py"],
            "suspected_root_cause": "Invalid state transition in helper",
            "minimal_intended_change": "Bound mutation to helper guard",
            "non_goals": ["No API changes"],
        }
        nudge = json.loads(
            _run_tool(
                mcp_server.drift_nudge(
                    session_id=session_id,
                    changed_files="src/a.py",
                    diagnostic_hypothesis=payload,
                )
            )
        )
        hypothesis_id = nudge["hypothesis_id"]

        diff = json.loads(
            _run_tool(mcp_server.drift_diff(session_id=session_id, hypothesis_id=hypothesis_id))
        )

        assert diff["hypothesis_id"] == hypothesis_id
        assert diff["verification_evidence"]["tool"] == "drift_diff"
        assert diff["verification_evidence"]["accept_change"] is False

        trace_raw = _run_tool(mcp_server.drift_session_trace(session_id=session_id, last_n=20))
        trace = json.loads(trace_raw)["trace"]
        diff_entries = [e for e in trace if e.get("tool") == "drift_diff"]
        assert diff_entries
        assert diff_entries[-1].get("hypothesis_id") == hypothesis_id
        assert diff_entries[-1].get("verification_evidence", {}).get("tool") == "drift_diff"
