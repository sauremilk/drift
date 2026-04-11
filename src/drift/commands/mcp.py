"""drift mcp — start drift as an MCP server for VS Code / Copilot integration."""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Callable
from typing import Any, NoReturn

import click

from drift import __version__
from drift.commands import console
from drift.errors import DriftSystemError


def _load_mcp_entrypoints() -> tuple[Callable[[], list[dict[str, Any]]], Callable[[], None]]:
    """Import MCP server entrypoints lazily for CLI startup."""
    module = importlib.import_module("drift.mcp_server")
    return module.get_tool_catalog, module.main


def _is_missing_mcp_dependency(exc: Exception) -> bool:
    """Return True only when the missing dependency is the optional mcp extra."""
    if isinstance(exc, ImportError):
        missing_module = getattr(exc, "name", None)
        if missing_module == "mcp" or (
            isinstance(missing_module, str) and missing_module.startswith("mcp.")
        ):
            return True

        message = str(exc)
        return "No module named 'mcp" in message or 'No module named "mcp' in message

    if isinstance(exc, RuntimeError):
        return "requires optional dependency 'mcp'" in str(exc)

    return False


def _raise_missing_mcp_extra(exc: Exception) -> NoReturn:
    raise DriftSystemError(
        "DRIFT-2010",
        message="MCP server requires the 'mcp' extra.",
        package="mcp",
        extra="mcp",
    ) from exc


def _emit_tty_startup_handshake(*, tools_count: int) -> None:
    """Emit a one-time startup event for manual TTY debug sessions."""
    payload = {
        "event": "drift.mcp.startup",
        "type": "server_started",
        "version": __version__,
        "tools_count": tools_count,
        "ready": True,
    }
    serialized = json.dumps(payload)
    # Emit on both streams for debug workflows that monitor only one channel.
    click.echo(serialized)
    click.echo(serialized, err=True)


@click.command("mcp")
@click.option(
    "--serve",
    is_flag=True,
    default=False,
    help="Start the MCP server on stdio transport.",
)
@click.option(
    "--list",
    "list_tools",
    is_flag=True,
    default=False,
    help="List available MCP tools without starting the server.",
)
@click.option(
    "--schema",
    "show_schema",
    is_flag=True,
    default=False,
    help="Print MCP tool parameter schema as JSON and exit.",
)
@click.option(
    "--allow-tty",
    is_flag=True,
    default=False,
    help="Allow --serve on interactive terminals (debug only).",
)
def mcp(serve: bool, list_tools: bool, show_schema: bool, allow_tty: bool) -> None:
    """Run drift in MCP command modes for VS Code / Copilot Chat integration.

    Requires the optional ``mcp`` extra::

        pip install drift-analyzer[mcp]

    Register in VS Code via ``.vscode/mcp.json``::

        {"servers": {"drift": {"type": "stdio", "command": "drift", "args": ["mcp", "--serve"]}}}
    """
    selected_modes = int(serve) + int(list_tools) + int(show_schema)
    if selected_modes > 1:
        raise click.UsageError("Use only one mode: --serve, --list, or --schema.")

    if list_tools or show_schema:
        from drift.mcp_server import get_tool_catalog as get_catalog

        catalog = get_catalog()

        if show_schema:
            console.print(json.dumps({"tools": catalog}, indent=2))
            raise SystemExit(0)

        console.print("[yellow]Available MCP tools:[/]")
        for tool in catalog:
            params = ", ".join(param["name"] for param in tool["parameters"])
            console.print(f"- {tool['name']}: {tool['description']}")
            console.print(f"  params: {params if params else '(none)'}")
        raise SystemExit(0)

    if not serve:
        console.print("Usage:", style="yellow")
        console.print(
            "  drift mcp --serve\n"
            "  drift mcp --serve --allow-tty\n"
            "  drift mcp --list\n"
            "  drift mcp --schema\n\n"
            "Starts drift as an MCP (Model Context Protocol) server on stdio.\n"
            "VS Code / Copilot Chat can then call drift analysis tools directly.\n\n"
            "Inspect tools without MCP extra via --list / --schema.\n"
            "Requires for --serve: pip install drift-analyzer[mcp].\n"
            "Interactive TTY launch is blocked by default to prevent accidental hanging.\n"
            "Use --allow-tty only for manual debugging.",
            style="dim",
            markup=False,
        )
        raise SystemExit(0)

    if sys.stdin.isatty() and not allow_tty:
        raise click.UsageError(
            "Refusing to start MCP stdio server on interactive TTY. "
            "Use VS Code MCP integration, or pass --allow-tty for manual debugging.",
        )

    try:
        get_tool_catalog, mcp_main = _load_mcp_entrypoints()
    except ImportError as exc:
        if _is_missing_mcp_dependency(exc):
            _raise_missing_mcp_extra(exc)
        raise

    if allow_tty:
        _emit_tty_startup_handshake(tools_count=len(get_tool_catalog()))

    try:
        mcp_main()
    except RuntimeError as exc:
        if not _is_missing_mcp_dependency(exc):
            raise
        _raise_missing_mcp_extra(exc)
