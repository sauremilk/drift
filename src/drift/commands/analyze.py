"""drift analyze — full repository analysis."""

from __future__ import annotations

import sys
from contextlib import nullcontext
from pathlib import Path
from typing import Literal, cast

import click
from rich.console import Console

from drift.errors import EXIT_FINDINGS_ABOVE_THRESHOLD


def _apply_analysis_cfg_overrides(
    cfg: object,
    worker_strategy: str | None,
    load_profile: str | None,
    no_embeddings: bool,
    embedding_model: str | None,
) -> None:
    """Apply CLI-level performance/model overrides to the loaded config."""
    if worker_strategy is not None:
        cfg.performance.worker_strategy = cast(Literal["fixed", "auto"], worker_strategy)  # type: ignore[union-attr, attr-defined]
    if load_profile is not None:
        cfg.performance.load_profile = cast(Literal["conservative"], load_profile)  # type: ignore[union-attr, attr-defined]
    if no_embeddings:
        cfg.embeddings_enabled = False  # type: ignore[union-attr, attr-defined]
    if embedding_model:
        cfg.embedding_model = embedding_model  # type: ignore[union-attr, attr-defined]


def _resolve_progress_mode(
    progress_format: str,
    output_format: str,
    quiet: bool,
) -> tuple[bool, bool, bool]:
    """Resolve progress mode flags, auto-detecting non-TTY stdout.

    Returns (use_json, use_rich, use_none).
    """
    if progress_format == "auto":
        from drift.commands._io import _is_non_tty_stdout

        if _is_non_tty_stdout():
            progress_format = "json"
    use_json_progress = progress_format == "json"
    use_rich_progress = progress_format == "auto" and not quiet and output_format == "rich"
    use_no_progress = (
        progress_format == "none"
        or quiet
        or (progress_format == "auto" and output_format != "rich")
    )
    return use_json_progress, use_rich_progress, use_no_progress


def _build_progress_callback(
    use_json_progress: bool,
    use_no_progress: bool,
    progress: object,
) -> tuple[object, list[object]]:
    """Build a progress callback function. Returns (callback_or_none, task_state)."""
    task_state: list[object] = [None, 1]  # [task_id, _last_total]

    def _on_rich(phase: str, current: int, total: int) -> None:
        if task_state[0] is not None:
            progress.update(task_state[0], completed=total, total=total)  # type: ignore[union-attr, attr-defined]
            progress.remove_task(task_state[0])  # type: ignore[union-attr, attr-defined]
        task_state[1] = max(total, 1)
        task_state[0] = progress.add_task(phase, total=task_state[1], completed=current)  # type: ignore[union-attr, attr-defined]

    if use_json_progress:
        import time

        _json_start = time.monotonic()
    else:
        _json_start = 0.0

    def _on_json(phase: str, current: int, total: int) -> None:
        import json as _json
        import time as _time

        msg = {
            "type": "progress",
            "step": current,
            "total": total,
            "signal": phase,
            "elapsed_s": round(_time.monotonic() - _json_start, 1),
        }
        sys.stderr.write(_json.dumps(msg) + "\n")
        sys.stderr.flush()

    if use_json_progress:
        return _on_json, task_state
    if use_no_progress:
        return None, task_state
    return _on_rich, task_state


def _maybe_enrich_plain_messages(
    analysis: object,
    audience: str | None,
    language_override: str | None,
    cfg: object,
) -> None:
    """Enrich findings with plain-language messages if --audience plain is requested."""
    effective_audience = audience or getattr(cfg, "audience", None)
    effective_language = language_override or getattr(cfg, "language", None) or "en"
    if effective_audience == "plain":
        from drift.lang import enrich_human_messages

        analysis.findings = enrich_human_messages(  # type: ignore[union-attr, attr-defined]
            analysis.findings, lang=effective_language, audience="plain"  # type: ignore[union-attr, attr-defined]
        )


