#!/usr/bin/env python3
"""Generate a formatted CHANGELOG entry snippet.

The script prints an entry to stdout and never edits CHANGELOG.md directly.
"""

from __future__ import annotations

import argparse
import datetime as dt
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def read_pyproject_version() -> str:
    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        data = tomllib.load(fh)
    return str(data["project"]["version"])


def build_entry(*, commit_type: str, message: str, version: str) -> str:
    section_map = {
        "feat": "Added",
        "fix": "Fixed",
        "chore": "Changed",
    }
    section = section_map[commit_type]
    date_str = dt.date.today().isoformat()
    return (
        f"## [{version}] - {date_str}\n\n"
        f"### {section}\n"
        f"- {message}\n\n"
        "<!-- Manually merge this snippet into CHANGELOG.md -->\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a CHANGELOG entry snippet.")
    parser.add_argument("--commit-type", choices=["feat", "fix", "chore"], required=True)
    parser.add_argument("--message", required=True, help="Single-line changelog bullet.")
    parser.add_argument("--version", default="", help="Optional version override.")
    args = parser.parse_args()

    version = args.version or read_pyproject_version()
    print(build_entry(commit_type=args.commit_type, message=args.message, version=version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
