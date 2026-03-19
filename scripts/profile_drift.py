"""Profile drift analyze to find the bottleneck."""

import cProfile
import pstats
import sys
from io import StringIO
from pathlib import Path

# Ensure drift is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from drift.analyzer import analyze_repo
from drift.config import DriftConfig

repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent

print(f"Profiling drift on: {repo}")
cfg = DriftConfig.load(repo)

pr = cProfile.Profile()
pr.enable()
result = analyze_repo(repo, cfg, since_days=90)
pr.disable()

print(
    f"\nScore: {result.drift_score}, Files: {result.total_files}, "
    f"Findings: {len(result.findings)}, Duration: {result.analysis_duration_seconds}s"
)

# Top 30 by cumulative time
s = StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
ps.print_stats(30)
print(s.getvalue())

# Top 30 by total time (self-time)
s2 = StringIO()
ps2 = pstats.Stats(pr, stream=s2).sort_stats("tottime")
ps2.print_stats(30)
print("\n--- BY SELF-TIME ---")
print(s2.getvalue())
