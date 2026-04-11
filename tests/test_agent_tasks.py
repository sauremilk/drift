"""Tests for agent-tasks output format."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from drift.models import (
    Finding,
    RepoAnalysis,
    Severity,
    SignalType,
)
from drift.output.agent_tasks import (
    REPAIR_MATURITY,
    _generate_constraints,
    _task_id,
    analysis_to_agent_tasks,
    analysis_to_agent_tasks_json,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    signal_type: SignalType = SignalType.PATTERN_FRAGMENTATION,
    severity: Severity = Severity.HIGH,
    score: float = 0.7,
    title: str = "Test PFS finding",
    description: str = "Pattern fragmentation detected",
    file_path: str = "services/payment.py",
    fix: str | None = "Consolidate pattern variants",
    impact: float = 0.6,
    metadata: dict | None = None,
) -> Finding:
    return Finding(
        signal_type=signal_type,
        severity=severity,
        score=score,
        title=title,
        description=description,
        file_path=Path(file_path),
        start_line=10,
        end_line=30,
        related_files=[Path("services/order.py")],
        fix=fix,
        impact=impact,
        metadata=metadata or {"variant_count": 5, "module": "services"},
    )


def _make_analysis(findings: list[Finding] | None = None) -> RepoAnalysis:
    return RepoAnalysis(
        repo_path=Path("/tmp/test-repo"),
        analyzed_at=datetime.datetime(2026, 3, 26, 12, 0, 0),
        drift_score=0.45,
        findings=findings or [],
    )


# ---------------------------------------------------------------------------
# Task ID determinism
# ---------------------------------------------------------------------------


class TestTaskId:
    def test_same_input_same_id(self) -> None:
        f = _make_finding()
        assert _task_id(f) == _task_id(f)

    def test_different_title_different_id(self) -> None:
        f1 = _make_finding(title="Finding A")
        f2 = _make_finding(title="Finding B")
        assert _task_id(f1) != _task_id(f2)

    def test_different_file_different_id(self) -> None:
        f1 = _make_finding(file_path="a.py")
        f2 = _make_finding(file_path="b.py")
        assert _task_id(f1) != _task_id(f2)

    def test_id_has_signal_prefix(self) -> None:
        f = _make_finding(signal_type=SignalType.PATTERN_FRAGMENTATION)
        assert _task_id(f).startswith("pfs-")

    def test_avs_prefix(self) -> None:
        f = _make_finding(signal_type=SignalType.ARCHITECTURE_VIOLATION)
        assert _task_id(f).startswith("avs-")


# ---------------------------------------------------------------------------
# Empty findings
# ---------------------------------------------------------------------------


class TestEmptyFindings:
    def test_empty_findings_empty_tasks(self) -> None:
        analysis = _make_analysis(findings=[])
        tasks = analysis_to_agent_tasks(analysis)
        assert tasks == []

    def test_empty_findings_json(self) -> None:
        analysis = _make_analysis(findings=[])
        raw = analysis_to_agent_tasks_json(analysis)
        data = json.loads(raw)
        assert data["task_count"] == 0
        assert data["tasks"] == []
        assert data["schema"] == "agent-tasks-v2"


# ---------------------------------------------------------------------------
# PFS finding → task
# ---------------------------------------------------------------------------


class TestPfsTask:
    def test_pfs_finding_produces_task(self) -> None:
        f = _make_finding()
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert len(tasks) == 1

        t = tasks[0]
        assert t.signal_type == SignalType.PATTERN_FRAGMENTATION
        assert t.severity == Severity.HIGH
        assert t.priority == 1
        assert t.file_path == "services/payment.py"

    def test_pfs_success_criteria(self) -> None:
        f = _make_finding()
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        t = tasks[0]

        assert len(t.success_criteria) >= 2
        assert any("pattern" in c.lower() or "variant" in c.lower() for c in t.success_criteria)
        assert any("test" in c.lower() for c in t.success_criteria)

    def test_pfs_expected_effect(self) -> None:
        f = _make_finding()
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert "variant" in tasks[0].expected_effect.lower()


# ---------------------------------------------------------------------------
# AVS circular → task with dependencies
# ---------------------------------------------------------------------------


class TestAvsDependencies:
    def test_circular_dep_task(self) -> None:
        f = _make_finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            title="Circular dependency in services",
            description="Circular import detected",
            metadata={"cycle": ["services.a", "services.b"]},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert len(tasks) == 1
        assert "circular" in tasks[0].title.lower()

    def test_circular_blocks_layer_violation(self) -> None:
        circular = _make_finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            title="Circular dependency in services",
            description="Circular import between services.a and services.b",
            file_path="services/a.py",
            metadata={"cycle": ["services.a", "services.b"]},
        )
        layer = _make_finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            title="Upward layer import in services",
            description="services.a imports from api layer",
            file_path="services/b.py",
            metadata={},
        )
        analysis = _make_analysis(findings=[circular, layer])
        tasks = analysis_to_agent_tasks(analysis)

        # Both should produce tasks
        assert len(tasks) == 2

        # The layer task should depend on the circular task
        circular_task = next(t for t in tasks if "circular" in t.title.lower())
        layer_task = next(t for t in tasks if "upward" in t.title.lower())
        assert circular_task.id in layer_task.depends_on


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------


class TestPriorityOrdering:
    def test_higher_severity_higher_priority(self) -> None:
        critical = _make_finding(
            severity=Severity.CRITICAL,
            score=0.9,
            impact=0.9,
            title="Critical PFS",
        )
        low = _make_finding(
            severity=Severity.LOW,
            score=0.3,
            impact=0.2,
            title="Low PFS",
        )
        analysis = _make_analysis(findings=[low, critical])
        tasks = analysis_to_agent_tasks(analysis)
        assert len(tasks) == 2
        assert tasks[0].priority < tasks[1].priority  # lower number = higher priority
        assert tasks[0].severity == Severity.CRITICAL

    def test_priorities_are_sequential(self) -> None:
        findings = [
            _make_finding(title=f"PFS {i}", score=0.9 - i * 0.1, impact=0.9 - i * 0.1)
            for i in range(5)
        ]
        analysis = _make_analysis(findings=findings)
        tasks = analysis_to_agent_tasks(analysis)
        priorities = [t.priority for t in tasks]
        assert priorities == list(range(1, len(tasks) + 1))


# ---------------------------------------------------------------------------
# Findings without recommender are skipped (unless they have .fix)
# ---------------------------------------------------------------------------


class TestFilteringBehavior:
    def test_report_only_signal_without_fix_skipped(self) -> None:
        f = _make_finding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            title="Broad exceptions",
            fix=None,
            metadata={},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert tasks == []

    def test_report_only_signal_with_fix_included(self) -> None:
        f = _make_finding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            title="Broad exceptions",
            fix="Replace bare except with specific exception types",
            metadata={},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert len(tasks) == 1
        assert "Replace bare except" in tasks[0].action


# ---------------------------------------------------------------------------
# JSON schema validation
# ---------------------------------------------------------------------------


class TestJsonSchema:
    def test_all_required_fields_present(self) -> None:
        f = _make_finding()
        analysis = _make_analysis(findings=[f])
        raw = analysis_to_agent_tasks_json(analysis)
        data = json.loads(raw)

        # Top-level fields
        assert "version" in data
        assert "schema" in data
        assert "repo" in data
        assert "analyzed_at" in data
        assert "drift_score" in data
        assert "severity" in data
        assert "task_count" in data
        assert "tasks" in data
        assert data["task_count"] == len(data["tasks"])

        # Task fields
        task = data["tasks"][0]
        required_fields = [
            "id",
            "signal_type",
            "severity",
            "priority",
            "title",
            "description",
            "action",
            "file_path",
            "start_line",
            "end_line",
            "related_files",
            "complexity",
            "expected_effect",
            "success_criteria",
            "depends_on",
            "metadata",
            "automation_fit",
            "review_risk",
            "change_scope",
            "verification_strength",
            "constraints",
            "repair_maturity",
        ]
        for field in required_fields:
            assert field in task, f"Missing field: {field}"

    def test_json_is_valid(self) -> None:
        analysis = _make_analysis(findings=[_make_finding()])
        raw = analysis_to_agent_tasks_json(analysis)
        data = json.loads(raw)  # must not raise
        assert isinstance(data, dict)

    def test_action_is_nonempty(self) -> None:
        analysis = _make_analysis(findings=[_make_finding()])
        raw = analysis_to_agent_tasks_json(analysis)
        data = json.loads(raw)
        for task in data["tasks"]:
            assert task["action"], "action must not be empty"

    def test_success_criteria_are_nonempty(self) -> None:
        analysis = _make_analysis(findings=[_make_finding()])
        raw = analysis_to_agent_tasks_json(analysis)
        data = json.loads(raw)
        for task in data["tasks"]:
            assert len(task["success_criteria"]) > 0

    def test_expected_effect_is_nonempty(self) -> None:
        analysis = _make_analysis(findings=[_make_finding()])
        raw = analysis_to_agent_tasks_json(analysis)
        data = json.loads(raw)
        for task in data["tasks"]:
            assert task["expected_effect"], "expected_effect must not be empty"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_duplicate_findings_deduplicated(self) -> None:
        f1 = _make_finding(title="Same finding")
        f2 = _make_finding(title="Same finding")
        analysis = _make_analysis(findings=[f1, f2])
        tasks = analysis_to_agent_tasks(analysis)
        assert len(tasks) == 1

    def test_same_title_different_files_keep_correct_recommendations(self) -> None:
        f1 = _make_finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            title="Same finding",
            file_path="services/a.py",
            metadata={
                "variant_count": 3,
                "module": "services.a",
                "canonical_variant": "guard_clause",
            },
        )
        f2 = _make_finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            title="Same finding",
            file_path="services/b.py",
            metadata={
                "variant_count": 4,
                "module": "services.b",
                "canonical_variant": "early_return",
            },
        )

        analysis = _make_analysis(findings=[f1, f2])
        tasks = analysis_to_agent_tasks(analysis)

        assert len(tasks) == 2
        action_by_file = {t.file_path: t.action for t in tasks}
        assert "guard_clause" in action_by_file["services/a.py"]
        assert "early_return" in action_by_file["services/b.py"]


# ---------------------------------------------------------------------------
# MDS signal → task
# ---------------------------------------------------------------------------


class TestMdsTask:
    def test_mds_finding_produces_task(self) -> None:
        f = _make_finding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            title="Near-duplicate: foo and bar",
            description="Functions foo and bar are 95% similar",
            metadata={
                "function_a": "foo",
                "function_b": "bar",
                "similarity": 0.95,
                "file_a": "utils/helpers.py",
                "file_b": "utils/helpers.py",
            },
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert len(tasks) == 1
        assert "foo" in tasks[0].success_criteria[0]
        assert "bar" in tasks[0].success_criteria[0]


# ---------------------------------------------------------------------------
# Phase 1: Automation fitness classification
# ---------------------------------------------------------------------------


class TestAutomationClassification:
    def test_mds_default_classification(self) -> None:
        f = _make_finding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            title="Near-duplicate: foo and bar",
            metadata={
                "function_a": "foo",
                "function_b": "bar",
                "similarity": 0.95,
                "file_a": "utils/helpers.py",
                "file_b": "utils/helpers.py",
            },
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        t = tasks[0]
        assert t.automation_fit == "high"
        assert t.review_risk == "low"
        assert t.change_scope == "local"
        assert t.verification_strength == "strong"

    def test_mds_cross_file_bumps_scope(self) -> None:
        f = _make_finding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            title="Near-duplicate cross-file",
            metadata={
                "function_a": "foo",
                "function_b": "bar",
                "similarity": 0.9,
                "file_a": "utils/a.py",
                "file_b": "utils/b.py",
            },
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert tasks[0].change_scope == "module"

    def test_tvs_classification(self) -> None:
        f = _make_finding(
            signal_type=SignalType.TEMPORAL_VOLATILITY,
            title="High churn in services",
            metadata={"ai_ratio": 0.7, "change_frequency_30d": 5.0},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        t = tasks[0]
        assert t.automation_fit == "low"
        assert t.review_risk == "high"
        assert t.change_scope == "cross-module"
        assert t.verification_strength == "weak"

    def test_pfs_with_canonical_bumps_fit(self) -> None:
        f = _make_finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            title="PFS with canonical",
            metadata={
                "variant_count": 4,
                "module": "services",
                "canonical_variant": "try_except_log",
            },
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert tasks[0].automation_fit == "high"

    def test_many_related_files_bumps_scope(self) -> None:
        f = _make_finding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            title="Undocumented function",
            metadata={"function_name": "process", "complexity": 5, "has_docstring": False},
        )
        # Add 4+ related files
        f.related_files = [Path(f"mod/{i}.py") for i in range(5)]
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        # EDS base is "local", bumped to "module" by related_files > 3
        assert tasks[0].change_scope == "module"

    def test_high_complexity_lowers_fit(self) -> None:
        f = _make_finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            title="Circular dependency in core",
            metadata={"cycle": ["core.a", "core.b"]},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        # AVS base is "medium"; with explicit high complexity it drops to low
        # Simulate by checking the classifier directly
        from drift.output.agent_tasks import _classify_task as clf

        t = tasks[0]
        t.complexity = "high"
        t.depends_on = []  # reset
        clf(f, t)
        assert t.automation_fit == "low"

    def test_depends_on_bumps_risk(self) -> None:
        circular = _make_finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            title="Circular dependency in services",
            file_path="services/a.py",
            metadata={"cycle": ["services.a", "services.b"]},
        )
        layer = _make_finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            title="Upward layer import in services",
            file_path="services/b.py",
            metadata={},
        )
        analysis = _make_analysis(findings=[circular, layer])
        tasks = analysis_to_agent_tasks(analysis)
        layer_task = next(t for t in tasks if "upward" in t.title.lower())
        # AVS base risk is "medium"; depends_on bumps to "high"
        assert layer_task.review_risk == "high"

    def test_classification_in_json(self) -> None:
        f = _make_finding()
        analysis = _make_analysis(findings=[f])
        raw = analysis_to_agent_tasks_json(analysis)
        data = json.loads(raw)
        task = data["tasks"][0]
        assert "automation_fit" in task
        assert "review_risk" in task
        assert "change_scope" in task
        assert "verification_strength" in task
        assert task["automation_fit"] in ("high", "medium", "low")
        assert task["review_risk"] in ("low", "medium", "high")
        assert task["change_scope"] in ("local", "module", "cross-module")
        assert task["verification_strength"] in ("strong", "moderate", "weak")


# ---------------------------------------------------------------------------
# Phase 2: Do-not-over-fix constraints
# ---------------------------------------------------------------------------


class TestConstraints:
    def test_universal_constraints_always_present(self) -> None:
        f = _make_finding()
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        t = tasks[0]
        assert len(t.constraints) >= 4
        assert any("minimal" in c.lower() for c in t.constraints)
        assert any("refactor" in c.lower() for c in t.constraints)

    def test_mds_has_body_hash_constraint(self) -> None:
        f = _make_finding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            title="Near-duplicate: foo and bar",
            metadata={"function_a": "foo", "function_b": "bar", "similarity": 0.95},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert any("sha256" in c.lower() for c in tasks[0].constraints)

    def test_dia_has_phantom_constraint(self) -> None:
        f = _make_finding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            title="Phantom reference in README",
            metadata={"contradiction_type": "phantom"},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert any("phantom" in c.lower() for c in tasks[0].constraints)

    def test_pfs_has_canonical_constraint(self) -> None:
        f = _make_finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            title="PFS finding",
            metadata={"variant_count": 3, "module": "svc"},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert any("canonical" in c.lower() for c in tasks[0].constraints)

    def test_eds_has_trivial_docstring_constraint(self) -> None:
        f = _make_finding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            title="Undocumented complex function",
            metadata={"function_name": "process", "complexity": 15, "has_docstring": False},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert any("trivial" in c.lower() for c in tasks[0].constraints)

    def test_constraints_in_json(self) -> None:
        f = _make_finding()
        analysis = _make_analysis(findings=[f])
        raw = analysis_to_agent_tasks_json(analysis)
        data = json.loads(raw)
        task = data["tasks"][0]
        assert "constraints" in task
        assert isinstance(task["constraints"], list)
        assert len(task["constraints"]) >= 4

    def test_generate_constraints_direct(self) -> None:
        f = _make_finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION, title="Layer violation", metadata={}
        )
        constraints = _generate_constraints(f)
        assert any("layer" in c.lower() for c in constraints)


# ---------------------------------------------------------------------------
# Phase 3: Enhanced success criteria (false-fix indicators)
# ---------------------------------------------------------------------------


class TestEnhancedSuccessCriteria:
    def test_mds_has_false_fix_indicator(self) -> None:
        f = _make_finding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            title="Near-duplicate: foo and bar",
            metadata={"function_a": "foo", "function_b": "bar", "similarity": 0.95},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        criteria = tasks[0].success_criteria
        assert any("false-fix" in c.lower() for c in criteria)

    def test_pfs_has_false_fix_indicator(self) -> None:
        f = _make_finding()
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        criteria = tasks[0].success_criteria
        assert any("false-fix" in c.lower() for c in criteria)

    def test_avs_circular_has_false_fix_indicator(self) -> None:
        f = _make_finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            title="Circular dependency in core",
            metadata={"cycle": ["core.a", "core.b"]},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        criteria = tasks[0].success_criteria
        assert any("false-fix" in c.lower() for c in criteria)

    def test_eds_has_false_fix_indicator(self) -> None:
        f = _make_finding(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            title="Undocumented function",
            metadata={"function_name": "do_thing", "complexity": 12, "has_docstring": False},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        criteria = tasks[0].success_criteria
        assert any("false-fix" in c.lower() for c in criteria)

    def test_tvs_has_side_effect_note(self) -> None:
        f = _make_finding(
            signal_type=SignalType.TEMPORAL_VOLATILITY,
            title="High churn",
            metadata={"ai_ratio": 0.5, "change_frequency_30d": 3.0},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        criteria = tasks[0].success_criteria
        assert any("side-effect" in c.lower() for c in criteria)

    def test_sms_has_false_fix_indicator(self) -> None:
        f = _make_finding(
            signal_type=SignalType.SYSTEM_MISALIGNMENT,
            title="Novel dependencies",
            metadata={"novel_imports": ["redis"]},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        criteria = tasks[0].success_criteria
        assert any("false-fix" in c.lower() for c in criteria)


# ---------------------------------------------------------------------------
# Phase 4: Repair maturity
# ---------------------------------------------------------------------------


class TestRepairMaturity:
    def test_mds_verified(self) -> None:
        f = _make_finding(
            signal_type=SignalType.MUTANT_DUPLICATE,
            title="Near-duplicate",
            metadata={"function_a": "a", "function_b": "b", "similarity": 0.9},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert tasks[0].repair_maturity == "verified"

    def test_dia_verified(self) -> None:
        f = _make_finding(
            signal_type=SignalType.DOC_IMPL_DRIFT,
            title="Phantom reference",
            metadata={"contradiction_type": "phantom"},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert tasks[0].repair_maturity == "verified"

    def test_pfs_verified(self) -> None:
        f = _make_finding()
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert tasks[0].repair_maturity == "verified"

    def test_avs_experimental(self) -> None:
        f = _make_finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            title="Circular dependency",
            metadata={"cycle": ["a", "b"]},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert tasks[0].repair_maturity == "experimental"

    def test_tvs_indirect_only(self) -> None:
        f = _make_finding(
            signal_type=SignalType.TEMPORAL_VOLATILITY,
            title="High churn",
            metadata={"ai_ratio": 0.5, "change_frequency_30d": 3.0},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert tasks[0].repair_maturity == "indirect-only"

    def test_sms_indirect_only(self) -> None:
        f = _make_finding(
            signal_type=SignalType.SYSTEM_MISALIGNMENT,
            title="Novel deps",
            metadata={"novel_imports": ["redis"]},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert tasks[0].repair_maturity == "indirect-only"

    def test_unknown_signal_defaults_experimental(self) -> None:
        f = _make_finding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            title="Broad exceptions",
            fix="Fix the exceptions",
            metadata={},
        )
        analysis = _make_analysis(findings=[f])
        tasks = analysis_to_agent_tasks(analysis)
        assert tasks[0].repair_maturity == "experimental"

    def test_maturity_in_json(self) -> None:
        f = _make_finding()
        analysis = _make_analysis(findings=[f])
        raw = analysis_to_agent_tasks_json(analysis)
        data = json.loads(raw)
        task = data["tasks"][0]
        assert "repair_maturity" in task
        assert task["repair_maturity"] in ("verified", "experimental", "indirect-only")

    def test_repair_maturity_constant_has_all_scored_signals(self) -> None:
        scored_signals = {
            SignalType.MUTANT_DUPLICATE,
            SignalType.DOC_IMPL_DRIFT,
            SignalType.PATTERN_FRAGMENTATION,
            SignalType.EXPLAINABILITY_DEFICIT,
            SignalType.ARCHITECTURE_VIOLATION,
            SignalType.TEMPORAL_VOLATILITY,
            SignalType.SYSTEM_MISALIGNMENT,
        }
        for sig in scored_signals:
            assert sig.value in REPAIR_MATURITY or sig in REPAIR_MATURITY
