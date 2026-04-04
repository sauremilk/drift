"""CLI tests for ``drift timeline`` command wiring."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from drift.cli import main


def test_timeline_command_builds_and_renders_timeline(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    config_file = tmp_path / "drift.yaml"
    config_file.write_text("{}", encoding="utf-8")

    fake_cfg = object()
    fake_analysis = SimpleNamespace(
        module_scores=[SimpleNamespace(path=Path("src"), drift_score=0.42)],
        commits=["c1"],
        file_histories={"src/a.py": object()},
        findings=[],
    )
    fake_timeline = object()
    calls: dict[str, object] = {}

    monkeypatch.setattr("drift.config.DriftConfig.load", lambda r, c: fake_cfg)

    def _fake_analyze(repo_path: Path, cfg: object, since_days: int):
        calls["analyze_repo"] = (repo_path, cfg, since_days)
        return fake_analysis

    def _fake_build(commits, file_histories, findings, module_scores):
        calls["build_timeline"] = (commits, file_histories, findings, module_scores)
        return fake_timeline

    def _fake_render(timeline_obj: object, console_obj: object) -> None:
        calls["render_timeline"] = (timeline_obj, console_obj)

    monkeypatch.setattr("drift.analyzer.analyze_repo", _fake_analyze)
    monkeypatch.setattr("drift.timeline.build_timeline", _fake_build)
    monkeypatch.setattr("drift.output.rich_output.render_timeline", _fake_render)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["timeline", "--repo", str(repo), "--since", "14", "--config", str(config_file)],
    )

    assert result.exit_code == 0, result.output
    assert "Drift Timeline — repo" in result.output
    assert calls["analyze_repo"] == (repo, fake_cfg, 14)
    assert calls["build_timeline"][0] == ["c1"]
    assert list(calls["build_timeline"][1].keys()) == ["src/a.py"]
    assert calls["build_timeline"][2] == []
    assert calls["build_timeline"][3] == {"src": 0.42}
    assert calls["render_timeline"][0] is fake_timeline


def test_timeline_command_handles_empty_commit_history(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    fake_cfg = object()
    fake_analysis = SimpleNamespace(
        module_scores=[],
        commits=[],
        file_histories={},
        findings=[],
    )
    calls: dict[str, object] = {}

    monkeypatch.setattr("drift.config.DriftConfig.load", lambda r, c: fake_cfg)
    monkeypatch.setattr(
        "drift.analyzer.analyze_repo",
        lambda repo_path, cfg, since_days: fake_analysis,
    )

    def _fake_build(commits, file_histories, findings, module_scores):
        calls["build_timeline"] = (commits, file_histories, findings, module_scores)
        return object()

    monkeypatch.setattr("drift.timeline.build_timeline", _fake_build)
    monkeypatch.setattr("drift.output.rich_output.render_timeline", lambda *_: None)

    runner = CliRunner()
    result = runner.invoke(main, ["timeline", "--repo", str(repo)])

    assert result.exit_code == 0, result.output
    assert calls["build_timeline"] == ([], {}, [], {})
