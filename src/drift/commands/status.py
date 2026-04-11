"""drift status — traffic-light project health indicator.

Shows a simple red/yellow/green status with everyday-language explanations
and copy-paste-ready prompts for AI assistants.  Designed for users
without software-architecture expertise (Persona A / Vibe-Coder).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

import click

from drift.commands import console


@click.command("status", short_help="Show repository health as a traffic-light summary.")
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
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option(
    "--profile",
    default="vibe-coding",
    help="Profile for guided thresholds (default: vibe-coding).",
)
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON.")
@click.option("--top", default=3, type=int, help="Number of top findings to show.")
def status(
    repo: Path,
    path: str | None,
    since: int,
    config: Path | None,
    profile: str,
    output_json: bool,
    top: int,
) -> None:
    """Show repository health as a traffic-light (green/yellow/red).

    Uses plain-language explanations and copy-paste-ready AI prompts for each finding.

    For each finding, outputs a copy-paste-ready prompt for your AI assistant.

    Exit code is always 0 (PRD NF-08).
    """
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig
    from drift.finding_rendering import build_first_run_summary, select_priority_findings
    from drift.output.guided_output import (
        can_continue,
        determine_status,
        emoji_for_status,
        headline_for_status,
        is_calibrated,
        plain_text_for_signal,
        profile_score_context,
        severity_label,
    )
    from drift.output.prompt_generator import generate_agent_prompt
    from drift.profiles import get_profile

    # --- Load config + profile ---
    cfg = DriftConfig.load(repo, config)

    try:
        prof = get_profile(profile)
    except KeyError:
        prof = get_profile("vibe-coding")

    thresholds = prof.guided_thresholds if prof.guided_thresholds else None
    language = cfg.language or prof.output_language or "en"

    # --- Run analysis (reuses existing engine) ---
    analysis = analyze_repo(
        repo,
        cfg,
        since_days=since,
        target_path=path,
    )

    # --- Compute traffic light ---
    light = determine_status(analysis, thresholds)
    headline = headline_for_status(light, language)
    emoji = emoji_for_status(light)
    continue_flag = can_continue(light)

    # --- Top findings by severity ---
    top_findings = select_priority_findings(analysis, max_items=top)
    first_run = build_first_run_summary(analysis, max_items=top, language=language)

    # --- JSON output ---
    if output_json:
        payload = _build_json_payload(
            light,
            headline,
            continue_flag,
            top_findings,
            analysis,
            thresholds,
            first_run,
        )
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        sys.exit(0)

    # --- Rich terminal output ---
    console.print()
    console.print(f"  {emoji}  {headline}", style="bold")
    score_ctx = profile_score_context(profile, language)
    score_line = (
        f"  Score: [bold]{analysis.drift_score:.2f}[/bold]"
        + (f"  [dim]{score_ctx}[/dim]" if score_ctx else "")
    )
    console.print(score_line)
    console.print(f"  {first_run['why_this_matters']}", style="dim")
    console.print()

    if not is_calibrated(thresholds):
        console.print(
            "  [dim]Note: No calibrated profile active. "
            "Run [bold]drift setup[/bold] for better results.[/dim]"
        )
        console.print()

    if not top_findings:
        console.print("  No issues found.", style="green")
    else:
        console.print(f"  Top {len(top_findings)} issues:", style="bold")
        console.print()
        for i, f in enumerate(top_findings, 1):
            sev = severity_label(f.severity.value, language)
            plain = plain_text_for_signal(f.signal_type, language)
            prompt = generate_agent_prompt(f, analysis)
            console.print(f"  {i}. [{_severity_color(f.severity.value)}]{sev}[/]: {plain}")
            # Show file:line reference as a separate navigation hint (PRD F-06: not in prompt)
            fp = getattr(f, "file_path", None)
            sl = getattr(f, "start_line", None)
            if fp is not None and sl is not None:
                console.print(f"     [dim]Location:[/dim] {fp}:{sl}")
            elif fp is not None:
                console.print(f"     [dim]Location:[/dim] {fp}")
            console.print("     [dim]Prompt:[/dim]")
            console.print(f"     {prompt}")
            console.print()
    # --- repo-context hint (only when findings exist, not spammy) ---
    if top_findings:
        # Map signal_type to abbreviation for the hint
        from drift.finding_rendering import signal_abbrev
        abbr = signal_abbrev(getattr(top_findings[0], "signal_type", ""))
        console.print(
            f"  [dim]Run [bold]drift explain {abbr} --repo-context[/bold] "
            "to see examples from your own codebase.[/dim]"
        )
        console.print()
    # --- Separator + can_continue ---
    if continue_flag:
        console.print("  [green]Everything looks good — proceed with confidence.[/green]")
    else:
        console.print(
            "  [yellow]Tip: Copy one of the prompts above "
            "and paste it into your AI assistant.[/yellow]"
        )
    console.print(f"  [bold]Next step:[/bold] {first_run['next_step']}")
    console.print()

    sys.exit(0)


# ---------------------------------------------------------------------------
# Helpers (internal)
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[str, int] = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}


def _severity_rank(severity: str) -> int:
    return _SEVERITY_ORDER.get(severity, 0)


def _severity_color(severity: str) -> str:
    return {
        "critical": "bold red",
        "high": "red",
        "medium": "yellow",
        "low": "cyan",
        "info": "dim",
    }.get(severity, "")


def _build_json_payload(
    light: object,
    headline: str,
    continue_flag: bool,
    top_findings: Sequence[object],
    analysis: object,
    thresholds: dict[str, float] | None,
    first_run: dict[str, object],
) -> dict[str, object]:
    """Build the JSON payload for ``drift status --json``."""
    from drift.finding_rendering import _finding_guided
    from drift.output.guided_output import is_calibrated

    findings_list = []
    for i, f in enumerate(top_findings, 1):
        findings_list.append(_finding_guided(f, rank=i))

    return {
        "status": light.value if hasattr(light, "value") else str(light),
        "headline": headline,
        "can_continue": continue_flag,
        "calibrated": is_calibrated(thresholds),
        "findings_count": len(getattr(analysis, "findings", [])),
        "why_this_matters": first_run.get("why_this_matters"),
        "next_step": first_run.get("next_step"),
        "top_findings": findings_list,
    }
