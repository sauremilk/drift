from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "release_automation.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("release_automation", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upsert_release_section_repositions_existing_version_below_unreleased():
    module = _load_module()
    changelog = """## [Unreleased]

### Fixed
- Keep this note

## [1.4.1] – 2026-04-02

Short version: Previous release.

### Changed
- Prior change.

## [1.5.0] – 2026-04-02

Short version: Stale retry section.

### Changed
- Retry artifact.

## [1.4.0] – 2026-04-01

Short version: Older release.
"""
    new_section = """## [1.5.0] – 2026-04-02

Short version: Correct retry section.

### Changed
- Corrected release.

"""

    updated = module._upsert_release_section(changelog, "1.5.0", new_section)

    assert updated.count("## [1.5.0] – 2026-04-02") == 1
    assert updated.index("## [Unreleased]") < updated.index("## [1.5.0] – 2026-04-02")
    assert updated.index("## [1.5.0] – 2026-04-02") < updated.index("## [1.4.1] – 2026-04-02")
    assert "Retry artifact." not in updated
    assert "Corrected release." in updated


def test_upsert_release_section_with_only_unreleased_keeps_unreleased_on_top():
    module = _load_module()
    changelog = """## [Unreleased]

### Fixed
- Keep me first
"""
    new_section = """## [1.5.0] – 2026-04-02

Short version: First release.

### Changed
- Initial release.

"""

    updated = module._upsert_release_section(changelog, "1.5.0", new_section)

    assert updated.index("## [Unreleased]") < updated.index("## [1.5.0] – 2026-04-02")
    assert "Keep me first" in updated


def test_ensure_clean_worktree_rejects_dirty_repo(monkeypatch):
    module = _load_module()

    def _fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"], returncode=0, stdout=" M foo.py\n?? bar.txt\n"
        )

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.ensure_clean_worktree() is False


def test_ensure_release_target_available_rejects_existing_local_tag(monkeypatch):
    module = _load_module()

    def _fake_tag_exists(tag_name: str, *, remote: bool) -> bool:
        assert tag_name == "v1.5.0"
        return not remote

    monkeypatch.setattr(module, "_tag_exists", _fake_tag_exists)

    assert module.ensure_release_target_available("v1.5.0") is False


def test_get_latest_version_falls_back_to_local_tags_when_remote_unreachable(monkeypatch):
    module = _load_module()

    def _fake_run(args, **_kwargs):
        if args[:4] == ["git", "ls-remote", "--tags", "--refs"]:
            raise subprocess.CalledProcessError(returncode=1, cmd=args)
        if args == ["git", "tag", "-l", "v*.*.*"]:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="v1.4.1\nv1.5.0\n")
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.get_latest_version() == (1, 5, 0)


def test_commit_messages_since_last_tag_falls_back_to_head_when_base_tag_missing(monkeypatch):
    module = _load_module()
    seen_ranges: list[str] = []

    def _fake_run(args, **_kwargs):
        if args[:2] != ["git", "log"]:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="")

        seen_ranges.append(args[2])
        if args[2] == "v9.9.9..HEAD":
            return subprocess.CompletedProcess(args=args, returncode=128, stdout="")
        if args[2] == "HEAD":
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="fix: x\x1e")
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    messages = module._commit_messages_since_last_tag("v9.9.9")

    assert seen_ranges == ["v9.9.9..HEAD", "HEAD"]
    assert messages == ["fix: x"]


def test_rollback_local_release_state_restores_commit_tag_and_files(monkeypatch):
    module = _load_module()
    calls: list[list[str]] = []

    def _fake_run(args, **_kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    module.rollback_local_release_state("abc123", "v1.5.0", created_commit=True, created_tag=True)

    assert calls == [
        ["git", "tag", "-d", "v1.5.0"],
        ["git", "reset", "--soft", "abc123"],
        [
            "git",
            "restore",
            "--source=HEAD",
            "--staged",
            "--worktree",
            "pyproject.toml",
            "CHANGELOG.md",
            "uv.lock",
        ],
    ]
