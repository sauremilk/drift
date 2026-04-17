"""Regression tests for Issue #496 in MCP tool catalog generation."""

from __future__ import annotations

import builtins
from typing import Any

import pytest


def _tool_alpha(path: str) -> str:
    """Alpha tool summary.

    Args:
        path: Path parameter.
    """
    return path


def _tool_beta(max_findings: int = 10) -> int:
    """Beta tool summary.

    Args:
        max_findings: Cap value.
    """
    return max_findings


class TestIssue496McpCatalog:
    def test_get_tool_catalog_import_error_returns_empty_with_error_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from drift import mcp_catalog

        mcp_catalog.get_tool_catalog.cache_clear()

        real_import = builtins.__import__

        def _raising_import(
            name: str,
            globals_: dict[str, Any] | None = None,
            locals_: dict[str, Any] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> Any:
            if name == "drift.mcp_server":
                msg = "mcp optional dependency missing"
                raise ImportError(msg)
            return real_import(name, globals_, locals_, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", _raising_import)

        catalog = mcp_catalog.get_tool_catalog()

        assert catalog == []
        error = mcp_catalog.get_tool_catalog_error()
        assert isinstance(error, str)
        assert "mcp optional dependency missing" in error

    def test_get_tool_catalog_cache_clear_rebuilds_after_export_changes(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from drift import mcp_catalog, mcp_server

        original_tools = mcp_server._EXPORTED_MCP_TOOLS
        monkeypatch.setattr(
            mcp_server,
            "_EXPORTED_MCP_TOOLS",
            (_tool_alpha,),
        )
        mcp_catalog.get_tool_catalog.cache_clear()

        first = mcp_catalog.get_tool_catalog()
        first_names = [entry["name"] for entry in first]
        assert first_names == ["_tool_alpha"]

        monkeypatch.setattr(
            mcp_server,
            "_EXPORTED_MCP_TOOLS",
            (_tool_beta,),
        )

        stale = mcp_catalog.get_tool_catalog()
        stale_names = [entry["name"] for entry in stale]
        assert stale_names == ["_tool_alpha"]

        mcp_catalog.get_tool_catalog.cache_clear()
        refreshed = mcp_catalog.get_tool_catalog()
        refreshed_names = [entry["name"] for entry in refreshed]
        assert refreshed_names == ["_tool_beta"]

        # Keep test isolation explicit even though monkeypatch restores attributes.
        monkeypatch.setattr(mcp_server, "_EXPORTED_MCP_TOOLS", original_tools)
