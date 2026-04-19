from __future__ import annotations

import datetime
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from drift.models import Finding, ParseResult, RepoAnalysis, Severity, SignalType


def _mk_finding(signal: str = "pattern_fragmentation") -> Finding:
    return Finding(
        signal_type=signal,
        severity=Severity.HIGH,
        score=0.8,
        title="t",
        description="d",
        file_path=Path("src/a.py"),
        start_line=12,
        end_line=13,
        impact=0.7,
        fix="fix",
    )


def test_ts_architecture_signal_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import drift.signals.ts_architecture as mod

    assert mod._has_ts_files([ParseResult(file_path=Path("a.py"), language="python")]) is False
    assert mod._has_ts_files([ParseResult(file_path=Path("a.ts"), language="typescript")]) is True
    assert mod._repo_path_from_pr([]) is None

    signal = mod.TypeScriptArchitectureSignal(repo_path=tmp_path)

    # No TS files -> no findings
    out_empty = signal.analyze(
        [ParseResult(file_path=Path("a.py"), language="python")], {}, SimpleNamespace()
    )
    assert out_empty == []

    # No repo path -> no findings
    signal_no_repo = mod.TypeScriptArchitectureSignal(repo_path=None)
    out_no_repo = signal_no_repo.analyze(
        [ParseResult(file_path=Path("a.ts"), language="typescript")], {}, SimpleNamespace()
    )
    assert out_no_repo == []

    # Success paths for all rule runners via monkeypatched modules
    monkeypatch.setattr(
        "drift.rules.tsjs.circular_module_detection.run_circular_module_detection",
        lambda _repo: [{"cycle_nodes": ["src/a.ts", "src/b.ts"], "cycle_length": 2}],
    )

    cfg_dir = tmp_path / ".drift"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "cross_package_import_ban.json").write_text("{}", encoding="utf-8")
    (cfg_dir / "layer_leak_detection.json").write_text("{}", encoding="utf-8")
    (cfg_dir / "ui_to_infra_import_ban.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "drift.rules.tsjs.cross_package_import_ban.run_cross_package_import_ban",
        lambda _repo, _cfg: [
            {
                "source_file": "src/x.ts",
                "target_file": "src/y.ts",
                "source_package": "a",
                "target_package": "b",
            }
        ],
    )
    monkeypatch.setattr(
        "drift.rules.tsjs.layer_leak_detection.run_layer_leak_detection",
        lambda _repo, _cfg: [
            {
                "source_file": "src/ui.ts",
                "target_file": "src/dom.ts",
                "source_layer": "ui",
                "target_layer": "domain",
            }
        ],
    )
    monkeypatch.setattr(
        "drift.rules.tsjs.ui_to_infra_import_ban.run_ui_to_infra_import_ban",
        lambda _repo, _cfg: [
            {
                "source_file": "src/ui.ts",
                "target_file": "src/infra.ts",
                "source_layer": "ui",
                "target_layer": "infra",
            }
        ],
    )

    out = signal.analyze(
        [ParseResult(file_path=Path("src/app.ts"), language="typescript")], {}, SimpleNamespace()
    )
    assert len(out) == 4
    assert all(f.signal_type == SignalType.TS_ARCHITECTURE for f in out)


def test_ts_architecture_rule_runner_importerror_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import drift.signals.ts_architecture as mod

    signal = mod.TypeScriptArchitectureSignal(repo_path=tmp_path)

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("drift.rules.tsjs"):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert signal._run_circular(tmp_path) == []
    assert signal._run_cross_package(tmp_path, SimpleNamespace()) == []
    assert signal._run_layer_leak(tmp_path, SimpleNamespace()) == []
    assert signal._run_ui_to_infra(tmp_path, SimpleNamespace()) == []


