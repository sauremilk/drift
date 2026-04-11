"""drift analyze — full repository analysis."""

from __future__ import annotations

import sys
from contextlib import nullcontext
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
    help="Path to the repository root.",
)
@click.option(
    "--path", "--target-path", "-p",
    default=None,
    help="Restrict analysis to a subdirectory.",
)
@click.option("--since", "-s", default=90, type=int, help="Days of git history to analyze.")
@click.option(
    "--output-format",
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json", "sarif", "csv", "markdown", "agent-tasks", "github"]),
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
    help="Write machine output (JSON/SARIF/CSV) to a file instead of stdout.",
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
@click.option(
    "--progress",
    "progress_format",
    type=click.Choice(["auto", "json", "none"]),
    default="auto",
    help="Progress reporting: auto (Rich bar), json (JSON-lines on stderr), none.",
)
@click.option(
    "--explain",
    "explain",
    is_flag=True,
    default=False,
    help="Show contextual explanation panels for each finding (why it matters, suggested action).",
)
@click.option(
    "--group-by",
    "group_by",
    type=click.Choice(["signal", "severity", "directory", "module"]),
    default=None,
    help="Group findings by dimension: signal, severity, directory, or module.",
)
@click.option(
    "--no-first-run",
    "no_first_run",
    is_flag=True,
    default=False,
    help="Disable the compact first-run output even when no drift.yaml exists.",
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
    progress_format: str,
    explain: bool,
    group_by: str | None,
    no_first_run: bool,
) -> None:
    """Detailed drift analysis \u2014 produces comprehensive findings for investigation and triage.

    For CI-compatible exit codes on diffs, use ``check``.
    """
    from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

    from drift.analyzer import _DEFAULT_WORKERS, analyze_repo
    from drift.api_helpers import build_drift_score_scope, signal_scope_label
    from drift.config import DriftConfig

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
    active_signals: set[str] | None = None
    if select_signals or ignore_signals:
        from drift.config import apply_signal_filter, resolve_signal_names

        apply_signal_filter(cfg, select_signals, ignore_signals)
        if select_signals:
            active_signals = set(resolve_signal_names(select_signals))

    drift_score_scope = build_drift_score_scope(
        context="repo",
        path=path,
        signal_scope=signal_scope_label(
            selected=resolve_signal_names(select_signals) if select_signals else None,
            ignored=resolve_signal_names(ignore_signals) if ignore_signals else None,
        ),
        baseline_filtered=baseline_file is not None,
    )

    # For machine-readable formats, send progress to stderr so stdout stays clean
    progress_console = Console(stderr=True) if output_format != "rich" else effective_console

    # Auto-detect: for non-TTY consumers, emit JSON progress on stderr (#155)
    if progress_format == "auto":
        from drift.commands._io import _is_non_tty_stdout

        if _is_non_tty_stdout():
            progress_format = "json"

    use_json_progress = progress_format == "json"
    # Auto-suppress Rich progress for machine-readable formats to avoid
    # stderr noise that triggers NativeCommandError in PowerShell (#118).
    use_rich_progress = (
        progress_format == "auto" and not quiet and output_format == "rich"
    )
    use_no_progress = progress_format == "none" or quiet or (
        progress_format == "auto" and output_format != "rich"
    )

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

    def _on_progress_json(phase: str, current: int, total: int) -> None:
        import json as _json
        import time

        msg = {
            "type": "progress",
            "step": current,
            "total": total,
            "signal": phase,
            "elapsed_s": round(time.monotonic() - _json_start, 1),
        }
        sys.stderr.write(_json.dumps(msg) + "\n")
        sys.stderr.flush()

    _json_start = 0.0
    if use_json_progress:
        import time
        _json_start = time.monotonic()

    if use_json_progress:
        effective_callback = _on_progress_json
    elif use_no_progress:
        effective_callback = None
    else:
        effective_callback = _on_progress

    progress_context = nullcontext() if not use_rich_progress else progress
    with progress_context:
        analysis = analyze_repo(
            repo,
            cfg,
            since_days=since,
            target_path=path,
            on_progress=effective_callback,
            workers=workers if workers is not None else _DEFAULT_WORKERS,
            active_signals=active_signals,
        )
        if use_rich_progress and task_id is not None:
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
        grade = analysis.grade[0]
        click.echo(
            f"score: {analysis.drift_score:.3f}  grade: {grade}"
            f"  severity: {sev}  findings: {n}"
        )
    elif output_format == "json":
        from drift.output.json_output import analysis_to_json

        json_text = analysis_to_json(
            analysis,
            compact=compact_json,
            drift_score_scope=drift_score_scope,
            language=cfg.language,
            group_by=group_by,
        )
        _emit_machine_output(json_text, output_file)
    elif output_format == "sarif":
        from drift.output.json_output import findings_to_sarif

        sarif_text = findings_to_sarif(analysis)
        _emit_machine_output(sarif_text, output_file)
    elif output_format == "csv":
        from drift.output.csv_output import analysis_to_csv

        csv_text = analysis_to_csv(analysis)
        _emit_machine_output(csv_text, output_file)
    elif output_format == "agent-tasks":
        from drift.output.agent_tasks import analysis_to_agent_tasks_json

        tasks_text = analysis_to_agent_tasks_json(analysis)
        _emit_machine_output(tasks_text, output_file)
    elif output_format == "markdown":
        from drift.output.markdown_report import analysis_to_markdown

        md_text = analysis_to_markdown(analysis, max_findings=max_findings)
        _emit_machine_output(md_text, output_file)
    elif output_format == "github":
        from drift.output.github_format import findings_to_github_annotations

        gh_text = findings_to_github_annotations(analysis)
        _emit_machine_output(gh_text, output_file)
    else:
        from drift.output.rich_output import render_full_report, render_recommendations

        # Auto-detect first-run: no drift.yaml and no .drift/ in repo
        is_first_run = (
            not no_first_run
            and not (repo / "drift.yaml").exists()
            and not (repo / ".drift").exists()
        )

        render_full_report(
            analysis,
            effective_console,
            sort_by=sort_by,
            max_findings=max_findings,
            show_code=not no_code,
            language=cfg.language,
            explain=explain,
            group_by=group_by,
            first_run=is_first_run,
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

