"""Tests for fix-loop batch metadata (ADR-020).

Covers:
- Fix-template equivalence classes
- Batch metadata injection
- API response fields
- Diff signal filtering
- remaining_by_signal in fix_plan
- resolved_count_by_rule in diff
"""

from __future__ import annotations

from pathlib import PurePosixPath

from drift.models import AgentTask, Finding, Severity, SignalType  # noqa: F811
from drift.output.agent_tasks import _fix_template_class, _inject_batch_metadata

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    signal: SignalType = SignalType.BROAD_EXCEPTION_MONOCULTURE,
    *,
    title: str = "bare except",
    file_path: str = "src/a.py",
    severity: Severity = Severity.MEDIUM,
    impact: float = 0.5,
    score: float = 0.3,
    fix: str = "Use specific exceptions",
    metadata: dict | None = None,
) -> Finding:
    return Finding(
        signal_type=signal,
        title=title,
        description="test finding",
        file_path=PurePosixPath(file_path),
        start_line=1,
        severity=severity,
        impact=impact,
        score=score,
        fix=fix,
        metadata=metadata or {},
    )


def _make_task(
    signal: SignalType = SignalType.BROAD_EXCEPTION_MONOCULTURE,
    *,
    file_path: str = "src/a.py",
    metadata: dict | None = None,
) -> AgentTask:
    return AgentTask(
        id=f"test-{file_path}",
        priority=1,
        signal_type=signal,
        severity=Severity.MEDIUM,
        title="test task",
        description="test description",
        action="fix it",
        file_path=file_path,
        start_line=1,
        symbol=None,
        related_files=[],
        complexity="low",
        automation_fit="high",
        review_risk="low",
        change_scope="single_file",
        constraints=[],
        success_criteria=["passes"],
        expected_effect="improvement",
        depends_on=[],
        metadata=metadata or {},
        repair_maturity="established",
    )


# ---------------------------------------------------------------------------
# Fix-template equivalence classes
# ---------------------------------------------------------------------------


class TestFixTemplateClass:
    def test_uniform_template_signal(self):
        """Uniform-template signals get signal-only key."""
        task = _make_task(SignalType.BROAD_EXCEPTION_MONOCULTURE)
        assert _fix_template_class(task) == "broad_exception_monoculture"

    def test_pfs_groups_by_canonical(self):
        """PFS tasks group by canonical pattern name."""
        task = _make_task(
            SignalType.PATTERN_FRAGMENTATION,
            metadata={"canonical": "factory_pattern"},
        )
        assert _fix_template_class(task) == "pattern_fragmentation:factory_pattern"

    def test_mds_groups_by_duplicate_group(self):
        """MDS tasks group by duplicate group."""
        task = _make_task(
            SignalType.MUTANT_DUPLICATE,
            metadata={"duplicate_group": "grp1"},
        )
        assert _fix_template_class(task) == "mutant_duplicate:grp1"

    def test_default_groups_by_rule_id(self):
        """Default signals group by signal:rule_id."""
        task = _make_task(
            SignalType.ARCHITECTURE_VIOLATION,
            metadata={"rule_id": "circular_dep"},
        )
        assert _fix_template_class(task) == "architecture_violation:circular_dep"

    def test_default_no_rule_id(self):
        """Without rule_id, key is just signal name."""
        task = _make_task(SignalType.ARCHITECTURE_VIOLATION, metadata={})
        assert _fix_template_class(task) == "architecture_violation"


# ---------------------------------------------------------------------------
# Batch metadata injection
# ---------------------------------------------------------------------------


