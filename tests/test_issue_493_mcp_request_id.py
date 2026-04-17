"""Regression tests for Issue #493 request_id correlation in MCP responses/logs."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid

import pytest


def _run_tool(result: object) -> object:
    """Await async MCP tool results in sync test context."""
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


class TestIssue493McpRequestCorrelation:
    def test_drift_scan_includes_request_id_on_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from drift import mcp_server

        monkeypatch.setattr("drift.api.scan", lambda *_a, **_kw: {"status": "ok"})

        result = json.loads(_run_tool(mcp_server.drift_scan(path=".")))

        request_id = result.get("request_id")
        assert isinstance(request_id, str)
        uuid.UUID(request_id)

    def test_drift_scan_error_includes_request_id_and_warning_log(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from drift import mcp_server

        def _broken_scan(*_a: object, **_kw: object) -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr("drift.api.scan", _broken_scan)

        with caplog.at_level(logging.WARNING, logger="drift"):
            result = json.loads(_run_tool(mcp_server.drift_scan(path=".")))

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-5001"
        assert result["tool"] == "drift_scan"
        request_id = result.get("request_id")
        assert isinstance(request_id, str)
        uuid.UUID(request_id)

        assert any(
            "DRIFT-5001 from drift_scan" in record.getMessage()
            and request_id in record.getMessage()
            for record in caplog.records
        )

    def test_drift_scan_logs_debug_call_with_request_id(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from drift import mcp_server

        monkeypatch.setattr("drift.api.scan", lambda *_a, **_kw: {"status": "ok"})

        with caplog.at_level(logging.DEBUG, logger="drift"):
            _run_tool(mcp_server.drift_scan(path="."))

        assert any("drift_scan called params=" in record.getMessage() for record in caplog.records)
