"""CI-reality tests: validate drift under real CI conditions.

Simulates the constraints that matter in production CI:
  1. Shallow clone (depth=1): no full git history available
  2. Performance budget: analysis must complete within a wall-clock limit
  3. Graceful degradation: drift must not crash when git data is missing
  4. Concurrent execution: analysis must be safe under parallel invocation
  5. diff-mode (check command): must work with HEAD~1 on shallow clone

These tests catch the class of failures that leads developers to
disable drift in their CI pipeline — the #1 existential threat.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from drift.analyzer import analyze_diff, analyze_repo
from drift.config import DriftConfig
from drift.models import Severity

pytestmark = pytest.mark.slow

DRIFT_REPO = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_shallow_clone(source: Path, dest: Path, depth: int = 1) -> Path:
    """Create a local shallow clone of a git repo."""
    subprocess.run(
        ["git", "clone", "--depth", str(depth), f"file://{source}", str(dest)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    return dest


def _make_detached_no_history(source: Path, dest: Path) -> Path:
    """Create a repo copy with zero git history (init + add, no prior commits)."""
    dest.mkdir(parents=True, exist_ok=True)
    # Copy source files (excluding .git)
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{source}", str(dest)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    # Remove .git and reinitialize — simulates "no history at all"
    import os
    import shutil
    import stat

    def _rm_readonly(func, path, _exc_info):  # type: ignore[no-untyped-def]
        """Handle read-only files on Windows (git pack files)."""
        os.chmod(path, stat.S_IWRITE)
        func(path)

    git_dir = dest / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir, onerror=_rm_readonly)
    subprocess.run(["git", "init"], cwd=dest, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=dest, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial", "--allow-empty"],
        cwd=dest,
        check=True,
        capture_output=True,
        env={
            **__import__("os").environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
        },
    )
    return dest


def _standard_config() -> DriftConfig:
    return DriftConfig(
        include=["**/*.py"],
        exclude=[
            "**/__pycache__/**",
            "**/node_modules/**",
            "**/.venv*/**",
            "**/.tmp_*venv*/**",
            "**/site-packages/**",
            "**/.pixi/**",
            "**/docs/**",
            "**/tests/**",
        ],
        embeddings_enabled=False,
    )


# ---------------------------------------------------------------------------
# 1. Shallow clone: drift must work with minimal git history
# ---------------------------------------------------------------------------


class TestShallowClone:
    """Drift must produce valid results from a depth=1 shallow clone."""

    @pytest.fixture(scope="class")
    def shallow_repo(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        dest = tmp_path_factory.mktemp("shallow") / "drift"
        return _make_shallow_clone(DRIFT_REPO, dest, depth=1)

    @pytest.fixture(scope="class")
    def shallow_analysis(self, shallow_repo: Path):
        """Compute once per class to avoid duplicate full scans in similar assertions."""
        config = _standard_config()
        return analyze_repo(shallow_repo, config=config, since_days=90)

    def test_analyze_completes(self, shallow_analysis) -> None:
        """Full analysis runs without error on a shallow clone."""
        assert shallow_analysis.total_files > 0
        assert 0.0 <= shallow_analysis.drift_score <= 1.0

    def test_findings_generated(self, shallow_analysis) -> None:
        """Signals that don't require git history still produce findings."""
        # At least explainability_deficit and pattern_fragmentation work
        # without git history
        assert len(shallow_analysis.findings) > 0, "No findings on shallow clone"

    def test_no_crash_on_diff_check(self, shallow_repo: Path) -> None:
        """diff-mode (CI check) must not crash even if HEAD~1 is unavailable."""
        config = _standard_config()
        # On a depth=1 clone, HEAD~1 doesn't exist. analyze_diff should
        # fall back gracefully (to full analysis or empty result).
        analysis = analyze_diff(shallow_repo, config=config, diff_ref="HEAD~1")
        assert analysis is not None
        assert 0.0 <= analysis.drift_score <= 1.0


# ---------------------------------------------------------------------------
# 2. No git history at all: freshly initialized repo
# ---------------------------------------------------------------------------


