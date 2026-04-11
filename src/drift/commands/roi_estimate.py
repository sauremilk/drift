"""drift roi-estimate -- estimate refactoring effort from current findings."""

from __future__ import annotations

import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import click

from drift.commands import console

_HOURS_PER_SIGNAL: dict[str, float] = {
    "pattern_fragmentation": 2.0,
    "architecture_violation": 3.0,
    "mutant_duplicate": 1.5,
    "explainability_deficit": 0.5,
    "doc_impl_drift": 0.5,
    "temporal_volatility": 1.0,
    "system_misalignment": 2.0,
    "broad_exception_monoculture": 0.5,
    "test_polarity_deficit": 1.5,
    "guard_clause_deficit": 0.5,
    "cohesion_deficit": 2.5,
    "naming_contract_violation": 0.3,
    "bypass_accumulation": 1.0,
    "exception_contract_drift": 1.0,
    "co_change_coupling": 2.0,
    "fan_out_explosion": 2.0,
    "circular_import": 1.5,
    "dead_code_accumulation": 0.5,
    "missing_authorization": 2.0,
    "insecure_default": 1.0,
    "hardcoded_secret": 0.5,
    "phantom_reference": 1.0,
    "ts_architecture": 1.5,
    "cognitive_complexity": 1.0,
}

_DEFAULT_HOURS = 1.0


def _estimate_hours(signal_type: str) -> float:
    """Return estimated fix-hours for a signal type."""
    return _HOURS_PER_SIGNAL.get(signal_type, _DEFAULT_HOURS)


def _build_estimate(findings: Sequence[Any]) -> list[dict[str, Any]]:
    """Group findings by signal and compute estimated hours."""
    counts: Counter[str] = Counter()
    files_per_signal: dict[str, set[str]] = {}

    for f in findings:
        st = f.signal_type  # type: ignore[attr-defined]
        counts[st] += 1
        if not files_per_signal.get(st):
            files_per_signal[st] = set()
        loc = getattr(f, "location", None)
        if loc:
            files_per_signal[st].add(str(loc))

    rows: list[dict[str, Any]] = []
    for signal_type, count in counts.most_common():
        hours_each = _estimate_hours(signal_type)
        total_hours = round(hours_each * count, 1)
        rows.append({
            "signal_type": signal_type,
            "findings": count,
            "files_affected": len(files_per_signal.get(signal_type, set())),
            "hours_per_finding": hours_each,
            "estimated_hours": total_hours,
        })

    return rows


@click.command("roi-estimate", short_help="Estimate refactoring effort from findings.")
@click.option(
    "--repo", "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Repository root.",
)
@click.option(
    "--path", "--target-path", "-p",
    default=None,
    help="Restrict analysis to a subdirectory.",
)
@click.option("--since", "-s", default=90, type=int, help="Days of git history.")
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option(
    "--format", "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
    help="Output format.",
)
@click.option("--top", default=3, type=int, help="Highlight top-N savings in summary.")
def roi_estimate(
    repo: Path,
    path: str | None,
    since: int,
    config: Path | None,
    output_format: str,
    top: int,
) -> None:
    """Estimate refactoring hours based on current drift findings.

    Runs a drift analysis, then maps each finding to a heuristic
    fix-effort estimate.  Useful for sprint planning and stakeholder
    communication.

    \b
    Examples:
      drift roi-estimate
      drift roi-estimate --format json
      drift roi-estimate --top 5 --path src/
    """
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig

    repo = repo.resolve()
    cfg = DriftConfig.load(repo, config)

    analysis = analyze_repo(repo, cfg, since_days=since, target_path=path)
    rows = _build_estimate(analysis.findings)
    total_hours = sum(float(r["estimated_hours"]) for r in rows)
    total_findings = sum(int(r["findings"]) for r in rows)

    if output_format == "json":
        payload = {
            "total_findings": total_findings,
            "total_estimated_hours": round(total_hours, 1),
            "drift_score": round(analysis.drift_score, 4),
            "signals": rows,
        }
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        sys.exit(0)

    # --- Rich output ---
    from rich.table import Table

    console.print()
    console.print("[bold]Drift ROI Estimate[/bold]")
    console.print(
        f"Drift Score: [bold]{analysis.drift_score:.2f}[/bold]  |  "
        f"Findings: [bold]{total_findings}[/bold]  |  "
        f"Estimated effort: [bold]{total_hours:.1f}h[/bold]"
    )
    console.print()

    if not rows:
        console.print("[green]No findings -- nothing to fix.[/green]")
        sys.exit(0)

    table = Table(show_header=True, header_style="bold")
    table.add_column("Signal", style="cyan")
    table.add_column("Findings", justify="right")
    table.add_column("Files", justify="right")
    table.add_column("h/finding", justify="right")
    table.add_column("Total hours", justify="right", style="bold")

    for r in rows:
        table.add_row(
            str(r["signal_type"]),
            str(r["findings"]),
            str(r["files_affected"]),
            f"{r['hours_per_finding']:.1f}",
            f"{r['estimated_hours']:.1f}",
        )

    console.print(table)

    top_rows = rows[:top]
    if top_rows:
        top_hours = sum(float(r["estimated_hours"]) for r in top_rows)
        console.print()
        console.print(
            f"  Fix the top {len(top_rows)} signal types "
            f"to save ~[bold]{top_hours:.1f}h[/bold] of refactoring."
        )

    console.print()
    sys.exit(0)
