"""Drift CLI — command line interface.

This module defines the top-level Click group and registers subcommands
from ``drift.commands.*``.  Individual command logic lives in separate
modules under ``src/drift/commands/`` to keep each file focused.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import sys

import click

from drift import __version__
from drift.commands import console  # noqa: F401 — re-export for backwards compat
from drift.errors import (
    ERROR_REGISTRY,
    EXIT_ANALYSIS_ERROR,
    EXIT_INTERRUPTED,
    EXIT_SYSTEM_ERROR,
    DriftError,
)


def _machine_error_enabled() -> bool:
    """Return True if CLI errors should be emitted as JSON."""
    return os.getenv("DRIFT_ERROR_FORMAT", "").strip().lower() == "json"


def _emit_error_payload(payload: dict[str, object]) -> None:
    """Emit a single-line machine-readable error payload to stderr."""
    click.echo(json.dumps(payload, sort_keys=True), err=True)


def _configure_logging(verbose: bool = False) -> None:
    """Set up structured logging for the drift tool."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        format="%(levelname)s [%(name)s] %(message)s",
        level=level,
    )


@click.group()
@click.version_option(version=__version__, prog_name="drift")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable debug logging.")
def main(verbose: bool = False) -> None:
    """Drift — Detect architectural erosion from AI-generated code."""
    _configure_logging(verbose)


# --- Register subcommands -------------------------------------------------
from drift.commands.analyze import analyze  # noqa: E402
from drift.commands.badge import badge  # noqa: E402
from drift.commands.baseline import baseline  # noqa: E402
from drift.commands.check import check  # noqa: E402
from drift.commands.config_cmd import config  # noqa: E402
from drift.commands.copilot_context import copilot_context  # noqa: E402
from drift.commands.explain import explain  # noqa: E402
from drift.commands.mcp import mcp  # noqa: E402
from drift.commands.patterns import patterns  # noqa: E402
from drift.commands.self_analyze import self_analyze  # noqa: E402
from drift.commands.timeline import timeline  # noqa: E402
from drift.commands.trend import trend  # noqa: E402

main.add_command(analyze)
main.add_command(baseline)
main.add_command(check)
main.add_command(config)
main.add_command(copilot_context)
main.add_command(explain)
main.add_command(mcp)
main.add_command(patterns)
main.add_command(timeline)
main.add_command(trend)
main.add_command(self_analyze)
main.add_command(badge)


def safe_main() -> None:
    """Entry point with user-friendly error handling."""
    machine_errors = _machine_error_enabled()
    try:
        main(standalone_mode=True)
    except click.exceptions.Exit:
        raise
    except click.ClickException as exc:
        # Enhance "no such option" with did-you-mean suggestions
        _handle_click_error(exc)
        raise
    except KeyboardInterrupt:
        if machine_errors:
            _emit_error_payload(
                {
                    "schema_version": "1.0",
                    "type": "error",
                    "error_code": "DRIFT-0000",
                    "category": "system",
                    "message": "Interrupted.",
                    "exit_code": EXIT_INTERRUPTED,
                    "hint": None,
                },
            )
        else:
            click.echo("\nInterrupted.", err=True)
        sys.exit(EXIT_INTERRUPTED)
    except DriftError as exc:
        info = ERROR_REGISTRY.get(exc.code)
        if machine_errors:
            _emit_error_payload(
                {
                    "schema_version": "1.0",
                    "type": "error",
                    "error_code": exc.code,
                    "category": info.category if info else "analysis",
                    "message": str(exc),
                    "detail": exc.detail,
                    "exit_code": exc.exit_code,
                    "hint": exc.hint,
                },
            )
        else:
            click.echo(exc.detail, err=True)
        sys.exit(exc.exit_code)
    except FileNotFoundError as exc:
        if machine_errors:
            _emit_error_payload(
                {
                    "schema_version": "1.0",
                    "type": "error",
                    "error_code": "DRIFT-2001",
                    "category": "system",
                    "message": str(exc),
                    "detail": f"[DRIFT-2001] {exc}",
                    "exit_code": EXIT_SYSTEM_ERROR,
                    "hint": None,
                },
            )
        else:
            click.echo(f"[DRIFT-2001] {exc}", err=True)
        sys.exit(EXIT_SYSTEM_ERROR)
    except Exception as exc:
        if machine_errors:
            _emit_error_payload(
                {
                    "schema_version": "1.0",
                    "type": "error",
                    "error_code": "DRIFT-3002",
                    "category": "analysis",
                    "message": str(exc),
                    "detail": f"[DRIFT-2003] {exc}",
                    "exit_code": EXIT_ANALYSIS_ERROR,
                    "hint": "Run with -v for the full traceback.",
                },
            )
        else:
            click.echo(f"[DRIFT-2003] {exc}", err=True)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                import traceback

                traceback.print_exc()
            else:
                click.echo("Hint: run with -v for the full traceback.", err=True)
        sys.exit(EXIT_ANALYSIS_ERROR)


def _handle_click_error(exc: click.ClickException) -> None:
    """Add did-you-mean suggestions for unknown options."""
    if not isinstance(exc, click.UsageError):
        return
    msg = str(exc.format_message())
    if "No such option:" not in msg and "no such option:" not in msg:
        return
    # Extract the bad option from the message
    for part in msg.split():
        if part.startswith("-"):
            bad_option = part.rstrip(".")
            break
    else:
        return

    # Collect known options from the failed command's context
    ctx = exc.ctx
    if ctx is None or ctx.command is None:
        return
    known = []
    for param in ctx.command.params:
        known.extend(param.opts)
        known.extend(param.secondary_opts)

    matches = difflib.get_close_matches(bad_option, known, n=1, cutoff=0.5)
    if matches:
        exc.message = (
            f"{exc.format_message().rstrip()}\n"
            f"  Hint: did you mean '{matches[0]}'?"
        )


if __name__ == "__main__":
    safe_main()
