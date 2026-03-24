from __future__ import annotations

from pathlib import Path

from drift.rules.tsjs.ui_to_infra_import_ban import run_ui_to_infra_import_ban


def test_positive_fixture_produces_exactly_one_finding_with_required_fields() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "tsjs_rule_ui_to_infra" / "positive"

    findings = run_ui_to_infra_import_ban(
        repo_path=fixture_root,
        config_path=fixture_root / "ui_to_infra_import_ban.json",
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
        "rule_id": "ui-to-infra-import-ban",
        "source_file": "src/ui/view.ts",
        "target_file": "src/infra/storage.ts",
        "source_layer": "ui",
        "target_layer": "infra",
    }


def test_negative_fixture_produces_no_findings() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "tsjs_rule_ui_to_infra" / "negative"

    findings = run_ui_to_infra_import_ban(
        repo_path=fixture_root,
        config_path=fixture_root / "ui_to_infra_import_ban.json",
    )

    assert findings == []
