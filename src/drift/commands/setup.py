"""drift setup — interactive guided onboarding for first-time users.

Asks 2–3 simple questions (no technical jargon) and generates
a drift.yaml tuned to the user's project type.  Replaces the static
``drift start`` for Persona A (Vibe-Coder) users.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml  # type: ignore[import-untyped]

from drift.commands import console

# ---------------------------------------------------------------------------
# Question definitions (German, everyday language)
# ---------------------------------------------------------------------------

_PROJECT_TYPES: dict[str, str] = {
    "1": "Web-App (Frontend + Backend)",
    "2": "API / Backend-Service",
    "3": "CLI-Tool oder Library",
    "4": "Data Science / ML",
    "5": "Monorepo / Mehrere Projekte",
}

_AI_USAGE: dict[str, str] = {
    "1": "Ja, regelmäßig (z.\u202fB. Copilot, Cursor, ChatGPT)",
    "2": "Manchmal",
    "3": "Nein, alles von Hand",
}


def _ask_project_type() -> str:
    """Ask which project type the user has."""
    console.print("  [bold]Was für ein Projekt ist das?[/bold]")
    console.print()
    for key, label in _PROJECT_TYPES.items():
        console.print(f"    {key}) {label}")
    console.print()
    choice = click.prompt("  Deine Wahl", type=click.Choice(list(_PROJECT_TYPES)), default="1")
    return choice


def _ask_ai_usage() -> str:
    """Ask how much AI is used for coding."""
    console.print()
    console.print("  [bold]Nutzt du KI beim Coden?[/bold]")
    console.print()
    for key, label in _AI_USAGE.items():
        console.print(f"    {key}) {label}")
    console.print()
    choice = click.prompt("  Deine Wahl", type=click.Choice(list(_AI_USAGE)), default="1")
    return choice


def _ask_strictness() -> str:
    """Ask how strict the checks should be."""
    console.print()
    console.print("  [bold]Wie streng sollen die Prüfungen sein?[/bold]")
    console.print()
    console.print("    1) Entspannt — nur wirklich wichtige Probleme anzeigen")
    console.print("    2) Ausgewogen — guter Mittelweg")
    console.print("    3) Streng — alles anzeigen")
    console.print()
    choice = click.prompt("  Deine Wahl", type=click.Choice(["1", "2", "3"]), default="1")
    return choice


# ---------------------------------------------------------------------------
# Profile selection logic
# ---------------------------------------------------------------------------


def _derive_profile(project_type: str, ai_usage: str, strictness: str) -> str:
    """Derive the best-fit profile name from user answers."""
    # AI-heavy usage → vibe-coding (optimised for AI debt patterns)
    if ai_usage == "1":
        return "vibe-coding"
    # Strict mode → strict profile
    if strictness == "3":
        return "strict"
    # Default for everything else
    return "default"


def _build_config(profile_name: str) -> dict[str, object]:
    """Build the drift.yaml content dict from a profile."""
    from drift.profiles import get_profile

    prof = get_profile(profile_name)
    cfg: dict[str, object] = {
        "include": ["**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"],
        "exclude": [
            "**/node_modules/**",
            "**/.venv/**",
            "**/dist/**",
            "**/build/**",
        ],
        "weights": prof.weights,
        "thresholds": dict(prof.thresholds),
        "fail_on": prof.fail_on,
        "auto_calibrate": prof.auto_calibrate,
    }
    if prof.output_language:
        cfg["language"] = prof.output_language
    return cfg


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


@click.command("setup", short_help="Interaktives Setup für Erstnutzer.")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help="Skip questions, use vibe-coding defaults.",
)
@click.option("--json", "output_json", is_flag=True, default=False, help="Output config as JSON.")
def setup(
    repo: Path,
    non_interactive: bool,
    output_json: bool,
) -> None:
    """Richtet drift für dein Projekt ein — in unter einer Minute.

    Stellt 2–3 einfache Fragen und erzeugt eine passende drift.yaml.
    Kein Fachwissen nötig.

    Verwende --non-interactive für die Standardkonfiguration ohne Fragen.
    """
    repo = repo.resolve()
    config_path = repo / "drift.yaml"

    if config_path.exists() and not output_json:
        console.print()
        console.print(
            f"  [yellow]drift.yaml existiert bereits in {repo.name}/.[/yellow]"
        )
        if not click.confirm("  Überschreiben?", default=False):
            console.print("  [dim]Abgebrochen.[/dim]")
            sys.exit(0)

    # --- Gather answers ---
    if non_interactive:
        profile_name = "vibe-coding"
    else:
        console.print()
        console.print("  [bold]drift setup[/bold] — Konfiguration in 3 Fragen")
        console.print("  " + "─" * 45)
        console.print()

        project_type = _ask_project_type()
        ai_usage = _ask_ai_usage()
        strictness = _ask_strictness()
        profile_name = _derive_profile(project_type, ai_usage, strictness)

    # --- Build config ---
    cfg = _build_config(profile_name)

    # --- JSON output for agents ---
    if output_json:
        payload = {
            "profile": profile_name,
            "config_path": str(config_path),
            "config": cfg,
        }
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        sys.exit(0)

    # --- Write drift.yaml ---
    yaml_content = (
        f"# drift-Konfiguration — Profil: {profile_name}\n"
        f"# Erstellt durch: drift setup\n"
        f"# Dokumentation: https://drift-analyzer.readthedocs.io/\n\n"
        + yaml.dump(cfg, allow_unicode=True, default_flow_style=False, sort_keys=False)
    )
    config_path.write_text(yaml_content, encoding="utf-8")

    console.print()
    console.print(f"  [green]✓[/green] drift.yaml erstellt (Profil: {profile_name})")
    console.print()
    console.print("  [bold]Nächster Schritt:[/bold]")
    console.print("    drift status")
    console.print()
    console.print("  [dim]Das zeigt dir den aktuellen Zustand deines Projekts.[/dim]")
    console.print()

    sys.exit(0)
