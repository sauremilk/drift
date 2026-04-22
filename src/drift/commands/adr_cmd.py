"""drift adr — list active Architecture Decision Records in a repository."""

from __future__ import annotations

import json
from pathlib import Path

import click

from drift.commands import console


@click.command("adr")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    show_default=True,
    help="Repository root to scan for decisions/*.md.",
)
@click.option(
    "--task",
    "-t",
    default="",
    help="Natural-language task description for relevance filtering.",
)
@click.option(
    "--scope",
    "-s",
    "scope_paths",
    multiple=True,
    help="File or directory paths in scope; can be repeated.",
)
@click.option(
    "--max",
    "max_results",
    default=20,
    show_default=True,
    help="Maximum number of ADRs to show.",
)
@click.option(
    "--output-format",
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
    show_default=True,
    help="Output format.",
)
def adr(
    repo: Path,
    task: str,
    scope_paths: tuple[str, ...],
    max_results: int,
    output_format: str,
) -> None:
    """List active Architecture Decision Records (ADRs) in a repository.

    Scans ``decisions/*.md`` for ADRs with status ``accepted`` or ``proposed``.
    When ``--task`` or ``--scope`` are given, only ADRs relevant to that
    context are shown.

    Examples::

        drift adr --repo .
        drift adr --task "refactor ingestion layer" --scope src/drift/ingestion
        drift adr --format json | jq '.[].title'
    """
    from drift.adr_scanner import scan_active_adrs

    results = scan_active_adrs(
        repo,
        scope_paths=list(scope_paths),
        task=task,
        max_results=max_results,
    )

    if output_format == "json":
        click.echo(json.dumps(results, indent=2))
        return

    if not results:
        decisions_dir = Path(repo) / "decisions"
        if not decisions_dir.is_dir():
            console.print("[yellow]No decisions/ directory found in repository.[/yellow]")
            console.print(
                "[dim]Create decisions/ADR-001-example.md with frontmatter "
                "(id: ADR-001, status: accepted) to get started.[/dim]"
            )
        else:
            filter_hint = ""
            if task or scope_paths:
                filter_hint = " matching the given task/scope"
            console.print(f"[dim]No active ADRs found{filter_hint}.[/dim]")
        return

    from rich.table import Table

    table = Table(title=f"Active ADRs ({len(results)} found)", show_lines=False)
    table.add_column("ID", style="bold cyan", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Title")
    table.add_column("Match", style="dim")

    status_style = {"accepted": "[green]accepted[/green]", "proposed": "[yellow]proposed[/yellow]"}

    for entry in results:
        adr_id = entry.get("id") or "—"
        title = entry.get("title") or "—"
        status = entry.get("status", "")
        reason = entry.get("scope_match_reason", "")

        match_label = ""
        if reason == "no_filter":
            match_label = ""
        elif reason.startswith("path_token:"):
            match_label = f"path: {reason.split(':', 1)[1]}"
        elif reason.startswith("task_keyword:"):
            match_label = f"keyword: {reason.split(':', 1)[1]}"

        table.add_row(adr_id, status_style.get(status, status), title, match_label)

    console.print(table)
    console.print(
        "[dim]Tip: use --task / --scope to narrow results; "
        "--format json for machine-readable output.[/dim]"
    )
