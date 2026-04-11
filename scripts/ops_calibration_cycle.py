"""Run a repeatable calibration cycle and persist artifacts.

This script is intended for routine workspace operations:
- feedback summary
- calibration status
- calibration dry-run or apply
- optional baseline analyze snapshot

Outputs are written to .drift/reports/<timestamp>/.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def _run_capture(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.returncode, proc.stdout, proc.stderr


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run drift calibration operations cycle.")
    parser.add_argument(
        "--repo",
        default=".",
        help="Repository root path (default: current directory).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply calibration changes (default is dry-run).",
    )
    parser.add_argument(
        "--skip-analyze",
        action="store_true",
        help="Skip baseline analyze snapshot step.",
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.exists():
        print(f"ERROR: repo path does not exist: {repo}", file=sys.stderr)
        return 2

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = repo / ".drift" / "reports" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    drift_cmd = [str(repo / ".venv" / "Scripts" / "drift.exe")]
    if not Path(drift_cmd[0]).exists():
        drift_cmd = ["drift"]

    manifest: dict[str, object] = {
        "timestamp": ts,
        "repo": str(repo),
        "mode": "apply" if args.apply else "dry-run",
        "steps": [],
    }

    def run_step(name: str, cmd: list[str], stdout_file: str, stderr_file: str) -> int:
        code, out, err = _run_capture(cmd, repo)
        _write_text(out_dir / stdout_file, out)
        _write_text(out_dir / stderr_file, err)
        cast_steps = manifest["steps"]
        assert isinstance(cast_steps, list)
        cast_steps.append({"name": name, "code": code, "cmd": cmd})
        return code

    overall = 0

    if not args.skip_analyze:
        code = run_step(
            "analyze",
            drift_cmd + ["analyze", "--repo", ".", "--format", "json", "--exit-zero"],
            "analyze.json",
            "analyze.stderr.log",
        )
        if code != 0:
            overall = code

    code = run_step(
        "feedback_summary",
        drift_cmd + ["feedback", "summary", "--repo", "."],
        "feedback_summary.txt",
        "feedback_summary.stderr.log",
    )
    if code != 0 and overall == 0:
        overall = code

    code = run_step(
        "calibrate_status",
        drift_cmd + ["calibrate", "status", "--repo", "."],
        "calibrate_status.txt",
        "calibrate_status.stderr.log",
    )
    if code != 0 and overall == 0:
        overall = code

    calibrate_cmd = drift_cmd + ["calibrate", "run", "--repo", ".", "--format", "json"]
    if not args.apply:
        calibrate_cmd.append("--dry-run")

    code = run_step(
        "calibrate_run",
        calibrate_cmd,
        "calibrate_run.json",
        "calibrate_run.stderr.log",
    )
    if code != 0 and overall == 0:
        overall = code

    _write_text(out_dir / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=True))

    print(f"Calibration cycle finished ({manifest['mode']}).")
    print(f"Artifacts: {out_dir}")
    return overall


if __name__ == "__main__":
    raise SystemExit(main())
