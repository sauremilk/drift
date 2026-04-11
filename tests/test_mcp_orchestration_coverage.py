"""Coverage tests for MCP orchestration helpers."""

from __future__ import annotations

from typing import Any

from drift.mcp_orchestration import (
    _derive_diagnostic_hypothesis_id,
    _effective_profile,
    _requires_diagnostic_hypothesis,
    _resolve_session,
    _session_called_tools,
    _session_defaults,
    _update_session_from_brief,
    _update_session_from_diff,
    _update_session_from_fix_plan,
    _update_session_from_scan,
    _validate_diagnostic_hypothesis_payload,
)

# ---------------------------------------------------------------------------
# Helpers — lightweight session stub
# ---------------------------------------------------------------------------


class _FakeSession:
    """Lightweight stand-in for DriftSession used in orchestration tests."""

    def __init__(self, **kwargs: Any) -> None:
        self.repo_path = "."
        self.signals: list[str] | None = None
        self.exclude_signals: list[str] | None = None
        self.target_path: str | None = None
        self.phase = "init"
        self.last_scan_score: float | None = None
        self.last_scan_top_signals: Any = None
        self.last_scan_finding_count: int | None = None
        self.score_at_start: float | None = None
        self.guardrails: Any = None
        self.guardrails_prompt_block: Any = None
        self.selected_tasks: list[dict[str, Any]] = []
        self.completed_task_ids: set[str] = set()
        self.trace: list[dict[str, Any]] = []
        self.diagnostic_hypotheses: dict[str, Any] = {}
        self._seen_verification_payload_hashes: set[str] = set()
        self.metrics: Any = None
        for k, v in kwargs.items():
            setattr(self, k, v)

    def begin_call(self) -> None:
        pass

    def touch(self) -> None:
        pass

    def advance_phase(self, p: str) -> None:
        self.phase = p

    def snapshot_run(self, score: float, count: int) -> None:
        pass


# ---------------------------------------------------------------------------
# _resolve_session
# ---------------------------------------------------------------------------


class TestResolveSession:
    def test_none_id(self):
        assert _resolve_session(None) is None

    def test_empty_id(self):
        assert _resolve_session("") is None


# ---------------------------------------------------------------------------
# _session_defaults
# ---------------------------------------------------------------------------


class TestSessionDefaults:
    def test_none_session(self):
        kwargs = {"path": ".", "signals": None}
        result = _session_defaults(None, kwargs)
        assert result == kwargs

    def test_applies_defaults(self):
        session = _FakeSession(
            repo_path="/repo",
            signals=["PFS"],
            exclude_signals=["MDS"],
            target_path="src/",
        )
        kwargs: dict[str, Any] = {
            "path": ".",
            "signals": None,
            "exclude_signals": None,
            "target_path": None,
        }
        result = _session_defaults(session, kwargs)
        assert result["path"] == "/repo"
        assert result["signals"] == ["PFS"]
        assert result["exclude_signals"] == ["MDS"]
        assert result["target_path"] == "src/"

    def test_explicit_values_not_overridden(self):
        session = _FakeSession(repo_path="/repo", signals=["PFS"])
        kwargs: dict[str, Any] = {"path": "/other", "signals": ["AVS"]}
        result = _session_defaults(session, kwargs)
        assert result["path"] == "/other"
        assert result["signals"] == ["AVS"]


# ---------------------------------------------------------------------------
# _update_session_from_scan
# ---------------------------------------------------------------------------


class TestUpdateSessionFromScan:
    def test_none_session(self):
        _update_session_from_scan(None, {})  # should not raise

    def test_updates_state(self):
        session = _FakeSession()
        _update_session_from_scan(
            session,
            {
                "drift_score": 0.42,
                "top_signals": ["PFS"],
                "finding_count": 5,
            },
        )
        assert session.last_scan_score == 0.42
        assert session.last_scan_finding_count == 5
        assert session.score_at_start == 0.42
        assert session.phase == "scan"

    def test_finding_count_from_findings_list(self):
        session = _FakeSession()
        _update_session_from_scan(
            session,
            {
                "drift_score": 0.1,
                "findings": [{"a": 1}, {"b": 2}],
            },
        )
        assert session.last_scan_finding_count == 2


# ---------------------------------------------------------------------------
# _update_session_from_fix_plan
# ---------------------------------------------------------------------------


class TestUpdateSessionFromFixPlan:
    def test_none_session(self):
        _update_session_from_fix_plan(None, {})  # should not raise

    def test_advances_phase(self):
        session = _FakeSession(phase="scan")
        _update_session_from_fix_plan(
            session,
            {
                "tasks": [{"id": "t1", "file": "a.py"}],
            },
        )
        assert session.phase == "fix"
        assert session.selected_tasks == [{"id": "t1", "file": "a.py"}]


# ---------------------------------------------------------------------------
# _update_session_from_brief
# ---------------------------------------------------------------------------


class TestUpdateSessionFromBrief:
    def test_none_session(self):
        _update_session_from_brief(None, {})  # should not raise

    def test_stores_guardrails(self):
        session = _FakeSession()
        _update_session_from_brief(
            session,
            {
                "guardrails": ["gr1"],
                "guardrails_prompt_block": "block",
            },
        )
        assert session.guardrails == ["gr1"]
        assert session.guardrails_prompt_block == "block"


