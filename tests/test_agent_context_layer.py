"""Tests for ADR-031 Agent Context Layer (M7 + M3 + M1).

Covers:
- M7: Plan-staleness detection
- M3: Auto-profiling by session phase
- M1: drift_map architecture overview
"""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from unittest.mock import patch

import pytest


def _run_tool(result: object) -> object:
    """Transparently await async MCP tool results in sync test context."""
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


# ---------------------------------------------------------------------------
# M3 — Auto-profiling by session phase (_effective_profile)
# ---------------------------------------------------------------------------


class TestEffectiveProfile:
    def test_explicit_overrides_phase(self):
        from drift.mcp_server import _effective_profile
        from drift.session import DriftSession

        s = DriftSession(session_id="x", repo_path="/tmp/repo", phase="fix")
        assert _effective_profile(s, "verifier") == "verifier"

    def test_phase_derived_when_no_explicit(self):
        from drift.mcp_server import _effective_profile
        from drift.session import DriftSession

        for phase, expected in [
            ("init", "planner"),
            ("scan", "planner"),
            ("fix", "coder"),
            ("verify", "verifier"),
            ("done", "merge_readiness"),
        ]:
            s = DriftSession(session_id="x", repo_path="/tmp/repo", phase=phase)
            assert _effective_profile(s, None) == expected, (
                f"phase={phase} should map to {expected}"
            )

    def test_none_when_no_session_no_explicit(self):
        from drift.mcp_server import _effective_profile

        assert _effective_profile(None, None) is None

    def test_explicit_with_no_session(self):
        from drift.mcp_server import _effective_profile

        assert _effective_profile(None, "coder") == "coder"

    def test_unknown_phase_returns_none(self):
        from drift.mcp_server import _effective_profile
        from drift.session import DriftSession

        s = DriftSession(session_id="x", repo_path="/tmp/repo", phase="unknown")
        assert _effective_profile(s, None) is None


# ---------------------------------------------------------------------------
# M7 — Plan-staleness in _enrich_response_with_session
# ---------------------------------------------------------------------------


class TestPlanStalenessEnrichment:
    @pytest.fixture(autouse=True)
    def _reset_sessions(self):
        from drift.session import SessionManager

        SessionManager.reset_instance()
        yield
        SessionManager.reset_instance()

    def test_stale_plan_injected_into_session_block(self):
        from drift.mcp_server import _enrich_response_with_session
        from drift.session import DriftSession

        s = DriftSession(
            session_id="s1",
            repo_path="/tmp/repo",
            git_head_at_plan="aaa111",
            phase="fix",
        )

        raw = json.dumps({"status": "ok", "agent_instruction": "Do stuff."})

        with patch("drift.pipeline._current_git_head", return_value="bbb222"):
            enriched = json.loads(_enrich_response_with_session(raw, s))

        assert enriched["session"]["plan_stale"] is True
        assert "aaa111" in enriched["session"]["plan_stale_reason"]
        assert "bbb222" in enriched["session"]["plan_stale_reason"]

    def test_no_stale_when_head_matches(self):
        from drift.mcp_server import _enrich_response_with_session
        from drift.session import DriftSession

        s = DriftSession(
            session_id="s2",
            repo_path="/tmp/repo",
            git_head_at_plan="aaa111",
            phase="fix",
        )

        raw = json.dumps({"status": "ok"})

        with patch("drift.pipeline._current_git_head", return_value="aaa111"):
            enriched = json.loads(_enrich_response_with_session(raw, s))

        assert "plan_stale" not in enriched.get("session", {})

    def test_no_stale_when_no_plan_head(self):
        from drift.mcp_server import _enrich_response_with_session
        from drift.session import DriftSession

        s = DriftSession(
            session_id="s3",
            repo_path="/tmp/repo",
            phase="fix",
        )

        raw = json.dumps({"status": "ok"})
        enriched = json.loads(_enrich_response_with_session(raw, s))

        assert "plan_stale" not in enriched.get("session", {})


