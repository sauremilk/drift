#!/usr/bin/env python3
"""Render a compact task card for agent task-start.

Wraps existing gate + audit scripts and prints a structured work card with
empty scope slots the agent must fill in before editing code. Pure stdlib,
no side effects on the repository.

Usage:
    python scripts/task_card.py --task "<kurzbeschreibung>" --type feat
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

VALID_TYPES = ("feat", "fix", "chore", "signal", "prompt", "review")

GATES_BY_TYPE: dict[str, tuple[str, ...]] = {
    "feat": ("2 (Feature-Evidence)", "3 (Changelog)", "6 (Docstring)", "8 (CI)"),
    "fix": ("3 (Changelog)", "6 (Docstring, bedingt)", "8 (CI)"),
    "chore": ("4/5 (Version/Lockfile, bedingt)", "8 (CI)"),
    "signal": ("2", "3", "7 (Risk-Audit)", "8"),
    "prompt": ("Policy-Gate", "8 (CI)"),
    "review": ("Quality-Workflow", "8 (CI)"),
}

ROUTING_BY_TYPE: dict[str, tuple[str, ...]] = {
    "feat": (
        ".github/instructions/drift-policy.instructions.md",
        ".github/instructions/drift-push-gates.instructions.md",
        ".github/skills/drift-commit-push/SKILL.md",
    ),
    "fix": (
        ".github/instructions/drift-policy.instructions.md",
        ".github/instructions/drift-push-gates.instructions.md",
    ),
    "chore": (".github/instructions/drift-push-gates.instructions.md",),
    "signal": (
        ".github/skills/drift-signal-development-full-lifecycle/SKILL.md",
        ".github/skills/drift-risk-audit-artifact-updates/SKILL.md",
        ".github/skills/drift-adr-workflow/SKILL.md",
    ),
    "prompt": (
        ".github/instructions/drift-prompt-engineering.instructions.md",
        ".github/skills/drift-agent-prompt-authoring/SKILL.md",
    ),
    "review": (
        ".github/instructions/drift-quality-workflow.instructions.md",
        ".github/prompts/_partials/review-checkliste.md",
    ),
}


def _run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"(subprocess error: {exc})"
    if result.returncode != 0 and not result.stdout.strip():
        return f"(exit {result.returncode}) {result.stderr.strip()}"
    return result.stdout.strip() or "(empty)"


def _gate_check_output(commit_type: str) -> str:
    mapped = commit_type if commit_type in ("feat", "fix", "chore") else "chore"
    return _run([sys.executable, "scripts/gate_check.py", "--commit-type", mapped])


def _audit_diff_output() -> str:
    return _run([sys.executable, "scripts/risk_audit_diff.py"])


def build_card(task: str, task_type: str) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"  Task Card  —  Type: {task_type}")
    lines.append("=" * 72)
    lines.append(f"Task: {task}")
    lines.append("")
    lines.append("Aktive Gates:")
    for gate in GATES_BY_TYPE.get(task_type, ("8 (CI)",)):
        lines.append(f"  - {gate}")
    lines.append("")
    lines.append("Relevante Instructions / Skills:")
    for path in ROUTING_BY_TYPE.get(task_type, ()):
        lines.append(f"  - {path}")
    lines.append("")
    lines.append("Scope (vor dem ersten Edit auszufuellen):")
    lines.append("  Ziel:            <ein Satz>")
    lines.append("  In-Scope:        <konkrete Dateien / Bereiche>")
    lines.append("  Out-of-Scope:    <was ausdruecklich nicht beruehrt wird>")
    lines.append("  Erfolgskriterien:<messbares Abschlusssignal>")
    lines.append("")
    lines.append("PFLICHT: Offene Unsicherheiten (mindestens 1, sonst Scope zu schmal):")
    lines.append("  1. <offene Frage oder Annahme>")
    lines.append("")
    lines.append("-" * 72)
    lines.append("Gate Check (proaktiv):")
    lines.append("-" * 72)
    lines.append(_gate_check_output(task_type))
    lines.append("")
    lines.append("-" * 72)
    lines.append("Risk-Audit-Diff (Policy #18):")
    lines.append("-" * 72)
    lines.append(_audit_diff_output())
    lines.append("=" * 72)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a compact task card before editing code."
    )
    parser.add_argument("--task", required=True, help="Short task description.")
    parser.add_argument(
        "--type",
        dest="task_type",
        required=True,
        choices=VALID_TYPES,
        help="Task type selects active gates and routing references.",
    )
    args = parser.parse_args()

    print(build_card(args.task, args.task_type))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
