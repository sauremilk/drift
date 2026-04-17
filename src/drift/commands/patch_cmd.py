"""drift patch — transactional protocol for agent-driven code changes.

Three subcommands: begin, check, commit (ADR-074).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from drift.commands import console
from drift.commands._io import _emit_machine_output


@click.group()
def patch() -> None:
    """Transactional patch protocol for agent-driven code changes (ADR-074)."""


@patch.command()
@click.option("--task-id", required=True, help="Unique identifier for the agent task.")
@click.option(
    "--declared-files",
    required=True,
    help="Comma-separated posix-relative file paths the agent intends to edit.",
)
@click.option(
    "--expected-outcome",
    required=True,
    help="Short description of what the edit should achieve.",
)
@click.option("--session-id", default=None, help="Optional session ID.")
@click.option(
    "--blast-radius",
    type=click.Choice(["local", "module", "repo"]),
    default="local",
    help="Expected blast radius (default: local).",
)
@click.option(
    "--forbidden-paths",
    default=None,
    help="Comma-separated paths the agent must NOT touch.",
)
@click.option(
    "--max-diff-lines",
    type=int,
    default=None,
    help="Maximum total diff lines before review is required.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="json",
    help="Output format (default: json).",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write output to file instead of stdout.",
)
def begin(
    task_id: str,
    declared_files: str,
    expected_outcome: str,
    session_id: str | None,
    blast_radius: str,
    forbidden_paths: str | None,
    max_diff_lines: int | None,
    output_format: str,
    output_file: Path | None,
) -> None:
    """Declare patch intent before editing files (phase 1)."""
    from drift.api.patch import patch_begin

    files = [f.strip() for f in declared_files.split(",") if f.strip()]
    forbidden = (
        [f.strip() for f in forbidden_paths.split(",") if f.strip()]
        if forbidden_paths
        else None
    )

    result = patch_begin(
        task_id=task_id,
        declared_files=files,
        expected_outcome=expected_outcome,
        session_id=session_id,
        blast_radius=blast_radius,
        forbidden_paths=forbidden,
        max_diff_lines=max_diff_lines,
    )

    if output_format == "json":
        _emit_machine_output(json.dumps(result, indent=2, default=str), output_file)
    else:
        console.print(f"[bold green]✓[/bold green] PatchIntent registered for {task_id}")
        console.print(f"  Declared files: {', '.join(files)}")
        console.print(f"  Next step: drift patch check --task-id {task_id}")


@patch.command()
@click.option("--task-id", required=True, help="Task ID matching a prior begin call.")
@click.option(
    "--declared-files",
    required=True,
    help="Comma-separated posix-relative file paths from the intent.",
)
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Repository root directory.",
)
@click.option(
    "--forbidden-paths",
    default=None,
    help="Comma-separated paths the agent must NOT touch.",
)
@click.option(
    "--max-diff-lines",
    type=int,
    default=None,
    help="Maximum total diff lines before review is required.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="json",
    help="Output format (default: json).",
)
@click.option(
    "--exit-zero",
    is_flag=True,
    default=False,
    help="Always exit 0, even on review_required.",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write output to file instead of stdout.",
)
def check(
    task_id: str,
    declared_files: str,
    repo: Path,
    forbidden_paths: str | None,
    max_diff_lines: int | None,
    output_format: str,
    exit_zero: bool,
    output_file: Path | None,
) -> None:
    """Validate scope compliance after editing (phase 2)."""
    from drift.api.patch import patch_check

    files = [f.strip() for f in declared_files.split(",") if f.strip()]
    forbidden = (
        [f.strip() for f in forbidden_paths.split(",") if f.strip()]
        if forbidden_paths
        else None
    )

    result = patch_check(
        task_id=task_id,
        declared_files=files,
        path=str(repo),
        forbidden_paths=forbidden,
        max_diff_lines=max_diff_lines,
    )

    status = result.get("status", "unknown")

    if output_format == "json":
        _emit_machine_output(json.dumps(result, indent=2, default=str), output_file)
    else:
        color = "green" if status == "clean" else "yellow"
        symbol = "✓" if status == "clean" else "⚠"
        console.print(f"[bold {color}]{symbol}[/bold {color}] Patch {status} for {task_id}")
        if result.get("scope_violations"):
            console.print(f"  Scope violations: {', '.join(result['scope_violations'])}")
        for reason in result.get("reasons", []):
            console.print(f"  → {reason}")

    if status != "clean" and not exit_zero:
        sys.exit(1)


@patch.command()
@click.option("--task-id", required=True, help="Task ID matching a prior begin call.")
@click.option(
    "--declared-files",
    required=True,
    help="Comma-separated posix-relative file paths from the intent.",
)
@click.option(
    "--expected-outcome",
    required=True,
    help="Short description of what the edit should achieve.",
)
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Repository root directory.",
)
@click.option("--session-id", default=None, help="Optional session ID.")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="json",
    help="Output format (default: json).",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write output to file instead of stdout.",
)
def commit(
    task_id: str,
    declared_files: str,
    expected_outcome: str,
    repo: Path,
    session_id: str | None,
    output_format: str,
    output_file: Path | None,
) -> None:
    """Generate evidence record for a completed patch (phase 3)."""
    from drift.api.patch import patch_commit

    files = [f.strip() for f in declared_files.split(",") if f.strip()]

    result = patch_commit(
        task_id=task_id,
        declared_files=files,
        expected_outcome=expected_outcome,
        path=str(repo),
        session_id=session_id,
    )

    if output_format == "json":
        _emit_machine_output(json.dumps(result, indent=2, default=str), output_file)
    else:
        mr = result.get("merge_readiness", "unknown")
        color = "green" if mr == "ready" else "yellow"
        console.print(f"[bold {color}]Evidence record[/bold {color}] for {task_id}")
        console.print(f"  Merge readiness: {mr}")
