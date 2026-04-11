"""Tests for issues #138, #139, #140."""

from __future__ import annotations

import asyncio
import json

import pytest


class TestIssue138NegativeContextErrorEnvelope:
    """#138: drift_negative_context must wrap exceptions in MCP error envelope."""

    def test_negative_context_wraps_runtime_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from drift import mcp_server

        def _boom(*_a: object, **_kw: object) -> None:
            raise RuntimeError("boom-negctx")

        monkeypatch.setattr("drift.api.negative_context", _boom)

        raw = asyncio.run(mcp_server.drift_negative_context(path="."))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-5001"
        assert result["tool"] == "drift_negative_context"
        assert "boom-negctx" in result["message"]

    def test_negative_context_timeout_still_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Timeout handling must remain unchanged."""
        import time

        from drift import mcp_server

        def _slow(*_a: object, **_kw: object) -> None:
            time.sleep(5)

        monkeypatch.setattr("drift.api.negative_context", _slow)
        monkeypatch.setattr(mcp_server, "_NEGATIVE_CONTEXT_TIMEOUT_SECONDS", 0.1)

        raw = asyncio.run(mcp_server.drift_negative_context(path="."))
        result = json.loads(raw)

        assert result["error_code"] == "DRIFT-2031"


class TestIssue140CheckPathOption:
    """#140: drift check must accept --path / --target-path."""

    def test_check_accepts_path_option(self) -> None:
        from click.testing import CliRunner

        from drift.commands.check import check

        runner = CliRunner()
        # Just verify the option is accepted (--help should list it)
        result = runner.invoke(check, ["--help"])
        assert result.exit_code == 0
        assert "--path" in result.output or "--target-path" in result.output

    def test_check_accepts_target_path_alias(self) -> None:
        from click.testing import CliRunner

        from drift.commands.check import check

        runner = CliRunner()
        result = runner.invoke(check, ["--help"])
        assert result.exit_code == 0
        assert "--target-path" in result.output

    def test_analyze_diff_accepts_target_path(self) -> None:
        """analyze_diff signature must include target_path parameter."""
        import inspect

        from drift.analyzer import analyze_diff

        sig = inspect.signature(analyze_diff)
        assert "target_path" in sig.parameters
