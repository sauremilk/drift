"""Tests for scripts/nudge_gate.py — the pre-commit nudge revert gate."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GATE_PATH = _REPO_ROOT / "scripts" / "nudge_gate.py"


def _load_gate_module():
    """Load scripts/nudge_gate.py as an importable module for unit tests."""
    spec = importlib.util.spec_from_file_location("drift_nudge_gate", _GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate_module()


def _init_git_repo(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-q"], cwd=path, check=True, stdin=subprocess.DEVNULL
    )
    subprocess.run(
        ["git", "config", "user.email", "t@t.t"],
        cwd=path,
        check=True,
        stdin=subprocess.DEVNULL,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"],
        cwd=path,
        check=True,
        stdin=subprocess.DEVNULL,
    )


def _stage(path: Path, rel: str) -> None:
    subprocess.run(
        ["git", "add", "--", rel],
        cwd=path,
        check=True,
        stdin=subprocess.DEVNULL,
    )


def _write_state(
    repo: Path,
    *,
    revert_recommended: bool,
    changed_files: list[str],
    file_hashes: dict[str, str] | None = None,
) -> None:
    cache = repo / ".drift-cache"
    cache.mkdir(exist_ok=True)
    (cache / "last_nudge.json").write_text(
        json.dumps({
            "schema_version": 1,
            "revert_recommended": revert_recommended,
            "changed_files": changed_files,
            "file_hashes": file_hashes or {},
        }),
        encoding="utf-8",
    )


class TestNudgeGate:
    def test_passes_when_no_state_file_and_no_python_staged(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("hi", encoding="utf-8")
        _stage(tmp_path, "README.md")
        assert gate.run(tmp_path) == 0

    def test_passes_when_revert_not_recommended(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "src").mkdir()
        f = tmp_path / "src" / "x.py"
        f.write_text("a=1\n", encoding="utf-8")
        _stage(tmp_path, "src/x.py")
        _write_state(tmp_path, revert_recommended=False, changed_files=["src/x.py"])
        assert gate.run(tmp_path) == 0

    def test_blocks_when_revert_and_file_unchanged(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "src").mkdir()
        f = tmp_path / "src" / "x.py"
        content = b"a=1\n"
        f.write_bytes(content)
        _stage(tmp_path, "src/x.py")
        import hashlib

        h = hashlib.sha256(content).hexdigest()[:16]
        _write_state(
            tmp_path,
            revert_recommended=True,
            changed_files=["src/x.py"],
            file_hashes={"src/x.py": h},
        )
        assert gate.run(tmp_path) == 1

    def test_passes_when_revert_but_file_was_modified(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "src").mkdir()
        f = tmp_path / "src" / "x.py"
        f.write_text("a=1\n", encoding="utf-8")
        _stage(tmp_path, "src/x.py")
        # Stored hash refers to an older, now-changed state.
        _write_state(
            tmp_path,
            revert_recommended=True,
            changed_files=["src/x.py"],
            file_hashes={"src/x.py": "deadbeefdeadbeef"},
        )
        assert gate.run(tmp_path) == 0

    def test_passes_when_revert_but_files_not_staged(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("hi", encoding="utf-8")
        _stage(tmp_path, "README.md")
        _write_state(
            tmp_path,
            revert_recommended=True,
            changed_files=["src/x.py"],
            file_hashes={"src/x.py": "abc"},
        )
        assert gate.run(tmp_path) == 0

    def test_skipped_via_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _init_git_repo(tmp_path)
        (tmp_path / "src").mkdir()
        f = tmp_path / "src" / "x.py"
        content = b"a=1\n"
        f.write_bytes(content)
        _stage(tmp_path, "src/x.py")
        import hashlib

        h = hashlib.sha256(content).hexdigest()[:16]
        _write_state(
            tmp_path,
            revert_recommended=True,
            changed_files=["src/x.py"],
            file_hashes={"src/x.py": h},
        )
        monkeypatch.setenv("DRIFT_SKIP_NUDGE_GATE", "1")
        assert gate.run(tmp_path) == 0

    def test_on_missing_block_policy(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "x.py").write_text("a=1\n", encoding="utf-8")
        _stage(tmp_path, "src/x.py")
        (tmp_path / "drift.yaml").write_text(
            "nudge_gate:\n  on_missing: block\n", encoding="utf-8"
        )
        # No state file present.
        assert gate.run(tmp_path) == 1

    def test_on_missing_warn_policy_is_default(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "x.py").write_text("a=1\n", encoding="utf-8")
        _stage(tmp_path, "src/x.py")
        # No drift.yaml, no state — default policy is warn.
        assert gate.run(tmp_path) == 0
