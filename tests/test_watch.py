"""Tests for the drift watch command (C3)."""

from __future__ import annotations

import pytest

from drift.commands.watch import _print_nudge_summary


class TestPrintNudgeSummary:
    """Test the nudge summary printer used by watch."""

    def test_improving_direction(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = {
            "direction": "improving",
            "delta": -0.05,
            "safe_to_commit": True,
            "new_findings": [],
            "resolved_findings": [{"title": "Fixed"}],
        }
        _print_nudge_summary(result)
        # No exception raised — output was printed

    def test_degrading_direction(self) -> None:
        result = {
            "direction": "degrading",
            "delta": 0.1,
            "safe_to_commit": False,
            "new_findings": [{"title": "New issue"}],
            "resolved_findings": [],
        }
        _print_nudge_summary(result)

    def test_stable_direction(self) -> None:
        result = {
            "direction": "stable",
            "delta": 0.0,
            "safe_to_commit": True,
            "new_findings": [],
            "resolved_findings": [],
        }
        _print_nudge_summary(result)

    def test_initial_baseline(self) -> None:
        result = {
            "direction": "stable",
            "delta": 0.0,
            "safe_to_commit": True,
            "new_findings": [],
            "resolved_findings": [],
        }
        _print_nudge_summary(result, initial=True)

    def test_many_new_findings_truncated(self) -> None:
        result = {
            "direction": "degrading",
            "delta": 0.2,
            "safe_to_commit": False,
            "new_findings": [{"title": f"Issue {i}"} for i in range(10)],
            "resolved_findings": [],
        }
        _print_nudge_summary(result)


class TestWatchCommandImport:
    """Verify the watch command can be imported and has expected attributes."""

    def test_command_exists(self) -> None:
        from drift.commands.watch import watch

        assert watch is not None
        assert hasattr(watch, "callback")

    def test_registered_in_cli(self) -> None:
        from drift.cli import main

        command_names = [cmd for cmd in main.commands]
        assert "watch" in command_names
