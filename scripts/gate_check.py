#!/usr/bin/env python3
"""Proactive pre-push gate status check.

This script mirrors the most important pre-push gates in a lightweight
"check before push" workflow.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_PATTERN = re.compile(r"^benchmark_results/v\d+\.\d+\.\d+.*_feature_evidence\.json$")
PUBLIC_DEF_PATTERN = re.compile(r"^\+def [a-z][a-zA-Z0-9_]*\(")
ADDED_DOCSTRING_PATTERN = re.compile(r"^\+[ \t]*(?:\"\"\"|''')")


class GateResult(NamedTuple):
    gate: int
    active: bool
    status: str
    reason: str


def _git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _detect_commit_type() -> str:
    message = " ".join(_git_lines("log", "-1", "--pretty=%s"))
    lowered = message.lower()
    if lowered.startswith("feat"):
        return "feat"
    if lowered.startswith("fix"):
        return "fix"
    return "chore"


def collect_changed_files() -> set[str]:
    changed: set[str] = set()
    changed.update(_git_lines("diff", "--name-only", "HEAD"))
    changed.update(_git_lines("diff", "--name-only", "--cached"))
    changed.update(_git_lines("ls-files", "--others", "--exclude-standard"))
    return changed


def _load_last_success_sha() -> str | None:
    path = REPO_ROOT / ".git" / ".drift-prepush-last-success"
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def check_public_api_docstrings_diff(diff_text: str) -> tuple[bool, list[str]]:
    current_file = ""
    has_public: set[str] = set()
    has_doc: set[str] = set()

    for line in diff_text.splitlines():
        if line.startswith("+++ b/src/drift/"):
            current_file = line[6:]
            continue
        if not current_file:
            continue
        if PUBLIC_DEF_PATTERN.match(line):
            has_public.add(current_file)
            continue
        if ADDED_DOCSTRING_PATTERN.match(line):
            has_doc.add(current_file)

    missing = sorted(path for path in has_public if path not in has_doc)
    return not missing, missing


def _compute_gate6_ok(changed_files: set[str]) -> tuple[bool, str]:
    if not any(path.startswith("src/drift/") for path in changed_files):
        return True, "Gate not active (no src/drift changes)"

    diff_output = subprocess.run(
        ["git", "diff", "--", "src/drift/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if diff_output.returncode != 0:
        return False, "Unable to read src/drift diff"

    ok, missing = check_public_api_docstrings_diff(diff_output.stdout)
    if ok:
        return True, "Public API docstring check passed"
    return False, f"Missing added docstring for files: {', '.join(missing)}"


def evaluate_gates(
    changed_files: set[str],
    commit_type: str,
    *,
    gate6_ok: bool,
    gate6_reason: str = "",
    head_sha: str | None,
    last_success_sha: str | None,
) -> list[GateResult]:
    results: list[GateResult] = []

    gate2_active = commit_type == "feat"
    if gate2_active:
        has_tests = any(path.startswith("tests/") for path in changed_files)
        has_empirical = any(
            path.startswith("benchmark_results/") or path.startswith("audit_results/")
            for path in changed_files
        )
        has_versioned_evidence = any(EVIDENCE_PATTERN.match(path) for path in changed_files)
        has_study = "docs/STUDY.md" in changed_files
        if has_tests and has_empirical and has_versioned_evidence and has_study:
            results.append(GateResult(2, True, "OK", "Feature evidence gate satisfied"))
        else:
            missing_bits: list[str] = []
            if not has_tests:
                missing_bits.append("tests/**")
            if not has_empirical:
                missing_bits.append("benchmark_results/** or audit_results/**")
            if not has_versioned_evidence:
                missing_bits.append("benchmark_results/vX.Y.Z_*_feature_evidence.json")
            if not has_study:
                missing_bits.append("docs/STUDY.md")
            results.append(
                GateResult(2, True, "MISSING", f"Missing: {', '.join(missing_bits)}")
            )
    else:
        results.append(GateResult(2, False, "NOT_YET", "Not active for this commit type"))

    gate3_active = commit_type in {"feat", "fix"}
    if gate3_active:
        if "CHANGELOG.md" in changed_files:
            results.append(GateResult(3, True, "OK", "CHANGELOG.md updated"))
        else:
            results.append(
                GateResult(3, True, "MISSING", "feat/fix detected without CHANGELOG.md")
            )
    else:
        results.append(GateResult(3, False, "NOT_YET", "Not active for this commit type"))

    gate6_active = any(path.startswith("src/drift/") for path in changed_files)
    if gate6_active:
        status = "OK" if gate6_ok else "MISSING"
        reason = gate6_reason or "Public API docstring check"
        results.append(GateResult(6, True, status, reason))
    else:
        results.append(GateResult(6, False, "NOT_YET", "No src/drift changes"))

    gate7_active = any(
        path.startswith("src/drift/signals/")
        or path.startswith("src/drift/ingestion/")
        or path.startswith("src/drift/output/")
        for path in changed_files
    )
    if gate7_active:
        has_audit_update = any(
            path
            in {
                "audit_results/fmea_matrix.md",
                "audit_results/stride_threat_model.md",
                "audit_results/fault_trees.md",
                "audit_results/risk_register.md",
            }
            for path in changed_files
        )
        if has_audit_update:
            results.append(GateResult(7, True, "OK", "Audit artifact update present"))
        else:
            results.append(
                GateResult(7, True, "MISSING", "Signal-related changes without audit update")
            )
    else:
        results.append(GateResult(7, False, "NOT_YET", "No signal/ingestion/output changes"))

    if head_sha and last_success_sha and head_sha == last_success_sha:
        results.append(GateResult(8, True, "OK", "Local CI cache is fresh for current HEAD"))
    elif head_sha and last_success_sha:
        results.append(
            GateResult(8, True, "MISSING", "Local CI cache is stale, run make check")
        )
    else:
        results.append(
            GateResult(8, True, "NOT_YET", "No CI cache marker, run make check")
        )

    return results


def _print_results(results: list[GateResult]) -> None:
    print("Gate status:")
    for result in results:
        active = "active" if result.active else "inactive"
        print(f"- [Gate {result.gate}] {result.status:<8} ({active}) - {result.reason}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Show proactive gate status before commit/push.")
    parser.add_argument(
        "--commit-type",
        choices=["feat", "fix", "chore", "signal"],
        help="Commit type to evaluate. Default: infer from latest commit subject.",
    )
    args = parser.parse_args()

    commit_type = args.commit_type or _detect_commit_type()
    changed_files = collect_changed_files()

    gate6_ok, gate6_reason = _compute_gate6_ok(changed_files)
    head_sha_lines = _git_lines("rev-parse", "HEAD")
    head_sha = head_sha_lines[0] if head_sha_lines else None
    last_success_sha = _load_last_success_sha()

    results = evaluate_gates(
        changed_files,
        commit_type,
        gate6_ok=gate6_ok,
        gate6_reason=gate6_reason,
        head_sha=head_sha,
        last_success_sha=last_success_sha,
    )
    _print_results(results)

    has_missing = any(result.status == "MISSING" for result in results if result.active)
    return 1 if has_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
