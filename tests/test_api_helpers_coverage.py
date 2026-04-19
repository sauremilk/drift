"""Coverage tests for api_helpers — _trend_dict, _signal_weight, _top_signals,
_derive_task_contract, validate_plan, PlanValidationResult."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from drift.api_helpers import (
    PlanValidationResult,
    _derive_task_contract,
    _signal_weight,
    _top_signals,
    _trend_dict,
    validate_plan,
)
from drift.models import (
    Finding,
    RepoAnalysis,
    Severity,
    SignalType,
    TrendContext,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(
    signal: str = SignalType.ARCHITECTURE_VIOLATION,
    file_path: str | None = "src/foo.py",
    score: float = 0.5,
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=Severity.MEDIUM,
        score=score,
        title="t",
        description="d",
        file_path=Path(file_path) if file_path else None,
    )


def _analysis(
    findings: list[Finding] | None = None,
    drift_score: float = 0.3,
    trend: TrendContext | None = None,
) -> RepoAnalysis:
    return RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=drift_score,
        findings=findings or [],
        trend=trend,
    )


# ---------------------------------------------------------------------------
# _trend_dict
# ---------------------------------------------------------------------------


class TestTrendDict:
    def test_none_when_no_trend(self):
        a = _analysis(trend=None)
        assert _trend_dict(a) is None

    def test_dict_when_trend_present(self):
        trend = TrendContext(
            previous_score=0.2,
            delta=-0.1,
            direction="improving",
            recent_scores=[0.3, 0.2],
            history_depth=2,
            transition_ratio=0.5,
        )
        a = _analysis(trend=trend)
        result = _trend_dict(a)
        assert result is not None
        assert result["direction"] == "improving"
        assert result["delta"] == -0.1
        assert result["previous_score"] == 0.2


# ---------------------------------------------------------------------------
# _signal_weight
# ---------------------------------------------------------------------------


class TestSignalWeight:
    def test_unknown_abbreviation(self):
        assert _signal_weight("UNKNOWN_SIG", None) == 1.0

    def test_no_weights_attribute(self):
        config = object()  # no .weights
        assert _signal_weight("AVS", config) == 1.0

    def test_valid_signal_from_config(self):
        @dataclass
        class FakeWeights:
            architecture_violation: float = 2.5

        @dataclass
        class FakeConfig:
            weights: FakeWeights = field(default_factory=FakeWeights)

        config = FakeConfig()
        result = _signal_weight("AVS", config)
        assert result == 2.5


# ---------------------------------------------------------------------------
# _top_signals
# ---------------------------------------------------------------------------


class TestTopSignals:
    def test_empty_findings(self):
        a = _analysis(findings=[])
        assert _top_signals(a) == []

    def test_aggregation_and_sorting(self):
        findings = [
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, score=0.8),
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, score=0.6),
            _finding(signal=SignalType.MUTANT_DUPLICATE, score=0.9),
        ]
        a = _analysis(findings=findings)
        result = _top_signals(a)
        assert len(result) == 2
        # Highest score first
        assert result[0]["signal"] == "MDS"
        assert result[0]["score"] == 0.9
        # AVS gets max score
        assert result[1]["score"] == 0.8
        assert result[1]["finding_count"] == 2

    def test_signal_filter(self):
        findings = [
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, score=0.5),
            _finding(signal=SignalType.MUTANT_DUPLICATE, score=0.5),
        ]
        a = _analysis(findings=findings)
        result = _top_signals(a, signal_filter={"AVS"})
        assert len(result) == 1
        assert result[0]["signal"] == "AVS"

    def test_exclude_report_only_default(self):
        """Report-only signals (weight=0.0) are excluded by default."""

        class _Weights:
            architecture_violation = 0.8
            cognitive_complexity = 0.0  # report-only

        cfg = SimpleNamespace(weights=_Weights())
        findings = [
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, score=0.7),
            _finding(signal=SignalType.COGNITIVE_COMPLEXITY, score=0.9),
        ]
        a = _analysis(findings=findings)
        result = _top_signals(a, config=cfg)
        signal_ids = {s["signal"] for s in result}
        assert "CXS" not in signal_ids, "report-only signal must be excluded by default"
        assert "AVS" in signal_ids

    def test_exclude_report_only_false_includes_all(self):
        """With exclude_report_only=False, report-only signals are included."""

        class _Weights:
            architecture_violation = 0.8
            cognitive_complexity = 0.0  # report-only

        cfg = SimpleNamespace(weights=_Weights())
        findings = [
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, score=0.7),
            _finding(signal=SignalType.COGNITIVE_COMPLEXITY, score=0.9),
        ]
        a = _analysis(findings=findings)
        result = _top_signals(a, config=cfg, exclude_report_only=False)
        signal_ids = {s["signal"] for s in result}
        assert "CXS" in signal_ids
        assert "AVS" in signal_ids
        # report_only flag must be set correctly
        cxs_entry = next(s for s in result if s["signal"] == "CXS")
        assert cxs_entry["report_only"] is True


# ---------------------------------------------------------------------------
# _derive_task_contract
# ---------------------------------------------------------------------------


class TestDeriveTaskContract:
    def test_with_file_and_related(self):
        task = {"file": "src/a.py", "related_files": ["src/b.py", "src/c.py"]}
        result = _derive_task_contract(task)
        assert "src/a.py" in result["allowed_files"]
        assert "src/b.py" in result["allowed_files"]
        assert result["completion_evidence"]["type"] == "nudge_safe"

    def test_no_file(self):
        task = {"related_files": ["src/x.py"]}
        result = _derive_task_contract(task)
        assert "src/x.py" in result["allowed_files"]
        assert len(result["allowed_files"]) == 1

    def test_empty_task(self):
        result = _derive_task_contract({})
        assert result["allowed_files"] == []

    def test_no_duplicate_in_allowed(self):
        task = {"file": "src/a.py", "related_files": ["src/a.py"]}
        result = _derive_task_contract(task)
        assert result["allowed_files"].count("src/a.py") == 1


# ---------------------------------------------------------------------------
# PlanValidationResult
# ---------------------------------------------------------------------------


class TestPlanValidationResult:
    def test_to_api_dict(self):
        r = PlanValidationResult(
            valid=False,
            reason="test",
            stale_files=["a.py"],
            recommendation="re_plan",
            triggered=["head_commit_changed"],
        )
        d = r.to_api_dict()
        assert d["valid"] is False
        assert d["recommendation"] == "re_plan"
        assert "a.py" in d["stale_files"]


# ---------------------------------------------------------------------------
# validate_plan
# ---------------------------------------------------------------------------


@dataclass
class _FakePlan:
    invalidated: bool = False
    invalidation_reason: str | None = None
    depended_on_repo_state: dict[str, Any] | None = None


class TestValidatePlan:
    def test_invalidated_plan(self):
        plan = _FakePlan(invalidated=True, invalidation_reason="stale")
        result = validate_plan(plan, ".")  # type: ignore[arg-type]
        assert result.valid is False
        assert result.recommendation == "re_plan"
        assert "explicit_invalidation" in result.triggered

    def test_invalidated_no_reason(self):
        plan = _FakePlan(invalidated=True)
        result = validate_plan(plan, ".")  # type: ignore[arg-type]
        assert "plan explicitly invalidated" in result.reason

    def test_legacy_plan_no_state(self):
        plan = _FakePlan(depended_on_repo_state=None)
        result = validate_plan(plan, ".")  # type: ignore[arg-type]
        assert result.valid is True
        assert result.recommendation == "continue"

    @patch("drift.task_graph._git_cmd")
    def test_unchanged_repo(self, mock_git):
        mock_git.return_value = "abc123"
        plan = _FakePlan(
            depended_on_repo_state={
                "head_commit": "abc123",
                "branch": "abc123",
            }
        )
        result = validate_plan(plan, "/repo")  # type: ignore[arg-type]
        assert result.valid is True

    @patch("drift.task_graph._git_cmd")
    def test_head_changed(self, mock_git):
        def side_effect(repo_path, *args):
            if "rev-parse" in args and "HEAD" in args and "--abbrev-ref" not in args:
                return "new_head"
            if "--abbrev-ref" in args:
                return "main"
            return ""

        mock_git.side_effect = side_effect
        plan = _FakePlan(
            depended_on_repo_state={
                "head_commit": "old_head",
                "branch": "main",
            }
        )
        result = validate_plan(plan, "/repo")  # type: ignore[arg-type]
        assert result.valid is False
        assert "head_commit_changed" in result.triggered

    @patch("drift.task_graph._git_cmd")
    def test_affected_files_modified(self, mock_git):
        def side_effect(repo_path, *args):
            if "rev-parse" in args and "--abbrev-ref" not in args:
                return "same"
            if "--abbrev-ref" in args:
                return "main"
            if "diff" in args:
                return "src/a.py\nsrc/b.py"
            return ""

        mock_git.side_effect = side_effect
        plan = _FakePlan(
            depended_on_repo_state={
                "head_commit": "same",
                "branch": "main",
                "affected_files": ["src/a.py"],
            }
        )
        result = validate_plan(plan, "/repo")  # type: ignore[arg-type]
        assert result.valid is False
        assert "affected_file_modified" in result.triggered
        assert "src/a.py" in result.stale_files
