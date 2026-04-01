"""Regression tests for explicit analysis degradation state."""

from __future__ import annotations

import datetime
import os
import subprocess
from pathlib import Path

import pytest

from drift.analyzer import analyze_diff, analyze_repo
from drift.config import DriftConfig
from drift.models import RepoAnalysis


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


def test_analyze_diff_uncommitted_mode_detects_working_tree_changes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    file_path = repo / "m.py"
    file_path.write_text("def f():\n    return 1\n", encoding="utf-8")

    _git(repo, "init")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    # Unstaged change in working tree.
    file_path.write_text("def f():\n    return 2\n", encoding="utf-8")

    analysis = analyze_diff(
        repo,
        config=_config(),
        diff_mode="uncommitted",
        workers=1,
    )

    assert analysis.total_files >= 1
    assert analysis.is_degraded is False


def test_analyze_diff_staged_mode_only_uses_index_changes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    file_path = repo / "m.py"
    file_path.write_text("def f():\n    return 1\n", encoding="utf-8")

    _git(repo, "init")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    # Unstaged change should not show up in staged-only mode.
    file_path.write_text("def f():\n    return 2\n", encoding="utf-8")
    unstaged = analyze_diff(
        repo,
        config=_config(),
        diff_mode="staged",
        workers=1,
    )
    assert unstaged.total_files == 0

    _git(repo, "add", "m.py")
    staged = analyze_diff(
        repo,
        config=_config(),
        diff_mode="staged",
        workers=1,
    )
    assert staged.total_files >= 1


def test_analyze_repo_target_path_respects_path_boundaries(tmp_path: Path) -> None:
    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "src" / "app2").mkdir(parents=True)
    (tmp_path / "src" / "app" / "in_scope.py").write_text(
        "def a():\n    return 1\n", encoding="utf-8",
    )
    (tmp_path / "src" / "app2" / "out_scope.py").write_text(
        "def b():\n    return 2\n", encoding="utf-8",
    )

    analysis = analyze_repo(tmp_path, config=_config(), target_path="src/app", workers=1)

    assert analysis.total_files == 1


def test_analyze_diff_fallback_preserves_since_days(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    _git(repo, "init")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    captured: dict[str, int] = {}

    def _fake_analyze_repo(*args: object, **kwargs: object) -> RepoAnalysis:
        captured["since_days"] = int(kwargs.get("since_days", -1))
        return RepoAnalysis(
            repo_path=repo,
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.0,
        )

    monkeypatch.setattr("drift.analyzer.analyze_repo", _fake_analyze_repo)

    analyze_diff(
        repo,
        config=_config(),
        diff_ref="invalid-ref-xyz",
        since_days=7,
        workers=1,
    )

    assert captured["since_days"] == 7
