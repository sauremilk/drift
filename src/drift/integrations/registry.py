"""Integration adapter registry.

Discovery order:
  1. Built-in adapters (drift.integrations.builtin.*)
  2. Entry-point adapters (group ``drift.integrations``)
  3. YAML-declared adapters (drift.yaml → integrations.adapters)

YAML-declared adapters with ``tier: run`` or ``tier: plugin`` are
materialised as ``YamlIntegrationAdapter`` instances so they can be
used without writing Python code.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any

from drift.integrations.base import IntegrationAdapter, IntegrationContext, IntegrationResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

INTEGRATION_GROUP = "drift.integrations"


# ---------------------------------------------------------------------------
# YAML adapter: materialised from drift.yaml → integrations.adapters
# ---------------------------------------------------------------------------


class YamlIntegrationAdapter:
    """An integration adapter built entirely from drift.yaml config.

    Supports hint, run, and plugin tiers without Python code.
    """

    def __init__(self, cfg: Any) -> None:
        self.name: str = cfg.name
        self.tier = cfg.tier
        self.enabled: bool = cfg.enabled
        self.trigger_signals: list[str] = list(cfg.trigger_signals)
        self._command: list[str] = list(cfg.command)
        self._timeout: int = cfg.timeout_seconds
        self._output_format: str = cfg.output_format
        self._hint_text: str | None = cfg.hint_text
        self._severity_map: dict[str, str] = cfg.severity_map.model_dump()

    def is_available(self) -> bool:
        if self.tier == "hint":
            return True
        import shutil

        return bool(self._command) and shutil.which(self._command[0]) is not None

    def run(self, ctx: IntegrationContext) -> IntegrationResult:
        if self.tier == "hint":
            return IntegrationResult(
                source=self.name,
                hint_text=self._hint_text or f"Consider running {self.name}.",
            )

        from drift.integrations.runner import parse_json_output, run_command

        sub = run_command(
            self._command,
            repo_path=ctx.repo_path,
            timeout_seconds=self._timeout,
        )
        if sub.exit_code == 127 or sub.timed_out:
            return IntegrationResult(
                source=self.name,
                summary=f"{self.name}: invocation failed (exit {sub.exit_code}).",
                raw_output=sub.stderr,
            )

        findings: list = []
        if self._output_format == "json":
            parsed = parse_json_output(sub.stdout)
            if parsed is not None:
                findings = _map_generic_json(
                    parsed, source=self.name, severity_map=self._severity_map
                )

        return IntegrationResult(
            source=self.name,
            findings=findings,
            raw_output=sub.stdout,
            summary=f"{self.name}: {len(findings)} finding(s).",
        )


# ---------------------------------------------------------------------------
# Generic JSON → Finding mapper for YAML adapters
# ---------------------------------------------------------------------------


def _map_generic_json(
    data: list | dict,
    *,
    source: str,
    severity_map: dict[str, str],
) -> list:
    """Attempt a best-effort mapping of JSON output to Finding objects.

    Supports arrays of objects with common keys (``message``, ``file``,
    ``line``, ``severity``/``level``/``type``).
    """
    from pathlib import Path

    from drift.models import Finding
    from drift.models._enums import Severity

    items = data if isinstance(data, list) else [data]
    findings = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_severity = (
            item.get("severity")
            or item.get("level")
            or item.get("type")
            or "info"
        )
        mapped = severity_map.get(str(raw_severity).lower(), "info")
        try:
            severity = Severity(mapped)
        except ValueError:
            severity = Severity.INFO

        file_str = item.get("file") or item.get("path") or item.get("filename")
        file_path = Path(file_str) if file_str else None

        findings.append(
            Finding(
                signal_type=source,
                severity=severity,
                score=0.0,
                title=str(item.get("message") or item.get("msg") or item.get("text") or source),
                description=str(
                    item.get("description") or item.get("details") or item.get("message") or ""
                ),
                file_path=file_path,
                start_line=item.get("line") or item.get("start_line"),
                metadata={
                    "integration_source": source,
                    "integration_tier": "run",
                    "raw": item,
                },
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Registry builder
# ---------------------------------------------------------------------------


def get_registry(config: Any = None) -> list[IntegrationAdapter]:
    """Return the list of available integration adapters.

    Sources (in order):
      1. Built-in adapters
      2. Entry-point adapters (``drift.integrations`` group)
      3. YAML-declared adapters from *config*

    Duplicate names (by ``adapter.name``) are deduplicated: later
    entries win, allowing user YAML to override built-ins.
    """
    adapters: dict[str, IntegrationAdapter] = {}

    # 1. Built-in adapters
    for adapter in _load_builtins():
        adapters[adapter.name] = adapter  # type: ignore[assignment]

    # 2. Entry-point adapters
    for adapter in _load_entry_points():
        adapters[adapter.name] = adapter  # type: ignore[assignment]

    # 3. YAML-declared adapters
    if config is not None:
        integrations_cfg = getattr(config, "integrations", None)
        if integrations_cfg is not None:
            for adapter_cfg in getattr(integrations_cfg, "adapters", []):
                yaml_adapter = YamlIntegrationAdapter(adapter_cfg)
                adapters[yaml_adapter.name] = yaml_adapter  # type: ignore[assignment]

    return list(adapters.values())


# ---------------------------------------------------------------------------
# Loader helpers
# ---------------------------------------------------------------------------


def _load_builtins() -> list:
    """Load all built-in integration adapters."""
    from drift.integrations.builtin.superpowers import SuperpowersAdapter

    return [SuperpowersAdapter()]


def _load_entry_points() -> list:
    """Load integration adapters from ``drift.integrations`` entry points."""
    loaded = []
    try:
        eps = entry_points(group=INTEGRATION_GROUP)
    except Exception:  # noqa: BLE001
        logger.debug("Could not load drift.integrations entry points.", exc_info=True)
        return []

    for ep in eps:
        try:
            adapter = ep.load()
            if isinstance(adapter, type):
                adapter = adapter()
            loaded.append(adapter)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Integration entry point %r failed to load; skipping.",
                ep.value,
                exc_info=True,
            )
    return loaded
