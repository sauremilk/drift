"""Tests for scripts/test_orchestrator.py — pure path-to-tier mapping."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import test_orchestrator as to  # noqa: E402


def test_docs_only_skips() -> None:
    assert to.classify_paths(["docs/README.md", "POLICY.md"]) == ["skip"]


def test_signals_triggers_precision_recall() -> None:
    tiers = to.classify_paths(["src/drift/signals/avs.py"])
    assert "precision-recall" in tiers
    assert "test-dev" in tiers


def test_output_triggers_contract_before_dev() -> None:
    tiers = to.classify_paths(["src/drift/output/json_output.py"])
    assert tiers.index("test-contract") < tiers.index("test-dev")


def test_ingestion_triggers_test_dev() -> None:
    assert to.classify_paths(["src/drift/ingestion/file_discovery.py"]) == ["test-dev"]


def test_other_src_drift_uses_test_fast() -> None:
    assert to.classify_paths(["src/drift/cli.py"]) == ["test-fast"]


def test_tests_or_scripts_use_test_fast() -> None:
    assert to.classify_paths(["tests/test_cli.py"]) == ["test-fast"]
    assert to.classify_paths(["scripts/foo.py"]) == ["test-fast"]


def test_empty_diff_defaults_to_test_fast() -> None:
    assert to.classify_paths([]) == ["test-fast"]


def test_mixed_paths_deduplicate_tiers() -> None:
    tiers = to.classify_paths(
        [
            "src/drift/signals/avs.py",
            "src/drift/output/json_output.py",
            "tests/test_cli.py",
        ]
    )
    # Each tier appears at most once.
    assert len(tiers) == len(set(tiers))
    assert "precision-recall" in tiers
    assert "test-contract" in tiers


@pytest.mark.parametrize("tier", sorted(to.TIER_COMMANDS.keys()))
def test_all_declared_tiers_have_commands(tier: str) -> None:
    cmd = to.TIER_COMMANDS[tier]
    if tier == "skip":
        assert cmd == []
    else:
        assert cmd
        assert cmd[0].endswith("python") or cmd[0].endswith("python.exe") or "python" in cmd[0]
