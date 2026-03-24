"""Run drift on TypeScript repositories and extract summary."""

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

    # Compute signal scores from findings (top-level signal_scores not in JSON)
    signal_findings: dict[str, list[float]] = {}
    for f in data["findings"]:
        sig = f["signal"]
        signal_findings.setdefault(sig, []).append(f["score"])
    scores = {
        sig: {"score": round(sum(vals) / len(vals), 3), "count": len(vals)}
        for sig, vals in signal_findings.items()
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


def main() -> None:
    results: list[dict] = []

    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="drift_ts_bench_"))
    print(f"Clone dir: {tmp}")

    # TypeScript/JavaScript benchmark repos — diverse architectures
    repos = {
        # Layered / well-structured frameworks
        "nestjs": "https://github.com/nestjs/nest.git",
        "angular": "https://github.com/angular/angular.git",
        # Monorepo / workspace architecture
        "turborepo": "https://github.com/vercel/turborepo.git",
        "trpc": "https://github.com/trpc/trpc.git",
        # Full-stack / hybrid
        "nextjs": "https://github.com/vercel/next.js.git",
        # Smaller / focused libraries
        "zod": "https://github.com/colinhacks/zod.git",
        "express": "https://github.com/expressjs/express.git",
        "fastify": "https://github.com/fastify/fastify.git",
        # UI / component architecture
        "svelte": "https://github.com/sveltejs/svelte.git",
        # Domain-heavy / CLI
        "prisma": "https://github.com/prisma/prisma.git",
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
            else:
                print(f"SKIP {name}: analysis returned no data")

    # Combined output
    (OUT_DIR / "ts_all_results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    # Summary table
    print(
        f"\n{'Repo':<18} {'Score':>6} {'Sev':>8} {'Files':>6} {'Funcs':>6} {'Finds':>6} {'Time':>6}"
    )
    print("-" * 68)
    for r in results:
        print(
            f"{r['name']:<18} {r['drift_score']:>6.3f} {r['severity']:>8} "
            f"{r['files']:>6} {r['functions']:>6} {r['findings']:>6} "
            f"{r['wall_s']:>5.1f}s"
        )


if __name__ == "__main__":
    main()
