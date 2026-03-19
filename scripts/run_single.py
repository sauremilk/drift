"""Run drift on a single repo and save compact summary."""

import json
import subprocess
import sys
from pathlib import Path

repo_path = sys.argv[1]
name = sys.argv[2]
out_dir = Path(__file__).parent.parent / "benchmark_results"
out_dir.mkdir(exist_ok=True)

r = subprocess.run(
    ["drift", "analyze", "--repo", repo_path, "--format", "json", "--since", "90"],
    capture_output=True,
    text=True,
    timeout=300,
)
data = json.loads(r.stdout)

summary = {
    "name": name,
    "drift_score": data["drift_score"],
    "severity": data["severity"],
    "total_files": data["summary"]["total_files"],
    "total_functions": data["summary"]["total_functions"],
    "ai_ratio": data["summary"]["ai_attributed_ratio"],
    "duration_s": round(data["summary"]["analysis_duration_seconds"], 2),
    "findings": len(data["findings"]),
    "signals": {
        s["signal"]: {"score": round(s["score"], 3), "count": s["count"]}
        for s in data.get("signal_scores", [])
    },
    "top5": [
        {"signal": f["signal"], "sev": f["severity"], "score": f["score"], "title": f["title"]}
        for f in sorted(data["findings"], key=lambda x: x["score"], reverse=True)[:5]
    ],
}

out_file = out_dir / f"{name.lower().replace(' ', '_')}.json"
with open(out_file, "w") as f:
    json.dump(summary, f, indent=2)

with open(out_dir / f"{name.lower().replace(' ', '_')}_full.json", "w") as f:
    f.write(r.stdout)

print(
    f"OK:{name}|{summary['drift_score']}|{summary['severity']}|{summary['total_files']}|{summary['total_functions']}|{summary['findings']}|{summary['duration_s']}"
)
