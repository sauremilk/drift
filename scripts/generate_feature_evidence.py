#!/usr/bin/env python3
"""Generate a deterministc feature-evidence artifact for feat: commits.

All metric values are computed live from the repository; no manual
metric arguments are accepted.  This ensures the evidence file cannot
be fabricated by an agent without actually running the measurement.

Usage::

    python scripts/generate_feature_evidence.py --version X.Y.Z --slug my-feature
    python scripts/generate_feature_evidence.py --version X.Y.Z --slug my-feature \\
        --skip-tests --skip-precision-recall

The generated file is written to::

    benchmark_results/v{VERSION}_{slug}_feature_evidence.json

A ``generated_by`` block is embedded, containing the current git SHA,
an ISO-8601 timestamp, and the script name.  ``validate_feature_evidence.py``
verifies this block during the pre-push gate.

Exit codes:
    0 — evidence file written successfully
    1 — measurement error (tests failing, drift invocation failed, …)
    2 — argument error
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = REPO_ROOT / "benchmark_results"
SCRIPT_NAME = "scripts/generate_feature_evidence.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(
    cmd: list[str],
    *,
    check: bool = False,
    capture: bool = True,
    timeout: int = 300,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check,
        timeout=timeout,
        cwd=cwd or REPO_ROOT,
    )


def _git_sha_long() -> str:
    """Return the full SHA of HEAD, or 'unknown' on failure."""
    result = _run(["git", "rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _drift_version() -> str:
    """Return the installed drift version string."""
    python = _python_exe()
    result = _run([python, "-m", "drift", "--version"])
    output = (result.stdout + result.stderr).strip()
    # version strings like "drift, version 2.25.0" or just "2.25.0"
    match = re.search(r"(\d+\.\d+\.\d+)", output)
    return match.group(1) if match else output or "unknown"


def _python_exe() -> str:
    """Return path to the venv python, falling back to sys.executable."""
    venv_scripts = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    venv_bin = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_scripts.exists():
        return str(venv_scripts)
    if venv_bin.exists():
        return str(venv_bin)
    return sys.executable


# ---------------------------------------------------------------------------
# Measurement functions
# ---------------------------------------------------------------------------


def run_self_analysis() -> dict:
    """Run drift analyze on the repo and return a before/after snapshot.

    Because we only have the current state (no before baseline in this
    context), we capture the current state and note the absence of a
    before snapshot.
    """
    python = _python_exe()
    print("  → running drift analyze…", flush=True)
    with tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, dir=REPO_ROOT
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        result = _run(
            [
                python, "-m", "drift", "analyze",
                "--repo", ".", "--path", "src/drift",
                "--format", "json", "--exit-zero",
            ],
            timeout=300,
        )
        raw = result.stdout + result.stderr
        # Extract JSON from output (drift may emit Rich symbols before/after)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            print("  ✗ drift analyze produced no JSON output", file=sys.stderr, flush=True)
            return {"error": "no JSON output from drift analyze", "raw_output": raw[:500]}

        data = json.loads(raw[start:end])
        compact = data.get("compact_summary", {})
        score = data.get("drift_score", data.get("score", None))
        # Normalise: some versions nest the score
        if score is None and isinstance(data.get("analysis_status"), dict):
            pass  # leave as None, reported below

        return {
            "drift_score": score,
            "total_findings": compact.get("findings_total", compact.get("total_findings")),
            "findings_deduplicated": compact.get("findings_deduplicated"),
            "analysis_status": data.get("analysis_status", {}).get("status", "unknown")
            if isinstance(data.get("analysis_status"), dict)
            else data.get("analysis_status", "unknown"),
            "source": "live: drift analyze --repo . --path src/drift --format json --exit-zero",
        }
    except json.JSONDecodeError as exc:
        return {"error": f"JSON parse error: {exc}"}
    except subprocess.TimeoutExpired:
        return {"error": "drift analyze timed out after 300s"}
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def run_tests(*, skip_precision_recall: bool = False) -> dict:
    """Run the quick test suite and return pass/fail counts."""
    python = _python_exe()
    print("  → running pytest (quick, no-smoke)…", flush=True)
    cmd = [
        python, "-m", "pytest",
        "tests/",
        "--ignore=tests/test_smoke_real_repos.py",
        "-m", "not slow",
        "-q", "--tb=short",
        "-n", "auto",
        "--dist=loadscope",
    ]
    if skip_precision_recall:
        cmd += ["--ignore=tests/test_precision_recall.py"]

    result = _run(cmd, timeout=600)
    output = result.stdout + result.stderr

    total_passing = 0
    total_failing = 0
    changed_test_note = ""

    # Parse "X passed, Y failed, Z error" from pytest summary line
    passed_match = re.search(r"(\d+) passed", output)
    failed_match = re.search(r"(\d+) failed", output)
    error_match = re.search(r"(\d+) error", output)

    if passed_match:
        total_passing = int(passed_match.group(1))
    if failed_match:
        total_failing += int(failed_match.group(1))
    if error_match:
        total_failing += int(error_match.group(1))

    if total_failing > 0:
        print(
            f"  ✗ {total_failing} test(s) failed — evidence file will note this.",
            file=sys.stderr,
            flush=True,
        )
        # Extract first FAILED line for the note
        lines = output.splitlines()
        failed_lines = [ln.strip() for ln in lines if ln.strip().startswith("FAILED")]
        changed_test_note = "; ".join(failed_lines[:3]) or "see pytest output"

    return {
        "total_passing": total_passing,
        "total_failing": total_failing,
        **({"failing_note": changed_test_note} if total_failing > 0 else {}),
        "exit_code": result.returncode,
    }


def run_precision_recall() -> dict | None:
    """Run precision-recall suite and return per-signal metrics, or None on skip."""
    python = _python_exe()
    pr_test = REPO_ROOT / "tests" / "test_precision_recall.py"
    if not pr_test.exists():
        return None

    print("  → running precision-recall tests…", flush=True)
    result = _run(
        [python, "-m", "pytest", str(pr_test), "-v", "--tb=short"],
        timeout=300,
    )
    output = result.stdout + result.stderr
    total_pr = 0
    pr_passing = 0
    pr_failing = 0

    passed_match = re.search(r"(\d+) passed", output)
    failed_match = re.search(r"(\d+) failed", output)

    if passed_match:
        pr_passing = int(passed_match.group(1))
        total_pr += pr_passing
    if failed_match:
        pr_failing = int(failed_match.group(1))
        total_pr += pr_failing

    return {
        "total_tests": total_pr,
        "passing": pr_passing,
        "failing": pr_failing,
        "exit_code": result.returncode,
        "source": "live: pytest tests/test_precision_recall.py -v --tb=short",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_filename(version: str, slug: str) -> str:
    return f"v{version}_{slug}_feature_evidence.json"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic feature-evidence artifact.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Semver version without 'v' prefix, e.g. 2.25.0",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="Short kebab-case feature slug, e.g. evidence-gate",
    )
    parser.add_argument(
        "--feature",
        default=None,
        help="Short human-readable feature description (default: derived from slug)",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip the pytest run (only self-analysis is run)",
    )
    parser.add_argument(
        "--skip-precision-recall",
        action="store_true",
        help="Skip the precision-recall test suite",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Override output path (default: benchmark_results/vVERSION_SLUG_feature_evidence.json)",  # noqa: E501
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # Validate version format
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        print(f"ERROR: --version must be X.Y.Z (got: {args.version!r})", file=sys.stderr)
        return 2

    # Validate slug format
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.slug):
        print(
            f"ERROR: --slug must be lowercase kebab-case (got: {args.slug!r})",
            file=sys.stderr,
        )
        return 2

    feature_label = args.feature or args.slug.replace("-", " ").replace("_", " ")
    out_filename = _build_filename(args.version, args.slug)
    out_path = Path(args.output) if args.output else BENCHMARK_DIR / out_filename

    print(f"[generate_feature_evidence] version={args.version} slug={args.slug}", flush=True)
    print(f"[generate_feature_evidence] output  → {out_path}", flush=True)

    # --- Collect measurements ---
    git_sha = _git_sha_long()
    drift_ver = _drift_version()
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    print("[generate_feature_evidence] Phase 1: self-analysis", flush=True)
    self_analysis = run_self_analysis()

    tests_result: dict | None = None
    pr_result: dict | None = None

    if not args.skip_tests:
        print("[generate_feature_evidence] Phase 2: test suite", flush=True)
        tests_result = run_tests(skip_precision_recall=args.skip_precision_recall)

    if not args.skip_tests and not args.skip_precision_recall:
        print("[generate_feature_evidence] Phase 3: precision-recall", flush=True)
        pr_result = run_precision_recall()

    # --- Assemble evidence document ---
    evidence: dict = {
        "version": args.version,
        "date": datetime.date.today().isoformat(),
        "feature": feature_label,
        "description": f"Feature evidence for {feature_label} (v{args.version}).",
        "generated_by": {
            "script": SCRIPT_NAME,
            "git_sha": git_sha,
            "drift_version": drift_ver,
            "timestamp": timestamp,
        },
        "self_analysis": self_analysis,
    }

    if tests_result is not None:
        evidence["tests"] = tests_result

    if pr_result is not None:
        evidence["precision_recall_suite"] = pr_result

    evidence["audit_artifacts_updated"] = []

    # --- Determine exit code based on failures ---
    failed = tests_result is not None and tests_result.get("total_failing", 0) > 0
    has_error = "error" in self_analysis

    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[generate_feature_evidence] ✓ written → {out_path}", flush=True)

    if has_error:
        print(
            "  ⚠ self-analysis encountered an error; review the evidence file.",
            file=sys.stderr,
            flush=True,
        )

    if failed:
        print(
            "  ✗ test failures detected — evidence recorded but push gate will block.",
            file=sys.stderr,
            flush=True,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
