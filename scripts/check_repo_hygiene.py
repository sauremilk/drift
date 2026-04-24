#!/usr/bin/env python3
"""Fail CI when public-repo hygiene rules are violated.

This script enforces two repository-level guardrails:

1. A glob-based blocklist for sensitive or local-only tracked files.
2. A root-entry allowlist that keeps the repository root intentionally small.

It is intended as a server-side guardrail that cannot be bypassed with
local --no-verify pushes.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path


def load_entries(config_path: Path) -> list[str]:
    patterns: list[str] = []
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def git_tracked_files() -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print(
            ">>> [repo-guard] ERROR: Could not list tracked files via git ls-files",
            file=sys.stderr,
        )
        if proc.stderr:
            print(proc.stderr.strip(), file=sys.stderr)
        sys.exit(2)

    files: list[str] = []
    for line in proc.stdout.splitlines():
        path = line.strip().replace("\\", "/")
        if path:
            files.append(path)
    return files


def find_violations(files: list[str], patterns: list[str]) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for file_path in files:
        for pattern in patterns:
            if fnmatch(file_path, pattern):
                violations.append((file_path, pattern))
                break
    return violations


def tracked_root_entries(files: list[str]) -> list[str]:
    return sorted({file_path.split("/", 1)[0] for file_path in files if file_path})


def find_root_violations(
    root_entries: list[str], allowlist_patterns: list[str]
) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for entry in root_entries:
        matched_pattern = next(
            (pattern for pattern in allowlist_patterns if fnmatch(entry, pattern)),
            None,
        )
        if matched_pattern is None:
            violations.append((entry, "<no allowlist match>"))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check tracked files against repo hygiene rules")
    parser.add_argument(
        "--config",
        default=".github/repo-guard.blocklist",
        help="Path to blocklist config (default: .github/repo-guard.blocklist)",
    )
    parser.add_argument(
        "--root-allowlist",
        default=".github/repo-root-allowlist",
        help="Path to root-entry allowlist (default: .github/repo-root-allowlist)",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f">>> [repo-guard] ERROR: Config not found: {config_path}", file=sys.stderr)
        return 2

    root_allowlist_path = Path(args.root_allowlist)
    if not root_allowlist_path.exists():
        print(
            f">>> [repo-guard] ERROR: Root allowlist not found: {root_allowlist_path}",
            file=sys.stderr,
        )
        return 2

    patterns = load_entries(config_path)
    if not patterns:
        print(
            f">>> [repo-guard] ERROR: No patterns configured in {config_path}",
            file=sys.stderr,
        )
        return 2

    root_allowlist = load_entries(root_allowlist_path)
    if not root_allowlist:
        print(
            f">>> [repo-guard] ERROR: No root entries configured in {root_allowlist_path}",
            file=sys.stderr,
        )
        return 2

    files = git_tracked_files()
    violations = find_violations(files, patterns)
    root_violations = find_root_violations(tracked_root_entries(files), root_allowlist)

    if violations:
        print(">>> [repo-guard] ERROR: Blocked tracked files detected:")
        for file_path, pattern in violations:
            print(f" - {file_path}  (matched: {pattern})")
        print(">>> [repo-guard] Remove these files from git history or rename/move them.")
        return 1

    if root_violations:
        print(">>> [repo-guard] ERROR: Unexpected tracked root entries detected:")
        for entry, pattern in root_violations:
            print(f" - {entry}  (matched: {pattern})")
        print(
            ">>> [repo-guard] Move the entry into the appropriate "
            "subdirectory or update the allowlist with rationale."
        )
        return 1

    print(">>> [repo-guard] OK: Blocklist and root-allowlist checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
