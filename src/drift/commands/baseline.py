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
    console.print(
        "[dim]Run [bold]drift check --diff HEAD~1[/bold] on future commits "
        "to track changes against this baseline.[/dim]"
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
@click.option(
    "--fail-on-new",
    type=int,
    default=None,
    help=(
        "Exit with code 1 if the number of NEW findings (not in baseline) exceeds this "
        "threshold. Enables use as a non-mutating pre-commit gate. "
        "Example: --fail-on-new 0 blocks any new drift."
    ),
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
    fail_on_new: int | None,
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

    # Ratchet gate (ADR-093): enforce a non-mutating upper bound on new findings.
    # Must run for both rich and json output modes so the JSON consumer also
    # benefits from the exit-code contract.
    if fail_on_new is not None and len(new) > fail_on_new:
        click.echo(
            f"drift baseline diff: {len(new)} new finding(s) exceed "
            f"--fail-on-new {fail_on_new}. "
            f"Review the diff above. To accept the new findings, run: "
            f"drift baseline update --confirm",
            err=True,
        )
        raise SystemExit(1)


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
    help="Worker resolution strategy.",
)
@click.option(
    "--load-profile",
    type=click.Choice(["conservative"]),
    default=None,
)
@click.option("--no-embeddings", is_flag=True, default=False)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help=f"Baseline file path (default: {DEFAULT_BASELINE_PATH}).",
)
@click.option(
    "--confirm",
    is_flag=True,
    default=False,
    help="Required acknowledgement that the new drift state is intentional.",
)
def update(
    repo: Path,
    since: int,
    config: Path | None,
    workers: int | None,
    worker_strategy: str | None,
    load_profile: str | None,
    no_embeddings: bool,
    output: Path | None,
    confirm: bool,
) -> None:
    """Update the saved baseline to the current finding state.

    This is a deliberate alias for ``baseline save`` that refuses to run without
    ``--confirm``. It exists so an agent (or developer) cannot silently ratchet
    the baseline via a short command typo — accepting new drift must be an
    explicit, reviewable act (ADR-093).
    """
    if not confirm:
        click.echo(
            "drift baseline update: refusing to run without --confirm.\n"
            "Accepting new drift into the baseline is a deliberate act. "
            "Re-run as: drift baseline update --confirm",
            err=True,
        )
        raise SystemExit(2)

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
        f"[bold green]✓ Baseline updated:[/bold green] {dest} "
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
@click.option("--no-embeddings", is_flag=True, default=False)
@click.option(
    "--baseline-file",
    "-b",
    type=click.Path(path_type=Path),
    default=None,
    help=f"Baseline file to inspect (default: {DEFAULT_BASELINE_PATH}).",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["rich", "json"]),
    default="rich",
)
def status(
    repo: Path,
    since: int,
    config: Path | None,
    workers: int | None,
    no_embeddings: bool,
    baseline_file: Path | None,
    output_format: str,
) -> None:
    """Print a one-shot summary of baseline vs. current findings.

    Pure read-only: unlike ``baseline diff`` this command never exits
    non-zero based on drift counts, so it is safe to call from
    dashboards, CI notifications or the ``drift info`` aggregator.
    Useful during local development to answer "how close am I to the
    baseline right now?" without parsing JSON.
    """
    import json as json_mod

    from drift.analyzer import analyze_repo
    from drift.baseline import baseline_diff, load_baseline
    from drift.config import DriftConfig

    bl_path = baseline_file or (repo / DEFAULT_BASELINE_PATH)
    bl_exists = bl_path.exists()

    cfg = DriftConfig.load(repo, config)
    if no_embeddings:
        cfg.embeddings_enabled = False

    with console.status("[bold blue]Analyzing repository..."):
        analysis = analyze_repo(repo, cfg, since_days=since, workers=workers)

    if bl_exists:
        try:
            fingerprints = load_baseline(bl_path)
        except Exception:  # noqa: BLE001 — best-effort status command
            fingerprints = []
            bl_exists = False
        new, known = baseline_diff(analysis.findings, fingerprints) if fingerprints else (
            analysis.findings,
            [],
        )
    else:
        fingerprints = []
        new, known = analysis.findings, []

    if output_format == "json":
        click.echo(
            json_mod.dumps(
                {
                    "baseline_exists": bl_exists,
                    "baseline_path": str(bl_path),
                    "baseline_findings": len(fingerprints),
                    "total_findings": len(analysis.findings),
                    "known_findings": len(known),
                    "new_findings": len(new),
                    "drift_score": analysis.drift_score,
                },
                indent=2,
            )
        )
        return

    if not bl_exists:
        console.print(
            f"[bold yellow]! No baseline at[/bold yellow] {bl_path}\n"
            f"  Run [bold]drift baseline save[/bold] to establish one."
        )
        console.print(
            f"  Current state: {len(analysis.findings)} findings, "
            f"score {analysis.drift_score:.2f}"
        )
        return

    delta = len(new)
    if delta == 0:
        marker = "[bold green]✓ clean[/bold green]"
    elif delta <= 5:
        marker = f"[bold yellow]{delta} new[/bold yellow]"
    else:
        marker = f"[bold red]{delta} new[/bold red]"

    console.print(f"\n[bold]Baseline status[/bold] ({bl_path.name}) — {marker}")
    console.print(
        f"  total: {len(analysis.findings)}  "
        f"known: {len(known)}  "
        f"new: {delta}  "
        f"score: {analysis.drift_score:.2f}"
    )

