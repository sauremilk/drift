from __future__ import annotations

import datetime
import json
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from drift.models import Finding, ModuleScore, RepoAnalysis, Severity


def _analysis(repo: Path) -> RepoAnalysis:
    f = Finding(
        signal_type="pattern_fragmentation",
        severity=Severity.HIGH,
        score=0.8,
        title="dup",
        description="duplicate code",
        file_path=Path("src/a.py"),
        start_line=10,
        impact=0.6,
    )
    return RepoAnalysis(
        repo_path=repo,
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=0.4,
        findings=[f],
        module_scores=[ModuleScore(path=Path("src"), drift_score=0.4, findings=[f])],
        total_files=2,
        total_functions=5,
        ai_attributed_ratio=0.1,
        analysis_duration_seconds=1.1,
        analysis_status="complete",
    )


def test_diff_cmd_variants(tmp_path: Path) -> None:
    from drift.commands.diff_cmd import diff

    runner = CliRunner()

    import drift.commands.diff_cmd as mod

    mod.api_diff = lambda *args, **kwargs: {"ok": True, "kwargs": kwargs}
    mod.to_json = lambda result: json.dumps(result)

    out_file = tmp_path / "diff.json"
    res = runner.invoke(
        diff,
        [
            "--repo",
            str(tmp_path),
            "--uncommitted",
            "--signals",
            "PFS,BEM",
            "--exclude-signals",
            "MDS",
            "--output",
            str(out_file),
        ],
    )
    assert res.exit_code == 0
    assert out_file.exists()

    res2 = runner.invoke(diff, ["--repo", str(tmp_path), "--uncommitted", "--staged-only"])
    assert res2.exit_code != 0


def test_export_context_paths(monkeypatch, tmp_path: Path) -> None:
    from drift.commands.export_context import export_context

    runner = CliRunner()

    monkeypatch.setattr("drift.config.DriftConfig.load", lambda *_a, **_k: SimpleNamespace())
    monkeypatch.setattr("drift.analyzer.analyze_repo", lambda *_a, **_k: _analysis(tmp_path))
    monkeypatch.setattr(
        "drift.negative_context.findings_to_negative_context", lambda *args, **kwargs: ["x", "y"]
    )
    monkeypatch.setattr(
        "drift.negative_context_export.render_negative_context_markdown",
        lambda *args, **kwargs: "{}" if kwargs.get("fmt") == "raw" else "NEG",
    )
    monkeypatch.setattr("drift.copilot_context.generate_instructions", lambda *_a, **_k: "POS")

    preview = runner.invoke(export_context, ["--repo", str(tmp_path), "--include-positive"])
    assert preview.exit_code == 0
    assert "POS" in preview.output

    out = tmp_path / "ctx.md"
    write = runner.invoke(
        export_context, ["--repo", str(tmp_path), "--write", "--output", str(out)]
    )
    assert write.exit_code == 0
    assert out.read_text(encoding="utf-8") == "NEG"

    raw = runner.invoke(
        export_context, ["--repo", str(tmp_path), "--format", "raw", "--include-positive"]
    )
    assert raw.exit_code == 0


def test_feedback_commands(monkeypatch, tmp_path: Path) -> None:
    from drift.commands.feedback import feedback

    runner = CliRunner()

    cfg = SimpleNamespace(calibration=SimpleNamespace(feedback_path="feedback.jsonl"))
    monkeypatch.setattr("drift.config.DriftConfig.load", lambda *_a, **_k: cfg)

    recorded = []

    monkeypatch.setattr(
        "drift.calibration.feedback.record_feedback",
        lambda path, event: recorded.append((path, event)),
    )
    monkeypatch.setattr(
        "drift.calibration.feedback.load_feedback",
        lambda _p: [SimpleNamespace(signal_type="p", tp=1, fp=0, fn=0)],
    )
    monkeypatch.setattr(
        "drift.calibration.feedback.feedback_metrics",
        lambda events: {
            "pattern_fragmentation": SimpleNamespace(
                tp=1, fp=0, fn=0, precision=1.0, recall=1.0, f1=1.0
            )
        },
    )

    mark = runner.invoke(
        feedback,
        [
            "mark",
            "--repo",
            str(tmp_path),
            "--mark",
            "tp",
            "--signal",
            "PFS",
            "--file",
            "src/a.py",
            "--line",
            "12",
        ],
    )
    assert mark.exit_code == 0
    assert recorded

    summary = runner.invoke(feedback, ["summary", "--repo", str(tmp_path)])
    assert summary.exit_code == 0
    assert "Feedback Summary" in summary.output

    monkeypatch.setattr("drift.calibration.feedback.load_feedback", lambda _p: [])
    summary_empty = runner.invoke(feedback, ["summary", "--repo", str(tmp_path)])
    assert summary_empty.exit_code == 0
    assert "No feedback recorded" in summary_empty.output

    source = tmp_path / "events.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr("drift.calibration.feedback.load_feedback", lambda _p: [SimpleNamespace()])
    imp = runner.invoke(feedback, ["import", "--repo", str(tmp_path), str(source)])
    assert imp.exit_code == 0


