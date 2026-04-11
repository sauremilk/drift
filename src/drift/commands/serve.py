"""drift serve — start an A2A-compatible HTTP server."""

from __future__ import annotations

import click

from drift.commands import console


@click.command("serve")
@click.option(
    "--base-url",
    required=True,
    help="Public base URL for the agent card (e.g. http://localhost:8080).",
)
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host address.")
@click.option("--port", default=8080, show_default=True, type=int, help="Bind port.")
@click.option("--reload", "use_reload", is_flag=True, default=False, help="Enable auto-reload.")
def serve(base_url: str, host: str, port: int, use_reload: bool) -> None:
    """Start an A2A-compatible HTTP server for drift.

    Exposes a /.well-known/agent-card.json endpoint for agent discovery
    and a /a2a/v1 JSON-RPC 2.0 endpoint for skill invocation.

    Requires: pip install drift-analyzer[serve]
    """
    try:
        import uvicorn  # noqa: F401
        from fastapi import FastAPI  # noqa: F401
    except ImportError:
        console.print(
            "[bold red]Missing dependencies for drift serve.[/bold red]\n"
            "Install them with:\n\n"
            "  pip install drift-analyzer[serve]\n",
        )
        raise SystemExit(1)  # noqa: B904

    from drift.serve.app import create_app

    app = create_app(base_url)

    console.print(
        f"[bold green]drift A2A server starting[/bold green] at {host}:{port}\n"
        f"  Agent Card: {base_url.rstrip('/')}/.well-known/agent-card.json\n"
        f"  A2A endpoint: {base_url.rstrip('/')}/a2a/v1\n"
        f"  Docs: http://{host}:{port}/docs\n",
    )

    uvicorn.run(app, host=host, port=port, reload=use_reload)