class TestInjectBatchMetadata:
    def test_single_task_not_batch_eligible(self):
        """A single task in its class is not batch-eligible."""
        tasks = [_make_task(file_path="src/a.py")]
        _inject_batch_metadata(tasks)
        assert tasks[0].metadata["batch_eligible"] is False
        assert tasks[0].metadata["pattern_instance_count"] == 1

    def test_multiple_tasks_same_class_batch_eligible(self):
        """Multiple tasks in same class are batch-eligible."""
        tasks = [
            _make_task(file_path="src/a.py"),
            _make_task(file_path="src/b.py"),
            _make_task(file_path="src/c.py"),
        ]
        _inject_batch_metadata(tasks)
        for t in tasks:
            assert t.metadata["batch_eligible"] is True
            assert t.metadata["pattern_instance_count"] == 3
            assert sorted(t.metadata["affected_files_for_pattern"]) == [
                "src/a.py",
                "src/b.py",
                "src/c.py",
            ]

    def test_mixed_classes(self):
        """Tasks in different classes get independent batch metadata."""
        t_bem = _make_task(SignalType.BROAD_EXCEPTION_MONOCULTURE, file_path="src/a.py")
        t_gcd = _make_task(SignalType.GUARD_CLAUSE_DEFICIT, file_path="src/b.py")
        tasks = [t_bem, t_gcd]
        _inject_batch_metadata(tasks)
        assert t_bem.metadata["batch_eligible"] is False
        assert t_gcd.metadata["batch_eligible"] is False


# ---------------------------------------------------------------------------
# API response fields
# ---------------------------------------------------------------------------


class TestApiResponseBatchFields:
    def test_task_api_dict_includes_batch_fields(self):
        """_task_to_api_dict includes batch metadata fields."""
        from drift.api_helpers import _task_to_api_dict

        task = _make_task(metadata={
            "batch_eligible": True,
            "pattern_instance_count": 3,
            "affected_files_for_pattern": ["a.py", "b.py", "c.py"],
            "fix_template_class": "broad_exception_monoculture",
        })
        d = _task_to_api_dict(task)
        assert d["batch_eligible"] is True
        assert d["pattern_instance_count"] == 3
        assert d["affected_files_for_pattern"] == ["a.py", "b.py", "c.py"]
        assert d["fix_template_class"] == "broad_exception_monoculture"

    def test_task_api_dict_defaults_when_no_batch(self):
        """_task_to_api_dict provides defaults when batch metadata is absent."""
        from drift.api_helpers import _task_to_api_dict

        task = _make_task(metadata={})
        d = _task_to_api_dict(task)
        assert d["batch_eligible"] is False
        assert d["pattern_instance_count"] == 1
        assert d["affected_files_for_pattern"] == []
        assert d["fix_template_class"] == ""


# ---------------------------------------------------------------------------
# canonical_refs in API response (ADR-023)
# ---------------------------------------------------------------------------


class TestCanonicalRefsInApiDict:
    def test_canonical_refs_from_exemplar_metadata(self):
        """canonical_exemplar in metadata produces a file_ref canonical_ref."""
        from drift.api_helpers import _task_to_api_dict

        task = _make_task(
            signal=SignalType.PATTERN_FRAGMENTATION,
            metadata={"canonical_exemplar": "services/handler_a.py:5"},
        )
        d = _task_to_api_dict(task)
        assert len(d["canonical_refs"]) == 1
        ref = d["canonical_refs"][0]
        assert ref["type"] == "file_ref"
        assert ref["ref"] == "services/handler_a.py:5"
        assert ref["source_signal"] == "PFS"

    def test_canonical_refs_from_negative_context(self):
        """canonical_alternative in NegativeContext produces a pattern ref."""
        from drift.api_helpers import _task_to_api_dict
        from drift.models import (
            NegativeContext,
            NegativeContextCategory,
            NegativeContextScope,
        )

        nc = NegativeContext(
            anti_pattern_id="neg-test",
            category=NegativeContextCategory.ARCHITECTURE,
            source_signal=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.MEDIUM,
            scope=NegativeContextScope.MODULE,
            description="test",
            forbidden_pattern="# bad",
            canonical_alternative="# REQUIRED: Follow the canonical pattern:\n# return_dict",
        )
        task = _make_task(
            signal=SignalType.PATTERN_FRAGMENTATION,
            metadata={},
        )
        task.negative_context = [nc]
        d = _task_to_api_dict(task)
        assert len(d["canonical_refs"]) == 1
        ref = d["canonical_refs"][0]
        assert ref["type"] == "pattern"
        assert "REQUIRED" in ref["ref"]
        assert ref["source_signal"] == "PFS"

    def test_canonical_refs_empty_when_no_data(self):
        """No canonical_refs when neither metadata nor NC provide them."""
        from drift.api_helpers import _task_to_api_dict

        task = _make_task(metadata={})
        d = _task_to_api_dict(task)
        assert d["canonical_refs"] == []

    def test_canonical_refs_max_three(self):
        """canonical_refs are capped at 3 entries."""
        from drift.api_helpers import _task_to_api_dict
        from drift.models import (
            NegativeContext,
            NegativeContextCategory,
            NegativeContextScope,
        )

        ncs = [
            NegativeContext(
                anti_pattern_id=f"neg-{i}",
                category=NegativeContextCategory.ARCHITECTURE,
                source_signal=SignalType.PATTERN_FRAGMENTATION,
                severity=Severity.MEDIUM,
                scope=NegativeContextScope.MODULE,
                description="test",
                forbidden_pattern="# bad",
                canonical_alternative=f"# Pattern variant {i}",
            )
            for i in range(5)
        ]
        task = _make_task(
            signal=SignalType.PATTERN_FRAGMENTATION,
            metadata={"canonical_exemplar": "a.py:1"},
        )
        task.negative_context = ncs
        d = _task_to_api_dict(task)
        assert len(d["canonical_refs"]) == 3


