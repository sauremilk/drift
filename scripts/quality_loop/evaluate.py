"""Multi-seed evaluator with gate logic for the quality improvement loop.

CLI usage::

    python -m scripts.quality_loop evaluate \\
        --src src/drift \\
        --seeds 11,22,33,44,55 \\
        --mode mcts \\
        --mcts-budget 10 \\
        --output-json benchmark_results/quality_loop_eval.json

The evaluator runs the quality loop for each seed in dry-run mode, collects
per-component metrics, and applies a hard gate before allowing apply.

Gate criteria (all must pass):
    * median_improvement  >= min_median      (default 0.01)
    * positive_seed_rate  >= min_pos_rate    (default 0.70)
    * ruff_regressions    == 0
    * mypy_regressions    == 0
    * max_drift_delta     <= drift_tolerance (default 0.005)
"""

from __future__ import annotations

import contextlib
import json
import statistics
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeedResult:
    """Result from a single-seed dry-run."""

    seed: int
    improvement: float
    baseline_ruff: int
    baseline_mypy: int
    baseline_drift: float
    final_ruff: int
    final_mypy: int
    final_drift: float
    applied: bool
    error: str | None = None

    @property
    def ruff_regression(self) -> bool:
        return self.final_ruff > self.baseline_ruff

    @property
    def mypy_regression(self) -> bool:
        return self.final_mypy > self.baseline_mypy

    @property
    def drift_delta(self) -> float:
        return self.final_drift - self.baseline_drift

    @classmethod
    def from_result_dict(cls, seed: int, d: dict) -> SeedResult:
        return cls(
            seed=seed,
            improvement=float(d.get("improvement", 0.0)),
            baseline_ruff=int(d.get("baseline_ruff", 0)),
            baseline_mypy=int(d.get("baseline_mypy", 0)),
            baseline_drift=float(d.get("baseline_drift", 0.0)),
            final_ruff=int(d.get("final_ruff", 0)),
            final_mypy=int(d.get("final_mypy", 0)),
            final_drift=float(d.get("final_drift", 0.0)),
            applied=bool(d.get("applied", False)),
        )

    @classmethod
    def from_error(cls, seed: int, error: str) -> SeedResult:
        return cls(
            seed=seed,
            improvement=0.0,
            baseline_ruff=0,
            baseline_mypy=0,
            baseline_drift=0.0,
            final_ruff=0,
            final_mypy=0,
            final_drift=0.0,
            applied=False,
            error=error,
        )


@dataclass
class EvaluationResult:
    """Aggregated multi-seed evaluation with gate decision."""

    src: str
    mode: str
    seeds: list[int]
    seed_details: list[SeedResult]
    # Aggregates
    median_improvement: float
    mean_improvement: float
    positive_seed_rate: float
    ruff_regressions: int
    mypy_regressions: int
    max_drift_delta: float
    # Gate
    gate_pass: bool
    gate_failure_reasons: list[str]
    # Thresholds used
    min_median: float
    min_positive_rate: float
    drift_tolerance: float
    # Metadata
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    error_seeds: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Core evaluation logic (pure — no subprocess, injectable for tests)
# ---------------------------------------------------------------------------


def compute_gate(
    seed_results: list[SeedResult],
    *,
    min_median: float = 0.01,
    min_positive_rate: float = 0.70,
    drift_tolerance: float = 0.005,
) -> tuple[bool, list[str]]:
    """Return (gate_pass, failure_reasons) for a list of seed results.

    Only results without errors are used for numeric aggregates.
    A gate failure on ANY criterion sets gate_pass=False.
    """
    valid = [r for r in seed_results if r.error is None]
    failures: list[str] = []

    if not valid:
        return False, ["no_valid_seeds: all seeds failed with errors"]

    improvements = [r.improvement for r in valid]
    median_imp = statistics.median(improvements)
    positive_count = sum(1 for v in improvements if v > 0)
    positive_rate = positive_count / len(valid)

    ruff_regressions = sum(1 for r in valid if r.ruff_regression)
    mypy_regressions = sum(1 for r in valid if r.mypy_regression)
    max_drift_delta = max(r.drift_delta for r in valid)

    if median_imp < min_median:
        failures.append(
            f"median_improvement={median_imp:.4f} < threshold={min_median:.4f}"
        )
    if positive_rate < min_positive_rate:
        failures.append(
            f"positive_seed_rate={positive_rate:.2%} < threshold={min_positive_rate:.2%}"
        )
    if ruff_regressions > 0:
        failures.append(f"ruff_regressions={ruff_regressions} (must be 0)")
    if mypy_regressions > 0:
        failures.append(f"mypy_regressions={mypy_regressions} (must be 0)")
    if max_drift_delta > drift_tolerance:
        failures.append(
            f"max_drift_delta={max_drift_delta:.4f} > tolerance={drift_tolerance:.4f}"
        )

    return len(failures) == 0, failures


