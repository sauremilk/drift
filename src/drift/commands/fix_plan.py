"""drift fix-plan — agent-native prioritized repair planning."""

from __future__ import annotations

from pathlib import Path

import click

from drift.api import fix_plan as api_fix_plan
from drift.api import to_json


@click.command("fix-plan")
@click.option(
    "--repo",
    "path",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Path to the repository root.",
)
@click.option(
    "--finding-id",
    default=None,
    help=(
        "Target a specific finding by task id (e.g. pfs-abc123) "
        "or rule_id (e.g. explainability_deficit)."
    ),
)
@click.option("--signal", default=None, help="Filter to a specific signal (e.g. PFS).")
@click.option("--max-tasks", type=int, default=5, help="Maximum tasks to return.")
@click.option(
    "--target-path",
    "--path",
    default=None,
    help="Restrict tasks to findings inside this subpath.",
)
@click.option(
    "--exclude",
    "exclude_paths",
    multiple=True,
    help="Exclude findings inside this subpath. Can be provided multiple times.",
)
@click.option(
    "--include-deferred",
    is_flag=True,
    default=False,
    help="Include findings marked as deferred in drift config.",
)
@click.option(
    "--automation-fit-min",
    type=click.Choice(["low", "medium", "high"]),
    default=None,
    help="Minimum automation fitness to include.",
)
@click.option(
    "--include-non-operational",
    is_flag=True,
    default=False,
    help="Include fixture/generated/migration/docs findings in prioritized tasks.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
def fix_plan(
    path: Path,
    finding_id: str | None,
    signal: str | None,
    max_tasks: int,
    target_path: str | None,
    exclude_paths: tuple[str, ...],
    include_deferred: bool,
    automation_fit_min: str | None,
    include_non_operational: bool,
    output: Path | None,
) -> None:
    """Generate a prioritized, agent-friendly repair plan as JSON."""
    result = api_fix_plan(
        path,
        finding_id=finding_id,
        signal=signal,
        max_tasks=max_tasks,
        automation_fit_min=automation_fit_min,
        target_path=target_path,
        exclude_paths=list(exclude_paths) or None,
        include_deferred=include_deferred,
        include_non_operational=include_non_operational,
    )
    text = to_json(result)
    if output is not None:
        output.write_text(text + "\n", encoding="utf-8")
        click.echo(f"Output written to {output}", err=True)
    else:
        click.echo(text)
