"""Hybrid MCTS + GA orchestrator for autonomous code quality improvement."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from scripts.quality_loop.genetic.individual import Op
from scripts.quality_loop.genetic.population import Population
from scripts.quality_loop.mcts.search import MCTSResult, MCTSSearch
from scripts.quality_loop.metric import CompositeMetric
from scripts.quality_loop.snapshot import Snapshot
from scripts.quality_loop.transforms import apply_transform


@dataclass
class PhaseResult:
    mode: str
    baseline_score: float
    best_score: float
    improvement: float
    duration_seconds: float
    details: dict = field(default_factory=dict)


@dataclass
class OrchestratorResult:
    """Full result from a HybridOrchestrator.run() call."""

    mode: str  # "mcts" | "genetic" | "hybrid"
    baseline_score: float
    final_score: float
    improvement: float
    applied: bool  # Whether changes were written to disk
    duration_seconds: float
    phases: list[PhaseResult] = field(default_factory=list)
    best_sequence: list[str] = field(default_factory=list)  # Human-readable ops
    # Seed used for this run (None = unseeded)
    seed: int | None = None
    # Per-component baseline metrics
    baseline_ruff: int = 0
    baseline_mypy: int = 0
    baseline_drift: float = 0.0
    # Per-component final metrics (after apply, or best-case in dry-run)
    final_ruff: int = 0
    final_mypy: int = 0
    final_drift: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


class HybridOrchestrator:
    """Orchestrates MCTS → GA pipeline for code quality improvement.

    Workflow:
    1. Measure baseline composite score.
    2. Run MCTS phase (budget_mcts iterations).
    3. Seed GA initial population with top MCTS sequences.
    4. Run GA phase (budget_ga_gen generations × budget_ga_pop population).
    5. Apply best sequence if improvement >= min_improvement.
    6. Return OrchestratorResult with full telemetry.
    """

    def __init__(
        self,
        src_root: Path,
        mode: str = "hybrid",
        budget_mcts: int = 50,
        budget_ga_gen: int = 20,
        budget_ga_pop: int = 10,
        min_improvement: float = 0.01,
        dry_run: bool = False,
        seed: int | None = None,
    ) -> None:
        self._src_root = src_root
        self._mode = mode
        self._budget_mcts = budget_mcts
        self._budget_ga_gen = budget_ga_gen
        self._budget_ga_pop = budget_ga_pop
        self._min_improvement = min_improvement
        self._dry_run = dry_run
        self._seed = seed
        self._metric = CompositeMetric(repo_root=src_root, src_path=src_root)

    def run(self) -> OrchestratorResult:
        start = time.monotonic()

        # ── Baseline ────────────────────────────────────────────────────
        baseline_result = self._metric.measure()
        baseline_score = baseline_result.composite
        src_files = sorted(self._src_root.rglob("*.py"))
        base_snapshot = Snapshot.capture(src_files)

        phases: list[PhaseResult] = []
        best_sequence: list[Op] = []
        best_score = baseline_score

        # ── MCTS Phase ──────────────────────────────────────────────────
        mcts_result: MCTSResult | None = None
        if self._mode in ("mcts", "hybrid"):
            t0 = time.monotonic()
            searcher = MCTSSearch(
                src_root=self._src_root,
                metric=self._metric,
                budget=self._budget_mcts,
                seed=self._seed,
            )
            mcts_result = searcher.run()
            base_snapshot.restore()  # Ensure filesystem is clean after MCTS

            phases.append(
                PhaseResult(
                    mode="mcts",
                    baseline_score=baseline_score,
                    best_score=mcts_result.best_score,
                    improvement=mcts_result.improvement,
                    duration_seconds=time.monotonic() - t0,
                    details={"iterations": mcts_result.iterations_run},
                )
            )

            if mcts_result.best_score < best_score:
                best_score = mcts_result.best_score
                best_sequence = mcts_result.best_sequence

        # ── GA Phase ────────────────────────────────────────────────────
        if self._mode in ("genetic", "hybrid"):
            t0 = time.monotonic()

            # Seed initial population
            seed_seqs: list[list[Op]] = []
            if mcts_result is not None and mcts_result.best_sequence:
                seed_seqs = [mcts_result.best_sequence]

            population = Population.initialize(
                src_files=src_files,
                size=self._budget_ga_pop,
                seed_sequences=seed_seqs,
            )

            gen_stats: list[dict] = []
            for gen in range(self._budget_ga_gen):
                population.evaluate_all(
                    base_snapshot=base_snapshot,
                    metric=self._metric,
                    max_workers=4,
                )
                base_snapshot.restore()  # Clean up after parallel evaluation
                stats = population.stats()
                gen_stats.append(
                    {
                        "generation": gen,
                        "best": stats.best_fitness,
                        "mean": stats.mean_fitness,
                        "diversity": stats.diversity,
                    }
                )
                population = population.evolve(src_files=src_files)

            # Evaluate final generation
            population.evaluate_all(
                base_snapshot=base_snapshot,
                metric=self._metric,
                max_workers=4,
            )
            base_snapshot.restore()

            ga_best = population.best()
            ga_best_score = (
                ga_best.fitness
                if ga_best and ga_best.fitness is not None
                else float("inf")
            )

            phases.append(
                PhaseResult(
                    mode="genetic",
                    baseline_score=baseline_score,
                    best_score=ga_best_score,
                    improvement=baseline_score - ga_best_score,
                    duration_seconds=time.monotonic() - t0,
                    details={
                        "generations": self._budget_ga_gen,
                        "population_size": self._budget_ga_pop,
                        "gen_stats": gen_stats,
                    },
                )
            )

            if ga_best and ga_best.fitness is not None and ga_best.fitness < best_score:
                best_score = ga_best.fitness
                best_sequence = ga_best.program

        # ── Apply ────────────────────────────────────────────────────────
        improvement = baseline_score - best_score
        applied = False

        if improvement >= self._min_improvement and not self._dry_run and best_sequence:
            base_snapshot.restore()
            for transform_cls, target_file in best_sequence:
                apply_transform(transform_cls, target_file)
            applied = True
        else:
            # Always restore clean state
            base_snapshot.restore()

        # ── Final component metrics ──────────────────────────────────────
        # Measure post-apply metrics so the caller can detect regressions.
        # * applied=True  → changes are on disk; measure directly.
        # * dry_run=True  → temporarily apply, measure, then restore so the
        #                   evaluator gets per-component delta without side effects.
        # * no improvement → final = baseline (no changes were made).
        if applied:
            final_result = self._metric.measure()
        elif best_sequence and improvement >= self._min_improvement:
            # Dry-run branch: apply temporarily for measurement only.
            for transform_cls, target_file in best_sequence:
                apply_transform(transform_cls, target_file)
            final_result = self._metric.measure()
            base_snapshot.restore()
        else:
            final_result = baseline_result

        # ── Result ───────────────────────────────────────────────────────
        readable_sequence = [
            f"{t.name}@{f.relative_to(self._src_root)}"
            for t, f in best_sequence
        ]

        return OrchestratorResult(
            mode=self._mode,
            baseline_score=baseline_score,
            final_score=best_score,
            improvement=improvement,
            applied=applied,
            duration_seconds=time.monotonic() - start,
            phases=phases,
            best_sequence=readable_sequence,
            seed=self._seed,
            baseline_ruff=baseline_result.ruff_count,
            baseline_mypy=baseline_result.mypy_count,
            baseline_drift=baseline_result.drift_score,
            final_ruff=final_result.ruff_count,
            final_mypy=final_result.mypy_count,
            final_drift=final_result.drift_score,
        )
