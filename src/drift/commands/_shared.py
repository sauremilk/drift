"""Shared analysis-pipeline helpers used by both analyze and check commands."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from drift.commands import console, make_console
from drift.commands._io import _emit_machine_output


def recompute_analysis_summary(analysis, cfg) -> None:
    """Recalculate drift score and module scores after filtering findings."""
    from drift.scoring.engine import (
        composite_score,
        compute_module_scores,
        compute_signal_scores,
    )

    signal_scores = compute_signal_scores(analysis.findings)
    analysis.drift_score = composite_score(signal_scores, cfg.weights)
    analysis.module_scores = compute_module_scores(analysis.findings, cfg.weights)


def configure_machine_output_console(output_format: str) -> None:
    """Route the shared console to stderr for machine-readable formats."""
    if output_format != "rich":
        import drift.commands as _cmds

        _cmds.console = make_console(stderr=True)


def build_effective_console(no_color: bool) -> Console:
    """Create a console that respects --no-color and ASCII fallback needs."""
    return make_console(no_color=no_color) if no_color else console


def apply_signal_filtering(
    analysis,
    cfg,
    select_signals: str | None,
    ignore_signals: str | None,
) -> None:
    """Remove findings for inactive signals and recompute scores."""
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
    recompute_analysis_summary(analysis, cfg)


def apply_baseline_filtering(analysis, cfg, baseline_file: Path | None) -> None:
    """Subtract known findings from a baseline fingerprint file."""
    if baseline_file is None:
        return

    from drift.baseline import baseline_diff, load_baseline

    fingerprints = load_baseline(baseline_file)
    new, known = baseline_diff(analysis.findings, fingerprints)
    analysis.findings = new
    analysis.suppressed_count += len(known)
    analysis.baseline_new_count = len(new)
    analysis.baseline_matched_count = len(known)
    recompute_analysis_summary(analysis, cfg)


def render_or_emit_output(
    analysis,
    output_format: str,
    compact_json: bool,
    drift_score_scope: str,
    output_file: Path | None,
    effective_console: Console,
    max_findings: int,
    no_code: bool,
    *,
    response_detail: str = "concise",
    language: str | None = None,
    group_by: str | None = None,
    sort_by: str = "impact",
    explain: bool = False,
    first_run: bool = False,
) -> None:
    """Route analysis output to the appropriate format renderer."""
    if output_format == "json":
        from drift.output.json_output import analysis_to_json

        json_text = analysis_to_json(
            analysis,
            compact=compact_json,
            response_detail=response_detail,
            drift_score_scope=drift_score_scope,
            language=language,
            group_by=group_by,
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

    if output_format == "markdown":
        from drift.output.markdown_report import analysis_to_markdown

        md_text = analysis_to_markdown(
            analysis,
            max_findings=5 if compact_json else max_findings,
            include_modules=not compact_json,
            include_signal_coverage=not compact_json,
        )
        _emit_machine_output(md_text, output_file)
        return

    if output_format == "pr-comment":
        from drift.output.pr_comment import analysis_to_pr_comment

        pr_text = analysis_to_pr_comment(analysis, max_findings=5)
        _emit_machine_output(pr_text, output_file)
        return

    if output_format == "github":
        from drift.output.github_format import findings_to_github_annotations

        gh_text = findings_to_github_annotations(analysis)
        _emit_machine_output(gh_text, output_file)
        return

    if output_format == "junit":
        import warnings

        warnings.warn(
            "--format junit is deprecated and will be removed in v3.0. "
            "Use --format sarif for CI integrations.",
            DeprecationWarning,
            stacklevel=1,
        )
        click.echo(
            "Warning: --format junit is deprecated (use --format sarif instead).",
            err=True,
        )
        from drift.output.junit_output import analysis_to_junit

        junit_text = analysis_to_junit(analysis)
        _emit_machine_output(junit_text, output_file)
        return

    if output_format == "llm":
        import warnings

        warnings.warn(
            "--format llm is deprecated and will be removed in v3.0. "
            "Use the MCP server (drift mcp) for LLM-optimized output.",
            DeprecationWarning,
            stacklevel=1,
        )
        click.echo(
            "Warning: --format llm is deprecated (use drift mcp for LLM workflows).",
            err=True,
        )
        from drift.output.llm_output import analysis_to_llm

        llm_text = analysis_to_llm(analysis)
        _emit_machine_output(llm_text, output_file)
        return

    # Default: rich terminal output
    from drift.output.rich_output import render_full_report

    render_full_report(
        analysis,
        effective_console,
        sort_by=sort_by,
        max_findings=max_findings,
        show_code=not no_code,
        language=language,
        explain=explain,
        group_by=group_by,
        first_run=first_run,
    )