# ---------------------------------------------------------------------------
# fix_plan agent_instruction
# ---------------------------------------------------------------------------


class TestFixPlanAgentInstruction:
    def test_batch_instruction_when_batch_eligible(self):
        """Agent instruction mentions batch workflow when batch tasks exist."""
        from drift.api import _fix_plan_agent_instruction

        task = _make_task(metadata={"batch_eligible": True})
        instruction = _fix_plan_agent_instruction([task])
        assert "batch_eligible" in instruction
        assert "affected_files_for_pattern" in instruction

    def test_default_instruction_when_no_batch(self):
        """Agent instruction is file-by-file when no batch tasks."""
        from drift.api import _fix_plan_agent_instruction

        task = _make_task(metadata={})
        instruction = _fix_plan_agent_instruction([task])
        assert "Do not batch" in instruction


# ---------------------------------------------------------------------------
# V-6: expected_score_delta in AgentTask
# ---------------------------------------------------------------------------


class TestExpectedScoreDelta:
    def test_score_delta_populated_from_finding(self):
        """Finding.score_contribution flows into AgentTask.expected_score_delta."""
        from drift.output.agent_tasks import _finding_to_task

        f = _make_finding(score=0.42)
        f.score_contribution = 0.035
        task = _finding_to_task(f, None, priority=1)
        assert task.expected_score_delta == 0.035

    def test_score_delta_defaults_to_zero(self):
        """Without score_contribution, expected_score_delta is 0.0."""
        task = _make_task()
        assert task.expected_score_delta == 0.0

    def test_score_delta_in_api_dict(self):
        """expected_score_delta appears in the API serialization."""
        from drift.api_helpers import _task_to_api_dict

        task = _make_task()
        task.expected_score_delta = 0.042
        d = _task_to_api_dict(task)
        assert d["expected_score_delta"] == 0.042


# ---------------------------------------------------------------------------
# V-13: dependency_depth computation
# ---------------------------------------------------------------------------


