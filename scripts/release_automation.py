#!/usr/bin/env python3
"""Simple Release Automation for Drift Analyzer."""

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
PRE_PUSH_HOOK = ROOT / ".githooks" / "pre-push"


def run_tests() -> bool:
    """Run quick tests."""
    print("\n▶ Running quick tests...")
    try:
        subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "tests/",
                "--tb=short",
                "--ignore=tests/test_smoke.py",
                "-q",
                "--maxfail=1",
            ],
            cwd=ROOT,
            check=True,
        )
        print("✓ Tests passed")
        return True
    except subprocess.CalledProcessError:
        print("✗ Tests failed")
        return False


def _get_commit_summary() -> str:
    """Return a curated one-line summary of commits since last tag."""
    try:
        last_tag = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        log = subprocess.run(
            ["git", "log", f"{last_tag}..HEAD", "--oneline", "--no-merges"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        lines = [line for line in log.splitlines() if line]
        if not lines:
            return "Maintenance and dependency updates."
        subject = lines[0].split(" ", 1)[-1] if " " in lines[0] else lines[0]
        # Strip conventional-commit prefixes (feat:, fix:, chore:, etc.)
        subject = re.sub(r"^[a-z]+(\([^)]+\))?:\s*", "", subject)
        extras = f" (+{len(lines) - 1} more commits)" if len(lines) > 1 else ""
        subject = subject[0].upper() + subject[1:] if subject else subject
        if not subject.endswith("."):
            subject += "."
        return subject + extras
    except Exception:
        return "Maintenance updates."


def get_latest_version() -> tuple[int, int, int]:
    """Get latest version from remote tags (source of truth = what is published).

    Falls back to local tags if remote is unreachable.
    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", "origin"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        tags = re.findall(r"refs/tags/(v\d+\.\d+\.\d+)$", result.stdout, re.MULTILINE)
        if tags:
            tags = sorted(tags, key=lambda t: tuple(int(x) for x in t.lstrip("v").split(".")))
            match = re.match(r"v(\d+)\.(\d+)\.(\d+)", tags[-1])
            if match:
                major, minor, patch = match.groups()
                return (int(major), int(minor), int(patch))
    except Exception:
        pass
    return (0, 1, 0)


def get_remote_sha(ref: str) -> str:
    """Return remote SHA for ref or 40x0 if ref does not exist on remote."""
    result = subprocess.run(
        ["git", "ls-remote", "--quiet", "origin", ref],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return "0" * 40
    for line in result.stdout.splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        sha, found_ref = parts
        if found_ref == ref:
            return sha
    return result.stdout.split()[0]


def _resolve_shell() -> str | None:
    """Resolve a POSIX-compatible shell, preferring Git-for-Windows sh over WSL."""
    candidates = [
        r"C:\Program Files\Git\bin\sh.exe",
        r"C:\Program Files\Git\usr\bin\sh.exe",
        shutil.which("bash"),
        shutil.which("sh"),
    ]
    return next(
        (c for c in candidates if c and Path(c).exists()),
        None,
    )


def run_pre_push_preflight(tag_name: str) -> bool:
    """Run pre-push hook for the current branch (before tag exists) to fail early.

    Only validates the branch-push portion of the hook. Tag-related hook
    gates are intentionally skipped here because the tag does not yet exist at
    preflight time; the hook will re-run automatically on actual push.
    """
    if not PRE_PUSH_HOOK.exists():
        print("ℹ No pre-push hook found. Skipping preflight.")
        return True

    shell = _resolve_shell()
    if shell is None:
        print("✗ Could not find sh/bash to run pre-push hook.")
        print("  Install Git for Windows or ensure sh is in PATH.")
        return False

    local_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    current_branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    remote_head = get_remote_sha(f"refs/heads/{current_branch}")

    # Only simulate branch push — tag does not exist yet at this point.
    hook_input = (
        f"refs/heads/{current_branch} {local_head} refs/heads/{current_branch} {remote_head}\n"
    )

    # Ensure the venv's Scripts/bin directory is first in PATH so that the
    # hook's bare `python`, `pytest`, `ruff`, `drift` etc. resolve correctly
    # on Windows (where the Windows Store alias may otherwise intercept them).
    import os as _os
    venv_scripts = ROOT / ".venv" / ("Scripts" if _os.name == "nt" else "bin")
    hook_env = dict(_os.environ)
    if venv_scripts.is_dir():
        hook_env["PATH"] = str(venv_scripts) + _os.pathsep + hook_env.get("PATH", "")

    print(f"\n▶ Running pre-push preflight checks ({current_branch} branch)...")
    preflight = subprocess.run(
        [shell, str(PRE_PUSH_HOOK)],
        cwd=ROOT,
        input=hook_input.encode("utf-8"),
        env=hook_env,
        check=False,
    )
    if preflight.returncode != 0:
        print("✗ Pre-push preflight failed. Fix issues above before pushing.")
        return False

    print("✓ Pre-push preflight passed")
    return True


def create_github_release(tag_name: str, version_no_v: str) -> bool:
    """Create GitHub release so publish workflow (release.created) is triggered."""
    gh_cli = shutil.which("gh")
    if gh_cli is None:
        print("✗ GitHub CLI (gh) not found.")
        print("  Install gh and run 'gh auth login' once.")
        return False

    title = f"v{version_no_v}"
    notes = f"Automated release {title} via scripts/release_automation.py"

    print("\n▶ Creating GitHub release...")
    result = subprocess.run(
        [gh_cli, "release", "create", tag_name, "--title", title, "--notes", notes],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        print("✗ GitHub release creation failed.")
        print("  PyPI publish will not start because workflow listens to release.created.")
        return False

    print(f"✓ GitHub release created: {tag_name}")
    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Drift Release Automation")
    parser.add_argument("--full-release", action="store_true", help="Full release workflow")
    parser.add_argument("--calc-version", action="store_true", help="Calculate version only")
    parser.add_argument("--skip-tests", action="store_true", help="Skip tests")

    args = parser.parse_args()

    print("=" * 60)
    print("Drift Release Automation")
    print("=" * 60)

    # Run tests if not skipped
    if not args.skip_tests and (args.full_release or args.calc_version) and not run_tests():
        print("\n✗ Tests failed. Aborting release.")
        return 1

    # Calculate next version
    current = get_latest_version()
    next_patch = current[2] + 1
    next_version = f"v{current[0]}.{current[1]}.{next_patch}"

    print(f"\n▶ Next version: {next_version}")

    if not args.full_release:
        print("(Use --full-release to perform actual release)")
        return 0

    # Full release: update files, commit, tag, push
    version_no_v = next_version.lstrip("v")

    try:
        # Update pyproject.toml
        pyproject_content = PYPROJECT.read_text("utf-8")
        pyproject_content = re.sub(
            r'version = "[^"]+"',
            f'version = "{version_no_v}"',
            pyproject_content,
            count=1,
        )
        PYPROJECT.write_text(pyproject_content, "utf-8")
        print(f"✓ Updated pyproject.toml: {version_no_v}")

        # Update CHANGELOG with format required by check_release_discipline.py:
        # - header: ## [x.y.z] – YYYY-MM-DD  (en-dash)
        # - first line: Short version: <sentence>
        # - curated bullets under ### Added / Changed / Fixed
        today = datetime.now().strftime("%Y-%m-%d")
        commit_summary = _get_commit_summary()
        new_section = (
            f"## [{version_no_v}] \u2013 {today}\n\n"
            f"Short version: {commit_summary}\n\n"
            f"### Changed\n\n"
            f"- {commit_summary}\n\n"
        )
        changelog_content = ""
        if CHANGELOG.exists():
            changelog_content = CHANGELOG.read_text("utf-8")

        CHANGELOG.write_text(new_section + changelog_content, "utf-8")
        print(f"✓ Updated CHANGELOG.md: {version_no_v}")

        # Create release commit and tag BEFORE preflight, so the pre-push
        # hook sees the CHANGELOG update in the committed state.
        print("\n▶ Creating release commit and tag...")
        subprocess.run(
            ["git", "add", "pyproject.toml", "CHANGELOG.md"],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"chore: Release {version_no_v}"],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            ["git", "tag", "-a", next_version, "-m", f"Release {next_version}"],
            cwd=ROOT,
            check=True,
        )

        # Preflight: run push gates AFTER commit so CHANGELOG gate sees
        # the release commit.  On failure, undo the commit+tag.
        if not run_pre_push_preflight(next_version):
            print("▶ Rolling back release commit and tag...")
            subprocess.run(["git", "tag", "-d", next_version], cwd=ROOT, check=False)
            subprocess.run(["git", "reset", "--soft", "HEAD~1"], cwd=ROOT, check=False)
            subprocess.run(
                ["git", "checkout", "--", "pyproject.toml", "CHANGELOG.md"],
                cwd=ROOT, check=False,
            )
            return 1

        current_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "push", "origin", current_branch, next_version],
            cwd=ROOT,
            check=True,
        )
        if not create_github_release(next_version, version_no_v):
            return 1

        print(f"✓ Committed: chore: Release {version_no_v}")
        print(f"✓ Tagged: {next_version}")
        print("✓ Pushed to GitHub")
        print("✓ Triggered publish workflow via GitHub release")
        print(f"\n✅ Release {next_version} complete!")
        print("   → GitHub Actions publish.yml should now publish to PyPI")

        return 0

    except subprocess.CalledProcessError as e:
        print(f"✗ Error: {e}")
        return 1
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
