#!/usr/bin/env python3
"""Orchestrate doc-consistency issue creation on GitHub.

Reads structured discrepancy JSON from:
  - check_model_consistency.py --json
  - check_doc_links.py
  - drift analyze --select DIA --format json

Groups related discrepancies, deduplicates against existing open issues
with label ``doc-drift``, and creates new GitHub issues via ``gh`` CLI.

Usage:
    python scripts/doc_consistency_issues.py \\
        --consistency consistency.json \\
        --links links.json \\
        --dia dia.json \\
        --max-issues 5

    python scripts/doc_consistency_issues.py --dry-run ...
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

LABEL = "doc-drift"
MAX_ISSUES_DEFAULT = 5


# ---------------------------------------------------------------------------
# Input loaders
# ---------------------------------------------------------------------------


def _load_json(path: str | None) -> list[dict[str, Any]]:
    """Load a JSON file and return a list of records."""
    if path is None:
        return []
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return []


def _load_dia_findings(path: str | None) -> list[dict[str, Any]]:
    """Convert drift JSON output findings into the common discrepancy schema."""
    if path is None:
        return []
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))

    findings = data.get("findings", []) if isinstance(data, dict) else []
    discs: list[dict[str, Any]] = []
    for f in findings:
        if f.get("signal", "") != "DIA":
            continue
        discs.append(
            {
                "check_id": f"dia_{f.get('rule_id', 'unknown')}".lower(),
                "category": "dia_finding",
                "severity": f.get("severity", "low"),
                "source_file": f.get("file", ""),
                "description": f.get("title", ""),
                "expected": "",
                "actual": "",
                "fix_suggestion": f.get("fix", ""),
            }
        )
    return discs


# ---------------------------------------------------------------------------
# Grouping: cluster discrepancies by target file
# ---------------------------------------------------------------------------


def _group_discrepancies(
    discs: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group discrepancies by source_file for issue bundling."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for d in discs:
        key = d.get("source_file", "unknown")
        groups.setdefault(key, []).append(d)
    return groups


# ---------------------------------------------------------------------------
# Deduplication against existing GitHub issues
# ---------------------------------------------------------------------------


def _fetch_existing_issue_titles() -> set[str]:
    """Fetch titles of open issues with doc-drift label via gh CLI."""
    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--label",
                LABEL,
                "--state",
                "open",
                "--json",
                "title",
                "--limit",
                "100",
            ],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=30,
        )
        if result.returncode != 0:
            print(
                f"Warning: gh issue list failed: {result.stderr.strip()}",
                file=sys.stderr,
            )
            return set()
        issues = json.loads(result.stdout)
        return {i["title"].lower() for i in issues}
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        print(f"Warning: could not fetch existing issues: {e}", file=sys.stderr)
        return set()


def _make_title(source_file: str, category: str) -> str:
    """Generate a deterministic issue title for dedup matching."""
    return f"docs: {category} — {source_file}"


# ---------------------------------------------------------------------------
# Issue body rendering
# ---------------------------------------------------------------------------

_SEVERITY_EMOJI = {
    "high": "🔴",
    "medium": "🟠",
    "low": "🟡",
    "info": "⚪",
}


def _render_issue_body(
    source_file: str,
    discs: list[dict[str, Any]],
) -> str:
    """Render a markdown issue body from grouped discrepancies."""
    lines: list[str] = []
    lines.append(
        "This issue was automatically created by the "
        "**doc-consistency** workflow.\n"
    )
    lines.append(f"**File:** `{source_file}`\n")
    lines.append("## Discrepancies\n")

    for d in discs:
        sev = d.get("severity", "low")
        emoji = _SEVERITY_EMOJI.get(sev, "⚪")
        lines.append(f"### {emoji} {d.get('description', '(no description)')}\n")
        if d.get("expected") or d.get("actual"):
            lines.append(f"- **Expected:** `{d.get('expected', '—')}`")
            lines.append(f"- **Actual:** `{d.get('actual', '—')}`")
        if d.get("fix_suggestion"):
            lines.append(f"- **Fix:** {d['fix_suggestion']}")
        if d.get("source_line"):
            lines.append(f"- **Line:** {d['source_line']}")
        lines.append("")

    lines.append("---")
    lines.append(
        "*Label:* `doc-drift` · *Close this issue after fixing the "
        "documentation.*"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Issue creation
# ---------------------------------------------------------------------------


def _create_issue(title: str, body: str, extra_labels: list[str] | None = None) -> bool:
    """Create a GitHub issue via gh CLI.  Returns True on success."""
    cmd = [
        "gh",
        "issue",
        "create",
        "--title",
        title,
        "--body",
        body,
        "--label",
        LABEL,
    ]
    for label in extra_labels or []:
        cmd.extend(["--label", label])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )
    if result.returncode != 0:
        print(
            f"Error creating issue '{title}': {result.stderr.strip()}",
            file=sys.stderr,
        )
        return False
    url = result.stdout.strip()
    print(f"Created: {url}")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> dict[str, Any]:
    """Minimal argument parsing without external dependencies."""
    args: dict[str, Any] = {
        "consistency": None,
        "links": None,
        "dia": None,
        "max_issues": MAX_ISSUES_DEFAULT,
        "dry_run": False,
    }
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--consistency" and i + 1 < len(argv):
            args["consistency"] = argv[i + 1]
            i += 2
        elif argv[i] == "--links" and i + 1 < len(argv):
            args["links"] = argv[i + 1]
            i += 2
        elif argv[i] == "--dia" and i + 1 < len(argv):
            args["dia"] = argv[i + 1]
            i += 2
        elif argv[i] == "--max-issues" and i + 1 < len(argv):
            args["max_issues"] = int(argv[i + 1])
            i += 2
        elif argv[i] == "--dry-run":
            args["dry_run"] = True
            i += 1
        else:
            print(f"Unknown argument: {argv[i]}", file=sys.stderr)
            i += 1
    return args


def main() -> int:
    """Orchestrate doc-consistency issue creation."""
    args = _parse_args()

    # 1. Collect all discrepancies
    all_discs: list[dict[str, Any]] = []
    all_discs.extend(_load_json(args["consistency"]))
    all_discs.extend(_load_json(args["links"]))
    all_discs.extend(_load_dia_findings(args["dia"]))

    if not all_discs:
        print("No discrepancies found. Documentation is consistent.")
        return 0

    print(f"Found {len(all_discs)} discrepancy(ies) total.")

    # 2. Group by file
    groups = _group_discrepancies(all_discs)

    # 3. Deduplicate
    existing_titles = set() if args["dry_run"] else _fetch_existing_issue_titles()

    issues_to_create: list[tuple[str, str, list[str]]] = []
    for source_file, discs in sorted(groups.items()):
        # Use the most common category for the title
        categories = [d.get("category", "unknown") for d in discs]
        primary_category = max(set(categories), key=categories.count)
        title = _make_title(source_file, primary_category)

        if title.lower() in existing_titles:
            print(f"  Skip (exists): {title}")
            continue

        body = _render_issue_body(source_file, discs)

        # Add good-first-issue label if all findings are low/medium severity
        severities = {d.get("severity", "low") for d in discs}
        extra_labels: list[str] = []
        if severities <= {"low", "medium", "info"}:
            extra_labels.append("good first issue")

        issues_to_create.append((title, body, extra_labels))

    max_issues: int = args["max_issues"]
    to_create = issues_to_create[:max_issues]
    skipped = len(issues_to_create) - len(to_create)

    if not to_create:
        print("All discrepancies already have open issues.")
        return 0

    # 4. Create or dry-run
    created = 0
    for title, body, extra_labels in to_create:
        if args["dry_run"]:
            print(f"\n{'='*60}")
            print("[DRY-RUN] Would create issue:")
            print(f"  Title: {title}")
            print(f"  Labels: {LABEL}" + (
                f", {', '.join(extra_labels)}" if extra_labels else ""
            ))
            print(f"  Body length: {len(body)} chars")
            print(f"  Preview:\n{body[:300]}...")
            created += 1
        else:
            if _create_issue(title, body, extra_labels):
                created += 1

    print(f"\n{'='*60}")
    action = "Would create" if args["dry_run"] else "Created"
    print(f"{action} {created} issue(s).")
    if skipped:
        print(
            f"Skipped {skipped} issue(s) due to --max-issues {max_issues} "
            f"limit."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