class TestDependencyDepth:
    def test_no_dependencies_all_depth_zero(self):
        """Tasks without dependencies all get depth 0."""
        from drift.output.agent_tasks import _compute_dependencies

        tasks = [_make_task(file_path="a.py"), _make_task(file_path="b.py")]
        _compute_dependencies(tasks)
        for t in tasks:
            assert t.metadata.get("dependency_depth") == 0

    def test_avs_circular_blocks_non_circular(self):
        """Circular AVS at depth 0, dependent non-circular AVS at depth 1."""
        from drift.output.agent_tasks import _compute_dependencies

        circ = _make_task(
            signal=SignalType.ARCHITECTURE_VIOLATION,
            file_path="pkg/mod.py",
        )
        circ.id = "circ-1"
        circ.title = "Circular import in pkg"

        non_circ = _make_task(
            signal=SignalType.ARCHITECTURE_VIOLATION,
            file_path="pkg/other.py",
        )
        non_circ.id = "layer-1"
        non_circ.title = "Layer violation in pkg"

        _compute_dependencies([circ, non_circ])
        assert circ.metadata["dependency_depth"] == 0
        assert non_circ.metadata["dependency_depth"] == 1
        assert non_circ.depends_on == ["circ-1"]

    def test_unrelated_signal_gets_depth_zero(self):
        """Non-AVS tasks always get depth 0 even when AVS deps exist."""
        from drift.output.agent_tasks import _compute_dependencies

        circ = _make_task(
            signal=SignalType.ARCHITECTURE_VIOLATION,
            file_path="pkg/mod.py",
        )
        circ.id = "circ-1"
        circ.title = "Circular import in pkg"

        bem = _make_task(
            signal=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            file_path="pkg/util.py",
        )
        bem.id = "bem-1"

        _compute_dependencies([circ, bem])
        assert bem.metadata["dependency_depth"] == 0


# ---------------------------------------------------------------------------
# V-5: finding_count_by_signal in scan response
# ---------------------------------------------------------------------------


class TestFindingCountBySignal:
    def test_counter_present_in_scan_response(self, tmp_path):
        """Scan response includes finding_count_by_signal dict."""
        from drift.api import scan

        # Minimal repo structure to get findings
        (tmp_path / "a.py").write_text("x = 1\n")
        result = scan(str(tmp_path))
        # The key must exist and be a dict (may be empty for trivial repos)
        assert isinstance(result.get("finding_count_by_signal"), dict)


# ---------------------------------------------------------------------------
# ADR-021: Batch-dominant scan agent_instruction
# ---------------------------------------------------------------------------


class TestScanAgentInstruction:
    def test_high_finding_count_recommends_batch(self):
        """Large backlogs get batch-first instruction."""
        from drift.api import _scan_agent_instruction

        instr = _scan_agent_instruction(total_finding_count=50)
        assert "max_tasks=20" in instr
        assert "batch_eligible" in instr
        assert "drift_nudge" in instr

    def test_low_finding_count_recommends_nudge(self):
        """Small backlogs get nudge-first instruction."""
        from drift.api import _scan_agent_instruction

        instr = _scan_agent_instruction(total_finding_count=10)
        assert "drift_nudge" in instr
        assert "max_tasks=20" not in instr

    def test_threshold_boundary(self):
        """Exactly at threshold → small-backlog path."""
        from drift.api import _BATCH_SCAN_THRESHOLD, _scan_agent_instruction

        at_threshold = _scan_agent_instruction(
            total_finding_count=_BATCH_SCAN_THRESHOLD,
        )
        above_threshold = _scan_agent_instruction(
            total_finding_count=_BATCH_SCAN_THRESHOLD + 1,
        )
        assert "max_tasks=20" not in at_threshold
        assert "max_tasks=20" in above_threshold


# ---------------------------------------------------------------------------
# ADR-021: Fix-plan agent_instruction unified
# ---------------------------------------------------------------------------


class TestFixPlanAgentInstructionADR021:
    def test_batch_instruction_mentions_nudge(self):
        """Batch-eligible fix_plan instruction mentions nudge for inner loop."""
        from drift.api import _fix_plan_agent_instruction

        task = _make_task(metadata={"batch_eligible": True})
        instr = _fix_plan_agent_instruction([task])
        assert "drift_nudge" in instr
        assert "affected_files_for_pattern" in instr

    def test_non_batch_instruction_uses_nudge_not_diff(self):
        """Non-batch fix_plan instruction recommends nudge, not per-file diff."""
        from drift.api import _fix_plan_agent_instruction

        task = _make_task(metadata={})
        instr = _fix_plan_agent_instruction([task])
        assert "drift_nudge" in instr
        assert "Do not batch changes across unrelated" in instr
