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
        metadata={},
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
        monkeypatch.setattr(
            api_module, "_finding_concise",
            lambda f: {
                "signal": api_module.signal_abbrev(f.signal_type),
                "title": f.title,
            },
        )
        monkeypatch.setattr(
            api_module, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )

        result = scan(Path("."), max_findings=15)
        signals_in_findings = {f["signal"] for f in result["findings"]}
        assert len(signals_in_findings) >= 3


# --- Task 2: fix_first dedup by (file, signal) ---

class TestFixFirstDedup:
    def test_fix_first_deduplicates_file_signal_pairs(
        self, monkeypatch,
    ):
        """fix_first contains each (file, signal) at most once."""
        import drift.api as api_module

        same_file = "src/service.py"
        findings = [
            _make_finding(PFS, 0.9, 0.9, file=same_file, line=10),
            _make_finding(PFS, 0.85, 0.85, file=same_file, line=20),
            _make_finding(PFS, 0.8, 0.8, file=same_file, line=30),
            _make_finding(AVS, 0.7, 0.7, file="src/other.py", line=5),
        ]
        analysis = SimpleNamespace(findings=findings)

        result = api_module._fix_first_concise(analysis, max_items=5)
        pairs = [(item["file"], item["signal"]) for item in result]
        assert len(pairs) == len(set(pairs))
        # The 3 PFS findings for same file should collapse to 1
        pfs_same = [
            it for it in result
            if it["file"] == same_file and it["signal"] == "PFS"
        ]
        assert len(pfs_same) == 1


# --- Task 3: diff --uncommitted scope ---

class TestDiffUncommittedScope:
    def test_uncommitted_overrides_diff_ref_to_head(self, monkeypatch):
        """uncommitted=True must set diff_ref='HEAD', not 'HEAD~1'."""
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.api import diff
        from drift.config import DriftConfig

        captured: dict[str, object] = {}
        analysis = SimpleNamespace(
            findings=[],
            drift_score=0.1,
            severity=Severity.LOW,
            trend=SimpleNamespace(previous_score=0.1),
            is_degraded=False,
            total_files=1,
        )

        def _fake_analyze_diff(*args, **kwargs):
            captured.update(kwargs)
            return analysis

        monkeypatch.setattr(
            DriftConfig, "load",
            staticmethod(lambda *a, **kw: object()),
        )
        monkeypatch.setattr(
            analyzer_module, "analyze_diff", _fake_analyze_diff,
        )
        monkeypatch.setattr(
            api_module, "_emit_api_telemetry",
            lambda **kw: None,
        )

        result = diff(Path("."), uncommitted=True)
        assert captured["diff_mode"] == "uncommitted"
        assert captured["diff_ref"] == "HEAD"
        assert result["diff_ref"] == "HEAD"

    def test_uncommitted_only_analyzes_wt_changes(
        self, monkeypatch, tmp_path,
    ):
        """uncommitted mode should scope to working-tree changes only."""
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.api import diff
        from drift.config import DriftConfig

        wt_finding = _make_finding(
            PFS, 0.8, 0.8, file="src/changed.py", line=10,
        )
        analysis = SimpleNamespace(
            findings=[wt_finding],
            drift_score=0.3,
            severity=Severity.MEDIUM,
            trend=SimpleNamespace(previous_score=0.1),
            is_degraded=False,
            total_files=1,
        )

        def _fake_analyze_diff(*args, **kwargs):
            assert kwargs["diff_mode"] == "uncommitted"
            assert kwargs["diff_ref"] == "HEAD"
            return analysis

        monkeypatch.setattr(
            DriftConfig, "load",
            staticmethod(lambda *a, **kw: object()),
        )
        monkeypatch.setattr(
            analyzer_module, "analyze_diff", _fake_analyze_diff,
        )
        monkeypatch.setattr(
            api_module, "_emit_api_telemetry",
            lambda **kw: None,
        )
        monkeypatch.setattr(
            api_module, "_finding_concise",
            lambda f: {
                "title": f.title,
                "file": f.file_path.as_posix(),
            },
        )

        result = diff(Path("."), uncommitted=True)
        assert result["new_finding_count"] == 1
        assert result["diff_mode"] == "uncommitted"


