"""Drift integration and plugin system.

Three-tier model:

  hint   — Drift mentions a relevant external tool in the report
  run    — Drift invokes the external tool and maps its output to Findings
  plugin — User-declared integrations via drift.yaml (YAML-only, no Python)

Integration adapters are discovered via:
  1. Built-in adapters in drift.integrations.builtin.*
  2. Python entry points (group ``drift.integrations``)
  3. YAML-declared adapters in drift.yaml → integrations:

Usage::

    from drift.integrations import run_integrations, IntegrationAdapter

    results = run_integrations(repo_path, findings, config)
"""

from __future__ import annotations

from drift.integrations.base import IntegrationAdapter, IntegrationContext, IntegrationResult
from drift.integrations.registry import get_registry
from drift.integrations.runner import run_integrations

__all__ = [
    "IntegrationAdapter",
    "IntegrationContext",
    "IntegrationResult",
    "get_registry",
    "run_integrations",
]
