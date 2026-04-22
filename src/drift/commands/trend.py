"""drift trend — score trend over time."""

from __future__ import annotations

from pathlib import Path

import click

from drift.commands import console
from drift.trend_history import load_history, snapshot_scope


@click.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
)
@click.option("--last", "-l", "days", default=90, type=int, help="Number of days to trend.")
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output trend data as JSON.")
def trend(repo: Path, days: int, config: Path | None, as_json: bool) -> None:
    """Show drift score trend over time; optional machine-readable JSON output."""
    import json as json_mod

    from rich.table import Table

    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)
    history_file = repo / cfg.cache_dir / "history.json"

    console.print(f"[bold]Drift — trend ({days}-day history window)[/bold]")
    console.print()

    with console.status("[bold blue]Analyzing current state..."):
        analysis = analyze_repo(repo, cfg, since_days=days)

    # Analyzer persistiert den aktuellen Snapshot bereits kanonisch.
    snapshots = [s for s in load_history(history_file) if snapshot_scope(s) == "repo"]

    # Filter to entries with required keys for display — malformed entries
    # (e.g. legacy format, partial writes) are silently skipped.
    snapshots = [
        s for s in snapshots
        if isinstance(s.get("drift_score"), (int, float)) and isinstance(s.get("timestamp"), str)
    ]

    # JSON output: structured machine-readable trend data
    if as_json:
        payload = {
            "current_score": analysis.drift_score,
            "total_files": analysis.total_files,
            "total_findings": len(analysis.findings),
            "snapshot_count": len(snapshots),
            "snapshots": snapshots,
        }
        if len(snapshots) >= 2:
            first_score = snapshots[0]["drift_score"]
            latest_score = snapshots[-1]["drift_score"]
            payload["overall_delta"] = round(latest_score - first_score, 6)
        click.echo(json_mod.dumps(payload, default=str))
        return

    # Display trend table
    if len(snapshots) < 2:
        console.print(f"  Drift score: [bold]{analysis.drift_score:.3f}[/bold]")
        console.print(f"  Files: {analysis.total_files}  |  Findings: {len(analysis.findings)}")
        console.print()
        console.print(
            "[yellow]\u26a0 Not enough history for trend comparison.[/yellow]\n"
            "  Snapshots are saved automatically on each run to "
            "[bold].drift-cache/history.json[/bold].\n"
            "  For a meaningful trend, run [bold]drift analyze[/bold] periodically — "
            "or add a scheduled CI job that caches [bold].drift-cache/[/bold] between runs:\n"
            "  See [bold]docs/guides/ci-integration.md[/bold] section \"Trend-Tracking\" "
            "for a ready-made GitHub Actions example."
        )
        return

    table = Table(title="Score History (last 10)")
    table.add_column("Timestamp", min_width=20)
    table.add_column("Score", justify="right")
    table.add_column("Δ", justify="right")
    table.add_column("Findings", justify="right")

    recent = snapshots[-10:]
    for i, snap in enumerate(recent):
        ts = snap["timestamp"][:19].replace("T", " ")
        score = snap["drift_score"]
        findings = snap.get("total_findings", "?")

        if i > 0:
            prev = recent[i - 1]["drift_score"]
            delta = score - prev
            delta_str = f"{delta:+.3f}"
            if delta > 0.01:
                delta_str = f"[red]{delta_str}[/red]"
            elif delta < -0.01:
                delta_str = f"[green]{delta_str}[/green]"
        else:
            delta_str = "—"

        color = "red" if score >= 0.6 else "yellow" if score >= 0.3 else "green"
        table.add_row(ts, f"[{color}]{score:.3f}[/{color}]", delta_str, str(findings))

    console.print(table)
    console.print()

    # Freshness indicator: warn when snapshots are clustered in a short window
    from datetime import datetime

    try:
        first_ts = datetime.fromisoformat(snapshots[0]["timestamp"])
        last_ts = datetime.fromisoformat(snapshots[-1]["timestamp"])
        span = last_ts - first_ts
        span_minutes = span.total_seconds() / 60

        if span.total_seconds() < 86400:  # less than 1 day
            if span_minutes < 60:
                span_label = f"{span_minutes:.0f} minutes"
            else:
                span_label = f"{span_minutes / 60:.1f} hours"
            console.print(
                f"  [bold yellow]\u26a0 All {len(snapshots)} snapshots span only"
                f" {span_label}.[/bold yellow]"
            )
            console.print(
                "  [dim]For meaningful trends, accumulate snapshots over days/weeks.[/dim]\n"
                "  [dim]Tip: cache [bold].drift-cache/[/bold] in CI so snapshots persist\n"
                "  across runs — see [bold]docs/guides/ci-integration.md[/bold]"
                " \u2192 Trend-Tracking.[/dim]"
            )
            console.print()
    except (ValueError, KeyError):
        pass

    # Summary
    first_score = snapshots[0]["drift_score"]
    latest_score = snapshots[-1]["drift_score"]
    overall_delta = latest_score - first_score
    direction = (
        "[red]↑ increasing[/red]"
        if overall_delta > 0.01
        else "[green]↓ decreasing[/green]"
        if overall_delta < -0.01
        else "[dim]→ stable[/dim]"
    )
    console.print(
        f"  Overall trend ({len(snapshots)} snapshots): {direction}  ({overall_delta:+.3f})"
    )

    console.print(f"  Current drift score: [bold]{analysis.drift_score:.3f}[/bold]")
    console.print(f"  Files analyzed: {analysis.total_files}")
    console.print(f"  Total findings: {len(analysis.findings)}")
    console.print(f"  AI-attributed commits: {analysis.ai_attributed_ratio:.0%}")

    # Trend chart
    if len(snapshots) >= 3:
        from drift.output.rich_output import render_trend_chart

        render_trend_chart(snapshots, console=console)
