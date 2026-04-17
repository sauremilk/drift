"""Protocol, context, and result types for Drift integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from drift.config import DriftConfig
    from drift.models import Finding


# ---------------------------------------------------------------------------
# Integration context (passed to every adapter.run())
# ---------------------------------------------------------------------------


@dataclass
class IntegrationContext:
    """Runtime context given to an adapter when Drift invokes it."""

    repo_path: Path
    findings: list[Finding]
    config: DriftConfig
    timeout_seconds: int = 30


# ---------------------------------------------------------------------------
# Integration result
# ---------------------------------------------------------------------------


@dataclass
class IntegrationResult:
    """Adapter output — findings plus optional free-text summary."""

    source: str
    findings: list[Finding] = field(default_factory=list)
    summary: str | None = None
    raw_output: str | None = None
    # For hint-tier adapters: a formatted hint string to render in reports.
    hint_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Adapter protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class IntegrationAdapter(Protocol):
    """Minimal contract every integration adapter must satisfy.

    Adapters are thin wrappers — they must not re-implement external tool
    logic, only invoke the tool and map its output to Drift findings.

    Integration tiers:
      hint   — ``run()`` returns an ``IntegrationResult`` with only
               ``hint_text`` populated; no subprocess call required.
      run    — ``run()`` invokes a subprocess and maps stdout → Findings.
      plugin — YAML-declared; materialised by ``YamlIntegrationAdapter``
               in ``drift.integrations.registry``.
    """

    name: str
    tier: Literal["hint", "run", "plugin"]
    enabled: bool
    trigger_signals: list[str]

    def is_available(self) -> bool:
        """Return True when the external tool can be invoked.

        For hint-tier adapters this should always return True.
        For run/plugin adapters this typically calls ``shutil.which``.
        """
        ...

    def run(self, ctx: IntegrationContext) -> IntegrationResult:
        """Execute this integration and return its result.

        Must never raise — return an empty ``IntegrationResult`` on error
        and log a warning.
        """
        ...
