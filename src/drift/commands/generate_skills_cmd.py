"""drift generate-skills — generate SKILL.md guard files from ArchGraph data.

Reads the persisted architecture graph and produces structured
``SkillBriefing`` objects.  By default shows a rich preview.
With ``--write`` actually writes ``.github/skills/<name>/SKILL.md`` files.

Usage::

    drift generate-skills                     # preview only
    drift generate-skills --write             # write new files (skip existing)
    drift generate-skills --write --force     # overwrite existing files
    drift generate-skills --write --dry-run   # preview without writing
    drift generate-skills --format json       # raw JSON output
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.table import Table

from drift.api.generate_skills import (
    generate_skills as _api_generate_skills,  # noqa: F401 (patched in tests)
)
from drift.arch_graph._models import SkillBriefing
from drift.arch_graph._skill_writer import render_skill_md
from drift.commands import console
from drift.commands._io import _emit_machine_output

# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------


@click.command("generate-skills", short_help="Generate SKILL.md guard files from ArchGraph.")
@click.option(
    "--repo",
    "path",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Path to the repository root.",
)
@click.option(
    "--write",
    is_flag=True,
    default=False,
    help="Write SKILL.md files to .github/skills/<name>/SKILL.md.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing SKILL.md files (only with --write).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview what would be written without actually writing (requires --write).",
)
@click.option(
    "--min-occurrences",
    type=int,
    default=4,
    show_default=True,
    help="Minimum signal recurrence to qualify a module.",
)
@click.option(
    "--min-confidence",
    type=float,
    default=0.6,
    show_default=True,
    help="Minimum confidence score to include a briefing.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write JSON output to this file instead of stdout.",
)
def generate_skills(
    path: Path,
    write: bool,
    force: bool,
    dry_run: bool,
    min_occurrences: int,
    min_confidence: float,
    output_format: str,
    output_file: Path | None,
) -> None:
    """Generate SKILL.md guard files for modules with recurring drift patterns.

    Reads the persisted architecture graph (``.drift-cache/``) and produces
    structured skill briefings.  Use ``drift map`` first to seed the graph.

    Examples::

        # Preview which guards would be generated
        drift generate-skills

        # Write new guard files (skip existing)
        drift generate-skills --write

        # Regenerate all (overwrite)
        drift generate-skills --write --force

        # Output raw JSON for agent consumption
        drift generate-skills --format json
    """
    result = _api_generate_skills(
        path=path,
        min_occurrences=min_occurrences,
        min_confidence=min_confidence,
    )

    # ---- JSON format -------------------------------------------------------
    if output_format == "json":
        payload = json.dumps(result, indent=2, ensure_ascii=False)
        _emit_machine_output(payload, output_file)
        if result.get("status") == "error":
            sys.exit(1)
        return

    # ---- Error ----------------------------------------------------------------
    if result.get("status") == "error":
        console.print(
            f"[bold red]Error:[/bold red] {result.get('error', 'Unknown error')} "
            f"([dim]{result.get('error_code', '')}[/dim])"
        )
        if result.get("recoverable"):
            console.print(
                "[yellow]Run [bold]drift map[/bold] or [bold]drift scan[/bold] "
                "first to seed the architecture graph.[/yellow]"
            )
        sys.exit(1)

    # ---- Rich output ----------------------------------------------------------
    briefing_dicts: list[dict[str, Any]] = result.get("skill_briefings", [])
    skill_count: int = result.get("skill_count", len(briefing_dicts))

    if skill_count == 0:
        console.print(
            "[green]No modules qualify for guard skills[/green] "
            "(thresholds not reached — try lowering [bold]--min-occurrences[/bold])."
        )
        return

    # Build preview table
    table = Table(
        title=f"Skill Briefings — {skill_count} module(s) qualify",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Module", style="bold")
    table.add_column("Signals")
    table.add_column("Confidence", justify="right")
    table.add_column("Hotspots", justify="right")
    table.add_column("Layer")

    for bd in briefing_dicts:
        table.add_row(
            bd["module_path"],
            ", ".join(bd.get("trigger_signals", [])),
            str(bd.get("confidence", "?")),
            str(len(bd.get("hotspot_files", []))),
            bd.get("layer") or "—",
        )

    console.print(table)

    # ---- Write mode -----------------------------------------------------------
    if write and not dry_run:
        _write_skills(path, briefing_dicts, force=force)
    elif write and dry_run:
        console.print(
            "\n[dim]Dry run — no files written.  "
            "Remove [bold]--dry-run[/bold] to write.[/dim]"
        )
    else:
        console.print(
            "\n[dim]Preview only.  "
            "Use [bold]--write[/bold] to generate the SKILL.md files.[/dim]"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _write_skills(
    repo_path: Path,
    briefing_dicts: list[dict[str, Any]],
    *,
    force: bool,
) -> None:
    """Write SKILL.md files from briefing dicts.

    Skips existing files unless *force* is True.
    """
    skills_root = repo_path / ".github" / "skills"
    written: list[Path] = []
    skipped: list[Path] = []

    for bd in briefing_dicts:
        briefing = SkillBriefing(
            name=bd["name"],
            module_path=bd["module_path"],
            trigger_signals=bd.get("trigger_signals", []),
            constraints=bd.get("constraints", []),
            hotspot_files=bd.get("hotspot_files", []),
            layer=bd.get("layer"),
            neighbors=bd.get("neighbors", []),
            abstractions=bd.get("abstractions", []),
            confidence=float(bd.get("confidence", 0.5)),
        )
        skill_dir = skills_root / briefing.name
        skill_file = skill_dir / "SKILL.md"

        if skill_file.exists() and not force:
            skipped.append(skill_file)
            continue

        skill_dir.mkdir(parents=True, exist_ok=True)
        content = render_skill_md(briefing)
        skill_file.write_text(content, encoding="utf-8")
        written.append(skill_file)

    # Report results
    if written:
        console.print(f"\n[green]Written {len(written)} SKILL.md file(s):[/green]")
        for p in written:
            console.print(f"  [bold]{p}[/bold]")

    if skipped:
        console.print(
            f"\n[yellow]Skipped {len(skipped)} existing file(s)[/yellow] "
            "(use [bold]--force[/bold] to overwrite):"
        )
        for p in skipped:
            console.print(f"  [dim]{p}[/dim]")

    if not written and not skipped:
        console.print("[dim]Nothing to write.[/dim]")
