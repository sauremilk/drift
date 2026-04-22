"""Tests for scripts/task_card.py — structure and scope-slot contract."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import task_card  # noqa: E402


@pytest.mark.parametrize("task_type", task_card.VALID_TYPES)
def test_build_card_contains_mandatory_slots(
    task_type: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every card must expose all four scope slots and the uncertainty block."""
    monkeypatch.setattr(task_card, "_gate_check_output", lambda _t: "(stub gate output)")
    monkeypatch.setattr(task_card, "_audit_diff_output", lambda: "(stub audit output)")

    output = task_card.build_card(task="demo task", task_type=task_type)

    for slot in ("Ziel:", "In-Scope:", "Out-of-Scope:", "Erfolgskriterien:"):
        assert slot in output, f"missing scope slot: {slot}"
    assert "Offene Unsicherheiten" in output
    assert "PFLICHT" in output
    assert "demo task" in output
    assert task_type in output


def test_build_card_includes_gate_and_audit_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(task_card, "_gate_check_output", lambda _t: "GATE-STUB")
    monkeypatch.setattr(task_card, "_audit_diff_output", lambda: "AUDIT-STUB")

    output = task_card.build_card(task="demo", task_type="feat")

    assert "Gate Check" in output
    assert "GATE-STUB" in output
    assert "Risk-Audit-Diff" in output
    assert "AUDIT-STUB" in output


def test_every_valid_type_has_gates_and_routing() -> None:
    """Every supported type must have both gate and routing entries."""
    for task_type in task_card.VALID_TYPES:
        assert task_type in task_card.GATES_BY_TYPE
        assert task_type in task_card.ROUTING_BY_TYPE
        assert task_card.GATES_BY_TYPE[task_type], f"empty gates for {task_type}"
        assert task_card.ROUTING_BY_TYPE[task_type], f"empty routing for {task_type}"


def test_cli_rejects_invalid_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["task_card.py", "--task", "x", "--type", "invalid"])
    with pytest.raises(SystemExit) as exc_info:
        task_card.main()
    assert exc_info.value.code != 0
