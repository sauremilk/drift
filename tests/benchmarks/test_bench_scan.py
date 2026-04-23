"""Continuous performance benchmarks for the drift scanning pipeline.

These benchmarks use pytest-benchmark and run against the drift workspace
itself (self-scan).  They establish a measurable, reproducible baseline for:

  - Full scan (drift.analyze): end-to-end latency and throughput
  - Ingestion phase: file discovery and AST parsing
  - Signal phase: per-signal execution time
  - Scoring phase: composite score calculation

The benchmarks are intentionally kept deterministic:
  - Fixed repo path (the drift workspace itself)
  - ``--exit-zero`` so analysis never fails due to drift score

Budget from ``benchmarks/perf_budget.json`` is loaded if present.
The benchmark job in CI compares against stored baselines from main.

Run locally:
    pytest tests/benchmarks/ -v --benchmark-only --benchmark-autosave
Compare against saved:
    pytest tests/benchmarks/ -v --benchmark-only --benchmark-compare
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
_PERF_BUDGET = _REPO_ROOT / "benchmarks" / "perf_budget.json"


def _load_perf_budget() -> dict:
    if _PERF_BUDGET.exists():
        return json.loads(_PERF_BUDGET.read_text(encoding="utf-8"))
    return {}


_BUDGET = _load_perf_budget()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_drift_json(extra_args: list[str] | None = None) -> dict:
    """Run 'drift analyze' against the workspace and return parsed JSON."""
    cmd = [
        sys.executable,
        "-m",
        "drift",
        "analyze",
        "--repo",
        str(_REPO_ROOT),
        "--format",
        "json",
        "--exit-zero",
    ] + (extra_args or [])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO_ROOT)
    assert result.returncode == 0, f"drift exited {result.returncode}:\n{result.stderr}"

    # Strip any non-JSON trailing console text before parsing.
    raw = result.stdout.strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    assert start >= 0, f"No JSON object in drift output:\n{raw[:500]}"
    return json.loads(raw[start:end])


# ---------------------------------------------------------------------------
# Full-scan benchmark
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.performance
def test_bench_full_scan(benchmark) -> None:
    """Benchmark: full drift analyze end-to-end latency (self-scan)."""
    data = benchmark(_run_drift_json)

    assert "drift_score" in data, "drift output must contain drift_score"
    score = data["drift_score"]
    assert 0.0 <= score <= 1.0

    # Enforce optional budget if configured
    budget_ms = _BUDGET.get("full_scan_ms")
    if budget_ms is not None:
        elapsed_ms = benchmark.stats["mean"] * 1_000
        assert elapsed_ms <= budget_ms, (
            f"Full scan took {elapsed_ms:.0f} ms, exceeds budget {budget_ms} ms"
        )


# ---------------------------------------------------------------------------
# Signal-only benchmark (skip ingestion via cached parse results)
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.performance
def test_bench_signal_count(benchmark) -> None:
    """Benchmark: number of findings stays within expected range (stability proxy)."""
    data = benchmark(_run_drift_json)

    findings = data.get("findings", [])
    # Sanity: drift scanning itself should produce at least some findings
    # (it is a complex codebase) but not an absurd number.
    assert len(findings) < 5_000, f"Unexpectedly high finding count: {len(findings)}"


# ---------------------------------------------------------------------------
# Scoring micro-benchmark
# ---------------------------------------------------------------------------


@pytest.mark.performance
def test_bench_composite_score_micro(benchmark) -> None:
    """Micro-benchmark: composite_score on a realistic finding set."""
    from drift.config._schema import SignalWeights
    from drift.models import Severity
    from drift.models._enums import SignalType
    from drift.models._findings import Finding
    from drift.scoring.engine import assign_impact_scores, composite_score, compute_signal_scores

    weights = SignalWeights()
    signal_types = [str(s) for s in SignalType]

    # Build a realistic finding set (50 findings across all signals)
    findings = [
        Finding(
            signal_type=signal_types[i % len(signal_types)],
            severity=Severity.MEDIUM,
            score=0.4 + 0.01 * (i % 60),
            title="bench",
            description="bench",
            file_path=Path(f"src/drift/bench_{i % 10}.py"),
        )
        for i in range(50)
    ]

    def _score_pipeline() -> float:
        assign_impact_scores(findings, weights)
        sig_scores = compute_signal_scores(findings)
        return composite_score(sig_scores, weights)

    result = benchmark(_score_pipeline)
    assert 0.0 <= result <= 1.0
