from __future__ import annotations

from pathlib import Path

from drift.rules.tsjs.circular_module_detection import run_circular_module_detection


def test_positive_fixture_produces_exactly_one_cycle_finding_with_required_fields() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "tsjs_rule_cycles" / "positive"

    findings = run_circular_module_detection(repo_path=fixture_root)

    assert len(findings) == 1
    assert set(findings[0].keys()) == {
        "rule_id",
        "cycle_nodes",
        "cycle_length",
    }
    assert findings[0] == {
        "rule_id": "circular-module-detection",
        "cycle_nodes": ["src/a.ts", "src/b.ts"],
        "cycle_length": 2,
    }


def test_negative_fixture_produces_no_findings() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "tsjs_rule_cycles" / "negative"

    findings = run_circular_module_detection(repo_path=fixture_root)

    assert findings == []
