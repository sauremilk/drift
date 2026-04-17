from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from drift.models import RepoAnalysis
from drift.trend_history import apply_trend_and_persist_snapshot, save_history


def test_save_history_keeps_existing_file_when_atomic_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history_file = tmp_path / ".drift-cache" / "history.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    old_content = "[{\"drift_score\": 0.42}]\n"
    history_file.write_text(old_content, encoding="utf-8")

    real_replace = Path.replace

    def _fail_replace(self: Path, target: Path | str) -> Path:
        if Path(target) == history_file:
            raise OSError("simulated replace failure")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", _fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        save_history(history_file, [{"drift_score": 0.99, "scope": "repo"}])

    # Atomic persistence must preserve the previous file if replace fails.
    assert history_file.read_text(encoding="utf-8") == old_content


def test_apply_trend_and_persist_snapshot_logs_warning_on_corrupt_history(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    history_file = tmp_path / ".drift-cache" / "history.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text("{invalid json", encoding="utf-8")

    analysis = RepoAnalysis(
        repo_path=tmp_path,
        analyzed_at=datetime.now(UTC),
        drift_score=0.5,
        total_files=1,
    )

    with caplog.at_level(logging.WARNING):
        history_corrupt = apply_trend_and_persist_snapshot(
            tmp_path,
            ".drift-cache",
            analysis,
            scope="repo",
        )

    assert history_corrupt is True
    assert analysis.trend is not None
    assert analysis.trend.direction == "baseline"
    assert any(
        "history" in rec.message.lower() and "corrupt" in rec.message.lower()
        for rec in caplog.records
    )
