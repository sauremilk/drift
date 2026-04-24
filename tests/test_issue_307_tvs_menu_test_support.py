from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import FileHistory
from drift.signals.temporal_volatility import TemporalVolatilitySignal

ISSUE_307_FILE = Path("extensions/telegram/src/bot-native-commands.menu-test-support.ts")


def _baseline_histories() -> dict[str, FileHistory]:
    histories: dict[str, FileHistory] = {}
    for i in range(9):
        histories[f"src/stable_{i}.py"] = FileHistory(
            path=Path(f"src/stable_{i}.py"),
            total_commits=3,
            unique_authors=1,
            change_frequency_30d=1.0,
            defect_correlated_commits=0,
        )
    return histories


def test_issue_307_menu_test_support_is_test_context() -> None:
    assert is_test_file(ISSUE_307_FILE)
    assert classify_file_context(ISSUE_307_FILE) == "test"


def test_issue_307_tvs_skips_menu_test_support_hotspot() -> None:
    histories = _baseline_histories()
    histories[ISSUE_307_FILE.as_posix()] = FileHistory(
        path=ISSUE_307_FILE,
        total_commits=90,
        unique_authors=24,
        change_frequency_30d=31.0,
        defect_correlated_commits=51,
        ai_attributed_commits=67,
    )
    histories["src/hot_module.py"] = FileHistory(
        path=Path("src/hot_module.py"),
        total_commits=55,
        unique_authors=12,
        change_frequency_30d=22.0,
        defect_correlated_commits=8,
        ai_attributed_commits=25,
    )

    findings = TemporalVolatilitySignal().analyze([], histories, DriftConfig())

    assert any(f.file_path.as_posix() == "src/hot_module.py" for f in findings)
    assert all(f.file_path.as_posix() != ISSUE_307_FILE.as_posix() for f in findings)
