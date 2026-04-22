"""Tests for scripts/session_handover.py helper script."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "session_handover.py"

_spec = importlib.util.spec_from_file_location("session_handover_script", _SCRIPT_PATH)
assert _spec and _spec.loader
_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_script)  # type: ignore[union-attr]


def test_build_handover_markdown_has_required_sections() -> None:
    content = _script.build_handover_markdown(
        task="Fix gate checks",
        session_id="abc12345",
        diff_stat=" Makefile | 10 +++++-----",
        gate_output="[Gate 3] OK",
        latest_commit_subject="fix: add gate checker",
    )

    assert "## Scope" in content
    assert "## Was wurde geaendert" in content
    assert "## Offene Gates" in content
    assert "## Naechster Schritt" in content
    assert 'session_id: "abc12345"' in content


def test_make_session_id_uses_first_8_chars() -> None:
    assert _script.make_session_id("12345678-abcd-efgh") == "12345678"


def test_make_session_id_generates_when_missing() -> None:
    generated = _script.make_session_id(None)
    assert len(generated) == 8
    assert generated.isalnum()
