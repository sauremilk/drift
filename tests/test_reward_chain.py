"""Tests for reward_chain — deterministic recommendation quality scoring."""

from __future__ import annotations

import json
from pathlib import Path

from drift.models import Finding, LogicalLocation, Severity
from drift.outcome_tracker import Outcome
from drift.recommendations import Recommendation
from drift.reward_chain import RewardScore, compute_reward

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(
    *,
    file_path: str = "src/app.py",
    symbol: str | None = "process",
    fqn: str | None = None,
) -> Finding:
    logical = None
    if fqn:
        logical = LogicalLocation(
            fully_qualified_name=fqn,
            name=fqn.rsplit(".", 1)[-1],
            kind="function",
        )
    return Finding(
        signal_type="pattern_fragmentation",
        severity=Severity.MEDIUM,
        score=0.7,
        title="Test finding",
        description="A test finding.",
        file_path=Path(file_path),
        start_line=10,
        symbol=symbol,
        logical_location=logical,
    )


def _make_rec(
    *,
    title: str = "Consolidate patterns",
    description: str = "Merge fragmented patterns in src/app.py near process symbol.",
    effort: str = "medium",
) -> Recommendation:
    return Recommendation(
        title=title,
        description=description,
        effort=effort,
        impact="medium",
        file_path=Path("src/app.py"),
        related_findings=["pfs-001"],
    )