def aggregate(
    seed_results: list[SeedResult],
    *,
    min_median: float = 0.01,
    min_positive_rate: float = 0.70,
    drift_tolerance: float = 0.005,
    src: str,
    mode: str,
    seeds: list[int],
) -> EvaluationResult:
    """Build a full EvaluationResult from a list of SeedResult objects."""
    valid = [r for r in seed_results if r.error is None]
    error_seeds = [r.seed for r in seed_results if r.error is not None]

    improvements = [r.improvement for r in valid] if valid else [0.0]
    median_imp = statistics.median(improvements)
    mean_imp = statistics.mean(improvements)
    positive_count = sum(1 for v in improvements if v > 0)
    positive_rate = positive_count / len(valid) if valid else 0.0

    ruff_regressions = sum(1 for r in valid if r.ruff_regression)
    mypy_regressions = sum(1 for r in valid if r.mypy_regression)
    max_drift_delta = max((r.drift_delta for r in valid), default=0.0)

    gate_pass, gate_failure_reasons = compute_gate(
        seed_results,
        min_median=min_median,
        min_positive_rate=min_positive_rate,
        drift_tolerance=drift_tolerance,
    )

    return EvaluationResult(
        src=src,
        mode=mode,
        seeds=seeds,
        seed_details=seed_results,
        median_improvement=median_imp,
        mean_improvement=mean_imp,
        positive_seed_rate=positive_rate,
        ruff_regressions=ruff_regressions,
        mypy_regressions=mypy_regressions,
        max_drift_delta=max_drift_delta,
        gate_pass=gate_pass,
        gate_failure_reasons=gate_failure_reasons,
        min_median=min_median,
        min_positive_rate=min_positive_rate,
        drift_tolerance=drift_tolerance,
        error_seeds=error_seeds,
    )


# ---------------------------------------------------------------------------
# Runner: spawns sub-processes for each seed
# ---------------------------------------------------------------------------


