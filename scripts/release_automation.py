#!/usr/bin/env python3
"""Release Automation for Drift Analyzer."""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"


def get_git_tags() -> list[str]:
    """Get all git tags matching v*.*.* pattern, sorted."""
    try:
        result = subprocess.run(
            ["git", "tag", "-l", "v*.*.*"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return sorted(result.stdout.strip().split("\n"))
    except subprocess.CalledProcessError:
        return []


def get_latest_version() -> tuple[int, int, int]:
    """Parse latest git tag as (major, minor, patch)."""
    tags = get_git_tags()
    if not tags:
        return (0, 1, 0)

    latest = tags[-1]
    match = re.match(r"v(\d+)\.(\d+)\.(\d+)", latest)
    if match:
        major, minor, patch = match.groups()
        return (int(major), int(minor), int(patch))
    return (0, 1, 0)


def get_commits_since_tag() -> list[dict]:
    """Get commit info since last tag."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        last_tag = result.stdout.strip() if result.returncode == 0 else None
    except subprocess.CalledProcessError:
        last_tag = None

    range_spec = f"{last_tag}..HEAD" if last_tag else "HEAD"

    try:
        result = subprocess.run(
            ["git", "log", range_spec, "--format=%H|%s"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            hash_id, subject = line.split("|", 1)
            commits.append({"hash": hash_id[:7], "subject": subject})
        return commits
    except subprocess.CalledProcessError:
        return []


def analyze_version_bump(commits: list[dict]) -> tuple[int, int, int]:
    """Analyze commits and return (major, minor, patch) bumps."""
    has_breaking = False
    has_feature = False

    for commit in commits:
        subject = commit["subject"].lower()
        if "breaking change" in subject:
            has_breaking = True
            break
        if subject.startswith("feat"):
            has_feature = True

    if has_breaking:
        return (1, 0, 0)
    if has_feature:
        return (0, 1, 0)
    return (0, 0, 1)


def calculate_next_version() -> str:
    """Calculate next semantic version."""
    current = get_latest_version()
    commits = get_commits_since_tag()

    if not commits:
        print("ℹ No commits since last tag. Keeping current version.")
        return f"v{current[0]}.{current[1]}.{current[2]}"

    bump = analyze_version_bump(commits)
    next_version = (
        current[0] + bump[0],
        current[1] + bump[1],
        current[2] + bump[2],
    )

    return f"v{next_version[0]}.{next_version[1]}.{next_version[2]}"


def update_pyproject_version(version: str) -> bool:
    """Update version in pyproject.toml."""
    version_no_v = version.lstrip("v")

    try:
        content = PYPROJECT.read_text("utf-8")
        pattern = r'version = "[^"]+"'
        new_content = re.sub(
            pattern, f'version = "{version_no_v}"', content, count=1
        )

        if new_content == content:
            print(f"✗ Could not find version line in {PYPROJECT}")
            return False

        PYPROJECT.write_text(new_content, "utf-8")
        print(f"✓ Updated pyproject.toml: version = {version_no_v}")
        return True
    except Exception as e:
        print(f"✗ Error updating pyproject.toml: {e}")
        return False


def update_changelog(version: str) -> bool:
    """Update CHANGELOG.md with new version."""
    version_no_v = version.lstrip("v")

    try:
        commits = get_commits_since_tag()
        if not commits:
            print("ℹ No commits since last tag. Skipping CHANGELOG update.")
            return True

        changelog_content = (
            CHANGELOG.read_text("utf-8") if CHANGELOG.exists() else ""
        )

        features = [c for c in commits if c["subject"].lower().startswith("feat")]
        fixes = [c for c in commits if c["subject"].lower().startswith("fix")]
        breaking = [
            c for c in commits if "breaking change" in c["subject"].lower()
        ]
        other = [
            c
            for c in commits
            if c not in features + fixes + breaking
        ]

        today = datetime.now().strftime("%Y-%m-%d")
        new_section = f"\n## [{version_no_v}] — {today}\n\n"

        if breaking:
            new_section += "### ⚠️ Breaking Changes\n"
            for c in breaking:
                new_section += f"- {c['subject']}\n"
            new_section += "\n"

        if features:
            new_section += "### Added\n"
            for c in features:
                new_section += f"- {c['subject']}\n"
            new_section += "\n"

        if fixes:
            new_section += "### Fixed\n"
            for c in fixes:
                new_section += f"- {c['subject']}\n"
            new_section += "\n"

        if other:
            new_section += "### Other\n"
            for c in other:
                new_section += f"- {c['subject']}\n"
            new_section += "\n"

        if changelog_content.startswith("#"):
            lines = changelog_content.split("\n", 1)
            new_content = (
                lines[0]
                + "\n"
                + new_section
                + (lines[1] if len(lines) > 1 else "")
            )
        else:
            new_content = new_section + changelog_content

        CHANGELOG.write_text(new_content, "utf-8")
        print(f"✓ Updated CHANGELOG.md with version {version_no_v}")
        return True

    except Exception as e:
        print(f"✗ Error updating CHANGELOG.md: {e}")
        return False


def run_tests() -> bool:
    """Run quick tests (no slow tests)."""
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
    except subprocess.CalledProcessError as e:
        print(f"✗ Tests failed: {e}")
        return False


def git_commit_and_tag(version: str) -> bool:
    """Create git commits and tag."""
    version_no_v = version.lstrip("v")

    try:
        print(f"\n▶ Staging changes for version {version_no_v}...")

        subprocess.run(
            ["git", "add", "src/drift/", "tests/"],
            cwd=ROOT,
            capture_output=True,
        )

        print("Creating release commit...")
        subprocess.run(
            ["git", "add", "CHANGELOG.md", "pyproject.toml"],
            cwd=ROOT,
            check=True,
        )

        commit_msg = f"chore: Release {version_no_v} — update version and changelog"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=ROOT,
            check=True,
        )
        print(f"✓ Committed: {commit_msg}")

        print(f"▶ Creating git tag {version}...")
        subprocess.run(
            ["git", "tag", "-a", version, "-m", f"Release {version}"],
            cwd=ROOT,
            check=True,
        )
        print(f"✓ Tagged: {version}")

        print("Pushing to origin/master and tags...")
        subprocess.run(
            ["git", "push", "origin", "master"],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", version],
            cwd=ROOT,
            check=True,
        )
        print(f"✓ Pushed master and {version}")

        print(f"\n✅ Release {version} complete!")
        print("   → GitHub release will be created automatically")
        print("   → PyPI publication via .github/workflows/publish.yml")

        return True

    except subprocess.CalledProcessError as e:
        print(f"✗ Git operation failed: {e}")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Drift Release Automation")
    parser.add_argument(
        "--calc-version",
        action="store_true",
        help="Calculate next version based on commits",
    )
    parser.add_argument(
        "--update-changelog",
        action="store_true",
        help="Update CHANGELOG.md",
    )
    parser.add_argument(
        "--full-release",
        action="store_true",
        help="Full release: tests → version → changelog → commit → tag → push",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running tests",
    )

    args = parser.parse_args()

    do_tests = not args.skip_tests and (
        args.full_release or (not args.calc_version and not args.update_changelog)
    )
    do_version = args.calc_version or args.full_release or (
        not args.calc_version and not args.update_changelog
    )
    do_changelog = args.update_changelog or args.full_release
    do_commit_tag = args.full_release

    print("=" * 60)
    print("Drift Release Automation")
    print("=" * 60)

    if do_tests and not run_tests():
        print("\n✗ Tests failed. Aborting release.")
        return 1

    version = calculate_next_version()
    print(f"\n▶ Next version: {version}")

    if do_version and not update_pyproject_version(version):
        print("\n✗ Failed to update pyproject.toml")
        return 1

    if do_changelog and not update_changelog(version):
        print("\n✗ Failed to update CHANGELOG.md")
        return 1

    if do_commit_tag and not git_commit_and_tag(version):
        print("\n✗ Failed to commit and tag")
        return 1

    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
