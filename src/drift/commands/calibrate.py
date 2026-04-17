"""drift calibrate — compute per-repo signal profile from feedback evidence."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import click

from drift.commands import console


@click.group()
def calibrate() -> None:
    """Calibrate signal weights using collected feedback evidence."""


@calibrate.command(name="run")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option("--dry-run", is_flag=True, default=False, help="Show changes without writing.")
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def run(repo: Path, dry_run: bool, config: Path | None, fmt: str) -> None:
    """Compute calibrated weights from all evidence sources."""
    from drift.calibration.feedback import (
        dedupe_feedback_events,
        load_feedback_with_stats,
        resolve_feedback_paths,
    )
    from drift.calibration.profile_builder import assess_calibration_quality, build_profile
    from drift.calibration.status import write_calibration_status
    from drift.config import DriftConfig, SignalWeights

    cfg = DriftConfig.load(repo, config)

    # Collect explicit feedback
    feedback_path, _local_feedback_path, _shared_feedback_path = resolve_feedback_paths(repo, cfg)
    events, skipped_feedback_lines = load_feedback_with_stats(feedback_path)

    # Collect git-correlation evidence if history exists
    history_dir = repo / cfg.calibration.history_dir
    if history_dir.exists():
        from drift.calibration.history import load_snapshots

        snapshots = load_snapshots(history_dir)
        if snapshots:
            # Load git commits for correlation
            git_events = _collect_git_correlation(repo, snapshots, cfg)
            events.extend(git_events)

    events = dedupe_feedback_events(events)

    if not events:
        if fmt == "json":
            click.echo(json.dumps({
                "status": "no_data",
                "message": "No feedback evidence found.",
                "skipped_feedback_lines": skipped_feedback_lines,
            }))
        else:
            console.print(
                "[dim]No feedback evidence found."
                " Use 'drift feedback mark' to record evidence.[/dim]"
            )
            if skipped_feedback_lines:
                console.print(
                    "[yellow]Skipped malformed feedback lines:"
                    f" {skipped_feedback_lines}[/yellow]"
                )
        return

    result = build_profile(
        events,
        cfg.weights,
        min_samples=cfg.calibration.min_samples,
        fn_boost_factor=cfg.calibration.fn_boost_factor,
    )
    default_weights = SignalWeights()
    diff = result.weight_diff(default_weights)
    quality = assess_calibration_quality(result, default_weights)

    if fmt == "json":
        click.echo(json.dumps({
            "status": "calibrated",
            "total_events": result.total_events,
            "signals_with_data": result.signals_with_data,
            "weight_changes": diff,
            "quality": quality.as_dict(),
            "clamped_signals": result.clamped_signals,
            "skipped_feedback_lines": skipped_feedback_lines,
            "dry_run": dry_run,
        }, indent=2))
    else:
        if skipped_feedback_lines:
            console.print(
                "[yellow]Skipped malformed feedback lines:"
                f" {skipped_feedback_lines}[/yellow]"
            )
        if not diff:
            console.print(
                "[dim]No weight changes computed"
                " (insufficient evidence or no change).[/dim]"
            )
        else:
            console.print(
                f"\n[bold]Calibration Result[/bold]"
                f" ({result.total_events} events,"
                f" {result.signals_with_data} signals with data)\n"
            )
            console.print(
                f"{'Signal':<30} {'Default':>8} {'Calibrated':>10} {'Delta':>8} {'Conf.':>6}"
            )
            console.print("-" * 65)
            for signal_name, info in sorted(diff.items()):
                delta_str = f"{info['delta']:+.4f}"
                console.print(
                    f"{signal_name:<30} {info['default']:>8.4f}"
                    f" {info['calibrated']:>10.4f}"
                    f" {delta_str:>8} {info['confidence']:>5.1%}"
                )

            if result.clamped_signals:
                console.print(
                    "\n[yellow]Signals at minimum floor (0.001):[/yellow]"
                    f" {', '.join(result.clamped_signals)}"
                )

            if quality.warning_count > 0:
                console.print("\n[bold yellow]Calibration quality warnings:[/bold yellow]")
                for warning in quality.warnings:
                    console.print(f"  - {warning}")
            console.print(
                f"\n[dim]Calibration quality score: {quality.score:.2f}"
                f" (magnitude={quality.magnitude:.2f},"
                f" min_confidence={quality.min_confidence:.1%})[/dim]"
            )

    if not dry_run:
        signal_counts = _summarize_feedback_counts(events)
        write_calibration_status(
            repo,
            {
                "calibrated_at": datetime.now(UTC).isoformat(),
                "total_events": len(events),
                "signals": signal_counts,
                "weight_changes": diff,
                "quality": quality.as_dict(),
                "clamped_signals": result.clamped_signals,
            },
        )

        if diff:
            _write_calibrated_weights(repo, config, result)
            if fmt != "json":
                console.print("\n[green]Calibrated weights written to drift.yaml[/green]")


@calibrate.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
def explain(repo: Path, config: Path | None) -> None:
    """Show detailed evidence per signal."""
    from drift.calibration.feedback import load_feedback, resolve_feedback_paths
    from drift.calibration.profile_builder import build_profile
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)
    feedback_path, _local_feedback_path, _shared_feedback_path = resolve_feedback_paths(repo, cfg)
    events = load_feedback(feedback_path)

    if not events:
        console.print("[dim]No feedback evidence found.[/dim]")
        return

    result = build_profile(events, cfg.weights, min_samples=cfg.calibration.min_samples)

    console.print(f"\n[bold]Evidence Detail[/bold] ({result.total_events} events)\n")
    for signal_type in sorted(result.evidence):
        ev = result.evidence[signal_type]
        if ev.total_observations == 0 and ev.fn == 0:
            continue
        conf = result.confidence_per_signal.get(signal_type, 0.0)
        console.print(f"[bold]{signal_type}[/bold]")
        console.print(
            f"  TP={ev.tp}  FP={ev.fp}  FN={ev.fn}"
            f"  Precision={ev.precision:.2%}  Confidence={conf:.1%}"
        )

    if result.clamped_signals:
        console.print(
            "\n[yellow]Signals at minimum floor (0.001):[/yellow]"
            f" {', '.join(result.clamped_signals)}"
        )


@calibrate.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
def status(repo: Path, config: Path | None) -> None:
    """Show calibration profile status and freshness."""
    from drift.calibration.feedback import load_feedback_with_stats, resolve_feedback_paths
    from drift.calibration.status import load_calibration_status
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)

    if not cfg.calibration.enabled:
        console.print(
            "[yellow]Calibration is not enabled.[/yellow]"
            " Set calibration.enabled: true in drift.yaml"
        )
        return

    feedback_path, local_feedback_path, shared_feedback_path = resolve_feedback_paths(repo, cfg)
    events, skipped_feedback_lines = load_feedback_with_stats(feedback_path)
    console.print(f"Feedback events: {len(events)}")
    if skipped_feedback_lines:
        console.print(f"Skipped malformed feedback lines: {skipped_feedback_lines}")
    console.print(f"Feedback path: {feedback_path}")
    if shared_feedback_path is not None:
        console.print(f"Local feedback path: {local_feedback_path}")
        console.print(f"Shared feedback path: {shared_feedback_path}")

    history_dir = repo / cfg.calibration.history_dir
    if history_dir.exists():
        from drift.calibration.history import load_snapshots
        snapshots = load_snapshots(history_dir)
        console.print(f"History snapshots: {len(snapshots)}")
    else:
        console.print("History snapshots: 0")

    console.print(f"Min samples for full confidence: {cfg.calibration.min_samples}")
    auto = "enabled" if cfg.calibration.auto_recalibrate else "disabled"
    console.print(f"Auto-recalibrate: {auto}")

    status_payload = load_calibration_status(repo)
    if status_payload and isinstance(status_payload.get("quality"), dict):
        quality_payload = status_payload["quality"]
        score = float(quality_payload.get("score", 0.0))
        warning_count = int(quality_payload.get("warning_count", 0))
        console.print(
            f"Calibration quality score: {score:.2f}"
            f" (warnings: {warning_count})"
        )

    if status_payload and isinstance(status_payload.get("clamped_signals"), list):
        clamped = [str(item) for item in status_payload["clamped_signals"] if item]
        if clamped:
            console.print(
                "Signals at minimum floor (0.001):"
                f" {', '.join(sorted(clamped))}"
            )


@calibrate.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def quality(repo: Path, fmt: str) -> None:
    """Show meta-calibration health from calibration status metadata."""
    from drift.calibration.status import load_calibration_status

    payload = load_calibration_status(repo) or {}
    quality_payload = payload.get("quality")

    if not isinstance(quality_payload, dict):
        if fmt == "json":
            click.echo(json.dumps({"status": "no_data", "message": "No calibration quality data."}))
        else:
            console.print(
                "[dim]No calibration quality data found. "
                "Run 'drift calibrate run' first.[/dim]"
            )
        return

    score = float(quality_payload.get("score", 0.0))
    magnitude = float(quality_payload.get("magnitude", 0.0))
    min_confidence = float(quality_payload.get("min_confidence", 0.0))
    warning_count = int(quality_payload.get("warning_count", 0))
    warnings = quality_payload.get("warnings", [])
    warnings_list = [str(item) for item in warnings] if isinstance(warnings, list) else []

    if fmt == "json":
        click.echo(json.dumps({
            "status": "ok",
            "score": score,
            "magnitude": magnitude,
            "min_confidence": min_confidence,
            "warning_count": warning_count,
            "warnings": warnings_list,
        }, indent=2))
        return

    console.print("[bold]Calibration Quality[/bold]")
    console.print(f"  Score: {score:.2f}")
    console.print(f"  Magnitude: {magnitude:.2f}")
    console.print(f"  Min confidence: {min_confidence:.1%}")
    console.print(f"  Warnings: {warning_count}")
    if warnings_list:
        console.print("  Details:")
        for warning in warnings_list:
            console.print(f"    - {warning}")


@calibrate.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option(
    "--clear-feedback",
    is_flag=True,
    default=False,
    help="Archive all feedback evidence after removing calibrated weights.",
)
@click.option(
    "--signal",
    "signal_type",
    type=str,
    default=None,
    help="Remove feedback evidence only for the specified signal type.",
)
def reset(
    repo: Path,
    config: Path | None,
    clear_feedback: bool,
    signal_type: str | None,
) -> None:
    """Remove calibrated weights and revert to defaults."""
    import yaml  # type: ignore[import-untyped]

    from drift.calibration.feedback import load_feedback_with_stats, resolve_feedback_paths
    from drift.config import DriftConfig

    if clear_feedback and signal_type:
        raise click.ClickException(
            "--clear-feedback and --signal are mutually exclusive."
        )

    feedback_path = repo / ".drift" / "feedback.jsonl"
    try:
        cfg = DriftConfig.load(repo, config)
        feedback_path, _, _ = resolve_feedback_paths(repo, cfg)
    except Exception:
        # Keep reset usable even when config contains non-calibration schema issues.
        feedback_path = repo / ".drift" / "feedback.jsonl"

    feedback_events, _skipped_feedback_lines = load_feedback_with_stats(feedback_path)

    config_path = config or DriftConfig._find_config_file(repo)

    if config_path is None or not config_path.exists():
        console.print("[yellow]No config file found.[/yellow]")
        return

    raw = config_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}

    if "weights" in data:
        del data["weights"]
        _atomic_write_text(
            config_path,
            yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        )
        console.print("[green]Calibrated weights removed. Defaults will be used.[/green]")
    else:
        console.print("[dim]No custom weights found in config.[/dim]")

    if clear_feedback:
        archived_path = _archive_feedback_file(feedback_path)
        if archived_path is None:
            console.print("[dim]No feedback file found to archive.[/dim]")
        else:
            console.print(
                "[green]Feedback evidence archived:[/green]"
                f" {archived_path}"
            )
        return

    if signal_type:
        removed_count = _remove_feedback_events_for_signal(feedback_path, signal_type)
        if removed_count:
            console.print(
                f"[green]Removed {removed_count} feedback events"
                f" for signal '{signal_type}'.[/green]"
            )
        else:
            console.print(
                f"[dim]No feedback events found for signal '{signal_type}'.[/dim]"
            )
        return

    if feedback_events:
        console.print(
            "[yellow]Feedback evidence was not cleared"
            f" ({len(feedback_events)} events at {feedback_path}).[/yellow]"
        )
        console.print(
            "[yellow]Running 'drift calibrate run' will re-apply calibration."
            " Use '--clear-feedback' to archive evidence.[/yellow]"
        )


def _archive_feedback_file(feedback_path: Path) -> Path | None:
    """Archive feedback evidence by moving JSONL to a timestamped backup."""
    if not feedback_path.exists():
        return None

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = feedback_path.with_name(f"{feedback_path.name}.bak-{timestamp}")
    os.replace(feedback_path, backup_path)
    return backup_path


def _remove_feedback_events_for_signal(feedback_path: Path, signal_type: str) -> int:
    """Remove feedback JSONL entries for one signal while preserving other lines."""
    if not feedback_path.exists():
        return 0

    kept_lines: list[str] = []
    removed_count = 0
    for raw_line in feedback_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            # Keep malformed lines untouched to avoid accidental data loss.
            kept_lines.append(raw_line)
            continue

        if isinstance(payload, dict) and payload.get("signal_type") == signal_type:
            removed_count += 1
            continue
        kept_lines.append(raw_line)

    if removed_count:
        _atomic_write_text(
            feedback_path,
            ("\n".join(kept_lines) + "\n") if kept_lines else "",
        )
    return removed_count


def _atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Write text atomically by writing to a sibling temp file and replacing target."""
    fd, temp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )

    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(content)
        os.replace(temp_path, path)
    except OSError:
        with contextlib.suppress(OSError):
            Path(temp_path).unlink(missing_ok=True)
        raise


