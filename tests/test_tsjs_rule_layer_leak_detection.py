from __future__ import annotations

from pathlib import Path

from drift.rules.tsjs.layer_leak_detection import run_layer_leak_detection


def test_positive_fixture_produces_exactly_one_finding_with_required_fields() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "tsjs_rule_layer_leak" / "positive"

    findings = run_layer_leak_detection(
        repo_path=fixture_root,
        config_path=fixture_root / "layer_leak_detection.json",
    )

    assert len(findings) == 1
    assert set(findings[0].keys()) == {
        "rule_id",
        "source_file",
        "target_file",
        "source_layer",
        "target_layer",
    }
    assert findings[0] == {
        "rule_id": "layer-leak-detection",
        "source_file": "src/infra/storage.ts",
        "target_file": "src/ui/view.ts",
        "source_layer": "infra",
        "target_layer": "ui",
    }


def test_negative_fixture_produces_no_findings() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "tsjs_rule_layer_leak" / "negative"

    findings = run_layer_leak_detection(
        repo_path=fixture_root,
        config_path=fixture_root / "layer_leak_detection.json",
    )

    assert findings == []
