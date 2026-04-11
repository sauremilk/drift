"""Coverage tests for mcp_orchestration helpers and pipeline helpers."""

from __future__ import annotations

from types import SimpleNamespace

from drift.mcp_orchestration import (
    _derive_diagnostic_hypothesis_id,
    _effective_profile,
    _session_called_tools,
    _session_defaults,
    _update_session_from_brief,
    _update_session_from_diff,
    _update_session_from_scan,
    _update_session_from_verification_result,
    _validate_diagnostic_hypothesis_payload,
)
from drift.pipeline import make_degradation_event


def _session(**kw):
    defaults = dict(
        repo_path="/tmp/repo",
        signals=None,
        exclude_signals=None,
        target_path=None,
        phase="init",
        guardrails=None,
        guardrails_prompt_block=None,
        last_scan_score=None,
        last_scan_top_signals=None,
        last_scan_finding_count=None,
        score_at_start=None,
        selected_tasks=[],
        trace=[],
        _seen_verification_payload_hashes=set(),
        metrics=None,
    )
    defaults.update(kw)
    ns = SimpleNamespace(**defaults)
    ns.touch = lambda: None
    ns.advance_phase = lambda p: setattr(ns, "phase", p)
    ns.snapshot_run = lambda s, f: None
    ns.begin_call = lambda: None
    return ns


# ── _session_defaults ────────────────────────────────────────────


class TestSessionDefaults:
    def test_none_session(self):
        kw = {"path": ".", "signals": None}
        assert _session_defaults(None, kw) is kw

    def test_applies_path(self):
        s = _session()
        result = _session_defaults(s, {"path": "."})
        assert result["path"] == "/tmp/repo"

    def test_applies_signals(self):
        s = _session(signals=["PFS"])
        result = _session_defaults(s, {"signals": None})
        assert result["signals"] == ["PFS"]

    def test_preserves_explicit(self):
        s = _session(signals=["PFS"])
        result = _session_defaults(s, {"signals": ["MDS"]})
        assert result["signals"] == ["MDS"]

    def test_applies_target_path(self):
        s = _session(target_path="src/")
        result = _session_defaults(s, {"target_path": None})
        assert result["target_path"] == "src/"


# ── _update_session_from_scan ────────────────────────────────────


class TestUpdateSessionFromScan:
    def test_sets_score(self):
        s = _session()
        _update_session_from_scan(s, {"drift_score": 0.45, "top_signals": ["PFS"]})
        assert s.last_scan_score == 0.45

    def test_none_session(self):
        _update_session_from_scan(None, {})  # no error

    def test_finding_count(self):
        s = _session()
        _update_session_from_scan(s, {"finding_count": 10})
        assert s.last_scan_finding_count == 10


# ── _update_session_from_brief ───────────────────────────────────


class TestUpdateSessionFromBrief:
    def test_sets_guardrails(self):
        s = _session()
        _update_session_from_brief(s, {"guardrails": ["rule1"], "guardrails_prompt_block": "block"})
        assert s.guardrails == ["rule1"]
        assert s.guardrails_prompt_block == "block"


# ── _update_session_from_diff ────────────────────────────────────


class TestUpdateSessionFromDiff:
    def test_score_update(self):
        s = _session(phase="fix")
        _update_session_from_diff(s, {"score_after": 0.3, "findings_after_count": 5})
        assert s.last_scan_score == 0.3
        assert s.phase == "verify"

    def test_none_session(self):
        _update_session_from_diff(None, {})


# ── _update_session_from_verification_result ─────────────────────


class TestUpdateSessionFromVerification:
    def test_records_verification(self):
        calls = []
        metrics = SimpleNamespace(
            record_verification=lambda **kw: calls.append(kw),
        )
        s = _session(metrics=metrics)
        result = {
            "changed_files": ["a.py"],
            "changed_loc": 10,
            "resolved_count": 2,
            "new_finding_count": 0,
        }
        _update_session_from_verification_result(s, result)
        assert len(calls) == 1
        assert calls[0]["changed_file_count"] == 1

    def test_dedup(self):
        calls = []
        metrics = SimpleNamespace(
            record_verification=lambda **kw: calls.append(kw),
        )
        s = _session(metrics=metrics)
        result = {
            "changed_files": ["a.py"],
            "changed_loc": 5,
            "resolved_count": 0,
            "new_finding_count": 0,
        }
        _update_session_from_verification_result(s, result)
        _update_session_from_verification_result(s, result)
        assert len(calls) == 1  # dedup

    def test_loc_changed_fallback(self):
        calls = []
        metrics = SimpleNamespace(
            record_verification=lambda **kw: calls.append(kw),
        )
        s = _session(metrics=metrics)
        result = {
            "changed_files": ["b.py"],
            "loc_changed": 7,
            "resolved_count": 1,
            "new_finding_count": 0,
        }
        _update_session_from_verification_result(s, result)
        assert calls[0]["loc_changed"] == 7

    def test_none_session(self):
        _update_session_from_verification_result(None, {})

    def test_no_metrics(self):
        s = _session(metrics=None)
        _update_session_from_verification_result(s, {"changed_files": ["x.py"]})


