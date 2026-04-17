from __future__ import annotations

import datetime
from pathlib import Path
from types import SimpleNamespace

from rich.console import Console

from drift.models import Finding, ModuleScore, RepoAnalysis, Severity


def _analysis() -> RepoAnalysis:
    f1 = Finding(
        signal_type="pattern_fragmentation",
        severity=Severity.HIGH,
        score=0.71,
        title="Duplicate pattern",
        description="same logic in multiple places\nsecond line",
        file_path=Path("src/app/mod.py"),
        start_line=10,
        end_line=11,
        related_files=[Path("src/app/util.py")],
        fix="Extract helper",
        metadata={
            "context_tags": ["api"],
            "deliberate_pattern_risk": "intentional strategy pattern",
        },
    )
    f2 = Finding(
        signal_type="architecture_violation",
        severity=Severity.MEDIUM,
        score=0.45,
        title="Layer break",
        description="router imports db",
        file_path=Path("src/api/routes.py"),
        start_line=3,
        related_files=[],
        fix="Move into service layer",
    )

    module = ModuleScore(
        path=Path("src/app"),
        drift_score=0.62,
        signal_scores={"pattern_fragmentation": 0.71, "architecture_violation": 0.45},
        findings=[f1, f2],
        file_count=3,
        function_count=8,
        ai_ratio=0.2,
    )

    trend = SimpleNamespace(
        direction="improving", delta=-0.12, recent_scores=[0.7, 0.62], history_depth=2
    )

    return RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=0.62,
        module_scores=[module],
        findings=[f1, f2],
        total_files=10,
        total_functions=30,
        ai_attributed_ratio=0.2,
        analysis_duration_seconds=1.5,
        phase_timings={
            "discover_seconds": 0.1,
            "parse_seconds": 0.5,
            "git_seconds": 0.2,
            "signals_seconds": 0.5,
            "output_seconds": 0.2,
            "total_seconds": 1.5,
        },
        trend=trend,
        analysis_status="complete",
        ai_tools_detected=["copilot"],
        suppressed_count=1,
        context_tagged_count=1,
    )


