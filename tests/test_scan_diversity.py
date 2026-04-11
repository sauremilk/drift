"""Tests for scan signal diversity, fix_first dedup, top_signals filter."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from drift.api import (
    _DIVERSE_MIN_TOP_IMPACT_SHARE,
    _diverse_findings,
    _format_scan_response,
    scan,
)
from drift.config import DriftConfig
from drift.models import AgentTask, Severity, SignalType

# Resolve the *module* drift.api.scan — drift.api.__init__ shadows the
# submodule name with the re-exported ``scan`` function.
_scan_mod = sys.modules["drift.api.scan"]


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

    def test_diverse_preserves_minimum_top_impact_share(self):
        """diverse strategy keeps a minimum share of top-impact hotspots."""
        findings = (
            [_make_finding(PFS, 0.95, 0.95 - i * 0.01) for i in range(15)]
            + [_make_finding(AVS, 0.8, 0.55)]
            + [_make_finding(MDS, 0.75, 0.54)]
            + [_make_finding(COD, 0.7, 0.53)]
        )
        max_findings = 10
        result = _diverse_findings(findings, max_findings)

        ranked = sorted(
            findings,
            key=lambda f: (
                -f.impact,
                f.signal_type,
                f.file_path.as_posix() if f.file_path else "",
                f.start_line or 0,
            ),
        )
        top_window_ids = {id(f) for f in ranked[:max_findings]}
        preserved = sum(1 for f in result if id(f) in top_window_ids)
        preserved_share = preserved / max_findings

        assert preserved_share >= _DIVERSE_MIN_TOP_IMPACT_SHARE

    def test_top_severity_preserves_old_behavior(self, monkeypatch):
        """top-severity returns pure score-sorted findings."""

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
        monkeypatch.setattr(_scan_mod, "_finding_concise",
            lambda f: {"title": f.title},
        )
        monkeypatch.setattr(_scan_mod, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )
        result = _format_scan_response(
            analysis, config=DriftConfig(), max_findings=5, strategy="top-severity",
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
        monkeypatch.setattr(_scan_mod, "_emit_api_telemetry",
            lambda **kw: None,
        )
        monkeypatch.setattr(_scan_mod, "_finding_concise",
            lambda f: {
                "signal": api_module.signal_abbrev(f.signal_type),
                "title": f.title,
            },
        )
        monkeypatch.setattr(_scan_mod, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )

        result = scan(Path("."), max_findings=15)
        signals_in_findings = {f["signal"] for f in result["findings"]}
        assert len(signals_in_findings) >= 3

    def test_scan_response_exposes_signal_abbrev_map(self):
        """scan output includes a stable abbreviation -> signal_type map."""
        analysis = SimpleNamespace(
            findings=[_make_finding(PFS, 0.8, 0.8)],
            drift_score=0.6,
            severity=Severity.HIGH,
            total_files=1,
            total_functions=1,
            ai_attributed_ratio=0.0,
            trend=None,
        )

        result = _format_scan_response(
            analysis,
            config=DriftConfig(),
            max_findings=10,
            strategy="top-severity",
        )

        assert result["signal_abbrev_map"]["AVS"] == "architecture_violation"
        assert result["signal_abbrev_map"]["HSC"] == "hardcoded_secret"

    def test_scan_reports_omitted_signals_when_truncated(self, monkeypatch):
        """scan response should expose signals omitted by truncation strategy."""
        import drift.api as api_module

        dia_findings = [
            _make_finding(SignalType.DOC_IMPL_DRIFT, 0.45, 0.45 - i * 0.01)
            for i in range(3)
        ]
        high_findings = [
            _make_finding(PFS, 0.95, 0.95 - i * 0.01)
            for i in range(4)
        ] + [
            _make_finding(AVS, 0.9, 0.9 - i * 0.01)
            for i in range(3)
        ]
        analysis = SimpleNamespace(
            findings=high_findings + dia_findings,
            drift_score=0.7,
            severity=Severity.HIGH,
            total_files=12,
            total_functions=60,
            ai_attributed_ratio=0.1,
            trend=None,
        )
        monkeypatch.setattr(_scan_mod, "_finding_concise",
            lambda f: {"signal": api_module.signal_abbrev(f.signal_type), "title": f.title},
        )
        monkeypatch.setattr(_scan_mod, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )

        result = _format_scan_response(
            analysis,
            config=DriftConfig(),
            max_findings=3,
            strategy="top-severity",
        )

        assert result["response_truncated"] is True
        assert "selection_diagnostics" in result
        omitted = result["selection_diagnostics"]["signals_with_omitted_findings"]
        dia_entry = next(item for item in omitted if item["signal"] == "DIA")
        assert dia_entry["included"] == 0
        assert dia_entry["omitted"] == 3
        assert dia_entry["reason"] == "deprioritized_by_strategy"

    def test_scan_reports_deprioritized_top_impact_window_for_diverse(self, monkeypatch):
        """diverse diagnostics should report when top-impact findings were deprioritized."""
        import drift.api as api_module

        findings = (
            [_make_finding(PFS, 0.95, 0.95 - i * 0.01) for i in range(6)]
            + [_make_finding(AVS, 0.8, 0.6)]
            + [_make_finding(MDS, 0.75, 0.59)]
            + [_make_finding(COD, 0.7, 0.58)]
        )
        analysis = SimpleNamespace(
            findings=findings,
            drift_score=0.62,
            severity=Severity.HIGH,
            total_files=10,
            total_functions=40,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        monkeypatch.setattr(_scan_mod, "_finding_concise",
            lambda f: {"signal": api_module.signal_abbrev(f.signal_type), "title": f.title},
        )
        monkeypatch.setattr(_scan_mod, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )

        result = _format_scan_response(
            analysis,
            config=DriftConfig(),
            max_findings=5,
            strategy="diverse",
        )

        top_window = result["selection_diagnostics"]["top_impact_window"]
        assert top_window["window_size"] == 5
        assert top_window["preserved_share"] >= _DIVERSE_MIN_TOP_IMPACT_SHARE
        assert top_window["deprioritized_count"] >= 1

    def test_scan_omission_diagnostics_absent_without_truncation(self, monkeypatch):
        """No omission diagnostics when all selected findings are returned."""
        import drift.api as api_module

        findings = [
            _make_finding(PFS, 0.8, 0.8),
            _make_finding(AVS, 0.7, 0.7),
        ]
        analysis = SimpleNamespace(
            findings=findings,
            drift_score=0.2,
            severity=Severity.MEDIUM,
            total_files=4,
            total_functions=8,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        monkeypatch.setattr(_scan_mod, "_finding_concise",
            lambda f: {"signal": api_module.signal_abbrev(f.signal_type), "title": f.title},
        )
        monkeypatch.setattr(_scan_mod, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )

        result = _format_scan_response(
            analysis,
            config=DriftConfig(),
            max_findings=10,
            strategy="top-severity",
        )

        assert result["response_truncated"] is False
        assert "selection_diagnostics" not in result


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


class TestScanCrossValidationFields:
    def test_concise_finding_contains_harmonized_signal_and_fingerprint(self):
        import drift.api as api_module

        finding = _make_finding(PFS, 0.9, 0.9, file="src/service.py", line=12)
        item = api_module._finding_concise(finding)

        assert item["signal"] == "PFS"
        assert item["signal_abbrev"] == "PFS"
        assert item["signal_id"] == "PFS"
        assert item["signal_type"] == PFS.value
        assert item["severity"] == "high"
        assert item["severity_rank"] == 4
        assert isinstance(item["fingerprint"], str)
        assert len(item["fingerprint"]) == 16

    def test_detailed_scan_response_includes_cross_validation_metadata(self):
        analysis = SimpleNamespace(
            findings=[_make_finding(PFS, 0.9, 0.9, file="src/service.py", line=12)],
            drift_score=0.6,
            severity=Severity.HIGH,
            total_files=10,
            total_functions=20,
            ai_attributed_ratio=0.0,
            trend=None,
            skipped_files=0,
            skipped_languages={},
        )

        result = _format_scan_response(
            analysis,
            config=DriftConfig(),
            detail="detailed",
            max_findings=5,
        )

        assert "cross_validation" in result
        cv = result["cross_validation"]
        assert cv["signal_fields"]["canonical_signal_type_field"] == "signal_type"
        assert cv["signal_fields"]["signal_id_field"] == "signal_id"
        assert cv["severity_scale"]["ranking"]["critical"] == 5
        assert cv["severity_scale"]["ranking"]["high"] == 4
        assert cv["numeric_score_range"]["min"] == 0.0
        assert cv["numeric_score_range"]["max"] == 1.0


class TestNonOperationalContextFiltering:
    def test_scan_excludes_fixture_from_findings_by_default(self, monkeypatch):
        import drift.analyzer as analyzer_module

        findings = [
            _make_finding(PFS, 0.95, 0.95, file="benchmarks/corpus/src/app.py", line=10),
            _make_finding(AVS, 0.7, 0.7, file="src/core/service.py", line=20),
        ]
        analysis = SimpleNamespace(
            findings=findings,
            drift_score=0.6,
            severity=Severity.HIGH,
            total_files=20,
            total_functions=100,
            ai_attributed_ratio=0.1,
            trend=None,
            skipped_files=0,
            skipped_languages={},
        )

        monkeypatch.setattr(
            DriftConfig, "load",
            staticmethod(lambda *a, **kw: DriftConfig()),
        )
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(_scan_mod, "_emit_api_telemetry", lambda **kw: None)
        monkeypatch.setattr(_scan_mod, "_finding_concise",
            lambda f: {"file": f.file_path.as_posix() if f.file_path else None},
        )

        result = scan(
            Path("."),
            response_detail="concise",
            strategy="top-severity",
            max_findings=1,
        )

        assert result["findings"][0]["file"] == "src/core/service.py"
        assert result["finding_context"]["excluded_from_prioritization"] == 1

    def test_scan_includes_fixture_in_findings_with_opt_in(self, monkeypatch):
        import drift.analyzer as analyzer_module

        findings = [
            _make_finding(PFS, 0.95, 0.95, file="benchmarks/corpus/src/app.py", line=10),
            _make_finding(AVS, 0.7, 0.7, file="src/core/service.py", line=20),
        ]
        analysis = SimpleNamespace(
            findings=findings,
            drift_score=0.6,
            severity=Severity.HIGH,
            total_files=20,
            total_functions=100,
            ai_attributed_ratio=0.1,
            trend=None,
            skipped_files=0,
            skipped_languages={},
        )

        monkeypatch.setattr(
            DriftConfig, "load",
            staticmethod(lambda *a, **kw: DriftConfig()),
        )
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(_scan_mod, "_emit_api_telemetry", lambda **kw: None)
        monkeypatch.setattr(_scan_mod, "_finding_concise",
            lambda f: {"file": f.file_path.as_posix() if f.file_path else None},
        )

        result = scan(
            Path("."),
            response_detail="concise",
            strategy="top-severity",
            include_non_operational=True,
            max_findings=1,
        )

        assert result["findings"][0]["file"] == "benchmarks/corpus/src/app.py"
        assert result["finding_context"]["excluded_from_prioritization"] == 0

    def test_scan_detailed_excludes_fixture_from_fix_first_by_default(self, monkeypatch):
        import drift.analyzer as analyzer_module

        findings = [
            _make_finding(PFS, 0.9, 0.9, file="benchmarks/corpus/src/app.py", line=10),
            _make_finding(AVS, 0.8, 0.8, file="src/core/service.py", line=20),
        ]
        analysis = SimpleNamespace(
            findings=findings,
            drift_score=0.6,
            severity=Severity.HIGH,
            total_files=20,
            total_functions=100,
            ai_attributed_ratio=0.1,
            trend=None,
            skipped_files=0,
            skipped_languages={},
        )

        monkeypatch.setattr(
            DriftConfig, "load",
            staticmethod(lambda *a, **kw: DriftConfig()),
        )
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(_scan_mod, "_emit_api_telemetry", lambda **kw: None)

        result = scan(Path("."), response_detail="detailed", max_findings=10)

        assert result["finding_context"]["excluded_from_fix_first"] >= 1
        assert all(item["file"] != "benchmarks/corpus/src/app.py" for item in result["fix_first"])

    def test_scan_detailed_includes_fixture_with_opt_in(self, monkeypatch):
        import drift.analyzer as analyzer_module

        findings = [
            _make_finding(PFS, 0.9, 0.9, file="benchmarks/corpus/src/app.py", line=10),
            _make_finding(AVS, 0.8, 0.8, file="src/core/service.py", line=20),
        ]
        analysis = SimpleNamespace(
            findings=findings,
            drift_score=0.6,
            severity=Severity.HIGH,
            total_files=20,
            total_functions=100,
            ai_attributed_ratio=0.1,
            trend=None,
            skipped_files=0,
            skipped_languages={},
        )

        monkeypatch.setattr(
            DriftConfig, "load",
            staticmethod(lambda *a, **kw: DriftConfig()),
        )
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(_scan_mod, "_emit_api_telemetry", lambda **kw: None)

        result = scan(
            Path("."),
            response_detail="detailed",
            include_non_operational=True,
            max_findings=10,
        )

        files = {item["file"] for item in result["fix_first"]}
        assert "benchmarks/corpus/src/app.py" in files

    def test_fix_plan_excludes_non_operational_by_default(self, monkeypatch):
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.api import fix_plan

        analysis = SimpleNamespace(
            findings=[],
            drift_score=0.41,
            severity=Severity.MEDIUM,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        tasks = [
            AgentTask(
                id="pfs-fixture",
                signal_type=SignalType.PATTERN_FRAGMENTATION,
                severity=Severity.HIGH,
                priority=1,
                title="Fixture duplicate",
                description="desc",
                action="action",
                file_path="benchmarks/corpus/src/a.py",
                metadata={"finding_context": "fixture"},
            ),
            AgentTask(
                id="avs-prod",
                signal_type=SignalType.ARCHITECTURE_VIOLATION,
                severity=Severity.HIGH,
                priority=2,
                title="Prod boundary",
                description="desc",
                action="action",
                file_path="src/core/b.py",
                metadata={"finding_context": "production"},
            ),
        ]

        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: DriftConfig()))
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(
            "drift.output.agent_tasks.analysis_to_agent_tasks",
            lambda *a, **kw: tasks,
        )
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)

        result = fix_plan(Path("."), max_tasks=5)
        assert result["task_count"] == 1
        assert result["tasks"][0]["id"] == "avs-prod"
        assert result["finding_context"]["excluded_from_fix_plan"] == 1

    def test_fix_plan_excludes_deferred_by_default(self, monkeypatch):
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.api import fix_plan

        deferred_finding = _make_finding(
            AVS,
            0.8,
            0.8,
            file="backend/api/routers/billing.py",
            line=12,
        )
        deferred_finding.deferred = True

        active_finding = _make_finding(
            PFS,
            0.7,
            0.7,
            file="src/core/service.py",
            line=8,
        )
        active_finding.deferred = False

        analysis = SimpleNamespace(
            findings=[deferred_finding, active_finding],
            drift_score=0.41,
            severity=Severity.MEDIUM,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        tasks = [
            AgentTask(
                id="avs-deferred",
                signal_type=SignalType.ARCHITECTURE_VIOLATION,
                severity=Severity.HIGH,
                priority=1,
                title=deferred_finding.title,
                description="desc",
                action="action",
                file_path="backend/api/routers/billing.py",
                metadata={"finding_context": "production"},
            ),
            AgentTask(
                id="pfs-active",
                signal_type=SignalType.PATTERN_FRAGMENTATION,
                severity=Severity.HIGH,
                priority=2,
                title=active_finding.title,
                description="desc",
                action="action",
                file_path="src/core/service.py",
                metadata={"finding_context": "production"},
            ),
        ]

        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: DriftConfig()))
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(
            "drift.output.agent_tasks.analysis_to_agent_tasks",
            lambda *a, **kw: tasks,
        )
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)

        result = fix_plan(Path("."), max_tasks=5)
        assert result["task_count"] == 1
        assert result["tasks"][0]["id"] == "pfs-active"

    def test_fix_plan_include_deferred_opt_in(self, monkeypatch):
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.api import fix_plan

        deferred_finding = _make_finding(
            AVS,
            0.8,
            0.8,
            file="backend/api/routers/billing.py",
            line=12,
        )
        deferred_finding.deferred = True

        active_finding = _make_finding(
            PFS,
            0.7,
            0.7,
            file="src/core/service.py",
            line=8,
        )
        active_finding.deferred = False

        analysis = SimpleNamespace(
            findings=[deferred_finding, active_finding],
            drift_score=0.41,
            severity=Severity.MEDIUM,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        tasks = [
            AgentTask(
                id="avs-deferred",
                signal_type=SignalType.ARCHITECTURE_VIOLATION,
                severity=Severity.HIGH,
                priority=1,
                title=deferred_finding.title,
                description="desc",
                action="action",
                file_path="backend/api/routers/billing.py",
                metadata={"finding_context": "production"},
            ),
            AgentTask(
                id="pfs-active",
                signal_type=SignalType.PATTERN_FRAGMENTATION,
                severity=Severity.HIGH,
                priority=2,
                title=active_finding.title,
                description="desc",
                action="action",
                file_path="src/core/service.py",
                metadata={"finding_context": "production"},
            ),
        ]

        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: DriftConfig()))
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(
            "drift.output.agent_tasks.analysis_to_agent_tasks",
            lambda *a, **kw: tasks,
        )
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)

        result = fix_plan(Path("."), include_deferred=True, max_tasks=5)
        assert result["task_count"] == 2

    def test_fix_plan_exclude_paths_filters_scope(self, monkeypatch):
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.api import fix_plan

        analysis = SimpleNamespace(
            findings=[],
            drift_score=0.41,
            severity=Severity.MEDIUM,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        tasks = [
            AgentTask(
                id="avs-billing",
                signal_type=SignalType.ARCHITECTURE_VIOLATION,
                severity=Severity.HIGH,
                priority=1,
                title="billing boundary",
                description="desc",
                action="action",
                file_path="backend/api/routers/billing.py",
                metadata={"finding_context": "production"},
            ),
            AgentTask(
                id="pfs-core",
                signal_type=SignalType.PATTERN_FRAGMENTATION,
                severity=Severity.HIGH,
                priority=2,
                title="core duplicate",
                description="desc",
                action="action",
                file_path="src/core/service.py",
                metadata={"finding_context": "production"},
            ),
        ]

        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: DriftConfig()))
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(
            "drift.output.agent_tasks.analysis_to_agent_tasks",
            lambda *a, **kw: tasks,
        )
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)

        result = fix_plan(Path("."), exclude_paths=["backend/api/routers"], max_tasks=5)
        assert result["task_count"] == 1
        assert result["tasks"][0]["id"] == "pfs-core"


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
        monkeypatch.setattr(_scan_mod, "_finding_concise",
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
        monkeypatch.setattr(_scan_mod, "_fix_first_concise",
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
        monkeypatch.setattr(_scan_mod, "_finding_concise",
            lambda f: {
                "signal": api_module.signal_abbrev(f.signal_type),
                "title": f.title,
            },
        )
        monkeypatch.setattr(_scan_mod, "_fix_first_concise",
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


class TestScanSignalFiltering:
    def test_max_per_signal_caps_returned_findings(self, monkeypatch):
        import drift.api as api_module

        findings = (
            [_make_finding(PFS, 0.95, 0.95 - i * 0.01) for i in range(8)]
            + [_make_finding(AVS, 0.85, 0.7 - i * 0.01) for i in range(6)]
            + [_make_finding(MDS, 0.75, 0.5 - i * 0.01) for i in range(4)]
        )
        analysis = SimpleNamespace(
            findings=findings,
            drift_score=0.6,
            severity=Severity.HIGH,
            total_files=20,
            total_functions=120,
            ai_attributed_ratio=0.1,
            trend=None,
        )
        monkeypatch.setattr(_scan_mod, "_finding_concise",
            lambda f: {"signal": api_module.signal_abbrev(f.signal_type), "title": f.title},
        )
        monkeypatch.setattr(_scan_mod, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )

        result = _format_scan_response(
            analysis,
            config=DriftConfig(),
            max_findings=9,
            max_per_signal=2,
            strategy="top-severity",
        )

        per_signal: dict[str, int] = {}
        for finding in result["findings"]:
            signal = finding["signal"]
            per_signal[signal] = per_signal.get(signal, 0) + 1

        assert result["selection_diagnostics"]["max_per_signal"] == 2
        assert max(per_signal.values()) <= 2

    def test_single_signal_scan_exposes_suppressed_finding_counts(self, monkeypatch):
        import drift.api as api_module

        findings = [_make_finding(AVS, 0.9, 0.9 - i * 0.01) for i in range(6)]
        analysis = SimpleNamespace(
            findings=findings,
            drift_score=0.5,
            severity=Severity.HIGH,
            total_files=10,
            total_functions=25,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        monkeypatch.setattr(_scan_mod, "_finding_concise",
            lambda f: {"signal": api_module.signal_abbrev(f.signal_type), "title": f.title},
        )
        monkeypatch.setattr(_scan_mod, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )

        result = _format_scan_response(
            analysis,
            config=DriftConfig(),
            max_findings=2,
            strategy="top-severity",
            signal_filter={"AVS"},
        )

        diagnostics = result["selection_diagnostics"]
        assert diagnostics["suppressed_findings_total"] == 4
        assert diagnostics["suppressed_findings_by_signal"] == {"AVS": 4}
        assert result["avs_suppressed_findings"] == 4

    def test_scan_forwards_exclude_signals_to_config(self, monkeypatch):
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.config import DriftConfig

        analysis = SimpleNamespace(
            findings=[_make_finding(PFS, 0.9, 0.9)],
            drift_score=0.5,
            severity=Severity.HIGH,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        captured: dict[str, object] = {}

        def _fake_apply_signal_filter(cfg, select, ignore):
            captured["select"] = select
            captured["ignore"] = ignore

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
        monkeypatch.setattr(_scan_mod, "_finding_concise",
            lambda f: {"signal": api_module.signal_abbrev(f.signal_type), "title": f.title},
        )
        monkeypatch.setattr(_scan_mod, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )
        monkeypatch.setattr("drift.config.apply_signal_filter", _fake_apply_signal_filter)

        scan(Path("."), signals=["PFS"], exclude_signals=["MDS"])

        assert captured["select"] == "PFS"
        assert captured["ignore"] == "MDS"


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
        monkeypatch.setattr(_scan_mod, "_fix_first_concise",
            lambda analysis, max_items=5: [],
        )

        result = scan(Path("."), response_detail="detailed")
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

    def test_diff_agent_hint_new_findings_within_threshold(self, monkeypatch):
        """WP-1: When accept_change=true but new findings exist (low sev,
        no delta), agent_instruction warns about new findings."""
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.config import DriftConfig

        # Low-severity finding that won't trigger blocking_reasons
        fake_finding = SimpleNamespace(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.LOW,
            score=0.3,
            impact=0.1,
            title="PFS finding",
            description="desc",
            fix="fix",
            file_path=Path("src/a.py"),
            start_line=1,
            end_line=5,
            symbol="func",
            related_files=[],
            rule_id="R1",
            score_contribution=0.01,
            metadata={},
        )
        analysis = SimpleNamespace(
            findings=[fake_finding],
            drift_score=0.0,  # same as previous → delta=0 → no blocking
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
        hint = result["agent_instruction"]
        assert "New findings exist" in hint
        assert "threshold" in hint.lower()

    def test_diff_agent_hint_no_findings_safe(self, monkeypatch):
        """WP-1: When accept_change=true AND no new findings, hint says safe."""
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
        hint = result["agent_instruction"]
        assert "No drift change detected" in hint
        assert "Safe to proceed" in hint


class TestFixPlanFindingIdDiagnostics:
    def test_fix_plan_task_includes_automation_fitness_alias(self, monkeypatch):
        """Fix-plan task schema exposes both automation_fit and automation_fitness."""
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.api import fix_plan
        from drift.config import DriftConfig

        analysis = SimpleNamespace(
            findings=[],
            drift_score=0.41,
            severity=Severity.MEDIUM,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        tasks = [
            AgentTask(
                id="eds-1111111111",
                signal_type=SignalType.EXPLAINABILITY_DEFICIT,
                severity=Severity.HIGH,
                priority=1,
                title="Improve explainability",
                description="desc",
                action="action",
                automation_fit="high",
            ),
        ]

        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: object()))
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(
            "drift.output.agent_tasks.analysis_to_agent_tasks",
            lambda *a, **kw: tasks,
        )
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)

        result = fix_plan(Path("."), max_tasks=5)

        assert result["task_count"] == 1
        task = result["tasks"][0]
        assert task["automation_fit"] == "high"
        assert task["automation_fitness"] == "high"

    def test_fix_plan_finding_id_accepts_rule_id(self, monkeypatch):
        """finding_id may use rule_id/signal style from scan output."""
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.api import fix_plan
        from drift.config import DriftConfig

        analysis = SimpleNamespace(
            findings=[],
            drift_score=0.41,
            severity=Severity.MEDIUM,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        tasks = [
            AgentTask(
                id="eds-1111111111",
                signal_type=SignalType.EXPLAINABILITY_DEFICIT,
                severity=Severity.HIGH,
                priority=1,
                title="Improve explainability",
                description="desc",
                action="action",
            ),
        ]

        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: object()))
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(
            "drift.output.agent_tasks.analysis_to_agent_tasks",
            lambda *a, **kw: tasks,
        )
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)

        result = fix_plan(Path("."), finding_id="explainability_deficit", max_tasks=5)

        assert result["task_count"] == 1
        assert result["tasks"][0]["id"] == "eds-1111111111"
        assert result["finding_id_diagnostic"] == "finding_id_interpreted_as_rule_id"

    def test_fix_plan_finding_id_no_match_returns_diagnostics(self, monkeypatch):
        """Unknown finding_id should not fail silently and should include hints."""
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.api import fix_plan
        from drift.config import DriftConfig

        analysis = SimpleNamespace(
            findings=[],
            drift_score=0.41,
            severity=Severity.MEDIUM,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        tasks = [
            AgentTask(
                id="eds-1111111111",
                signal_type=SignalType.EXPLAINABILITY_DEFICIT,
                severity=Severity.HIGH,
                priority=1,
                title="Improve explainability",
                description="desc",
                action="action",
            ),
        ]

        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: object()))
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(
            "drift.output.agent_tasks.analysis_to_agent_tasks",
            lambda *a, **kw: tasks,
        )
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)

        result = fix_plan(Path("."), finding_id="not-a-real-id", max_tasks=5)

        assert result["task_count"] == 0
        assert result["finding_id_diagnostic"] == "finding_id_no_match"
        assert result["suggested_fix"] is not None
        assert "valid_task_ids_sample" in result["suggested_fix"]
        assert result["invalid_fields"][0]["field"] == "finding_id"


# ---------------------------------------------------------------------------
# Next-Step Contracts (ADR-024)
# ---------------------------------------------------------------------------


def _assert_contract_shape(result: dict, *, allow_null_next: bool = False):
    """Validate the structural contract of next_tool_call / fallback_tool_call / done_when."""
    assert "done_when" in result, "missing done_when"
    assert isinstance(result["done_when"], str), "done_when must be str"
    assert len(result["done_when"]) > 0, "done_when must not be empty"

    assert "next_tool_call" in result, "missing next_tool_call"
    ntc = result["next_tool_call"]
    if allow_null_next:
        if ntc is not None:
            assert isinstance(ntc, dict)
            assert isinstance(ntc.get("tool"), str)
            assert isinstance(ntc.get("params"), dict)
    else:
        assert isinstance(ntc, dict), "next_tool_call must be dict"
        assert isinstance(ntc["tool"], str), "next_tool_call.tool must be str"
        assert isinstance(ntc["params"], dict), "next_tool_call.params must be dict"

    assert "fallback_tool_call" in result, "missing fallback_tool_call"
    ftc = result["fallback_tool_call"]
    if ftc is not None:
        assert isinstance(ftc, dict)
        assert isinstance(ftc.get("tool"), str)
        assert isinstance(ftc.get("params"), dict)


class TestNextStepContract:
    """ADR-024: machine-readable next-step contracts in API responses."""

    # -- scan ---------------------------------------------------------------

    def test_scan_detailed_has_contract(self, monkeypatch):
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.config import DriftConfig

        analysis = SimpleNamespace(
            findings=[
                _make_finding(SignalType.PATTERN_FRAGMENTATION, 0.8, 0.5),
            ],
            drift_score=0.4,
            severity=Severity.MEDIUM,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: object()))
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)
        monkeypatch.setattr(_scan_mod, "_fix_first_concise", lambda analysis, max_items=5: [])

        result = scan(Path("."), response_detail="detailed")

        _assert_contract_shape(result)
        assert result["next_tool_call"]["tool"] == "drift_fix_plan"

    def test_scan_concise_no_contract(self, monkeypatch):
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
        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: object()))
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)

        result = scan(Path("."), response_detail="concise")

        assert "next_tool_call" not in result

    def test_scan_zero_findings_null_next(self, monkeypatch):
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
        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: object()))
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)
        monkeypatch.setattr(_scan_mod, "_fix_first_concise", lambda analysis, max_items=5: [])

        result = scan(Path("."), response_detail="detailed")

        _assert_contract_shape(result, allow_null_next=True)
        assert result["next_tool_call"] is None

    # -- fix_plan -----------------------------------------------------------

    def test_fix_plan_has_contract(self, monkeypatch):
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.api import fix_plan
        from drift.config import DriftConfig

        analysis = SimpleNamespace(
            findings=[],
            drift_score=0.3,
            severity=Severity.MEDIUM,
            total_files=5,
            total_functions=10,
            ai_attributed_ratio=0.0,
            trend=None,
        )
        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: object()))
        monkeypatch.setattr(analyzer_module, "analyze_repo", lambda *a, **kw: analysis)
        monkeypatch.setattr(
            "drift.output.agent_tasks.analysis_to_agent_tasks",
            lambda *a, **kw: [],
        )
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)

        result = fix_plan(Path("."))

        _assert_contract_shape(result)
        assert "drift_nudge" in (result["next_tool_call"]["tool"])
        assert result["done_when"] == "drift_diff.accept_change == true"

    # -- diff ---------------------------------------------------------------

    def test_diff_has_contract(self, monkeypatch):
        import drift.analyzer as analyzer_module
        import drift.api as api_module
        from drift.api import diff
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
        monkeypatch.setattr(DriftConfig, "load", staticmethod(lambda *a, **kw: object()))
        monkeypatch.setattr(analyzer_module, "analyze_diff", lambda *a, **kw: analysis)
        monkeypatch.setattr(api_module, "_emit_api_telemetry", lambda **kw: None)

        result = diff(Path("."), uncommitted=True)

        _assert_contract_shape(result, allow_null_next=True)
        assert "accept_change" in result["done_when"]

    # -- contract shape validation ------------------------------------------

    def test_contract_shape_builder(self):
        from drift.api_helpers import DONE_ACCEPT_CHANGE, _next_step_contract

        c = _next_step_contract(
            next_tool="drift_fix_plan",
            next_params={"max_tasks": 5},
            done_when=DONE_ACCEPT_CHANGE,
            fallback_tool="drift_explain",
            fallback_params={"signal": "PFS"},
        )
        assert c["next_tool_call"] == {"tool": "drift_fix_plan", "params": {"max_tasks": 5}}
        assert c["fallback_tool_call"] == {"tool": "drift_explain", "params": {"signal": "PFS"}}
        assert c["done_when"] == DONE_ACCEPT_CHANGE

    def test_contract_null_next(self):
        from drift.api_helpers import DONE_NO_FINDINGS, _next_step_contract

        c = _next_step_contract(next_tool=None, done_when=DONE_NO_FINDINGS)
        assert c["next_tool_call"] is None
        assert c["fallback_tool_call"] is None
        assert c["done_when"] == DONE_NO_FINDINGS

    def test_error_response_recovery_tool_call(self):
        from drift.api_helpers import _error_response, _tool_call

        recovery = _tool_call("drift_validate", {"path": "."})
        resp = _error_response(
            "DRIFT-5001",
            "Something went wrong",
            recoverable=True,
            recovery_tool_call=recovery,
        )
        assert resp["recovery_tool_call"]["tool"] == "drift_validate"
        assert resp["recovery_tool_call"]["params"] == {"path": "."}

    def test_error_response_no_recovery_by_default(self):
        from drift.api_helpers import _error_response

        resp = _error_response("DRIFT-5001", "oops", recoverable=True)
        assert "recovery_tool_call" not in resp
