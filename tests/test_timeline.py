"""Tests for timeline root-cause analysis."""

from __future__ import annotations

import datetime
from pathlib import Path

from drift.models import CommitInfo, FileHistory, Finding, Severity, SignalType
from drift.timeline import (
    _detect_ai_bursts,
    _find_drift_onset,
    _group_commits_by_module,
    build_timeline,
)


def _make_commit(
    hash: str = "abc123",
    author: str = "dev",
    files: list[str] | None = None,
    is_ai: bool = False,
    ai_confidence: float = 0.0,
    message: str = "some change",
    days_ago: int = 0,
) -> CommitInfo:
    ts = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=days_ago)
    return CommitInfo(
        hash=hash,
        author=author,
        email=f"{author}@test.com",
        timestamp=ts,
        message=message,
        files_changed=files or ["src/main.py"],
        is_ai_attributed=is_ai,
        ai_confidence=ai_confidence,
    )


class TestGroupCommitsByModule:
    def test_groups_by_first_directory(self):
        commits = [
            _make_commit(files=["src/a.py", "src/b.py"]),
            _make_commit(files=["tests/test_a.py"]),
        ]
        grouped = _group_commits_by_module(commits)
        assert "src" in grouped
        assert "tests" in grouped
        assert len(grouped["src"]) == 1
        assert len(grouped["tests"]) == 1

    def test_root_level_files(self):
        commits = [_make_commit(files=["setup.py"])]
        grouped = _group_commits_by_module(commits)
        assert "." in grouped


class TestDetectAiBursts:
    def test_no_ai_commits_no_bursts(self):
        commits = [_make_commit(is_ai=False) for _ in range(5)]
        assert _detect_ai_bursts(commits) == []

    def test_detects_burst(self):
        commits = [
            _make_commit(hash=f"h{i}", is_ai=True, ai_confidence=0.95, days_ago=0) for i in range(4)
        ]
        bursts = _detect_ai_bursts(commits, window_days=3, min_commits=3)
        assert len(bursts) == 1
        assert bursts[0].ai_commit_count >= 3

    def test_spread_out_commits_no_burst(self):
        commits = [
            _make_commit(hash=f"h{i}", is_ai=True, ai_confidence=0.95, days_ago=i * 5)
            for i in range(4)
        ]
        bursts = _detect_ai_bursts(commits, window_days=3, min_commits=3)
        assert len(bursts) == 0


class TestFindDriftOnset:
    def test_no_commits_returns_none(self):
        clean, started, triggers = _find_drift_onset([], {}, "src")
        assert clean is None
        assert started is None
        assert triggers == []

    def test_detects_onset_from_ai_commits(self):
        commits = [
            _make_commit(
                hash="h1", is_ai=False, days_ago=10, files=["src/a.py"], message="initial setup"
            ),
            _make_commit(
                hash="h2",
                is_ai=True,
                ai_confidence=0.95,
                days_ago=5,
                files=["src/b.py"],
                message="AI refactor",
            ),
            _make_commit(
                hash="h3",
                is_ai=True,
                ai_confidence=0.95,
                days_ago=4,
                files=["src/c.py"],
                message="AI update",
            ),
            _make_commit(
                hash="h4",
                is_ai=True,
                ai_confidence=0.95,
                days_ago=3,
                files=["src/d.py"],
                message="AI cleanup",
            ),
        ]
        file_histories = {
            "src/a.py": FileHistory(path=Path("src/a.py")),
            "src/b.py": FileHistory(path=Path("src/b.py")),
            "src/c.py": FileHistory(path=Path("src/c.py")),
            "src/d.py": FileHistory(path=Path("src/d.py")),
        }
        clean, started, triggers = _find_drift_onset(commits, file_histories, "src")
        # At least some trigger commits should be detected
        assert len(triggers) >= 2


class TestBuildTimeline:
    def test_empty_inputs(self):
        tl = build_timeline([], {}, [], {})
        assert tl.module_timelines == []
        assert tl.global_events == []

    def test_builds_module_timeline(self):
        commits = [
            _make_commit(hash="h1", is_ai=True, ai_confidence=0.95, days_ago=2, files=["src/a.py"]),
        ]
        findings = [
            Finding(
                signal_type=SignalType.TEMPORAL_VOLATILITY,
                severity=Severity.MEDIUM,
                score=0.5,
                title="test",
                description="test",
                file_path=Path("src/a.py"),
            ),
        ]
        file_histories = {"src/a.py": FileHistory(path=Path("src/a.py"))}
        tl = build_timeline(commits, file_histories, findings, {"src": 0.5})
        assert len(tl.module_timelines) == 1
        assert tl.module_timelines[0].module_path == "src"

    def test_global_events_from_high_confidence_ai(self):
        commits = [
            _make_commit(hash="h1", is_ai=True, ai_confidence=0.95, days_ago=1),
        ]
        tl = build_timeline(commits, {}, [], {})
        assert len(tl.global_events) == 1
        assert tl.global_events[0].is_ai
