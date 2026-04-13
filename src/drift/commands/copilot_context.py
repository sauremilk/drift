"""drift copilot-context — generate Copilot instructions from drift analysis."""

from __future__ import annotations

import json
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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json"], case_sensitive=False),
    default="markdown",
    help="Output format (default: markdown).",
)
@click.option(
    "--json",
    "json_shortcut",
    is_flag=True,
    default=False,
    help="Shortcut for --format json (agent-friendly).",
)
@click.option("--since", "-s", default=90, type=int, help="Days of git history to analyze.")
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to drift config file.",
)
@click.option(
    "--target",
    "-t",
    type=click.Choice(
        ["copilot", "cursor", "windsurf", "claude", "agents", "all"],
        case_sensitive=False,
    ),
    default="copilot",
    help=(
        "Target agent platform: copilot (.github/copilot-instructions.md), "
        "cursor (.cursorrules), windsurf (.windsurfrules), "
        "claude (CLAUDE.md), agents (AGENTS.md), or all."
    ),
)
def copilot_context(
    repo: Path,
    output: Path | None,
    write: bool,
    no_merge: bool,
    output_format: str,
    json_shortcut: bool,
    since: int,
    config: Path | None,
    target: str,
) -> None:
    """Generate Copilot instructions from drift analysis results.

    Analyzes the repository and produces architectural constraints that
    Copilot can use to generate better code.  Output is framed with merge
    markers so it can be safely combined with hand-written instructions.

    Examples::

        drift copilot-context                 # preview to stdout
        drift copilot-context --json          # machine-readable JSON to stdout
        drift copilot-context --write         # merge into .github/copilot-instructions.md
        drift copilot-context -w -o docs/ai.md  # write to custom path
        drift copilot-context --target cursor   # generate .cursorrules format
        drift copilot-context --target windsurf # generate .windsurfrules format
        drift copilot-context --target claude   # generate CLAUDE.md format
        drift copilot-context --target agents   # generate AGENTS.md format
        drift copilot-context --target all -w   # write all formats at once
    """
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig
    from drift.copilot_context import (
        generate_constraints_payload,
        generate_for_target,
        generate_instructions,
        merge_into_file,
        target_default_path,
    )

    if json_shortcut:
        output_format = "json"
    output_format = output_format.lower()
    target = target.lower()

    repo_path = repo.resolve()
    cfg = DriftConfig.load(config or repo_path)

    click.echo("Running drift analysis...", err=True)
    analysis = analyze_repo(repo_path, config=cfg, since_days=since)

    # JSON output ignores --target (always machine-readable)
    if output_format == "json":
        rendered = json.dumps(generate_constraints_payload(analysis), indent=2)
        if not write:
            click.echo(rendered)
            return
        json_target = output or (repo_path / ".drift-copilot-context.json")
        json_target.parent.mkdir(parents=True, exist_ok=True)
        json_target.write_text(rendered + "\n", encoding="utf-8")
        console.print(
            f"[green]✓[/] Written to [bold]{json_target}[/]",
            highlight=False,
        )
        return

    # --target all: write all supported target formats
    if target == "all":
        if not write:
            # Preview: show copilot format to stdout
            click.echo(generate_instructions(analysis))
            return
        targets = ["copilot", "cursor", "windsurf", "claude", "agents"]
        for t in targets:
            rendered_t = generate_for_target(t, analysis)
            t_path = target_default_path(t, repo_path)
            # Only Copilot uses marker-based merge
            use_merge = t == "copilot"
            if use_merge:
                changed = merge_into_file(t_path, rendered_t, no_merge=no_merge)
            else:
                t_path.parent.mkdir(parents=True, exist_ok=True)
                t_path.write_text(rendered_t, encoding="utf-8")
                changed = True
            if changed:
                console.print(
                    f"[green]✓[/] Written to [bold]{t_path}[/]",
                    highlight=False,
                )
            else:
                console.print(
                    f"[dim]No changes — [bold]{t_path}[/] is already up to date.[/]",
                    highlight=False,
                )
        return

    # Single target format
    rendered = generate_for_target(target, analysis)

    if not write:
        click.echo(rendered)
        return

    file_target = output or target_default_path(target, repo_path)
    # Copilot uses marker-based merge; other targets overwrite
    if target == "copilot":
        changed = merge_into_file(file_target, rendered, no_merge=no_merge)
    else:
        file_target.parent.mkdir(parents=True, exist_ok=True)
        file_target.write_text(rendered, encoding="utf-8")
        changed = True

    if changed:
        console.print(
            f"[green]✓[/] Written to [bold]{file_target}[/]",
            highlight=False,
        )
    else:
        console.print(
            f"[dim]No changes — [bold]{file_target}[/] is already up to date.[/]",
            highlight=False,
        )