def _collect_git_correlation(
    repo: Path,
    snapshots: list,  # type: ignore[type-arg]
    cfg: object,
) -> list:  # type: ignore[type-arg]
    """Collect git-correlation evidence from history + git log."""
    from drift.calibration.outcome_correlator import correlate_outcomes

    try:
        from drift.ingestion.git_history import parse_git_history

        commits_raw = parse_git_history(repo, since_days=180)
        commits: list[dict[str, object]] = [
            {
                "timestamp": (
                    c.timestamp.isoformat()
                    if hasattr(c.timestamp, "isoformat")
                    else str(c.timestamp)
                ),
                "message": c.message,
                "files_changed": c.files_changed,
            }
            for c in commits_raw
        ]
    except Exception:
        return []

    cal_cfg = getattr(cfg, "calibration", None)
    window = getattr(cal_cfg, "correlation_window_days", 30) if cal_cfg else 30
    weak_fp = getattr(cal_cfg, "weak_fp_window_days", 60) if cal_cfg else 60

    return correlate_outcomes(
        snapshots,
        commits,
        correlation_window_days=window,
        weak_fp_window_days=weak_fp,
    )


def _write_calibrated_weights(
    repo: Path,
    config_path: Path | None,
    result: object,
) -> None:
    """Write calibrated weights to the drift.yaml config file."""
    import yaml

    from drift.config import DriftConfig

    actual_config = config_path or DriftConfig._find_config_file(repo)
    if actual_config is None:
        actual_config = repo / "drift.yaml"

    if actual_config.exists():
        raw = actual_config.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
    else:
        data = {}

    # Get calibrated weights as dict
    cal_weights = result.calibrated_weights.as_dict()  # type: ignore[attr-defined]

    # Only write weights that differ from defaults
    from drift.config import SignalWeights
    default_dict = SignalWeights().as_dict()
    custom_weights: dict[str, float] = {}
    for key, val in cal_weights.items():
        default_val = default_dict.get(key, 0.0)
        if abs(val - default_val) > 0.0001:
            custom_weights[key] = round(val, 6)

    if custom_weights:
        data["weights"] = custom_weights

    _atomic_write_text(
        actual_config,
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
    )


