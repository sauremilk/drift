from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

HOOK_SOURCE = Path(__file__).resolve().parent.parent / ".githooks" / "pre-push"


def _resolve_posix_shell() -> str | None:
    git_exe = shutil.which("git")
    if git_exe:
        git_path = Path(git_exe).resolve()
        git_root = git_path.parent.parent
        bundled_candidates = [
            git_root / "bin" / "sh.exe",
            git_root / "usr" / "bin" / "sh.exe",
            git_root / "bin" / "sh",
            git_root / "usr" / "bin" / "sh",
        ]
        for candidate in bundled_candidates:
            if candidate.exists():
                return str(candidate)

    for cmd in ("sh", "bash"):
        resolved = shutil.which(cmd)
        if resolved:
            return resolved

    return None


SHELL_CMD = _resolve_posix_shell()


@dataclass(frozen=True)
class PushCase:
    name: str
    commit_message: str
    changed_files: dict[str, str]
    expected_exit_code: int
    expected_output: str
    env_overrides: dict[str, str] | None = None
    tag_base: bool = False


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )


def _write(repo: Path, relative_path: str, content: str) -> None:
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _seed_repo(tmp_path: Path, case: PushCase) -> tuple[Path, str, str]:
    repo = tmp_path / case.name
    repo.mkdir(parents=True, exist_ok=True)

    _run_git(repo, "init", "-b", "main")
    _run_git(repo, "config", "user.name", "Drift Test")
    _run_git(repo, "config", "user.email", "drift-tests@example.com")

    _write(repo, "README.md", "# drift pre-push test\n")
    _write(repo, "CHANGELOG.md", "# Changelog\n")
    _write(repo, "docs/STUDY.md", "# Study\n")
    _write(
        repo,
        "pyproject.toml",
        "[project]\nname = \"drift-prepush-test\"\nversion = \"1.0.0\"\n",
    )
    _write(repo, "uv.lock", "version = 1\n")
    _write(repo, "src/drift/__init__.py", "")
    _write(repo, "audit_results/fmea_matrix.md", "# fmea\n")
    _write(repo, "audit_results/stride_threat_model.md", "# stride\n")
    _write(repo, "audit_results/fault_trees.md", "# fault trees\n")
    _write(repo, "audit_results/risk_register.md", "# risk register\n")

    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-m", "chore: baseline")
    base_sha = _run_git(repo, "rev-parse", "HEAD").stdout.strip()

    if case.tag_base:
        _run_git(repo, "tag", "v1.0.0")

    for rel_path, content in case.changed_files.items():
        _write(repo, rel_path, content)

    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-m", case.commit_message)
    head_sha = _run_git(repo, "rev-parse", "HEAD").stdout.strip()

    hook_target = repo / ".githooks" / "pre-push"
    hook_target.parent.mkdir(parents=True, exist_ok=True)
    hook_target.write_text(HOOK_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")

    # Avoid running expensive local CI checks in gate-focused tests.
    (repo / ".git" / ".drift-prepush-last-success").write_text(
        f"{head_sha}\n", encoding="utf-8"
    )

    return repo, base_sha, head_sha


def _run_pre_push(
    repo: Path,
    base_sha: str,
    head_sha: str,
    env_overrides: dict[str, str] | None,
) -> tuple[int, str]:
    env = os.environ.copy()
    # Strip inherited DRIFT_SKIP_* vars so gate-failure tests aren't affected by
    # the caller's bypass flags (e.g. set during a push session).
    _drift_skip_keys = [k for k in env if k.startswith("DRIFT_SKIP_")]
    for k in _drift_skip_keys:
        env.pop(k, None)
    if env_overrides:
        env.update(env_overrides)

    stdin_payload = f"refs/heads/main {head_sha} refs/heads/main {base_sha}\n"
    result = subprocess.run(
        [str(SHELL_CMD), str(repo / ".githooks" / "pre-push")],
        cwd=repo,
        input=stdin_payload.encode("utf-8"),
        capture_output=True,
        env=env,
        check=False,
    )
    output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    return result.returncode, output


@pytest.mark.skipif(
    shutil.which("git") is None or SHELL_CMD is None,
    reason="requires git and a POSIX shell",
)
@pytest.mark.parametrize(
    "case",
    [
        PushCase(
            name="changelog_gate_fails",
            commit_message="fix: missing changelog update",
            changed_files={"README.md": "# updated\n"},
            expected_exit_code=1,
            expected_output="CHANGELOG gate failed",
        ),
        PushCase(
            name="version_bump_gate_fails",
            commit_message="chore: change pyproject without bump",
            changed_files={
                "pyproject.toml": (
                    "[project]\nname = \"drift-prepush-test\"\n"
                    "version = \"1.0.0\"\ndescription = \"changed\"\n"
                ),
                "uv.lock": "version = 2\n",
            },
            expected_exit_code=1,
            expected_output="Version bump gate failed",
            tag_base=True,
        ),
        PushCase(
            name="lockfile_gate_fails",
            commit_message="chore: bump version but forget lockfile",
            changed_files={
                "pyproject.toml": (
                    "[project]\nname = \"drift-prepush-test\"\n"
                    "version = \"1.0.1\"\n"
                )
            },
            expected_exit_code=1,
            expected_output="Lock-file sync gate failed",
            tag_base=True,
        ),
        PushCase(
            name="docstring_gate_fails",
            commit_message="chore: add public api without docstring",
            changed_files={"src/drift/new_api.py": "def run_task():\n    return 42\n"},
            expected_exit_code=1,
            expected_output="Public API docstring gate failed",
        ),
        PushCase(
            name="risk_audit_gate_fails",
            commit_message="chore: signal change without audit",
            changed_files={
                "src/drift/signals/new_signal.py": (
                    "def detect():\n"
                    "    \"\"\"Synthetic signal entrypoint for hook tests.\"\"\"\n"
                    "    return []\n"
                )
            },
            expected_exit_code=1,
            expected_output="Risk audit gate failed",
        ),
    ],
    ids=lambda case: case.name,
)
def test_pre_push_gate_failures_are_enforced(tmp_path: Path, case: PushCase) -> None:
    repo, base_sha, head_sha = _seed_repo(tmp_path, case)

    return_code, output = _run_pre_push(repo, base_sha, head_sha, case.env_overrides)

    assert return_code == case.expected_exit_code
    assert case.expected_output in output


@pytest.mark.skipif(
    shutil.which("git") is None or SHELL_CMD is None,
    reason="requires git and a POSIX shell",
)
@pytest.mark.parametrize(
    "case",
    [
        PushCase(
            name="skip_changelog_gate",
            commit_message="fix: changelog intentionally skipped",
            changed_files={"README.md": "# updated\n"},
            expected_exit_code=0,
            expected_output="CHANGELOG gate skipped",
            env_overrides={"DRIFT_SKIP_CHANGELOG": "1"},
        ),
        PushCase(
            name="skip_version_bump_gate",
            commit_message="chore: pyproject changed",
            changed_files={
                "pyproject.toml": (
                    "[project]\nname = \"drift-prepush-test\"\n"
                    "version = \"1.0.0\"\ndescription = \"changed\"\n"
                ),
                "uv.lock": "version = 2\n",
            },
            expected_exit_code=0,
            expected_output="Version bump gate skipped",
            env_overrides={"DRIFT_SKIP_VERSION_BUMP": "1"},
            tag_base=True,
        ),
        PushCase(
            name="skip_lockfile_gate",
            commit_message="chore: pyproject changed without lock update",
            changed_files={
                "pyproject.toml": (
                    "[project]\nname = \"drift-prepush-test\"\n"
                    "version = \"1.0.1\"\n"
                )
            },
            expected_exit_code=0,
            expected_output="Lock-file sync gate skipped",
            env_overrides={"DRIFT_SKIP_LOCKFILE": "1"},
            tag_base=True,
        ),
        PushCase(
            name="skip_docstring_gate",
            commit_message="chore: add public api without docstring",
            changed_files={"src/drift/new_api.py": "def run_task():\n    return 42\n"},
            expected_exit_code=0,
            expected_output="Public API docstring gate skipped",
            env_overrides={"DRIFT_SKIP_DOCSTRING": "1"},
        ),
        PushCase(
            name="skip_risk_audit_gate",
            commit_message="chore: signal change without audit",
            changed_files={
                "src/drift/signals/new_signal.py": (
                    "def detect():\n"
                    "    \"\"\"Synthetic signal entrypoint for hook tests.\"\"\"\n"
                    "    return []\n"
                )
            },
            expected_exit_code=0,
            expected_output="Risk audit gate skipped",
            env_overrides={"DRIFT_SKIP_RISK_AUDIT": "1"},
        ),
        PushCase(
            name="skip_all_hooks",
            commit_message="chore: blocked path but all hooks skipped",
            changed_files={"tagesplanung/private.md": "do not push\n"},
            expected_exit_code=0,
            expected_output="All gates skipped",
            env_overrides={"DRIFT_SKIP_HOOKS": "1"},
        ),
    ],
    ids=lambda case: case.name,
)
def test_pre_push_skip_overrides_allow_push(tmp_path: Path, case: PushCase) -> None:
    repo, base_sha, head_sha = _seed_repo(tmp_path, case)

    return_code, output = _run_pre_push(repo, base_sha, head_sha, case.env_overrides)

    assert return_code == case.expected_exit_code
    assert case.expected_output in output
