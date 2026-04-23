"""drift synthesize — cluster recurring findings and generate skill drafts.

Analyses scan history to detect recurring finding patterns, generates
guard and repair skill drafts, and triages them against existing skills.

Usage::

    drift synthesize                      # rich preview
    drift synthesize --format json        # JSON for agent consumption
    drift synthesize --kinds guard        # guard skills only
    drift synthesize --kinds repair       # repair skills only
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table

from drift.api.synthesize import synthesize as _api_synthesize
from drift.commands import console
from drift.commands._io import _emit_machine_output


@click.command(
    "synthesize",
    short_help="Synthesize skill drafts from recurring findings.",
    hidden=True,
)
@click.option(
    "--repo",
    "path",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Path to the repository root.",
)
@click.option(
    "--kinds",
    "-k",
    type=click.Choice(["guard", "repair", "all"]),
    default="all",
    show_default=True,
    help="Which skill types to generate.",
)
@click.option(
    "--min-recurrence",
    type=int,
    default=3,
    show_default=True,
    help="Minimum finding recurrences across scans.",
)
@click.option(
    "--min-recurrence-rate",
    type=float,
    default=0.5,
    show_default=True,
    help="Minimum fraction of scans a cluster must appear in.",
)
@click.option(
    "--max-skills",
    type=int,
    default=25,
    show_default=True,
    help="Maximum total skills (sprawl guard).",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write JSON output to this file instead of stdout.",
)
def synthesize(
    path: Path,
    kinds: str,
    min_recurrence: int,
    min_recurrence_rate: float,
    max_skills: int,
    output_format: str,
    output_file: Path | None,
) -> None:
    """Synthesize skill drafts from recurring drift findings.

    Reads scan history from ``.drift-cache/history/`` and generates
    guard/repair skill proposals.  Use ``drift scan`` first to build
    scan history.

    Examples::

        # Preview skill proposals
        drift synthesize

        # JSON output for agent consumption
        drift synthesize --format json

        # Only repair skills
        drift synthesize --kinds repair
    """
    result = _api_synthesize(
        repo=str(path),
        kinds=kinds,
        min_recurrence=min_recurrence,
        min_recurrence_rate=min_recurrence_rate,
        max_skills=max_skills,
    )

    # ---- JSON format -------------------------------------------------------
    if output_format == "json":
        payload = json.dumps(result, indent=2, ensure_ascii=False)
        _emit_machine_output(payload, output_file)
        if result.get("status") not in ("ok", "no_clusters", "insufficient_data"):
            sys.exit(1)
        return

    # ---- Insufficient data -------------------------------------------------
    status = result.get("status", "")
    if status in ("insufficient_data", "no_clusters"):
        console.print(
            f"[yellow]{result.get('message', 'Keine Daten.')}[/yellow]",
        )
        return

    # ---- Rich output -------------------------------------------------------
    _render_clusters(result.get("clusters", []))
    _render_decisions(result.get("decisions", []))

    summary = result.get("decisions_summary", {})
    console.print(
        Panel(
            f"[bold green]{summary.get('new', 0)}[/bold green] neue Skills  |  "
            f"[bold yellow]{summary.get('merge', 0)}[/bold yellow] Merge-Vorschlaege  |  "
            f"[bold red]{summary.get('discard', 0)}[/bold red] verworfen",
            title="Skill Synthesizer — Zusammenfassung",
        ),
    )


def _render_clusters(clusters: list[dict]) -> None:
    """Render a summary table of finding clusters."""
    if not clusters:
        return
    table = Table(
        title=f"Finding-Cluster ({len(clusters)})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Signal", style="bold")
    table.add_column("Modul")
    table.add_column("Dateien", justify="right")
    table.add_column("Vorkommen", justify="right")
    table.add_column("Rate", justify="right")
    table.add_column("Trend")

    for c in clusters[:20]:  # cap at 20 rows
        trend_style = {
            "degrading": "[bold red]",
            "stable": "",
            "improving": "[green]",
        }.get(c.get("trend", ""), "")
        table.add_row(
            c.get("signal_type", "?"),
            c.get("module_path", "?"),
            str(len(c.get("affected_files", []))),
            str(c.get("occurrence_count", 0)),
            f"{c.get('recurrence_rate', 0):.0%}",
            f"{trend_style}{c.get('trend', '?')}",
        )
    console.print(table)


def _render_decisions(decisions: list[dict]) -> None:
    """Render a table of triage decisions."""
    if not decisions:
        return
    table = Table(
        title=f"Triage-Entscheidungen ({len(decisions)})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Skill", style="bold")
    table.add_column("Art")
    table.add_column("Aktion")
    table.add_column("Merge-Ziel")
    table.add_column("Grund")

    action_style = {
        "new": "[bold green]new[/bold green]",
        "merge": "[bold yellow]merge[/bold yellow]",
        "discard": "[bold red]discard[/bold red]",
    }

    for d in decisions[:30]:
        draft = d.get("draft", {})
        table.add_row(
            draft.get("name", "?"),
            draft.get("kind", "?"),
            action_style.get(d.get("action", ""), d.get("action", "?")),
            d.get("merge_target") or "—",
            d.get("reason", "")[:60],
        )
    console.print(table)
