"""drift self — self-analysis of drift's own codebase."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from drift.commands import console
from drift.errors import DriftSystemError


@click.command(name="self")
@click.option("--since", "-s", default=90, type=int, help="Days of git history to analyze.")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json", "sarif", "agent-tasks"]),
    default="rich",
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(path_type=Path),
    default=None,
    help="Write machine output (JSON/SARIF) to a file instead of stdout.",
)
def self_analyze(since: int, output_format: str, output_file: Path | None) -> None:
    """Analyze Drift's own codebase and optionally write machine output to a file."""
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig

    # Locate drift's own source tree (package root -> src/drift -> repo)
    drift_root = Path(__file__).resolve().parent.parent.parent.parent
    if not (drift_root / "pyproject.toml").exists():
        raise DriftSystemError(
            "DRIFT-2001",
            message=(
                "drift self only works inside the drift source code repository "
                "(github.com/sauremilk/drift). "
                "For your project, use 'drift scan' instead."
            ),
            path=str(drift_root),
            suggested_action=(
                "Run inside the drift source repository, or use "
                "'drift scan' / 'drift analyze' for other projects."
            ),
        )

    cfg = DriftConfig.load(drift_root)
    # Self-checks run after tests in CI; temporary launch venvs can inflate score gates.
    if "**/.tmp_*venv*/**" not in cfg.exclude:
        cfg.exclude.append("**/.tmp_*venv*/**")

    info_console = Console(stderr=True) if output_format != "rich" else console
    info_console.print(f"[bold]drift self[/bold] — analyzing drift's own codebase ({drift_root})")
    info_console.print()

    with info_console.status("[bold blue]Running self-analysis..."):
        analysis = analyze_repo(
            drift_root,
            cfg,
            since_days=since,
            target_path="src/drift",
        )

    if output_format == "json":
        from drift.output.json_output import analysis_to_json

        text = analysis_to_json(analysis)
        if output_file:
            output_file.write_text(text + "\n", encoding="utf-8")
            click.echo(f"Output written to {output_file}", err=True)
        else:
            click.echo(text)
    elif output_format == "sarif":
        from drift.output.json_output import findings_to_sarif

        text = findings_to_sarif(analysis)
        if output_file:
            output_file.write_text(text + "\n", encoding="utf-8")
            click.echo(f"Output written to {output_file}", err=True)
        else:
            click.echo(text)
    elif output_format == "agent-tasks":
        from drift.output.agent_tasks import analysis_to_agent_tasks_json

        text = analysis_to_agent_tasks_json(analysis)
        if output_file:
            output_file.write_text(text + "\n", encoding="utf-8")
            click.echo(f"Output written to {output_file}", err=True)
        else:
            click.echo(text)
    else:
        from drift.output.rich_output import render_full_report, render_recommendations

        render_full_report(analysis, console)

        from drift.recommendations import generate_recommendations

        recs = generate_recommendations(analysis.findings)
        if recs:
            render_recommendations(recs, console)
