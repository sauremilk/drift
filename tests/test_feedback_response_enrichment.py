"""Tests for enriched feedback response (Bruchstelle 3).

Feedback responses must include pending FP count and a next_tool_call hint
so the agent knows its feedback will take effect after calibration.
"""

from __future__ import annotations

import json
from pathlib import Path


def _fe(
    signal: str = "pattern_fragmentation",
    file: str = "src/a.py",
    verdict: str = "fp",
    source: str = "user",
    **kw: object,
) -> object:
    from drift.calibration.feedback import FeedbackEvent

    return FeedbackEvent(
        signal_type=signal,
        file_path=file,
        verdict=verdict,  # type: ignore[arg-type]
        source=source,  # type: ignore[arg-type]
        **kw,  # type: ignore[arg-type]
    )


class TestFeedbackResponseEnrichment:
    """Feedback response includes pending FP count and calibration hint."""

    def test_feedback_response_includes_pending_fp_count(self, tmp_path: Path) -> None:
        """After recording an FP, response shows how many FPs are pending for that signal."""
        from drift.calibration.feedback import record_feedback, resolve_feedback_paths
        from drift.config import DriftConfig

        cfg = DriftConfig()
        feedback_path, _, _ = resolve_feedback_paths(tmp_path, cfg)

        # Pre-seed 2 FPs for the same signal
        record_feedback(feedback_path, _fe(signal="pattern_fragmentation", file="src/a.py"))  # type: ignore[arg-type]
        record_feedback(feedback_path, _fe(signal="pattern_fragmentation", file="src/b.py"))  # type: ignore[arg-type]

        # Now call run_feedback synchronously via the inner _sync logic
        from drift.mcp_router_calibration import _build_feedback_response

        result = _build_feedback_response(
            resolved_signal="pattern_fragmentation",
            file_path="src/c.py",
            verdict="fp",
            finding_id="abc123",
            feedback_path=feedback_path,
        )
        parsed = json.loads(result)

        assert parsed["status"] == "recorded"
        assert parsed["pending_fp_count"] >= 2  # at least the 2 pre-seeded
        assert "pending_fp_count" in parsed

    def test_feedback_response_includes_next_tool_call(self, tmp_path: Path) -> None:
        """Feedback response suggests drift_calibrate as next tool."""
        from drift.calibration.feedback import resolve_feedback_paths
        from drift.config import DriftConfig
        from drift.mcp_router_calibration import _build_feedback_response

        cfg = DriftConfig()
        feedback_path, _, _ = resolve_feedback_paths(tmp_path, cfg)

        result = _build_feedback_response(
            resolved_signal="pattern_fragmentation",
            file_path="src/a.py",
            verdict="fp",
            finding_id="abc123",
            feedback_path=feedback_path,
        )
        parsed = json.loads(result)

        assert "next_tool_call" in parsed
        assert parsed["next_tool_call"]["tool"] == "drift_calibrate"

    def test_feedback_response_tp_has_zero_fp_count(self, tmp_path: Path) -> None:
        """TP verdicts still get pending_fp_count (which is 0 when no FPs exist)."""
        from drift.calibration.feedback import resolve_feedback_paths
        from drift.config import DriftConfig
        from drift.mcp_router_calibration import _build_feedback_response

        cfg = DriftConfig()
        feedback_path, _, _ = resolve_feedback_paths(tmp_path, cfg)

        result = _build_feedback_response(
            resolved_signal="pattern_fragmentation",
            file_path="src/a.py",
            verdict="tp",
            finding_id="abc123",
            feedback_path=feedback_path,
        )
        parsed = json.loads(result)

        assert parsed["pending_fp_count"] == 0
        assert parsed["verdict"] == "tp"

    def test_feedback_response_includes_agent_instruction(self, tmp_path: Path) -> None:
        """Feedback response includes actionable agent_instruction."""
        from drift.calibration.feedback import resolve_feedback_paths
        from drift.config import DriftConfig
        from drift.mcp_router_calibration import _build_feedback_response

        cfg = DriftConfig()
        feedback_path, _, _ = resolve_feedback_paths(tmp_path, cfg)

        result = _build_feedback_response(
            resolved_signal="pattern_fragmentation",
            file_path="src/a.py",
            verdict="fp",
            finding_id="abc123",
            feedback_path=feedback_path,
        )
        parsed = json.loads(result)

        assert "agent_instruction" in parsed
        assert "calibrate" in parsed["agent_instruction"].lower()
