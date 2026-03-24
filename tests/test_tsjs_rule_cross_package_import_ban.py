from __future__ import annotations

from pathlib import Path

from drift.rules.tsjs.cross_package_import_ban import run_cross_package_import_ban


def test_positive_fixture_produces_exactly_one_finding_with_required_fields() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "tsjs_rule_cross_package" / "positive"

    findings = run_cross_package_import_ban(
        repo_path=fixture_root,
        config_path=fixture_root / "cross_package_import_ban.json",
    )

    assert len(findings) == 1
    assert set(findings[0].keys()) == {
        "rule_id",
        "source_file",
        "target_file",
        "source_package",
        "target_package",
    }
    assert findings[0] == {
        "rule_id": "cross-package-import-ban",
        "source_file": "packages/app/src/main.ts",
        "target_file": "packages/ui/src/button.ts",
        "source_package": "packages/app",
        "target_package": "packages/ui",
    }


def test_negative_fixture_produces_no_findings() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "tsjs_rule_cross_package" / "negative"

    findings = run_cross_package_import_ban(
        repo_path=fixture_root,
        config_path=fixture_root / "cross_package_import_ban.json",
    )

    assert findings == []
