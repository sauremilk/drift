"""drift badge — generate shields.io badge URL."""

from __future__ import annotations

from pathlib import Path

import click

from drift.commands import console
from drift.models import Severity, severity_for_score


def _badge_color_for_score(score: float) -> str:
    """Return shield color aligned to canonical score severity mapping."""
    severity = severity_for_score(score)

    if severity is Severity.CRITICAL:
        return "critical"
    if severity is Severity.HIGH:
        return "orange"
    if severity is Severity.MEDIUM:
        return "yellow"
    return "brightgreen"


@click.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
)
@click.option("--since", "-s", default=90, type=int, help="Days of git history to analyze.")
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option(
    "--style",
    type=click.Choice(["flat", "flat-square", "for-the-badge", "plastic"]),
    default="flat",
    help="shields.io badge style.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["url", "svg"]),
    default="url",
    help="Output format: shields.io URL or self-contained SVG.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Write badge (URL or SVG) to file.",
)
def badge(
    repo: Path, since: int, config: Path | None, style: str, fmt: str, output: Path | None
) -> None:
    """Generate a shields.io badge URL or SVG for the repository drift score."""
    from urllib.parse import quote

    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)

    with console.status("[bold blue]Analyzing for badge..."):
        analysis = analyze_repo(repo, cfg, since_days=since)

    score = analysis.drift_score
    color = _badge_color_for_score(score)

    if fmt == "svg":
        from drift.output.badge_svg import render_badge_svg

        svg = render_badge_svg("drift score", f"{score:.2f}", color)
        if output:
            output.write_text(svg, encoding="utf-8")
            console.print(f"Badge SVG written to {output}")
        else:
            click.echo(svg)
        return

    label = quote("drift score")
    value = quote(f"{score:.2f}")
    url = f"https://img.shields.io/badge/{label}-{value}-{color}?style={style}"

    md_snippet = f"[![Drift Score]({url})](https://github.com/mick-gsk/drift)"

    if output:
        output.write_text(url, encoding="utf-8")
        console.print(f"Badge URL written to {output}")

    console.print()
    console.print("[bold]Drift Badge[/bold]")
    console.print()
    console.print(f"  Score: [bold]{score:.2f}[/bold]  ({analysis.severity.value})")
    console.print()
    console.print("[dim]URL:[/dim]")
    click.echo(f"  {url}")
    console.print()
    console.print("[dim]Markdown:[/dim]")
    click.echo(f"  {md_snippet}")
