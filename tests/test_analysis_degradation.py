"""Regression tests for explicit analysis degradation state."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from drift.analyzer import analyze_diff, analyze_repo
from drift.config import DriftConfig


def _config() -> DriftConfig:
    return DriftConfig(
        include=["**/*.py"],
        exclude=["**/.git/**", "**/.drift-cache/**", "**/__pycache__/**"],
        embeddings_enabled=False,
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        },
    )


def test_signal_failure_marks_analysis_degraded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "a.py").write_text("def f(x):\n    return x\n", encoding="utf-8")

    class _FailingSignal:
        name = "failing_signal"

        def analyze(self, *_args: object, **_kwargs: object) -> list:
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "drift.analyzer.create_signals",
        lambda _ctx: [_FailingSignal()],
    )

    analysis = analyze_repo(tmp_path, config=_config(), workers=1)

    assert analysis.is_degraded is True
    assert "signal_failure" in analysis.degradation_causes
    assert "signal:failing_signal" in analysis.degradation_components


def test_corrupt_history_file_marks_analysis_degraded(tmp_path: Path) -> None:
    cfg = _config()
    (tmp_path / "pkg").mkdir(parents=True)
    (tmp_path / "pkg" / "mod.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    history_file = tmp_path / cfg.cache_dir / "history.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text("{not-json", encoding="utf-8")

    analysis = analyze_repo(tmp_path, config=cfg, workers=1)

    assert analysis.is_degraded is True
    assert "history_cache_corrupt" in analysis.degradation_causes
    assert "history_cache" in analysis.degradation_components


def test_invalid_diff_ref_marks_fallback_as_degraded(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    _git(repo, "init")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    analysis = analyze_diff(repo, config=_config(), diff_ref="invalid-ref-xyz", workers=1)

    assert analysis.total_files > 0
    assert analysis.is_degraded is True
    assert "diff_ref_invalid" in analysis.degradation_causes
    assert "git_diff" in analysis.degradation_components
