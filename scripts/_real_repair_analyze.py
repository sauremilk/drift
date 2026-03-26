#!/usr/bin/env python3
"""Analyze a real repo and output top agent tasks for repair."""
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from drift.analyzer import analyze_repo
from drift.output.agent_tasks import analysis_to_agent_tasks_json
from drift.output.json_output import analysis_to_json

_default = r"C:\Users\mickg\AppData\Local\Temp\drift_real_repair_httpx"
repo = Path(os.environ.get("HTTPX_DIR", _default))

r = analyze_repo(repo)
print(f"Score: {r.drift_score}")
print(f"Findings: {len(r.findings)}")
print()

c = Counter(f.signal_type.value for f in r.findings)
for sig, n in c.most_common():
    print(f"  {sig}: {n}")
print()

tasks_json = analysis_to_agent_tasks_json(r)
td = json.loads(tasks_json)
print(f"Tasks: {td['task_count']}")
print()
for t in td["tasks"][:5]:
    prio = t["priority"]
    sig = t["signal_type"]
    title = t["title"]
    files = t.get("affected_files", [])[:3]
    crit = len(t["success_criteria"])
    print(f"  [{prio}] {sig}: {title}")
    if files:
        print(f"       Files: {files}")
    print(f"       Criteria: {crit}")
print()

# Save full analysis + tasks for before/after comparison
out_dir = Path(__file__).resolve().parent.parent / "benchmark_results" / "repair" / "real_world"
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "httpx_before.json").write_text(
    analysis_to_json(r), encoding="utf-8"
)
(out_dir / "httpx_tasks.json").write_text(
    tasks_json, encoding="utf-8"
)
print(f"Saved to {out_dir}")
