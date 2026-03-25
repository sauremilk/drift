#!/usr/bin/env python3
"""Fail CI when blocked files are tracked in git.

This script reads a simple glob-based blocklist and checks all tracked files.
It is intended as a server-side guardrail that cannot be bypassed with
local --no-verify pushes.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path


def load_patterns(config_path: Path) -> list[str]:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check tracked files against blocklist")
    parser.add_argument(
        "--config",
        default=".github/repo-guard.blocklist",
        help="Path to blocklist config (default: .github/repo-guard.blocklist)",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f">>> [repo-guard] ERROR: Config not found: {config_path}", file=sys.stderr)
        return 2

    patterns = load_patterns(config_path)
    if not patterns:
        print(
            f">>> [repo-guard] ERROR: No patterns configured in {config_path}",
            file=sys.stderr,
        )
        return 2

    files = git_tracked_files()
    violations = find_violations(files, patterns)

    if violations:
        print(">>> [repo-guard] ERROR: Blocked tracked files detected:")
        for file_path, pattern in violations:
            print(f" - {file_path}  (matched: {pattern})")
        print(">>> [repo-guard] Remove these files from git history or rename/move them.")
        return 1

    print(">>> [repo-guard] OK: No blocked tracked files detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())