# ---------------------------------------------------------------------------
# M1 — drift_map API function
# ---------------------------------------------------------------------------


class TestDriftMapApi:
    def test_returns_modules_and_dependencies(self, tmp_repo: Path):
        from drift.api import drift_map

        result = drift_map(tmp_repo)

        assert result["status"] == "ok"
        assert isinstance(result["modules"], list)
        assert isinstance(result["dependencies"], list)
        assert isinstance(result["stats"], dict)
        assert result["stats"]["total_files"] > 0
        assert result["stats"]["total_modules"] > 0

    def test_modules_have_expected_fields(self, tmp_repo: Path):
        from drift.api import drift_map

        result = drift_map(tmp_repo)

        for mod in result["modules"]:
            assert "path" in mod
            assert "files" in mod
            assert isinstance(mod["files"], int)
            assert "functions" in mod
            assert "classes" in mod
            assert "lines" in mod
            assert "languages" in mod

    def test_empty_repo_returns_empty(self, tmp_path: Path):
        from drift.api import drift_map

        result = drift_map(tmp_path)

        assert result["status"] == "ok"
        assert result["modules"] == []
        assert result["stats"]["total_files"] == 0

    def test_target_path_restricts_scope(self, tmp_repo: Path):
        from drift.api import drift_map

        # Full map
        full_result = drift_map(tmp_repo)
        # Restricted to services/
        scoped_result = drift_map(tmp_repo, target_path="services")

        assert scoped_result["status"] == "ok"
        scoped_modules = {m["path"] for m in scoped_result["modules"]}
        # All scoped modules should start with services
        for mod_path in scoped_modules:
            assert "services" in mod_path or mod_path == "<root>"

        # Full should have more or equal modules
        assert full_result["stats"]["total_modules"] >= scoped_result["stats"]["total_modules"]

    def test_nonexistent_target_path_returns_empty(self, tmp_repo: Path):
        from drift.api import drift_map

        result = drift_map(tmp_repo, target_path="nonexistent_dir")

        assert result["status"] == "ok"
        assert result["modules"] == []

    def test_max_modules_respected(self, tmp_repo: Path):
        from drift.api import drift_map

        result = drift_map(tmp_repo, max_modules=2)

        assert len(result["modules"]) <= 2

    def test_agent_instruction_present(self, tmp_repo: Path):
        from drift.api import drift_map

        result = drift_map(tmp_repo)

        assert "agent_instruction" in result
        assert len(result["agent_instruction"]) > 0


# ---------------------------------------------------------------------------
# M1 — drift_map MCP tool
# ---------------------------------------------------------------------------


class TestDriftMapMcpTool:
    @pytest.fixture(autouse=True)
    def _reset_sessions(self):
        from drift.session import SessionManager

        SessionManager.reset_instance()
        yield
        SessionManager.reset_instance()

    def test_mcp_tool_returns_valid_json(self, tmp_repo: Path):
        from drift import mcp_server

        raw = _run_tool(mcp_server.drift_map(path=str(tmp_repo)))
        result = json.loads(raw)

        assert result["status"] == "ok"
        assert "modules" in result

    def test_mcp_tool_error_on_broken_api(self, monkeypatch: pytest.MonkeyPatch):
        from drift import mcp_server

        def _broken_map(*_args, **_kwargs):
            raise RuntimeError("map boom")

        monkeypatch.setattr("drift.api.drift_map", _broken_map)
        raw = _run_tool(mcp_server.drift_map(path="."))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-7001"

    def test_mcp_tool_with_session(self, tmp_repo: Path):
        from drift import mcp_server
        from drift.session import SessionManager

        mgr = SessionManager.instance()
        sid = mgr.create(str(tmp_repo))

        raw = _run_tool(mcp_server.drift_map(path=".", session_id=sid))
        result = json.loads(raw)

        assert result["status"] == "ok"
        assert "session" in result
        assert result["session"]["session_id"] == sid
