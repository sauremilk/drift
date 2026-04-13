"""drift suppress — inspect and audit inline suppression directives."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import click
from rich.table import Table

from drift.commands import console


def _abbrev_from_signal_map() -> dict[str, str]:
    from drift.config import SIGNAL_ABBREV

    reverse: dict[str, str] = {}
    for abbrev, signal in SIGNAL_ABBREV.items():
        reverse.setdefault(signal, abbrev)
    return reverse


def _render_signals(signals: set[str] | None, signal_to_abbrev: dict[str, str]) -> str:
    if signals is None:
        return "ALL"
    labels: list[str] = []
    for signal in sorted(signals):
        labels.append(signal_to_abbrev.get(signal, signal.upper()))
    return ",".join(labels)


def _discover_files(repo: Path, config: Path | None):
    from drift.config import DriftConfig
    from drift.ingestion.file_discovery import discover_files

    cfg = DriftConfig.load(repo, config)
    return discover_files(
        repo_path=repo,
        include=cfg.include,
        exclude=cfg.exclude,
        max_files=cfg.thresholds.max_discovery_files,
        ts_enabled=cfg.languages.typescript,
        cache_dir=cfg.cache_dir,
    )


@click.group("suppress")
def suppress() -> None:
    """List and audit inline ``drift:ignore`` suppressions."""


@suppress.command("list")
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
def list_suppressions(repo: Path, config: Path | None) -> None:
    """List all inline suppression directives with optional metadata."""
    from drift.suppression import collect_inline_suppressions

    files = _discover_files(repo, config)
    entries = collect_inline_suppressions(files, repo)

    if not entries:
        console.print("[dim]No inline suppressions found.[/dim]")
        return

    signal_to_abbrev = _abbrev_from_signal_map()
    table = Table(title=f"Inline suppressions ({len(entries)})")
    table.add_column("File", overflow="fold")
    table.add_column("Line", justify="right")
    table.add_column("Signals")
    table.add_column("Until")
    table.add_column("Reason", overflow="fold")

    for entry in sorted(entries, key=lambda e: (e.file_path, e.line_number)):
        table.add_row(
            entry.file_path,
            str(entry.line_number),
            _render_signals(entry.signals, signal_to_abbrev),
            entry.until.isoformat() if entry.until else "-",
            entry.reason or "-",
        )

    console.print(table)


@suppress.command("audit")
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
    "--today",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Override current date for deterministic checks (YYYY-MM-DD).",
)
def audit_suppressions(repo: Path, config: Path | None, today: datetime | None) -> None:
    """Fail with exit code 1 when any suppression has an expired ``until`` date."""
    from drift.suppression import collect_inline_suppressions

    current_day = date.today()
    if isinstance(today, datetime):
        current_day = today.date()

    files = _discover_files(repo, config)
    entries = collect_inline_suppressions(files, repo)
    expired = [
        entry
        for entry in entries
        if entry.until is not None and entry.until < current_day
    ]

    if not expired:
        console.print("[green]No expired suppressions.[/green]")
        return

    table = Table(title=f"Expired suppressions ({len(expired)})")
    table.add_column("File", overflow="fold")
    table.add_column("Line", justify="right")
    table.add_column("Until")
    table.add_column("Reason", overflow="fold")
    for entry in sorted(expired, key=lambda e: (e.file_path, e.line_number)):
        table.add_row(
            entry.file_path,
            str(entry.line_number),
            entry.until.isoformat() if entry.until else "-",
            entry.reason or "-",
        )
    console.print(table)
    raise click.ClickException(
        f"Found {len(expired)} expired inline suppression(s)."
    )
