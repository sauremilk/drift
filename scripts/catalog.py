#!/usr/bin/env python3
"""List script files with short descriptions.

Examples:
    python scripts/catalog.py
    python scripts/catalog.py --search evidence
    python scripts/catalog.py --json
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def _extract_summary(path: Path) -> str:
    """Return the first non-empty line of module docstring, or fallback text."""
    try:
        source = path.read_text(encoding="utf-8")
        module = ast.parse(source)
        docstring = ast.get_docstring(module)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return "No readable module docstring"

    if not docstring:
        return "No module docstring"

    for line in docstring.splitlines():
        text = line.strip()
        if text:
            return text
    return "No module docstring"


def _iter_scripts() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        if path.name.startswith("__"):
            continue
        entries.append({"script": path.name, "summary": _extract_summary(path)})
    return entries


def _print_table(entries: list[dict[str, str]]) -> None:
    if not entries:
        print("No scripts found.")
        return

    name_width = max(len(item["script"]) for item in entries)
    name_width = max(name_width, len("Script"))

    print(f"{'Script'.ljust(name_width)}  Summary")
    print(f"{'-' * name_width}  {'-' * 60}")
    for item in entries:
        print(f"{item['script'].ljust(name_width)}  {item['summary']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="List scripts with short descriptions.")
    parser.add_argument(
        "--search",
        default="",
        help="Case-insensitive substring filter over script name and summary.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of table format.",
    )
    args = parser.parse_args()

    entries = _iter_scripts()
    if args.search:
        needle = args.search.lower()
        entries = [
            item
            for item in entries
            if needle in item["script"].lower() or needle in item["summary"].lower()
        ]

    if args.json:
        print(json.dumps(entries, indent=2, ensure_ascii=True))
    else:
        _print_table(entries)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
