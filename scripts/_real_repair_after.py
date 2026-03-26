"""Re-analyze httpx after repairs and save results."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from drift.analyzer import analyze_repo
from drift.output.json_output import analysis_to_json

HTTPX = Path(r"C:\Users\mickg\AppData\Local\Temp\drift_real_repair_httpx")
OUT = Path(__file__).resolve().parent.parent / "benchmark_results" / "repair" / "real_world"

r = analyze_repo(HTTPX)
data_str = analysis_to_json(r)
data = json.loads(data_str)

print(f"Score: {data['drift_score']}")
print(f"Findings: {len(data['findings'])}")

c = Counter(f["signal"] for f in data["findings"])
for sig, n in c.most_common():
    print(f"  {sig}: {n}")

# Load before for comparison
before = json.loads((OUT / "httpx_before.json").read_text())
print("\n--- Delta ---")
print(f"Score: {before['drift_score']} -> {data['drift_score']}")
print(f"Findings: {len(before['findings'])} -> {len(data['findings'])}")

before_c = Counter(f["signal"] for f in before["findings"])
all_sigs = sorted(set(list(c.keys()) + list(before_c.keys())))
for sig in all_sigs:
    b, a = before_c.get(sig, 0), c.get(sig, 0)
    delta = a - b
    marker = " <--" if delta != 0 else ""
    print(f"  {sig}: {b} -> {a} ({delta:+d}){marker}")

# Save after
(OUT / "httpx_after.json").write_text(json.dumps(data, indent=2))
print("\nSaved httpx_after.json")
