from __future__ import annotations

from dataclasses import fields
from typing import get_type_hints

from drift.models import (
    AgentTask,
    AutomationFit,
    ChangeScope,
    RepairMaturity,
    ReviewRisk,
    Severity,
    TaskComplexity,
    VerificationStrength,
)


def _field_type(model: type, name: str):
    resolved = get_type_hints(model)
    for f in fields(model):
        if f.name == name:
            return resolved.get(name, f.type)
    raise AssertionError(f"Field {name!r} not found")


def test_agent_task_classification_fields_are_typed_enums() -> None:
    assert _field_type(AgentTask, "complexity") is TaskComplexity
    assert _field_type(AgentTask, "automation_fit") is AutomationFit
    assert _field_type(AgentTask, "review_risk") is ReviewRisk
    assert _field_type(AgentTask, "change_scope") is ChangeScope
    assert _field_type(AgentTask, "verification_strength") is VerificationStrength
    assert _field_type(AgentTask, "repair_maturity") is RepairMaturity


def test_agent_task_classification_defaults_are_enum_values() -> None:
    task = AgentTask(
        id="t-458",
        signal_type="pattern_fragmentation",
        severity=Severity.MEDIUM,
        priority=1,
        title="t",
        description="d",
        action="a",
    )
    assert task.complexity == TaskComplexity.MEDIUM
    assert task.automation_fit == AutomationFit.MEDIUM
    assert task.review_risk == ReviewRisk.MEDIUM
    assert task.change_scope == ChangeScope.LOCAL
    assert task.verification_strength == VerificationStrength.MODERATE
    assert task.repair_maturity == RepairMaturity.EXPERIMENTAL