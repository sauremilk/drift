"""Drift CLI — command line interface.

This module defines the top-level Click group and registers subcommands
from ``drift.commands.*``.  Individual command logic lives in separate
modules under ``src/drift/commands/`` to keep each file focused.
"""

from __future__ import annotations

import logging
import sys

import click

from drift import __version__
from drift.commands import console  # noqa: F401 — re-export for backwards compat


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
from drift.commands.check import check  # noqa: E402
from drift.commands.patterns import patterns  # noqa: E402
from drift.commands.self_analyze import self_analyze  # noqa: E402
from drift.commands.timeline import timeline  # noqa: E402
from drift.commands.trend import trend  # noqa: E402

main.add_command(analyze)
main.add_command(check)
main.add_command(patterns)
main.add_command(timeline)
main.add_command(trend)
main.add_command(self_analyze)
main.add_command(badge)


def safe_main() -> None:
    """Entry point with user-friendly error handling."""
    try:
        main(standalone_mode=True)
    except click.exceptions.Exit:
        raise
    except click.ClickException:
        raise
    except KeyboardInterrupt:
        click.echo("\nInterrupted.", err=True)
        sys.exit(130)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            import traceback

            traceback.print_exc()
        else:
            click.echo("Hint: run with -v for the full traceback.", err=True)
        sys.exit(1)


if __name__ == "__main__":
    safe_main()
