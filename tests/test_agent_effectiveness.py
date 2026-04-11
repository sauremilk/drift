"""Tests for drift.config.AgentObjective and session agent-effectiveness fields.

Decision: ADR-029
"""

from __future__ import annotations

import pytest

from drift.config import AgentObjective, DriftConfig
from drift.mcp_server import _update_session_from_verification_result
from drift.session import DriftSession, OrchestrationMetrics, SessionManager


@pytest.fixture(autouse=True)
def _reset_manager():
    """Ensure a fresh SessionManager for every test."""
    SessionManager.reset_instance()
    yield
    SessionManager.reset_instance()


# ---------------------------------------------------------------------------
# AgentObjective config tests
# ---------------------------------------------------------------------------


class TestAgentObjective:
    def test_defaults(self):
        obj = AgentObjective()
        assert obj.goal == ""
        assert obj.out_of_scope == []
        assert obj.success_criteria == []
        assert (
            obj.effectiveness_thresholds.low_effect_resolved_per_changed_file == 0.25
        )

    def test_full_config(self):
        obj = AgentObjective(
            goal="Migrate billing to Stripe",
            out_of_scope=["legacy/", "tests/"],
            success_criteria=["No new AVS findings"],
        )
        assert obj.goal == "Migrate billing to Stripe"
        assert len(obj.out_of_scope) == 2
        assert "No new AVS findings" in obj.success_criteria

    def test_extra_forbidden(self):
        with pytest.raises(ValueError):
            AgentObjective(goal="x", unknown_field="y")  # type: ignore[call-arg]

    def test_effectiveness_thresholds_override(self):
        obj = AgentObjective(
            goal="optimize",
            effectiveness_thresholds={
                "low_effect_resolved_per_changed_file": 0.4,
                "high_churn_min_changed_files": 4,
            },
        )
        assert obj.effectiveness_thresholds.low_effect_resolved_per_changed_file == 0.4
        assert obj.effectiveness_thresholds.high_churn_min_changed_files == 4

    def test_effectiveness_thresholds_reject_unknown_keys(self):
        with pytest.raises(ValueError):
            AgentObjective(
                goal="x",
                effectiveness_thresholds={"unknown_threshold": 0.1},
            )


class TestDriftConfigAgent:
    def test_agent_none_by_default(self):
        cfg = DriftConfig()
        assert cfg.agent is None

    def test_agent_from_dict(self):
        cfg = DriftConfig(
            agent=AgentObjective(goal="test goal", out_of_scope=["vendor/"])
        )
        assert cfg.agent is not None
        assert cfg.agent.goal == "test goal"
        assert cfg.agent.out_of_scope == ["vendor/"]


# ---------------------------------------------------------------------------
# Session phase / trace / run_history tests
# ---------------------------------------------------------------------------


