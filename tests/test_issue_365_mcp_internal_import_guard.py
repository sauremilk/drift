"""Regression tests for Issue #365:
MCP catalog advertises tools that fail at runtime with missing internal modules.

When a drift.* internal module cannot be imported during tool invocation,
the MCP surface must return a user-friendly DRIFT-5001 error with an
actionable recovery message instead of a raw Python ImportError string.

Additionally, the MCP --serve startup must validate core internal imports
and raise DRIFT-2011 before starting the transport loop.
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


# ---------------------------------------------------------------------------
# mcp_utils helpers
# ---------------------------------------------------------------------------


class TestIsbrokenInternalDriftModule:
    """_is_broken_internal_drift_module correctly classifies ImportErrors."""

    def test_returns_true_for_drift_submodule(self) -> None:
        from drift.mcp_utils import _is_broken_internal_drift_module

        exc = ImportError("No module named 'drift.output'")
        exc.name = "drift.output"  # type: ignore[attr-defined]
        assert _is_broken_internal_drift_module(exc) is True

    def test_returns_true_for_drift_incremental(self) -> None:
        from drift.mcp_utils import _is_broken_internal_drift_module

        exc = ImportError("No module named 'drift.incremental'")
        exc.name = "drift.incremental"  # type: ignore[attr-defined]
        assert _is_broken_internal_drift_module(exc) is True

    def test_returns_true_for_bare_drift(self) -> None:
        from drift.mcp_utils import _is_broken_internal_drift_module

        exc = ImportError("No module named 'drift'")
        exc.name = "drift"  # type: ignore[attr-defined]
        assert _is_broken_internal_drift_module(exc) is True

    def test_returns_false_for_mcp_module(self) -> None:
        from drift.mcp_utils import _is_broken_internal_drift_module

        exc = ImportError("No module named 'mcp'")
        exc.name = "mcp"  # type: ignore[attr-defined]
        assert _is_broken_internal_drift_module(exc) is False

    def test_returns_false_for_unrelated_module(self) -> None:
        from drift.mcp_utils import _is_broken_internal_drift_module

        exc = ImportError("No module named 'rich'")
        exc.name = "rich"  # type: ignore[attr-defined]
        assert _is_broken_internal_drift_module(exc) is False

    def test_returns_false_for_non_import_error(self) -> None:
        from drift.mcp_utils import _is_broken_internal_drift_module

        assert _is_broken_internal_drift_module(ValueError("drift.output")) is False


class TestBrokenInternalModuleError:
    """_broken_internal_module_error returns a well-formed DRIFT-5001 payload."""

    def test_contains_required_fields(self) -> None:
        from drift.mcp_utils import _broken_internal_module_error

        exc = ImportError("No module named 'drift.output'")
        exc.name = "drift.output"  # type: ignore[attr-defined]
        result = _broken_internal_module_error("drift_scan", exc)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-5001"
        assert result["tool"] == "drift_scan"
        assert result["recoverable"] is False
        assert "drift.output" in result["message"]
        assert "pip install" in result["message"]

    def test_agent_instruction_is_actionable(self) -> None:
        from drift.mcp_utils import _broken_internal_module_error

        exc = ImportError("No module named 'drift.incremental'")
        exc.name = "drift.incremental"  # type: ignore[attr-defined]
        result = _broken_internal_module_error("drift_nudge", exc)

        assert "agent_instruction" in result
        assert "drift_nudge" in result["agent_instruction"]
        assert "drift.incremental" in result["agent_instruction"]

    def test_broken_module_field_present(self) -> None:
        from drift.mcp_utils import _broken_internal_module_error

        exc = ImportError("No module named 'drift.output'")
        exc.name = "drift.output"  # type: ignore[attr-defined]
        result = _broken_internal_module_error("drift_scan", exc)

        assert result["broken_module"] == "drift.output"


# ---------------------------------------------------------------------------
# _run_api_tool wraps internal ImportError as friendly DRIFT-5001
# ---------------------------------------------------------------------------


class TestRunApiToolInternalImportGuard:
    """_run_api_tool catches internal drift ImportErrors and returns friendly error."""

    def test_internal_import_error_returns_friendly_5001(self) -> None:
        import asyncio

        from drift.mcp_utils import _run_api_tool

        def _broken_api(**_kwargs: object) -> object:
            exc = ImportError("No module named 'drift.output'")
            exc.name = "drift.output"  # type: ignore[attr-defined]
            raise exc

        raw = asyncio.run(_run_api_tool("drift_scan", _broken_api))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-5001"
        assert result["tool"] == "drift_scan"
        assert result["recoverable"] is False
        assert "pip install" in result["message"]
        assert "drift.output" in result["message"]
        assert "agent_instruction" in result

    def test_generic_exception_still_returns_recoverable_5001(self) -> None:
        import asyncio

        from drift.mcp_utils import _run_api_tool

        def _broken_api(**_kwargs: object) -> object:
            msg = "unexpected analysis failure"
            raise RuntimeError(msg)

        raw = asyncio.run(_run_api_tool("drift_scan", _broken_api))
        result = json.loads(raw)

        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-5001"
        assert result["recoverable"] is True


# ---------------------------------------------------------------------------
# commands/mcp.py startup validation
# ---------------------------------------------------------------------------


class TestCheckMcpCoreImports:
    """_check_mcp_core_imports detects broken internal modules at startup."""

    def test_returns_empty_when_all_modules_ok(self) -> None:
        from drift.commands.mcp import _check_mcp_core_imports

        broken = _check_mcp_core_imports()
        assert broken == [], f"Unexpected broken modules: {broken}"

    def test_detects_unimportable_module(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If a core module fails to import, it appears in the returned list."""
        import sys

        from drift.commands.mcp import _check_mcp_core_imports

        # Remove drift.output from sys.modules so importlib actually tries to import it,
        # then make the import fail via a patched sys.modules sentinel.
        saved = sys.modules.pop("drift.output", None)
        try:
            # Inserting None signals to importlib that the import should fail.
            monkeypatch.setitem(sys.modules, "drift.output", None)  # type: ignore[arg-type]
            broken = _check_mcp_core_imports()
        finally:
            if saved is not None:
                sys.modules["drift.output"] = saved
            elif "drift.output" in sys.modules:
                del sys.modules["drift.output"]

        assert "drift.output" in broken

    def test_returns_empty_list_when_modules_importable(self) -> None:
        from drift.commands.mcp import _check_mcp_core_imports

        # Calling twice should be safe (modules cached in sys.modules)
        assert _check_mcp_core_imports() == []


# ---------------------------------------------------------------------------
# DRIFT-2011 error code is registered
# ---------------------------------------------------------------------------


class TestDrift2011ErrorCode:
    """DRIFT-2011 is registered in the error registry."""

    def test_drift_2011_registered(self) -> None:
        from drift.errors._codes import ERROR_REGISTRY

        assert "DRIFT-2011" in ERROR_REGISTRY
        info = ERROR_REGISTRY["DRIFT-2011"]
        assert info.code == "DRIFT-2011"
        assert info.category == "system"
        assert "pip install" in info.action
