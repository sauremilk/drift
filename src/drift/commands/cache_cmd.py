"""drift cache — cache inspection and management subcommands."""

from __future__ import annotations

from pathlib import Path

import click

from drift.commands import make_console


@click.group("cache", hidden=True)
def cache() -> None:
    """Manage the drift parse and signal cache."""


@cache.command("clear")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root (default: current directory).",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to drift.yaml config file.",
)
@click.option(
    "--parse-only",
    "parse_only",
    is_flag=True,
    default=False,
    help="Clear only parse cache entries.",
)
@click.option(
    "--signal-only",
    "signal_only",
    is_flag=True,
    default=False,
    help="Clear only signal cache entries.",
)
@click.option(
    "--dry-run",
    "dry_run",
    is_flag=True,
    default=False,
    help="Preview what would be deleted without removing any files.",
)
def clear(
    repo: Path,
    config: Path | None,
    parse_only: bool,
    signal_only: bool,
    dry_run: bool,
) -> None:
    """Clear parse and/or signal cache entries.

    \b
    Examples:
      drift cache clear                   # clear all cache entries
      drift cache clear --parse-only      # clear only parse entries
      drift cache clear --signal-only     # clear only signal entries
      drift cache clear --dry-run         # preview without deleting
    """
    from drift.config import DriftConfig

    console = make_console()

    if parse_only and signal_only:
        raise click.UsageError("--parse-only and --signal-only are mutually exclusive.")

    cfg = DriftConfig.load(repo, config)
    cache_root = repo.resolve() / cfg.cache_dir

    clear_parse = not signal_only
    clear_signals = not parse_only

    parse_dir = cache_root / "parse"
    signals_dir = cache_root / "signals"

    def _count_and_remove(directory: Path, *, dry: bool) -> int:
        if not directory.exists():
            return 0
        entries = list(directory.glob("*.json"))
        if not dry:
            import contextlib
            for entry in entries:
                with contextlib.suppress(OSError):
                    entry.unlink(missing_ok=True)
        return len(entries)

    parse_count = 0
    signal_count = 0

    if clear_parse:
        parse_count = _count_and_remove(parse_dir, dry=dry_run)
    if clear_signals:
        signal_count = _count_and_remove(signals_dir, dry=dry_run)

    prefix = "[dim]Would clear[/dim]" if dry_run else "Cleared"
    parts: list[str] = []
    if clear_parse:
        parts.append(f"{parse_count} parse entr{'y' if parse_count == 1 else 'ies'}")
    if clear_signals:
        parts.append(f"{signal_count} signal entr{'y' if signal_count == 1 else 'ies'}")

    summary = " and ".join(parts)
    cache_dir_display = cfg.cache_dir

    if dry_run:
        console.print(
            f"[bold yellow]dry-run:[/bold yellow] would clear {summary} "
            f"from [cyan]{cache_dir_display}[/cyan]"
        )
    else:
        console.print(
            f"{prefix} {summary} from [cyan]{cache_dir_display}[/cyan]"
        )
