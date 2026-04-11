"""drift session-report — render session metrics from persisted session files."""

from __future__ import annotations

import json
from pathlib import Path

import click

from drift.commands import console


@click.command("session-report", short_help="Render session effectiveness metrics.")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option(
    "--file",
    "-f",
    "session_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to a specific .drift-session-*.json file.",
)
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON.")
@click.option(
    "--latest",
    is_flag=True,
    default=False,
    help="Auto-select the most recent session file.",
)
def session_report(
    repo: Path,
    session_file: Path | None,
    output_json: bool,
    latest: bool,
) -> None:
    """Display effectiveness metrics from a saved drift session.

    Session files are created when ``drift_session_update(save_to_disk=True)``
    is called via MCP, or when sessions are explicitly saved.

    Without --file, scans the repo directory for .drift-session-*.json files.
    """
    if session_file is None:
        session_files = sorted(
            repo.glob(".drift-session-*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not session_files:
            console.print(
                "[yellow]No session files found.[/yellow]\n"
                "Session files are created via MCP with save_to_disk=True.\n"
                "Try: drift session-report --file <path>"
            )
            raise SystemExit(1)

        if latest or len(session_files) == 1:
            session_file = session_files[0]
        else:
            console.print("[bold]Available session files:[/bold]")
            for i, sf in enumerate(session_files[:10], 1):
                console.print(f"  {i}. {sf.name}")
            console.print()
            console.print(
                "Use [bold]--file <path>[/bold] to select a specific session, "
                "or [bold]--latest[/bold] for the most recent."
            )
            raise SystemExit(0)

    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        console.print(f"[red]Failed to read session file: {exc}[/red]")
        raise SystemExit(1) from exc

    if not isinstance(data, dict) or "session_id" not in data:
        console.print("[red]Invalid session file format.[/red]")
        raise SystemExit(1)

    if output_json:
        console.print_json(json.dumps(data, indent=2, default=str))
        return

    from drift.output.session_renderer import render_session_report

    render_session_report(data, console)
