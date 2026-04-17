"""Tests for the drift watch command (C3)."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

import drift.commands.watch as watch_cmd
from drift.commands.watch import _print_nudge_summary


def _render_watch_summary(result: dict, *, initial: bool = False) -> str:
    """Render watch summary to a test console and return plain text output."""
    stream = StringIO()
    test_console = Console(file=stream, force_terminal=False, no_color=True)
    original_console = watch_cmd.console
    watch_cmd.console = test_console
    try:
        _print_nudge_summary(result, initial=initial)
    finally:
        watch_cmd.console = original_console
    return stream.getvalue()


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

    def test_shows_estimated_cross_file_signal_notice(self) -> None:
        result = {
            "direction": "stable",
            "delta": 0.0,
            "safe_to_commit": True,
            "new_findings": [],
            "resolved_findings": [],
            "cross_file_signals_estimated": [
                "architecture_violation",
                "doc_impl_drift",
            ],
            "confidence": {
                "architecture_violation": "estimated",
                "doc_impl_drift": "estimated",
                "pattern_fragmentation": "exact",
            },
        }

        rendered = _render_watch_summary(result)
        lowered = rendered.lower()
        assert "estimated" in lowered
        assert "avs" in lowered
        assert "dia" in lowered
        assert "drift analyze" in lowered

    def test_falls_back_to_confidence_map_for_estimated_notice(self) -> None:
        result = {
            "direction": "stable",
            "delta": 0.0,
            "safe_to_commit": True,
            "new_findings": [],
            "resolved_findings": [],
            "confidence": {
                "architecture_violation": "estimated",
                "pattern_fragmentation": "exact",
            },
        }

        rendered = _render_watch_summary(result)
        lowered = rendered.lower()
        assert "estimated" in lowered
        assert "avs" in lowered


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
