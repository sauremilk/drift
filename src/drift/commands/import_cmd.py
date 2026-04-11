"""drift import — compare external tool reports with Drift analysis."""

from __future__ import annotations

from pathlib import Path

import click

from drift.commands import console


@click.command("import")
@click.argument("report", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["sonarqube", "pylint", "codeclimate"]),
    required=True,
    help="Format of the external report.",
)
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Repository root for Drift analysis.",
)
@click.option(
    "--since",
    "-s",
    default=90,
    type=int,
    help="Days of git history.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Output comparison as JSON.",
)
def import_report(
    report: Path,
    fmt: str,
    repo: Path,
    since: int,
    json_output: bool,
) -> None:
    """Compare an external tool report with Drift's own analysis.

    Reads a JSON report from SonarQube, pylint, or CodeClimate, then runs
    Drift analysis on the same repository and shows a side-by-side comparison.

    \b
    Examples:
      drift import sonar-report.json --format sonarqube
      drift import pylint-out.json --format pylint --repo ./myproject
      drift import codeclimate.json --format codeclimate --json
    """
    import json as json_mod

    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig
    from drift.ingestion.external_report import load_external_report

    # 1. Load external findings
    try:
        external_findings = load_external_report(report, fmt)
    except (ValueError, json_mod.JSONDecodeError) as exc:
        raise click.ClickException(str(exc)) from exc

    # 2. Run Drift analysis
    cfg = DriftConfig.load(repo)
    with console.status("[bold blue]Running Drift analysis for comparison..."):
        analysis = analyze_repo(repo, cfg, since_days=since)

    drift_findings = analysis.findings

    # 3. Build comparison
    external_files = {str(f.file_path) for f in external_findings if f.file_path}
    drift_files = {str(f.file_path) for f in drift_findings if f.file_path}
    overlap_files = external_files & drift_files
    drift_only_files = drift_files - external_files
    external_only_files = external_files - drift_files

    comparison = {
        "external_tool": fmt,
        "external_report": str(report),
        "external_findings_count": len(external_findings),
        "drift_findings_count": len(drift_findings),
        "drift_score": analysis.drift_score,
        "drift_severity": analysis.severity.value,
        "files_in_both": len(overlap_files),
        "files_only_in_drift": len(drift_only_files),
        "files_only_in_external": len(external_only_files),
        "drift_additional_signals": _unique_signals(drift_findings),
    }

    if json_output:
        click.echo(json_mod.dumps(comparison, indent=2))
        return

    # 4. Rich output
    _render_comparison(comparison, external_findings, drift_findings)


def _unique_signals(findings: list) -> list[str]:
    """Return sorted unique signal types from findings."""
    return sorted({f.signal_type for f in findings})


def _render_comparison(
    comparison: dict,
    external_findings: list,
    drift_findings: list,
) -> None:
    """Render a side-by-side comparison table."""
    from rich.panel import Panel
    from rich.table import Table

    tool = comparison["external_tool"]

    # Summary panel
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row(f"{tool} findings", str(comparison["external_findings_count"]))
    summary.add_row("Drift findings", str(comparison["drift_findings_count"]))
    summary.add_row("Drift score", f"{comparison['drift_score']:.2f}")
    summary.add_row("Drift severity", comparison["drift_severity"])
    summary.add_row("Files in both", str(comparison["files_in_both"]))
    summary.add_row("Files only in Drift", str(comparison["files_only_in_drift"]))
    summary.add_row(f"Files only in {tool}", str(comparison["files_only_in_external"]))

    console.print()
    console.print(Panel(summary, title=f"[bold]Drift vs. {tool}[/bold]", expand=False))

    # Drift-unique signals
    signals = comparison["drift_additional_signals"]
    if signals:
        console.print()
        console.print("[bold]Drift signals not covered by external tool:[/bold]")
        for sig in signals:
            if not sig.startswith(f"{tool}:"):
                console.print(f"  • {sig}")

    # Top Drift findings the external tool missed
    external_files = {str(f.file_path) for f in external_findings if f.file_path}
    additional = [f for f in drift_findings if str(f.file_path) not in external_files]

    if additional:
        console.print()
        table = Table(
            title="Drift findings in files not covered by external tool",
            show_lines=False,
        )
        table.add_column("File", style="cyan", max_width=50)
        table.add_column("Signal", style="yellow")
        table.add_column("Severity")
        table.add_column("Title", max_width=60)

        for f in additional[:15]:
            table.add_row(
                str(f.file_path) if f.file_path else "—",
                f.signal_type,
                f.severity.value,
                f.title,
            )
        if len(additional) > 15:
            table.add_row("…", f"+{len(additional) - 15} more", "", "")

        console.print(table)

    console.print()
    console.print(
        "[dim]Imported findings are for comparison only — "
        "they do not affect the drift score.[/dim]"
    )
