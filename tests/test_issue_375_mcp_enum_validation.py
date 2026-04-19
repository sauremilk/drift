"""Regression tests for Issue #375:
Missing input validation before dispatch in drift_scan, drift_diff,
drift_verify, and drift_fix_plan (mcp_server.py).

Each affected tool must return a structured DRIFT-1003 error response
when invalid enum values are supplied, rather than propagating errors
from deep internal call frames.
"""

from __future__ import annotations

import asyncio
import inspect
import json

import pytest


def _run_tool(coro: object) -> str:
    """Await async MCP tool coroutines in a sync test context."""
    if inspect.isawaitable(coro):
        return asyncio.run(coro)  # type: ignore[arg-type]
    return coro  # type: ignore[return-value]


class TestDriftScanEnumValidation:
    """drift_scan rejects invalid enum values before dispatch."""

    def test_invalid_response_detail_returns_1003(self) -> None:
        from drift import mcp_server

        raw = _run_tool(mcp_server.drift_scan(response_detail="verbose"))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["tool"] == "drift_scan"
        assert result["invalid_fields"][0]["field"] == "response_detail"
        assert "valid_values" in result["suggested_fix"]
        assert result.get("pass") is None

    def test_invalid_response_profile_returns_1003(self) -> None:
        from drift import mcp_server

        raw = _run_tool(mcp_server.drift_scan(response_profile="reviewer"))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["tool"] == "drift_scan"
        assert result["invalid_fields"][0]["field"] == "response_profile"
        assert result.get("pass") is None

    def test_valid_response_detail_does_not_return_1003(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Valid 'concise' must not be rejected by enum validation."""
        from drift import mcp_server

        # Patch API to avoid real analysis
        monkeypatch.setattr(
            "drift.api.scan",
            lambda *a, **kw: {"status": "ok", "findings": []},
        )
        raw = _run_tool(mcp_server.drift_scan(response_detail="concise"))
        result = json.loads(raw)

        assert result.get("error_code") != "DRIFT-1003"
        assert result.get("pass") is None

    def test_valid_response_detail_detailed_passes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from drift import mcp_server

        monkeypatch.setattr(
            "drift.api.scan",
            lambda *a, **kw: {"status": "ok", "findings": []},
        )
        raw = _run_tool(mcp_server.drift_scan(response_detail="detailed"))
        result = json.loads(raw)

        assert result.get("error_code") != "DRIFT-1003"
        assert result.get("pass") is None


class TestDriftDiffEnumValidation:
    """drift_diff rejects invalid enum values before dispatch."""

    def test_invalid_response_detail_returns_1003(self) -> None:
        from drift import mcp_server

        raw = _run_tool(mcp_server.drift_diff(response_detail="full"))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["tool"] == "drift_diff"
        assert result["invalid_fields"][0]["field"] == "response_detail"
        assert result.get("pass") is None

    def test_invalid_response_profile_returns_1003(self) -> None:
        from drift import mcp_server

        raw = _run_tool(mcp_server.drift_diff(response_profile="architect"))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["tool"] == "drift_diff"
        assert result["invalid_fields"][0]["field"] == "response_profile"
        assert result.get("pass") is None


class TestDriftVerifyEnumValidation:
    """drift_verify rejects invalid enum values before dispatch."""

    def test_invalid_fail_on_returns_1003(self) -> None:
        from drift import mcp_server

        raw = _run_tool(mcp_server.drift_verify(fail_on="severe"))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["tool"] == "drift_verify"
        assert result["invalid_fields"][0]["field"] == "fail_on"
        assert "valid_values" in result["suggested_fix"]
        assert result.get("pass") is None

    def test_invalid_response_profile_returns_1003(self) -> None:
        from drift import mcp_server

        raw = _run_tool(mcp_server.drift_verify(response_profile="reviewer"))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["tool"] == "drift_verify"
        assert result["invalid_fields"][0]["field"] == "response_profile"
        assert result.get("pass") is None

    def test_valid_fail_on_values_do_not_trigger_1003(self) -> None:
        """All documented fail_on enum values must pass _validate_enum_param."""
        from drift.mcp_server import _FAIL_ON_VALUES, _validate_enum_param

        for value in _FAIL_ON_VALUES:
            err = _validate_enum_param("fail_on", value, _FAIL_ON_VALUES, "drift_verify")
            assert err is None, f"Valid fail_on='{value}' was rejected"


class TestDriftFixPlanEnumValidation:
    """drift_fix_plan rejects invalid enum values before dispatch."""

    def test_invalid_automation_fit_min_returns_1003(self) -> None:
        from drift import mcp_server

        raw = _run_tool(mcp_server.drift_fix_plan(automation_fit_min="urgent"))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["tool"] == "drift_fix_plan"
        assert result["invalid_fields"][0]["field"] == "automation_fit_min"
        assert result.get("pass") is None

    def test_invalid_response_profile_returns_1003(self) -> None:
        from drift import mcp_server

        raw = _run_tool(mcp_server.drift_fix_plan(response_profile="ux_designer"))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-1003"
        assert result["tool"] == "drift_fix_plan"
        assert result["invalid_fields"][0]["field"] == "response_profile"
        assert result.get("pass") is None

    def test_none_automation_fit_min_is_allowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """automation_fit_min is optional; None must not trigger validation error."""
        from drift import mcp_server

        monkeypatch.setattr(
            "drift.api.fix_plan",
            lambda *a, **kw: {"type": "ok", "tasks": []},
        )
        raw = _run_tool(mcp_server.drift_fix_plan(automation_fit_min=None))
        result = json.loads(raw)

        assert result.get("error_code") != "DRIFT-1003"
        assert result.get("pass") is None


class TestValidateEnumParamHelper:
    """Unit tests for the _validate_enum_param helper itself."""

    def test_returns_none_for_valid_value(self) -> None:
        from drift.mcp_server import _validate_enum_param

        assert _validate_enum_param("x", "high", frozenset({"low", "medium", "high"}), "t") is None

    def test_returns_none_for_none_when_not_required(self) -> None:
        from drift.mcp_server import _validate_enum_param

        assert _validate_enum_param("x", None, frozenset({"a", "b"}), "t") is None

    def test_returns_error_for_invalid_value(self) -> None:
        from drift.mcp_server import _validate_enum_param

        err = _validate_enum_param("x", "bad", frozenset({"a", "b"}), "mytool")
        assert err is not None
        assert err["error_code"] == "DRIFT-1003"
        assert err["invalid_fields"][0]["field"] == "x"
        assert err["invalid_fields"][0]["value"] == "bad"
        assert err.get("pass") is None

    def test_returns_error_for_none_when_required(self) -> None:
        from drift.mcp_server import _validate_enum_param

        err = _validate_enum_param("x", None, frozenset({"a", "b"}), "mytool", required=True)
        assert err is not None
        assert err["error_code"] == "DRIFT-1003"
        assert err["invalid_fields"][0]["field"] == "x"
        assert err.get("pass") is None

    def test_case_insensitive_normalisation(self) -> None:
        """Values like 'High' or 'CONCISE' must be accepted."""
        from drift.mcp_server import _validate_enum_param

        assert _validate_enum_param("x", "HIGH", frozenset({"low", "medium", "high"}), "t") is None
        assert _validate_enum_param("x", "Concise", frozenset({"concise", "detailed"}), "t") is None
