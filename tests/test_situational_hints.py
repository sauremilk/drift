"""Tests for situational hints (SH-001 … SH-007).

Each rule is tested with a synthetic DriftSession state that satisfies
its triggering condition and a negative case that verifies no-op.
"""

from __future__ import annotations

import time

from drift.session import DriftSession
from drift.situational_hints import build_situational_hint

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(**overrides: object) -> DriftSession:
    """Create a minimal DriftSession with optional field overrides."""
    defaults: dict[str, object] = {
        "session_id": "test0001",
        "repo_path": "/tmp/repo",
        "phase": "fix",
    }
    defaults.update(overrides)
    return DriftSession(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# SH-001: drift_scan while open tasks remain
# ---------------------------------------------------------------------------


class TestSH001:
    def test_fires_when_tasks_remain(self) -> None:
        s = _make_session(
            selected_tasks=[{"id": "t1", "signal": "PFS"}],
            completed_task_ids=[],
        )
        hint = build_situational_hint("drift_scan", s)
        assert hint is not None
        assert "drift_nudge" in hint

    def test_silent_when_all_completed(self) -> None:
        s = _make_session(
            selected_tasks=[{"id": "t1", "signal": "PFS"}],
            completed_task_ids=["t1"],
        )
        hint = build_situational_hint("drift_scan", s)
        assert hint is None

    def test_silent_for_other_tools(self) -> None:
        s = _make_session(
            selected_tasks=[{"id": "t1", "signal": "PFS"}],
            completed_task_ids=[],
        )
        hint = build_situational_hint("drift_nudge", s)
        # SH-001 only fires for drift_scan
        assert hint is None or "rescan" not in (hint or "").lower()


# ---------------------------------------------------------------------------
# SH-002: top signal not in fix plan
# ---------------------------------------------------------------------------


class TestSH002:
    def test_fires_when_top_signal_missing(self) -> None:
        s = _make_session(
            last_scan_top_signals=[{"signal": "MDS"}],
            selected_tasks=[{"id": "t1", "signal": "PFS"}],
        )
        hint = build_situational_hint("drift_fix_plan", s)
        assert hint is not None
        assert "MDS" in hint

    def test_silent_when_signal_covered(self) -> None:
        s = _make_session(
            last_scan_top_signals=[{"signal": "PFS"}],
            selected_tasks=[{"id": "t1", "signal": "PFS"}],
        )
        hint = build_situational_hint("drift_fix_plan", s)
        # SH-002 should not fire; SH-007 may or may not
        assert hint is None or "PFS" not in (hint or "")


# ---------------------------------------------------------------------------
# SH-003: consecutive nudge degradations
# ---------------------------------------------------------------------------


class TestSH003:
    def test_fires_after_three_degradations(self) -> None:
        s = _make_session(
            trace=[
                {
                    "tool": "drift_nudge",
                    "direction": "degrading",
                    "ts": 1.0,
                    "phase": "fix",
                    "advisory": "",
                    "tool_calls_so_far": i,
                }
                for i in range(3)
            ],
        )
        hint = build_situational_hint("drift_nudge", s)
        assert hint is not None
        assert "degradation" in hint.lower() or "degrad" in hint.lower()

    def test_silent_with_only_two(self) -> None:
        s = _make_session(
            trace=[
                {
                    "tool": "drift_nudge",
                    "direction": "degrading",
                    "ts": 1.0,
                    "phase": "fix",
                    "advisory": "",
                    "tool_calls_so_far": i,
                }
                for i in range(2)
            ],
        )
        hint = build_situational_hint("drift_nudge", s)
        assert hint is None

    def test_streak_broken_by_improving(self) -> None:
        s = _make_session(
            trace=[
                {
                    "tool": "drift_nudge",
                    "direction": "degrading",
                    "ts": 1.0,
                    "phase": "fix",
                    "advisory": "",
                    "tool_calls_so_far": 0,
                },
                {
                    "tool": "drift_nudge",
                    "direction": "improving",
                    "ts": 2.0,
                    "phase": "fix",
                    "advisory": "",
                    "tool_calls_so_far": 1,
                },
                {
                    "tool": "drift_nudge",
                    "direction": "degrading",
                    "ts": 3.0,
                    "phase": "fix",
                    "advisory": "",
                    "tool_calls_so_far": 2,
                },
                {
                    "tool": "drift_nudge",
                    "direction": "degrading",
                    "ts": 4.0,
                    "phase": "fix",
                    "advisory": "",
                    "tool_calls_so_far": 3,
                },
            ],
        )
        hint = build_situational_hint("drift_nudge", s)
        # Only last 2 are consecutive degrading — threshold is 3
        assert hint is None


# ---------------------------------------------------------------------------
# SH-004: session_end with active leases
# ---------------------------------------------------------------------------


class TestSH004:
    def test_fires_with_active_leases(self) -> None:
        s = _make_session(
            active_leases={
                "t1": {"agent_id": "a", "expires_at": time.time() + 300, "acquired_at": time.time()}
            },
        )
        hint = build_situational_hint("drift_session_end", s)
        assert hint is not None
        assert "release" in hint.lower()

    def test_silent_without_leases(self) -> None:
        s = _make_session(active_leases={})
        hint = build_situational_hint("drift_session_end", s)
        assert hint is None


# ---------------------------------------------------------------------------
# SH-005: nudge with unresolved blocker
# ---------------------------------------------------------------------------


class TestSH005:
    def test_fires_when_blocker_unresolved(self) -> None:
        s = _make_session(
            selected_tasks=[
                {"id": "t1", "signal": "AVS", "depends_on": ["t0"]},
            ],
            completed_task_ids=[],
        )
        hint = build_situational_hint("drift_nudge", s)
        assert hint is not None
        assert "blocker" in hint.lower() or "t0" in hint

    def test_silent_when_blocker_completed(self) -> None:
        s = _make_session(
            selected_tasks=[
                {"id": "t1", "signal": "AVS", "depends_on": ["t0"]},
            ],
            completed_task_ids=["t0"],
        )
        hint = build_situational_hint("drift_nudge", s)
        assert hint is None


# ---------------------------------------------------------------------------
# SH-006: sustained quality degradation (3+ snapshots)
# ---------------------------------------------------------------------------


class TestSH006:
    def test_fires_with_three_degrading_snapshots(self) -> None:
        s = _make_session(
            run_history=[
                {"score": 80.0, "finding_count": 10, "ts": 1.0, "tool_calls_at": 1},
                {"score": 75.0, "finding_count": 12, "ts": 2.0, "tool_calls_at": 2},
                {"score": 70.0, "finding_count": 14, "ts": 3.0, "tool_calls_at": 3},
            ],
        )
        hint = build_situational_hint("drift_nudge", s)
        assert hint is not None
        assert "10" in hint or "dropped" in hint.lower()

    def test_silent_when_stable(self) -> None:
        s = _make_session(
            run_history=[
                {"score": 80.0, "finding_count": 10, "ts": 1.0, "tool_calls_at": 1},
                {"score": 80.0, "finding_count": 10, "ts": 2.0, "tool_calls_at": 2},
                {"score": 80.0, "finding_count": 10, "ts": 3.0, "tool_calls_at": 3},
            ],
        )
        hint = build_situational_hint("drift_nudge", s)
        assert hint is None

    def test_silent_with_too_few_snapshots(self) -> None:
        s = _make_session(
            run_history=[
                {"score": 80.0, "finding_count": 10, "ts": 1.0, "tool_calls_at": 1},
                {"score": 70.0, "finding_count": 14, "ts": 2.0, "tool_calls_at": 2},
            ],
        )
        # drift_nudge won't trigger SH-006 with only 2 entries
        hint = build_situational_hint("drift_nudge", s)
        assert hint is None


# ---------------------------------------------------------------------------
# SH-007: repeated plan staleness
# ---------------------------------------------------------------------------


class TestSH007:
    def test_fires_after_two_stale_events(self) -> None:
        s = _make_session(
            trace=[
                {
                    "tool": "drift_fix_plan",
                    "plan_stale": True,
                    "ts": 1.0,
                    "phase": "fix",
                    "advisory": "",
                    "tool_calls_so_far": 1,
                },
                {
                    "tool": "drift_fix_plan",
                    "plan_stale": True,
                    "ts": 2.0,
                    "phase": "fix",
                    "advisory": "",
                    "tool_calls_so_far": 2,
                },
            ],
        )
        hint = build_situational_hint("drift_fix_plan", s)
        assert hint is not None
        assert "target_path" in hint

    def test_silent_with_one_stale(self) -> None:
        s = _make_session(
            trace=[
                {
                    "tool": "drift_fix_plan",
                    "plan_stale": True,
                    "ts": 1.0,
                    "phase": "fix",
                    "advisory": "",
                    "tool_calls_so_far": 1,
                },
            ],
        )
        hint = build_situational_hint("drift_fix_plan", s)
        assert hint is None


# ---------------------------------------------------------------------------
# Edge case: no session
# ---------------------------------------------------------------------------


class TestNoSession:
    def test_returns_none_for_none_session(self) -> None:
        assert build_situational_hint("drift_scan", None) is None
