"""Tests for outcome_tracker — finding lifecycle tracking."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from drift.models import Finding, FindingStatus, LogicalLocation, Severity
from drift.outcome_tracker import OutcomeTracker, compute_fingerprint

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(
    *,
    signal_type: str = "pattern_fragmentation",
    file_path: str = "src/app.py",
    start_line: int = 10,
    symbol: str | None = None,
    fqn: str | None = None,
    status: FindingStatus = FindingStatus.ACTIVE,
) -> Finding:
    logical = None
    if fqn:
        logical = LogicalLocation(
            fully_qualified_name=fqn,
            name=fqn.rsplit(".", 1)[-1],
            kind="function",
        )
    return Finding(
        signal_type=signal_type,
        severity=Severity.MEDIUM,
        score=0.7,
        title=f"Test finding in {file_path}",
        description="A test finding.",
        file_path=Path(file_path),
        start_line=start_line,
        symbol=symbol,
        status=status,
        logical_location=logical,
    )


# ---------------------------------------------------------------------------
# Fingerprint tests (F-02)
# ---------------------------------------------------------------------------

class TestFingerprint:
    def test_uses_fqn_when_available(self) -> None:
        finding = _make_finding(fqn="src.app.MyClass.method")
        fp = compute_fingerprint(finding)
        # Changing line number should NOT change fingerprint when fqn is set
        finding2 = _make_finding(fqn="src.app.MyClass.method", start_line=999)
        assert fp == compute_fingerprint(finding2)

    def test_falls_back_to_path_line(self) -> None:
        f1 = _make_finding(file_path="src/a.py", start_line=10)
        f2 = _make_finding(file_path="src/a.py", start_line=20)
        assert compute_fingerprint(f1) != compute_fingerprint(f2)

    def test_different_signal_types_different_fingerprint(self) -> None:
        f1 = _make_finding(signal_type="pattern_fragmentation", fqn="a.b")
        f2 = _make_finding(signal_type="cohesion_deficit", fqn="a.b")
        assert compute_fingerprint(f1) != compute_fingerprint(f2)

    def test_deterministic(self) -> None:
        finding = _make_finding(fqn="x.y.z")
        assert compute_fingerprint(finding) == compute_fingerprint(finding)


# ---------------------------------------------------------------------------
# OutcomeTracker tests
# ---------------------------------------------------------------------------

class TestOutcomeTracker:
    def test_issue_444_record_uses_interprocess_lock(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import drift.outcome_tracker as outcome_tracker_module

        path = tmp_path / ".drift" / "outcomes.jsonl"
        tracker = OutcomeTracker(path)
        calls: list[Path] = []

        class _DummyLock:
            def __init__(self, lock_path: Path) -> None:
                self._lock_path = lock_path

            def __enter__(self) -> None:
                calls.append(self._lock_path)

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        monkeypatch.setattr(
            outcome_tracker_module,
            "interprocess_lock",
            lambda lock_path, timeout_seconds=10.0, poll_interval_seconds=0.05: _DummyLock(lock_path),
        )

        tracker.record(_make_finding())
        assert calls == [path]

    def test_issue_444_resolve_uses_interprocess_lock(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import drift.outcome_tracker as outcome_tracker_module

        path = tmp_path / ".drift" / "outcomes.jsonl"
        old_time = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "fingerprint": "fp-lock-test",
                    "signal_type": "pattern_fragmentation",
                    "recommendation_title": "Fix",
                    "reported_at": old_time,
                    "resolved_at": None,
                    "days_to_fix": None,
                    "effort_estimate": "medium",
                    "was_suppressed": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )

        tracker = OutcomeTracker(path)
        calls: list[Path] = []

        class _DummyLock:
            def __init__(self, lock_path: Path) -> None:
                self._lock_path = lock_path

            def __enter__(self) -> None:
                calls.append(self._lock_path)

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        monkeypatch.setattr(
            outcome_tracker_module,
            "interprocess_lock",
            lambda lock_path, timeout_seconds=10.0, poll_interval_seconds=0.05: _DummyLock(lock_path),
        )

        resolved = tracker.resolve(set())
        assert len(resolved) == 1
        assert calls == [path]

    def test_record_creates_jsonl_file(self, tmp_path: Path) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        tracker = OutcomeTracker(path)
        tracker.record(_make_finding())
        assert path.exists()
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["signal_type"] == "pattern_fragmentation"
        assert data["resolved_at"] is None

    def test_record_idempotent_same_session(self, tmp_path: Path) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        tracker = OutcomeTracker(path)
        finding = _make_finding()
        tracker.record(finding)
        tracker.record(finding)  # same session → ignored (F-06)
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_resolve_marks_missing_findings(self, tmp_path: Path) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        tracker = OutcomeTracker(path)
        finding = _make_finding(fqn="a.b.c")
        tracker.record(finding)

        # Resolve with empty set → finding disappeared
        resolved = tracker.resolve(set())
        assert len(resolved) == 1
        assert resolved[0].resolved_at is not None

    def test_resolve_calculates_days_to_fix(self, tmp_path: Path) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        # Write an outcome with a known reported_at in the past
        old_time = (datetime.now(UTC) - timedelta(days=3)).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"fingerprint": "abc123", "signal_type": "pattern_fragmentation",
                        "recommendation_title": "Fix it", "reported_at": old_time,
                        "resolved_at": None, "days_to_fix": None,
                        "effort_estimate": "medium", "was_suppressed": False}) + "\n",
            encoding="utf-8",
        )

        tracker = OutcomeTracker(path)
        resolved = tracker.resolve(set())  # abc123 not present → resolved
        assert len(resolved) == 1
        assert resolved[0].days_to_fix is not None
        assert resolved[0].days_to_fix >= 2.9  # ~3 days

    def test_suppressed_findings_marked(self, tmp_path: Path) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        tracker = OutcomeTracker(path)
        finding = _make_finding(status=FindingStatus.SUPPRESSED)
        tracker.record(finding)
        outcomes = tracker.load()
        assert len(outcomes) == 1
        assert outcomes[0].was_suppressed is True

    def test_load_missing_file_no_error(self, tmp_path: Path) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        tracker = OutcomeTracker(path)
        assert tracker.load() == []

    def test_issue_443_load_warns_on_skipped_unreadable_entries(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        valid = {
            "fingerprint": "ok1",
            "signal_type": "pfs",
            "recommendation_title": "Fix",
            "reported_at": datetime.now(UTC).isoformat(),
            "resolved_at": None,
            "days_to_fix": None,
            "effort_estimate": "medium",
            "was_suppressed": False,
        }
        missing_required = {
            "signal_type": "pfs",
            "recommendation_title": "Fix",
            "reported_at": datetime.now(UTC).isoformat(),
        }
        path.write_text(
            "\n".join(
                [
                    json.dumps(valid),
                    "{not-valid-json}",
                    json.dumps(missing_required),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        tracker = OutcomeTracker(path)
        with caplog.at_level(logging.WARNING):
            loaded = tracker.load()

        assert len(loaded) == 1
        assert loaded[0].fingerprint == "ok1"
        assert (
            "OutcomeTracker: skipped 2 unreadable entries" in caplog.text
        )

    def test_issue_443_load_accepts_entries_with_unknown_fields(self, tmp_path: Path) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with_unknown = {
            "fingerprint": "fp-legacy",
            "signal_type": "pattern_fragmentation",
            "recommendation_title": "Fix",
            "reported_at": datetime.now(UTC).isoformat(),
            "resolved_at": None,
            "days_to_fix": None,
            "effort_estimate": "medium",
            "was_suppressed": False,
            "legacy_extra_field": "ignored",
        }
        path.write_text(json.dumps(with_unknown) + "\n", encoding="utf-8")

        tracker = OutcomeTracker(path)
        loaded = tracker.load()

        assert len(loaded) == 1
        assert loaded[0].fingerprint == "fp-legacy"

    def test_archive_moves_old_entries(self, tmp_path: Path) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        old_time = (datetime.now(UTC) - timedelta(days=200)).isoformat()
        recent_time = datetime.now(UTC).isoformat()

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            # Old resolved entry → should be archived
            f.write(json.dumps({
                "fingerprint": "old1", "signal_type": "pfs",
                "recommendation_title": "Fix", "reported_at": old_time,
                "resolved_at": old_time, "days_to_fix": 1.0,
                "effort_estimate": "low", "was_suppressed": False,
            }) + "\n")
            # Recent entry → should stay
            f.write(json.dumps({
                "fingerprint": "new1", "signal_type": "avs",
                "recommendation_title": "Fix", "reported_at": recent_time,
                "resolved_at": None, "days_to_fix": None,
                "effort_estimate": "medium", "was_suppressed": False,
            }) + "\n")

        tracker = OutcomeTracker(path)
        archived = tracker.archive(max_age_days=180)
        assert archived == 1

        remaining = tracker.load()
        assert len(remaining) == 1
        assert remaining[0].fingerprint == "new1"

        archive_path = path.with_suffix(".archive.jsonl")
        assert archive_path.exists()

    def test_no_pii_in_outcomes(self, tmp_path: Path) -> None:
        """Outcomes must not contain author names or emails (NF-08)."""
        path = tmp_path / ".drift" / "outcomes.jsonl"
        tracker = OutcomeTracker(path)
        tracker.record(_make_finding(fqn="src.app.Handler.process"))
        content = path.read_text(encoding="utf-8")
        # Check no PII-like fields leaked
        data = json.loads(content.strip())
        assert "author" not in data
        assert "email" not in data
        assert "@" not in content  # no email addresses

    def test_resolve_does_not_touch_already_resolved(self, tmp_path: Path) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        old_time = datetime.now(UTC).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "fingerprint": "resolved1", "signal_type": "pfs",
                "recommendation_title": "Fix", "reported_at": old_time,
                "resolved_at": old_time, "days_to_fix": 2.0,
                "effort_estimate": "low", "was_suppressed": False,
            }) + "\n",
            encoding="utf-8",
        )
        tracker = OutcomeTracker(path)
        resolved = tracker.resolve(set())
        assert len(resolved) == 0  # already resolved, not touched again

    def test_issue_445_resolve_marks_outcome_for_inactive_signal_type(
        self,
        tmp_path: Path,
    ) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        now = datetime.now(UTC).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "fingerprint": "fp-old-signal",
                    "signal_type": "removed_signal",
                    "recommendation_title": "Fix",
                    "reported_at": now,
                    "resolved_at": None,
                    "days_to_fix": None,
                    "effort_estimate": "medium",
                    "was_suppressed": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )

        tracker = OutcomeTracker(path)
        resolved = tracker.resolve(
            current_fingerprints={"fp-old-signal"},
            active_signal_types={"pattern_fragmentation"},
        )

        assert len(resolved) == 1
        assert resolved[0].fingerprint == "fp-old-signal"
        assert resolved[0].resolved_at is not None

    def test_issue_445_resolve_preserves_subsequent_append(
        self,
        tmp_path: Path,
    ) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        old_time = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "fingerprint": "fp-existing",
                    "signal_type": "pattern_fragmentation",
                    "recommendation_title": "Fix",
                    "reported_at": old_time,
                    "resolved_at": None,
                    "days_to_fix": None,
                    "effort_estimate": "medium",
                    "was_suppressed": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )

        tracker_a = OutcomeTracker(path)
        tracker_b = OutcomeTracker(path)

        resolved = tracker_a.resolve(set())
        assert len(resolved) == 1

        interleaved = tracker_b._deserialize_outcome(
            {
                "fingerprint": "fp-interleaved",
                "signal_type": "architecture_violation",
                "recommendation_title": "Fix",
                "reported_at": datetime.now(UTC).isoformat(),
                "resolved_at": None,
                "days_to_fix": None,
                "effort_estimate": "high",
                "was_suppressed": False,
            }
        )
        assert interleaved is not None
        tracker_b._append(interleaved)

        loaded_after = OutcomeTracker(path).load()
        assert {o.fingerprint for o in loaded_after} == {"fp-existing", "fp-interleaved"}

    def test_issue_435_rewrite_is_atomic_on_replace_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = '{"old": true}\n'
        path.write_text(previous, encoding="utf-8")

        def _fail_replace(self: Path, _target: Path) -> None:
            raise OSError("simulated replace failure")

        monkeypatch.setattr(Path, "replace", _fail_replace)

        tracker = OutcomeTracker(path)
        with pytest.raises(OSError, match="simulated replace failure"):
            tracker._rewrite([])

        assert path.read_text(encoding="utf-8") == previous
        remaining = sorted(p.name for p in path.parent.iterdir())
        assert remaining in ([path.name], [path.name, f"{path.name}.lock"])

    def test_issue_435_archive_recovers_after_merge_crash(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = tmp_path / ".drift" / "outcomes.jsonl"
        old_time = (datetime.now(UTC) - timedelta(days=200)).isoformat()
        recent_time = datetime.now(UTC).isoformat()

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({
                "fingerprint": "old1", "signal_type": "pfs",
                "recommendation_title": "Fix", "reported_at": old_time,
                "resolved_at": old_time, "days_to_fix": 1.0,
                "effort_estimate": "low", "was_suppressed": False,
            }) + "\n")
            f.write(json.dumps({
                "fingerprint": "new1", "signal_type": "avs",
                "recommendation_title": "Fix", "reported_at": recent_time,
                "resolved_at": None, "days_to_fix": None,
                "effort_estimate": "medium", "was_suppressed": False,
            }) + "\n")

        tracker = OutcomeTracker(path)
        original_merge = OutcomeTracker._merge_into_archive

        state = {"calls": 0}

        def _fail_once_merge(self: OutcomeTracker, outcomes) -> None:
            state["calls"] += 1
            if state["calls"] == 1:
                raise OSError("simulated merge crash")
            original_merge(self, outcomes)

        monkeypatch.setattr(OutcomeTracker, "_merge_into_archive", _fail_once_merge)

        with pytest.raises(OSError, match="simulated merge crash"):
            tracker.archive(max_age_days=180)

        remaining = tracker.load()
        assert len(remaining) == 1
        assert remaining[0].fingerprint == "new1"
        assert path.with_suffix(".archive.pending.json").exists()

        archived = tracker.archive(max_age_days=180)
        assert archived == 0

        archive_path = path.with_suffix(".archive.jsonl")

        archive_text = archive_path.read_text(encoding='utf-8')
        archive_lines = [line for line in archive_text.splitlines() if line.strip()]
        assert len(archive_lines) == 1
        assert json.loads(archive_lines[0])["fingerprint"] == "old1"
        assert not path.with_suffix(".archive.pending.json").exists()
