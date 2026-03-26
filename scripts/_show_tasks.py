#!/usr/bin/env python3
"""Show repair-relevant tasks from httpx analysis."""
import json
from pathlib import Path

tasks = json.loads(
    Path("benchmark_results/repair/real_world/httpx_tasks.json").read_text()
)
for t in tasks["tasks"]:
    sig = t["signal_type"]
    if sig in (
        "mutant_duplicate",
        "doc_impl_drift",
        "pattern_fragmentation",
    ):
        tid = t["id"]
        title = t["title"]
        prio = t["priority"]
        files = t.get("affected_files", [])
        ctx = t.get("context", t.get("description", ""))[:300]
        crit = t["success_criteria"]
        print(f"=== {tid}: {title} ===")
        print(f"Signal: {sig}, Priority: {prio}")
        print(f"Files: {files}")
        print(f"Context: {ctx}...")
        print(f"Criteria: {crit}")
        print()