def test_api_explain_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    exp = importlib.import_module("drift.api.explain")

    monkeypatch.setattr(exp, "_emit_api_telemetry", lambda **kwargs: None)
    monkeypatch.setattr(
        "drift.commands.explain._SIGNAL_INFO",
        {
            "PFS": {
                "name": "Pattern",
                "weight": "0.2",
                "description": "d",
                "detects": "x",
                "fix_hint": "f",
            }
        },
    )
    monkeypatch.setattr(
        exp, "_repo_examples_for_signal", lambda *args, **kwargs: [{"file": "src/a.py"}]
    )

    # Abbreviation path
    r1 = exp.explain("PFS", repo_path=tmp_path)
    assert r1["type"] == "signal"
    assert r1["signal"] == "PFS"

    # resolve_signal path with known abbrev
    monkeypatch.setattr(
        exp,
        "resolve_signal",
        lambda topic: (
            SignalType.PATTERN_FRAGMENTATION if topic == "pattern_fragmentation" else None
        ),
    )
    monkeypatch.setattr(exp, "signal_abbrev", lambda sig: "PFS")
    r2 = exp.explain("pattern_fragmentation")
    assert r2["type"] == "signal"

    # resolve_signal path with unknown abbrev mapping in signal_info
    monkeypatch.setattr(exp, "signal_abbrev", lambda sig: "ZZZ")
    r3 = exp.explain("pattern_fragmentation")
    assert r3["signal"] == "ZZZ"

    # error code path
    monkeypatch.setattr(
        "drift.errors.ERROR_REGISTRY",
        {"DRIFT-1001": SimpleNamespace(code="DRIFT-1001", category="cfg")},
    )
    monkeypatch.setattr(
        "drift.errors.format_error_info_for_explain", lambda *_a, **_k: ("s", "w", "a")
    )
    r4 = exp.explain("DRIFT-1001")
    assert r4["type"] == "error_code"

    # fingerprint path
    monkeypatch.setattr(
        exp,
        "_explain_finding_by_fingerprint",
        lambda *_a, **_k: {"status": "ok", "type": "finding"},
    )
    r5 = exp.explain("abcd1234")
    assert r5["type"] == "finding"

    # unknown topic
    monkeypatch.setattr(exp, "resolve_signal", lambda _t: None)
    monkeypatch.setattr("drift.errors.ERROR_REGISTRY", {})
    r6 = exp.explain("UNKNOWN")
    assert r6["type"] == "error"


def test_api_explain_fingerprint_helper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    exp = importlib.import_module("drift.api.explain")

    f = _mk_finding("pattern_fragmentation")
    analysis = RepoAnalysis(
        repo_path=tmp_path,
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=0.3,
        findings=[f],
    )

    monkeypatch.setattr("drift.analyzer.analyze_repo", lambda *_a, **_k: analysis)
    monkeypatch.setattr(exp, "_load_config_cached", lambda *_a, **_k: SimpleNamespace())
    monkeypatch.setattr("drift.baseline.finding_fingerprint", lambda _f: "deadbeef")
    monkeypatch.setattr(exp, "signal_abbrev", lambda _s: "PFS")
    monkeypatch.setattr(
        "drift.commands.explain._SIGNAL_INFO",
        {"PFS": {"name": "Pattern", "description": "d", "detects": "x", "fix_hint": "f"}},
    )

    found = exp._explain_finding_by_fingerprint("deadbeef", tmp_path)
    assert found is not None
    assert found["type"] == "finding"

    none_case = exp._explain_finding_by_fingerprint("cafebabe", tmp_path)
    assert none_case is None


