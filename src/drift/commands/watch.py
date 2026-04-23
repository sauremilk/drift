"""``drift watch`` — live incremental feedback during development."""

from __future__ import annotations

import contextlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from drift.commands import console
from drift.signal_mapping import signal_abbrev


@click.command("watch")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to the repository root.",
)
@click.option(
    "--debounce",
    type=float,
    default=0.5,
    help="Seconds to wait after last file change before re-analysis (default: 0.5).",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to drift config file.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Write nudge result as JSON to this file after each change. "
        "Agents and IDEs can read this file without an MCP server. "
        "Example: --output .drift/nudge.json"
    ),
)
def watch(repo: Path, debounce: float, config: Path | None, output: Path | None) -> None:
    """Watch for file changes and show incremental drift feedback.

    Runs an initial analysis to establish a baseline, then watches for
    file changes and reports new/resolved findings in real time using
    the nudge API.

    With --output, each nudge result is also written as a compact JSON
    summary so agents and IDEs can read it without an MCP server::

        drift watch --output .drift/nudge.json

    Requires the ``watchfiles`` package::

        pip install drift-analyzer[watch]

    Examples::

        drift watch                              # watch current directory
        drift watch --repo ../myproj             # watch a different repo
        drift watch --debounce 1.0               # longer debounce window
        drift watch --output .drift/nudge.json   # write JSON for agents/IDEs
    """
    try:
        from watchfiles import watch as fs_watch  # type: ignore[import-untyped]
    except ImportError:
        console.print(
            "[red]Error:[/] drift watch requires the [bold]watchfiles[/] package.\n"
            "Install it with: [bold]pip install drift-analyzer\\[watch][/bold]",
            highlight=False,
        )
        raise SystemExit(1) from None

    from drift.api.nudge import nudge
    from drift.config import DriftConfig

    repo_path = repo.resolve()
    cfg = DriftConfig.load(config or repo_path)

    # Build glob patterns for watchfiles filtering
    include_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs"}

    console.print(
        f"[bold blue]drift watch[/] — watching [bold]{repo_path}[/]",
        highlight=False,
    )
    console.print("[dim]Press Ctrl+C to stop.[/]")
    console.print()

    # Initial nudge to establish baseline
    console.print("[yellow]Running initial analysis to establish baseline...[/]")
    try:
        result = nudge(path=repo_path)
        _print_nudge_summary(result, initial=True)
        if output:
            summary = _build_nudge_summary(result, changed_files=[], initial=True)
            _write_nudge_json(summary, output)
            console.print(f"  [dim]Output written to {output}[/]", highlight=False)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Initial analysis failed:[/] {exc}")
        raise SystemExit(1) from exc

    console.print()
    console.print("[dim]Watching for file changes...[/]")

    # Resolve exclude dirs
    exclude_dirs = set(cfg.exclude) if cfg.exclude else set()
    exclude_dirs.update({
        ".git", "__pycache__", ".venv", "venv", "node_modules",
        ".drift-cache", ".mypy_cache", ".ruff_cache",
    })

    def _should_include(path: str) -> bool:
        """Filter: only source files, skip excluded dirs."""
        p = Path(path)
        # Skip excluded directories
        for part in p.relative_to(repo_path).parts:
            if part in exclude_dirs:
                return False
        return p.suffix in include_exts

    try:
        for changes in fs_watch(
            repo_path,
            debounce=int(debounce * 1000),
            recursive=True,
            step=100,
        ):
            changed_files = []
            for _change_type, path_str in changes:
                if _should_include(path_str):
                    try:
                        rel = Path(path_str).relative_to(repo_path)
                        changed_files.append(rel.as_posix())
                    except ValueError:
                        pass

            if not changed_files:
                continue

            console.print()
            console.print(
                f"[blue]⟳[/] {len(changed_files)} file(s) changed: "
                f"[dim]{', '.join(changed_files[:5])}"
                f"{'...' if len(changed_files) > 5 else ''}[/]",
                highlight=False,
            )

            try:
                result = nudge(
                    path=repo_path,
                    changed_files=changed_files,
                )
                _print_nudge_summary(result)
                if output:
                    summary = _build_nudge_summary(
                        result, changed_files=changed_files, initial=False
                    )
                    _write_nudge_json(summary, output)
            except Exception as exc:  # noqa: BLE001
                console.print(f"[red]Analysis error:[/] {exc}")
                if output:
                    error_summary = _build_nudge_summary(
                        {}, changed_files=changed_files, initial=False, error=str(exc)
                    )
                    _write_nudge_json(error_summary, output)

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching.[/]")
        raise SystemExit(0) from None


