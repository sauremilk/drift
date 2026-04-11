"""Rich-based session metrics renderer for CLI output."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def render_session_report(
    data: dict[str, Any],
    console: Console | None = None,
) -> None:
    """Render a session report from a session dict to the console."""
    console = console or Console()

    sid = data.get("session_id", "unknown")[:8]
    repo = data.get("repo_path", ".")
    phase = data.get("phase", "unknown")
    tool_calls = data.get("tool_calls", 0)

    # Header
    console.print()
    console.print(
        Panel(
            f"[bold]Session:[/bold] {sid}  │  "
            f"[bold]Repo:[/bold] {repo}  │  "
            f"[bold]Phase:[/bold] {phase}  │  "
            f"[bold]Tool calls:[/bold] {tool_calls}",
            title="[bold]Drift Session Report[/bold]",
            border_style="rgb(13,148,136)",
        )
    )

    # Timestamps
    created = data.get("created_at")
    last_activity = data.get("last_activity")
    if created and last_activity:
        try:
            duration = float(last_activity) - float(created)
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            console.print(f"  Duration: {minutes}m {seconds}s")
        except (TypeError, ValueError):
            pass
    console.print()

    # Score progression
    score_start = data.get("score_at_start")
    scan = data.get("last_scan_score")
    if score_start is not None or scan is not None:
        score_table = Table(title="Score Progression", show_header=True)
        score_table.add_column("Metric", min_width=20)
        score_table.add_column("Value", justify="right")

        if score_start is not None:
            score_table.add_row("Score at start", f"{score_start:.3f}")
        if scan is not None:
            score_table.add_row("Score at end", f"{scan:.3f}")
        if score_start is not None and scan is not None:
            delta = scan - score_start
            color = "green" if delta < 0 else "red" if delta > 0 else "dim"
            arrow = "↓" if delta < 0 else "↑" if delta > 0 else "→"
            score_table.add_row(
                "Delta",
                f"[{color}]{arrow} {delta:+.3f}[/]",
            )

        console.print(score_table)
        console.print()

    # Task queue
    tasks = data.get("selected_tasks")
    completed_ids = data.get("completed_task_ids", [])
    failed_ids = data.get("failed_task_ids", [])
    if tasks is not None:
        task_table = Table(title="Task Queue", show_header=True)
        task_table.add_column("Metric", min_width=20)
        task_table.add_column("Value", justify="right")
        task_table.add_row("Total tasks", str(len(tasks)))
        task_table.add_row("Completed", f"[green]{len(completed_ids)}[/]")
        task_table.add_row("Failed", f"[red]{len(failed_ids)}[/]")
        remaining = len(tasks) - len(completed_ids) - len(failed_ids)
        task_table.add_row("Remaining", str(max(0, remaining)))
        console.print(task_table)
        console.print()

    # Orchestration metrics
    metrics = data.get("metrics", {})
    if metrics:
        _render_metrics(metrics, console)

    # Effectiveness warnings
    # Compute from thresholds if available
    thresholds = data.get("effectiveness_thresholds", {})
    warnings = _compute_warnings(metrics, thresholds)
    if warnings:
        console.print()
        console.print("[bold yellow]⚠ Effectiveness Warnings:[/bold yellow]")
        for w in warnings:
            console.print(f"  • {w}")


def _render_metrics(metrics: dict[str, Any], console: Console) -> None:
    """Render orchestration metrics as grouped tables."""
    # Efficiency metrics
    eff_table = Table(title="Efficiency Metrics", show_header=True)
    eff_table.add_column("Metric", min_width=30)
    eff_table.add_column("Value", justify="right")

    eff_fields = [
        ("Plans created", "plans_created"),
        ("Plans invalidated", "plans_invalidated"),
        ("Tasks claimed", "tasks_claimed"),
        ("Tasks completed", "tasks_completed"),
        ("Tasks failed", "tasks_failed"),
        ("Tasks released", "tasks_released"),
        ("Tasks expired", "tasks_expired"),
        ("Plan reuse ratio", "plan_reuse_ratio"),
        ("Discarded work ratio", "discarded_work_ratio"),
    ]
    for label, key in eff_fields:
        val = metrics.get(key)
        if val is not None:
            display = f"{val:.2%}" if isinstance(val, float) and val <= 1.0 else str(val)
            eff_table.add_row(label, display)
    console.print(eff_table)
    console.print()

    # Quality metrics
    qual_table = Table(title="Quality Metrics", show_header=True)
    qual_table.add_column("Metric", min_width=30)
    qual_table.add_column("Value", justify="right")

    qual_fields = [
        ("Nudge checks", "nudge_checks"),
        ("Nudge improving", "nudge_improving"),
        ("Nudge degrading", "nudge_degrading"),
        ("Nudge stable", "nudge_stable"),
        ("Verification failures", "verification_failures"),
        ("Total findings seen", "total_findings_seen"),
        ("Findings acted on", "findings_acted_on"),
        ("Findings suppressed", "findings_suppressed"),
        ("Suppression ratio", "suppression_ratio"),
        ("Action ratio", "action_ratio"),
    ]
    for label, key in qual_fields:
        val = metrics.get(key)
        if val is not None:
            display = f"{val:.2%}" if isinstance(val, float) and val <= 1.0 else str(val)
            qual_table.add_row(label, display)
    console.print(qual_table)
    console.print()

    # Outcome KPIs
    out_table = Table(title="Outcome KPIs", show_header=True)
    out_table.add_column("Metric", min_width=35)
    out_table.add_column("Value", justify="right")

    outcome_fields = [
        ("Verification runs", "verification_runs"),
        ("Changed files total", "changed_files_total"),
        ("LOC changed total", "loc_changed_total"),
        ("Resolved findings", "resolved_findings_total"),
        ("New findings", "new_findings_total"),
        ("Relocated findings", "relocated_findings_total"),
        ("Resolved / changed file", "resolved_findings_per_changed_file"),
        ("Resolved / 100 LOC", "resolved_findings_per_100_loc_changed"),
        ("Relocated ratio", "relocated_findings_ratio"),
        ("Verification density", "verification_density"),
    ]
    for label, key in outcome_fields:
        val = metrics.get(key)
        if val is not None:
            if isinstance(val, float):
                display = f"{val:.4f}" if val < 1.0 else f"{val:.2f}"
            else:
                display = str(val)
            out_table.add_row(label, display)
    console.print(out_table)


def _compute_warnings(
    metrics: dict[str, Any],
    thresholds: dict[str, float],
) -> list[str]:
    """Compute effectiveness warnings from metrics and thresholds."""
    warnings: list[str] = []

    changed = metrics.get("changed_files_total", 0)
    resolved = metrics.get("resolved_findings_total", 0)
    new = metrics.get("new_findings_total", 0)

    if changed > 5 and resolved == 0:
        warnings.append(
            "High churn with zero resolved findings — consider narrowing scope."
        )
    if new > resolved and resolved > 0:
        warnings.append(
            f"Net regression: {new} new findings vs {resolved} resolved."
        )

    degrading = metrics.get("nudge_degrading", 0)
    nudge_total = metrics.get("nudge_checks", 0)
    if nudge_total >= 3 and degrading > nudge_total * 0.5:
        warnings.append(
            "Majority of nudge checks show degradation — review approach."
        )

    return warnings
