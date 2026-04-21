"""drift fix-plan — agent-native prioritized repair planning."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import click

from drift.api import fix_plan as api_fix_plan
from drift.api import to_json
from drift.api.fix_apply import fix_apply as api_fix_apply
from drift.commands._io import _is_non_tty_stdout
from drift.config import DriftConfig
from drift.fix_plan_dismissals import (
    DEFAULT_TTL_DAYS,
    dismiss_task,
    get_active_dismissals,
    reset_dismissals,
)

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


def _validate_fix_plan_special_ops(
    dismiss_task_id: str | None,
    show_dismissed: bool,
    reset_dismissed: bool,
    do_apply: bool,
    dry_run: bool,
) -> None:
    """Raise UsageError if mutually exclusive special-op flags are combined."""
    special_ops = [
        bool(dismiss_task_id),
        show_dismissed,
        reset_dismissed,
        do_apply,
        dry_run,
    ]
    if sum(1 for enabled in special_ops if enabled) > 1:
        mutually_exclusive = [bool(dismiss_task_id), show_dismissed, reset_dismissed]
        if sum(1 for e in mutually_exclusive if e) > 1:
            raise click.UsageError(
                "Use only one of --dismiss, --show-dismissed, or --reset at a time"
            )


def _execute_fix_plan_operation(
    path: Path,
    repo_path: Path,
    cache_dir: str,
    dismiss_task_id: str | None,
    show_dismissed: bool,
    reset_dismissed: bool,
    do_apply: bool,
    dry_run: bool,
    finding_id: str | None,
    signal: str | None,
    max_tasks: int,
    target_path: str | None,
    exclude_paths: tuple[str, ...],
    automation_fit_min: str | None,
    include_deferred: bool,
    include_non_operational: bool,
    progress_cb: object,
    yes: bool = False,
) -> dict:  # type: ignore[type-arg]
    """Dispatch to the appropriate fix-plan sub-operation and return the result dict."""
    if dismiss_task_id:
        task_id = dismiss_task_id.strip()
        if not task_id:
            raise click.UsageError("--dismiss requires a non-empty task id")
        record = dismiss_task(repo_path, task_id, cache_dir, ttl_days=DEFAULT_TTL_DAYS)
        return {
            "schema_version": "2.1",
            "operation": "dismiss",
            "task_id": record["task_id"],
            "dismissed_at": record["dismissed_at"],
            "expires_at": record["expires_at"],
            "ttl_days": DEFAULT_TTL_DAYS,
            "cache_file": f"{cache_dir}/fix-plan-dismissed.json",
        }
    if show_dismissed:
        return {
            "schema_version": "2.1",
            "operation": "show-dismissed",
            "cache_file": f"{cache_dir}/fix-plan-dismissed.json",
            "dismissed": get_active_dismissals(repo_path, cache_dir),
        }
    if reset_dismissed:
        removed = reset_dismissals(repo_path, cache_dir)
        return {
            "schema_version": "2.1",
            "operation": "reset",
            "removed": removed,
            "cache_file": f"{cache_dir}/fix-plan-dismissed.json",
        }
    if do_apply or dry_run:
        return api_fix_apply(
            path,
            signal=signal,
            max_tasks=max_tasks,
            dry_run=dry_run or not do_apply,
            target_path=target_path,
            exclude_paths=list(exclude_paths) or None,
            require_clean_git=not yes,
        )
    return api_fix_plan(
        path,
        finding_id=finding_id,
        signal=signal,
        max_tasks=max_tasks,
        automation_fit_min=automation_fit_min,
        target_path=target_path,
        exclude_paths=list(exclude_paths) or None,
        include_deferred=include_deferred,
        include_non_operational=include_non_operational,
        on_progress=progress_cb,  # type: ignore[arg-type]
    )


def _emit_fix_plan_result(result: dict, output: Path | None, output_format: str) -> None:  # type: ignore[type-arg]
    """Validate and emit fix-plan result: file output, JSON, or Rich table."""
    if bool(result.get("error")):
        raise click.UsageError(str(result.get("message", "Invalid fix-plan input")))
    if output is not None:
        text = to_json(result)
        output.write_text(text + "\n", encoding="utf-8")
        click.echo(f"Output written to {output}", err=True)
        return
    use_json = output_format == "json" or (
        output_format == "auto" and _is_non_tty_stdout()
    )
    if use_json:
        click.echo(to_json(result))
    else:
        from drift.commands import console
        from drift.output.fix_plan_rich import render_fix_plan

        render_fix_plan(result, console)


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
    "--dismiss",
    "dismiss_task_id",
    default=None,
    help=(
        "Temporarily dismiss a fix-plan task id from output "
        f"(default TTL: {DEFAULT_TTL_DAYS} days)."
    ),
)
@click.option(
    "--show-dismissed",
    is_flag=True,
    default=False,
    help="Show currently dismissed fix-plan tasks.",
)
@click.option(
    "--reset",
    "reset_dismissed",
    is_flag=True,
    default=False,
    help="Clear all dismissed fix-plan tasks.",
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
@click.option(
    "--apply",
    "do_apply",
    is_flag=True,
    default=False,
    help=(
        "Apply high-confidence patches automatically. "
        "Requires a clean git state. "
        "Use --dry-run to preview without writing files."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview patches that would be applied without writing any files.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip the clean-git confirmation prompt when using --apply.",
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
    dismiss_task_id: str | None,
    show_dismissed: bool,
    reset_dismissed: bool,
    progress: str,
    output: Path | None,
    output_format: str,
    do_apply: bool,
    dry_run: bool,
    yes: bool,
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

    _validate_fix_plan_special_ops(
        dismiss_task_id, show_dismissed, reset_dismissed, do_apply, dry_run
    )

    repo_path = path.resolve()
    cfg = DriftConfig.load(repo_path)
    cache_dir = getattr(cfg, "cache_dir", ".drift-cache")

    result = _execute_fix_plan_operation(
        path, repo_path, cache_dir,
        dismiss_task_id, show_dismissed, reset_dismissed,
        do_apply, dry_run,
        finding_id, signal, max_tasks, target_path, exclude_paths,
        automation_fit_min, include_deferred, include_non_operational, progress_cb,
        yes=yes,
    )
    _emit_fix_plan_result(result, output, output_format)
