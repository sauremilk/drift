"""Subprocess runner for 'run' and 'plugin' tier integrations.

This module is intentionally minimal:
  - Sequential execution only (no threads/parallelism in Phase 1)
  - Hard timeout via subprocess.run()
  - Errors produce an empty IntegrationResult + warning log, never abort
"""

from __future__ import annotations

import json
import logging
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Raw subprocess result
# ---------------------------------------------------------------------------


@dataclass
class SubprocessResult:
    """Raw result from running an external command."""

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


def run_command(
    command: list[str],
    *,
    repo_path: Path,
    timeout_seconds: int = 30,
) -> SubprocessResult:
    """Run *command* with *timeout_seconds*, substituting ``{repo_path}``.

    ``{repo_path}`` in any argument is replaced with the absolute
    POSIX path of the repository root.  This is the only supported
    placeholder — no shell expansion, no glob patterns.

    Returns a ``SubprocessResult`` regardless of exit code.  Callers
    are responsible for interpreting the exit code and output.

    This function never raises; all exceptions are caught and logged.
    """
    repo_posix = str(repo_path.resolve())
    expanded = [arg.replace("{repo_path}", repo_posix) for arg in command]

    logger.debug(
        "integration runner: %s (timeout=%ds)",
        shlex.join(expanded),
        timeout_seconds,
    )

    try:
        proc = subprocess.run(  # noqa: S603
            expanded,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return SubprocessResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
        )
    except subprocess.TimeoutExpired as exc:
        logger.warning(
            "integration '%s' timed out after %ds.",
            shlex.join(expanded[:2]),
            timeout_seconds,
        )
        return SubprocessResult(
            stdout="",
            stderr=str(exc),
            exit_code=-1,
            timed_out=True,
        )
    except FileNotFoundError:
        cmd_name = expanded[0] if expanded else "<empty>"
        logger.warning(
            "integration command not found: %r. Is the tool installed?",
            cmd_name,
        )
        return SubprocessResult(stdout="", stderr="command not found", exit_code=127)
    except Exception:  # noqa: BLE001
        logger.warning(
            "integration command failed unexpectedly.",
            exc_info=True,
        )
        return SubprocessResult(stdout="", stderr="unexpected error", exit_code=-2)


# ---------------------------------------------------------------------------
# JSON output parsing helpers
# ---------------------------------------------------------------------------


def parse_json_output(raw: str) -> list[dict] | dict | None:
    """Parse JSON from *raw*, returning None on failure.

    Tolerates trailing non-JSON text (e.g. Rich console output) by
    extracting from the first ``[`` or ``{`` to the matching close bracket.
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    for start_char, end_char in (("[", "]"), ("{", "}")):
        start = text.find(start_char)
        if start == -1:
            continue
        end = text.rfind(end_char)
        if end <= start:
            continue
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            continue
    logger.debug("Could not parse JSON from integration output: %r", text[:200])
    return None


# ---------------------------------------------------------------------------
# Delegating top-level runner (called from integrations package)
# ---------------------------------------------------------------------------


def run_integrations(
    repo_path: Path,
    findings: list,
    config: object,
) -> list:
    """Discover active adapters and run them.

    Returns a flat list of ``IntegrationResult`` objects.
    Adapters that are unavailable or disabled are silently skipped.

    This is the entry-point called from the analysis pipeline.
    """
    from drift.integrations.registry import get_registry

    # Access the integrations config; guard for configs without the field.
    integrations_cfg = getattr(config, "integrations", None)
    if integrations_cfg is None or not getattr(integrations_cfg, "enabled", False):
        return []

    from drift.integrations.base import IntegrationContext

    ctx = IntegrationContext(
        repo_path=Path(repo_path),
        findings=findings,
        config=config,  # type: ignore[arg-type]
    )

    registry = get_registry(config)
    active_signal_types = {f.signal_type for f in findings}
    results = []

    for adapter in registry:
        if not adapter.enabled:
            continue
        triggers = set(adapter.trigger_signals)
        # '*' means trigger on any finding present, or even no findings
        if "*" not in triggers and not triggers.intersection(active_signal_types):
            continue
        if not adapter.is_available():
            logger.debug(
                "integration '%s' skipped: is_available() returned False.",
                adapter.name,
            )
            continue
        try:
            result = adapter.run(ctx)
            results.append(result)
        except Exception:  # noqa: BLE001
            logger.warning(
                "integration '%s' raised an unexpected exception.",
                adapter.name,
                exc_info=True,
            )

    return results
