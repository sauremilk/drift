"""drift status — traffic-light project health indicator.

Shows a simple red/yellow/green status with everyday-language explanations
and copy-paste-ready prompts for AI assistants.  Designed for users
without software-architecture expertise (Persona A / Vibe-Coder).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from drift.commands import console


@click.command("status", short_help="Zeigt den Projektzustand als Ampel an.")
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
    """Zeigt den Projektzustand als Ampel (grün/gelb/rot) mit Alltagssprache.

    Liefert für jedes Finding einen kopierbaren Prompt, den du direkt
    an deinen KI-Assistenten weitergeben kannst.

    Exit-Code ist immer 0 (PRD NF-08).
    """
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig
    from drift.output.guided_output import (
        can_continue,
        determine_status,
        emoji_for_status,
        headline_for_status,
        is_calibrated,
        plain_text_for_signal,
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

    # --- Run analysis (reuses existing engine) ---
    analysis = analyze_repo(
        repo,
        cfg,
        since_days=since,
        target_path=path,
    )

    # --- Compute traffic light ---
    light = determine_status(analysis, thresholds)
    headline = headline_for_status(light)
    emoji = emoji_for_status(light)
    continue_flag = can_continue(light)

    # --- Top findings by severity ---
    sorted_findings = sorted(
        analysis.findings,
        key=lambda f: (-_severity_rank(f.severity.value), -f.score),
    )
    top_findings = sorted_findings[:top]

    # --- JSON output ---
    if output_json:
        payload = _build_json_payload(
            light, headline, continue_flag, top_findings, analysis, thresholds
        )
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        sys.exit(0)

    # --- Rich terminal output ---
    console.print()
    console.print(f"  {emoji}  {headline}", style="bold")
    console.print()

    if not is_calibrated(thresholds):
        console.print(
            "  [dim]Hinweis: Kein kalibriertes Profil aktiv. "
            "Führe [bold]drift setup[/bold] aus für bessere Ergebnisse.[/dim]"
        )
        console.print()

    if not top_findings:
        console.print("  Keine Auffälligkeiten gefunden.", style="green")
    else:
        console.print(f"  Top-{len(top_findings)} Auffälligkeiten:", style="bold")
        console.print()
        for i, f in enumerate(top_findings, 1):
            sev = severity_label(f.severity.value)
            plain = plain_text_for_signal(f.signal_type)
            prompt = generate_agent_prompt(f, analysis)
            console.print(f"  {i}. [{_severity_color(f.severity.value)}]{sev}[/]: {plain}")
            console.print("     [dim]Prompt:[/dim]")
            console.print(f"     {prompt}")
            console.print()

    # --- Separator + can_continue ---
    if continue_flag:
        console.print("  [green]Du kannst weiterarbeiten.[/green]")
    else:
        console.print(
            "  [yellow]Tipp: Kopiere einen der Prompts oben "
            "und gib ihn deinem KI-Assistenten.[/yellow]"
        )
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
    top_findings: list[object],
    analysis: object,
    thresholds: dict[str, float] | None,
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
        "top_findings": findings_list,
    }
