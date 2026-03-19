"""Benchmark drift on real-world repositories for STUDY.md."""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPOS = {
    "PWBS-Backend": str(Path(__file__).resolve().parents[2] / "backend"),
    "drift-self": str(Path(__file__).resolve().parents[1]),
}

# Public repos to clone and analyze
CLONE_REPOS = {
    "FastAPI": "https://github.com/fastapi/fastapi.git",
    "Pydantic": "https://github.com/pydantic/pydantic.git",
    "httpx": "https://github.com/encode/httpx.git",
}

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "benchmark_results"
OUTPUT_DIR.mkdir(exist_ok=True)


def run_drift(repo_path: str, name: str) -> dict | None:
    """Run drift analyze on a repo and return parsed JSON."""
    print(f"\n{'=' * 60}")
    print(f"Analyzing: {name} ({repo_path})")
    print(f"{'=' * 60}")
    start = time.time()
    result = subprocess.run(
        ["drift", "analyze", "--repo", repo_path, "--format", "json", "--since", "90"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    elapsed = time.time() - start

    if result.returncode != 0 and not result.stdout.strip():
        print(f"  FAILED (exit {result.returncode}): {result.stderr[:200]}")
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"  JSON parse failed. stdout length: {len(result.stdout)}")
        return None

    summary = {
        "name": name,
        "repo_path": repo_path,
        "drift_score": data["drift_score"],
        "severity": data["severity"],
        "total_files": data["summary"]["total_files"],
        "total_functions": data["summary"]["total_functions"],
        "ai_attributed_ratio": data["summary"]["ai_attributed_ratio"],
        "analysis_duration_seconds": round(data["summary"]["analysis_duration_seconds"], 2),
        "wall_clock_seconds": round(elapsed, 2),
        "total_findings": len(data["findings"]),
        "signal_scores": {
            s["signal"]: {"score": round(s["score"], 3), "count": s["count"]}
            for s in data.get("signal_scores", [])
        },
        "top_findings": [
            {
                "signal": f["signal"],
                "severity": f["severity"],
                "score": f["score"],
                "title": f["title"],
                "file": f["file"],
            }
            for f in sorted(data["findings"], key=lambda x: x["score"], reverse=True)[:5]
        ],
    }

    out_file = OUTPUT_DIR / f"{name.lower().replace(' ', '_').replace('-', '_')}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Also save full output
    full_file = OUTPUT_DIR / f"{name.lower().replace(' ', '_').replace('-', '_')}_full.json"
    with open(full_file, "w", encoding="utf-8") as f:
        f.write(result.stdout)

    print(f"  Score: {summary['drift_score']} ({summary['severity']})")
    print(f"  Files: {summary['total_files']}, Functions: {summary['total_functions']}")
    print(f"  Findings: {summary['total_findings']}")
    print(
        f"  Duration: {summary['analysis_duration_seconds']}s (wall: {summary['wall_clock_seconds']}s)"
    )
    for sig, info in summary["signal_scores"].items():
        print(f"    {sig}: {info['score']} ({info['count']} findings)")

    return summary


def clone_and_analyze(name: str, url: str, tmp_dir: str) -> dict | None:
    """Clone a public repo and run drift on it."""
    clone_path = Path(tmp_dir) / name.lower()
    if not clone_path.exists():
        print(f"\nCloning {name} from {url}...")
        result = subprocess.run(
            ["git", "clone", "--depth", "50", url, str(clone_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  Clone failed: {result.stderr[:200]}")
            return None
    return run_drift(str(clone_path), name)


def main() -> None:
    all_results = []

    # Local repos
    for name, path in REPOS.items():
        result = run_drift(path, name)
        if result:
            all_results.append(result)

    # Clone and analyze public repos
    tmp_dir = tempfile.mkdtemp(prefix="drift_benchmark_")
    print(f"\nTemp directory for clones: {tmp_dir}")

    for name, url in CLONE_REPOS.items():
        try:
            result = clone_and_analyze(name, url, tmp_dir)
            if result:
                all_results.append(result)
        except Exception as e:
            print(f"  Error analyzing {name}: {e}")

    # Write combined results
    combined_file = OUTPUT_DIR / "all_results.json"
    with open(combined_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"ALL RESULTS SAVED TO: {OUTPUT_DIR}")
    print(f"{'=' * 60}")

    # Print comparison table
    print(
        f"\n{'Repo':<20} {'Score':>6} {'Sev':>8} {'Files':>6} {'Funcs':>6} {'Finds':>7} {'Time':>6}"
    )
    print("-" * 65)
    for r in all_results:
        print(
            f"{r['name']:<20} {r['drift_score']:>6.3f} {r['severity']:>8} "
            f"{r['total_files']:>6} {r['total_functions']:>6} "
            f"{r['total_findings']:>7} {r['wall_clock_seconds']:>5.1f}s"
        )


if __name__ == "__main__":
    main()
