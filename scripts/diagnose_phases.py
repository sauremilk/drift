"""Diagnose which phase of drift is slow on PWBS backend."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import signal modules
import drift.signals.architecture_violation  # noqa: F401
import drift.signals.doc_impl_drift  # noqa: F401
import drift.signals.explainability_deficit  # noqa: F401
import drift.signals.mutant_duplicates  # noqa: F401
import drift.signals.pattern_fragmentation  # noqa: F401
import drift.signals.system_misalignment  # noqa: F401
import drift.signals.temporal_volatility  # noqa: F401
from drift.cache import ParseCache
from drift.config import DriftConfig
from drift.ingestion.ast_parser import parse_file
from drift.ingestion.file_discovery import discover_files
from drift.ingestion.git_history import build_file_histories, parse_git_history
from drift.signals.base import AnalysisContext, create_signals

repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
print(f"Target: {repo}")

cfg = DriftConfig.load(repo)

# Phase 1: Discovery
t0 = time.monotonic()
files = discover_files(repo, include=cfg.include, exclude=cfg.exclude)
t1 = time.monotonic()
print(f"[1] Discovery: {len(files)} files in {t1 - t0:.2f}s")

# Phase 2: Parsing
cache = ParseCache(repo / cfg.cache_dir)
parse_results = []
t2 = time.monotonic()
for finfo in files:
    full_path = repo / finfo.path
    try:
        content_hash = ParseCache.file_hash(full_path)
        hit = cache.get(content_hash)
        if hit is not None:
            parse_results.append(hit)
            continue
    except OSError:
        pass
    result = parse_file(finfo.path, repo, finfo.language)
    parse_results.append(result)
    try:
        content_hash = ParseCache.file_hash(full_path)
        cache.put(content_hash, result)
    except OSError:
        pass
t3 = time.monotonic()
print(f"[2] Parsing:   {len(parse_results)} results in {t3 - t2:.2f}s")

total_funcs = sum(len(pr.functions) for pr in parse_results)
print(f"    Total functions found: {total_funcs}")

# Phase 3: Git history
t4 = time.monotonic()
known_files = {f.path.as_posix() for f in files}
commits = parse_git_history(repo, since_days=90, file_filter=known_files)
file_histories = build_file_histories(commits, known_files=known_files)
t5 = time.monotonic()
print(f"[3] Git hist:  {len(commits)} commits in {t5 - t4:.2f}s")

# Phase 4: Signals (one by one)
ctx = AnalysisContext(
    repo_path=repo,
    config=cfg,
    parse_results=parse_results,
    file_histories=file_histories,
)
signals = create_signals(ctx)
print(f"\n[4] Running {len(signals)} signals...")
for signal in signals:
    ts = time.monotonic()
    try:
        findings = signal.analyze(parse_results, file_histories, cfg)
        te = time.monotonic()
        print(f"    {signal.name:30s} → {len(findings):4d} findings in {te - ts:.2f}s")
    except Exception as exc:
        te = time.monotonic()
        print(f"    {signal.name:30s} → ERROR in {te - ts:.2f}s: {exc}")

total = time.monotonic() - t0
print(f"\nTotal: {total:.2f}s")