def _print_nudge_summary(result: dict, *, initial: bool = False) -> None:
    """Print a compact summary of a nudge result."""
    direction = result.get("direction", "unknown")
    delta = result.get("delta", 0.0)
    safe = result.get("safe_to_commit", False)
    new_findings = result.get("new_findings", [])
    resolved = result.get("resolved_findings", [])
    estimated_signals = _estimated_signal_labels(result)

    # Direction indicator
    if direction == "improving":
        icon = "[green]↗[/]"
    elif direction == "degrading":
        icon = "[red]↘[/]"
    elif direction == "stable":
        icon = "[dim]→[/]"
    else:
        icon = "[dim]?[/]"

    if initial:
        console.print(f"  Baseline established — direction: {icon} {direction}")
    else:
        parts = [f"  {icon} {direction}"]
        if delta:
            parts.append(f"(delta: {delta:+.3f})")
        console.print(" ".join(parts), highlight=False)

    if new_findings:
        console.print(
            f"  [red]+{len(new_findings)} new[/] finding(s)", highlight=False
        )
        for f in new_findings[:3]:
            title = f.get("title", f.get("rule_id", "unknown"))
            console.print(f"    • {title}", highlight=False)
        if len(new_findings) > 3:
            console.print(
                f"    [dim]...and {len(new_findings) - 3} more[/]",
                highlight=False,
            )

    if resolved:
        console.print(
            f"  [green]-{len(resolved)} resolved[/] finding(s)", highlight=False
        )

    if estimated_signals:
        plural = "s" if len(estimated_signals) != 1 else ""
        console.print(
            f"  [yellow]⚠ {len(estimated_signals)} cross-file signal{plural} estimated[/]: "
            f"{', '.join(estimated_signals)}",
            highlight=False,
        )
        console.print(
            "  [dim]Estimated findings come from the last baseline; "
            "run [bold]drift analyze[/] to refresh.[/]",
            highlight=False,
        )

    if safe:
        console.print("  [green]✓ safe to commit[/]", highlight=False)
    elif not initial:
        console.print("  [yellow]⚠ not safe to commit[/]", highlight=False)


def _build_nudge_summary(
    result: dict[str, Any],
    *,
    changed_files: list[str],
    initial: bool,
    error: str | None = None,
) -> dict[str, Any]:
    """Build a compact, agent-readable summary dict from a nudge result."""
    new_findings_raw = result.get("new_findings") or []
    resolved_raw = result.get("resolved_findings") or []

    new_findings = [
        {
            "rule_id": f.get("rule_id", ""),
            "title": f.get("title", ""),
            "severity": f.get("severity", ""),
        }
        for f in new_findings_raw
        if isinstance(f, dict)
    ]
    resolved_findings = [
        {"rule_id": f.get("rule_id", "")}
        for f in resolved_raw
        if isinstance(f, dict)
    ]

    return {
        "schema_version": "1",
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "changed_files": changed_files,
        "initial": initial,
        "direction": result.get("direction") if not error else None,
        "delta": result.get("delta") if not error else None,
        "safe_to_commit": result.get("safe_to_commit") if not error else None,
        "new_findings": new_findings,
        "resolved_findings": resolved_findings,
        "auto_fast_path": result.get("auto_fast_path"),
        "latency_exceeded": result.get("latency_exceeded"),
        "error": error,
    }


def _write_nudge_json(summary: dict[str, Any], output_path: Path) -> None:
    """Atomically write *summary* as JSON to *output_path*.

    Creates parent directories if needed. Uses a temp file + ``Path.replace``
    so readers never observe a partially-written file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(summary, indent=2, default=str)
    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=output_path.parent, prefix=".nudge_", suffix=".tmp"
    )
    try:
        import os

        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        Path(tmp_name).replace(output_path)
    except Exception:  # noqa: BLE001
        # Best-effort cleanup; do not propagate — watcher must not crash.
        with contextlib.suppress(OSError):
            Path(tmp_name).unlink(missing_ok=True)
        raise


def _estimated_signal_labels(result: dict) -> list[str]:
    """Return stable signal labels for estimated cross-file findings."""
    estimated_raw: list[str] = []

    direct = result.get("cross_file_signals_estimated")
    if isinstance(direct, list):
        estimated_raw.extend(str(item) for item in direct if item)

    confidence = result.get("confidence")
    if isinstance(confidence, dict):
        for signal, level in confidence.items():
            if str(level).lower() == "estimated":
                estimated_raw.append(str(signal))

    labels = {
        signal_abbrev(signal).upper()
        for signal in estimated_raw
        if signal
    }
    return sorted(labels)
