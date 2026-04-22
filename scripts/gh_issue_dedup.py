#!/usr/bin/env python3
"""Paket 2C / ADR-095 — opt-in BLOCK-finding issue filing with dedup.

Reads a drift JSON report, filters findings with severity ``critical`` or
``high`` (BLOCK-band), and for each finding either opens a new GitHub
issue or skips if an open issue already embeds the same ``finding_id``
marker.

Behaviour is strictly opt-in: the caller must pass ``--repo``. The
underlying ``gh`` CLI MUST already be authenticated; this script does
NOT shell out to the GitHub API without credentials.

Exit codes
----------
0  OK — all BLOCK findings have an open issue (existing or newly filed).
1  One or more ``gh`` invocations failed.
2  Usage / input error (missing report, malformed JSON, missing gh).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BLOCK_SEVERITIES = {"critical", "high"}
FINDING_MARKER_PREFIX = "drift-finding-id:"
DEFAULT_LABELS = "drift,agent-block"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _marker(finding_id: str) -> str:
    """Return the machine-readable marker that identifies the finding in
    the issue body. Dedup scans existing open issues for this marker."""
    return f"<!-- {FINDING_MARKER_PREFIX} {finding_id} -->"


def _iter_block_findings(report: dict) -> Iterable[dict]:
    for f in report.get("findings") or []:
        sev = str((f or {}).get("severity", "")).lower()
        if sev in BLOCK_SEVERITIES:
            yield f


def _finding_id(f: dict) -> str:
    # drift attaches a stable id; fall back to fingerprint if available.
    for key in ("id", "finding_id", "fingerprint"):
        val = f.get(key)
        if val:
            return str(val)
    # Deterministic fallback (signal+file+line).
    sig = f.get("signal_type") or f.get("signal") or "unknown"
    loc = f.get("location") or {}
    fp = loc.get("file_path") or loc.get("file") or "unknown"
    ln = loc.get("line") or loc.get("start_line") or 0
    return f"{sig}:{fp}:{ln}"


def _issue_title(f: dict) -> str:
    title = f.get("title") or f.get("message") or "Drift BLOCK finding"
    return f"[drift] {title}"[:240]


def _issue_body(f: dict, finding_id: str) -> str:
    severity = f.get("severity", "unknown")
    signal = f.get("signal_type") or f.get("signal") or "unknown"
    loc = f.get("location") or {}
    file_path = loc.get("file_path") or loc.get("file") or "?"
    line = loc.get("line") or loc.get("start_line") or "?"
    rationale = f.get("rationale") or f.get("description") or ""
    return (
        f"{_marker(finding_id)}\n\n"
        f"**Signal:** `{signal}`\n"
        f"**Severity:** `{severity}`\n"
        f"**Location:** `{file_path}:{line}`\n\n"
        f"{rationale}\n\n"
        f"_Auto-filed by drift action (Paket 2C, ADR-095). "
        f"This issue will not be re-opened if closed manually._"
    )


def _run_gh(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(  # noqa: S603 — gh CLI invocation with explicit args
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def _existing_open_issues(repo: str, labels: str) -> list[dict]:
    """Return deduplicated open issues carrying at least one of the labels.

    Scans *every* label in the comma-separated list so a renamed primary
    label does not break dedup (Paket 2C+ automation hardening).
    """
    seen: dict[int, dict] = {}
    for raw_label in (s.strip() for s in labels.split(",") if s.strip()):
        rc, out = _run_gh(
            [
                "issue", "list",
                "--repo", repo,
                "--state", "open",
                "--label", raw_label,
                "--limit", "200",
                "--json", "number,title,body",
            ]
        )
        if rc != 0:
            print(
                f"::warning::gh issue list failed for label '{raw_label}': {out}",
                file=sys.stderr,
            )
            continue
        try:
            for issue in json.loads(out or "[]"):
                num = issue.get("number")
                if isinstance(num, int):
                    seen[num] = issue
        except json.JSONDecodeError:
            continue
    return list(seen.values())


def _is_duplicate(finding_id: str, issues: list[dict]) -> bool:
    m = _marker(finding_id)
    return any(m in (i.get("body") or "") for i in issues)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, help="owner/repo to file issues in.")
    ap.add_argument("--report", required=True, help="Path to drift JSON report.")
    ap.add_argument("--labels", default=DEFAULT_LABELS, help="Comma-separated labels.")
    ap.add_argument(
        "--max-issues",
        type=int,
        default=10,
        help=(
            "Flood guard: refuse to file more than N issues in a single run. "
            "New findings beyond the cap are skipped with a warning, the "
            "script still exits 0 to keep CI productive (Paket 2C+)."
        ),
    )
    ap.add_argument("--dry-run", action="store_true", help="Do not call gh.")
    args = ap.parse_args(argv)

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"::warning::report file not found: {report_path}", file=sys.stderr)
        return 0  # no report = no findings; treat as clean

    if not shutil.which("gh") and not args.dry_run:
        print("::error::gh CLI is required but not on PATH.", file=sys.stderr)
        return 2

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"::error::malformed JSON: {exc}", file=sys.stderr)
        return 2

    findings = list(_iter_block_findings(report))
    if not findings:
        print("no BLOCK-severity findings — nothing to file.")
        return 0

    open_issues = [] if args.dry_run else _existing_open_issues(args.repo, args.labels)
    filed, skipped, failed, capped = 0, 0, 0, 0

    for f in findings:
        fid = _finding_id(f)
        if _is_duplicate(fid, open_issues):
            skipped += 1
            print(f"skip (dup): {fid}")
            continue

        if args.max_issues is not None and filed >= args.max_issues:
            capped += 1
            print(f"::warning::flood guard: --max-issues {args.max_issues} reached; skipping {fid}")
            continue

        title = _issue_title(f)
        body = _issue_body(f, fid)

        if args.dry_run:
            filed += 1
            print(f"[dry-run] would file: {title}")
            continue

        rc, out = _run_gh(
            [
                "issue", "create",
                "--repo", args.repo,
                "--title", title,
                "--body", body,
                "--label", args.labels,
            ]
        )
        if rc == 0:
            filed += 1
            print(f"filed: {title}")
        else:
            failed += 1
            print(f"::warning::gh issue create failed for {fid}: {out}", file=sys.stderr)

    print(f"summary: filed={filed} skipped={skipped} capped={capped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
