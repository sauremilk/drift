"""drift baseline — save and compare finding baselines."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import click

from drift.api_helpers import build_drift_score_scope
from drift.commands import console

DEFAULT_BASELINE_PATH = Path(".drift-baseline.json")


@click.group()
def baseline() -> None:
    """Manage finding baselines for incremental adoption."""


@baseline.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option("--since", "-s", default=90, type=int, help="Days of git history to analyze.")
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option("--workers", "-w", default=None, type=int)
@click.option(
    "--worker-strategy",
    type=click.Choice(["fixed", "auto"]),
    default=None,
    help="Worker resolution strategy. fixed uses CPU fallback, auto enables conservative tuning.",
)
@click.option(
    "--load-profile",
    type=click.Choice(["conservative"]),
    default=None,
    help="Auto-tuning load profile (currently conservative only).",
)
@click.option("--no-embeddings", is_flag=True, default=False)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help=f"Baseline file path (default: {DEFAULT_BASELINE_PATH}).",
)
def save(
    repo: Path,
    since: int,
    config: Path | None,
    workers: int | None,
    worker_strategy: str | None,
    load_profile: str | None,
    no_embeddings: bool,
    output: Path | None,
) -> None:
    """Save the current finding state as a baseline."""
    from drift.analyzer import analyze_repo
    from drift.baseline import save_baseline
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)
    if worker_strategy is not None:
        cfg.performance.worker_strategy = cast(Literal["fixed", "auto"], worker_strategy)
    if load_profile is not None:
        cfg.performance.load_profile = cast(Literal["conservative"], load_profile)
    if no_embeddings:
        cfg.embeddings_enabled = False

    with console.status("[bold blue]Analyzing repository..."):
        analysis = analyze_repo(repo, cfg, since_days=since, workers=workers)

    dest = output or (repo / DEFAULT_BASELINE_PATH)
    save_baseline(analysis, dest)
    console.print(
        f"[bold green]✓ Baseline saved:[/bold green] {dest} "
        f"({len(analysis.findings)} findings, score {analysis.drift_score:.2f})"
    )


@baseline.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option("--since", "-s", default=90, type=int, help="Days of git history to analyze.")
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option("--workers", "-w", default=None, type=int)
@click.option(
    "--worker-strategy",
    type=click.Choice(["fixed", "auto"]),
    default=None,
    help="Worker resolution strategy. fixed uses CPU fallback, auto enables conservative tuning.",
)
@click.option(
    "--load-profile",
    type=click.Choice(["conservative"]),
    default=None,
    help="Auto-tuning load profile (currently conservative only).",
)
@click.option("--no-embeddings", is_flag=True, default=False)
@click.option(
    "--baseline-file",
    "-b",
    type=click.Path(path_type=Path),
    default=None,
    help=f"Baseline file to compare against (default: {DEFAULT_BASELINE_PATH}).",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Write output to a file instead of stdout.",
)
def diff(
    repo: Path,
    since: int,
    config: Path | None,
    workers: int | None,
    worker_strategy: str | None,
    load_profile: str | None,
    no_embeddings: bool,
    baseline_file: Path | None,
    output_format: str,
    output: Path | None,
) -> None:
    """Show only new findings compared to a saved baseline."""
    import json as json_mod

    from drift.analyzer import analyze_repo
    from drift.baseline import baseline_diff, load_baseline
    from drift.config import DriftConfig
    from drift.output.json_output import _finding_to_dict

    bl_path = baseline_file or (repo / DEFAULT_BASELINE_PATH)
    if not bl_path.exists():
        console.print(
            f"[bold red]✗ Baseline not found:[/bold red] {bl_path}\n"
            f"  Run this command first, then re-run baseline diff:\n"
            f"  [bold]drift baseline save --output {bl_path}[/bold]"
        )
        raise SystemExit(1)

    cfg = DriftConfig.load(repo, config)
    if worker_strategy is not None:
        cfg.performance.worker_strategy = cast(Literal["fixed", "auto"], worker_strategy)
    if load_profile is not None:
        cfg.performance.load_profile = cast(Literal["conservative"], load_profile)
    if no_embeddings:
        cfg.embeddings_enabled = False

    import json as _json

    try:
        fingerprints = load_baseline(bl_path)
    except (OSError, ValueError, _json.JSONDecodeError) as exc:
        console.print(
            f"[bold red]✗ Baseline file is corrupt[/bold red] — delete it and re-save: "
            f"[bold]drift baseline save[/bold]  ({exc})"
        )
        raise SystemExit(1) from exc

    with console.status("[bold blue]Analyzing repository..."):
        analysis = analyze_repo(repo, cfg, since_days=since, workers=workers)

    new, known = baseline_diff(analysis.findings, fingerprints)

    if output_format == "json":
        data = {
            "new_findings": [_finding_to_dict(f) for f in new],
            "known_findings_count": len(known),
            "total_findings": len(analysis.findings),
            "baseline_findings_count": len(fingerprints),
            "drift_score": analysis.drift_score,
            "drift_score_scope": build_drift_score_scope(
                context="repo",
                signal_scope="all",
                baseline_filtered=True,
            ),
        }
        text = json_mod.dumps(data, indent=2)
        if output is not None:
            output.write_text(text + "\n", encoding="utf-8")
            click.echo(f"Output written to {output}", err=True)
        else:
            click.echo(text)
    else:
        console.print(
            f"\n[bold]Baseline comparison[/bold] ({bl_path.name})"
        )
        console.print(
            f"  Total findings: {len(analysis.findings)}  |  "
            f"Known (baselined): {len(known)}  |  "
            f"[bold yellow]New: {len(new)}[/bold yellow]"
        )

        if new:
            console.print()
            from drift.output.rich_output import render_findings

            render_findings(new, max_items=len(new), console=console, repo_root=repo)
        else:
            console.print("\n[bold green]✓ No new findings since baseline.[/bold green]")
