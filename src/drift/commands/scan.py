"""drift scan — agent-native repository scan."""

from __future__ import annotations

from pathlib import Path

import click

from drift.api import scan as api_scan
from drift.api import to_json
from drift.commands._io import _write_output_file


@click.command("scan")
@click.option(
    "--repo",
    "path",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Path to the repository root.",
)
@click.option("--target-path", default=None, help="Restrict analysis to a subdirectory.")
@click.option("--since", "since_days", type=int, default=90, help="Days of git history.")
@click.option(
    "--select",
    "--signals",
    "select",
    default=None,
    help="Comma-separated signal IDs to include (e.g. PFS,AVS).",
)
@click.option(
    "--max-findings",
    type=click.IntRange(min=1, max=200),
    default=10,
    help="Maximum findings to return (1-200).",
)
@click.option(
    "--strategy",
    type=click.Choice(["diverse", "top-severity"]),
    default="diverse",
    help="Finding selection strategy: diverse (default) or top-severity.",
)
@click.option(
    "--response-detail",
    type=click.Choice(["concise", "detailed"]),
    default="concise",
    help="Response detail level.",
)
@click.option(
    "--include-non-operational",
    is_flag=True,
    default=False,
    help="Include fixture/generated/migration/docs findings in prioritization queues.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
def scan(
    path: Path,
    target_path: str | None,
    since_days: int,
    select: str | None,
    max_findings: int,
    strategy: str,
    response_detail: str,
    include_non_operational: bool,
    output: Path | None,
) -> None:
    """Run the agent-native scan workflow and emit structured JSON."""

    signals = [item.strip() for item in select.split(",") if item.strip()] if select else None
    result = api_scan(
        path,
        target_path=target_path,
        since_days=since_days,
        signals=signals,
        max_findings=max_findings,
        response_detail=response_detail,
        strategy=strategy,
        include_non_operational=include_non_operational,
    )
    text = to_json(result)
    if output is not None:
        _write_output_file(text, output)
        click.echo(f"Output written to {output}", err=True)
    else:
        click.echo(text)
