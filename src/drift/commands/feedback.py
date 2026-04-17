"""drift feedback — record TP/FP/FN evidence for signal calibration."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

from drift.commands import console


@click.group()
def feedback() -> None:
    """Record calibration feedback for signal weight tuning."""


@feedback.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option(
    "--mark",
    "-m",
    type=click.Choice(["tp", "fp", "fn"]),
    required=True,
    help="Verdict: true positive, false positive, or false negative.",
)
@click.option(
    "--signal",
    "-s",
    required=True,
    help="Signal type or abbreviation (e.g. PFS, architecture_violation).",
)
@click.option(
    "--file",
    "-f",
    "file_path",
    required=True,
    help="File path the finding relates to.",
)
@click.option(
    "--reason",
    default=None,
    help="Optional reason for the verdict.",
)
@click.option(
    "--line",
    "-l",
    type=int,
    default=None,
    help="Start line of the finding (for line-precise feedback).",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=None,
    help="Config file path.",
)
def mark(
    repo: Path,
    mark: str,
    signal: str,
    file_path: str,
    reason: str | None,
    line: int | None,
    config: Path | None,
) -> None:
    """Record a single feedback verdict for a finding."""
    from drift.calibration.feedback import FeedbackEvent, record_feedback, resolve_feedback_paths
    from drift.config import SIGNAL_ABBREV, DriftConfig

    cfg = DriftConfig.load(repo, config)

    # Resolve signal abbreviation to full name
    resolved_signal = SIGNAL_ABBREV.get(signal.upper(), signal)

    feedback_path, _local_feedback_path, _shared_feedback_path = resolve_feedback_paths(repo, cfg)
    event = FeedbackEvent(
        signal_type=resolved_signal,
        file_path=file_path,
        verdict=mark,  # type: ignore[arg-type]
        source="user",
        start_line=line,
        evidence={"reason": reason} if reason else {},
    )

    record_feedback(feedback_path, event)
    loc = f"{file_path}:{line}" if line is not None else file_path
    console.print(
        f"[green]Recorded[/green] {mark.upper()} for "
        f"[bold]{resolved_signal}[/bold] in {loc}"
    )


@feedback.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=None,
    help="Config file path.",
)
def summary(repo: Path, config: Path | None) -> None:
    """Show aggregated feedback counts per signal."""
    from drift.calibration.feedback import (
        dedupe_feedback_events,
        feedback_metrics,
        load_feedback,
        resolve_feedback_paths,
    )
    from drift.calibration.status import load_calibration_status
    from drift.config import SIGNAL_ABBREV, DriftConfig, SignalWeights

    cfg = DriftConfig.load(repo, config)
    feedback_path, _local_feedback_path, _shared_feedback_path = resolve_feedback_paths(repo, cfg)
    events = dedupe_feedback_events(load_feedback(feedback_path))

    if not events:
        console.print("[dim]No feedback recorded yet.[/dim]")
        return

    metrics = feedback_metrics(events)
    console.print(f"\n[bold]Feedback Summary[/bold] ({len(events)} events)\n")
    console.print(
        f"{'Signal':<30} {'TP':>5} {'FP':>5} {'FN':>5}"
        f" {'Prec':>6} {'Rec':>6} {'F1':>6} {'N':>5}"
    )
    console.print("-" * 76)
    low_sample_signals: list[str] = []
    for signal_type in sorted(metrics):
        m = metrics[signal_type]
        n = getattr(m, "total_observations", m.tp + m.fp)
        console.print(
            f"{signal_type:<30} {m.tp:>5} {m.fp:>5} {m.fn:>5}"
            f" {m.precision:>6.2f} {m.recall:>6.2f} {m.f1:>6.2f} {n:>5}"
        )
        if n < 20:
            low_sample_signals.append(signal_type)

    if low_sample_signals:
        console.print()
        console.print(
            f"[bold yellow]\u26a0 {len(low_sample_signals)} signal(s) have "
            f"<20 observations — calibration confidence will be low.[/bold yellow]"
        )
        console.print(
            "[dim]Calibration needs \u226520 TP+FP events per signal for "
            "full confidence (see drift calibrate explain).[/dim]"
        )

    default_weights = SignalWeights().as_dict()
    configured_weights = default_weights
    if hasattr(cfg, "weights") and hasattr(cfg.weights, "as_dict"):
        configured_weights = cfg.weights.as_dict()

    abbrev_by_signal = {signal: abbrev for abbrev, signal in SIGNAL_ABBREV.items()}
    calibration_status = load_calibration_status(repo) or {}
    calibrated_at_raw = str(calibration_status.get("calibrated_at", "")).strip()
    calibrated_at = _parse_iso_ts(calibrated_at_raw)

    pending_marks = len(events)
    if calibrated_at is not None:
        pending_marks = 0
        for event in events:
            event_ts = _parse_iso_ts(getattr(event, "timestamp", ""))
            if event_ts is not None and event_ts > calibrated_at:
                pending_marks += 1

    last_calibrated_text = "never"
    if calibrated_at is not None:
        last_calibrated_text = calibrated_at.strftime("%Y-%m-%d %H:%M")

    pending_text = "none pending"
    if pending_marks > 0:
        pending_text = f"{pending_marks} feedback marks since then — pending"

    console.print("\n[bold]Calibration Status[/bold]")
    console.print(f"  Last calibrated: {last_calibrated_text} ({pending_text})")
    console.print("  Weight changes from defaults:")

    status_signals = calibration_status.get("signals", {})
    display_signals = sorted(metrics.keys())
    if not display_signals and isinstance(status_signals, dict):
        display_signals = sorted(status_signals.keys())

    if not display_signals:
        console.print("    [dim]No signal-level feedback available yet.[/dim]")
        return

    for signal_name in display_signals:
        default_weight = float(default_weights.get(signal_name, 0.0))
        calibrated_weight = float(configured_weights.get(signal_name, default_weight))

        status_counts = (
            status_signals.get(signal_name, {}) if isinstance(status_signals, dict) else {}
        )
        if isinstance(status_counts, dict):
            tp = int(status_counts.get("tp", 0))
            fp = int(status_counts.get("fp", 0))
            fn = int(status_counts.get("fn", 0))
        else:
            metric_entry = metrics.get(signal_name)
            tp = int(getattr(metric_entry, "tp", 0)) if metric_entry is not None else 0
            fp = int(getattr(metric_entry, "fp", 0)) if metric_entry is not None else 0
            fn = int(getattr(metric_entry, "fn", 0)) if metric_entry is not None else 0

        source_text = _format_feedback_source(tp=tp, fp=fp, fn=fn)
        display_signal = abbrev_by_signal.get(signal_name, signal_name).upper()
        console.print(
            f"    {display_signal}: {default_weight:>5.2f} -> {calibrated_weight:>5.2f}"
            f" ({source_text})"
        )


def _parse_iso_ts(raw: str) -> datetime | None:
    """Parse ISO timestamp and gracefully handle trailing 'Z'."""
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _format_feedback_source(tp: int, fp: int, fn: int) -> str:
    """Render compact per-signal feedback source text."""
    parts: list[str] = []
    if tp:
        parts.append(f"{tp} TP")
    if fp:
        parts.append(f"{fp} FP")
    if fn:
        parts.append(f"{fn} FN")

    if not parts:
        return "no feedback marks"
    return "/".join(parts) + " marks applied"


@feedback.command(name="import")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=None,
    help="Config file path.",
)
@click.argument(
    "source_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def import_feedback(repo: Path, config: Path | None, source_file: Path) -> None:
    """Import feedback events from an external JSONL file."""
    from drift.calibration.feedback import load_feedback, record_feedback, resolve_feedback_paths
    from drift.config import DriftConfig

    cfg = DriftConfig.load(repo, config)
    feedback_path, _local_feedback_path, _shared_feedback_path = resolve_feedback_paths(repo, cfg)

    events = load_feedback(source_file)
    if not events:
        console.print("[yellow]No valid events found in source file.[/yellow]")
        return

    for event in events:
        record_feedback(feedback_path, event)

    console.print(f"[green]Imported {len(events)} events[/green] into {feedback_path}")


@feedback.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=None,
    help="Config file path.",
)
@click.option(
    "--to-shared",
    is_flag=True,
    default=False,
    help="Merge events from local calibration.feedback_path into calibration.shared_feedback_path.",
)
def push(repo: Path, config: Path | None, to_shared: bool) -> None:
    """Merge local feedback events into the configured shared feedback file."""
    from drift.calibration.feedback import load_feedback, record_feedback, resolve_feedback_paths
    from drift.config import DriftConfig

    if not to_shared:
        raise click.ClickException("Use --to-shared to select the merge target.")

    cfg = DriftConfig.load(repo, config)
    _effective_path, local_feedback_path, shared_feedback_path = resolve_feedback_paths(repo, cfg)

    if shared_feedback_path is None:
        raise click.ClickException(
            "calibration.shared_feedback_path is not set in config. "
            "Set it first, then rerun 'drift feedback push --to-shared'."
        )

    local_events = load_feedback(local_feedback_path)
    if not local_events:
        console.print(f"[dim]No local feedback events found in {local_feedback_path}.[/dim]")
        return

    shared_events = load_feedback(shared_feedback_path)
    existing_keys = {
        (
            event.finding_id,
            event.verdict,
            event.timestamp,
            event.signal_type,
            event.file_path,
            event.start_line,
        )
        for event in shared_events
    }

    imported = 0
    for event in local_events:
        key = (
            event.finding_id,
            event.verdict,
            event.timestamp,
            event.signal_type,
            event.file_path,
            event.start_line,
        )
        if key in existing_keys:
            continue
        record_feedback(shared_feedback_path, event)
        existing_keys.add(key)
        imported += 1

    console.print(
        f"[green]Merged {imported} new event(s)[/green] from {local_feedback_path} "
        f"into {shared_feedback_path}"
    )