def _summarize_feedback_counts(events: Sequence[object]) -> dict[str, dict[str, int]]:
    """Summarize TP/FP/FN counts while tolerating malformed test doubles."""
    counts: dict[str, dict[str, int]] = {}
    for event in events:
        signal_type = getattr(event, "signal_type", None)
        verdict = getattr(event, "verdict", None)
        if not isinstance(signal_type, str) or verdict not in {"tp", "fp", "fn"}:
            continue
        if signal_type not in counts:
            counts[signal_type] = {"tp": 0, "fp": 0, "fn": 0}
        counts[signal_type][verdict] += 1
    return counts


# ---------------------------------------------------------------------------
# effort-* subcommands — Adaptive Recommendation Engine (ARE)
# ---------------------------------------------------------------------------


@calibrate.command(name="effort-run")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def effort_run(repo: Path, config: Path | None, fmt: str) -> None:
    """Calibrate recommendation effort labels from outcome history."""
    from drift.calibration.recommendation_calibrator import (
        calibrate_efforts,
        save_calibration,
    )
    from drift.config import DriftConfig
    from drift.outcome_tracker import OutcomeTracker

    cfg = DriftConfig.load(repo, config)
    outcome_path = repo / cfg.recommendations.outcome_path
    cal_path = repo / cfg.recommendations.calibration_path

    tracker = OutcomeTracker(outcome_path)
    outcomes = tracker.load()

    if not outcomes:
        if fmt == "json":
            click.echo(json.dumps({"status": "no_data", "message": "No outcome data found."}))
        else:
            console.print("[dim]No outcome data found. Run 'drift analyze' first.[/dim]")
        return

    calibrations = calibrate_efforts(
        outcomes,
        min_samples=cfg.recommendations.min_calibration_samples,
    )

    if not calibrations:
        if fmt == "json":
            click.echo(json.dumps({
                "status": "insufficient_data",
                "message": "Not enough resolved outcomes for calibration.",
            }))
        else:
            console.print(
                "[dim]Not enough resolved outcomes per signal type "
                f"(min {cfg.recommendations.min_calibration_samples}).[/dim]"
            )
        return

    save_calibration(calibrations, cal_path)

    if fmt == "json":
        from dataclasses import asdict

        click.echo(json.dumps({
            "status": "calibrated",
            "calibrations": [asdict(c) for c in calibrations],
        }, indent=2))
    else:
        console.print(f"\n[bold]Effort Calibration[/bold] ({len(calibrations)} signals)\n")
        console.print(f"{'Signal':<35} {'Effort':>8} {'Samples':>8} {'Median d':>9}")
        console.print("-" * 62)
        for cal in calibrations:
            console.print(
                f"{cal.signal_type:<35} {cal.effort:>8}"
                f" {cal.sample_size:>8} {cal.median_days_to_fix:>8.1f}d"
            )
        console.print(f"\n[green]Calibration saved to {cal_path}[/green]")