def test_rich_output_smoke_paths(monkeypatch, tmp_path: Path) -> None:
    from drift.output import rich_output as ro

    analysis = _analysis()
    console = Console(record=True, force_terminal=True, width=120)

    src = tmp_path / "src" / "app"
    src.mkdir(parents=True)
    (src / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "src" / "api").mkdir(parents=True)
    (tmp_path / "src" / "api" / "routes.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "src" / "app" / "util.py").write_text("pass\n", encoding="utf-8")

    # Make paths resolvable for snippet rendering.
    for finding in analysis.findings:
        if finding.file_path is not None:
            finding.file_path = Path(tmp_path / finding.file_path)
        finding.related_files = [Path(tmp_path / p) for p in finding.related_files]

    monkeypatch.setattr(
        "drift.finding_rendering.build_first_run_summary",
        lambda *_args, **_kwargs: {
            "headline": "h",
            "why_this_matters": "w",
            "top_findings": [
                {"signal_abbrev": "PFS", "title": "dup", "file": "src/app/mod.py", "line": 10}
            ],
            "next_step": "run drift check",
        },
    )

    ro.render_summary(analysis, console=console, language="de")
    ro.render_module_table(analysis, console=console)
    ro.render_findings(
        analysis.findings,
        max_items=10,
        console=console,
        sort_by="score",
        repo_root=tmp_path,
        show_code=True,
        explain=True,
        group_by="signal",
    )
    ro.render_module_detail(analysis.module_scores[0], console=console)
    ro.render_full_report(analysis, console=console, sort_by="impact", max_findings=5, explain=True)

    output = console.export_text()
    assert "DRIFT SCORE" in output
    assert "Phase timing" in output
    assert "Findings" in output


def test_rich_output_timeline_recommendations_and_trend() -> None:
    from drift.output import rich_output as ro

    console = Console(record=True, force_terminal=True, width=120)
    d1 = datetime.date(2026, 4, 1)
    d2 = datetime.date(2026, 4, 3)

    timeline = SimpleNamespace(
        ai_burst_periods=[
            SimpleNamespace(
                start_date=d1,
                end_date=d2,
                ai_commit_count=5,
                commit_count=7,
                files_affected={"a.py", "b.py"},
            )
        ],
        module_timelines=[
            SimpleNamespace(
                module_path="src/app",
                clean_until=datetime.date(2026, 3, 31),
                drift_started=d1,
                trigger_commits=[
                    SimpleNamespace(
                        date="2026-04-01",
                        commit_hash="abc1234",
                        author="Mick",
                        is_ai=True,
                        description="changed",
                    )
                ],
                ai_burst=True,
                current_score=0.71,
            )
        ],
    )
    ro.render_timeline(timeline, console=console)

    recs = [
        SimpleNamespace(
            impact="high",
            effort="low",
            title="Extract helper",
            description="Consolidate duplicates",
            file_path=Path("src/app/mod.py"),
        )
    ]
    ro.render_recommendations(recs, console=console)
    ro.render_recommendations([], console=console)

    ro.render_trend_chart(
        [
            {"timestamp": "2026-04-01T00:00:00Z", "drift_score": 0.6},
            {"timestamp": "2026-04-02T00:00:00Z", "drift_score": 0.5},
            {"timestamp": "2026-04-03T00:00:00Z", "drift_score": 0.4},
        ],
        console=console,
    )
    ro.render_trend_chart(
        [
            {"timestamp": "2026-04-01T00:00:00Z", "drift_score": 0.6},
        ],
        console=console,
    )

    output = console.export_text()
    assert "Drift Score Trend" in output
    assert "Recommendations" in output


def test_small_helpers_of_rich_output(tmp_path: Path) -> None:
    from drift.output import rich_output as ro

    assert ro._signal_label("unknown_sig") == "unknown_sig"
    assert ro._sparkline([]) == ""
    assert ro._sparkline([0.1, 0.2, 0.3])

    p = tmp_path / "a.py"
    p.write_text("line1\nline2\nline3\n", encoding="utf-8")
    snippet = ro._read_code_snippet(p, 2, context=1, max_lines=5)
    assert snippet is not None

    missing = ro._read_code_snippet(Path("does-not-exist.py"), 1)
    assert missing is None


def test_render_summary_surfaces_parser_failure_files() -> None:
    from drift.output import rich_output as ro

    analysis = RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=0.31,
        total_files=2,
        total_functions=1,
        ai_attributed_ratio=0.0,
        analysis_duration_seconds=0.4,
        analysis_status="degraded",
        degradation_causes=["parser_failure"],
        degradation_components=["parser"],
        degradation_events=[
            {
                "cause": "parser_failure",
                "component": "parser",
                "message": "Parser failed for src/broken.ts; file skipped in degraded mode.",
                "details": {
                    "file": "src/broken.ts",
                    "error": "Unexpected token",
                },
            }
        ],
    )
    console = Console(record=True, force_terminal=True, width=120)

    ro.render_summary(analysis, console=console)

    output = console.export_text()
    assert "Parser failures" in output
    assert "src/broken.ts" in output


def test_render_summary_surfaces_skipped_language_warning() -> None:
    from drift.output import rich_output as ro

    analysis = RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=0.12,
        total_files=1,
        total_functions=1,
        ai_attributed_ratio=0.0,
        analysis_duration_seconds=0.2,
        analysis_status="complete",
        skipped_languages={"typescript": 3},
    )
    console = Console(record=True, force_terminal=True, width=120)

    ro.render_summary(analysis, console=console)

    output = console.export_text()
    assert "Skipped 3 file(s): typescript (3)." in output
    assert "pip install drift-analyzer[typescript]" in output
