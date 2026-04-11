"""drift check — CI-mode diff analysis."""

from __future__ import annotations

import sys
from contextlib import nullcontext
from pathlib import Path

import click
from rich.console import Console

from drift.commands import console
from drift.commands._io import _emit_machine_output
from drift.errors import EXIT_FINDINGS_ABOVE_THRESHOLD


def _recompute_analysis_summary(analysis, cfg) -> None:
    from drift.scoring.engine import (
        composite_score,
        compute_module_scores,
        compute_signal_scores,
    )

    signal_scores = compute_signal_scores(analysis.findings)
    analysis.drift_score = composite_score(signal_scores, cfg.weights)
    analysis.module_scores = compute_module_scores(analysis.findings, cfg.weights)


def _configure_machine_output_console(output_format: str) -> None:
    if output_format != "rich":
        import drift.commands as _cmds

        _cmds.console = Console(stderr=True)


def _build_effective_console(no_color: bool) -> Console:
    return Console(no_color=True) if no_color else console


def _apply_signal_filtering(
    analysis,
    cfg,
    select_signals: str | None,
    ignore_signals: str | None,
) -> None:
    if not (select_signals or ignore_signals):
        return

    from drift.config import SignalWeights
    from drift.models import SignalType

    active_signals = {
        SignalType(field)
        for field in SignalWeights.model_fields
        if getattr(cfg.weights, field, 0.0) > 0.0
    }
    analysis.findings = [f for f in analysis.findings if f.signal_type in active_signals]
    _recompute_analysis_summary(analysis, cfg)


def _apply_baseline_filtering(analysis, cfg, baseline_file: Path | None) -> None:
    if baseline_file is None:
        return

    from drift.baseline import baseline_diff, load_baseline

    fingerprints = load_baseline(baseline_file)
    new, known = baseline_diff(analysis.findings, fingerprints)
    analysis.findings = new
    analysis.suppressed_count += len(known)
    analysis.baseline_new_count = len(new)
    analysis.baseline_matched_count = len(known)
    _recompute_analysis_summary(analysis, cfg)


def _render_or_emit_output(
    analysis,
    output_format: str,
    compact_json: bool,
    drift_score_scope: str,
    output_file: Path | None,
    effective_console: Console,
    max_findings: int,
    no_code: bool,
) -> None:
    if output_format == "json":
        from drift.output.json_output import analysis_to_json

        json_text = analysis_to_json(
            analysis,
            compact=compact_json,
            drift_score_scope=drift_score_scope,
        )
        _emit_machine_output(json_text, output_file)
        return

    if output_format == "sarif":
        from drift.output.json_output import findings_to_sarif

        sarif_text = findings_to_sarif(analysis)
        _emit_machine_output(sarif_text, output_file)
        return

    if output_format == "csv":
        from drift.output.csv_output import analysis_to_csv

        csv_text = analysis_to_csv(analysis)
        _emit_machine_output(csv_text, output_file)
        return

    if output_format == "agent-tasks":
        from drift.output.agent_tasks import analysis_to_agent_tasks_json

        tasks_text = analysis_to_agent_tasks_json(analysis)
        _emit_machine_output(tasks_text, output_file)
        return

    if output_format == "github":
        from drift.output.github_format import findings_to_github_annotations

        gh_text = findings_to_github_annotations(analysis)
        _emit_machine_output(gh_text, output_file)
        return

    if output_format == "junit":
        from drift.output.junit_output import analysis_to_junit

        junit_text = analysis_to_junit(analysis)
        _emit_machine_output(junit_text, output_file)
        return

    if output_format == "llm":
        from drift.output.llm_output import analysis_to_llm

        llm_text = analysis_to_llm(analysis)
        _emit_machine_output(llm_text, output_file)
        return

    from drift.output.rich_output import render_full_report

    render_full_report(
        analysis, effective_console, max_findings=max_findings, show_code=not no_code,
    )


