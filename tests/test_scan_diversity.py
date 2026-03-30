"""Tests for scan signal diversity, fix_first dedup, top_signals filter."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from drift.api import _diverse_findings, _format_scan_response, scan
from drift.models import Severity, SignalType


def _make_finding(
    signal_type: SignalType,
    score: float,
    impact: float,
    file: str = "src/a.py",
    line: int = 1,
):
    return SimpleNamespace(
        signal_type=signal_type,
        severity=Severity.HIGH if score >= 0.7 else Severity.MEDIUM,
        score=score,
        impact=impact,
        title=f"{signal_type.value} finding",
        description="desc",
        fix="fix it",
        file_path=Path(file),
        start_line=line,
        end_line=line + 5,
        symbol="func",
        related_files=[],
        rule_id=f"RULE-{signal_type.value[:3]}",
        score_contribution=impact * 0.1,
    )


PFS = SignalType.PATTERN_FRAGMENTATION
AVS = SignalType.ARCHITECTURE_VIOLATION
MDS = SignalType.MUTANT_DUPLICATE
COD = SignalType.COHESION_DEFICIT


# --- Task 1: Signal diversity ---

class TestDiverseFindings:
    def test_diverse_selects_multiple_signals(self):
        """diverse strategy includes findings from >= 3 signals."""
        findings = (
            [_make_finding(PFS, 0.9, 0.9 - i * 0.01) for i in range(10)]
            + [_make_finding(AVS, 0.8, 0.8)]
            + [_make_finding(MDS, 0.7, 0.7)]
            + [_make_finding(COD, 0.6, 0.6)]
        )
        result = _diverse_findings(findings, 15)
        signal_types = {f.signal_type for f in result}
        assert len(signal_types) >= 3

    def test_diverse_respects_max(self):
        findings = [
            _make_finding(PFS, 0.9, 0.9 - i * 0.01)
            for i in range(20)
        ]
        result = _diverse_findings(findings, 5)
        assert len(result) <= 5

    def test_top_severity_preserves_old_behavior(self, monkeypatch):
        """top-severity returns pure score-sorted findings."""
        import drift.api as api_module

        findings = (
            [
                _make_finding(PFS, 0.9, 0.95 - i * 0.01)
                for i in range(10)
            ]
            + [_make_finding(AVS, 0.8, 0.5)]
        )
        analysis = SimpleNamespace(
            findings=findings,
            drift_score=0.5,
            severity=Severity.HIGH,
            total_files=10,
            total_functions=50,
            ai_attributed_ratio=0.1,
            trend=None,
        )
        monkeypatch.setattr(
            api_module, "_finding_concise",
            lambda f: {"title": f.title},
        )
        monkeypatch.setattr(
            api_module, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )
        result = _format_scan_response(
            analysis, max_findings=5, strategy="top-severity",
        )
        assert result["findings_returned"] == 5

    def test_diverse_via_scan_api(self, monkeypatch):
        """scan() with diverse strategy returns diverse signals."""
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.config import DriftConfig

        findings = (
            [
                _make_finding(PFS, 0.9, 0.9 - i * 0.01)
                for i in range(10)
            ]
            + [_make_finding(AVS, 0.85, 0.85)]
            + [_make_finding(MDS, 0.75, 0.75)]
            + [_make_finding(COD, 0.65, 0.65)]
        )
        analysis = SimpleNamespace(
            findings=findings,
            drift_score=0.6,
            severity=Severity.HIGH,
            total_files=20,
            total_functions=100,
            ai_attributed_ratio=0.15,
            trend=None,
        )
        monkeypatch.setattr(
            DriftConfig, "load",
            staticmethod(lambda *a, **kw: object()),
        )
        monkeypatch.setattr(
            analyzer_module, "analyze_repo",
            lambda *a, **kw: analysis,
        )
        monkeypatch.setattr(
            api_module, "_emit_api_telemetry",
            lambda **kw: None,
        )

        result = scan(Path("."), max_findings=15)
        signals_in_findings = {f["signal"] for f in result["findings"]}
        assert len(signals_in_findings) >= 3
