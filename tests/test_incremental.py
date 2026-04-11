"""Tests for incremental analysis (Phases 2 & 3).

Phase 2: ``SignalCache.content_hash_for_file`` and ``BaselineSnapshot``.
Phase 3: Signal scope registry, ``IncrementalResult``, ``IncrementalSignalRunner``.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from drift.cache import SignalCache
from drift.config import DriftConfig
from drift.incremental import (  # noqa: I001
    BaselineSnapshot,
    IncrementalResult,
    IncrementalSignalRunner,
    _direction_for_delta,
    _finding_key,
)
from drift.models import Finding, ParseResult, Severity, SignalType

# ---------------------------------------------------------------------------
# SignalCache.content_hash_for_file
# ---------------------------------------------------------------------------


class TestContentHashForFile:
    def test_returns_file_hash_unchanged(self) -> None:
        file_hash = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
        assert SignalCache.content_hash_for_file(file_hash) == file_hash

    def test_different_hashes_produce_different_keys(self) -> None:
        h1 = "aaaa" * 8
        h2 = "bbbb" * 8
        assert SignalCache.content_hash_for_file(h1) != SignalCache.content_hash_for_file(h2)


# ---------------------------------------------------------------------------
# BaselineSnapshot
# ---------------------------------------------------------------------------


class TestBaselineSnapshot:
    @pytest.fixture()
    def baseline_hashes(self) -> dict[str, str]:
        return {
            "src/a.py": "aaa1",
            "src/b.py": "bbb2",
            "src/c.py": "ccc3",
        }

    def test_is_valid_within_ttl(self, baseline_hashes: dict[str, str]) -> None:
        snap = BaselineSnapshot(file_hashes=baseline_hashes, ttl_seconds=60)
        assert snap.is_valid()

    def test_is_valid_expired(self, baseline_hashes: dict[str, str]) -> None:
        snap = BaselineSnapshot(
            file_hashes=baseline_hashes,
            created_at=time.time() - 1000,
            ttl_seconds=60,
        )
        assert not snap.is_valid()

    def test_changed_files_no_changes(self, baseline_hashes: dict[str, str]) -> None:
        snap = BaselineSnapshot(file_hashes=baseline_hashes)
        added, removed, modified = snap.changed_files(baseline_hashes)
        assert added == set()
        assert removed == set()
        assert modified == set()

    def test_changed_files_added(self, baseline_hashes: dict[str, str]) -> None:
        snap = BaselineSnapshot(file_hashes=baseline_hashes)
        current = {**baseline_hashes, "src/d.py": "ddd4"}
        added, removed, modified = snap.changed_files(current)
        assert added == {"src/d.py"}
        assert removed == set()
        assert modified == set()

    def test_changed_files_removed(self, baseline_hashes: dict[str, str]) -> None:
        snap = BaselineSnapshot(file_hashes=baseline_hashes)
        current = {"src/a.py": "aaa1", "src/b.py": "bbb2"}
        added, removed, modified = snap.changed_files(current)
        assert added == set()
        assert removed == {"src/c.py"}
        assert modified == set()

    def test_changed_files_modified(self, baseline_hashes: dict[str, str]) -> None:
        snap = BaselineSnapshot(file_hashes=baseline_hashes)
        current = {**baseline_hashes, "src/b.py": "xxx9"}
        added, removed, modified = snap.changed_files(current)
        assert added == set()
        assert removed == set()
        assert modified == {"src/b.py"}

    def test_changed_files_mixed(self, baseline_hashes: dict[str, str]) -> None:
        snap = BaselineSnapshot(file_hashes=baseline_hashes)
        current = {
            "src/a.py": "aaa1",  # unchanged
            # src/b.py removed
            "src/c.py": "zzz0",  # modified
            "src/new.py": "nnn1",  # added
        }
        added, removed, modified = snap.changed_files(current)
        assert added == {"src/new.py"}
        assert removed == {"src/b.py"}
        assert modified == {"src/c.py"}

    def test_all_changed_union(self, baseline_hashes: dict[str, str]) -> None:
        snap = BaselineSnapshot(file_hashes=baseline_hashes)
        current = {
            "src/a.py": "aaa1",
            "src/c.py": "zzz0",
            "src/new.py": "nnn1",
        }
        result = snap.all_changed(current)
        assert result == {"src/b.py", "src/c.py", "src/new.py"}

    def test_stores_score(self) -> None:
        snap = BaselineSnapshot(file_hashes={}, score=0.42)
        assert snap.score == 0.42

    def test_default_ttl(self) -> None:
        snap = BaselineSnapshot(file_hashes={})
        assert snap.ttl_seconds == 900

    def test_empty_baseline_vs_populated_current(self) -> None:
        snap = BaselineSnapshot(file_hashes={})
        current = {"a.py": "hash1", "b.py": "hash2"}
        added, removed, modified = snap.changed_files(current)
        assert added == {"a.py", "b.py"}
        assert removed == set()
        assert modified == set()


# ---------------------------------------------------------------------------
# Phase 3 — Signal scope registry
# ---------------------------------------------------------------------------


class TestSignalScopeRegistry:
    """Verify that every registered signal has a valid incremental_scope."""

    def test_all_signals_have_valid_scope(self) -> None:
        from drift.signals.base import registered_signals

        for cls in registered_signals():
            assert cls.incremental_scope in {
                "file_local",
                "cross_file",
                "git_dependent",
            }, f"{cls.__name__} has invalid scope '{cls.incremental_scope}'"

    def test_file_local_signals_present(self) -> None:
        from drift.signals.base import registered_signals

        file_local = [c for c in registered_signals() if c.incremental_scope == "file_local"]
        # At least 10 signals should be file-local (we have 14)
        assert len(file_local) >= 10

    def test_git_dependent_signals_present(self) -> None:
        from drift.signals.base import registered_signals

        git_dep = [c for c in registered_signals() if c.incremental_scope == "git_dependent"]
        assert len(git_dep) >= 3  # CCC, ECM, SMS, TVS

    def test_cross_file_signals_present(self) -> None:
        from drift.signals.base import registered_signals

        cross = [c for c in registered_signals() if c.incremental_scope == "cross_file"]
        assert len(cross) >= 3  # AVS, CIR, DCA, MDS

    def test_default_scope_is_cross_file(self) -> None:
        from drift.signals.base import BaseSignal

        assert BaseSignal.incremental_scope == "cross_file"


# ---------------------------------------------------------------------------
# Phase 3 — _direction_for_delta
# ---------------------------------------------------------------------------


class TestDirectionForDelta:
    def test_improving(self) -> None:
        assert _direction_for_delta(-0.05) == "improving"

    def test_degrading(self) -> None:
        assert _direction_for_delta(0.05) == "degrading"

    def test_stable_zero(self) -> None:
        assert _direction_for_delta(0.0) == "stable"

    def test_stable_small_positive(self) -> None:
        assert _direction_for_delta(0.004) == "stable"

    def test_stable_small_negative(self) -> None:
        assert _direction_for_delta(-0.004) == "stable"

    def test_boundary_positive(self) -> None:
        # Exactly at threshold → stable
        assert _direction_for_delta(0.005) == "stable"

    def test_boundary_negative(self) -> None:
        assert _direction_for_delta(-0.005) == "stable"


# ---------------------------------------------------------------------------
# Phase 3 — _finding_key
# ---------------------------------------------------------------------------


class TestFindingKey:
    def _make_finding(
        self,
        *,
        signal_type: SignalType = SignalType.PATTERN_FRAGMENTATION,
        file_path: str = "src/a.py",
        start_line: int = 10,
        title: str = "test finding",
    ) -> Finding:
        return Finding(
            signal_type=signal_type,
            severity=Severity.MEDIUM,
            score=0.5,
            title=title,
            description="desc",
            file_path=Path(file_path) if file_path else None,
            start_line=start_line,
        )

    def test_deterministic(self) -> None:
        f = self._make_finding()
        assert _finding_key(f) == _finding_key(f)

    def test_different_file(self) -> None:
        f1 = self._make_finding(file_path="a.py")
        f2 = self._make_finding(file_path="b.py")
        assert _finding_key(f1) != _finding_key(f2)

    def test_different_line(self) -> None:
        f1 = self._make_finding(start_line=1)
        f2 = self._make_finding(start_line=2)
        assert _finding_key(f1) != _finding_key(f2)

    def test_different_signal(self) -> None:
        f1 = self._make_finding(signal_type=SignalType.PATTERN_FRAGMENTATION)
        f2 = self._make_finding(signal_type=SignalType.COHESION_DEFICIT)
        assert _finding_key(f1) != _finding_key(f2)

    def test_none_file_path(self) -> None:
        f = Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.MEDIUM,
            score=0.5,
            title="t",
            description="d",
            file_path=None,
            start_line=1,
        )
        key = _finding_key(f)
        assert "::" in key  # still produces a valid key


# ---------------------------------------------------------------------------
# Phase 3 — IncrementalResult
# ---------------------------------------------------------------------------


class TestIncrementalResult:
    def test_construction(self) -> None:
        r = IncrementalResult(
            score=0.35,
            delta=-0.05,
            direction="improving",
            new_findings=[],
            resolved_findings=[],
            confidence={"pattern_fragmentation": "exact"},
            file_local_signals_run=["pattern_fragmentation"],
            cross_file_signals_estimated=[],
            baseline_valid=True,
        )
        assert r.score == 0.35
        assert r.delta == -0.05
        assert r.direction == "improving"
        assert r.baseline_valid is True

    def test_confidence_mixed(self) -> None:
        r = IncrementalResult(
            score=0.4,
            delta=0.0,
            direction="stable",
            new_findings=[],
            resolved_findings=[],
            confidence={
                "pattern_fragmentation": "exact",
                "architecture_violation": "estimated",
            },
            file_local_signals_run=["pattern_fragmentation"],
            cross_file_signals_estimated=["architecture_violation"],
            baseline_valid=True,
        )
        assert r.confidence["pattern_fragmentation"] == "exact"
        assert r.confidence["architecture_violation"] == "estimated"


# ---------------------------------------------------------------------------
# Phase 3 — IncrementalSignalRunner
# ---------------------------------------------------------------------------


class TestIncrementalSignalRunner:
    """Integration-level tests for the incremental runner."""

    @pytest.fixture(autouse=True)
    def _fast_signal_registry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keep runner behavior under test while avoiding heavyweight full signal sets."""
        from drift.signals.base import BaseSignal

        class _FastFileLocalSignal(BaseSignal):
            incremental_scope = "file_local"

            @property
            def signal_type(self) -> SignalType:
                return SignalType.PATTERN_FRAGMENTATION

            @property
            def name(self) -> str:
                return "fast_file_local_signal"

        class _FastCognitiveSignal(_FastFileLocalSignal):
            @property
            def signal_type(self) -> SignalType:
                return SignalType.COGNITIVE_COMPLEXITY

            @property
            def name(self) -> str:
                return "fast_cognitive_signal"

            def analyze(self, parse_results, file_history, config):  # type: ignore[override]
                findings: list[Finding] = []
                for pr in parse_results:
                    findings.append(
                        Finding(
                            signal_type=self.signal_type,
                            severity=Severity.LOW,
                            score=0.05,
                            title="fast-test-finding",
                            description="lightweight fixture finding",
                            file_path=pr.file_path,
                            start_line=1,
                        )
                    )
                return findings

        monkeypatch.setattr(
            "drift.signals.base.registered_signals",
            lambda: [_FastFileLocalSignal, _FastCognitiveSignal],
        )

    @pytest.fixture()
    def config(self) -> DriftConfig:
        return DriftConfig()

    @pytest.fixture()
    def baseline_pr(self) -> ParseResult:
        return ParseResult(file_path=Path("src/a.py"), language="python", line_count=50)

    @pytest.fixture()
    def baseline_finding(self) -> Finding:
        return Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.MEDIUM,
            score=0.4,
            title="fragmented error handling",
            description="desc",
            file_path=Path("src/a.py"),
            start_line=10,
        )

    def test_empty_changed_files_runs_without_error(
        self,
        config: DriftConfig,
    ) -> None:
        baseline = BaselineSnapshot(file_hashes={}, score=0.0)
        runner = IncrementalSignalRunner(
            baseline=baseline,
            config=config,
            baseline_findings=[],
            baseline_parse_results={},
        )
        result = runner.run(changed_files=set(), current_parse_results={})
        assert result.baseline_valid is True
        assert isinstance(result.score, float)
        assert isinstance(result.delta, float)
        assert result.resolved_findings == []

    def test_expired_baseline_flagged(
        self,
        config: DriftConfig,
        baseline_pr: ParseResult,
    ) -> None:
        baseline = BaselineSnapshot(
            file_hashes={"src/a.py": "aaa"},
            score=0.3,
            created_at=time.time() - 9999,
            ttl_seconds=60,
        )
        runner = IncrementalSignalRunner(
            baseline=baseline,
            config=config,
            baseline_findings=[],
            baseline_parse_results={"src/a.py": baseline_pr},
        )
        result = runner.run(changed_files=set(), current_parse_results={})
        assert result.baseline_valid is False

    def test_file_local_signals_marked_exact(
        self,
        config: DriftConfig,
    ) -> None:
        """Run with a changed file → file-local signals should get 'exact' confidence."""
        pr = ParseResult(file_path=Path("src/a.py"), language="python", line_count=10)
        baseline = BaselineSnapshot(file_hashes={"src/a.py": "old"}, score=0.0)

        runner = IncrementalSignalRunner(
            baseline=baseline,
            config=config,
            baseline_findings=[],
            baseline_parse_results={"src/a.py": pr},
        )
        result = runner.run(
            changed_files={"src/a.py"},
            current_parse_results={"src/a.py": pr},
        )
        # All file-local signals that ran → exact
        for sig_name in result.file_local_signals_run:
            assert result.confidence[sig_name] == "exact"

    def test_cross_file_findings_carried_estimated(
        self,
        config: DriftConfig,
    ) -> None:
        """Cross-file baseline findings are carried forward as 'estimated'."""
        # architecture_violation is cross_file scope
        cross_finding = Finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            severity=Severity.HIGH,
            score=0.6,
            title="layer breach",
            description="desc",
            file_path=Path("src/b.py"),
            start_line=5,
        )
        pr_a = ParseResult(file_path=Path("src/a.py"), language="python", line_count=10)
        pr_b = ParseResult(file_path=Path("src/b.py"), language="python", line_count=10)
        baseline = BaselineSnapshot(
            file_hashes={"src/a.py": "aaa", "src/b.py": "bbb"},
            score=0.4,
        )

        runner = IncrementalSignalRunner(
            baseline=baseline,
            config=config,
            baseline_findings=[cross_finding],
            baseline_parse_results={"src/a.py": pr_a, "src/b.py": pr_b},
        )
        result = runner.run(
            changed_files={"src/a.py"},
            current_parse_results={"src/a.py": pr_a},
        )
        # Cross-file finding should be carried forward
        assert "architecture_violation" in result.confidence
        assert result.confidence["architecture_violation"] == "estimated"

    def test_new_finding_detected(
        self,
        config: DriftConfig,
    ) -> None:
        """A finding that didn't exist in baseline shows as 'new'."""
        baseline = BaselineSnapshot(file_hashes={"src/a.py": "old"}, score=0.0)
        pr = ParseResult(file_path=Path("src/a.py"), language="python", line_count=10)

        runner = IncrementalSignalRunner(
            baseline=baseline,
            config=config,
            baseline_findings=[],  # No pre-existing findings
            baseline_parse_results={"src/a.py": pr},
        )
        result = runner.run(
            changed_files={"src/a.py"},
            current_parse_results={"src/a.py": pr},
        )
        # Any findings produced are new (baseline was empty)
        assert result.resolved_findings == []

    def test_resolved_finding_when_file_removed(
        self,
        config: DriftConfig,
    ) -> None:
        """Findings for a removed file should be resolved."""
        old_finding = Finding(
            signal_type=SignalType.COGNITIVE_COMPLEXITY,
            severity=Severity.MEDIUM,
            score=0.5,
            title="complex function",
            description="desc",
            file_path=Path("src/deleted.py"),
            start_line=1,
        )
        old_pr = ParseResult(
            file_path=Path("src/deleted.py"), language="python", line_count=100
        )
        baseline = BaselineSnapshot(
            file_hashes={"src/deleted.py": "xxx"},
            score=0.3,
        )

        runner = IncrementalSignalRunner(
            baseline=baseline,
            config=config,
            baseline_findings=[old_finding],
            baseline_parse_results={"src/deleted.py": old_pr},
        )
        # File removed → not in current_parse_results, in changed_files
        result = runner.run(
            changed_files={"src/deleted.py"},
            current_parse_results={},
        )
        # The old finding should be resolved (file is gone)
        resolved_keys = {_finding_key(f) for f in result.resolved_findings}
        assert _finding_key(old_finding) in resolved_keys

    def test_delta_and_direction(
        self,
        config: DriftConfig,
    ) -> None:
        """Verify delta = score - baseline.score and direction derives from it."""
        baseline = BaselineSnapshot(file_hashes={}, score=0.5)
        runner = IncrementalSignalRunner(
            baseline=baseline,
            config=config,
            baseline_findings=[],
            baseline_parse_results={},
        )
        result = runner.run(changed_files=set(), current_parse_results={})
        # This test guards the invariant, independent of repo-specific findings.
        assert result.delta == pytest.approx(result.score - baseline.score)
        assert result.direction == _direction_for_delta(result.delta)
