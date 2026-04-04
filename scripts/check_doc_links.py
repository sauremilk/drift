#!/usr/bin/env python3
"""Check internal markdown links across documentation files.

Scans all .md files in docs/, docs-site/, and root for broken internal
links (relative paths and anchor references).  External URLs (http/https)
are skipped — they are too fragile for deterministic CI.

Output: JSON array of discrepancy objects (same schema as
check_model_consistency.py --json).

Exit 0 = no broken links.
Exit 1 = broken links found.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_LINK_RE = re.compile(
    r"\[(?P<text>[^\]]*)\]\((?P<target>[^)]+)\)",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _collect_md_files(root: Path) -> list[Path]:
    """Collect markdown files from documentation directories and root."""
    files: list[Path] = []
    # Root-level markdown
    for p in root.glob("*.md"):
        files.append(p)
    # docs/ and docs-site/ recursively
    for subdir in ("docs", "docs-site"):
        d = root / subdir
        if d.is_dir():
            files.extend(d.rglob("*.md"))
    return sorted(set(files))


def _check_links(root: Path, md_files: list[Path]) -> list[dict[str, Any]]:
    """Check all internal markdown links for broken targets."""
    discs: list[dict[str, Any]] = []

    for md_file in md_files:
        try:
            text = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        rel_file = str(md_file.relative_to(root)).replace("\\", "/")

        for line_no, line in enumerate(text.splitlines(), start=1):
            for m in _LINK_RE.finditer(line):
                target = m.group("target").strip()

                # Skip external URLs
                if target.startswith(("http://", "https://", "mailto:")):
                    continue

                # Skip pure anchors within same file
                if target.startswith("#"):
                    continue

                # Split off anchor from path
                path_part = target.split("#")[0]
                if not path_part:
                    continue

                # Resolve relative to the markdown file's directory
                resolved = (md_file.parent / path_part).resolve()

                if not resolved.exists():
                    # Use relative path in description (not absolute)
                    rel_target = str(
                        resolved.relative_to(root)
                    ).replace("\\", "/") if str(resolved).startswith(
                        str(root)
                    ) else str(resolved)
                    discs.append(
                        {
                            "check_id": "broken_internal_link",
                            "category": "dead_link",
                            "severity": "low",
                            "source_file": rel_file,
                            "source_line": line_no,
                            "expected": path_part,
                            "actual": "(file not found)",
                            "description": (
                                f"{rel_file}:{line_no}: link to "
                                f"'{path_part}' target "
                                f"{rel_target} does not exist"
                            ),
                            "fix_suggestion": (
                                f"Fix or remove the link to '{path_part}' "
                                f"in {rel_file} line {line_no}"
                            ),
                        }
                    )

    return discs


def main() -> int:
    root = _repo_root()
    md_files = _collect_md_files(root)
    discs = _check_links(root, md_files)

    print(json.dumps(discs, indent=2))
    return 1 if discs else 0


if __name__ == "__main__":
    sys.exit(main())