def _render_analysis_details(
    analysis: object,
    output_format: str,
    compact_json: bool,
    drift_score_scope: object,
    output_file: Path | None,
    effective_console: Console,
    max_findings: int,
    no_code: bool,
    response_detail: str,
    cfg: object,
    group_by: str | None,
    sort_by: str,
    explain: bool,
    no_first_run: bool,
    repo: Path,
    show_suppressed: bool,
) -> None:
    """Render full (non-quiet) analysis output: findings, suppression count, recommendations."""
    from drift.commands._shared import render_or_emit_output

    is_first_run = (
        not no_first_run
        and not (repo / "drift.yaml").exists()
        and not (repo / ".drift").exists()
    )
    render_or_emit_output(
        analysis=analysis,
        output_format=output_format,
        compact_json=compact_json,
        drift_score_scope=drift_score_scope,  # type: ignore[arg-type]
        output_file=output_file,
        effective_console=effective_console,
        max_findings=max_findings,
        no_code=no_code,
        response_detail=response_detail,
        language=getattr(cfg, "language", None),
        group_by=group_by,
        sort_by=sort_by,
        explain=explain,
        first_run=is_first_run,
    )
    if show_suppressed and analysis.suppressed_count:  # type: ignore[union-attr, attr-defined]
        effective_console.print(
            f"[dim italic]{analysis.suppressed_count} finding(s) suppressed "  # type: ignore[union-attr, attr-defined]
            f"via drift:ignore comments.[/dim italic]"
        )
    if output_format == "rich":
        from drift.output.rich_output import render_recommendations
        from drift.recommendations import generate_recommendations

        recs = generate_recommendations(analysis.findings)  # type: ignore[union-attr, attr-defined]
        recs = _refine_recommendations_with_are(recs, analysis, cfg, repo)  # type: ignore[assignment, arg-type]
        if recs:
            render_recommendations(recs, effective_console)

    if output_format == "rich":
        from drift.calibration.feedback import resolve_feedback_paths
        from drift.output.rich_output import render_feedback_calibration_hint

        _feedback_path, _, _ = resolve_feedback_paths(repo, cfg)
        render_feedback_calibration_hint(
            analysis,  # type: ignore[arg-type]
            _feedback_path,
            effective_console,
        )


def _emit_intent_status(analysis: object, repo: Path, intent: bool) -> None:
    """Print intent validation status if --intent is requested."""
    if not intent:
        return
    from drift.intent._matcher import match_findings_to_contracts
    from drift.intent._status import format_intent_status
    from drift.intent._store import load_contracts

    contracts = load_contracts(repo)
    if not contracts:
        return
    statuses = match_findings_to_contracts(analysis.findings, contracts)  # type: ignore[union-attr, attr-defined]
    intent_lines = format_intent_status(statuses)
    if intent_lines:
        click.echo("")
        click.echo("Intent-Status:")
        for line in intent_lines:
            click.echo(f"  {line}")
        click.echo("")


def _refine_recommendations_with_are(
    recs: list[object],
    analysis: object,
    cfg: object,
    repo: Path,
) -> list[object]:
    """Apply Adaptive Recommendation Engine calibration if enabled in config."""
    if not cfg.recommendations.enabled or not recs:  # type: ignore[union-attr, attr-defined]
        return recs
    from drift.calibration.recommendation_calibrator import load_calibration
    from drift.outcome_tracker import Outcome, OutcomeTracker, compute_fingerprint
    from drift.recommendation_refiner import refine
    from drift.reward_chain import compute_reward

    repo_root = Path(repo)
    outcome_path = repo_root / cfg.recommendations.outcome_path  # type: ignore[union-attr, attr-defined]
    cal_path = repo_root / cfg.recommendations.calibration_path  # type: ignore[union-attr, attr-defined]

    tracker = OutcomeTracker(outcome_path)
    for finding in analysis.findings:  # type: ignore[union-attr, attr-defined]
        tracker.record(finding)
    current_fps = {compute_fingerprint(f) for f in analysis.findings}  # type: ignore[union-attr, attr-defined]
    tracker.resolve(current_fps)
    tracker.archive(max_age_days=cfg.recommendations.archive_after_days)  # type: ignore[union-attr, attr-defined]

    outcomes = tracker.load()
    outcome_by_fp: dict[str, Outcome] = {o.fingerprint: o for o in outcomes}
    effort_map = load_calibration(cal_path)
    refined_recs: list[object] = []
    for rec in recs:
        related = rec.related_findings or []  # type: ignore[union-attr, attr-defined]
        primary_finding = related[0] if related else None
        if primary_finding is None:
            refined_recs.append(rec)
            continue
        fp = compute_fingerprint(primary_finding)
        outcome = outcome_by_fp.get(fp)
        if effort_map.get(primary_finding.signal_type):
            rec.effort = effort_map[primary_finding.signal_type]  # type: ignore[union-attr, attr-defined]
        reward = compute_reward(
            outcome,
            rec,
            primary_finding,
            all_outcomes=outcomes,
            calibrated_effort=effort_map.get(primary_finding.signal_type),
        )  # type: ignore[arg-type]
        refined_recs.append(refine(rec, primary_finding, reward))  # type: ignore[arg-type]
    return refined_recs  # type: ignore[return-value]


