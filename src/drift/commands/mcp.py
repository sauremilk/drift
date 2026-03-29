"""drift mcp — start drift as an MCP server for VS Code / Copilot integration."""

from __future__ import annotations

import click

from drift.commands import console


@click.command("mcp")
@click.option(
    "--serve",
    is_flag=True,
    default=False,
    help="Start the MCP server on stdio transport.",
)
def mcp(serve: bool) -> None:
    """Start drift as an MCP server for VS Code / Copilot Chat.

    Requires the optional ``mcp`` extra::

        pip install drift-analyzer[mcp]

    Register in VS Code via ``.vscode/mcp.json``::

        {"servers": {"drift": {"type": "stdio", "command": "drift", "args": ["mcp", "--serve"]}}}
    """
    if not serve:
        console.print(
            "[yellow]Usage:[/] drift mcp --serve\n\n"
            "Starts drift as an MCP (Model Context Protocol) server on stdio.\n"
            "VS Code / Copilot Chat can then call drift analysis tools directly.\n\n"
            "[dim]Requires: pip install drift-analyzer[mcp][/]"
        )
        raise SystemExit(0)

    try:
        from drift.mcp_server import main as mcp_main
    except ImportError:
        console.print(
            "[red]Error:[/] MCP server requires the 'mcp' extra.\n"
            "Install with: [bold]pip install drift-analyzer\\[mcp][/]"
        )
        raise SystemExit(1)  # noqa: B904

    try:
        mcp_main()
    except RuntimeError as exc:
        if "requires optional dependency 'mcp'" not in str(exc):
            raise
        console.print(
            "[red]Error:[/] MCP server requires the 'mcp' extra.\n"
            "Install with: [bold]pip install drift-analyzer\\[mcp][/]"
        )
        raise SystemExit(1)  # noqa: B904
