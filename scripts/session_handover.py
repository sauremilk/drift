#!/usr/bin/env python3
"""Generate a lightweight session handover artifact.

The script collects a small local snapshot (diff stat, latest commit subject,
and proactive gate status) and writes a handover markdown file to work_artifacts/.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def make_session_id(raw_session_id: str | None) -> str:
    if raw_session_id:
        return raw_session_id[:8]
    return uuid.uuid4().hex[:8]


def _run_command(cmd: list[str]) -> str:
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _latest_commit_subject() -> str:
    return _run_command(["git", "log", "-1", "--pretty=%s"]) or "(no commit subject)"


def _diff_stat() -> str:
    output = _run_command(["git", "diff", "--stat", "HEAD"])
    return output or "(no working tree changes detected)"


def _gate_output() -> str:
    output = _run_command(["python", "scripts/gate_check.py", "--commit-type", "chore"])
    return output or "(gate_check unavailable)"


def build_handover_markdown(
    *,
    task: str,
    session_id: str,
    diff_stat: str,
    gate_output: str,
    latest_commit_subject: str,
) -> str:
    now = dt.datetime.now(dt.UTC).replace(microsecond=0)
    now_iso = now.isoformat().replace("+00:00", "Z")

    return (
        "---\n"
        f'session_id: "{session_id}"\n'
        f'started_at: "{now_iso}"\n'
        f'ended_at: "{now_iso}"\n'
        "duration_seconds: 0\n"
        "tool_calls: 0\n"
        "tasks_completed: 0\n"
        "tasks_remaining: 0\n"
        "findings_delta: 0\n"
        'change_class: "chore"\n'
        f'repo_path: "{REPO_ROOT.as_posix()}"\n'
        'git_head_at_plan: "unknown"\n'
        'git_head_at_end: "unknown"\n'
        "adr_refs: []\n"
        "evidence_files: []\n"
        "audit_artifacts_updated: []\n"
        "---\n\n"
        "## Scope\n\n"
        f"{task}\n\n"
        "## Was wurde geaendert\n\n"
        "```\n"
        f"{diff_stat}\n"
        "```\n\n"
        "## Offene Gates\n\n"
        "```\n"
        f"{gate_output}\n"
        "```\n\n"
        "## Naechster Schritt\n\n"
        "Pruefe die offenen Gate-Punkte und setze auf dem letzten Commit auf:"
        f" {latest_commit_subject}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a session handover markdown artifact.")
    parser.add_argument("--task", required=True, help="Short description of the current task.")
    parser.add_argument(
        "--session-id",
        default="",
        help="Optional session identifier (first 8 chars are used).",
    )
    args = parser.parse_args()

    sid = make_session_id(args.session_id or None)
    content = build_handover_markdown(
        task=args.task,
        session_id=sid,
        diff_stat=_diff_stat(),
        gate_output=_gate_output(),
        latest_commit_subject=_latest_commit_subject(),
    )

    output_dir = REPO_ROOT / "work_artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"session_{sid}.md"
    output_path.write_text(content, encoding="utf-8")

    print(str(output_path.relative_to(REPO_ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
