"""Run drift on repos and extract summary. No terminal encoding issues."""

import json
import subprocess
import time
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "benchmark_results"
OUT_DIR.mkdir(exist_ok=True)


def analyze(repo_path: str, name: str) -> dict | None:
    start = time.time()
    r = subprocess.run(
        ["drift", "analyze", "--repo", repo_path, "--format", "json", "--since", "90"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=900,
    )
    elapsed = time.time() - start

    if not r.stdout.strip():
        print(f"FAIL {name}: no stdout (exit={r.returncode})")
        print(f"  stderr: {r.stderr[:300]}")
        return None

    data = json.loads(r.stdout)
    (OUT_DIR / f"{name}_full.json").write_text(r.stdout, encoding="utf-8")

    scores = {
        s["signal"]: {"score": round(s["score"], 3), "count": s["count"]}
        for s in data.get("signal_scores", [])
    }
    top5 = sorted(data["findings"], key=lambda f: f["score"], reverse=True)[:5]

    summary = {
        "name": name,
        "drift_score": data["drift_score"],
        "severity": data["severity"],
        "files": data["summary"]["total_files"],
        "functions": data["summary"]["total_functions"],
        "ai_ratio": data["summary"]["ai_attributed_ratio"],
        "analysis_s": round(data["summary"]["analysis_duration_seconds"], 2),
        "wall_s": round(elapsed, 2),
        "findings": len(data["findings"]),
        "signals": scores,
        "top5": [
            {"sig": f["signal"], "sev": f["severity"], "score": f["score"], "title": f["title"]}
            for f in top5
        ],
    }
    (OUT_DIR / f"{name}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def clone(name: str, url: str, tmp: Path) -> str | None:
    dest = tmp / name.lower()
    if dest.exists():
        return str(dest)
    r = subprocess.run(
        ["git", "clone", "--depth", "50", url, str(dest)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        print(f"CLONE FAIL {name}: {r.stderr[:200]}")
        return None
    return str(dest)


def main():
    results = []

    # 1) PWBS backend
    pwbs = analyze(r"c:\Users\mickg\PWBS\backend", "pwbs_backend")
    if pwbs:
        results.append(pwbs)
        print(
            f"OK {pwbs['name']}: score={pwbs['drift_score']} sev={pwbs['severity']} "
            f"files={pwbs['files']} findings={pwbs['findings']} {pwbs['wall_s']}s"
        )

    # 2) drift self
    drift_self = analyze(str(Path(__file__).parent.parent), "drift_self")
    if drift_self:
        results.append(drift_self)
        print(
            f"OK {drift_self['name']}: score={drift_self['drift_score']} sev={drift_self['severity']} "
            f"files={drift_self['files']} findings={drift_self['findings']} {drift_self['wall_s']}s"
        )

    # 3) Public repos
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="drift_bench_"))
    print(f"Clone dir: {tmp}")

    repos = {
        "fastapi": "https://github.com/fastapi/fastapi.git",
        "pydantic": "https://github.com/pydantic/pydantic.git",
        "httpx": "https://github.com/encode/httpx.git",
    }
    for name, url in repos.items():
        path = clone(name, url, tmp)
        if path:
            result = analyze(path, name)
            if result:
                results.append(result)
                print(
                    f"OK {name}: score={result['drift_score']} sev={result['severity']} "
                    f"files={result['files']} findings={result['findings']} {result['wall_s']}s"
                )

    # Combined
    (OUT_DIR / "all_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Summary table
    print(
        f"\n{'Repo':<18} {'Score':>6} {'Sev':>8} {'Files':>6} {'Funcs':>6} {'Finds':>6} {'Time':>6}"
    )
    print("-" * 60)
    for r in results:
        print(
            f"{r['name']:<18} {r['drift_score']:>6.3f} {r['severity']:>8} "
            f"{r['files']:>6} {r['functions']:>6} {r['findings']:>6} "
            f"{r['wall_s']:>5.1f}s"
        )


if __name__ == "__main__":
    main()
