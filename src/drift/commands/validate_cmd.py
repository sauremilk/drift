"""drift validate — agent-native preflight validation."""

from __future__ import annotations

from pathlib import Path

import click

from drift.api import to_json
from drift.api import validate as api_validate


@click.command("validate")
@click.option(
    "--repo",
    "path",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Path to the repository root.",
)
@click.option(
    "--config",
    "config_file",
    type=click.Path(path_type=Path),
    default=None,
    help="Explicit configuration file path.",
)
@click.option(
    "--baseline",
    "baseline_file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Baseline file for progress comparison (runs quick scan).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
def validate(
    path: Path,
    config_file: Path | None,
    baseline_file: Path | None,
    output: Path | None,
) -> None:
    """Validate drift config and environment and emit structured JSON."""
    result = api_validate(
        path,
        config_file=str(config_file) if config_file else None,
        baseline_file=str(baseline_file) if baseline_file else None,
    )
    text = to_json(result)
    if output is not None:
        output.write_text(text + "\n", encoding="utf-8")
        click.echo(f"Output written to {output}", err=True)
    else:
        click.echo(text)
