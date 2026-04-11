from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner


def test_setup_helper_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    from drift.commands import setup as setup_mod

    answers = iter(["2", "3", "1"])
    monkeypatch.setattr("click.prompt", lambda *args, **kwargs: next(answers))

    assert setup_mod._ask_project_type() == "2"
    assert setup_mod._ask_ai_usage() == "3"
    assert setup_mod._ask_strictness() == "1"

    assert setup_mod._derive_profile("1", "1", "1") == "vibe-coding"
    assert setup_mod._derive_profile("1", "3", "3") == "strict"
    assert setup_mod._derive_profile("1", "3", "2") == "default"


def test_setup_build_config_and_overwrite_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from drift.commands.setup import _build_config, setup

    profile = SimpleNamespace(
        weights={"pattern_fragmentation": 0.2},
        thresholds={"min_complexity": 5},
        fail_on="none",
        auto_calibrate=False,
        output_language="de",
    )
    monkeypatch.setattr("drift.profiles.get_profile", lambda _name: profile)

    cfg = _build_config("default")
    assert cfg["language"] == "de"
    assert "weights" in cfg

    runner = CliRunner()

    # Existing config + decline overwrite -> clean abort path.
    (tmp_path / "drift.yaml").write_text("x: 1\n", encoding="utf-8")
    monkeypatch.setattr("click.confirm", lambda *args, **kwargs: False)
    abort_res = runner.invoke(setup, ["--repo", str(tmp_path), "--non-interactive"])
    assert abort_res.exit_code == 0

    # Existing config + accept overwrite path.
    monkeypatch.setattr("click.confirm", lambda *args, **kwargs: True)
    ok_res = runner.invoke(setup, ["--repo", str(tmp_path), "--non-interactive"])
    assert ok_res.exit_code == 0
    assert "drift.yaml erstellt" in ok_res.output


def test_setup_interactive_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from drift.commands.setup import setup

    profile = SimpleNamespace(
        weights={"pattern_fragmentation": 0.2},
        thresholds={"min_complexity": 5},
        fail_on="none",
        auto_calibrate=False,
        output_language=None,
    )
    monkeypatch.setattr("drift.profiles.get_profile", lambda _name: profile)

    answers = iter(["1", "2", "3"])
    monkeypatch.setattr("click.prompt", lambda *args, **kwargs: next(answers))

    runner = CliRunner()
    res = runner.invoke(setup, ["--repo", str(tmp_path)])
    assert res.exit_code == 0
    assert (tmp_path / "drift.yaml").exists()


def test_watch_importerror_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import builtins

    from drift.commands.watch import watch

    runner = CliRunner()
    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "watchfiles":
            raise ImportError("missing")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = runner.invoke(watch, ["--repo", str(tmp_path)])
    assert result.exit_code == 1
    assert "watchfiles" in result.output


def test_watch_happy_path_and_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from drift.commands.watch import watch

    runner = CliRunner()

    calls: list[dict] = []

    def fake_nudge(*, path, changed_files=None):
        calls.append({"path": path, "changed_files": changed_files})
        return {
            "direction": "stable",
            "delta": 0.0,
            "safe_to_commit": True,
            "new_findings": [],
            "resolved_findings": [],
        }

    class _Iter:
        def __iter__(self):
            yield {
                (1, str(tmp_path / "src" / "a.py")),
                (1, str(tmp_path / ".git" / "index")),
            }
            raise KeyboardInterrupt

    def fake_watch(*args, **kwargs):
        return _Iter()

    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "src" / "a.py").write_text("x=1\n", encoding="utf-8")

    sys_mod = __import__("sys")
    monkeypatch.setitem(sys_mod.modules, "watchfiles", SimpleNamespace(watch=fake_watch))
    monkeypatch.setitem(sys_mod.modules, "drift.api.nudge", SimpleNamespace(nudge=fake_nudge))
    monkeypatch.setattr(
        "drift.config.DriftConfig.load", lambda *_a, **_k: SimpleNamespace(exclude=[])
    )

    result = runner.invoke(watch, ["--repo", str(tmp_path), "--debounce", "0.1"])
    assert result.exit_code == 0
    assert len(calls) >= 2  # baseline + one change event
    assert calls[1]["changed_files"] == ["src/a.py"]
