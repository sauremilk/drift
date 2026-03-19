"""Drift CLI — command line interface."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console

from drift import __version__

console = Console()


def _configure_logging(verbose: bool = False) -> None:
    """Set up structured logging for the drift tool."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        format="%(levelname)s [%(name)s] %(message)s",
        level=level,
    )


@click.group()
@click.version_option(version=__version__, prog_name="drift")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable debug logging.")
def main(verbose: bool = False) -> None:
    """Drift — Detect architectural erosion from AI-generated code."""
    _configure_logging(verbose)


@main.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option("--path", "-p", default=None, help="Restrict analysis to a subdirectory.")
@click.option("--since", "-s", default=90, type=int, help="Days of git history to analyze.")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json", "sarif"]),
    default="rich",
    help="Output format.",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option(
    "--workers", "-w", default=8, type=int, help="Parallel workers for file parsing."
)
def analyze(
    repo: Path,
    path: str | None,
    since: int,
    output_format: str,
    config: Path | None,
    workers: int,
) -> None:
    """Analyze a repository for architectural drift."""
    from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)

    # For machine-readable formats, send progress to stderr so stdout stays clean
    progress_console = Console(stderr=True) if output_format != "rich" else console

    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=progress_console,
    )

    task_id = None
    _last_total: int = 1

    def _on_progress(phase: str, current: int, total: int) -> None:
        nonlocal task_id, _last_total
        if task_id is not None:
            progress.update(task_id, completed=total, total=total)
            progress.remove_task(task_id)
        _last_total = max(total, 1)
        task_id = progress.add_task(phase, total=_last_total, completed=current)

    with progress:
        analysis = analyze_repo(
            repo, cfg, since_days=since, target_path=path,
            on_progress=_on_progress, workers=workers,
        )
        if task_id is not None:
            progress.update(task_id, completed=_last_total)

    if output_format == "json":
        from drift.output.json_output import analysis_to_json

        click.echo(analysis_to_json(analysis))
    elif output_format == "sarif":
        from drift.output.json_output import findings_to_sarif

        click.echo(findings_to_sarif(analysis))
    else:
        from drift.output.rich_output import render_full_report, render_recommendations

        render_full_report(analysis, console)

        # Actionable recommendations
        from drift.recommendations import generate_recommendations

        recs = generate_recommendations(analysis.findings)
        if recs:
            render_recommendations(recs, console)


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
@click.option(
    "--workers", "-w", default=8, type=int, help="Parallel workers for file parsing."
)
def check(
    repo: Path,
    diff_ref: str,
    fail_on: str | None,
    output_format: str,
    config: Path | None,
    workers: int,
) -> None:
    """Check a diff for drift (CI mode)."""
    from drift.analyzer import analyze_diff
    from drift.config import DriftConfig
    from drift.scoring.engine import severity_gate_pass

    cfg = DriftConfig.load(repo, config)
    threshold = fail_on or cfg.severity_gate()

    with console.status("[bold blue]Checking diff..."):
        analysis = analyze_diff(repo, cfg, diff_ref=diff_ref, workers=workers)

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
            f"\n[bold green]✓ Drift check passed[/bold green] (threshold: {threshold}).",
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

    cfg = DriftConfig.load(repo)

    with console.status("[bold blue]Discovering patterns..."):
        analysis = analyze_repo(repo, cfg)

    for cat, instances in sorted(analysis.pattern_catalog.items(), key=lambda x: x[0].value):
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
@click.option("--since", "-s", default=90, type=int, help="Days of git history to analyze.")
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
def timeline(repo: Path, since: int, config: Path | None) -> None:
    """Show when and why drift began in each module (root-cause analysis)."""
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig
    from drift.ingestion.file_discovery import discover_files
    from drift.ingestion.git_history import build_file_histories, parse_git_history
    from drift.output.rich_output import render_timeline
    from drift.timeline import build_timeline

    cfg = DriftConfig.load(repo, config)

    with console.status("[bold blue]Analyzing repository..."):
        analysis = analyze_repo(repo, cfg, since_days=since)

    # Reconstruct commits and file histories for timeline
    with console.status("[bold blue]Building timeline..."):
        files = discover_files(repo.resolve(), include=cfg.include, exclude=cfg.exclude)
        known_files = {f.path.as_posix() for f in files}
        commits = parse_git_history(repo.resolve(), since_days=since, file_filter=known_files)
        file_histories = build_file_histories(commits, known_files=known_files)

        module_scores = {ms.path.as_posix(): ms.drift_score for ms in analysis.module_scores}
        tl = build_timeline(commits, file_histories, analysis.findings, module_scores)

    console.print()
    console.print(f"[bold]Drift Timeline — {repo.resolve().name}[/bold]  ({since}-day history)")
    render_timeline(tl, console)


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
    import json

    from rich.table import Table

    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)
    history_file = repo / cfg.cache_dir / "history.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing snapshots
    snapshots: list[dict] = []
    if history_file.exists():
        try:
            snapshots = json.loads(history_file.read_text(encoding="utf-8"))
        except Exception:
            snapshots = []

    console.print(f"[bold]Drift — trend ({days}-day history window)[/bold]")
    console.print()

    with console.status("[bold blue]Analyzing current state..."):
        analysis = analyze_repo(repo, cfg, since_days=days)

    # Save snapshot
    from drift.scoring.engine import compute_signal_scores

    signal_scores = compute_signal_scores(analysis.findings)
    snapshot = {
        "timestamp": analysis.analyzed_at.isoformat(),
        "drift_score": analysis.drift_score,
        "signal_scores": {s.value: v for s, v in signal_scores.items()},
        "total_files": analysis.total_files,
        "total_findings": len(analysis.findings),
    }
    snapshots.append(snapshot)

    # Keep last 100 snapshots
    snapshots = snapshots[-100:]
    history_file.write_text(json.dumps(snapshots, indent=2), encoding="utf-8")

    # Display trend table
    if len(snapshots) < 2:
        console.print(f"  Drift score: [bold]{analysis.drift_score:.3f}[/bold]")
        console.print(f"  Files: {analysis.total_files}  |  Findings: {len(analysis.findings)}")
        console.print()
        console.print("[dim]Run again later to see trend comparison.[/dim]")
        return

    table = Table(title="Score History (last 10)")
    table.add_column("Timestamp", min_width=20)
    table.add_column("Score", justify="right")
    table.add_column("Δ", justify="right")
    table.add_column("Findings", justify="right")

    recent = snapshots[-10:]
    for i, snap in enumerate(recent):
        ts = snap["timestamp"][:19].replace("T", " ")
        score = snap["drift_score"]
        findings = snap.get("total_findings", "?")

        if i > 0:
            prev = recent[i - 1]["drift_score"]
            delta = score - prev
            delta_str = f"{delta:+.3f}"
            if delta > 0.01:
                delta_str = f"[red]{delta_str}[/red]"
            elif delta < -0.01:
                delta_str = f"[green]{delta_str}[/green]"
        else:
            delta_str = "—"

        color = "red" if score >= 0.6 else "yellow" if score >= 0.3 else "green"
        table.add_row(ts, f"[{color}]{score:.3f}[/{color}]", delta_str, str(findings))

    console.print(table)
    console.print()

    # Summary
    first_score = snapshots[0]["drift_score"]
    latest_score = snapshots[-1]["drift_score"]
    overall_delta = latest_score - first_score
    direction = (
        "[red]↑ increasing[/red]"
        if overall_delta > 0.01
        else "[green]↓ decreasing[/green]"
        if overall_delta < -0.01
        else "[dim]→ stable[/dim]"
    )
    console.print(
        f"  Overall trend ({len(snapshots)} snapshots): {direction}  ({overall_delta:+.3f})"
    )

    console.print(f"  Current drift score: [bold]{analysis.drift_score:.2f}[/bold]")
    console.print(f"  Files analyzed: {analysis.total_files}")
    console.print(f"  Total findings: {len(analysis.findings)}")
    console.print(f"  AI-attributed commits: {analysis.ai_attributed_ratio:.0%}")

    # Trend chart
    if len(snapshots) >= 3:
        from drift.output.rich_output import render_trend_chart

        render_trend_chart(snapshots, console=console)


if __name__ == "__main__":
    main()
