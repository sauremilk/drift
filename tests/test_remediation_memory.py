"""Tests for ADR-072: Remediation Memory — outcome-informed fix recommendations.

Tests the enhanced ``similar_outcomes()`` method on RepairTemplateRegistry
and the enrichment of fix-plan tasks via ``_enrich_tasks_with_similar_outcomes``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from drift.models import Severity
from drift.models._agent import AgentTask
from drift.repair_template_registry import (
    RepairTemplateRegistry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(
    signal: str = "pattern_fragmentation",
    fix_template_class: str = "extract-function",
    context: str = "production",
    task_id: str = "t-001",
) -> AgentTask:
    return AgentTask(
        id=task_id,
        signal_type=signal,
        severity=Severity.MEDIUM,
        priority=1,
        title="Test task",
        description="desc",
        action="fix it",
        metadata={
            "fix_template_class": fix_template_class,
            "finding_context": context,
        },
    )


def _registry_with_outcomes(
    tmp_path: Path,
    outcomes: list[dict],
) -> RepairTemplateRegistry:
    """Create a registry loaded from given outcome records."""
    outcomes_path = tmp_path / "outcomes.jsonl"
    seed_path = tmp_path / "templates.json"
    seed_path.write_text('{"entries": []}', encoding="utf-8")
    outcomes_path.write_text(
        "\n".join(json.dumps(o) for o in outcomes),
        encoding="utf-8",
    )
    reg = RepairTemplateRegistry()
    reg.load(seed_path=seed_path, outcomes_path=outcomes_path)
    return reg


# ---------------------------------------------------------------------------
# similar_outcomes tests
# ---------------------------------------------------------------------------


class TestSimilarOutcomes:
    def test_returns_none_when_no_data(self, tmp_path: Path) -> None:
        reg = _registry_with_outcomes(tmp_path, [])
        result = reg.similar_outcomes("PFS", "extract-function")
        assert result is None

    def test_returns_summary_with_counts(self, tmp_path: Path) -> None:
        outcomes = [
            {
                "signal": "PFS",
                "edit_kind": "extract-function",
                "context_class": "production",
                "direction": "improving",
            },
            {
                "signal": "PFS",
                "edit_kind": "extract-function",
                "context_class": "production",
                "direction": "improving",
            },
            {
                "signal": "PFS",
                "edit_kind": "extract-function",
                "context_class": "production",
                "direction": "regressing",
            },
        ]
        reg = _registry_with_outcomes(tmp_path, outcomes)
        result = reg.similar_outcomes("PFS", "extract-function")

        assert result is not None
        assert result["total_outcomes"] == 3
        assert result["improving"] == 2
        assert result["regressing"] == 1
        assert result["stable"] == 0
        assert isinstance(result["known_regressions"], list)

    def test_confidence_none_below_threshold(self, tmp_path: Path) -> None:
        # Only 2 outcomes < MIN_OUTCOMES_FOR_CONFIDENCE (3)
        outcomes = [
            {
                "signal": "PFS",
                "edit_kind": "extract-function",
                "context_class": "production",
                "direction": "improving",
            },
            {
                "signal": "PFS",
                "edit_kind": "extract-function",
                "context_class": "production",
                "direction": "stable",
            },
        ]
        reg = _registry_with_outcomes(tmp_path, outcomes)
        result = reg.similar_outcomes("PFS", "extract-function")

        assert result is not None
        # confidence requires improving+regressing >= MIN_OUTCOMES_FOR_CONFIDENCE
        assert result["confidence"] is None

    def test_confidence_computed_above_threshold(self, tmp_path: Path) -> None:
        outcomes = [
            {
                "signal": "PFS",
                "edit_kind": "extract-function",
                "context_class": "production",
                "direction": d,
            }
            for d in ["improving", "improving", "regressing"]
        ]
        reg = _registry_with_outcomes(tmp_path, outcomes)
        result = reg.similar_outcomes("PFS", "extract-function")

        assert result is not None
        assert result["confidence"] == pytest.approx(2 / 3, abs=0.01)

    def test_wildcard_fallback(self, tmp_path: Path) -> None:
        """Lookup with context_class=test falls back to * when no exact match."""
        outcomes = [
            {
                "signal": "PFS",
                "edit_kind": "extract-function",
                "context_class": "*",
                "direction": "improving",
            },
        ]
        reg = _registry_with_outcomes(tmp_path, outcomes)
        result = reg.similar_outcomes("PFS", "extract-function", context_class="test")

        assert result is not None
        assert result["total_outcomes"] == 1


# ---------------------------------------------------------------------------
# Enhanced record_outcome tests
# ---------------------------------------------------------------------------


class TestEnhancedRecordOutcome:
    def test_new_fields_persisted(self, tmp_path: Path) -> None:
        outcomes_path = tmp_path / "outcomes.jsonl"
        seed_path = tmp_path / "templates.json"
        seed_path.write_text('{"entries": []}', encoding="utf-8")

        reg = RepairTemplateRegistry()
        reg.load(seed_path=seed_path, outcomes_path=outcomes_path)

        reg.record_outcome(
            signal="PFS",
            edit_kind="extract-function",
            direction="improving",
            task_id="task-123",
            new_findings_count=2,
            resolved_count=5,
            outcomes_path=outcomes_path,
        )

        line = outcomes_path.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        assert record["task_id"] == "task-123"
        assert record["new_findings_count"] == 2
        assert record["resolved_count"] == 5

    def test_defaults_for_new_fields(self, tmp_path: Path) -> None:
        outcomes_path = tmp_path / "outcomes.jsonl"
        seed_path = tmp_path / "templates.json"
        seed_path.write_text('{"entries": []}', encoding="utf-8")

        reg = RepairTemplateRegistry()
        reg.load(seed_path=seed_path, outcomes_path=outcomes_path)

        reg.record_outcome(
            signal="PFS",
            edit_kind="extract-function",
            direction="stable",
            outcomes_path=outcomes_path,
        )

        line = outcomes_path.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        assert record["task_id"] == ""
        assert record["new_findings_count"] == 0
        assert record["resolved_count"] == 0


# ---------------------------------------------------------------------------
# _enrich_tasks_with_similar_outcomes integration test
# ---------------------------------------------------------------------------


class TestEnrichTasks:
    def test_enrichment_attaches_outcomes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tasks get similar_outcomes when registry has data."""
        outcomes = [
            {
                "signal": "pattern_fragmentation",
                "edit_kind": "extract-function",
                "context_class": "production",
                "direction": d,
            }
            for d in ["improving", "improving", "regressing", "stable"]
        ]
        reg = _registry_with_outcomes(tmp_path, outcomes)

        # Monkeypatch the singleton to return our test registry
        import drift.repair_template_registry as rtr_mod

        monkeypatch.setattr(rtr_mod, "_registry", reg)

        from drift.api.fix_plan import _enrich_tasks_with_similar_outcomes

        tasks = [_make_task()]
        _enrich_tasks_with_similar_outcomes(tasks)

        assert tasks[0].similar_outcomes is not None
        assert tasks[0].similar_outcomes["total_outcomes"] == 4
        assert tasks[0].similar_outcomes["improving"] == 2

    def test_enrichment_skips_when_no_template_class(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tasks without fix_template_class don't get outcomes."""
        outcomes = [
            {
                "signal": "pattern_fragmentation",
                "edit_kind": "extract-function",
                "context_class": "production",
                "direction": "improving",
            },
        ]
        reg = _registry_with_outcomes(tmp_path, outcomes)

        import drift.repair_template_registry as rtr_mod

        monkeypatch.setattr(rtr_mod, "_registry", reg)

        from drift.api.fix_plan import _enrich_tasks_with_similar_outcomes

        task = _make_task(fix_template_class="")
        _enrich_tasks_with_similar_outcomes([task])

        assert task.similar_outcomes is None

    def test_enrichment_survives_registry_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If registry raises, enrichment is a no-op."""
        import drift.repair_template_registry as rtr_mod

        def failing_get_registry():
            raise RuntimeError("test failure")

        monkeypatch.setattr(rtr_mod, "get_registry", failing_get_registry)

        from drift.api.fix_plan import _enrich_tasks_with_similar_outcomes

        task = _make_task()
        # Should not raise
        _enrich_tasks_with_similar_outcomes([task])
        assert task.similar_outcomes is None
