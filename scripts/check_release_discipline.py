#!/usr/bin/env python3
"""Enforce Drift's binding release discipline.

Checks the current release metadata against the documented rule:
- top changelog entry must match pyproject.toml version
- top changelog entry must start with a short summary sentence
- top changelog entry must use curated Added/Changed/Fixed bullets
- top changelog entry must stay small enough to communicate one coherent step
- changelog bullets must not simply replay conventional commit prefixes
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

RELEASE_HEADER_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\]\s+[–-]\s+.+$", re.MULTILINE)
SECTION_HEADER_RE = re.compile(r"^### (Added|Changed|Fixed)\s*$")
CONVENTIONAL_COMMIT_RE = re.compile(
    r"^-\s+(feat|fix|docs|chore|refactor|perf|test|style|ci)(\(.+\))?:",
    re.IGNORECASE,
)


def _fail(message: str) -> None:
    print(f"ERROR: {message}", flush=True)
    sys.exit(1)


def _ok(message: str) -> None:
    print(f"OK: {message}", flush=True)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )


def _tag_exists(tag: str) -> bool:
    result = _git("rev-parse", "--verify", "--quiet", f"refs/tags/{tag}")
    return result.returncode == 0


def _is_ancestor(ancestor_ref: str, descendant_ref: str = "HEAD") -> bool:
    result = _git("merge-base", "--is-ancestor", ancestor_ref, descendant_ref)
    return result.returncode == 0


def _warn(message: str) -> None:
    print(f"WARNING: {message}", flush=True)


def _find_release_commit_on_main(version: str) -> str | None:
    """Find the correct 'chore: Release X.Y.Z' commit on HEAD's lineage."""
    result = _git(
        "log", "--oneline", "--grep", f"chore: Release {version}", "--format=%H", "HEAD",
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().splitlines()[0]
    return None


def _validate_version_tag_lineage(version: str) -> None:
    tag = f"v{version}"

    if not _tag_exists(tag):
        _fail(
            "Release tag lineage check failed. "
            f"Expected release tag '{tag}' for version '{version}', but the tag does not exist."
        )

    if _is_ancestor(tag, "HEAD"):
        return

    # Tag exists but is not an ancestor of HEAD — orphaned/rewritten tag.
    correct_commit = _find_release_commit_on_main(version)
    repair_hint = ""
    if correct_commit:
        short = correct_commit[:12]
        repair_hint = (
            f"\n  Detected correct release commit on main: {short}"
            f"\n  Repair: git tag -f {tag} {short} && git push origin {tag} -f"
        )

    message = (
        "Release tag lineage check failed. "
        f"Tag '{tag}' is not an ancestor of HEAD. "
        "This indicates a detached/rewritten release tag and can block "
        "python-semantic-release."
        f"{repair_hint}"
    )

    if os.environ.get("DRIFT_TAG_LINEAGE_WARN") == "1":
        _warn(message + " (continuing because DRIFT_TAG_LINEAGE_WARN=1)")
        return

    _fail(message)


def _read_pyproject_version() -> str:
    pyproject_path = _repo_root() / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)
    return data["project"]["version"]


def _read_changelog() -> str:
    changelog_path = _repo_root() / "CHANGELOG.md"
    return changelog_path.read_text(encoding="utf-8")


def _extract_top_release(changelog_text: str) -> tuple[str, str]:
    matches = list(RELEASE_HEADER_RE.finditer(changelog_text))
    if not matches:
        _fail(
            "CHANGELOG.md does not contain any release headings in the form "
            "'## [x.y.z] – YYYY-MM-DD'."
        )

    first = matches[0]
    version = first.group(1)
    start = first.end()
    end = matches[1].start() if len(matches) > 1 else len(changelog_text)
    body = changelog_text[start:end].strip("\n")
    return version, body


def _validate_summary(body: str) -> None:
    lines = [line.rstrip() for line in body.splitlines()]
    first_non_empty = next((line.strip() for line in lines if line.strip()), None)
    if first_non_empty is None:
        _fail("Top changelog release entry is empty.")

    if not first_non_empty.startswith("Short version:"):
        _fail("Top changelog release entry must begin with a 'Short version:' summary line.")


def _collect_release_bullets(body: str) -> list[str]:
    current_section: str | None = None
    bullets: list[str] = []

    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        section_match = SECTION_HEADER_RE.match(line.strip())
        if section_match:
            current_section = section_match.group(1)
            continue

        if line.startswith("### "):
            current_section = None
            continue

        if current_section in {"Added", "Changed", "Fixed"} and line.lstrip().startswith("- "):
            bullets.append(line.lstrip())

    return bullets


def _validate_curated_bullets(body: str) -> None:
    bullets = _collect_release_bullets(body)
    if not bullets:
        _fail(
            "Top changelog release entry must contain curated bullets under "
            "Added, Changed, or Fixed."
        )

    if len(bullets) > 5:
        _fail(
            "Top changelog release entry has more than 5 bullets. "
            "Split the release or compress it into a smaller coherent summary."
        )

    for bullet in bullets:
        if CONVENTIONAL_COMMIT_RE.match(bullet):
            _fail(
                "Top changelog release entry contains a raw conventional-commit style bullet. "
                "Curate release notes by user impact instead of replaying commit messages."
            )


def validate_release_discipline() -> None:
    pyproject_version = _read_pyproject_version()
    changelog_version, changelog_body = _extract_top_release(_read_changelog())

    if changelog_version != pyproject_version:
        _fail(
            "Top changelog release does not match pyproject.toml version. "
            f"pyproject={pyproject_version}, top changelog={changelog_version}."
        )

    _validate_summary(changelog_body)
    _validate_curated_bullets(changelog_body)
    _validate_version_tag_lineage(pyproject_version)
    _ok(f"Release discipline checks passed for version '{pyproject_version}'")


if __name__ == "__main__":
    validate_release_discipline()