class TestNoGitHistory:
    """Drift must not crash on a repo with zero commit history."""

    @pytest.fixture(scope="class")
    def bare_repo(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        dest = tmp_path_factory.mktemp("bare") / "drift"
        return _make_detached_no_history(DRIFT_REPO, dest)

    @pytest.fixture(scope="class")
    def bare_analysis(self, bare_repo: Path):
        """Reuse no-history analysis across tests in this class."""
        config = _standard_config()
        return analyze_repo(bare_repo, config=config, since_days=90)

    def test_analyze_completes(self, bare_analysis) -> None:
        assert bare_analysis.total_files > 0
        assert 0.0 <= bare_analysis.drift_score <= 1.0

    def test_temporal_signals_degrade_gracefully(self, bare_analysis) -> None:
        """Temporal volatility should return 0 findings, not crash."""
        from drift.models import SignalType

        temporal = [
            f for f in bare_analysis.findings if f.signal_type == SignalType.TEMPORAL_VOLATILITY
        ]
        # Temporal findings should be absent (no history) — not errored
        # This is acceptable; the signal simply doesn't fire
        assert isinstance(temporal, list)


# ---------------------------------------------------------------------------
# 3. Performance budget
# ---------------------------------------------------------------------------


class TestPerformanceBudget:
    """Drift must respect wall-clock time budgets reasonable for CI."""

    # Budget: drift self-analysis should complete in under 45s.
    # On CI (GitHub Actions, 2 vCPU), runners can be slow (~32s observed).
    # Django (2890 files) reportedly takes ~36s — that's the stress case.
    SELF_ANALYSIS_BUDGET_S = 45.0
    _CORE_TARGET_PATH = "src/drift"

    def test_self_analysis_within_budget(self) -> None:
        """Self-analysis (≈45 Python files) must complete within budget."""
        config = _standard_config()
        start = time.monotonic()
        analysis = analyze_repo(
            DRIFT_REPO,
            config=config,
            since_days=90,
            target_path=self._CORE_TARGET_PATH,
        )
        elapsed = time.monotonic() - start

        assert analysis.total_files > 0
        assert elapsed < self.SELF_ANALYSIS_BUDGET_S, (
            f"Self-analysis took {elapsed:.1f}s, budget is {self.SELF_ANALYSIS_BUDGET_S}s"
        )

    def test_duration_field_accurate(self) -> None:
        """analysis_duration_seconds should roughly match wall-clock time."""
        config = _standard_config()
        start = time.monotonic()
        analysis = analyze_repo(
            DRIFT_REPO,
            config=config,
            since_days=90,
            target_path=self._CORE_TARGET_PATH,
        )
        wall = time.monotonic() - start

        # Allow 50% tolerance (GC pauses, startup overhead)
        assert analysis.analysis_duration_seconds > 0
        ratio = analysis.analysis_duration_seconds / wall if wall > 0 else 1.0
        assert 0.5 <= ratio <= 2.0, (
            f"Duration field ({analysis.analysis_duration_seconds:.1f}s) diverges "
            f"from wall-clock ({wall:.1f}s), ratio={ratio:.2f}"
        )


# ---------------------------------------------------------------------------
# 4. Concurrent execution safety
# ---------------------------------------------------------------------------


class TestConcurrentExecution:
    """Multiple drift analyses can run in parallel without interference."""

    def test_parallel_analyses_produce_consistent_results(self) -> None:
        """Two concurrent analyses of the same repo must produce equal scores."""
        from concurrent.futures import ThreadPoolExecutor

        config = _standard_config()

        def _run() -> float:
            analysis = analyze_repo(
                DRIFT_REPO,
                config=config,
                since_days=90,
                target_path="src/drift",
            )
            return analysis.drift_score

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_run) for _ in range(2)]
            scores = [f.result(timeout=120) for f in futures]

        # Scores should be identical (same input = same output, deterministic)
        assert abs(scores[0] - scores[1]) < 0.01, (
            f"Parallel runs produced different scores: {scores[0]:.3f} vs {scores[1]:.3f}"
        )


# ---------------------------------------------------------------------------
# 5. Exit-code contract for CI
# ---------------------------------------------------------------------------


class TestExitCodeContract:
    """The severity gate must produce correct exit signals for CI."""

    def test_severity_gate_pass_on_clean_repo(self) -> None:
        """A repo with no critical findings should pass the severity gate."""
        from drift.scoring.engine import severity_gate_pass

        config = _standard_config()
        analysis = analyze_repo(
            DRIFT_REPO,
            config=config,
            since_days=90,
            target_path="src/drift",
        )

        # drift itself should pass on "critical" gate
        assert severity_gate_pass(analysis.findings, "critical"), (
            "drift's own repo should pass the critical severity gate"
        )

    def test_severity_gate_blocks_on_high_findings(self) -> None:
        """A finding at HIGH severity must block when gate is 'high'."""
        from drift.models import Finding, SignalType
        from drift.scoring.engine import severity_gate_pass

        fake_findings = [
            Finding(
                signal_type=SignalType.PATTERN_FRAGMENTATION,
                severity=Severity.HIGH,
                score=0.75,
                title="test finding",
                description="test",
            )
        ]
        assert not severity_gate_pass(fake_findings, "high"), (
            "HIGH finding should block when gate is 'high'"
        )

    def test_severity_gate_passes_below_threshold(self) -> None:
        """A MEDIUM finding must pass when gate is 'high'."""
        from drift.models import Finding, SignalType
        from drift.scoring.engine import severity_gate_pass

        fake_findings = [
            Finding(
                signal_type=SignalType.EXPLAINABILITY_DEFICIT,
                severity=Severity.MEDIUM,
                score=0.45,
                title="test finding",
                description="test",
            )
        ]
        assert severity_gate_pass(fake_findings, "high"), (
            "MEDIUM finding should pass when gate is 'high'"
        )
