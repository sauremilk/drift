"""drift check — CI-mode diff analysis."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from drift.commands import console


@click.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
)
@click.option("--diff", "diff_ref", default="HEAD~1", help="Git ref to diff against.")
@click.option(
    "--fail-on",
    type=click.Choice(["critical", "high", "medium", "low", "none"]),
    default=None,
    help="Exit code 1 if any finding at or above this severity. Use 'none' for report-only.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json", "sarif", "agent-tasks"]),
    default="rich",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option("--workers", "-w", default=None, type=int, help="Parallel workers for file parsing.")
@click.option(
    "--no-embeddings", is_flag=True, default=False, help="Disable embedding-based analysis."
)
@click.option("--embedding-model", default=None, help="Sentence-transformers model name.")
@click.option(
    "--since",
    "since_days",
    default=None,
    type=int,
    help="Days of git history to consider.",
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
def check(
    repo: Path,
    diff_ref: str,
    fail_on: str | None,
    output_format: str,
    config: Path | None,
    workers: int | None,
    no_embeddings: bool,
    embedding_model: str | None,
    since_days: int | None,
    quiet: bool,
    no_code: bool,
) -> None:
    """Check a diff for drift (CI mode)."""
    from drift.analyzer import _DEFAULT_WORKERS, analyze_diff
    from drift.config import DriftConfig
    from drift.scoring.engine import severity_gate_pass

    cfg = DriftConfig.load(repo, config)
    if no_embeddings:
        cfg.embeddings_enabled = False
    if embedding_model:
        cfg.embedding_model = embedding_model
    threshold = fail_on or cfg.severity_gate()

    effective_workers = workers if workers is not None else _DEFAULT_WORKERS
    effective_since = since_days if since_days is not None else 90
    with console.status("[bold blue]Checking diff..."):
        analysis = analyze_diff(
            repo, cfg, diff_ref=diff_ref, workers=effective_workers,
            since_days=effective_since,
        )

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
        from drift.output.rich_output import render_full_report

        render_full_report(analysis, console, show_code=not no_code)

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
