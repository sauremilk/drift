"""Tests for context-aware finding prioritization (Issue 370).

Verifies that _context_score and _composite_sort_key in finding_priority
correctly rank findings in high-churn / broad-ownership files ahead of
equal-severity findings in stable, rarely-touched files.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from drift.finding_priority import (
    _composite_sort_key,
    _context_score,
)
from drift.models import FileHistory, Finding, Severity, SignalType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    signal_type: str = SignalType.DEAD_CODE_ACCUMULATION,
    severity: Severity = Severity.MEDIUM,
    file_path: str = "src/module.py",
    impact: float = 0.5,
) -> Finding:
    return Finding(
        signal_type=signal_type,
        severity=severity,
        score=0.5,
        title="test finding",
        description="test",
        file_path=Path(file_path),
        start_line=1,
        impact=impact,
    )


def _make_history(
    path: str = "src/module.py",
    change_frequency_30d: float = 0.0,
    unique_authors: int = 0,
    last_modified: datetime.datetime | None = None,
) -> FileHistory:
    return FileHistory(
        path=Path(path),
        change_frequency_30d=change_frequency_30d,
        unique_authors=unique_authors,
        last_modified=last_modified,
    )


# ---------------------------------------------------------------------------
# _context_score tests
# ---------------------------------------------------------------------------


class TestContextScore:
    def test_no_history_returns_zero(self) -> None:
        f = _make_finding()
        assert _context_score(f, None) == 0.0

    def test_score_in_unit_interval(self) -> None:
        recent = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=10)
        fh = _make_history(change_frequency_30d=3.0, unique_authors=7, last_modified=recent)
        score = _context_score(_make_finding(), fh)
        assert 0.0 <= score <= 1.0

    def test_high_churn_raises_score(self) -> None:
        low_churn = _make_history(change_frequency_30d=0.0, unique_authors=0)
        high_churn = _make_history(change_frequency_30d=4.0, unique_authors=0)
        f = _make_finding()
        assert _context_score(f, high_churn) > _context_score(f, low_churn)

    def test_many_authors_raises_score(self) -> None:
        solo = _make_history(unique_authors=1)
        broad = _make_history(unique_authors=10)
        f = _make_finding()
        assert _context_score(f, broad) > _context_score(f, solo)

    def test_recent_file_raises_score(self) -> None:
        now = datetime.datetime.now(tz=datetime.UTC)
        old_fh = _make_history(last_modified=now - datetime.timedelta(days=400))
        new_fh = _make_history(last_modified=now - datetime.timedelta(days=5))
        f = _make_finding()
        assert _context_score(f, new_fh) > _context_score(f, old_fh)

    def test_max_inputs_saturate_at_one(self) -> None:
        recent = datetime.datetime.now(tz=datetime.UTC)
        fh = _make_history(change_frequency_30d=100.0, unique_authors=100, last_modified=recent)
        score = _context_score(_make_finding(), fh)
        assert score == pytest.approx(1.0)

    def test_naive_datetime_handled(self) -> None:
        naive_dt = datetime.datetime(2025, 1, 1)  # no tzinfo
        fh = _make_history(last_modified=naive_dt)
        f = _make_finding()
        score = _context_score(f, fh)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# _composite_sort_key tests
# ---------------------------------------------------------------------------


class TestCompositeSortKey:
    def test_high_churn_file_sorts_before_stable_equal_severity(self) -> None:
        """A MEDIUM finding in a hot file must rank before the same severity in a cold file."""
        hot_file = "src/hot.py"
        cold_file = "src/cold.py"
        recent = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=2)

        f_hot = _make_finding(file_path=hot_file, severity=Severity.MEDIUM)
        f_cold = _make_finding(file_path=cold_file, severity=Severity.MEDIUM)

        fh_hot = _make_history(
            path=hot_file, change_frequency_30d=3.0, unique_authors=5, last_modified=recent
        )
        fh_cold = _make_history(path=cold_file)

        histories = {hot_file: fh_hot, cold_file: fh_cold}

        key_hot = _composite_sort_key(f_hot, file_histories=histories)
        key_cold = _composite_sort_key(f_cold, file_histories=histories)

        assert key_hot < key_cold, (
            f"Expected hot-file finding to sort first, but keys were: {key_hot!r} vs {key_cold!r}"
        )

    def test_higher_severity_still_wins_over_context(self) -> None:
        """A HIGH severity finding with no context must rank before MEDIUM even in hot file."""
        hot_file = "src/hot.py"
        cold_file = "src/cold.py"
        recent = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=1)

        f_high = _make_finding(
            file_path=cold_file, severity=Severity.HIGH,
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
        )
        f_medium_hot = _make_finding(
            file_path=hot_file, severity=Severity.MEDIUM
        )

        histories = {
            cold_file: _make_history(path=cold_file),
            hot_file: _make_history(
                path=hot_file, change_frequency_30d=5.0, unique_authors=10, last_modified=recent
            ),
        }

        key_high = _composite_sort_key(f_high, file_histories=histories)
        key_medium = _composite_sort_key(f_medium_hot, file_histories=histories)

        assert key_high < key_medium

    def test_no_history_falls_back_to_legacy_order(self) -> None:
        """Without file_histories the sort key must equal the legacy class+severity+impact tuple."""
        f1 = _make_finding(severity=Severity.HIGH, impact=0.8)
        f2 = _make_finding(severity=Severity.MEDIUM, impact=0.8)

        k1 = _composite_sort_key(f1)
        k2 = _composite_sort_key(f2)
        assert k1 < k2, "HIGH should sort before MEDIUM when no context is available"

    def test_file_history_passed_directly(self) -> None:
        recent = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=3)
        fh = _make_history(change_frequency_30d=2.0, unique_authors=4, last_modified=recent)
        f = _make_finding()

        key_with = _composite_sort_key(f, file_history=fh)
        key_without = _composite_sort_key(f)

        # context_score is non-zero → third element differs
        assert key_with[2] < key_without[2], (
            "Providing history should produce a more-negative third element (higher priority)"
        )

    def test_sorted_list_respects_context(self) -> None:
        """Sorting a mixed list by composite key places the hot-file finding first."""
        hot = "src/hot.py"
        cold = "src/cold.py"
        recent = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=1)

        findings = [
            _make_finding(file_path=cold, severity=Severity.MEDIUM),
            _make_finding(file_path=hot, severity=Severity.MEDIUM),
        ]
        histories = {
            hot: _make_history(path=hot, change_frequency_30d=3.0, last_modified=recent),
            cold: _make_history(path=cold),
        }

        ranked = sorted(findings, key=lambda f: _composite_sort_key(f, file_histories=histories))
        assert ranked[0].file_path == Path(hot)