# --- Task 4: Warning for invalid target_path ---

class TestTargetPathWarning:
    def test_scan_warns_on_nonexistent_target_path(self, monkeypatch):
        """scan() emits a warning when target_path doesn't exist."""
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.config import DriftConfig

        analysis = SimpleNamespace(
            findings=[],
            drift_score=0.0,
            severity=Severity.LOW,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
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
        monkeypatch.setattr(
            api_module, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )

        result = scan(Path("."), target_path="does/not/exist")
        assert "warnings" in result
        assert any("does/not/exist" in w for w in result["warnings"])


# --- Task 5: top_signals respects --select filter ---

class TestTopSignalsFilter:
    def test_top_signals_filtered_by_select(self, monkeypatch):
        """scan(signals=["PFS"]) limits top_signals to PFS only."""
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.config import DriftConfig

        findings = [
            _make_finding(PFS, 0.9, 0.9),
            _make_finding(AVS, 0.8, 0.8),
            _make_finding(MDS, 0.7, 0.7),
        ]
        analysis = SimpleNamespace(
            findings=findings,
            drift_score=0.5,
            severity=Severity.HIGH,
            total_files=10,
            total_functions=30,
            ai_attributed_ratio=0.1,
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
        monkeypatch.setattr(
            api_module, "_finding_concise",
            lambda f: {
                "signal": api_module.signal_abbrev(f.signal_type),
                "title": f.title,
            },
        )
        monkeypatch.setattr(
            api_module, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )
        monkeypatch.setattr(
            "drift.config.apply_signal_filter",
            lambda *a, **kw: None,
        )

        result = scan(Path("."), signals=["PFS"])
        top_sigs = result["top_signals"]
        signal_ids = {s["signal"] for s in top_sigs}
        assert signal_ids == {"PFS"}
        findings_signal_ids = {f["signal"] for f in result["findings"]}
        assert findings_signal_ids == {"PFS"}


# --- Task 6: agent_instruction in API responses ---


class TestAgentInstruction:
    """Every API response includes an agent_instruction field."""

    def test_scan_response_has_agent_instruction(self, monkeypatch):
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.config import DriftConfig

        analysis = SimpleNamespace(
            findings=[],
            drift_score=0.0,
            severity=Severity.LOW,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
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
        monkeypatch.setattr(
            api_module, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )

        result = scan(Path("."))
        assert "agent_instruction" in result
        assert isinstance(result["agent_instruction"], str)
        assert "drift_diff" in result["agent_instruction"]

    def test_fix_plan_response_has_agent_instruction(self, monkeypatch):
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.config import DriftConfig

        analysis = SimpleNamespace(
            findings=[],
            drift_score=0.0,
            severity=Severity.LOW,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
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
        monkeypatch.setattr(
            "drift.output.agent_tasks.analysis_to_agent_tasks",
            lambda *a, **kw: [],
        )

        from drift.api import fix_plan

        result = fix_plan(Path("."))
        assert "agent_instruction" in result
        assert "drift_diff" in result["agent_instruction"]
        assert "Do not batch" in result["agent_instruction"]

    def test_diff_response_has_agent_instruction(self, monkeypatch):
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.config import DriftConfig

        analysis = SimpleNamespace(
            findings=[],
            drift_score=0.0,
            severity=Severity.LOW,
            total_files=10,
            total_functions=50,
            ai_attributed_ratio=0.1,
            trend=SimpleNamespace(
                direction="stable",
                previous_score=0.0,
                delta=0.0,
            ),
            is_degraded=False,
        )
        monkeypatch.setattr(
            DriftConfig, "load",
            staticmethod(lambda *a, **kw: object()),
        )
        monkeypatch.setattr(
            analyzer_module, "analyze_diff",
            lambda *a, **kw: analysis,
        )
        monkeypatch.setattr(
            api_module, "_emit_api_telemetry",
            lambda **kw: None,
        )

        from drift.api import diff

        result = diff(Path("."), uncommitted=True)
        assert "agent_instruction" in result
        assert isinstance(result["agent_instruction"], str)
