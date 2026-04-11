"""drift fix-plan — agent-native prioritized repair planning."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import click

from drift.api import fix_plan as api_fix_plan
from drift.api import to_json
from drift.commands._io import _is_non_tty_stdout

_progress_start: float = 0.0


def _json_progress_callback(phase: str, current: int, total: int) -> None:
    """Emit structured JSON-lines progress on stderr for agent consumption."""
    msg = {
        "type": "progress",
        "step": current,
        "total": total,
        "signal": phase,
        "elapsed_s": round(time.monotonic() - _progress_start, 1),
    }
    sys.stderr.write(json.dumps(msg) + "\n")
    sys.stderr.flush()


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
    "--progress",
    type=click.Choice(["auto", "json", "none"]),
    default="auto",
    help="Progress reporting: auto (json for non-TTY), json, none.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["auto", "rich", "json"]),
    default="auto",
    help=(
        "Output format: auto (rich in terminal, json for pipes/CI), "
        "rich (always rich), json (always JSON, default for --output)."
    ),
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
    progress: str,
    output: Path | None,
    output_format: str,
) -> None:
    """Generate a prioritized, agent-friendly repair plan.

    Outputs Rich tables in a terminal (auto-detected) and JSON for pipes/CI.
    Use --format json to force JSON, or --format rich to force Rich output.
    """
    # Auto-detect: use JSON progress for non-TTY consumers (#155)
    if progress == "auto" and _is_non_tty_stdout():
        progress = "json"

    progress_cb = None
    if progress == "json":
        global _progress_start
        _progress_start = time.monotonic()
        progress_cb = _json_progress_callback

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
        on_progress=progress_cb,
    )

    # API-level validation errors (e.g. unknown signal) must surface as
    # CLI failures so machine-mode callers receive a non-zero exit code.
    if bool(result.get("error")):
        raise click.UsageError(str(result.get("message", "Invalid fix-plan input")))

    # --output always writes JSON regardless of --format
    if output is not None:
        text = to_json(result)
        output.write_text(text + "\n", encoding="utf-8")
        click.echo(f"Output written to {output}", err=True)
        return

    # Resolve effective output format
    use_json = (
        output_format == "json"
        or (output_format == "auto" and _is_non_tty_stdout())
    )

    if use_json:
        click.echo(to_json(result))
    else:
        from drift.commands import console
        from drift.output.fix_plan_rich import render_fix_plan

        render_fix_plan(result, console)