def _run_interactive_review(
    analysis: object,
    max_findings: int,
    output_format: str,
    quiet: bool,
    review_mode: bool,
    repo: Path,
    cfg: object,
    effective_console: Console,
) -> None:
    """Run interactive feedback review if --review is requested."""
    if not (review_mode and output_format == "rich" and not quiet):
        return
    from drift.calibration.feedback import resolve_feedback_paths
    from drift.output.interactive_review import review_findings

    feedback_path, _, _ = resolve_feedback_paths(repo, cfg)
    review_findings(
        analysis.findings[:max_findings],  # type: ignore[index, attr-defined]
        feedback_path,
        effective_console,
        repo_root=repo,
    )


def _maybe_save_analysis_baseline(
    analysis: object,
    save_baseline_path: Path | None,
    effective_console: Console,
    ok_marker: str,
) -> None:
    """Save findings as a baseline file if --save-baseline was requested."""
    if save_baseline_path is None:
        return
    from drift.baseline import save_baseline as _save_bl

    _save_bl(analysis, save_baseline_path)  # type: ignore[arg-type]
    effective_console.print(
        f"[bold green]{ok_marker} Baseline saved:[/bold green] {save_baseline_path} "
        f"({len(analysis.findings)} findings)",  # type: ignore[arg-type, attr-defined]
    )
    effective_console.print(
        "  [dim]Next step: [bold]drift trend[/bold] "
        "\u2014 shows score evolution over time[/dim]"
    )


def _apply_analysis_severity_gate(
    analysis: object,
    fail_on: str | None,
    cfg: object,
    exit_zero: bool,
    quiet: bool,
    fail_marker: str,
    ok_marker: str,
    effective_console: Console,
) -> None:
    """Apply the severity gate and sys.exit if findings exceed the threshold."""
    threshold = fail_on or cfg.severity_gate()  # type: ignore[union-attr, attr-defined]
    if not threshold or threshold == "none":
        return
    from drift.scoring.engine import severity_gate_pass

    if not severity_gate_pass(analysis.findings, threshold):  # type: ignore[union-attr, attr-defined]
        if not quiet:
            effective_console.print(
                f"\n[bold red]{fail_marker} Drift check failed:[/bold red] "
                f"findings at or above '{threshold}' severity.",
            )
        if not exit_zero:
            sys.exit(EXIT_FINDINGS_ABOVE_THRESHOLD)
    elif not quiet:
        effective_console.print(
            f"\n[bold green]{ok_marker} Drift check passed[/bold green] "
            f"(threshold: {threshold}).",
        )