def test_patterns_and_status_commands(monkeypatch, tmp_path: Path) -> None:
    from drift.commands.patterns import patterns
    from drift.commands.status import status

    runner = CliRunner()

    class _Cat:
        def __init__(self, value: str) -> None:
            self.value = value

        def __hash__(self) -> int:
            return hash(self.value)

        def __eq__(self, other: object) -> bool:
            return isinstance(other, _Cat) and other.value == self.value

    analysis = _analysis(tmp_path)
    pi = SimpleNamespace(
        file_path=Path("src/a.py"),
        function_name="fn",
        start_line=1,
        end_line=5,
        variant_id="v1",
    )
    analysis.pattern_catalog = {_Cat("logging"): [pi]}

    monkeypatch.setattr(
        "drift.config.DriftConfig.load", lambda *_a, **_k: SimpleNamespace(language="de")
    )
    monkeypatch.setattr("drift.analyzer.analyze_repo", lambda *_a, **_k: analysis)

    p_json = runner.invoke(patterns, ["--repo", str(tmp_path), "--output-format", "json"])
    assert p_json.exit_code == 0
    assert "logging" in p_json.output

    p_rich = runner.invoke(patterns, ["--repo", str(tmp_path)])
    assert p_rich.exit_code == 0

    # status command dependencies
    monkeypatch.setattr(
        "drift.finding_rendering.select_priority_findings", lambda *_a, **_k: analysis.findings
    )
    monkeypatch.setattr(
        "drift.finding_rendering.build_first_run_summary",
        lambda *_a, **_k: {"why_this_matters": "w", "next_step": "n"},
    )
    monkeypatch.setattr(
        "drift.output.guided_output.determine_status",
        lambda *_a, **_k: SimpleNamespace(value="yellow"),
    )
    monkeypatch.setattr("drift.output.guided_output.can_continue", lambda *_a, **_k: False)
    monkeypatch.setattr("drift.output.guided_output.emoji_for_status", lambda *_a, **_k: "🟡")
    monkeypatch.setattr(
        "drift.output.guided_output.headline_for_status", lambda *_a, **_k: "Achtung"
    )
    monkeypatch.setattr("drift.output.guided_output.is_calibrated", lambda *_a, **_k: False)
    monkeypatch.setattr(
        "drift.output.guided_output.plain_text_for_signal", lambda *_a, **_k: "text"
    )
    monkeypatch.setattr("drift.output.guided_output.severity_label", lambda *_a, **_k: "HIGH")
    monkeypatch.setattr(
        "drift.output.prompt_generator.generate_agent_prompt", lambda *_a, **_k: "PROMPT"
    )
    monkeypatch.setattr(
        "drift.profiles.get_profile",
        lambda *_a, **_k: SimpleNamespace(guided_thresholds=None, output_language="de"),
    )
    monkeypatch.setattr(
        "drift.finding_rendering._finding_guided",
        lambda f, rank=1: {"rank": rank, "title": f.title},
    )

    st_json = runner.invoke(status, ["--repo", str(tmp_path), "--json"])
    assert st_json.exit_code == 0
    assert "yellow" in st_json.output

    st_rich = runner.invoke(status, ["--repo", str(tmp_path), "--top", "1"])
    assert st_rich.exit_code == 0


