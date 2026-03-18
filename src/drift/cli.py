"""Drift CLI — command line interface."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from drift import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="drift")
def main() -> None:
    """Drift — Detect architectural erosion from AI-generated code."""


@main.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option("--path", "-p", default=None, help="Restrict analysis to a subdirectory.")
@click.option(
    "--since", "-s", default=90, type=int, help="Days of git history to analyze."
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json", "sarif"]),
    default="rich",
    help="Output format.",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
def analyze(
    repo: Path,
    path: str | None,
    since: int,
    output_format: str,
    config: Path | None,
) -> None:
    """Analyze a repository for architectural drift."""
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)

    with console.status("[bold blue]Analyzing repository..."):
        analysis = analyze_repo(repo, cfg, since_days=since, target_path=path)

    if output_format == "json":
        from drift.output.json_output import analysis_to_json

        click.echo(analysis_to_json(analysis))
    elif output_format == "sarif":
        from drift.output.json_output import findings_to_sarif

        click.echo(findings_to_sarif(analysis))
    else:
        from drift.output.rich_output import render_full_report

        render_full_report(analysis, console)


@main.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
)
@click.option("--diff", "diff_ref", default="HEAD~1", help="Git ref to diff against.")
@click.option(
    "--fail-on",
    type=click.Choice(["critical", "high", "medium", "low"]),
    default=None,
    help="Exit code 1 if any finding at or above this severity.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json", "sarif"]),
    default="rich",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
def check(
    repo: Path,
    diff_ref: str,
    fail_on: str | None,
    output_format: str,
    config: Path | None,
) -> None:
    """Check a diff for drift (CI mode)."""
    from drift.analyzer import analyze_diff
    from drift.config import DriftConfig
    from drift.scoring.engine import severity_gate_pass

    cfg = DriftConfig.load(repo, config)
    threshold = fail_on or cfg.severity_gate()

    with console.status("[bold blue]Checking diff..."):
        analysis = analyze_diff(repo, cfg, diff_ref=diff_ref)

    if output_format == "json":
        from drift.output.json_output import analysis_to_json

        click.echo(analysis_to_json(analysis))
    elif output_format == "sarif":
        from drift.output.json_output import findings_to_sarif

        click.echo(findings_to_sarif(analysis))
    else:
        from drift.output.rich_output import render_full_report

        render_full_report(analysis, console)

    if not severity_gate_pass(analysis.findings, threshold):
        console.print(
            f"\n[bold red]✗ Drift check failed:[/bold red] "
            f"findings at or above '{threshold}' severity.",
        )
        sys.exit(1)
    else:
        console.print(
            f"\n[bold green]✓ Drift check passed[/bold green] "
            f"(threshold: {threshold}).",
        )


@main.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
)
@click.option(
    "--category",
    type=click.Choice(
        [
            "error_handling",
            "data_access",
            "api_endpoint",
            "caching",
            "logging",
            "authentication",
            "validation",
        ]
    ),
    default=None,
    help="Filter by pattern category.",
)
def patterns(repo: Path, category: str | None) -> None:
    """Show discovered code patterns in the repository."""
    from rich.table import Table

    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig
    from drift.models import PatternCategory

    cfg = DriftConfig.load(repo)

    with console.status("[bold blue]Discovering patterns..."):
        analysis = analyze_repo(repo, cfg)

    for cat, instances in sorted(
        analysis.pattern_catalog.items(), key=lambda x: x[0].value
    ):
        if category and cat.value != category:
            continue

        table = Table(title=f"Pattern: {cat.value} ({len(instances)} instances)")
        table.add_column("File", min_width=30)
        table.add_column("Function", min_width=20)
        table.add_column("Lines")
        table.add_column("Variant", min_width=15)

        for inst in instances[:20]:
            variant = inst.variant_id or "—"
            table.add_row(
                inst.file_path.as_posix(),
                inst.function_name,
                f"{inst.start_line}-{inst.end_line}",
                variant,
            )

        console.print(table)
        console.print()

    if not analysis.pattern_catalog:
        console.print("[dim]No patterns detected.[/dim]")


@main.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
)
@click.option("--last", "days", default=90, type=int, help="Number of days to trend.")
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
def trend(repo: Path, days: int, config: Path | None) -> None:
    """Show drift score trend over time (requires git history)."""
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)

    # Analyze at multiple points in history
    intervals = min(days // 7, 12)  # Weekly intervals, max 12
    if intervals < 2:
        intervals = 2

    console.print(
        f"[bold]Drift trend over {days} days ({intervals} data points)[/bold]"
    )
    console.print()

    # For MVP: just show current score with a note about temporal analysis
    with console.status("[bold blue]Analyzing current state..."):
        analysis = analyze_repo(repo, cfg, since_days=days)

    console.print(f"  Current drift score: [bold]{analysis.drift_score:.2f}[/bold]")
    console.print(f"  Files analyzed: {analysis.total_files}")
    console.print(f"  Total findings: {len(analysis.findings)}")
    console.print(f"  AI-attributed commits: {analysis.ai_attributed_ratio:.0%}")
    console.print()
    console.print(
        "[dim]Full temporal trend analysis (weekly history snapshots) "
        "is planned for v0.2.0.[/dim]"
    )


if __name__ == "__main__":
    main()