@click.command()
@click.argument(
    "repo_arg",
    default=None,
    required=False,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    metavar="[REPO]",
)
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option(
    "--path",
    "--target-path",
    "-p",
    default=None,
    help="Restrict analysis to a subdirectory.",
)
@click.option("--since", "-s", default=90, type=int, help="Days of git history to analyze.")
@click.option(
    "--output-format",
    "--format",
    "-f",
    "output_format",
    type=click.Choice(
        [
            "rich",
            "json",
            "sarif",
            "csv",
            "markdown",
            "agent-tasks",
            "github",
            "junit",
            "llm",
            "pr-comment",
        ],
    ),
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
    "--exclude-signals",
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
    "--worker-strategy",
    type=click.Choice(["fixed", "auto"]),
    default=None,
    help="Worker resolution strategy. fixed uses CPU fallback, auto enables conservative tuning.",
)
@click.option(
    "--load-profile",
    type=click.Choice(["conservative"]),
    default=None,
    help="Auto-tuning load profile (currently conservative only).",
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
    "--response-detail",
    "response_detail",
    type=click.Choice(["concise", "detailed"]),
    default="detailed",
    help=(
        "JSON detail level: concise uses slim finding objects, detailed "
        "includes full finding payloads."
    ),
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
@click.option(
    "--review",
    "review_mode",
    is_flag=True,
    default=False,
    help="Interactively triage each finding as true/false positive after analysis (requires TTY).",
)
@click.option(
    "--no-cache",
    "no_cache",
    is_flag=True,
    default=False,
    help="Bypass the parse and signal cache for this run (reads and writes are both skipped).",
)
@click.option(
    "--audience",
    "audience",
    type=click.Choice(["developer", "plain"]),
    default=None,
    help="Target audience: developer (technical, default) or plain (non-programmer-friendly).",
)
@click.option(
    "--language",
    "--lang",
    "language_override",
    default=None,
    help="Language for plain-audience messages (ISO 639-1, e.g. de, en). Overrides config.",
)
@click.option(
    "--intent",
    is_flag=True,
    default=False,
    help="Validate findings against intent contracts from .drift-intent.yaml.",
)
def analyze(
    repo_arg: Path | None,
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
    worker_strategy: str | None,
    load_profile: str | None,
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
    response_detail: str,
    no_color: bool,
    progress_format: str,
    explain: bool,
    group_by: str | None,
    no_first_run: bool,
    review_mode: bool,
    no_cache: bool,
    audience: str | None,
    language_override: str | None,
    intent: bool,
) -> None:
    """Detailed drift analysis — produces comprehensive findings for investigation and triage.

    For CI-compatible exit codes on diffs, use ``check``.

    \b
    Common patterns:
      drift analyze                         # rich output, current directory
      drift analyze --format json           # machine-readable, agent-friendly
      drift analyze --select PFS,AVS        # only specific signals
      drift analyze --fail-on high          # exit 1 when high/critical findings exist
      drift analyze --quiet                 # score + count only (fast CI check)

    \b
    Progress modes (--progress):
      auto    Rich bar in terminal, auto-switches to json when output is piped (default)
      json    JSON-lines on stderr — useful for CI log parsing: --progress json
      none    Silent — no progress output at all
    """
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        TextColumn,
        TimeRemainingColumn,
    )

    from drift.analyzer import analyze_repo
    from drift.api_helpers import build_drift_score_scope, signal_scope_label
    from drift.commands._shared import (
        apply_baseline_filtering,
        build_effective_console,
        configure_machine_output_console,
    )
    from drift.config import DriftConfig

    # Positional [REPO] argument takes precedence over --repo option
    if repo_arg is not None:
        repo = repo_arg

    if json_shortcut:
        output_format = "json"

    # For machine-readable formats, redirect the shared console to stderr
    # so stray console.print() calls never pollute the JSON payload.  (#75, #77)
    configure_machine_output_console(output_format)

    # Apply --no-color: create a color-disabled console for rich output
    effective_console = build_effective_console(no_color)
    ascii_only = bool(getattr(effective_console, "_drift_ascii_only", False))
    ok_marker = "OK" if ascii_only else "✓"
    fail_marker = "X" if ascii_only else "✗"

    cfg = DriftConfig.load(repo, config)
    _apply_analysis_cfg_overrides(
        cfg, worker_strategy, load_profile, no_embeddings, embedding_model
    )
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
    # Auto-suppress Rich progress for machine-readable formats to avoid
    # stderr noise that triggers NativeCommandError in PowerShell (#118).
    use_json_progress, use_rich_progress, use_no_progress = _resolve_progress_mode(
        progress_format, output_format, quiet
    )

    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        console=progress_console,
    )
    effective_callback, _progress_state = _build_progress_callback(
        use_json_progress, use_no_progress, progress
    )

    progress_context = nullcontext() if not use_rich_progress else progress
    with progress_context:
        analysis = analyze_repo(
            repo,
            cfg,
            since_days=since,
            target_path=path,
            on_progress=effective_callback,  # type: ignore[arg-type]
            workers=workers,
            active_signals=active_signals,
            no_cache=no_cache,
        )
        if use_rich_progress and _progress_state[0] is not None:
            progress.update(_progress_state[0], completed=_progress_state[1])  # type: ignore[arg-type]

    # Baseline filtering: remove known findings if --baseline is provided
    apply_baseline_filtering(analysis, cfg, baseline_file)

    # Translation layer: enrich findings with plain-language messages
    _maybe_enrich_plain_messages(analysis, audience, language_override, cfg)

    # Intent-aware validation: match findings against intent contracts
    _emit_intent_status(analysis, repo, intent)

    # Auto-save snapshot for `drift diff --auto` (silent on failure)
    from drift.commands._last_scan import save_last_scan

    save_last_scan(analysis, repo, getattr(cfg, "cache_dir", ".drift-cache"))

    if quiet:
        sev = analysis.severity.value.upper()
        n = len(analysis.findings)
        grade = analysis.grade[0]
        click.echo(
            f"score: {analysis.drift_score:.3f}  grade: {grade}  severity: {sev}  findings: {n}"
        )
    else:
        _render_analysis_details(
            analysis, output_format, compact_json, drift_score_scope, output_file,
            effective_console, max_findings, no_code, response_detail, cfg, group_by,
            sort_by, explain, no_first_run, repo, show_suppressed,
        )

    # Interactive feedback review (--review, TTY-only)
    _run_interactive_review(
        analysis, max_findings, output_format, quiet, review_mode, repo, cfg, effective_console
    )

    # Save baseline if requested (--save-baseline)
    _maybe_save_analysis_baseline(analysis, save_baseline_path, effective_console, ok_marker)

    # Severity gate (opt-in via --fail-on)
    _apply_analysis_severity_gate(
        analysis, fail_on, cfg, exit_zero, quiet, fail_marker, ok_marker, effective_console
    )