def test_baseline_and_copilot_context(monkeypatch, tmp_path: Path) -> None:
    from drift.commands.baseline import baseline
    from drift.commands.copilot_context import copilot_context

    runner = CliRunner()

    # baseline save + diff
    monkeypatch.setattr(
        "drift.config.DriftConfig.load", lambda *_a, **_k: SimpleNamespace(embeddings_enabled=True)
    )
    monkeypatch.setattr("drift.analyzer.analyze_repo", lambda *_a, **_k: _analysis(tmp_path))
    monkeypatch.setattr(
        "drift.baseline.save_baseline",
        lambda analysis, dest: dest.write_text("{}", encoding="utf-8"),
    )

    save_out = tmp_path / "base.json"
    bsave = runner.invoke(
        baseline, ["save", "--repo", str(tmp_path), "--output", str(save_out), "--no-embeddings"]
    )
    assert bsave.exit_code == 0
    assert save_out.exists()

    monkeypatch.setattr("drift.baseline.load_baseline", lambda _p: {"x"})
    monkeypatch.setattr("drift.baseline.baseline_diff", lambda findings, fps: (findings, []))
    monkeypatch.setattr("drift.output.json_output._finding_to_dict", lambda f: {"title": f.title})

    bjson = runner.invoke(
        baseline,
        ["diff", "--repo", str(tmp_path), "--baseline-file", str(save_out), "--format", "json"],
    )
    assert bjson.exit_code == 0
    assert "new_findings" in bjson.output

    monkeypatch.setattr("drift.baseline.baseline_diff", lambda findings, fps: ([], findings))
    brich = runner.invoke(
        baseline, ["diff", "--repo", str(tmp_path), "--baseline-file", str(save_out)]
    )
    assert brich.exit_code == 0
    assert "No new findings" in brich.output

    # missing baseline file path
    missing = runner.invoke(
        baseline,
        ["diff", "--repo", str(tmp_path), "--baseline-file", str(tmp_path / "missing.json")],
    )
    assert missing.exit_code != 0

    # copilot-context command variants
    monkeypatch.setattr("drift.copilot_context.generate_constraints_payload", lambda _a: {"k": 1})
    monkeypatch.setattr("drift.copilot_context.generate_for_target", lambda t, _a: f"OUT-{t}")
    monkeypatch.setattr("drift.copilot_context.generate_instructions", lambda _a: "OUT")
    monkeypatch.setattr(
        "drift.copilot_context.target_default_path", lambda t, repo: repo / f"{t}.md"
    )
    monkeypatch.setattr(
        "drift.copilot_context.merge_into_file", lambda path, text, no_merge=False: True
    )

    cj = runner.invoke(copilot_context, ["--repo", str(tmp_path), "--json"])
    assert cj.exit_code == 0
    assert '"k": 1' in cj.output

    cjw = runner.invoke(copilot_context, ["--repo", str(tmp_path), "--json", "--write"])
    assert cjw.exit_code == 0

    call = runner.invoke(copilot_context, ["--repo", str(tmp_path), "--target", "all", "--write"])
    assert call.exit_code == 0

    cone = runner.invoke(
        copilot_context, ["--repo", str(tmp_path), "--target", "cursor", "--write"]
    )
    assert cone.exit_code == 0