@calibrate.command(name="effort-report")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def effort_report(repo: Path, config: Path | None, fmt: str) -> None:
    """Show current effort calibration status."""
    from drift.calibration.recommendation_calibrator import load_calibration
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)
    cal_path = repo / cfg.recommendations.calibration_path
    mapping = load_calibration(cal_path)

    if fmt == "json":
        click.echo(json.dumps({"calibrations": mapping, "path": str(cal_path)}, indent=2))
    else:
        if not mapping:
            console.print(
                "[dim]No effort calibration found."
                " Run 'drift calibrate effort-run'.[/dim]"
            )
            return
        console.print(f"\n[bold]Effort Calibration[/bold] ({len(mapping)} signals)\n")
        for signal, effort in sorted(mapping.items()):
            console.print(f"  {signal:<35} → {effort}")
        console.print(f"\n[dim]Source: {cal_path}[/dim]")


@calibrate.command(name="effort-reset")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option("--config", "-c", type=click.Path(path_type=Path), default=None)
def effort_reset(repo: Path, config: Path | None) -> None:
    """Remove effort calibration file and revert to default effort labels."""
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)
    cal_path = repo / cfg.recommendations.calibration_path

    if cal_path.exists():
        cal_path.unlink()
        console.print("[green]Effort calibration removed. Default efforts will be used.[/green]")
    else:
        console.print("[dim]No effort calibration file found.[/dim]")
