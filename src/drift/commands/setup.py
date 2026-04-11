"""drift setup — interactive guided onboarding for first-time users.

Asks 2–3 simple questions (no technical jargon) and generates
a drift.yaml tuned to the user's project type.  Replaces the static
``drift start`` for Persona A (Vibe-Coder) users.
"""

from __future__ import annotations

import json
import locale
import sys
from pathlib import Path
from typing import cast

import click
import yaml  # type: ignore[import-untyped]

from drift.commands import console

# ---------------------------------------------------------------------------
# Locale detection
# ---------------------------------------------------------------------------


def _detect_language() -> str:
    """Return 'de' when the system locale is German, else 'en'."""
    try:
        loc = locale.getlocale()[0] or ""
        if loc.startswith("de"):
            return "de"
    except Exception:  # noqa: BLE001
        pass
    return "en"


# ---------------------------------------------------------------------------
# Question definitions — German and English variants
# ---------------------------------------------------------------------------

_PROJECT_TYPES_DE: dict[str, str] = {
    "1": "Web-App (Frontend + Backend)",
    "2": "API / Backend-Service",
    "3": "CLI-Tool oder Library",
    "4": "Data Science / ML",
    "5": "Monorepo / Mehrere Projekte",
}

_PROJECT_TYPES_EN: dict[str, str] = {
    "1": "Web app (frontend + backend)",
    "2": "API / backend service",
    "3": "CLI tool or library",
    "4": "Data science / ML",
    "5": "Monorepo / multiple projects",
}

_PROJECT_TYPES = _PROJECT_TYPES_DE  # backward-compat alias

_AI_USAGE_DE: dict[str, str] = {
    "1": "Ja, regelmäßig (z.\u202fB. Copilot, Cursor, ChatGPT)",
    "2": "Manchmal",
    "3": "Nein, alles von Hand",
}

_AI_USAGE_EN: dict[str, str] = {
    "1": "Yes, regularly (e.g. Copilot, Cursor, ChatGPT)",
    "2": "Sometimes",
    "3": "No, I write everything myself",
}

_AI_USAGE = _AI_USAGE_DE  # backward-compat alias


def _ask_project_type(lang: str = "en") -> str:
    """Ask which project type the user has."""
    types = _PROJECT_TYPES_DE if lang.startswith("de") else _PROJECT_TYPES_EN
    q = (
        "  [bold]Was für ein Projekt ist das?[/bold]"
        if lang.startswith("de")
        else "  [bold]What type of project is this?[/bold]"
    )
    prompt_label = "  Deine Wahl" if lang.startswith("de") else "  Your choice"
    console.print(q)
    console.print()
    for key, label in types.items():
        console.print(f"    {key}) {label}")
    console.print()
    choice = click.prompt(prompt_label, type=click.Choice(list(types)), default="1")
    return cast(str, choice)


def _ask_ai_usage(lang: str = "en") -> str:
    """Ask how much AI is used for coding."""
    usage = _AI_USAGE_DE if lang.startswith("de") else _AI_USAGE_EN
    q = (
        "  [bold]Nutzt du KI beim Coden?[/bold]"
        if lang.startswith("de")
        else "  [bold]Do you use AI for coding?[/bold]"
    )
    prompt_label = "  Deine Wahl" if lang.startswith("de") else "  Your choice"
    console.print()
    console.print(q)
    console.print()
    for key, label in usage.items():
        console.print(f"    {key}) {label}")
    console.print()
    choice = click.prompt(prompt_label, type=click.Choice(list(usage)), default="1")
    return cast(str, choice)


def _ask_strictness(lang: str = "en") -> str:
    """Ask how strict the checks should be."""
    prompt_label = "  Deine Wahl" if lang.startswith("de") else "  Your choice"
    console.print()
    if lang.startswith("de"):
        console.print("  [bold]Wie streng sollen die Prüfungen sein?[/bold]")
        console.print()
        console.print("    1) Entspannt \u2014 nur wirklich wichtige Probleme anzeigen")
        console.print("    2) Ausgewogen \u2014 guter Mittelweg")
        console.print("    3) Streng \u2014 alles anzeigen")
    else:
        console.print("  [bold]How strict should the checks be?[/bold]")
        console.print()
        console.print("    1) Relaxed \u2014 only show the most important problems")
        console.print("    2) Balanced \u2014 a good middle ground")
        console.print("    3) Strict \u2014 show everything")
    console.print()
    choice = click.prompt(prompt_label, type=click.Choice(["1", "2", "3"]), default="1")
    return cast(str, choice)


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


@click.command("setup", short_help="Interactive guided setup for first-time users.")
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
    """Set up drift for your project in under a minute.

    Asks 2\u20133 simple questions and generates a drift.yaml tailored to your
    project. No architectural expertise required.

    Use --non-interactive for defaults without questions.
    """
    repo = repo.resolve()
    config_path = repo / "drift.yaml"
    lang = _detect_language()

    if config_path.exists() and not output_json:
        console.print()
        if lang.startswith("de"):
            console.print(
                f"  [yellow]drift.yaml existiert bereits in {repo.name}/.[/yellow]"
            )
            if not click.confirm("  \u00dcberschreiben?", default=False):
                console.print("  [dim]Abgebrochen.[/dim]")
                sys.exit(0)
        else:
            console.print(
                f"  [yellow]drift.yaml already exists in {repo.name}/.[/yellow]"
            )
            if not click.confirm("  Overwrite?", default=False):
                console.print("  [dim]Cancelled.[/dim]")
                sys.exit(0)

    # --- Gather answers ---
    if non_interactive:
        profile_name = "vibe-coding"
    else:
        console.print()
        if lang.startswith("de"):
            console.print("  [bold]drift setup[/bold] \u2014 Konfiguration in 3 Fragen")
        else:
            console.print("  [bold]drift setup[/bold] \u2014 configure in 3 questions")
        console.print("  " + "\u2500" * 45)
        console.print()

        project_type = _ask_project_type(lang)
        ai_usage = _ask_ai_usage(lang)
        strictness = _ask_strictness(lang)
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
    if lang.startswith("de"):
        console.print(f"  [green]\u2713[/green] drift.yaml erstellt (Profil: {profile_name})")
        console.print()
        console.print("  [bold]Nächster Schritt:[/bold]")
        console.print("    drift status")
        console.print()
        console.print("  [dim]Das zeigt dir den aktuellen Zustand deines Projekts.[/dim]")
    else:
        console.print(f"  [green]\u2713[/green] drift.yaml created (profile: {profile_name})")
        console.print()
        console.print("  [bold]Next step:[/bold]")
        console.print("    drift status")
        console.print()
        console.print("  [dim]This shows the current structural health of your project.[/dim]")
    console.print()

    sys.exit(0)
