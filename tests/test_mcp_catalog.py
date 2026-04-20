"""Tests that all expected MCP tools are registered in the FastMCP runtime registry.

Guards against silent schema-generation failures that cause individual tools to
disappear from the MCP tool catalog without raising an error at startup (Issue: transient
drift_nudge absence).
"""

from __future__ import annotations

import asyncio

import pytest

from drift.mcp_server import (
    _EXPORTED_MCP_TOOLS,
    _MCP_AVAILABLE,
    _assert_mcp_tools_registered,
    mcp,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXPECTED_TOOL_NAMES = [f.__name__ for f in _EXPORTED_MCP_TOOLS]


def _registered_tool_names() -> set[str]:
    """Return the set of tool names registered in the FastMCP runtime registry."""
    tools = asyncio.run(mcp.list_tools())
    return {t.name for t in tools}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not _MCP_AVAILABLE, reason="mcp extra not installed"
)


class TestMcpCatalogCompleteness:
    """Verify the FastMCP registry exactly matches _EXPORTED_MCP_TOOLS."""

    def test_registered_count_equals_exported_count(self) -> None:
        """Number of FastMCP-registered tools must equal len(_EXPORTED_MCP_TOOLS)."""
        registered = _registered_tool_names()
        assert len(registered) == len(_EXPORTED_MCP_TOOLS), (
            f"Expected {len(_EXPORTED_MCP_TOOLS)} registered tools, "
            f"got {len(registered)}. "
            f"Missing: {set(_EXPECTED_TOOL_NAMES) - registered}. "
            f"Extra: {registered - set(_EXPECTED_TOOL_NAMES)}."
        )

    def test_no_missing_tools(self) -> None:
        """Every tool declared in _EXPORTED_MCP_TOOLS must appear in FastMCP registry."""
        registered = _registered_tool_names()
        missing = set(_EXPECTED_TOOL_NAMES) - registered
        assert not missing, (
            f"Tools declared in _EXPORTED_MCP_TOOLS but missing from FastMCP registry: "
            f"{sorted(missing)}. "
            "This indicates a silent FastMCP schema-generation failure."
        )

    def test_no_extra_tools(self) -> None:
        """FastMCP registry must not contain tools absent from _EXPORTED_MCP_TOOLS."""
        registered = _registered_tool_names()
        extra = registered - set(_EXPECTED_TOOL_NAMES)
        assert not extra, (
            f"Tools in FastMCP registry not declared in _EXPORTED_MCP_TOOLS: "
            f"{sorted(extra)}. Add them to _EXPORTED_MCP_TOOLS."
        )

    @pytest.mark.parametrize("tool_name", _EXPECTED_TOOL_NAMES)
    def test_each_tool_registered(self, tool_name: str) -> None:
        """Each individual tool declared in _EXPORTED_MCP_TOOLS is in the registry."""
        registered = _registered_tool_names()
        assert tool_name in registered, (
            f"Tool '{tool_name}' is declared in _EXPORTED_MCP_TOOLS but not registered "
            f"in the FastMCP runtime registry. FastMCP may have silently dropped it "
            f"during schema generation."
        )


class TestAssertMcpToolsRegistered:
    """Verify _assert_mcp_tools_registered() behaves correctly."""

    def test_does_not_raise_when_all_tools_present(self) -> None:
        """_assert_mcp_tools_registered() must not raise when registry is complete."""
        # Should complete without raising
        _assert_mcp_tools_registered()

    def test_raises_runtime_error_on_missing_tool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_assert_mcp_tools_registered() raises RuntimeError if a tool is absent."""
        import drift.mcp_server as server_module

        original_exported = server_module._EXPORTED_MCP_TOOLS

        # Inject a fake tool name into _EXPORTED_MCP_TOOLS so it appears expected
        # but is absent from FastMCP registry
        def _fake_tool() -> None:
            pass

        _fake_tool.__name__ = "_drift_nonexistent_test_tool_xyz"

        monkeypatch.setattr(
            server_module,
            "_EXPORTED_MCP_TOOLS",
            (*original_exported, _fake_tool),
        )

        with pytest.raises(RuntimeError, match="_drift_nonexistent_test_tool_xyz"):
            server_module._assert_mcp_tools_registered()

    def test_raises_runtime_error_when_list_tools_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_assert_mcp_tools_registered() raises RuntimeError if mcp.list_tools() throws.

        Guards the silent-swallow regression: the old code caught Exception and
        returned without raising, allowing the server to start with an incomplete
        catalog (root cause of transient drift_nudge absence).
        """
        import drift.mcp_server as server_module

        def _boom() -> None:
            raise OSError("simulated FastMCP schema generation failure")

        monkeypatch.setattr(server_module.mcp, "list_tools", _boom)

        with pytest.raises(RuntimeError, match="MCP tool registry introspection failed"):
            server_module._assert_mcp_tools_registered()


class TestNewToolsV223(TestMcpCatalogCompleteness):
    """Regression guard: 8 new tools added in v2.23.0 must remain in the catalog."""

    _NEW_TOOLS = [
        "drift_capture_intent",
        "drift_verify_intent",
        "drift_feedback_for_agent",
        "drift_fix_apply",
        "drift_steer",
        "drift_compile_policy",
        "drift_suggest_rules",
        "drift_generate_skills",
    ]

    @pytest.mark.parametrize("tool_name", _NEW_TOOLS)
    def test_new_tool_registered(self, tool_name: str) -> None:
        """Each v2.23.0 tool must be registered in the FastMCP runtime catalog."""
        registered = _registered_tool_names()
        assert tool_name in registered, (
            f"v2.23.0 tool '{tool_name}' missing from FastMCP registry."
        )

    @pytest.mark.parametrize("tool_name", _NEW_TOOLS)
    def test_new_tool_in_exported_list(self, tool_name: str) -> None:
        """Each v2.23.0 tool must appear in _EXPORTED_MCP_TOOLS."""
        assert tool_name in _EXPECTED_TOOL_NAMES, (
            f"v2.23.0 tool '{tool_name}' not declared in _EXPORTED_MCP_TOOLS."
        )
