"""drift check — CI-mode diff analysis."""

from __future__ import annotations

import sys
from contextlib import nullcontext
from pathlib import Path

import click
from rich.console import Console

from drift.commands import console
from drift.errors import EXIT_FINDINGS_ABOVE_THRESHOLD


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
    "--output-format",
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json", "sarif", "agent-tasks", "github"]),
    default="rich",
    help="Output format.",
)
@click.option(
    "--exit-zero",
    is_flag=True,
    default=False,
    help="Always exit with code 0, even when findings exceed the severity gate.",
)
@click.option(
    "--select",
    "--signals",
    "select_signals",
    default=None,
    help="Comma-separated signal IDs to include (e.g. PFS,AVS,MDS).",
)
@click.option(
    "--ignore",
    "ignore_signals",
    default=None,
    help="Comma-separated signal IDs to exclude (e.g. TVS,DIA).",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option(
    "--workers",
    "-w",
    default=None,
    type=click.IntRange(min=1),
    help="Parallel workers for file parsing.",
)
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
@click.option(
    "--baseline",
    "baseline_file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Filter out known findings from a baseline file.",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(path_type=Path),
    default=None,
    help="Write machine output (JSON/SARIF) to a file instead of stdout.",
)
@click.option(
    "--json",
    "json_shortcut",
    is_flag=True,
    default=False,
    help="Shortcut for --format json (agent-friendly).",
)
@click.option(
    "--compact",
    "compact_json",
    is_flag=True,
    default=False,
    help="Emit compact JSON optimized for agent/CI summaries.",
)
@click.option(
    "--no-color",
    "no_color",
    is_flag=True,
    default=False,
    help="Disable colored output (also respects NO_COLOR env variable).",
)
def check(
    repo: Path,
    diff_ref: str,
    fail_on: str | None,
    output_format: str,
    exit_zero: bool,
    select_signals: str | None,
    ignore_signals: str | None,
    config: Path | None,
    workers: int | None,
    no_embeddings: bool,
    embedding_model: str | None,
    since_days: int | None,
    quiet: bool,
    no_code: bool,
    baseline_file: Path | None,
    output_file: Path | None,
    json_shortcut: bool,
    compact_json: bool,
    no_color: bool,
) -> None:
    """Check a diff for drift (CI mode)."""
    from drift.analyzer import _DEFAULT_WORKERS, analyze_diff
    from drift.config import DriftConfig
    from drift.scoring.engine import severity_gate_pass

    def _recompute_summary() -> None:
        from drift.scoring.engine import (
            composite_score,
            compute_module_scores,
            compute_signal_scores,
        )

        signal_scores = compute_signal_scores(analysis.findings)
        analysis.drift_score = composite_score(signal_scores, cfg.weights)
        analysis.module_scores = compute_module_scores(analysis.findings, cfg.weights)

    if json_shortcut:
        output_format = "json"

    # Apply --no-color: create a color-disabled console for rich output
    effective_console = Console(no_color=True) if no_color else console

    cfg = DriftConfig.load(repo, config)
    if no_embeddings:
        cfg.embeddings_enabled = False
    if embedding_model:
        cfg.embedding_model = embedding_model
    if select_signals or ignore_signals:
        from drift.config import apply_signal_filter

        apply_signal_filter(cfg, select_signals, ignore_signals)
    threshold = fail_on or cfg.severity_gate()

    effective_workers = workers if workers is not None else _DEFAULT_WORKERS
    effective_since = since_days if since_days is not None else 90
    status_console = Console(stderr=True) if output_format != "rich" else effective_console
    status_context = (
        nullcontext() if quiet else status_console.status("[bold blue]Checking diff...")
    )
    with status_context:
        analysis = analyze_diff(
            repo,
            cfg,
            diff_ref=diff_ref,
            workers=effective_workers,
            since_days=effective_since,
        )

    # Baseline filtering: remove known findings if --baseline is provided
    if baseline_file is not None:
        from drift.baseline import baseline_diff, load_baseline

        fingerprints = load_baseline(baseline_file)
        new, _known = baseline_diff(analysis.findings, fingerprints)
        analysis.findings = new
        _recompute_summary()

    if quiet:
        sev = analysis.severity.value.upper()
        n = len(analysis.findings)
        click.echo(f"score: {analysis.drift_score:.2f}  severity: {sev}  findings: {n}")
    elif output_format == "json":
        from drift.output.json_output import analysis_to_json

        json_text = analysis_to_json(analysis, compact=compact_json)
        if output_file:
            output_file.write_text(json_text + "\n", encoding="utf-8")
            click.echo(f"Output written to {output_file}", err=True)
        else:
            click.echo(json_text)
    elif output_format == "sarif":
        from drift.output.json_output import findings_to_sarif

        sarif_text = findings_to_sarif(analysis)
        if output_file:
            output_file.write_text(sarif_text + "\n", encoding="utf-8")
            click.echo(f"Output written to {output_file}", err=True)
        else:
            click.echo(sarif_text)
    elif output_format == "agent-tasks":
        from drift.output.agent_tasks import analysis_to_agent_tasks_json

        tasks_text = analysis_to_agent_tasks_json(analysis)
        if output_file:
            output_file.write_text(tasks_text + "\n", encoding="utf-8")
            click.echo(f"Output written to {output_file}", err=True)
        else:
            click.echo(tasks_text)
    elif output_format == "github":
        from drift.output.github_format import findings_to_github_annotations

        gh_text = findings_to_github_annotations(analysis)
        if output_file:
            output_file.write_text(gh_text + "\n", encoding="utf-8")
            click.echo(f"Output written to {output_file}", err=True)
        else:
            click.echo(gh_text)
    else:
        from drift.output.rich_output import render_full_report

        render_full_report(analysis, effective_console, show_code=not no_code)

    if not severity_gate_pass(analysis.findings, threshold):
        if not quiet:
            effective_console.print(
                f"\n[bold red]✗ Drift check failed:[/bold red] "
                f"findings at or above '{threshold}' severity.",
            )
        if not exit_zero:
            sys.exit(EXIT_FINDINGS_ABOVE_THRESHOLD)
    elif not quiet:
        effective_console.print(
            f"\n[bold green]✓ Drift check passed[/bold green] (threshold: {threshold}).",
        )