def _print_check_result(
    analysis,
    threshold: str,
    quiet: bool,
    effective_console: Console,
    exit_zero: bool,
    diff_ref: str = "HEAD~1",
) -> None:
    from drift.scoring.engine import severity_gate_pass

    if not severity_gate_pass(analysis.findings, threshold):
        if not quiet:
            effective_console.print(
                f"\n[bold red]✗ Drift check failed:[/bold red] "
                f"findings at or above '{threshold}' severity.",
            )
        if not exit_zero:
            sys.exit(EXIT_FINDINGS_ABOVE_THRESHOLD)
        return

    if not quiet:
        effective_console.print(
            f"\n[bold green]✓ Drift check passed[/bold green] (threshold: {threshold}).",
        )
        if not analysis.findings and diff_ref == "HEAD~1":
            from rich.panel import Panel

            effective_console.print(
                Panel(
                    "[dim]drift check scans only changed files (vs. HEAD~1 by default).\n"
                    "To scan the full repository:  [bold]drift analyze --repo .[/bold]\n"
                    "To check more history:        [bold]drift check --diff HEAD~3[/bold][/dim]",
                    title="[dim]Note[/dim]",
                    border_style="dim",
                )
            )


@click.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
)
@click.option(
    "--path", "--target-path", "-p",
    "target_path",
    default=None,
    help="Restrict analysis to a subdirectory.",
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
    type=click.Choice(["rich", "json", "sarif", "csv", "agent-tasks", "github", "junit", "llm"]),
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
    help="Write machine output (JSON/SARIF/CSV) to a file instead of stdout.",
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
@click.option(
    "--save-baseline",
    "save_baseline_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Save the current findings as a baseline file after analysis.",
)
@click.option(
    "--max-findings",
    type=int,
    default=20,
    help="Maximum number of findings to display (default: 20).",
)
def check(
    repo: Path,
    target_path: str | None,
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
    save_baseline_path: Path | None,
    max_findings: int,
) -> None:
    """CI gate — analyze a diff and exit non-zero when findings exceed a threshold.

    Use in CI pipelines and pre-merge checks.
    For detailed investigation, use ``analyze``.
    """
    from drift.analyzer import _DEFAULT_WORKERS, analyze_diff
    from drift.api_helpers import build_drift_score_scope, signal_scope_label
    from drift.config import DriftConfig
    if json_shortcut:
        output_format = "json"

    # Keep machine-readable payloads clean by routing shared console to stderr.
    _configure_machine_output_console(output_format)
    effective_console = _build_effective_console(no_color)

    cfg = DriftConfig.load(repo, config)
    if no_embeddings:
        cfg.embeddings_enabled = False
    if embedding_model:
        cfg.embedding_model = embedding_model
    if select_signals or ignore_signals:
        from drift.config import apply_signal_filter, resolve_signal_names

        apply_signal_filter(cfg, select_signals, ignore_signals)

    drift_score_scope = build_drift_score_scope(
        context="diff",
        path=target_path,
        signal_scope=signal_scope_label(
            selected=resolve_signal_names(select_signals) if select_signals else None,
            ignored=resolve_signal_names(ignore_signals) if ignore_signals else None,
        ),
        baseline_filtered=baseline_file is not None,
    )
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
            target_path=target_path,
        )

    _apply_signal_filtering(analysis, cfg, select_signals, ignore_signals)
    _apply_baseline_filtering(analysis, cfg, baseline_file)

    if quiet:
        sev = analysis.severity.value.upper()
        n = len(analysis.findings)
        click.echo(f"score: {analysis.drift_score:.3f}  severity: {sev}  findings: {n}")
    else:
        _render_or_emit_output(
            analysis=analysis,
            output_format=output_format,
            compact_json=compact_json,
            drift_score_scope=drift_score_scope,
            output_file=output_file,
            effective_console=effective_console,
            max_findings=max_findings,
            no_code=no_code,
        )

    # Save baseline if requested (--save-baseline)
    if save_baseline_path is not None:
        from drift.baseline import save_baseline as _save_bl

        _save_bl(analysis, save_baseline_path)
        effective_console.print(
            f"[bold green]\u2713 Baseline saved:[/bold green] {save_baseline_path} "
            f"({len(analysis.findings)} findings)",
        )

    _print_check_result(
        analysis=analysis,
        threshold=threshold,
        quiet=quiet,
        effective_console=effective_console,
        exit_zero=exit_zero,
        diff_ref=diff_ref,
    )
