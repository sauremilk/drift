from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner


class _FakeWeights:
    def as_dict(self) -> dict[str, float]:
        return {
            "pattern_fragmentation": 0.2,
            "architecture_violation": 0.3,
        }


class _FakeCalibrationResult:
    def __init__(self, *, diff: dict[str, dict[str, float]] | None = None) -> None:
        self.total_events = 3
        self.signals_with_data = 2
        self.calibrated_weights = _FakeWeights()
        self.evidence = {
            "pattern_fragmentation": SimpleNamespace(
                total_observations=2,
                tp=1,
                fp=1,
                fn=0,
                precision=0.5,
            )
        }
        self.confidence_per_signal = {"pattern_fragmentation": 0.8}
        self._diff = diff or {
            "pattern_fragmentation": {
                "default": 0.1,
                "calibrated": 0.2,
                "delta": 0.1,
                "confidence": 0.8,
            }
        }

    def weight_diff(self, _defaults: object) -> dict[str, dict[str, float]]:
        return self._diff


@pytest.fixture
def fake_cfg(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        weights=SimpleNamespace(),
        calibration=SimpleNamespace(
            feedback_path="feedback.jsonl",
            history_dir="history",
            min_samples=2,
            fn_boost_factor=1.5,
            correlation_window_days=30,
            weak_fp_window_days=60,
            enabled=True,
            auto_recalibrate=False,
        ),
    )


def test_calibrate_run_json_no_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_cfg: SimpleNamespace
) -> None:
    from drift.commands.calibrate import calibrate

    runner = CliRunner()

    monkeypatch.setattr("drift.config.DriftConfig.load", lambda *_args, **_kwargs: fake_cfg)
    monkeypatch.setattr("drift.calibration.feedback.load_feedback", lambda _p: [])

    result = runner.invoke(calibrate, ["run", "--repo", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "no_data"


def test_calibrate_run_text_and_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_cfg: SimpleNamespace
) -> None:
    from drift.commands.calibrate import calibrate

    runner = CliRunner()

    written: dict[str, object] = {}

    monkeypatch.setattr("drift.config.DriftConfig.load", lambda *_args, **_kwargs: fake_cfg)
    monkeypatch.setattr("drift.calibration.feedback.load_feedback", lambda _p: [SimpleNamespace()])
    monkeypatch.setattr(
        "drift.calibration.profile_builder.build_profile",
        lambda *_args, **_kwargs: _FakeCalibrationResult(),
    )
    monkeypatch.setattr(
        "drift.commands.calibrate._write_calibrated_weights",
        lambda repo, config, result: written.update(
            {"repo": repo, "config": config, "result": result}
        ),
    )

    result = runner.invoke(calibrate, ["run", "--repo", str(tmp_path), "--format", "text"])
    assert result.exit_code == 0
    assert "Calibration Result" in result.output
    assert written["repo"] == tmp_path


def test_calibrate_explain_and_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_cfg: SimpleNamespace
) -> None:
    from drift.commands.calibrate import calibrate

    runner = CliRunner()

    monkeypatch.setattr("drift.config.DriftConfig.load", lambda *_args, **_kwargs: fake_cfg)
    monkeypatch.setattr("drift.calibration.feedback.load_feedback", lambda _p: [SimpleNamespace()])
    monkeypatch.setattr(
        "drift.calibration.profile_builder.build_profile",
        lambda *_args, **_kwargs: _FakeCalibrationResult(diff={}),
    )
    monkeypatch.setattr("drift.calibration.history.load_snapshots", lambda _p: [SimpleNamespace()])

    history_dir = tmp_path / fake_cfg.calibration.history_dir
    history_dir.mkdir(parents=True)

    explain_res = runner.invoke(calibrate, ["explain", "--repo", str(tmp_path)])
    assert explain_res.exit_code == 0
    assert "Evidence Detail" in explain_res.output

    status_res = runner.invoke(calibrate, ["status", "--repo", str(tmp_path)])
    assert status_res.exit_code == 0
    assert "Feedback events:" in status_res.output