def run_seed(
    *,
    src: str,
    mode: str,
    seed: int,
    mcts_budget: int,
    ga_generations: int,
    ga_population: int,
    min_improvement: float,
    python: str,
) -> SeedResult:
    """Run quality loop for a single seed in dry-run mode; return SeedResult."""
    with tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w"
    ) as tmp:
        tmp_path = tmp.name

    cmd = [
        python, "-m", "scripts.quality_loop", "run",
        "--src", src,
        "--mode", mode,
        "--mcts-budget", str(mcts_budget),
        "--ga-generations", str(ga_generations),
        "--ga-population", str(ga_population),
        "--seed", str(seed),
        "--min-improvement", str(min_improvement),
        "--dry-run",
        "--exit-zero",
        "--output-json", tmp_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            return SeedResult.from_error(
                seed, f"exit_code={result.returncode}: {result.stderr[:500]}"
            )
        raw = Path(tmp_path).read_text(encoding="utf-8")
        d = json.loads(raw)
        return SeedResult.from_result_dict(seed, d)
    except subprocess.TimeoutExpired:
        return SeedResult.from_error(seed, "timeout after 600s")
    except Exception as exc:  # noqa: BLE001
        return SeedResult.from_error(seed, str(exc))
    finally:
        with contextlib.suppress(OSError):
            Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command("evaluate")
@click.option(
    "--src",
    default="src/drift",
    show_default=True,
    help="Source root to analyse (relative to cwd).",
)
@click.option(
    "--seeds",
    default="11,22,33,44,55",
    show_default=True,
    help="Comma-separated list of random seeds.",
)
@click.option(
    "--mode",
    type=click.Choice(["mcts", "genetic", "hybrid"]),
    default="mcts",
    show_default=True,
    help="Search mode.",
)
@click.option(
    "--mcts-budget",
    default=10,
    show_default=True,
    help="MCTS iterations per seed.",
)
@click.option(
    "--ga-generations",
    default=5,
    show_default=True,
    help="GA generations per seed.",
)
@click.option(
    "--ga-population",
    default=5,
    show_default=True,
    help="GA population size per seed.",
)
@click.option(
    "--min-improvement",
    default=0.01,
    show_default=True,
    help="Minimum composite score improvement to count as positive.",
)
@click.option(
    "--min-median",
    default=0.01,
    show_default=True,
    help="Gate: minimum required median improvement.",
)
@click.option(
    "--min-positive-rate",
    default=0.70,
    show_default=True,
    help="Gate: minimum fraction of seeds with positive improvement.",
)
@click.option(
    "--drift-tolerance",
    default=0.005,
    show_default=True,
    help="Gate: maximum allowed drift_score increase per seed.",
)
@click.option(
    "--output-json",
    default=None,
    help="Path to write the evaluation JSON (default: print to stdout).",
)
@click.option(
    "--exit-zero",
    is_flag=True,
    default=False,
    help="Always exit 0 (useful for report-only CI steps).",
)
@click.option(
    "--python",
    default=sys.executable,
    show_default=True,
    help="Python interpreter to use for sub-process runs.",
)
def evaluate_cmd(
    src: str,
    seeds: str,
    mode: str,
    mcts_budget: int,
    ga_generations: int,
    ga_population: int,
    min_improvement: float,
    min_median: float,
    min_positive_rate: float,
    drift_tolerance: float,
    output_json: str | None,
    exit_zero: bool,
    python: str,
) -> None:
    """Run multi-seed evaluation to validate quality-loop effectiveness."""
    seed_list = [int(s.strip()) for s in seeds.split(",") if s.strip()]
    click.echo(
        f"[evaluate] mode={mode} src={src} seeds={seed_list} "
        f"min_median={min_median} min_pos_rate={min_positive_rate}"
    )

    seed_results: list[SeedResult] = []
    for i, seed in enumerate(seed_list, 1):
        click.echo(f"[evaluate] running seed {seed} ({i}/{len(seed_list)})...")
        sr = run_seed(
            src=src,
            mode=mode,
            seed=seed,
            mcts_budget=mcts_budget,
            ga_generations=ga_generations,
            ga_population=ga_population,
            min_improvement=min_improvement,
            python=python,
        )
        status = "ERROR" if sr.error else f"improvement={sr.improvement:+.4f}"
        click.echo(f"[evaluate]   seed={seed} {status}")
        seed_results.append(sr)

    eval_result = aggregate(
        seed_results,
        min_median=min_median,
        min_positive_rate=min_positive_rate,
        drift_tolerance=drift_tolerance,
        src=src,
        mode=mode,
        seeds=seed_list,
    )

    result_dict = eval_result.to_dict()

    # Output
    if output_json:
        out_path = Path(output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result_dict, indent=2), encoding="utf-8")
        click.echo(f"[evaluate] Result written to {out_path}")
    else:
        click.echo(json.dumps(result_dict, indent=2))

    # Summary
    gate_str = "PASS" if eval_result.gate_pass else "FAIL"
    click.echo(
        f"[evaluate] median={eval_result.median_improvement:+.4f} "
        f"positive_rate={eval_result.positive_seed_rate:.0%} "
        f"ruff_regressions={eval_result.ruff_regressions} "
        f"mypy_regressions={eval_result.mypy_regressions} "
        f"gate={gate_str}"
    )
    if eval_result.gate_failure_reasons:
        for reason in eval_result.gate_failure_reasons:
            click.echo(f"[evaluate] GATE FAIL: {reason}", err=True)

    if not exit_zero and not eval_result.gate_pass:
        sys.exit(1)
