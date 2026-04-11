"""Rich terminal renderer for drift fix-plan output (ADR-047)."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_FIT_STYLE: dict[str, str] = {
    "high": "bold green",
    "medium": "yellow",
    "low": "dim",
}

_SEV_STYLE: dict[str, str] = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "cyan",
    "info": "dim",
}


def render_fix_plan(result: dict[str, Any], console: Console) -> None:
    """Render a fix-plan API result as a Rich terminal table.

    Parameters
    ----------
    result:
        The dict returned by ``drift.api.fix_plan()``.
    console:
        The Rich Console to write to.
    """
    tasks: list[dict[str, Any]] = result.get("tasks") or []
    task_count: int = result.get("task_count", len(tasks))
    total_available: int = result.get("total_available", task_count)
    drift_score: float | None = result.get("drift_score")
    warnings: list[str] = result.get("warnings") or []

    # --- Header panel ---
    score_str = f"{drift_score:.3f}" if drift_score is not None else "—"
    header_text = Text.assemble(
        ("Drift Score  ", "bold"),
        (score_str, "bold cyan"),
        ("  │  ", "dim"),
        (f"Showing {task_count} of {total_available} tasks", ""),
    )
    if total_available > task_count:
        header_text.append(
            f"  │  use --max-tasks {total_available} to see all",
            style="dim italic",
        )
    console.print(
        Panel(header_text, title="[bold]drift fix-plan[/bold]", border_style="cyan")
    )

    if warnings:
        for w in warnings:
            console.print(f"  [yellow]⚠[/yellow] {w}", highlight=False)
        console.print()

    if not tasks:
        console.print("  [dim]No tasks in current scope.[/dim]")
        console.print()
        return

    # --- Task table ---
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=3, no_wrap=True)
    table.add_column("Signal", no_wrap=True, min_width=6)
    table.add_column("Severity", no_wrap=True, min_width=8)
    table.add_column("File", no_wrap=False, min_width=20)
    table.add_column("Task", no_wrap=False)
    table.add_column("Fit", no_wrap=True, min_width=4)

    for i, task in enumerate(tasks, 1):
        signal = task.get("signal_type", "")
        severity = str(task.get("severity", "")).lower()
        file_path = str(task.get("file_path") or "—")
        line = task.get("start_line")
        if line:
            file_path = f"{file_path}:{line}"
        title = task.get("title") or task.get("description") or "—"
        fit = str(task.get("automation_fit", "")).lower()

        table.add_row(
            str(i),
            Text(signal, style="bold"),
            Text(severity, style=_SEV_STYLE.get(severity, "")),
            Text(file_path, style="dim"),
            title,
            Text(fit, style=_FIT_STYLE.get(fit, "")),
        )

    console.print(table)
    console.print()

    # --- Next step hint ---
    next_step = (result.get("recommended_next_actions") or [None])[0]
    if next_step:
        console.print(f"  [dim]Next:[/dim] {next_step}")
    console.print(
        "  [dim]For machine-readable output: [bold]--format json[/bold][/dim]"
    )
    console.print()
