"""Adapters for importing findings from external tool reports.

Supported formats:
- **SonarQube** — ``sonarqube`` (JSON export from ``api/issues/search``)
- **pylint** — ``pylint`` (JSON reporter output)
- **CodeClimate** — ``codeclimate`` (CodeClimate JSON format)

Each adapter reads the external JSON and produces a list of
:class:`~drift.models.Finding` objects with ``metadata["source"]``
set to the originating tool name.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drift.models import Finding, Severity

# ---------------------------------------------------------------------------
# Severity mapping helpers
# ---------------------------------------------------------------------------

_SONARQUBE_SEVERITY: dict[str, Severity] = {
    "BLOCKER": Severity.CRITICAL,
    "CRITICAL": Severity.HIGH,
    "MAJOR": Severity.MEDIUM,
    "MINOR": Severity.LOW,
    "INFO": Severity.INFO,
}

_PYLINT_SEVERITY: dict[str, Severity] = {
    "fatal": Severity.CRITICAL,
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "convention": Severity.LOW,
    "refactor": Severity.LOW,
    "information": Severity.INFO,
}

_CODECLIMATE_SEVERITY: dict[str, Severity] = {
    "blocker": Severity.CRITICAL,
    "critical": Severity.HIGH,
    "major": Severity.MEDIUM,
    "minor": Severity.LOW,
    "info": Severity.INFO,
}

# ---------------------------------------------------------------------------
# Format adapters
# ---------------------------------------------------------------------------


def _parse_sonarqube(data: dict[str, Any]) -> list[Finding]:
    """Parse SonarQube JSON (``api/issues/search`` response)."""
    issues = data.get("issues", [])
    findings: list[Finding] = []
    for issue in issues:
        component = issue.get("component", "")
        # SonarQube component format: "project:path/to/file.py"
        file_path_str = component.split(":", 1)[-1] if ":" in component else component
        sev_key = issue.get("severity", "INFO")
        findings.append(
            Finding(
                signal_type=f"sonarqube:{issue.get('rule', 'unknown')}",
                severity=_SONARQUBE_SEVERITY.get(sev_key, Severity.INFO),
                score=0.0,
                title=issue.get("message", "Imported SonarQube issue"),
                description=issue.get("message", ""),
                file_path=Path(file_path_str) if file_path_str else None,
                start_line=issue.get("textRange", {}).get("startLine"),
                end_line=issue.get("textRange", {}).get("endLine"),
                metadata={
                    "source": "sonarqube",
                    "external_rule": issue.get("rule"),
                    "external_key": issue.get("key"),
                    "external_type": issue.get("type"),
                },
            )
        )
    return findings


def _parse_pylint(data: list[dict[str, Any]] | dict[str, Any]) -> list[Finding]:
    """Parse pylint JSON reporter output (list of message dicts)."""
    messages: list[dict[str, Any]] = data if isinstance(data, list) else data.get("messages", [])
    findings: list[Finding] = []
    for msg in messages:
        sev_key = msg.get("type", "information")
        findings.append(
            Finding(
                signal_type=f"pylint:{msg.get('symbol', msg.get('message-id', 'unknown'))}",
                severity=_PYLINT_SEVERITY.get(sev_key, Severity.INFO),
                score=0.0,
                title=msg.get("message", "Imported pylint issue"),
                description=msg.get("message", ""),
                file_path=Path(msg["path"]) if msg.get("path") else None,
                start_line=msg.get("line"),
                end_line=msg.get("endLine"),
                symbol=msg.get("obj") or None,
                metadata={
                    "source": "pylint",
                    "external_rule": msg.get("symbol"),
                    "external_id": msg.get("message-id"),
                    "external_module": msg.get("module"),
                },
            )
        )
    return findings


def _parse_codeclimate(data: list[dict[str, Any]]) -> list[Finding]:
    """Parse CodeClimate JSON format (list of issue dicts)."""
    findings: list[Finding] = []
    for issue in data:
        sev_key = issue.get("severity", "info")
        location = issue.get("location", {})
        file_path_str = location.get("path", "")
        lines = location.get("lines", {})
        findings.append(
            Finding(
                signal_type=f"codeclimate:{issue.get('check_name', 'unknown')}",
                severity=_CODECLIMATE_SEVERITY.get(sev_key, Severity.INFO),
                score=0.0,
                title=issue.get("description", "Imported CodeClimate issue"),
                description=issue.get("description", ""),
                file_path=Path(file_path_str) if file_path_str else None,
                start_line=lines.get("begin"),
                end_line=lines.get("end"),
                metadata={
                    "source": "codeclimate",
                    "external_rule": issue.get("check_name"),
                    "external_fingerprint": issue.get("fingerprint"),
                    "external_categories": issue.get("categories", []),
                },
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_ADAPTERS: dict[str, Any] = {
    "sonarqube": _parse_sonarqube,
    "pylint": _parse_pylint,
    "codeclimate": _parse_codeclimate,
}

SUPPORTED_FORMATS = sorted(_ADAPTERS)


def load_external_report(path: Path, fmt: str) -> list[Finding]:
    """Load an external tool report and return imported findings.

    Parameters
    ----------
    path:
        Path to the JSON report file.
    fmt:
        One of ``sonarqube``, ``pylint``, ``codeclimate``.

    Returns
    -------
    list[Finding]
        Imported findings with ``metadata["source"]`` set.

    Raises
    ------
    ValueError
        If the format is unsupported.
    json.JSONDecodeError
        If the file is not valid JSON.
    """
    if fmt not in _ADAPTERS:
        raise ValueError(f"Unsupported format '{fmt}'. Supported: {', '.join(SUPPORTED_FORMATS)}")
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    adapter = _ADAPTERS[fmt]
    result: list[Finding] = adapter(data)
    return result