class TestSessionPhase:
    def test_initial_phase(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        assert s.phase == "init"

    def test_advance_phase(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        old = s.advance_phase("scan")
        assert old == "init"
        assert s.phase == "scan"

    def test_phase_in_summary(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        summary = s.summary()
        assert summary["phase"] == "init"


class TestSessionTrace:
    def test_trace_empty_initially(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        assert s.trace == []

    def test_record_trace(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        s.record_trace("drift_scan", advisory="some hint")
        assert len(s.trace) == 1
        assert s.trace[0]["tool"] == "drift_scan"
        assert s.trace[0]["advisory"] == "some hint"
        assert s.trace[0]["phase"] == "init"

    def test_trace_uses_current_phase(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        s.advance_phase("fix")
        s.record_trace("drift_nudge")
        assert s.trace[0]["phase"] == "fix"

    def test_trace_in_summary(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        s.record_trace("drift_scan")
        s.record_trace("drift_fix_plan")
        summary = s.summary()
        assert summary["trace_entries"] == 2


class TestSessionRunHistory:
    def test_snapshot_run(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        s.snapshot_run(42.5, 15)
        assert len(s.run_history) == 1
        assert s.run_history[0]["score"] == 42.5
        assert s.run_history[0]["finding_count"] == 15

    def test_multiple_snapshots(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        s.snapshot_run(50.0, 20)
        s.snapshot_run(45.0, 18)
        assert len(s.run_history) == 2
        assert s.run_history[0]["score"] == 50.0
        assert s.run_history[1]["score"] == 45.0


# ---------------------------------------------------------------------------
# Serialisation round-trip with new fields
# ---------------------------------------------------------------------------


class TestSessionSerialisation:
    def test_round_trip_new_fields(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        s.advance_phase("fix")
        s.record_trace("drift_scan")
        s.snapshot_run(30.0, 10)

        data = s.to_dict()
        assert data["phase"] == "fix"
        assert len(data["trace"]) == 1
        assert len(data["run_history"]) == 1

        restored = DriftSession.from_dict(data)
        assert restored.phase == "fix"
        assert len(restored.trace) == 1
        assert len(restored.run_history) == 1


# ---------------------------------------------------------------------------
# OrchestrationMetrics quality proxies
# ---------------------------------------------------------------------------


class TestQualityProxyMetrics:
    def test_default_values(self):
        m = OrchestrationMetrics()
        assert m.total_findings_seen == 0
        assert m.findings_suppressed == 0
        assert m.findings_acted_on == 0

    def test_serialisation(self):
        m = OrchestrationMetrics(
            total_findings_seen=100,
            findings_suppressed=20,
            findings_acted_on=60,
        )
        d = m.to_dict()
        assert d["total_findings_seen"] == 100
        assert d["suppression_ratio"] == 0.2
        assert d["action_ratio"] == 0.75

    def test_round_trip(self):
        m = OrchestrationMetrics(
            total_findings_seen=50,
            findings_suppressed=10,
            findings_acted_on=30,
        )
        d = m.to_dict()
        restored = OrchestrationMetrics.from_dict(d)
        assert restored.total_findings_seen == 50
        assert restored.findings_suppressed == 10
        assert restored.findings_acted_on == 30


class TestOutcomeCentricEffectiveness:
    def test_record_verification_updates_counters_and_kpis(self):
        m = OrchestrationMetrics()
        m.record_verification(
            changed_file_count=4,
            loc_changed=200,
            resolved_count=2,
            new_finding_count=1,
        )

        serialized = m.to_dict()
        assert serialized["verification_runs"] == 1
        assert serialized["changed_files_total"] == 4
        assert serialized["loc_changed_total"] == 200
        assert serialized["resolved_findings_total"] == 2
        assert serialized["new_findings_total"] == 1
        assert serialized["relocated_findings_total"] == 1
        assert serialized["resolved_findings_per_changed_file"] == 0.5
        assert serialized["resolved_findings_per_100_loc_changed"] == 1.0
        assert serialized["relocated_findings_ratio"] == 0.5
        assert serialized["verification_density"] == 0.25

    def test_low_effect_high_churn_warning_is_deterministic(self):
        s = DriftSession(
            session_id="abc",
            repo_path="/tmp/repo",
            effectiveness_thresholds={
                "low_effect_resolved_per_changed_file": 0.3,
                "low_effect_resolved_per_100_loc_changed": 0.6,
                "high_churn_min_changed_files": 3,
                "high_churn_min_loc_changed": 120,
            },
        )
        s.metrics.record_verification(
            changed_file_count=8,
            loc_changed=400,
            resolved_count=1,
            new_finding_count=2,
        )

        summary = s.summary()
        warnings = summary["effectiveness_warnings"]
        assert summary["orchestration_metrics"]["changed_files_total"] == 8
        assert any(w["code"] == "low_effect_high_churn" for w in warnings)

    def test_identical_verification_payload_is_not_counted_twice(self):
        s = DriftSession(session_id="abc", repo_path="/tmp/repo")
        payload = {
            "changed_files": ["src/a.py"],
            "changed_file_count": 1,
            "changed_loc": 20,
            "resolved_count": 2,
            "new_finding_count": 1,
        }

        _update_session_from_verification_result(s, payload)
        _update_session_from_verification_result(s, payload)

        assert s.metrics.verification_runs == 1
        assert s.metrics.changed_files_total == 1
        assert s.metrics.loc_changed_total == 20
        assert s.metrics.resolved_findings_total == 2
