"""drift suppress — inspect and audit inline suppression directives."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import click
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from drift.commands import console
from drift.models import Finding


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
@click.option(
    "--check-stale",
    is_flag=True,
    default=False,
    help=(
        "Highlight suppressions whose code content has changed since the "
        "suppression was written (requires the hash: tag in the comment; "
        "use drift suppress insert --include-hash to embed it)."
    ),
)
def list_suppressions(repo: Path, config: Path | None, check_stale: bool) -> None:
    """List all inline suppression directives with optional staleness metadata."""
    from drift.suppression import collect_inline_suppressions

    files = _discover_files(repo, config)
    entries = collect_inline_suppressions(files, repo)

    if not entries:
        console.print("[dim]No inline suppressions found.[/dim]")
        return

    signal_to_abbrev = _abbrev_from_signal_map()

    stale_entries = []
    if check_stale:
        stale_entries = [
            e for e in entries
            if e.stored_hash is not None and e.current_hash != e.stored_hash
        ]
        hashless = [e for e in entries if e.stored_hash is None]

    table = Table(title=f"Inline suppressions ({len(entries)})")
    table.add_column("File", overflow="fold")
    table.add_column("Line", justify="right")
    table.add_column("Signals")
    table.add_column("Until")
    table.add_column("Reason", overflow="fold")
    if check_stale:
        table.add_column("Stale?")

    for entry in sorted(entries, key=lambda e: (e.file_path, e.line_number)):
        is_stale = (
            check_stale
            and entry.stored_hash is not None
            and entry.current_hash != entry.stored_hash
        )
        row = [
            entry.file_path,
            str(entry.line_number),
            _render_signals(entry.signals, signal_to_abbrev),
            entry.until.isoformat() if entry.until else "-",
            entry.reason or "-",
        ]
        if check_stale:
            if is_stale:
                row.append("[bold red]STALE[/bold red]")
            elif entry.stored_hash is None:
                row.append("[dim]no hash[/dim]")
            else:
                row.append("[green]ok[/green]")
        table.add_row(*row)

    console.print(table)

    if check_stale:
        if stale_entries:
            console.print(
                f"\n[bold red]{len(stale_entries)} stale suppression(s) detected.[/bold red] "
                "The code at these lines has changed since the suppression was added. "
                "Review whether the suppression is still justified."
            )
        if hashless:
            console.print(
                f"\n[dim]{len(hashless)} suppression(s) have no embedded hash "
                "and cannot be checked for staleness. Re-add them with "
                "`drift suppress interactive` "
                "(or `insert_suppression_comment(..., include_hash=True)`) "
                "to enable future staleness detection.[/dim]"
            )


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


# ---------------------------------------------------------------------------
# Interactive triage
# ---------------------------------------------------------------------------

_TRIAGE_CHOICES = "[y]es(+90d) / [a]lways / [n]o / [s]kip / [q]uit"
_TEMPORAL_DAYS = 90


def _read_source_lines(file_path: Path, start_line: int | None, context: int = 2) -> str | None:
    """Return a few lines around *start_line* from *file_path*, or ``None``."""
    if start_line is None or not file_path.is_file():
        return None
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    first = max(0, start_line - 1 - context)
    last = min(len(lines), start_line + context)
    return "\n".join(lines[first:last])


def _infer_language(file_path: Path | None) -> str:
    if file_path is None:
        return "python"
    suffix = file_path.suffix.lower()
    return {
        ".py": "python",
        ".pyi": "python",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "jsx",
    }.get(suffix, "python")


def _prompt_choice(prompt: str) -> str:
    """Read a single choice character from stdin (case-insensitive)."""
    raw = click.prompt(prompt, default="", show_default=False).strip().lower()
    return raw[:1] if raw else ""


def _display_finding(finding: Finding, idx: int, total: int, repo: Path) -> None:
    """Print panel and optional code snippet for one triage finding."""
    file_rel = finding.file_path.as_posix() if finding.file_path else "<unknown>"
    line_info = f":{finding.start_line}" if finding.start_line else ""
    signal_abbrev = _abbrev_from_signal_map()
    signal_label = signal_abbrev.get(finding.signal_type, finding.signal_type.upper())

    snippet: str | None = None
    if finding.file_path:
        abs_path = (
            repo / finding.file_path
            if not finding.file_path.is_absolute()
            else finding.file_path
        )
        snippet = _read_source_lines(abs_path, finding.start_line)

    details = (
        f"[bold]{signal_label}[/bold]  "
        f"[dim]{file_rel}{line_info}[/dim]  "
        f"score=[cyan]{finding.score:.2f}[/cyan]\n"
        f"{finding.title}"
    )
    if finding.description and finding.description != finding.title:
        details += f"\n[dim]{finding.description}[/dim]"

    console.print(Panel(details, title=f"Finding {idx}/{total}", border_style="blue"))

    if snippet:
        lang = finding.language or _infer_language(finding.file_path)
        console.print(
            Syntax(
                snippet,
                lang,
                line_numbers=True,
                start_line=max(1, (finding.start_line or 1) - 2),
            )
        )


def _apply_triage_suppress(
    finding: Finding,
    repo: Path,
    dry_run: bool,
    choice: str,
    temporal_days: int,
) -> tuple[int, int]:
    """Handle y/a choice: prompt for reason, insert suppression comment.

    Returns (suppressed_delta, skipped_delta).
    """
    from drift.suppression import insert_suppression_comment

    signal_abbrev = _abbrev_from_signal_map()
    signal_label = signal_abbrev.get(finding.signal_type, finding.signal_type.upper())

    reason_raw = click.prompt("  reason (optional, Enter to skip)", default="").strip()
    reason: str | None = reason_raw if reason_raw else None
    until: date | None = (
        date.today() + timedelta(days=temporal_days) if choice == "y" else None
    )
    signals: set[str] | None = {str(finding.signal_type)} if finding.signal_type else None
    language = finding.language or _infer_language(finding.file_path)

    if finding.file_path and finding.start_line is not None:
        abs_path = (
            repo / finding.file_path
            if not finding.file_path.is_absolute()
            else finding.file_path
        )
        if not dry_run:
            insert_suppression_comment(
                abs_path,
                line_number=finding.start_line,
                signals=signals,
                until=until,
                reason=reason,
                language=language,
            )
        label = "until:" + until.isoformat() if until else "permanent"
        mode = "[dim](dry-run)[/dim] " if dry_run else ""
        console.print(f"  {mode}[green]Suppressed[/green] [{signal_label}] {label}")
        return 1, 0
    console.print("  [yellow]Cannot suppress — no file/line information.[/yellow]")
    return 0, 1


@suppress.command("interactive")
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
    "--since",
    default=90,
    type=int,
    help="Days of git history to consider (default: 90).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show decisions without writing any changes to disk.",
)
def interactive(repo: Path, config: Path | None, since: int, dry_run: bool) -> None:
    """Interactive triage — review each finding and add suppress comments.

    \b
    For each active finding you are prompted:
      [y]  suppress temporarily (``until:+90d``)
      [a]  suppress permanently (no expiry)
      [n]  do not suppress
      [s]  skip (decide later)
      [q]  quit immediately

    Use ``--dry-run`` to preview decisions without touching any files.
    """
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig

    if dry_run:
        console.print("[bold yellow]Dry-run mode — no files will be modified.[/bold yellow]")

    repo = repo.resolve()
    cfg = DriftConfig.load(repo, config)

    with console.status("[bold]Running analysis…[/bold]"):
        analysis = analyze_repo(repo, config=cfg, since_days=since)

    active = [f for f in analysis.findings if f.status.value == "active"]
    total = len(active)

    if not total:
        console.print("[green]No active findings to triage.[/green]")
        return

    console.print(f"\n[bold]{total} active finding(s)[/bold] — {_TRIAGE_CHOICES}\n")

    suppressed_count = 0
    skipped_count = 0

    for idx, finding in enumerate(active, start=1):
        _display_finding(finding, idx, total, repo)
        choice = _prompt_choice(_TRIAGE_CHOICES + " > ")

        if choice == "q":
            console.print("[dim]Quit.[/dim]")
            break

        if choice in ("y", "a"):
            s_delta, sk_delta = _apply_triage_suppress(
                finding, repo, dry_run, choice, _TEMPORAL_DAYS
            )
            suppressed_count += s_delta
            skipped_count += sk_delta
        elif choice == "n":
            console.print("  [dim]Kept active.[/dim]")
        elif choice == "s":
            console.print("  [dim]Skipped.[/dim]")
            skipped_count += 1
        else:
            console.print("  [dim]Unknown choice — skipped.[/dim]")
            skipped_count += 1

        console.print()

    dry_label = " (dry-run)" if dry_run else ""
    console.print(
        f"[bold]Done{dry_label}.[/bold] "
        f"{suppressed_count} suppressed, {skipped_count} skipped, "
        f"{total - suppressed_count - skipped_count} kept active."
    )
