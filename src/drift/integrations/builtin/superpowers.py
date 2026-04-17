"""Built-in integration adapter for Superpowers.

Tier: run
Trigger signals: pattern_fragmentation, architecture_violation

Superpowers is invoked as::

    superpowers check --format json <repo_path>

Expected JSON output schema (best-effort — gracefully degrades):
  Array of objects with keys:
    - message  (str)   — human-readable description
    - file     (str)   — relative file path
    - line     (int)   — start line
    - severity (str)   — "error" | "warning" | "info"
    - rule     (str)   — optional rule identifier
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from drift.integrations.base import IntegrationContext, IntegrationResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_TRIGGER_SIGNALS: list[str] = [
    "pattern_fragmentation",
    "architecture_violation",
]

_SEVERITY_MAP: dict[str, str] = {
    "error": "high",
    "warning": "medium",
    "info": "info",
    "hint": "info",
}


class SuperpowersAdapter:
    """Built-in adapter for Superpowers static analyser."""

    name: str = "superpowers"
    tier: Literal["hint", "run", "plugin"] = "run"
    enabled: bool = True
    trigger_signals: list[str] = _TRIGGER_SIGNALS

    def is_available(self) -> bool:
        return shutil.which("superpowers") is not None

    def run(self, ctx: IntegrationContext) -> IntegrationResult:
        from drift.integrations.runner import parse_json_output, run_command

        cmd = ["superpowers", "check", "--format", "json", str(ctx.repo_path.resolve())]
        sub = run_command(cmd, repo_path=ctx.repo_path, timeout_seconds=ctx.timeout_seconds)

        if sub.exit_code == 127 or sub.timed_out:
            return IntegrationResult(
                source=self.name,
                summary="superpowers: invocation failed — is the tool installed?",
                raw_output=sub.stderr,
            )

        findings = []
        parsed = parse_json_output(sub.stdout)
        if parsed is not None:
            findings = _map_superpowers_output(parsed, ctx.repo_path)

        return IntegrationResult(
            source=self.name,
            findings=findings,
            raw_output=sub.stdout,
            summary=f"superpowers: {len(findings)} finding(s).",
        )


# ---------------------------------------------------------------------------
# Output mapper
# ---------------------------------------------------------------------------


def _map_superpowers_output(data: list | dict, repo_path: Path) -> list:
    """Map Superpowers JSON output to Drift Finding objects."""
    from drift.models import Finding
    from drift.models._enums import Severity

    items: list = data if isinstance(data, list) else [data]
    findings = []

    for item in items:
        if not isinstance(item, dict):
            continue

        raw_severity = str(item.get("severity") or item.get("level") or "info").lower()
        mapped = _SEVERITY_MAP.get(raw_severity, "info")
        try:
            severity = Severity(mapped)
        except ValueError:
            severity = Severity.INFO

        file_str = item.get("file") or item.get("path")
        file_path: Path | None = None
        if file_str:
            candidate = Path(file_str)
            if not candidate.is_absolute():
                candidate = repo_path / candidate
            file_path = candidate

        rule_id = item.get("rule") or "superpowers"
        message = str(
            item.get("message") or item.get("msg") or item.get("text") or "superpowers finding"
        )

        findings.append(
            Finding(
                signal_type="superpowers",
                severity=severity,
                score=0.0,
                title=message,
                description=str(item.get("description") or message),
                file_path=file_path,
                start_line=item.get("line") or item.get("start_line"),
                rule_id=rule_id,
                metadata={
                    "integration_source": "superpowers",
                    "integration_tier": "run",
                    "raw": item,
                },
            )
        )

    return findings