def _make_outcome(
    *,
    days_to_fix: float | None = 2.0,
    resolved_at: str | None = "2024-01-05T00:00:00+00:00",
    effort_estimate: str = "medium",
    was_suppressed: bool = False,
) -> Outcome:
    return Outcome(
        fingerprint="abc123",
        signal_type="pattern_fragmentation",
        recommendation_title="Consolidate patterns",
        reported_at="2024-01-01T00:00:00+00:00",
        resolved_at=resolved_at,
        days_to_fix=days_to_fix,
        effort_estimate=effort_estimate,
        was_suppressed=was_suppressed,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestComputeReward:
    def test_no_outcome_low_confidence(self) -> None:
        """Without outcome data, confidence must be < 0.5 (F-09)."""
        finding = _make_finding()
        rec = _make_rec()
        result = compute_reward(None, rec, finding)
        assert isinstance(result, RewardScore)
        assert result.confidence < 0.5
        assert result.breakdown["fix_speed"] == 0.0
        assert result.breakdown["no_regression"] == 0.0

    def test_fast_fix_scores_high(self) -> None:
        outcome = _make_outcome(days_to_fix=0.5)
        result = compute_reward(outcome, _make_rec(), _make_finding())
        assert result.breakdown["fix_speed"] == 1.0

    def test_slow_fix_scores_low(self) -> None:
        outcome = _make_outcome(days_to_fix=14.0)
        result = compute_reward(outcome, _make_rec(), _make_finding())
        assert result.breakdown["fix_speed"] == 0.0

    def test_specificity_bonus_for_file_and_symbol(self) -> None:
        finding = _make_finding(file_path="src/handler.py", symbol="handle")
        rec = _make_rec(
            description="Refactor handle in src/handler.py to reduce fragmentation."
        )
        result = compute_reward(
            _make_outcome(), rec, finding
        )
        assert result.breakdown["specificity"] >= 0.7

    def test_specificity_penalty_for_generic_verbs(self) -> None:
        rec = _make_rec(
            description="Consider reviewing and ensuring the code is evaluated properly."
        )
        result = compute_reward(_make_outcome(), rec, _make_finding())
        assert result.breakdown["specificity"] <= 0.5

    def test_effort_accuracy_perfect_match(self) -> None:
        # 2 days → actual=medium, estimate=medium → 1.0
        outcome = _make_outcome(days_to_fix=2.0, effort_estimate="medium")
        result = compute_reward(outcome, _make_rec(), _make_finding())
        assert result.breakdown["effort_accuracy"] == 1.0

    def test_effort_accuracy_off_by_one(self) -> None:
        # 2 days → actual=medium, estimate=low → 0.5
        outcome = _make_outcome(days_to_fix=2.0, effort_estimate="low")
        result = compute_reward(outcome, _make_rec(), _make_finding())
        assert result.breakdown["effort_accuracy"] == 0.5

    def test_effort_accuracy_off_by_two(self) -> None:
        # 0.5 days → actual=low, estimate=high → 0.0
        outcome = _make_outcome(days_to_fix=0.5, effort_estimate="high")
        result = compute_reward(outcome, _make_rec(), _make_finding())
        assert result.breakdown["effort_accuracy"] == 0.0

    def test_no_regression_detected(self) -> None:
        outcome = _make_outcome(resolved_at="2024-01-05T00:00:00+00:00")
        regression = Outcome(
            fingerprint="abc123",
            signal_type="pattern_fragmentation",
            recommendation_title="Fix",
            reported_at="2024-01-15T00:00:00+00:00",  # 10d after resolve → regression
        )
        result = compute_reward(
            outcome, _make_rec(), _make_finding(),
            all_outcomes=[outcome, regression],
        )
        assert result.breakdown["no_regression"] == 0.0

    def test_no_regression_clean(self) -> None:
        outcome = _make_outcome(resolved_at="2024-01-05T00:00:00+00:00")
        result = compute_reward(
            outcome, _make_rec(), _make_finding(),
            all_outcomes=[outcome],
        )
        assert result.breakdown["no_regression"] == 1.0

    def test_total_within_bounds(self) -> None:
        outcome = _make_outcome()
        result = compute_reward(outcome, _make_rec(), _make_finding())
        assert 0.0 <= result.total <= 1.0
        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# Calibrated effort wiring (Loop 4)
# ---------------------------------------------------------------------------

class TestCalibratedEffortWiring:
    """Verify that calibrated_effort overrides outcome.effort_estimate."""

    def test_calibrated_effort_exact_match_scores_1(self) -> None:
        # days_to_fix=0.5 → actual=low(0); calibrated label "low" → exact match
        outcome = _make_outcome(days_to_fix=0.5, effort_estimate="high")
        result = compute_reward(
            outcome, _make_rec(), _make_finding(), calibrated_effort="low"
        )
        assert result.breakdown["effort_accuracy"] == 1.0

    def test_calibrated_effort_off_by_one_scores_half(self) -> None:
        # days_to_fix=0.5 → actual=low(0); calibrated label "medium"(1) → off-by-one
        outcome = _make_outcome(days_to_fix=0.5, effort_estimate="low")
        result = compute_reward(
            outcome, _make_rec(), _make_finding(), calibrated_effort="medium"
        )
        assert result.breakdown["effort_accuracy"] == 0.5

    def test_fallback_to_outcome_estimate_when_no_calibrated_effort(self) -> None:
        # days_to_fix=0.5 → actual=low(0); outcome says "low" → exact match (no calibration)
        outcome = _make_outcome(days_to_fix=0.5, effort_estimate="low")
        result = compute_reward(outcome, _make_rec(), _make_finding())
        assert result.breakdown["effort_accuracy"] == 1.0

    def test_calibrated_effort_none_falls_back_to_outcome(self) -> None:
        # Explicit None → same as not passing
        outcome = _make_outcome(days_to_fix=0.5, effort_estimate="high")
        result = compute_reward(
            outcome, _make_rec(), _make_finding(), calibrated_effort=None
        )
        # outcome says "high"(2) vs actual low(0) → diff=2 → 0.0
        assert result.breakdown["effort_accuracy"] == 0.0


# ---------------------------------------------------------------------------
# RewardLogEntry / append_reward_log tests
# ---------------------------------------------------------------------------


class TestRewardLog:
    def test_append_creates_file_and_writes_json_line(self, tmp_path):
        from drift.reward_chain import RewardLogEntry, append_reward_log

        entry = RewardLogEntry(
            ts="2024-01-01T00:00:00+00:00",
            signal_type="pattern_fragmentation",
            finding_id="abc123",
            total=0.75,
            breakdown={"fix_speed": 0.8, "specificity": 0.7},
            confidence=0.9,
            recommendation_id="rec-1",
        )
        log_path = tmp_path / ".drift" / "reward_log.jsonl"
        append_reward_log(log_path, entry)

        assert log_path.exists()
        rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 1
        assert rows[0]["signal_type"] == "pattern_fragmentation"
        assert rows[0]["total"] == 0.75
        assert rows[0]["recommendation_id"] == "rec-1"

    def test_append_accumulates_multiple_entries(self, tmp_path):
        from drift.reward_chain import RewardLogEntry, append_reward_log

        log_path = tmp_path / "reward_log.jsonl"
        for i in range(3):
            entry = RewardLogEntry(
                ts=f"2024-01-0{i + 1}T00:00:00+00:00",
                signal_type="pfs",
                finding_id=f"f{i}",
                total=float(i) * 0.1,
                breakdown={},
                confidence=0.5,
            )
            append_reward_log(log_path, entry)

        rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 3

    def test_missing_recommendation_id_written_as_null(self, tmp_path):
        from drift.reward_chain import RewardLogEntry, append_reward_log

        entry = RewardLogEntry(
            ts="2024-01-01T00:00:00+00:00",
            signal_type="eds",
            finding_id="x",
            total=0.5,
            breakdown={},
            confidence=0.6,
        )
        log_path = tmp_path / "r.jsonl"
        append_reward_log(log_path, entry)
        row = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert row["recommendation_id"] is None