# ── _session_called_tools ────────────────────────────────────────


class TestSessionCalledTools:
    def test_none(self):
        assert _session_called_tools(None) == set()

    def test_from_trace(self):
        s = _session(trace=[{"tool": "drift_scan"}])
        result = _session_called_tools(s)
        assert "drift_scan" in result

    def test_infers_validate(self):
        s = _session(phase="fix")
        result = _session_called_tools(s)
        assert "drift_validate" in result

    def test_infers_brief(self):
        s = _session(guardrails=["rule"])
        result = _session_called_tools(s)
        assert "drift_brief" in result


# ── _effective_profile ───────────────────────────────────────────


class TestEffectiveProfile:
    def test_explicit(self):
        assert _effective_profile(None, "custom") == "custom"

    def test_none(self):
        assert _effective_profile(None, None) is None

    def test_fix_phase(self):
        s = _session(phase="fix")
        assert _effective_profile(s, None) == "coder"

    def test_init_phase(self):
        s = _session(phase="init")
        assert _effective_profile(s, None) == "planner"

    def test_unknown_phase(self):
        s = _session(phase="custom_phase")
        assert _effective_profile(s, None) is None


# ── _validate_diagnostic_hypothesis_payload ──────────────────────


class TestValidateHypothesisPayload:
    def test_valid(self):
        payload = {
            "affected_files": ["a.py"],
            "suspected_root_cause": "duplication",
            "minimal_intended_change": "extract helper",
            "non_goals": ["no refactor"],
        }
        assert _validate_diagnostic_hypothesis_payload(payload) == []

    def test_not_dict(self):
        errors = _validate_diagnostic_hypothesis_payload("string")
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

    def test_empty_non_goals_items(self):
        payload = {
            "affected_files": ["a.py"],
            "suspected_root_cause": "x",
            "minimal_intended_change": "y",
            "non_goals": [""],
        }
        errors = _validate_diagnostic_hypothesis_payload(payload)
        assert any("non_goals" in e for e in errors)

    def test_missing_root_cause(self):
        payload = {
            "affected_files": ["a.py"],
            "suspected_root_cause": "",
            "minimal_intended_change": "y",
            "non_goals": ["z"],
        }
        errors = _validate_diagnostic_hypothesis_payload(payload)
        assert any("suspected_root_cause" in e for e in errors)


# ── _derive_diagnostic_hypothesis_id ─────────────────────────────


class TestDeriveHypothesisId:
    def test_deterministic(self):
        payload = {
            "affected_files": ["a.py"],
            "suspected_root_cause": "dup",
            "minimal_intended_change": "fix",
            "non_goals": ["none"],
        }
        id1 = _derive_diagnostic_hypothesis_id(payload)
        id2 = _derive_diagnostic_hypothesis_id(payload)
        assert id1 == id2
        assert id1.startswith("hyp-")

    def test_different_payload(self):
        p1 = {
            "affected_files": ["a.py"],
            "suspected_root_cause": "x",
            "minimal_intended_change": "y",
            "non_goals": ["z"],
        }
        p2 = {
            "affected_files": ["b.py"],
            "suspected_root_cause": "x",
            "minimal_intended_change": "y",
            "non_goals": ["z"],
        }
        assert _derive_diagnostic_hypothesis_id(p1) != _derive_diagnostic_hypothesis_id(p2)


# ── make_degradation_event ───────────────────────────────────────


class TestMakeDegradationEvent:
    def test_basic(self):
        event = make_degradation_event(
            cause="test",
            component="pipe",
            message="failed",
        )
        assert event["cause"] == "test"
        assert event["component"] == "pipe"
        assert event["message"] == "failed"

    def test_with_details(self):
        event = make_degradation_event(
            cause="err",
            component="git",
            message="timeout",
            details={"elapsed": 30},
        )
        assert event["details"]["elapsed"] == 30
