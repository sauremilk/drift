"""drift analyze — full repository analysis."""

from __future__ import annotations

import sys
from contextlib import nullcontext
from pathlib import Path

import click
from rich.console import Console

from drift.commands import console
from drift.errors import EXIT_FINDINGS_ABOVE_THRESHOLD, DriftConfigError


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
    "--output-format",
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json", "sarif", "agent-tasks", "github"]),
    default="rich",
    help="Output format.",
)
@click.option(
    "--fail-on",
    type=click.Choice(["critical", "high", "medium", "low", "none"]),
    default=None,
    help="Exit code 1 if any finding at or above this severity.",
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
    "--save-baseline",
    "save_baseline_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Save the current findings as a baseline file after analysis.",
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
def analyze(
    repo: Path,
    path: str | None,
    since: int,
    output_format: str,
    fail_on: str | None,
    exit_zero: bool,
    select_signals: str | None,
    ignore_signals: str | None,
    config: Path | None,
    workers: int | None,
    no_embeddings: bool,
    embedding_model: str | None,
    sort_by: str,
    max_findings: int,
    show_suppressed: bool,
    quiet: bool,
    no_code: bool,
    baseline_file: Path | None,
    output_file: Path | None,
    save_baseline_path: Path | None,
    json_shortcut: bool,
    compact_json: bool,
    no_color: bool,
) -> None:
    """Detailed drift analysis \u2014 produces comprehensive findings for investigation and triage.

    For CI-compatible exit codes on diffs, use ``check``.
    """
    from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

    from drift.analyzer import _DEFAULT_WORKERS, analyze_repo
    from drift.config import DriftConfig

    def _write_output_file(content: str, destination: Path) -> None:
        try:
            destination.write_text(content + "\n", encoding="utf-8")
        except OSError as exc:
            raise DriftConfigError(
                "DRIFT-2003",
                path=str(destination),
                reason=str(exc),
            ) from exc

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

    # For machine-readable formats, redirect the shared console to stderr
    # so stray console.print() calls never pollute the JSON payload.  (#75, #77)
    if output_format != "rich":
        import drift.commands as _cmds

        _cmds.console = Console(stderr=True)

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

    # For machine-readable formats, send progress to stderr so stdout stays clean
    progress_console = Console(stderr=True) if output_format != "rich" else effective_console

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

    progress_context = nullcontext() if quiet else progress
    with progress_context:
        analysis = analyze_repo(
            repo,
            cfg,
            since_days=since,
            target_path=path,
            on_progress=None if quiet else _on_progress,
            workers=workers if workers is not None else _DEFAULT_WORKERS,
        )
        if not quiet and task_id is not None:
            progress.update(task_id, completed=_last_total)

    # Baseline filtering: remove known findings if --baseline is provided
    if baseline_file is not None:
        from drift.baseline import baseline_diff, load_baseline

        fingerprints = load_baseline(baseline_file)
        new, known = baseline_diff(analysis.findings, fingerprints)
        analysis.findings = new
        _recompute_summary()

    if quiet:
        sev = analysis.severity.value.upper()
        n = len(analysis.findings)
        click.echo(f"score: {analysis.drift_score:.3f}  severity: {sev}  findings: {n}")
    elif output_format == "json":
        from drift.output.json_output import analysis_to_json

        json_text = analysis_to_json(analysis, compact=compact_json)
        if output_file:
            _write_output_file(json_text, output_file)
            click.echo(f"Output written to {output_file}", err=True)
        else:
            click.echo(json_text)
    elif output_format == "sarif":
        from drift.output.json_output import findings_to_sarif

        sarif_text = findings_to_sarif(analysis)
        if output_file:
            _write_output_file(sarif_text, output_file)
            click.echo(f"Output written to {output_file}", err=True)
        else:
            click.echo(sarif_text)
    elif output_format == "agent-tasks":
        from drift.output.agent_tasks import analysis_to_agent_tasks_json

        tasks_text = analysis_to_agent_tasks_json(analysis)
        if output_file:
            _write_output_file(tasks_text, output_file)
            click.echo(f"Output written to {output_file}", err=True)
        else:
            click.echo(tasks_text)
    elif output_format == "github":
        from drift.output.github_format import findings_to_github_annotations

        gh_text = findings_to_github_annotations(analysis)
        if output_file:
            _write_output_file(gh_text, output_file)
            click.echo(f"Output written to {output_file}", err=True)
        else:
            click.echo(gh_text)
    else:
        from drift.output.rich_output import render_full_report, render_recommendations

        render_full_report(
            analysis,
            effective_console,
            sort_by=sort_by,
            max_findings=max_findings,
            show_code=not no_code,
        )

        if show_suppressed and analysis.suppressed_count:
            effective_console.print(
                f"[dim italic]{analysis.suppressed_count} finding(s) suppressed "
                f"via drift:ignore comments.[/dim italic]"
            )

        # Actionable recommendations
        from drift.recommendations import generate_recommendations

        recs = generate_recommendations(analysis.findings)
        if recs:
            render_recommendations(recs, effective_console)

    # Save baseline if requested (--save-baseline)
    if save_baseline_path is not None:
        from drift.baseline import save_baseline as _save_bl

        _save_bl(analysis, save_baseline_path)
        effective_console.print(
            f"[bold green]✓ Baseline saved:[/bold green] {save_baseline_path} "
            f"({len(analysis.findings)} findings)",
        )

    # Severity gate (opt-in via --fail-on)
    threshold = fail_on or cfg.severity_gate()
    if threshold and threshold != "none":
        from drift.scoring.engine import severity_gate_pass

        if not severity_gate_pass(analysis.findings, threshold):
            if not quiet:
                effective_console.print(
                    f"\n[bold red]\u2717 Drift check failed:[/bold red] "
                    f"findings at or above '{threshold}' severity.",
                )
            if not exit_zero:
                sys.exit(EXIT_FINDINGS_ABOVE_THRESHOLD)
        elif not quiet:
            effective_console.print(
                f"\n[bold green]\u2713 Drift check passed[/bold green] "
                f"(threshold: {threshold}).",
            )

