"""Tests for semantic advisory checks (SA-001 … SA-004) in _pre_call_advisory.

These checks extend the structural pre-call advisory pipeline with
runtime-aware semantic guidance.
"""

from __future__ import annotations

from drift.session import DriftSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(**overrides: object) -> DriftSession:
    defaults: dict[str, object] = {
        "session_id": "test0001",
        "repo_path": "/tmp/repo",
        "phase": "fix",
    }
    defaults.update(overrides)
    return DriftSession(**defaults)  # type: ignore[arg-type]


def _call_advisory(tool_name: str, session: DriftSession) -> str:
    """Call _pre_call_advisory with mocked TOOL_CATALOG to isolate SA checks."""
    from drift.mcp_server import _pre_call_advisory

    return _pre_call_advisory(tool_name, session)


# ---------------------------------------------------------------------------
# SA-001: Blocker-awareness
# ---------------------------------------------------------------------------


class TestSA001:
    def test_warns_on_nudge_with_unresolved_dep(self) -> None:
        s = _make_session(
            selected_tasks=[
                {"id": "t1", "signal": "AVS", "depends_on": ["t0"]},
            ],
            completed_task_ids=[],
        )
        adv = _call_advisory("drift_nudge", s)
        assert "unresolved dependency" in adv.lower() or "t0" in adv

    def test_warns_on_task_complete_with_unresolved_dep(self) -> None:
        s = _make_session(
            selected_tasks=[
                {"id": "t1", "signal": "AVS", "depends_on": ["t0"]},
            ],
            completed_task_ids=[],
        )
        adv = _call_advisory("drift_task_complete", s)
        assert "unresolved" in adv.lower() or "t0" in adv

    def test_silent_when_deps_resolved(self) -> None:
        s = _make_session(
            selected_tasks=[
                {"id": "t1", "signal": "AVS", "depends_on": ["t0"]},
            ],
            completed_task_ids=["t0"],
        )
        adv = _call_advisory("drift_nudge", s)
        assert "unresolved" not in adv.lower()


# ---------------------------------------------------------------------------
# SA-002: Canonical-pattern deviation (repeated scan in fix phase)
# ---------------------------------------------------------------------------


class TestSA002:
    def test_warns_on_repeated_scan_in_fix_phase(self) -> None:
        s = _make_session(
            phase="fix",
            trace=[
                {
                    "tool": "drift_scan",
                    "ts": 1.0,
                    "phase": "fix",
                    "advisory": "",
                    "tool_calls_so_far": 1,
                },
            ],
        )
        adv = _call_advisory("drift_scan", s)
        assert "canonical" in adv.lower() or "repeated scan" in adv.lower()

    def test_silent_in_scan_phase(self) -> None:
        s = _make_session(
            phase="scan",
            trace=[
                {
                    "tool": "drift_scan",
                    "ts": 1.0,
                    "phase": "scan",
                    "advisory": "",
                    "tool_calls_so_far": 1,
                },
            ],
        )
        adv = _call_advisory("drift_scan", s)
        assert "canonical" not in adv.lower()


# ---------------------------------------------------------------------------
# SA-003: Goal-coherence (hypothesis check)
# ---------------------------------------------------------------------------


class TestSA003:
    def test_warns_on_file_outside_hypothesis(self) -> None:
        s = _make_session(
            diagnostic_hypotheses={
                "hyp-1": {
                    "affected_files": ["src/main.py"],
                    "suspected_root_cause": "test",
                    "minimal_intended_change": "test",
                    "non_goals": [],
                },
            },
            trace=[
                {
                    "tool": "drift_fix_plan",
                    "ts": 1.0,
                    "phase": "fix",
                    "advisory": "",
                    "tool_calls_so_far": 1,
                    "changed_files": "src/other.py",
                },
            ],
        )
        adv = _call_advisory("drift_nudge", s)
        assert "hypothesis" in adv.lower() or "scope creep" in adv.lower()

    def test_silent_when_no_hypothesis(self) -> None:
        s = _make_session(
            diagnostic_hypotheses={},
            trace=[
                {
                    "tool": "drift_fix_plan",
                    "ts": 1.0,
                    "phase": "fix",
                    "advisory": "",
                    "tool_calls_so_far": 1,
                    "changed_files": "src/other.py",
                },
            ],
        )
        adv = _call_advisory("drift_nudge", s)
        assert "hypothesis" not in adv.lower()


# ---------------------------------------------------------------------------
# SA-004: Completed-task rework
# ---------------------------------------------------------------------------


class TestSA004:
    def test_warns_on_nudge_for_completed_task_file(self) -> None:
        s = _make_session(
            selected_tasks=[
                {"id": "t1", "signal": "PFS", "file": "src/main.py"},
            ],
            completed_task_ids=["t1"],
        )
        adv = _call_advisory("drift_nudge", s)
        assert "completed task" in adv.lower() or "rework" in adv.lower()

    def test_silent_when_no_completed_tasks(self) -> None:
        s = _make_session(
            selected_tasks=[
                {"id": "t1", "signal": "PFS", "file": "src/main.py"},
            ],
            completed_task_ids=[],
        )
        adv = _call_advisory("drift_nudge", s)
        assert "rework" not in adv.lower()

    def test_warns_for_batch_affected_files(self) -> None:
        s = _make_session(
            selected_tasks=[
                {
                    "id": "t1",
                    "signal": "PFS",
                    "file": "src/main.py",
                    "affected_files_for_pattern": ["src/util.py"],
                },
            ],
            completed_task_ids=["t1"],
        )
        adv = _call_advisory("drift_nudge", s)
        assert "completed task" in adv.lower() or "rework" in adv.lower()
