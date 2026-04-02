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
import warnings

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

# Suppress SyntaxWarnings from third-party libraries (e.g. passlib) that
# pollute stderr and confuse agents parsing CLI output.  (#72)
warnings.filterwarnings("ignore", category=SyntaxWarning, module=r"passlib\..*")


def _machine_error_enabled(argv: list[str] | None = None) -> bool:
    """Return True if CLI errors should be emitted as JSON.

    Machine-readable errors are enabled when:
    - ``DRIFT_ERROR_FORMAT=json`` is set, or
    - the active CLI invocation requests JSON output (``--json`` or
      ``--format json`` / ``--output-format json``).
    """
    if os.getenv("DRIFT_ERROR_FORMAT", "").strip().lower() == "json":
        return True

    args = list(argv if argv is not None else sys.argv[1:])
    idx = 0
    while idx < len(args):
        token = args[idx]

        if token == "--json":
            return True

        if token in {"--format", "--output-format", "-f"}:
            if idx + 1 < len(args) and args[idx + 1].strip().lower() == "json":
                return True
            idx += 2
            continue

        if token.startswith("--format=") or token.startswith("--output-format="):
            _, value = token.split("=", 1)
            if value.strip().lower() == "json":
                return True

        if token.startswith("-f="):
            _, value = token.split("=", 1)
            if value.strip().lower() == "json":
                return True

        idx += 1

    return False


def _emit_error_payload(payload: dict[str, object]) -> None:
    """Emit a single-line machine-readable error payload to stderr."""
    click.echo(json.dumps(payload, sort_keys=True), err=True)


def _build_error_payload(
    error_code: str,
    category: str,
    message: str,
    exit_code: int,
    *,
    detail: str | None = None,
    hint: str | None = None,
) -> dict[str, object]:
    """Build a v2.0 machine-readable error payload with recovery info."""
    info = ERROR_REGISTRY.get(error_code)
    recoverable = category == "user"
    suggested_action = info.action if info else hint
    return {
        "error": True,
        "schema_version": "2.0",
        "type": "error",
        "error_code": error_code,
        "category": category,
        "message": message,
        "detail": detail,
        "exit_code": exit_code,
        "hint": hint,
        "recoverable": recoverable,
        "suggested_fix": suggested_action,
        "suggested_action": suggested_action,
    }


