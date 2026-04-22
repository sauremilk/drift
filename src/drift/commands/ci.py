"""drift ci — zero-config CI command with auto-baseline and environment detection."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import click
from rich.console import Console

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
    "--fail-on",
    type=click.Choice(["critical", "high", "medium", "low", "none"]),
    default=None,
    help="Exit non-zero if any finding at or above this severity.",
)
@click.option(
    "--output-format",
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json", "sarif", "csv", "junit", "github", "llm"]),
    default=None,
    help="Output format (default: auto-detect based on CI provider).",
)
@click.option(
    "--baseline",
    "baseline_file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Baseline file for filtering known findings.",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(path_type=Path),
    default=None,
    help="Write output to a file instead of stdout.",
)
@click.option(
    "--exit-zero",
    is_flag=True,
    default=False,
    help="Always exit with code 0.",
)
@click.option(
    "--diff-ref",
    default=None,
    help="Override auto-detected base ref for diff analysis.",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option("--since", "-s", default=90, type=int, help="Days of git history.")
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Minimal output.",
)
@click.option(
    "--trend-gate/--no-trend-gate",
    "trend_gate_override",
    default=None,
    help="Override config trend-gate enabled setting.",
)
def ci(
    repo: Path,
    fail_on: str | None,
    output_format: str | None,
    baseline_file: Path | None,
    output_file: Path | None,
    exit_zero: bool,
    diff_ref: str | None,
    config: Path | None,
    since: int,
    quiet: bool,
    trend_gate_override: bool | None,
) -> None:
    """Zero-config CI analysis with auto-environment detection.

    Detects GitHub Actions, GitLab CI, CircleCI, Azure Pipelines and
    automatically selects diff-ref, output format, and exit-code behavior.

    \b
    In a pull request:  analyzes only changed files (diff mode)
    On push to main:    analyzes the full repository
    """
    from drift.analyzer import analyze_diff, analyze_repo
    from drift.ci_detect import CIContext, detect_ci_environment
    from drift.config import DriftConfig

    ci_ctx: CIContext | None = detect_ci_environment()

    # Auto-select format: sarif for GitHub Actions, json for others, rich for local
    if output_format is None:
        if ci_ctx is not None and ci_ctx.provider == "github-actions":
            output_format = "sarif"
        elif ci_ctx is not None:
            output_format = "json"
        else:
            output_format = "rich"

    # Redirect console for machine-readable formats
    if output_format != "rich":
        import drift.commands as _cmds

        _cmds.console = Console(stderr=True)

    cfg = DriftConfig.load(repo, config)
    threshold = fail_on or cfg.severity_gate()

    # Determine diff ref: explicit > CI-detected > full analysis
    effective_ref = diff_ref or (ci_ctx.base_ref if ci_ctx and ci_ctx.is_pr else None)

    if effective_ref:
        # PR / diff mode
        if not quiet:
            click.echo(
                f"drift ci: diff mode against {effective_ref} "
                f"(provider: {ci_ctx.provider if ci_ctx else 'local'})",
                err=True,
            )
        analysis = analyze_diff(repo, cfg, diff_ref=effective_ref, since_days=since)
    else:
        # Full analysis (push on default branch)
        if not quiet:
            click.echo(
                f"drift ci: full analysis "
                f"(provider: {ci_ctx.provider if ci_ctx else 'local'})",
                err=True,
            )
        analysis = analyze_repo(repo, cfg, since_days=since)

    # Baseline filtering
    if baseline_file is not None:
        import json as _json

        from drift.baseline import baseline_diff, load_baseline

        try:
            fingerprints = load_baseline(baseline_file)
        except (OSError, ValueError, _json.JSONDecodeError) as exc:
            click.echo(
                f"drift ci: Baseline file is corrupt — delete it and re-save: "
                f"drift baseline save  ({exc})",
                err=True,
            )
            sys.exit(1)
        new, _known = baseline_diff(analysis.findings, fingerprints)
        analysis.findings = new

    # Emit output
    _emit_output(analysis, output_format, output_file, cfg)

    # Trend gate
    if _trend_gate_enabled(cfg, trend_gate_override):
        _enforce_trend_gate(
            repo=repo, cfg=cfg, output_format=output_format, quiet=quiet, exit_zero=exit_zero
        )

    # Severity gate
    from drift.scoring.engine import severity_gate_pass

    if not severity_gate_pass(analysis.findings, threshold):
        if not quiet:
            click.echo(
                f"drift ci: FAILED — findings at or above '{threshold}' severity",
                err=True,
            )
        if not exit_zero:
            sys.exit(EXIT_FINDINGS_ABOVE_THRESHOLD)
    elif not quiet:
        click.echo(
            f"drift ci: PASSED (threshold: {threshold})",
            err=True,
        )


def _trend_gate_enabled(cfg, override: bool | None) -> bool:
    if override is not None:
        return override
    return bool(cfg.gate.trend.enabled)


def _enforce_trend_gate(
    *,
    repo: Path,
    cfg,
    output_format: str,
    quiet: bool,
    exit_zero: bool,
) -> None:
    from drift.quality_gate import evaluate_trend_gate
    from drift.trend_history import load_history, snapshot_scope

    gate_cfg = cfg.gate.trend
    history_file = repo / cfg.cache_dir / "history.json"
    snapshots = [s for s in load_history(history_file) if snapshot_scope(s) == "diff"]
    decision = evaluate_trend_gate(
        snapshots=snapshots,
        window_commits=gate_cfg.window_commits,
        delta_threshold=gate_cfg.delta_threshold,
        require_remediation_activity=gate_cfg.require_remediation_activity,
    )
    if decision.blocked:
        if not quiet:
            click.echo(
                f"drift ci: TREND GATE BLOCKED — {decision.reason}",
                err=True,
            )
        if not exit_zero:
            sys.exit(EXIT_FINDINGS_ABOVE_THRESHOLD)


def _emit_output(
    analysis,
    output_format: str,
    output_file: Path | None,
    cfg,
) -> None:
    """Dispatch to the appropriate output formatter."""
    if output_format == "json":
        from drift.output.json_output import analysis_to_json

        _emit_machine_output(analysis_to_json(analysis), output_file)
    elif output_format == "sarif":
        from drift.output.json_output import findings_to_sarif

        _emit_machine_output(findings_to_sarif(analysis), output_file)
    elif output_format == "csv":
        from drift.output.csv_output import analysis_to_csv

        _emit_machine_output(analysis_to_csv(analysis), output_file)
    elif output_format == "junit":
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

        _emit_machine_output(analysis_to_junit(analysis), output_file)
    elif output_format == "github":
        from drift.output.github_format import findings_to_github_annotations

        _emit_machine_output(findings_to_github_annotations(analysis), output_file)
    elif output_format == "llm":
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

        _emit_machine_output(analysis_to_llm(analysis), output_file)
    else:
        from drift.output.rich_output import render_full_report

        render_full_report(analysis, Console())
