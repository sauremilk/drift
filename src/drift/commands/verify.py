"""drift verify — post-edit coherence verification with binary pass/fail.

Provides a single verdict for CI pipelines and agent workflows:
does this edit degrade structural coherence?

Decision: ADR-070
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console

from drift.commands import console
from drift.commands._io import _emit_machine_output
from drift.errors import EXIT_FINDINGS_ABOVE_THRESHOLD


@click.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Repository root directory.",
)
@click.option(
    "--ref",
    default=None,
    help="Git ref to compare against (reserved for future use).",
)
@click.option(
    "--uncommitted/--no-uncommitted",
    default=True,
    help="Analyze working-tree changes vs HEAD (default: true).",
)
@click.option(
    "--staged-only",
    is_flag=True,
    default=False,
    help="Analyze only staged changes.",
)
@click.option(
    "--fail-on",
    type=click.Choice(["critical", "high", "medium", "low", "none"]),
    default="high",
    help="Severity threshold for FAIL verdict (default: high).",
)
@click.option(
    "--baseline",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Baseline file for fingerprint comparison.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
    help="Output format.",
)
@click.option(
    "--exit-zero",
    is_flag=True,
    default=False,
    help="Always exit with code 0, even on FAIL.",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write output to file instead of stdout.",
)
@click.option(
    "--scope",
    default=None,
    help="Comma-separated file paths to restrict verification scope.",
)
def verify(
    repo: Path,
    ref: str | None,
    uncommitted: bool,
    staged_only: bool,
    fail_on: str,
    baseline: Path | None,
    output_format: str,
    exit_zero: bool,
    output_file: Path | None,
    scope: str | None,
) -> None:
    """Verify structural coherence after edits — binary pass/fail verdict.

    Designed for CI pipelines and agent workflows. Returns PASS when no
    new findings above the severity threshold are introduced and the
    drift score has not degraded.

    \b
    Examples:
      drift verify                              # Quick check, rich output
      drift verify --format json                # Machine-readable verdict
            drift verify --ref main --no-uncommitted # Compare against explicit ref
      drift verify --fail-on medium             # Stricter threshold
      drift verify --scope src/api.py,src/db.py # Restrict to specific files
      drift verify --exit-zero                  # Report-only mode
    """
    from drift.api.verify import verify as api_verify

    scope_files = [s.strip() for s in scope.split(",") if s.strip()] if scope else None

    result = api_verify(
        path=str(repo),
        ref=ref,
        uncommitted=uncommitted if not staged_only else False,
        staged_only=staged_only,
        fail_on=fail_on,
        baseline=str(baseline) if baseline else None,
        scope_files=scope_files,
    )

    # Handle error responses.
    if result.get("type") == "error":
        if output_format == "json":
            _emit_machine_output(json.dumps(result, indent=2, default=str), output_file)
        else:
            console.print(f"[bold red]✗ Verify error:[/bold red] {result.get('message', '')}")
        if not exit_zero:
            sys.exit(EXIT_FINDINGS_ABOVE_THRESHOLD)
        return

    passed = result.get("pass", False)

    if output_format == "json":
        _emit_machine_output(json.dumps(result, indent=2, default=str), output_file)
    else:
        _render_rich_verdict(result, console)

    if not passed and not exit_zero:
        sys.exit(EXIT_FINDINGS_ABOVE_THRESHOLD)


def _render_rich_verdict(result: dict, con: Console) -> None:
    """Render a human-readable pass/fail verdict."""
    from rich.panel import Panel
    from rich.table import Table

    passed = result.get("pass", False)
    delta = result.get("score_delta", 0.0)
    direction = result.get("direction", "stable")
    introduced = result.get("findings_introduced_count", 0)
    resolved = result.get("findings_resolved_count", 0)
    blocking = result.get("blocking_reasons", [])

    if passed:
        con.print(
            Panel(
                f"[bold green]✓ PASS[/bold green]  —  "
                f"No structural coherence degradation detected.\n\n"
                f"  Score delta: {delta:+.4f}  ({direction})\n"
                f"  New findings: {introduced}  |  Resolved: {resolved}",
                title="[bold green]drift verify[/bold green]",
                border_style="green",
            )
        )
    else:
        # Build blocking reasons table.
        table = Table(show_header=True, header_style="bold red")
        table.add_column("Type", style="dim")
        table.add_column("Reason")
        table.add_column("File", style="dim")

        for reason in blocking[:10]:
            table.add_row(
                reason.get("type", ""),
                reason.get("reason", ""),
                reason.get("file", ""),
            )

        con.print(
            Panel(
                f"[bold red]✗ FAIL[/bold red]  —  "
                f"{len(blocking)} blocking reason(s) detected.\n\n"
                f"  Score delta: {delta:+.4f}  ({direction})\n"
                f"  New findings: {introduced}  |  Resolved: {resolved}",
                title="[bold red]drift verify[/bold red]",
                border_style="red",
            )
        )
        con.print(table)
        con.print(
            "\n[dim]Run [bold]drift fix-plan[/bold] for a prioritized repair plan.[/dim]"
        )