def test_api_negative_context_success_and_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    neg = importlib.import_module("drift.api.neg_context")

    monkeypatch.setattr(neg, "_emit_api_telemetry", lambda **kwargs: None)
    monkeypatch.setattr(neg, "_warn_config_issues", lambda *_a, **_k: None)
    monkeypatch.setattr(
        neg, "_load_config_cached", lambda *_a, **_k: SimpleNamespace(embeddings_enabled=True)
    )

    analysis = RepoAnalysis(
        repo_path=tmp_path,
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=0.4,
        findings=[_mk_finding()],
    )
    monkeypatch.setattr("drift.analyzer.analyze_repo", lambda *_a, **_k: analysis)
    monkeypatch.setattr(
        "drift.negative_context.findings_to_negative_context",
        lambda *args, **kwargs: [SimpleNamespace(x=1)],
    )
    monkeypatch.setattr("drift.negative_context.negative_context_to_dict", lambda nc: {"x": 1})

    ok = neg.negative_context(path=tmp_path, scope="file", target_file="src/a.py")
    assert ok["status"] == "ok"
    assert ok["items_returned"] == 1

    monkeypatch.setattr(
        "drift.analyzer.analyze_repo",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    err = neg.negative_context(path=tmp_path)
    assert err["type"] == "error"


def test_finding_rendering_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    import drift.finding_rendering as fr

    f1 = _mk_finding("pattern_fragmentation")
    f2 = _mk_finding("architecture_violation")
    f2.file_path = Path("src/b.py")
    f2.severity = Severity.LOW
    f2.impact = 0.1

    analysis = RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=0.5,
        findings=[f1, f2],
    )

    assert fr.severity_rank("high") == 4

    monkeypatch.setattr(
        "drift.output.json_output._dedupe_findings", lambda findings: (findings, {})
    )
    monkeypatch.setattr("drift.output.json_output._priority_class", lambda f: "core")
    selected = fr.select_priority_findings(analysis, max_items=1)
    assert len(selected) == 1

    monkeypatch.setattr("drift.output.json_output._next_step_for_finding", lambda f: "next")
    monkeypatch.setattr(
        "drift.output.json_output._expected_benefit_for_finding", lambda f: "benefit"
    )
    summary = fr.build_first_run_summary(analysis, max_items=2, language="de")
    assert "next_step" in summary

    monkeypatch.setattr("drift.baseline.finding_fingerprint", lambda f: "fp")
    concise = fr._finding_concise(f1)
    assert concise["finding_id"] == "fp"
    assert concise["fingerprint"] == "fp"
    assert concise["finding_id"] == concise["fingerprint"]
    assert concise["line"] == f1.start_line
    assert concise["start_line"] == f1.start_line
    assert concise["end_line"] == f1.end_line

    monkeypatch.setattr(
        "drift.recommendations.generate_recommendation",
        lambda f: SimpleNamespace(title="t", description="d", effort="low", impact="high"),
    )
    detailed = fr._finding_detailed(f1, rank=1)
    assert detailed["finding_id"] == "fp"
    assert detailed["finding_id"] == detailed["fingerprint"]
    assert detailed["remediation"]["title"] == "t"
    assert detailed["line"] == f1.start_line
    assert detailed["start_line"] == f1.start_line
    assert detailed["end_line"] == f1.end_line

    monkeypatch.setattr("drift.recommendations.generate_recommendation", lambda f: None)
    detailed_no_rec = fr._finding_detailed(f2)
    assert detailed_no_rec["remediation"] is None

    tr = fr._trend_dict(analysis)
    assert tr is None

    analysis.trend = SimpleNamespace(direction="improving", delta=-0.1, previous_score=0.6)
    tr2 = fr._trend_dict(analysis)
    assert tr2 is not None

    class _W:
        pattern_fragmentation = 0.2

    top = fr._top_signals(
        analysis, config=SimpleNamespace(weights=_W()), signal_filter={"PFS", "AVS"}
    )
    assert top

    ff = fr._fix_first_concise(analysis, max_items=2)
    assert ff

    monkeypatch.setattr("drift.output.guided_output.plain_text_for_signal", lambda s: "plain")
    monkeypatch.setattr("drift.output.guided_output.severity_label", lambda s: "High")
    monkeypatch.setattr("drift.output.prompt_generator.file_role_description", lambda f: "role")
    monkeypatch.setattr("drift.output.prompt_generator.generate_agent_prompt", lambda f: "prompt")
    guided = fr._finding_guided(f1, rank=1)
    assert guided["agent_prompt"] == "prompt"
