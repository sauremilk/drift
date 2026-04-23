"""Coverage-Boost: commands/explain.py — output/repo-context branches."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from drift.commands.explain import explain


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# --list --output file.json  (covers _write_json_output in list_all branch)
# ---------------------------------------------------------------------------


def test_explain_list_to_json_file(runner: CliRunner, tmp_path: Path) -> None:
    out_file = tmp_path / "signals.json"
    result = runner.invoke(explain, ["--list", "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) > 0


# ---------------------------------------------------------------------------
# drift explain DRIFT-xxxx --output file.json  (error-code + output branch)
# ---------------------------------------------------------------------------


def test_explain_error_code_to_json_file(runner: CliRunner, tmp_path: Path) -> None:
    out_file = tmp_path / "err.json"
    # Use a known error code; DRIFT-1001 should exist
    result = runner.invoke(explain, ["DRIFT-1001", "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert "code" in data


# ---------------------------------------------------------------------------
# --repo-context with mocked _repo_examples_for_signal (covers _print_repo_examples)
# ---------------------------------------------------------------------------


def test_explain_repo_context_no_examples(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Covers _print_repo_examples when no examples are found."""
    monkeypatch.setattr(
        "drift.api._repo_examples_for_signal",
        lambda *a, **kw: [],
    )
    result = runner.invoke(explain, ["PFS", "--repo-context", "--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "No findings" in result.output or len(result.output) > 0


def test_explain_repo_context_with_examples(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Covers _print_repo_examples when examples are present."""
    fake_examples: list[dict[str, Any]] = [
        {"file": "src/foo.py", "line": 42, "finding": "Pattern issue", "next_action": "refactor"},
        {"file": "src/bar.py", "line": None, "finding": "Another issue", "next_action": None},
    ]
    monkeypatch.setattr(
        "drift.api._repo_examples_for_signal",
        lambda *a, **kw: fake_examples,
    )
    result = runner.invoke(explain, ["PFS", "--repo-context", "--repo", str(tmp_path)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# _append_contract_section with list value (covers the list branch)
# ---------------------------------------------------------------------------


def test_append_contract_section_with_list_value() -> None:
    """_append_contract_section: value is a list → body.append per item."""
    from rich.text import Text

    from drift.commands.explain import _append_contract_section

    body = Text()
    contract: dict[str, Any] = {
        "notes": ["note 1", "note 2"],
    }
    _append_contract_section(body, contract)
    text = body.plain
    assert "note 1" in text
    assert "note 2" in text


def test_append_contract_section_with_dict_value() -> None:
    """_append_contract_section: value is a dict."""
    from rich.text import Text

    from drift.commands.explain import _append_contract_section

    body = Text()
    contract: dict[str, Any] = {
        "thresholds": {"min_loc": 5, "min_complexity": 2},
    }
    _append_contract_section(body, contract)
    text = body.plain
    assert "min_loc" in text


# ---------------------------------------------------------------------------
# explain with unknown signal (exit 1)
# ---------------------------------------------------------------------------


def test_explain_unknown_signal(runner: CliRunner) -> None:
    result = runner.invoke(explain, ["XYZUNKNOWN"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# explain signal with --output (covers _write_json_output for signal payload)
# ---------------------------------------------------------------------------


def test_explain_signal_with_output_file(runner: CliRunner, tmp_path: Path) -> None:
    out_file = tmp_path / "pfs.json"
    result = runner.invoke(explain, ["PFS", "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["abbreviation"] == "PFS"
