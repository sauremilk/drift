"""Integration tests for the compile_policy API endpoint."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestCompilePolicyAPI:
    """Test the API wrapper (config loading, telemetry, error handling)."""

    @patch("drift.api.compile_policy._load_config_cached")
    @patch("drift.api.compile_policy._warn_config_issues")
    @patch("drift.api.compile_policy._emit_api_telemetry")
    def test_returns_ok_response(self, mock_tel, mock_warn, mock_cfg, tmp_path: Path):
        from drift.api.compile_policy import compile_policy

        mock_cfg.return_value = MagicMock(calibration=None)
        result = compile_policy(
            str(tmp_path),
            task="add logging to ingestion",
        )
        assert result["status"] == "ok"
        assert result["type"] == "compile_policy"
        assert "task" in result
        assert "rules" in result
        assert "scope" in result
        assert "agent_instruction" in result
        mock_tel.assert_called_once()

    @patch("drift.api.compile_policy._load_config_cached")
    @patch("drift.api.compile_policy._warn_config_issues")
    @patch("drift.api.compile_policy._emit_api_telemetry")
    def test_returns_next_step_contract(self, mock_tel, mock_warn, mock_cfg, tmp_path: Path):
        from drift.api.compile_policy import compile_policy

        mock_cfg.return_value = MagicMock(calibration=None)
        result = compile_policy(
            str(tmp_path),
            task="refactor scoring engine",
            diff_ref=None,
        )
        # Should have next_tool in response
        assert "next_tool" in result or "done_when" in result

    @patch("drift.api.compile_policy._load_config_cached")
    @patch("drift.api.compile_policy._warn_config_issues")
    @patch("drift.api.compile_policy._emit_api_telemetry")
    def test_with_diff_ref(self, mock_tel, mock_warn, mock_cfg, tmp_path: Path):
        from drift.api.compile_policy import compile_policy

        mock_cfg.return_value = MagicMock(calibration=None)
        # git diff will fail in tmp_path (no git repo), should still work
        result = compile_policy(
            str(tmp_path),
            task="fix tests",
            diff_ref="HEAD",
        )
        assert result["status"] == "ok"

    @patch("drift.api.compile_policy._load_config_cached", side_effect=RuntimeError("boom"))
    @patch("drift.api.compile_policy._emit_api_telemetry")
    def test_error_handling(self, mock_tel, mock_cfg, tmp_path: Path):
        from drift.api.compile_policy import compile_policy

        result = compile_policy(
            str(tmp_path),
            task="crash test",
        )
        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-0099"

    @patch("drift.api.compile_policy._load_config_cached")
    @patch("drift.api.compile_policy._warn_config_issues")
    @patch("drift.api.compile_policy._emit_api_telemetry")
    def test_response_profile_shaping(self, mock_tel, mock_warn, mock_cfg, tmp_path: Path):
        from drift.api.compile_policy import compile_policy

        mock_cfg.return_value = MagicMock(calibration=None)
        result = compile_policy(
            str(tmp_path),
            task="test shaping",
            response_profile="compact",
        )
        # Should still be a valid dict (shape_for_profile may transform)
        assert isinstance(result, dict)


class TestCompilePolicyMCPHandler:
    """Test the MCP dispatch integration."""

    def test_dispatch_table_includes_compile_policy(self):
        from drift.serve.a2a_router import _SKILL_DISPATCH, _ensure_dispatch_table

        _ensure_dispatch_table()
        assert "compile_policy" in _SKILL_DISPATCH

    @patch("drift.serve.a2a_router._validate_repo_path", side_effect=lambda p: p)
    def test_handler_calls_api(self, mock_validate):
        from drift.serve.a2a_router import _handle_compile_policy

        with patch(
            "drift.api.compile_policy",
            return_value={"status": "ok", "type": "compile_policy"},
        ) as mock_api:
            result = _handle_compile_policy({
                "path": ".",
                "task": "test task",
                "max_rules": 10,
            })
            mock_api.assert_called_once()
            assert result["status"] == "ok"

    @patch("drift.serve.a2a_router._validate_repo_path", side_effect=lambda p: p)
    def test_handler_defaults(self, mock_validate):
        from drift.serve.a2a_router import _handle_compile_policy

        with patch("drift.api.compile_policy", return_value={"status": "ok"}) as mock_api:
            _handle_compile_policy({"task": "minimal"})
            call_kwargs = mock_api.call_args
            assert call_kwargs.kwargs.get("max_rules", 15) == 15


class TestAgentCardSkill:
    """Test the agent card includes the compile_policy skill."""

    def test_skill_registered(self):
        from drift.serve.agent_card import _build_skills

        skills = _build_skills()
        skill_ids = [s["id"] for s in skills]
        assert "compile_policy" in skill_ids

    def test_skill_has_required_fields(self):
        from drift.serve.agent_card import _build_skills

        skills = _build_skills()
        cp_skill = next(s for s in skills if s["id"] == "compile_policy")
        assert "name" in cp_skill
        assert "description" in cp_skill
        assert "tags" in cp_skill
        assert "examples" in cp_skill


class TestAPIExports:
    """Test that compile_policy is properly exported."""

    def test_importable_from_api(self):
        from drift.api import compile_policy

        assert callable(compile_policy)

    def test_in_stable_api(self):
        from drift.api import STABLE_API

        assert "compile_policy" in STABLE_API