def _configure_logging(verbose: bool = False) -> None:
    """Set up structured logging for the drift tool."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        format="%(levelname)s [%(name)s] %(message)s",
        level=level,
    )


class SuggestingGroup(click.Group):
    """Click Group that adds did-you-mean hints for unknown subcommands."""

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        command = super().get_command(ctx, cmd_name)
        if command is not None:
            return command

        matches = difflib.get_close_matches(cmd_name, self.list_commands(ctx), n=1, cutoff=0.5)
        if matches:
            raise click.UsageError(
                f"No such command '{cmd_name}'.\n  Hint: did you mean '{matches[0]}'?",
                ctx=ctx,
            )
        return None


@click.group(cls=SuggestingGroup)
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
from drift.commands.diff_cmd import diff  # noqa: E402
from drift.commands.explain import explain  # noqa: E402
from drift.commands.export_context import export_context  # noqa: E402
from drift.commands.fix_plan import fix_plan  # noqa: E402
from drift.commands.init_cmd import init  # noqa: E402
from drift.commands.mcp import mcp  # noqa: E402
from drift.commands.patterns import patterns  # noqa: E402
from drift.commands.scan import scan  # noqa: E402
from drift.commands.self_analyze import self_analyze  # noqa: E402
from drift.commands.timeline import timeline  # noqa: E402
from drift.commands.trend import trend  # noqa: E402
from drift.commands.validate_cmd import validate  # noqa: E402

main.add_command(analyze)
main.add_command(baseline)
main.add_command(init)
main.add_command(check)
main.add_command(config)
main.add_command(copilot_context)
main.add_command(diff)
main.add_command(explain)
main.add_command(export_context)
main.add_command(fix_plan)
main.add_command(mcp)
main.add_command(patterns)
main.add_command(scan)
main.add_command(timeline)
main.add_command(trend)
main.add_command(validate)
main.add_command(self_analyze)
main.add_command(badge)


def safe_main() -> None:
    """Entry point with user-friendly error handling."""
    machine_errors = _machine_error_enabled(sys.argv[1:])
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
                _build_error_payload(
                    "DRIFT-0000", "system", "Interrupted.",
                    EXIT_INTERRUPTED,
                ),
            )
        else:
            click.echo("\nInterrupted.", err=True)
        sys.exit(EXIT_INTERRUPTED)
    except DriftError as exc:
        info = ERROR_REGISTRY.get(exc.code)
        if machine_errors:
            _emit_error_payload(
                _build_error_payload(
                    exc.code,
                    info.category if info else "analysis",
                    str(exc),
                    exc.exit_code,
                    detail=exc.detail,
                    hint=exc.hint,
                ),
            )
        else:
            click.echo(exc.detail, err=True)
        sys.exit(exc.exit_code)
    except FileNotFoundError as exc:
        if machine_errors:
            _emit_error_payload(
                _build_error_payload(
                    "DRIFT-2001", "system", str(exc),
                    EXIT_SYSTEM_ERROR,
                    detail=f"[DRIFT-2001] {exc}",
                ),
            )
        else:
            click.echo(f"[DRIFT-2001] {exc}", err=True)
        sys.exit(EXIT_SYSTEM_ERROR)
    except Exception as exc:
        if machine_errors:
            _emit_error_payload(
                _build_error_payload(
                    "DRIFT-3002", "analysis", str(exc),
                    EXIT_ANALYSIS_ERROR,
                    detail=f"[DRIFT-3002] {exc}",
                    hint="Run with -v for the full traceback.",
                ),
            )
        else:
            click.echo(f"[DRIFT-3002] {exc}", err=True)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                import traceback

                traceback.print_exc()
            else:
                click.echo("Hint: run with -v for the full traceback.", err=True)
        sys.exit(EXIT_ANALYSIS_ERROR)


def _handle_click_error(exc: click.ClickException) -> None:
    """Add did-you-mean suggestions for unknown options and commands."""
    if not isinstance(exc, click.UsageError):
        return
    msg = str(exc.format_message())
    ctx = exc.ctx
    command = ctx.command if ctx is not None else None

    if "No such option:" in msg or "no such option:" in msg:
        if command is None:
            return
        # Extract the bad option from the message.
        for part in msg.split():
            if part.startswith("-"):
                bad_option = part.rstrip(".")
                break
        else:
            return

        known: list[str] = []
        for param in command.params:
            known.extend(param.opts)
            known.extend(param.secondary_opts)

        matches = difflib.get_close_matches(bad_option, known, n=1, cutoff=0.5)
        if matches:
            exc.message = (
                f"{exc.format_message().rstrip()}\n"
                f"  Hint: did you mean '{matches[0]}'?"
            )
        return

    if "No such command" in msg or "no such command" in msg:
        # Click stores subcommands on Group.commands.
        known_commands = list(getattr(command, "commands", {}).keys())
        if not known_commands:
            known_commands = list(getattr(main, "commands", {}).keys())
        if not known_commands:
            return

        bad_command = ""
        marker = "No such command "
        lower_msg = msg.lower()
        idx = lower_msg.find(marker.lower())
        if idx != -1:
            tail = msg[idx + len(marker):].strip()
            bad_command = tail.strip("'\".")

        if not bad_command:
            return

        matches = difflib.get_close_matches(bad_command, known_commands, n=1, cutoff=0.5)
        if matches:
            exc.message = (
                f"{exc.format_message().rstrip()}\n"
                f"  Hint: did you mean '{matches[0]}'?"
            )


if __name__ == "__main__":
    safe_main()
