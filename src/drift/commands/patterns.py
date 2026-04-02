"""drift patterns — display discovered code patterns."""

from __future__ import annotations

from pathlib import Path

import click

from drift.commands import console


@click.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
)
@click.option(
    "--category",
    type=click.Choice(
        [
            "error_handling",
            "data_access",
            "api_endpoint",
            "caching",
            "logging",
            "authentication",
            "validation",
        ]
    ),
    default=None,
    help="Filter by pattern category.",
)
@click.option(
    "--target-path",
    default=None,
    help="Restrict pattern discovery to a subdirectory.",
)
def patterns(repo: Path, category: str | None, target_path: str | None) -> None:
    """Show discovered code patterns in the repository.

    Use ``target_path`` to scope discovery to a specific subdirectory.
    """
    from rich.table import Table

    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo)

    with console.status("[bold blue]Discovering patterns..."):
        analysis = analyze_repo(repo, cfg, target_path=target_path)

    for cat, instances in sorted(analysis.pattern_catalog.items(), key=lambda x: x[0].value):
        if category and cat.value != category:
            continue

        table = Table(title=f"Pattern: {cat.value} ({len(instances)} instances)")
        table.add_column("File", min_width=30)
        table.add_column("Function", min_width=20)
        table.add_column("Lines")
        table.add_column("Variant", min_width=15)

        for inst in instances[:20]:
            variant = inst.variant_id or "—"
            table.add_row(
                inst.file_path.as_posix(),
                inst.function_name,
                f"{inst.start_line}-{inst.end_line}",
                variant,
            )

        console.print(table)
        console.print()

    if not analysis.pattern_catalog:
        console.print("[dim]No patterns detected.[/dim]")
