"""Plugin discovery for Drift.

Drift supports three extension points via Python entry_points (PEP 517/621):

  drift.signals   — Custom signal classes (subclass BaseSignal + register via
                    register_signal decorator from drift.signals.base)
  drift.output    — Custom output format modules (must expose ``format_results``)
  drift.commands  — Custom Click commands (must expose a ``command`` attribute)

Plugins are discovered at analysis time and installed alongside drift-analyzer.
Drift trusts code from installed packages the same way it trusts its own code.

Example ``pyproject.toml`` for a plugin package::

    [project.entry-points."drift.signals"]
    my_signal = "my_package.signals:MySignal"

    [project.entry-points."drift.output"]
    my_format = "my_package.output:format_results"

    [project.entry-points."drift.commands"]
    my_cmd = "my_package.commands:command"
"""

from __future__ import annotations

import logging
from importlib.metadata import EntryPoint, entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from click import Command

logger = logging.getLogger(__name__)

# Entry-point group names — stable public API
SIGNAL_GROUP: str = "drift.signals"
OUTPUT_GROUP: str = "drift.output"
COMMAND_GROUP: str = "drift.commands"


def _load_entry_points(group: str) -> list[EntryPoint]:
    """Return entry points for the given group, empty list on failure."""
    try:
        eps = entry_points(group=group)
        return list(eps)
    except Exception:  # noqa: BLE001
        logger.debug("Could not load entry points for group %r", group, exc_info=True)
        return []


def discover_signal_plugins() -> list[type]:
    """Discover and return signal classes registered under 'drift.signals'.

    Each entry point must point to a class that:
    - subclasses ``drift.signals.base.BaseSignal``
    - is decorated with ``@register_signal`` (or calls ``register_signal_meta``
      from ``drift.signal_registry``)

    Returns a list of loaded signal classes. Failed entry points are
    logged and skipped — they do not abort the analysis.
    """
    from drift.signals.base import BaseSignal

    loaded: list[type] = []
    for ep in _load_entry_points(SIGNAL_GROUP):
        try:
            cls = ep.load()
        except Exception:  # noqa: BLE001
            logger.warning(
                "Plugin signal entry point %r failed to load; skipping.",
                ep.value,
                exc_info=True,
            )
            continue

        if not (isinstance(cls, type) and issubclass(cls, BaseSignal)):
            logger.warning(
                "Plugin signal %r is not a BaseSignal subclass; skipping.",
                ep.value,
            )
            continue

        loaded.append(cls)
        logger.debug("Loaded plugin signal: %s", cls.__name__)

    return loaded


def discover_output_plugins() -> dict[str, object]:
    """Discover output formatter modules registered under 'drift.output'.

    Each entry point must point to a callable ``format_results(findings, ...)``
    or a module that exposes such a callable.

    Returns a dict of {name: formatter} for successfully loaded plugins.
    """
    loaded: dict[str, object] = {}
    for ep in _load_entry_points(OUTPUT_GROUP):
        try:
            formatter = ep.load()
        except Exception:  # noqa: BLE001
            logger.warning(
                "Plugin output entry point %r failed to load; skipping.",
                ep.value,
                exc_info=True,
            )
            continue

        loaded[ep.name] = formatter
        logger.debug("Loaded plugin output formatter: %s", ep.name)

    return loaded


def discover_command_plugins() -> list[Command]:
    """Discover and load CLI commands registered under 'drift.commands'.

    Each entry point must point to a ``click.BaseCommand`` instance
    exposed as a module-level ``command`` attribute.

    Returns a list of loaded Click commands.
    """
    import click as _click  # lazy import to keep module lightweight

    loaded: list[Command] = []
    for ep in _load_entry_points(COMMAND_GROUP):
        try:
            obj = ep.load()
        except Exception:  # noqa: BLE001
            logger.warning(
                "Plugin command entry point %r failed to load; skipping.",
                ep.value,
                exc_info=True,
            )
            continue

        if not isinstance(obj, _click.Command):
            logger.warning(
                "Plugin command %r is not a click.Command; skipping.",
                ep.value,
            )
            continue

        loaded.append(obj)
        logger.debug("Loaded plugin command: %s", obj.name)

    return loaded


def load_all_plugins() -> None:
    """Discover and register all plugins in one call.

    Intended to be called once during CLI/API startup. Safe to call
    multiple times — subsequent calls are idempotent because
    ``register_signal`` and ``register_signal_meta`` deduplicate.
    """
    from drift.signals.base import register_signal

    for cls in discover_signal_plugins():
        # register_signal may already have been called by the decorator —
        # calling it again is safe (it adds the class again) so we rely on
        # the class itself having used @register_signal.
        # If it hasn't, register it here as a fallback.
        from drift.signals.base import _SIGNAL_REGISTRY  # noqa: PLC0415

        if cls not in _SIGNAL_REGISTRY:
            register_signal(cls)

    # Output and command plugins are discovered on-demand by their consumers.
    # We do not auto-register them here to avoid side effects.
