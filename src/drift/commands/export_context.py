"""drift export-context — export negative context as Markdown for agent consumption."""

from __future__ import annotations

from pathlib import Path

import click

from drift.commands import console


@click.command("export-context")
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
    help="Output file path (default: .drift-negative-context.md).",
)
@click.option(
    "--write",
    "-w",
    is_flag=True,
    default=False,
    help="Write to the output file.  Without this flag, prints to stdout.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["instructions", "prompt", "raw"], case_sensitive=False),
    default="instructions",
    help=(
        "Output format: 'instructions' (.instructions.md compatible),"
        " 'prompt' (.prompt.md compact), 'raw' (machine-readable JSON)."
    ),
)
@click.option(
    "--scope",
    type=click.Choice(["file", "module", "repo"], case_sensitive=False),
    default=None,
    help="Filter by scope.",
)
@click.option(
    "--max-items",
    type=int,
    default=25,
    help="Maximum anti-pattern items to include (default: 25).",
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
    "--include-positive",
    is_flag=True,
    default=False,
    help=(
        "Include positive architectural guidance (from copilot-context) "
        "above the anti-pattern constraints.  Produces a single combined "
        "context document."
    ),
)
def export_context(
    repo: Path,
    output: Path | None,
    write: bool,
    fmt: str,
    scope: str | None,
    max_items: int,
    since: int,
    config: Path | None,
    include_positive: bool,
) -> None:
    """Export anti-pattern context for coding agents and automation.

    Runs drift analysis and converts findings into a structured context
    document that coding agents or automation can consume. The output is
    compatible with .github/copilot-instructions.md, .instructions.md,
    .prompt.md files, or machine-readable JSON.

    Examples::

        drift export-context                    # preview to stdout
        drift export-context --write            # write .drift-negative-context.md
        drift export-context -w --format prompt # write as .prompt.md format
        drift export-context --include-positive # combined positive + negative context
        drift export-context -w -o .github/instructions/anti-patterns.instructions.md
    """
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig
    from drift.finding_context import split_findings_by_context
    from drift.negative_context import findings_to_negative_context
    from drift.negative_context.export import render_negative_context_markdown

    repo_path = repo.resolve()
    cfg = DriftConfig.load(config or repo_path)
    triage_cfg = cfg if hasattr(cfg, "finding_context") else DriftConfig()

    click.echo("Running drift analysis...", err=True)
    analysis = analyze_repo(repo_path, config=cfg, since_days=since)
    prioritized_findings, _excluded_findings, _context_counts = split_findings_by_context(
        analysis.findings,
        triage_cfg,
        include_non_operational=False,
    )

    items = findings_to_negative_context(
        prioritized_findings,
        scope=scope,
        max_items=max_items,
    )

    markdown = render_negative_context_markdown(
        items,
        fmt=fmt,
        drift_score=analysis.drift_score,
        severity=analysis.severity,
    )

    # Optionally prepend positive architectural guidance
    if include_positive and fmt != "raw":
        from drift.copilot_context import generate_instructions

        positive_section = generate_instructions(analysis, config=triage_cfg)
        markdown = positive_section + "\n---\n\n" + markdown
    elif include_positive and fmt == "raw":
        import json

        from drift.copilot_context import generate_instructions

        positive_section = generate_instructions(analysis, config=triage_cfg)
        raw_data = json.loads(markdown)
        raw_data["positive_context"] = positive_section
        markdown = json.dumps(raw_data, indent=2)

    if not write:
        click.echo(markdown)
        return

    target = output or (repo_path / ".drift-negative-context.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")

    console.print(
        f"[green]✓[/] Exported {len(items)} anti-pattern items to [bold]{target}[/]",
        highlight=False,
    )