def test_plugins_and_a2a_router(monkeypatch, tmp_path: Path) -> None:
    import click

    from drift.plugins import (
        COMMAND_GROUP,
        OUTPUT_GROUP,
        SIGNAL_GROUP,
        _load_entry_points,
        discover_command_plugins,
        discover_output_plugins,
        discover_signal_plugins,
        load_all_plugins,
    )
    from drift.serve.a2a_router import dispatch
    from drift.serve.models import A2AMessage, A2AMessagePart, A2AMessageSendParams

    class _EP:
        def __init__(self, name, value, obj=None, exc=False):
            self.name = name
            self.value = value
            self._obj = obj
            self._exc = exc

        def load(self):
            if self._exc:
                raise RuntimeError("boom")
            return self._obj

    class _BaseSignal:
        pass

    class _Sig(_BaseSignal):
        pass

    cmd = click.Command("x")

    # _load_entry_points fallback path
    monkeypatch.setattr(
        "drift.plugins.entry_points", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("e"))
    )
    assert _load_entry_points("x") == []

    monkeypatch.setattr(
        "drift.plugins._load_entry_points",
        lambda group: {
            SIGNAL_GROUP: [
                _EP("ok", "v", _Sig),
                _EP("bad", "v", object),
                _EP("fail", "v", exc=True),
            ],
            OUTPUT_GROUP: [_EP("fmt", "v", lambda *_a, **_k: None), _EP("fail", "v", exc=True)],
            COMMAND_GROUP: [
                _EP("cmd", "v", cmd),
                _EP("bad", "v", object),
                _EP("fail", "v", exc=True),
            ],
        }[group],
    )
    monkeypatch.setattr("drift.signals.base.BaseSignal", _BaseSignal)

    sigs = discover_signal_plugins()
    assert _Sig in sigs

    outs = discover_output_plugins()
    assert "fmt" in outs

    cmds = discover_command_plugins()
    assert cmds and cmds[0].name == "x"

    monkeypatch.setattr("drift.plugins.discover_signal_plugins", lambda: [_Sig])
    monkeypatch.setattr("drift.signals.base._SIGNAL_REGISTRY", [])
    monkeypatch.setattr("drift.signals.base.register_signal", lambda cls: None)
    load_all_plugins()

    # A2A router dispatch
    params_missing = A2AMessageSendParams(
        message=A2AMessage(parts=[A2AMessagePart(kind="text", text="hi")])
    )
    r_missing = dispatch(params_missing, "1")
    assert hasattr(r_missing, "error")

    params_unknown = A2AMessageSendParams(
        message=A2AMessage(
            metadata={"skillId": "does-not-exist"}, parts=[A2AMessagePart(kind="text", text="hi")]
        )
    )
    r_unknown = dispatch(params_unknown, "1")
    assert hasattr(r_unknown, "error")

    monkeypatch.setattr("os.path.realpath", lambda p: str(tmp_path))
    monkeypatch.setattr("os.path.normpath", lambda p: p)
    monkeypatch.setattr("os.path.isdir", lambda p: True)

    import drift.serve.a2a_router as router

    router._SKILL_DISPATCH.clear()
    router._SKILL_DISPATCH.update({"scan": lambda p: {"ok": True}})

    params_ok = A2AMessageSendParams(
        message=A2AMessage(
            metadata={"skillId": "scan"},
            parts=[A2AMessagePart(kind="data", data={"skill": "scan", "path": str(tmp_path)})],
        )
    )
    r_ok = dispatch(params_ok, "1")
    assert hasattr(r_ok, "result")

    router._SKILL_DISPATCH.clear()
    router._SKILL_DISPATCH.update(
        {"scan": lambda p: (_ for _ in ()).throw(ValueError("bad params"))}
    )
    r_val = dispatch(params_ok, "1")
    assert hasattr(r_val, "error")

    router._SKILL_DISPATCH.clear()
    router._SKILL_DISPATCH.update({"scan": lambda p: (_ for _ in ()).throw(RuntimeError("boom"))})
    r_err = dispatch(params_ok, "1")
    assert hasattr(r_err, "error")


def test_markdown_report_generation(tmp_path: Path) -> None:
    from drift.output.markdown_report import analysis_to_markdown

    analysis = _analysis(tmp_path)
    analysis.analysis_status = "degraded"
    analysis.degradation_causes = ["x"]
    analysis.trend = SimpleNamespace(delta=1.2, direction="degrading")
    analysis.preflight = SimpleNamespace(
        git_available=True,
        python_files_found=10,
        active_count=2,
        skipped_count=1,
        skipped_signals=[SimpleNamespace(signal_id="a", signal_name="A", reason="r", hint="h")],
        warnings=["w1"],
        active_signals=["pfs"],
    )
    analysis.analyzer_warnings = [SimpleNamespace(signal_type="x", message="m", skipped=True)]

    md = analysis_to_markdown(
        analysis, max_findings=1, include_preflight=True, include_interpretation=True
    )
    assert "Drift Analysis Report" in md
    assert "Preflight Diagnostics" in md
    assert "Analyzer Warnings" in md
    assert "degraded" in md

    analysis.findings = []
    md2 = analysis_to_markdown(analysis, include_preflight=False, include_interpretation=False)
    assert "No findings" in md2
