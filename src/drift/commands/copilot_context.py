"""drift copilot-context — generate Copilot instructions from drift analysis."""

from __future__ import annotations

from pathlib import Path

import click

from drift.commands import console


@click.command("copilot-context")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: .github/copilot-instructions.md).",
)
@click.option(
    "--write",
    "-w",
    is_flag=True,
    default=False,
    help="Write/merge into the output file. Without this flag, prints to stdout.",
)
@click.option(
    "--no-merge",
    is_flag=True,
    default=False,
    help="Overwrite the entire file instead of merging into existing content.",
)
@click.option("--since", "-s", default=90, type=int, help="Days of git history to analyze.")
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to drift config file.",
)
def copilot_context(
    repo: Path,
    output: Path | None,
    write: bool,
    no_merge: bool,
    since: int,
    config: Path | None,
) -> None:
    """Generate Copilot instructions from drift analysis results.

    Analyzes the repository and produces architectural constraints that
    Copilot can use to generate better code.  Output is framed with merge
    markers so it can be safely combined with hand-written instructions.

    Examples::

        drift copilot-context                 # preview to stdout
        drift copilot-context --write         # merge into .github/copilot-instructions.md
        drift copilot-context -w -o docs/ai.md  # write to custom path
    """
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig
    from drift.copilot_context import generate_instructions, merge_into_file

    repo_path = repo.resolve()
    cfg = DriftConfig.load(config or repo_path)

    click.echo("Running drift analysis...", err=True)
    analysis = analyze_repo(repo_path, config=cfg, since_days=since)

    section = generate_instructions(analysis)

    if not write:
        click.echo(section)
        return

    target = output or (repo_path / ".github" / "copilot-instructions.md")
    changed = merge_into_file(target, section, no_merge=no_merge)

    if changed:
        console.print(
            f"[green]✓[/] Written to [bold]{target}[/]",
            highlight=False,
        )
    else:
        console.print(
            f"[dim]No changes — [bold]{target}[/] is already up to date.[/]",
            highlight=False,
        )
