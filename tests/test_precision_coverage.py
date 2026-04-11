"""Coverage tests for precision module — PrecisionRecallReport and helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.models import Finding, Severity, SignalType
from drift.precision import PrecisionRecallReport, has_matching_finding

# Import ExpectedFinding from ground truth
from tests.fixtures.ground_truth import ExpectedFinding

# ---------------------------------------------------------------------------
# has_matching_finding
# ---------------------------------------------------------------------------


def _finding(
    signal: str = SignalType.ARCHITECTURE_VIOLATION,
    file_path: str | None = "src/foo.py",
    related: list[str] | None = None,
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=Severity.MEDIUM,
        score=0.5,
        title="t",
        description="d",
        file_path=Path(file_path) if file_path else None,
        related_files=[Path(r) for r in related] if related else [],
    )


class TestHasMatchingFinding:
    def test_exact_file_match(self):
        findings = [_finding(file_path="src/foo.py")]
        expected = ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="src/foo.py",
            should_detect=True,
            description="test",
        )
        assert has_matching_finding(findings, expected) is True

    def test_substring_match_in_file_path(self):
        findings = [_finding(file_path="project/src/foo.py")]
        expected = ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="src/foo.py",
            should_detect=True,
            description="test",
        )
        assert has_matching_finding(findings, expected) is True

    def test_no_match_wrong_signal(self):
        findings = [_finding(signal=SignalType.MUTANT_DUPLICATE)]
        expected = ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="src/foo.py",
            should_detect=True,
            description="test",
        )
        assert has_matching_finding(findings, expected) is False

    def test_file_path_none_skipped(self):
        findings = [_finding(file_path=None)]
        expected = ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="src/foo.py",
            should_detect=True,
            description="test",
        )
        assert has_matching_finding(findings, expected) is False

    def test_related_files_fallback(self):
        findings = [_finding(file_path="src/other.py", related=["src/foo.py"])]
        expected = ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="src/foo.py",
            should_detect=True,
            description="test",
        )
        assert has_matching_finding(findings, expected) is True

    def test_no_match_at_all(self):
        findings = [_finding(file_path="src/bar.py")]
        expected = ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="src/foo.py",
            should_detect=True,
            description="test",
        )
        assert has_matching_finding(findings, expected) is False

    def test_trailing_slash_stripped(self):
        findings = [_finding(file_path="src/foo/bar.py")]
        expected = ExpectedFinding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            file_path="src/foo/",
            should_detect=True,
            description="test",
        )
        assert has_matching_finding(findings, expected) is True


# ---------------------------------------------------------------------------
# PrecisionRecallReport
# ---------------------------------------------------------------------------


class TestPrecisionRecallReport:
    def test_empty_report(self):
        r = PrecisionRecallReport()
        assert r.aggregate_f1() == 0.0
        assert r.all_signals == []
        d = r.to_dict()
        assert d["total_fixtures"] == 0
        assert d["signals"] == {}

    def test_perfect_precision(self):
        r = PrecisionRecallReport()
        sig = SignalType.ARCHITECTURE_VIOLATION
        r.record_tp(sig, "fix1", "d")
        r.record_tp(sig, "fix2", "d")
        assert r.precision(sig) == 1.0

    def test_precision_with_fp(self):
        r = PrecisionRecallReport()
        sig = SignalType.MUTANT_DUPLICATE
        r.record_tp(sig, "fix1", "d")
        r.record_fp(sig, "fix2", "d")
        assert r.precision(sig) == pytest.approx(0.5)

    def test_recall_with_fn(self):
        r = PrecisionRecallReport()
        sig = SignalType.MUTANT_DUPLICATE
        r.record_tp(sig, "fix1", "d")
        r.record_fn(sig, "fix2", "d")
        assert r.recall(sig) == pytest.approx(0.5)

    def test_f1_score(self):
        r = PrecisionRecallReport()
        sig = SignalType.ARCHITECTURE_VIOLATION
        r.record_tp(sig, "a", "d")
        r.record_fp(sig, "b", "d")
        r.record_fn(sig, "c", "d")
        # P=1/2, R=1/2, F1=0.5
        assert r.f1(sig) == pytest.approx(0.5)

    def test_f1_zero_when_no_tp(self):
        r = PrecisionRecallReport()
        sig = SignalType.ARCHITECTURE_VIOLATION
        r.record_fp(sig, "a", "d")
        r.record_fn(sig, "b", "d")
        # P=0, R=0 → F1=0
        assert r.f1(sig) == 0.0

    def test_precision_recall_default_when_no_data(self):
        r = PrecisionRecallReport()
        sig = SignalType.MUTANT_DUPLICATE
        # No data → 1.0 (convention)
        assert r.precision(sig) == 1.0
        assert r.recall(sig) == 1.0

    def test_all_signals_sorted(self):
        r = PrecisionRecallReport()
        r.record_tp(SignalType.MUTANT_DUPLICATE, "a", "d")
        r.record_tn(SignalType.ARCHITECTURE_VIOLATION, "b", "d")
        sigs = r.all_signals
        assert len(sigs) == 2
        vals = [s.value for s in sigs]
        assert vals == sorted(vals)

    def test_to_dict_structure(self):
        r = PrecisionRecallReport()
        sig = SignalType.ARCHITECTURE_VIOLATION
        r.record_tp(sig, "a", "d")
        r.record_tn(sig, "b", "d")
        r.record_fp(sig, "c", "d")
        r.record_fn(sig, "e", "d")
        d = r.to_dict()
        entry = d["signals"][sig.value]
        assert entry["tp"] == 1
        assert entry["tn"] == 1
        assert entry["fp"] == 1
        assert entry["fn"] == 1
        assert d["total_fixtures"] == 4
        assert "aggregate_f1" in d

    def test_to_json(self):
        r = PrecisionRecallReport()
        r.record_tp(SignalType.MUTANT_DUPLICATE, "a", "d")
        j = r.to_json()
        import json

        data = json.loads(j)
        assert "signals" in data

    def test_summary_format(self):
        r = PrecisionRecallReport()
        sig = SignalType.ARCHITECTURE_VIOLATION
        r.record_tp(sig, "a", "d")
        s = r.summary()
        assert "Precision/Recall Report" in s
        assert "Macro-Average F1" in s
        assert sig.value in s

    def test_aggregate_f1_multi_signal(self):
        r = PrecisionRecallReport()
        r.record_tp(SignalType.ARCHITECTURE_VIOLATION, "a", "d")
        r.record_tp(SignalType.MUTANT_DUPLICATE, "b", "d")
        # Both have P=1.0 R=1.0 F1=1.0 → aggregate F1=1.0
        assert r.aggregate_f1() == pytest.approx(1.0)
