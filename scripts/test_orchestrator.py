#!/usr/bin/env python3
"""Risk-based test orchestrator.

Maps `git diff --name-only` output to an appropriate pytest invocation
from the existing Makefile tiers. Does NOT replace `make check` — that
remains mandatory before push. This script is an inner-loop accelerator
only.

Mapping (first match wins, top-down):
    src/drift/signals/     -> test-dev + tests/test_precision_recall.py
    src/drift/output/      -> test-contract + test-dev
    src/drift/ingestion/   -> test-dev
    src/drift/             -> test-fast
    tests/                 -> test-fast
    scripts/               -> test-fast
    docs/, *.md only       -> skip (info only)

Usage:
    python scripts/test_orchestrator.py              # auto-detect and run
    python scripts/test_orchestrator.py --dry-run    # print plan only
    python scripts/test_orchestrator.py --full       # force `make check`
    python scripts/test_orchestrator.py --base main  # diff base override
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Tier -> pytest argv (Python-side, no make dependency).
TIER_COMMANDS: dict[str, list[str]] = {
    "skip": [],
    "test-fast": [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "-m",
        "not slow",
        "--ignore=tests/test_smoke_real_repos.py",
        "-n",
        "auto",
        "--dist=loadscope",
    ],
    "test-dev": [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "-m",
        "not slow and not performance and not ground_truth",
        "--ignore=tests/test_smoke_real_repos.py",
        "-n",
        "auto",
        "--dist=loadscope",
    ],
    "test-contract": [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "--tb=short",
        "-m",
        "contract",
    ],
    "precision-recall": [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_precision_recall.py",
        "-v",
        "--tb=short",
    ],
    "full-check": [sys.executable, "-m", "pytest", "-q", "--tb=short", "--run-slow"],
}


def classify_paths(paths: list[str]) -> list[str]:
    """Return the ordered list of test tiers for a set of changed paths.

    Order matters: test-contract before test-dev before test-fast so the
    most targeted checks run first.
    """
    if not paths:
        return ["test-fast"]

    only_docs = all(
        p.startswith("docs/") or p.endswith(".md") or p.endswith(".txt")
        for p in paths
    )
    if only_docs:
        return ["skip"]

    tiers: list[str] = []

    def add(tier: str) -> None:
        if tier not in tiers:
            tiers.append(tier)

    for path in paths:
        if path.startswith("src/drift/signals/"):
            add("test-dev")
            add("precision-recall")
        elif path.startswith("src/drift/output/"):
            add("test-contract")
            add("test-dev")
        elif path.startswith("src/drift/ingestion/"):
            add("test-dev")
        elif (
            path.startswith("src/drift/")
            or path.startswith("tests/")
            or path.startswith("scripts/")
        ):
            add("test-fast")
        else:
            add("test-fast")

    return tiers


def _git_changed_files(base: str | None) -> list[str]:
    if base:
        args = ["git", "diff", "--name-only", f"{base}...HEAD"]
    else:
        args = ["git", "diff", "--name-only", "HEAD"]

    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    # Also include staged + untracked so a fresh session isn't empty.
    for extra in (
        ["git", "diff", "--name-only", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        extra_result = subprocess.run(
            extra,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        for line in extra_result.stdout.splitlines():
            p = line.strip()
            if p and p not in files:
                files.append(p)

    return files


def _run_command(cmd: list[str]) -> int:
    print(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=REPO_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Risk-based test orchestrator.")
    parser.add_argument("--base", default=None, help="Diff base (e.g. origin/main).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned tier sequence and commands without executing.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force the full-check tier (equivalent of `make check` pytest layer).",
    )
    args = parser.parse_args()

    if args.full:
        tiers = ["full-check"]
        paths: list[str] = []
    else:
        paths = _git_changed_files(args.base)
        tiers = classify_paths(paths)

    print("Changed files:", len(paths))
    for path in paths[:20]:
        print(f"  - {path}")
    if len(paths) > 20:
        print(f"  ... and {len(paths) - 20} more")
    print("Selected tiers:", tiers)

    if tiers == ["skip"]:
        print("docs-only diff — no tests required (run `make check` before push).")
        return 0

    if args.dry_run:
        for tier in tiers:
            cmd = TIER_COMMANDS[tier]
            print(f"# {tier}: {' '.join(cmd)}")
        return 0

    for tier in tiers:
        cmd = TIER_COMMANDS[tier]
        rc = _run_command(cmd)
        if rc != 0:
            print(f"Tier {tier!r} failed with exit code {rc}. Stopping.")
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
