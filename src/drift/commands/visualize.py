"""drift visualize — interactive TUI dashboard for architecture health.

Requires the ``textual`` optional dependency::

    pip install drift-analyzer[tui]
"""

from __future__ import annotations

from pathlib import Path

import click

from drift.commands import console


@click.command("visualize", short_help="Interactive TUI dashboard for architecture health.")
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
def visualize(
    repo: Path,
    path: str | None,
    since: int,
    config: Path | None,
) -> None:
    """Launch an interactive terminal dashboard showing module-level
    architecture health, score heatmaps, and finding drill-down.

    Requires: ``pip install drift-analyzer[tui]``
    """
    try:
        from drift.output.tui_renderer import DriftVisualizeApp
    except ImportError as exc:
        console.print(
            "[red]The 'textual' package is required for the visualize command.[/red]\n"
            "Install it with: [bold]pip install drift-analyzer\\[tui][/bold]"
        )
        raise SystemExit(1) from exc

    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)

    with console.status("[bold blue]Analyzing repository..."):
        analysis = analyze_repo(repo, cfg, since_days=since, target_path=path)

    if not analysis.module_scores:
        console.print("[yellow]No module scores found. Nothing to visualize.[/yellow]")
        return

    app = DriftVisualizeApp(analysis)
    app.run()
