"""drift analyze — full repository analysis."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from drift.commands import console


@click.command()
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
    type=click.Choice(["rich", "json", "sarif", "agent-tasks"]),
    default="rich",
    help="Output format.",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option("--workers", "-w", default=None, type=int, help="Parallel workers for file parsing.")
@click.option(
    "--no-embeddings", is_flag=True, default=False, help="Disable embedding-based analysis."
)
@click.option("--embedding-model", default=None, help="Sentence-transformers model name.")
@click.option(
    "--sort-by",
    type=click.Choice(["impact", "score"]),
    default="impact",
    help="Sort findings by impact (default) or raw score.",
)
@click.option(
    "--max-findings",
    type=int,
    default=20,
    help="Maximum number of findings to display (default: 20).",
)
@click.option(
    "--show-suppressed",
    is_flag=True,
    default=False,
    help="Show findings suppressed via drift:ignore comments.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Minimal output: score, severity, finding count, exit code only.",
)
@click.option(
    "--no-code",
    is_flag=True,
    default=False,
    help="Suppress inline code snippets in rich output.",
)
def analyze(
    repo: Path,
    path: str | None,
    since: int,
    output_format: str,
    config: Path | None,
    workers: int | None,
    no_embeddings: bool,
    embedding_model: str | None,
    sort_by: str,
    max_findings: int,
    show_suppressed: bool,
    quiet: bool,
    no_code: bool,
) -> None:
    """Analyze a repository for architectural drift."""
    from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

    from drift.analyzer import _DEFAULT_WORKERS, analyze_repo
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)
    if no_embeddings:
        cfg.embeddings_enabled = False
    if embedding_model:
        cfg.embedding_model = embedding_model

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
            repo,
            cfg,
            since_days=since,
            target_path=path,
            on_progress=_on_progress,
            workers=workers if workers is not None else _DEFAULT_WORKERS,
        )
        if task_id is not None:
            progress.update(task_id, completed=_last_total)

    if quiet:
        sev = analysis.severity.value.upper()
        n = len(analysis.findings)
        click.echo(f"score: {analysis.drift_score:.2f}  severity: {sev}  findings: {n}")
    elif output_format == "json":
        from drift.output.json_output import analysis_to_json

        click.echo(analysis_to_json(analysis))
    elif output_format == "sarif":
        from drift.output.json_output import findings_to_sarif

        click.echo(findings_to_sarif(analysis))
    elif output_format == "agent-tasks":
        from drift.output.agent_tasks import analysis_to_agent_tasks_json

        click.echo(analysis_to_agent_tasks_json(analysis))
    else:
        from drift.output.rich_output import render_full_report, render_recommendations

        render_full_report(
            analysis,
            console,
            sort_by=sort_by,
            max_findings=max_findings,
            show_code=not no_code,
        )

        if show_suppressed and analysis.suppressed_count:
            console.print(
                f"[dim italic]{analysis.suppressed_count} finding(s) suppressed "
                f"via drift:ignore comments.[/dim italic]"
            )

        # Actionable recommendations
        from drift.recommendations import generate_recommendations

        recs = generate_recommendations(analysis.findings)
        if recs:
            render_recommendations(recs, console)

