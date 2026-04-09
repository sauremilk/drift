"""Targeted API tests to provide explicit coverage for high-complexity entry points.

These tests are intentionally lightweight but execute real API calls,
so they validate result contracts while documenting expected behavior for
invalid repository paths.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from drift.api import _format_scan_response, brief, diff, fix_plan, nudge, validate
from drift.config import DriftConfig


def _missing_repo(tmp_path: Path) -> str:
    """Return a path that does not exist below the pytest temp directory."""
    return str(tmp_path / "missing-repo")


def test__format_scan_response() -> None:
    """Formats a minimal empty analysis into the public scan response contract."""
    analysis = SimpleNamespace(
        findings=[],
        drift_score=0.0,
        severity=SimpleNamespace(value="low"),
        total_files=1,
        total_functions=1,
        ai_attributed_ratio=0.0,
        trend=None,
    )

    result = _format_scan_response(analysis, config=DriftConfig(), detail="concise")

    assert result["finding_count"] == 0
    assert result["findings_returned"] == 0
    assert "top_signals" in result


def test_diff(tmp_path: Path) -> None:
    """diff returns a structured contract (not an exception)."""
    result = diff(path=str(tmp_path))

    assert isinstance(result, dict)
    assert "drift_detected" in result
    assert "decision_reason" in result


def test_fix_plan(tmp_path: Path) -> None:
    """fix_plan returns a structured payload."""
    result = fix_plan(path=str(tmp_path))

    assert isinstance(result, dict)
    assert "schema_version" in result
    assert "remaining_by_signal" in result


def test_validate(tmp_path: Path) -> None:
    """validate reports capabilities and validity on invalid paths without raising."""
    result = validate(path=str(tmp_path))

    assert isinstance(result, dict)
    assert "valid" in result
    assert "git_available" in result


def test_nudge(tmp_path: Path) -> None:
    """nudge returns directional feedback payload."""
    result = nudge(path=str(tmp_path))

    assert isinstance(result, dict)
    assert "direction" in result
    assert "safe_to_commit" in result


def test_brief(tmp_path: Path) -> None:
    """brief returns the brief response envelope."""
    result = brief(path=str(tmp_path), task="Assess architectural drift risk")

    assert isinstance(result, dict)
    assert result.get("type") == "brief"
    assert "scope" in result
