#!/usr/bin/env python3
"""H5 instrument: Adversarial Brief Audit — tests whether drift brief suggests harmful actions.

Runs drift brief on each adversarial fixture and checks if the output
contains the harmful_action pattern defined in the fixture manifest.

Usage:
    python scripts/adversarial_brief_audit.py
    python scripts/adversarial_brief_audit.py --dry-run

Outputs:
    benchmark_results/adversarial_brief_audit.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "benchmarks" / "gauntlet" / "scenarios" / "adversarial"
MANIFEST_FILE = FIXTURES_DIR / "manifest.json"
RESULTS_DIR = REPO_ROOT / "benchmark_results"


def _load_manifest() -> list[dict]:
    if not MANIFEST_FILE.exists():
        sys.exit(f"Manifest not found: {MANIFEST_FILE}")
    data = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    return data["fixtures"]


def _run_drift_brief(repo_path: Path, task: str = "") -> dict | None:
    """Run drift brief on a directory and return parsed JSON."""
    cmd = [
        sys.executable, "-m", "drift", "brief",
        "--repo", str(repo_path),
        "--format", "json",
    ]
    if task:
        cmd.extend(["--task", task])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )
        text = result.stdout
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        print(f"  brief failed: {exc}", file=sys.stderr)
    return None


def _check_harmful_action(brief_output: dict, harmful_pattern: str) -> bool:
    """Check if brief output contains a harmful action recommendation."""
    # Recursively search all string values in the brief output
    text = json.dumps(brief_output).lower()
    return harmful_pattern.lower() in text


def audit(dry_run: bool = False) -> None:
    """Run adversarial brief audit."""
    fixtures = _load_manifest()
    print(f"Adversarial Brief Audit (H5): {len(fixtures)} fixtures")

    results: list[dict] = []

    for fixture in fixtures:
        fid = fixture["id"]
        directory = fixture["directory"]
        harmful_action = fixture["harmful_action"]
        fixture_path = FIXTURES_DIR / directory

        print(f"\n[{fid}] {fixture['title']}")
        print(f"  Expected signal: {fixture['expected_signal']}")
        print(f"  Harmful action pattern: '{harmful_action}'")

        if not fixture_path.exists():
            print(f"  SKIP: directory not found: {fixture_path}")
            results.append({
                "fixture_id": fid,
                "status": "missing_directory",
                "harmful_constraint_present": None,
            })
            continue

        if dry_run:
            print(f"  DRY-RUN: would run drift brief on {fixture_path}")
            results.append({
                "fixture_id": fid,
                "status": "dry_run",
                "harmful_constraint_present": None,
            })
            continue

        task_desc = f"Review and fix {fixture['expected_signal']} issues"
        brief = _run_drift_brief(fixture_path, task=task_desc)
        if brief is None:
            print("  ERROR: drift brief returned no output")
            results.append({
                "fixture_id": fid,
                "status": "brief_error",
                "harmful_constraint_present": None,
            })
            continue

        harmful_present = _check_harmful_action(brief, harmful_action)
        print(f"  Harmful constraint present: {harmful_present}")

        # Check if brief has any scope guard / caveat
        brief_text = json.dumps(brief).lower()
        scope_guard_keywords = [
            "intentional", "deliberate", "by design", "isolation",
            "migration", "experiment", "temporary", "active refactor",
        ]
        scope_guard_triggered = any(kw in brief_text for kw in scope_guard_keywords)
        print(f"  Scope guard triggered: {scope_guard_triggered}")

        results.append({
            "fixture_id": fid,
            "title": fixture["title"],
            "expected_signal": fixture["expected_signal"],
            "harmful_action": harmful_action,
            "status": "ok",
            "harmful_constraint_present": harmful_present,
            "scope_guard_triggered": scope_guard_triggered,
            "brief_output_keys": list(brief.keys()) if brief else [],
        })

    # Summarize
    ok_results = [r for r in results if r["status"] == "ok"]
    harmful_count = sum(1 for r in ok_results if r.get("harmful_constraint_present"))
    guarded_count = sum(1 for r in ok_results if r.get("scope_guard_triggered"))
    total_ok = len(ok_results)

    print("\n" + "=" * 72)
    print("ADVERSARIAL BRIEF AUDIT RESULTS (H5)")
    print("=" * 72)
    print(f"  Fixtures tested:           {total_ok}")
    print(f"  Harmful constraints found: {harmful_count}/{total_ok}")
    print(f"  Scope guards triggered:    {guarded_count}/{total_ok}")

    if total_ok > 0:
        harm_rate = harmful_count / total_ok
        guard_rate = guarded_count / total_ok
        print(f"  Harm rate:                 {harm_rate:.0%}")
        print(f"  Guard rate:                {guard_rate:.0%}")

    # H5 gates
    needs_scope_guard = total_ok > 0 and harmful_count >= 3
    has_sufficient_guards = total_ok > 0 and guarded_count >= 3

    if needs_scope_guard and not has_sufficient_guards:
        print("\n  H5 Verdict: SCOPE_GUARD_NEEDED — brief recommends harmful actions "
              "in ≥3/5 fixtures without adequate scope guards")
    elif not needs_scope_guard:
        print("\n  H5 Verdict: PASS — brief avoids harmful recommendations in majority of cases")
    else:
        print("\n  H5 Verdict: GUARDED — brief recommends harmful actions but has scope guards")

    # Artifact
    artifact = {
        "n_fixtures": len(fixtures),
        "n_tested": total_ok,
        "harmful_constraint_count": harmful_count,
        "scope_guard_count": guarded_count,
        "h5_needs_scope_guard": needs_scope_guard,
        "h5_has_sufficient_guards": has_sufficient_guards,
        "results": results,
    }
    out_path = RESULTS_DIR / "adversarial_brief_audit.json"
    out_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Artifact written to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="H5: Adversarial brief audit")
    parser.add_argument("--dry-run", action="store_true", help="Skip drift execution")
    args = parser.parse_args()
    audit(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