# ---------------------------------------------------------------------------
# _update_session_from_diff
# ---------------------------------------------------------------------------


class TestUpdateSessionFromDiff:
    def test_none_session(self):
        _update_session_from_diff(None, {})  # should not raise

    def test_updates_score(self):
        session = _FakeSession(phase="fix")
        _update_session_from_diff(
            session,
            {
                "score_after": 0.3,
                "findings_after_count": 10,
            },
        )
        assert session.last_scan_score == 0.3
        assert session.phase == "verify"


# ---------------------------------------------------------------------------
# _session_called_tools
# ---------------------------------------------------------------------------


class TestSessionCalledTools:
    def test_none_session(self):
        assert _session_called_tools(None) == set()

    def test_from_trace(self):
        session = _FakeSession(
            trace=[{"tool": "drift_scan"}, {"tool": "drift_nudge"}],
        )
        tools = _session_called_tools(session)
        assert "drift_scan" in tools
        assert "drift_nudge" in tools

    def test_inference_from_phase(self):
        session = _FakeSession(
            phase="fix",
            guardrails=["some_gr"],
            last_scan_score=0.5,
            selected_tasks=[{"id": "t1"}],
        )
        tools = _session_called_tools(session)
        assert "drift_validate" in tools
        assert "drift_brief" in tools
        assert "drift_scan" in tools
        assert "drift_fix_plan" in tools


# ---------------------------------------------------------------------------
# _effective_profile
# ---------------------------------------------------------------------------


class TestEffectiveProfile:
    def test_explicit_override(self):
        assert _effective_profile(None, "coder") == "coder"

    def test_none_session(self):
        assert _effective_profile(None, None) is None

    def test_phase_mapping(self):
        for phase, expected in [
            ("init", "planner"),
            ("scan", "planner"),
            ("fix", "coder"),
            ("verify", "verifier"),
            ("done", "merge_readiness"),
        ]:
            session = _FakeSession(phase=phase)
            assert _effective_profile(session, None) == expected


# ---------------------------------------------------------------------------
# _requires_diagnostic_hypothesis
# ---------------------------------------------------------------------------


class TestRequiresDiagnosticHypothesis:
    def test_none_session(self):
        assert _requires_diagnostic_hypothesis(None) is False

    def test_no_batch_tasks(self):
        session = _FakeSession(
            selected_tasks=[{"id": "t1", "batch_eligible": False}],
        )
        assert _requires_diagnostic_hypothesis(session) is False

    def test_batch_eligible_task(self):
        session = _FakeSession(
            selected_tasks=[{"id": "t1", "batch_eligible": True}],
        )
        assert _requires_diagnostic_hypothesis(session) is True


# ---------------------------------------------------------------------------
# _validate_diagnostic_hypothesis_payload
# ---------------------------------------------------------------------------


class TestValidateDiagnosticHypothesisPayload:
    def test_valid_payload(self):
        payload = {
            "affected_files": ["a.py"],
            "suspected_root_cause": "missing guard",
            "minimal_intended_change": "add isinstance check",
            "non_goals": ["no refactoring"],
        }
        assert _validate_diagnostic_hypothesis_payload(payload) == []

    def test_non_dict(self):
        errors = _validate_diagnostic_hypothesis_payload("not a dict")
        assert len(errors) == 1

    def test_empty_affected_files(self):
        payload = {
            "affected_files": [],
            "suspected_root_cause": "x",
            "minimal_intended_change": "y",
            "non_goals": ["z"],
        }
        errors = _validate_diagnostic_hypothesis_payload(payload)
        assert any("affected_files" in e for e in errors)

    def test_invalid_item_types(self):
        payload = {
            "affected_files": [123],
            "suspected_root_cause": "x",
            "minimal_intended_change": "y",
            "non_goals": ["z"],
        }
        errors = _validate_diagnostic_hypothesis_payload(payload)
        assert len(errors) >= 1


# ---------------------------------------------------------------------------
# _derive_diagnostic_hypothesis_id
# ---------------------------------------------------------------------------


class TestDeriveDiagnosticHypothesisId:
    def test_deterministic(self):
        payload = {
            "affected_files": ["b.py", "a.py"],
            "suspected_root_cause": "root",
            "minimal_intended_change": "change",
            "non_goals": ["no"],
        }
        id1 = _derive_diagnostic_hypothesis_id(payload)
        id2 = _derive_diagnostic_hypothesis_id(payload)
        assert id1 == id2
        assert id1.startswith("hyp-")

    def test_different_payload_different_id(self):
        p1 = {
            "affected_files": ["a.py"],
            "suspected_root_cause": "root1",
            "minimal_intended_change": "change",
            "non_goals": ["no"],
        }
        p2 = {
            "affected_files": ["a.py"],
            "suspected_root_cause": "root2",
            "minimal_intended_change": "change",
            "non_goals": ["no"],
        }
        assert _derive_diagnostic_hypothesis_id(p1) != _derive_diagnostic_hypothesis_id(p2)