def test_calibrate_reset_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from drift.commands.calibrate import calibrate

    runner = CliRunner()

    cfg = tmp_path / "drift.yaml"
    cfg.write_text("weights:\n  pattern_fragmentation: 0.2\n", encoding="utf-8")
    monkeypatch.setattr("drift.config.DriftConfig._find_config_file", lambda _repo: cfg)

    res = runner.invoke(calibrate, ["reset", "--repo", str(tmp_path)])
    assert res.exit_code == 0
    assert "removed" in res.output
    assert "weights" not in cfg.read_text(encoding="utf-8")

    res2 = runner.invoke(calibrate, ["reset", "--repo", str(tmp_path)])
    assert res2.exit_code == 0
    assert "No custom weights" in res2.output


def test_collect_git_correlation_success_and_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from drift.commands.calibrate import _collect_git_correlation

    snapshots = [SimpleNamespace()]
    cfg = SimpleNamespace(
        calibration=SimpleNamespace(correlation_window_days=7, weak_fp_window_days=9)
    )

    commit = SimpleNamespace(
        timestamp=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00+00:00"),
        message="m",
        files_changed=["a.py"],
    )
    monkeypatch.setattr(
        "drift.ingestion.git_history.parse_git_history", lambda *_args, **_kwargs: [commit]
    )
    monkeypatch.setattr(
        "drift.calibration.outcome_correlator.correlate_outcomes", lambda *args, **kwargs: ["ok"]
    )

    events = _collect_git_correlation(tmp_path, snapshots, cfg)
    assert events == ["ok"]

    monkeypatch.setattr(
        "drift.ingestion.git_history.parse_git_history",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    events_fail = _collect_git_correlation(tmp_path, snapshots, cfg)
    assert events_fail == []


def test_precision_command_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    from drift.commands.precision_cmd import precision
    from drift.models import SignalType

    runner = CliRunner()

    fixture = SimpleNamespace(inferred_kind=SimpleNamespace(name="POSITIVE"))
    monkeypatch.setattr("tests.fixtures.ground_truth.ALL_FIXTURES", [fixture])

    class _FakeFixtureKind:
        POSITIVE = SimpleNamespace(name="POSITIVE")

        def __iter__(self):
            return iter([self.POSITIVE])

    monkeypatch.setattr("tests.fixtures.ground_truth.FixtureKind", _FakeFixtureKind())

    report = SimpleNamespace(
        to_json=lambda: '{"ok": true}',
        all_signals=[SignalType.PATTERN_FRAGMENTATION],
        tp={SignalType.PATTERN_FRAGMENTATION: 1},
        fp={SignalType.PATTERN_FRAGMENTATION: 0},
        fn={SignalType.PATTERN_FRAGMENTATION: 0},
        tn={SignalType.PATTERN_FRAGMENTATION: 0},
        f1=lambda _sig: 1.0,
        precision=lambda _sig: 1.0,
        recall=lambda _sig: 1.0,
        aggregate_f1=lambda: 1.0,
        summary=lambda: "summary",
    )

    monkeypatch.setattr("drift.precision.ensure_signals_registered", lambda: None)
    monkeypatch.setattr("drift.precision.evaluate_fixtures", lambda *args, **kwargs: (report, []))

    ok = runner.invoke(precision, ["--signal", "pfs", "--json"])
    assert ok.exit_code == 0
    assert '"ok": true' in ok.output

    bad_signal = runner.invoke(precision, ["--signal", "unknown"])
    assert bad_signal.exit_code == 2


def test_precision_threshold_and_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    from drift.commands.precision_cmd import precision
    from drift.models import SignalType

    runner = CliRunner()

    fixture = SimpleNamespace(inferred_kind=SimpleNamespace(name="POSITIVE"))
    monkeypatch.setattr("tests.fixtures.ground_truth.ALL_FIXTURES", [fixture])

    class _FakeFixtureKind:
        POSITIVE = SimpleNamespace(name="POSITIVE")

        def __iter__(self):
            return iter([self.POSITIVE])

    monkeypatch.setattr("tests.fixtures.ground_truth.FixtureKind", _FakeFixtureKind())

    report = SimpleNamespace(
        to_json=lambda: "{}",
        all_signals=[SignalType.PATTERN_FRAGMENTATION],
        tp={SignalType.PATTERN_FRAGMENTATION: 1},
        fp={SignalType.PATTERN_FRAGMENTATION: 1},
        fn={SignalType.PATTERN_FRAGMENTATION: 1},
        tn={SignalType.PATTERN_FRAGMENTATION: 0},
        f1=lambda _sig: 0.4,
        precision=lambda _sig: 0.5,
        recall=lambda _sig: 0.5,
        aggregate_f1=lambda: 0.4,
        summary=lambda: "summary",
    )
    warnings = [SimpleNamespace(signal_type="pattern_fragmentation", message="warn")]

    monkeypatch.setattr("drift.precision.ensure_signals_registered", lambda: None)
    monkeypatch.setattr(
        "drift.precision.evaluate_fixtures", lambda *args, **kwargs: (report, warnings)
    )

    res = runner.invoke(precision, ["--threshold", "0.8"])
    assert res.exit_code == 1
    assert "warn" in res.output


def test_print_rich_table_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    from drift.commands import precision_cmd as pmod
    from drift.models import SignalType

    report = SimpleNamespace(
        all_signals=[SignalType.PATTERN_FRAGMENTATION, SignalType.ARCHITECTURE_VIOLATION],
        tp={SignalType.PATTERN_FRAGMENTATION: 1, SignalType.ARCHITECTURE_VIOLATION: 1},
        tn={SignalType.PATTERN_FRAGMENTATION: 1, SignalType.ARCHITECTURE_VIOLATION: 1},
        fp={SignalType.PATTERN_FRAGMENTATION: 0, SignalType.ARCHITECTURE_VIOLATION: 0},
        fn={SignalType.PATTERN_FRAGMENTATION: 0, SignalType.ARCHITECTURE_VIOLATION: 0},
        f1=lambda _sig: 0.9,
        precision=lambda _sig: 1.0,
        recall=lambda _sig: 1.0,
        aggregate_f1=lambda: 0.9,
        summary=lambda: "fallback-summary",
    )

    # Fallback branch without rich.
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("rich"):
            raise ImportError("no rich")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    pmod._print_rich_table(report)

    monkeypatch.setattr("builtins.__import__", real_import)
    pmod._print_rich_table(report)


def test_self_analyze_formats(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from drift.commands.self_analyze import self_analyze

    runner = CliRunner()

    fake_root = tmp_path
    (fake_root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    class _FakeResolved:
        @property
        def parent(self) -> Path:
            return fake_root / "src" / "drift" / "commands"

    monkeypatch.setattr("drift.commands.self_analyze.Path.resolve", lambda _self: _FakeResolved())

    cfg = SimpleNamespace(exclude=[])
    analysis = SimpleNamespace(findings=[], module_scores=[], drift_score=0.1, total_files=1)

    monkeypatch.setattr("drift.config.DriftConfig.load", lambda *_args, **_kwargs: cfg)
    monkeypatch.setattr("drift.analyzer.analyze_repo", lambda *_args, **_kwargs: analysis)
    monkeypatch.setattr("drift.output.json_output.analysis_to_json", lambda _a: "{}")
    monkeypatch.setattr("drift.output.json_output.findings_to_sarif", lambda _a: "{}")
    monkeypatch.setattr("drift.output.agent_tasks.analysis_to_agent_tasks_json", lambda _a: "{}")
    monkeypatch.setattr(
        "drift.output.rich_output.render_full_report", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "drift.output.rich_output.render_recommendations", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr("drift.recommendations.generate_recommendations", lambda _f: ["x"])

    out_json = tmp_path / "out.json"
    r1 = runner.invoke(self_analyze, ["--format", "json", "--output", str(out_json)])
    assert r1.exit_code == 0
    assert out_json.exists()

    r2 = runner.invoke(self_analyze, ["--format", "sarif"])
    assert r2.exit_code == 0

    r3 = runner.invoke(self_analyze, ["--format", "agent-tasks"])
    assert r3.exit_code == 0

    r4 = runner.invoke(self_analyze, ["--format", "rich"])
    assert r4.exit_code == 0


def test_setup_command_non_interactive_and_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from drift.commands.setup import setup

    runner = CliRunner()

    fake_profile = SimpleNamespace(
        weights={"pattern_fragmentation": 0.2},
        thresholds={"min_complexity": 5},
        fail_on="none",
        auto_calibrate=False,
        output_language=None,
    )
    monkeypatch.setattr("drift.profiles.get_profile", lambda _name: fake_profile)

    # JSON mode
    j = runner.invoke(setup, ["--repo", str(tmp_path), "--non-interactive", "--json"])
    assert j.exit_code == 0
    payload = json.loads(j.output)
    assert payload["profile"] == "vibe-coding"

    # Write mode
    w = runner.invoke(setup, ["--repo", str(tmp_path), "--non-interactive"])
    assert w.exit_code == 0
    assert (tmp_path / "drift.yaml").exists()
