#!/usr/bin/env python3
"""Version-consistency synchroniser for drift.

Reads the canonical version from ``pyproject.toml`` and repairs any
inconsistencies in ``llms.txt`` and ``SECURITY.md`` without touching
``pyproject.toml`` or ``CHANGELOG.md`` (those are managed by PSR/CI).

This script is the **single source of truth** for version-ref repairs.
It is called:
  - by ``scripts/release.yml`` (CI) to keep files in sync after PSR release
  - by ``.githooks/pre-push`` (auto-repair safety net before gates run)
  - manually by developers: ``python scripts/sync_version.py --fix``

Usage:
    python scripts/sync_version.py              # check only (exit 1 on drift)
    python scripts/sync_version.py --fix        # check + auto-repair files
    python scripts/sync_version.py --fix --git-add          # repair + stage
    python scripts/sync_version.py --fix --git-add --commit # repair + stage + chore commit
    python scripts/sync_version.py --json       # machine-readable (check only)

Exit codes:
    0 – all refs consistent (or successfully repaired)
    1 – inconsistencies detected (check mode) or repair failed
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class VersionFix:
    """Describes one detected (and optionally applied) version-ref repair."""

    file: str
    check_id: str
    description: str
    old_value: str
    new_value: str
    applied: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_pyproject_version() -> str:
    path = _REPO_ROOT / "pyproject.toml"
    if not path.exists():
        print("ERROR: pyproject.toml not found", flush=True)
        sys.exit(1)
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    try:
        return data["project"]["version"]
    except KeyError:
        print("ERROR: pyproject.toml missing [project].version", flush=True)
        sys.exit(1)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


# ---------------------------------------------------------------------------
# Check + repair: llms.txt
# ---------------------------------------------------------------------------

_LLMS_STATUS_RE = re.compile(r"(Release status:\s*)(v?[\d]+\.[\d]+\.[\d]+)")


def _check_llms_txt(version: str, *, apply: bool) -> list[VersionFix]:
    fixes: list[VersionFix] = []
    path = _REPO_ROOT / "llms.txt"
    if not path.exists():
        return fixes

    text = path.read_text(encoding="utf-8")
    updated = text

    for m in _LLMS_STATUS_RE.finditer(text):
        claimed = m.group(2).lstrip("v")
        if claimed == version:
            continue

        fix = VersionFix(
            file="llms.txt",
            check_id="llms_version_mismatch",
            description=f"Release status: v{claimed} → v{version}",
            old_value=claimed,
            new_value=version,
        )

        if apply:
            updated = updated[: m.start(2)] + f"v{version}" + updated[m.end(2) :]
            fix.applied = True

        fixes.append(fix)

    if apply and updated != text:
        path.write_text(updated, encoding="utf-8")

    return fixes


# ---------------------------------------------------------------------------
# Check + repair: SECURITY.md
# ---------------------------------------------------------------------------

_SECURITY_RELEASE_LINE_RE = re.compile(
    r"(Current release line:\s*\*\*)(v[\d.]+)(\*\*\.)"
)
_SECURITY_TABLE_HEADER_RE = re.compile(
    r"(\| Version \| Supported\s*\n\| [-]+ \| [-]+.*?\n)", re.DOTALL
)


def _check_security_md(version: str, *, apply: bool) -> list[VersionFix]:
    fixes: list[VersionFix] = []
    path = _REPO_ROOT / "SECURITY.md"
    if not path.exists():
        return fixes

    text = path.read_text(encoding="utf-8")
    major_minor = ".".join(version.split(".")[:2])
    pattern = f"{major_minor}.x"

    # Fix 1: Add missing major.minor.x row to supported-versions table
    if pattern not in text:
        fix = VersionFix(
            file="SECURITY.md",
            check_id="security_version_row_missing",
            description=f"Add {pattern} to supported versions table",
            old_value="(missing)",
            new_value=pattern,
        )
        if apply:
            m = _SECURITY_TABLE_HEADER_RE.search(text)
            if m:
                new_row = f"| {pattern}  | :white_check_mark: |\n"
                text = text[: m.end()] + new_row + text[m.end() :]
                fix.applied = True
        fixes.append(fix)

    # Fix 2: Update "Current release line: **vX.Y.Z**."
    for m in _SECURITY_RELEASE_LINE_RE.finditer(text):
        claimed = m.group(2).lstrip("v")
        if claimed == version:
            continue

        fix = VersionFix(
            file="SECURITY.md",
            check_id="security_release_line_mismatch",
            description=f"Current release line: v{claimed} → v{version}",
            old_value=claimed,
            new_value=version,
        )
        if apply:
            text = text[: m.start(2)] + f"v{version}" + text[m.end(2) :]
            fix.applied = True
        fixes.append(fix)

    if apply and any(f.applied for f in fixes):
        path.write_text(text, encoding="utf-8")

    return fixes


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git_add(files: list[str]) -> None:
    result = _git("add", *files)
    if result.returncode != 0:
        print(f"ERROR: git add failed: {result.stderr.strip()}", flush=True)
        sys.exit(1)


def _git_commit(message: str) -> None:
    # Configure identity if not already set (CI environments)
    name_result = _git("config", "user.name")
    if not name_result.stdout.strip():
        _git("config", "user.name", "github-actions[bot]")
        _git("config", "user.email", "github-actions[bot]@users.noreply.github.com")

    result = _git("commit", "-m", message)
    if result.returncode != 0:
        # Nothing to commit is acceptable (files were already staged + in sync)
        if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
            print("INFO: Nothing to commit (files already consistent).", flush=True)
            return
        print(f"ERROR: git commit failed: {result.stderr.strip()}", flush=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sync version references in llms.txt and SECURITY.md "
            "to match pyproject.toml."
        ),
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply repairs (default: check only, exit 1 on drift)",
    )
    parser.add_argument(
        "--git-add",
        action="store_true",
        help="Stage repaired files with `git add` (requires --fix)",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Create a chore commit with staged fixes (requires --fix --git-add)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON list of discrepancies to stdout",
    )
    args = parser.parse_args()

    version = _read_pyproject_version()

    all_fixes: list[VersionFix] = []
    all_fixes += _check_llms_txt(version, apply=args.fix)
    all_fixes += _check_security_md(version, apply=args.fix)

    # --- JSON output mode ---------------------------------------------------
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "file": f.file,
                        "check_id": f.check_id,
                        "description": f.description,
                        "old": f.old_value,
                        "new": f.new_value,
                        "applied": f.applied,
                    }
                    for f in all_fixes
                ],
                indent=2,
            )
        )
        # Exit 1 only if unfixed drift remains
        unfixed = [f for f in all_fixes if not f.applied]
        sys.exit(1 if unfixed else 0)

    # --- Human output mode --------------------------------------------------
    if not all_fixes:
        print(f"OK: All version refs consistent (v{version})", flush=True)
        sys.exit(0)

    if not args.fix:
        print(
            f"DRIFT: Version inconsistencies detected (canonical: {version}):",
            flush=True,
        )
        for f in all_fixes:
            print(f"  [{f.file}] {f.description}", flush=True)
        print(
            "\nRepair with:  python scripts/sync_version.py --fix [--git-add] [--commit]",
            flush=True,
        )
        sys.exit(1)

    # --fix was set — report what was repaired
    applied = [f for f in all_fixes if f.applied]
    failed = [f for f in all_fixes if not f.applied]

    if applied:
        print(f"FIXED: Synced {len(applied)} version ref(s) to v{version}:", flush=True)
        for f in applied:
            print(f"  [{f.file}] {f.description}", flush=True)

    if failed:
        print(
            f"WARN: {len(failed)} repair(s) could not be applied automatically:",
            flush=True,
        )
        for f in failed:
            print(f"  [{f.file}] {f.description}", flush=True)

    # --- Stage ---
    if args.git_add and applied:
        changed_files = list({f.file for f in applied})
        _git_add(changed_files)
        print(f"STAGED: {', '.join(sorted(changed_files))}", flush=True)

        # --- Commit ---
        if args.commit:
            msg = f"chore: sync version refs to v{version}"
            _git_commit(msg)
            print(f"COMMITTED: '{msg}'", flush=True)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
