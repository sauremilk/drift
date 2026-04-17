"""Tests for ADR-005: Delta-First Score Interpretation."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from drift.analyzer import analyze_diff, analyze_repo
from drift.config import DriftConfig
from drift.models import RepoAnalysis, TrendContext
from drift.scoring.engine import delta_gate_pass

# ── TrendContext ──────────────────────────────────────────────────────────


class TestTrendContext:
    def test_baseline_when_no_history(self):
        from drift.analyzer import _build_trend_context

        ctx = _build_trend_context(0.45, [])
        assert ctx.direction == "baseline"
        assert ctx.previous_score is None
        assert ctx.delta is None
        assert ctx.recent_scores == []
        assert ctx.history_depth == 0

    def test_improving(self):
        from drift.analyzer import _build_trend_context

        history = [{"drift_score": 0.50}, {"drift_score": 0.48}]
        ctx = _build_trend_context(0.46, history)
        assert ctx.direction == "improving"
        assert ctx.previous_score == 0.48
        assert ctx.delta == pytest.approx(-0.02, abs=1e-4)
        assert ctx.history_depth == 2

    def test_degrading(self):
        from drift.analyzer import _build_trend_context

        history = [{"drift_score": 0.40}]
        ctx = _build_trend_context(0.42, history)
        assert ctx.direction == "degrading"
        assert ctx.delta == pytest.approx(0.02, abs=1e-4)

    def test_stable_within_noise_floor(self):
        from drift.analyzer import _build_trend_context

        history = [{"drift_score": 0.500}]
        ctx = _build_trend_context(0.503, history)
        assert ctx.direction == "stable"

    def test_recent_scores_capped_at_five(self):
        from drift.analyzer import _build_trend_context

        history = [{"drift_score": i * 0.01} for i in range(10)]
        ctx = _build_trend_context(0.10, history)
        assert len(ctx.recent_scores) == 5


# ── delta_gate_pass ───────────────────────────────────────────────────────


class TestDeltaGatePass:
    def test_no_history_always_passes(self):
        assert delta_gate_pass(0.99, [], fail_on_delta=0.01) is True

    def test_passes_within_budget(self):
        history = [{"drift_score": 0.40}, {"drift_score": 0.42}]
        # Mean = 0.41, current = 0.44 → Δ = +0.03, budget = 0.05 → pass
        assert delta_gate_pass(0.44, history, fail_on_delta=0.05) is True

    def test_fails_exceeding_budget(self):
        history = [{"drift_score": 0.40}, {"drift_score": 0.42}]
        # Mean = 0.41, current = 0.50 → Δ = +0.09, budget = 0.05 → fail
        assert delta_gate_pass(0.50, history, fail_on_delta=0.05) is False

    def test_improving_always_passes(self):
        history = [{"drift_score": 0.50}]
        # Δ = -0.10, any positive budget → pass
        assert delta_gate_pass(0.40, history, fail_on_delta=0.01) is True

    def test_window_limits_history(self):
        history = [{"drift_score": 0.90}] + [{"drift_score": 0.40}] * 5
        # window=5 → only last 5 scores (all 0.40), mean = 0.40
        # current = 0.42 → Δ = 0.02, budget = 0.05 → pass
        assert delta_gate_pass(0.42, history, fail_on_delta=0.05, window=5) is True

    def test_exact_boundary_passes(self):
        history = [{"drift_score": 0.40}]
        # Δ = 0.05 exactly == budget → passes (<=)
        assert delta_gate_pass(0.45, history, fail_on_delta=0.05) is True


# ── History persistence ───────────────────────────────────────────────────


class TestHistoryPersistence:
    def test_load_missing_file(self, tmp_path: Path):
        from drift.analyzer import _load_history

        assert _load_history(tmp_path / "nonexistent.json") == []

    def test_load_corrupt_file(self, tmp_path: Path):
        from drift.analyzer import _load_history

        bad = tmp_path / "bad.json"
        bad.write_text("not json!", encoding="utf-8")
        assert _load_history(bad) == []

    def test_roundtrip(self, tmp_path: Path):
        from drift.analyzer import _load_history, _save_history

        hfile = tmp_path / "history.json"
        data = [{"drift_score": 0.42, "timestamp": "2025-01-01T00:00:00"}]
        _save_history(hfile, data)
        loaded = _load_history(hfile)
        assert loaded == data

    def test_save_caps_at_100(self, tmp_path: Path):
        from drift.analyzer import _load_history, _save_history

        hfile = tmp_path / "history.json"
        data = [{"drift_score": i * 0.001} for i in range(150)]
        _save_history(hfile, data)
        loaded = _load_history(hfile)
        assert len(loaded) == 100
        assert loaded[0]["drift_score"] == pytest.approx(0.05)

    def test_save_keeps_repo_history_when_diff_is_high_volume(self, tmp_path: Path):
        """Issue #440: diff snapshots must not crowd out repo-scoped history."""
        from drift.analyzer import _load_history, _save_history

        hfile = tmp_path / "history.json"
        data = [{"drift_score": 0.2, "scope": "repo"}] + [
            {"drift_score": i * 0.001, "scope": "diff"} for i in range(150)
        ]

        _save_history(hfile, data)
        loaded = _load_history(hfile)

        repo_entries = [s for s in loaded if s.get("scope") != "diff"]
        diff_entries = [s for s in loaded if s.get("scope") == "diff"]

        assert len(repo_entries) == 1
        assert len(diff_entries) == 100


class TestAnalyzeDiffHistory:
    def _run_git(self, repo: Path, *args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
            },
        )

    def test_analyze_diff_persists_scoped_history(self, tmp_path: Path):
        repo = tmp_path / "repo"
        repo.mkdir(parents=True, exist_ok=True)

        target = repo / "pkg" / "mod.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("def fn(x):\n    return x\n", encoding="utf-8")

        self._run_git(repo, "init")
        self._run_git(repo, "add", ".")
        self._run_git(repo, "commit", "-m", "initial")

        target.write_text(
            "def fn(x):\n    if x < 0:\n        raise ValueError('neg')\n    return x\n",
            encoding="utf-8",
        )
        self._run_git(repo, "add", ".")
        self._run_git(repo, "commit", "-m", "change-1")

        cfg = DriftConfig(
            include=["**/*.py"],
            exclude=["**/.git/**", "**/.drift-cache/**"],
            embeddings_enabled=False,
        )

        first = analyze_diff(repo, config=cfg, diff_ref="HEAD~1", workers=1)
        assert first.trend is not None
        assert first.trend.direction == "baseline"
        assert first.trend.history_depth == 0

        history_file = repo / cfg.cache_dir / "history.json"
        history = json.loads(history_file.read_text(encoding="utf-8"))
        assert history[-1]["scope"] == "diff"

        # Seed a full-repo snapshot and ensure diff trend still stays scoped.
        history.append(
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "drift_score": 0.99,
                "signal_scores": {},
                "total_files": 1,
                "total_findings": 1,
                "scope": "repo",
            }
        )
        history_file.write_text(json.dumps(history), encoding="utf-8")

        target.write_text(
            "def fn(x):\n    if x < 0:\n        raise RuntimeError('neg')\n    return x\n",
            encoding="utf-8",
        )
        self._run_git(repo, "add", ".")
        self._run_git(repo, "commit", "-m", "change-2")

        second = analyze_diff(repo, config=cfg, diff_ref="HEAD~1", workers=1)
        assert second.trend is not None
        assert second.trend.history_depth >= 1
        assert second.trend.previous_score is not None

        updated_history = json.loads(history_file.read_text(encoding="utf-8"))
        diff_entries = [s for s in updated_history if s.get("scope") == "diff"]
        assert len(diff_entries) >= 2


class TestAnalyzeRepoHistoryScope:
    def test_analyze_repo_uses_legacy_and_repo_snapshots_for_repo_scope(self, tmp_path: Path):
        cfg = DriftConfig(
            include=["**/*.py"],
            exclude=["**/.git/**", "**/.drift-cache/**"],
            embeddings_enabled=False,
        )
        (tmp_path / "pkg").mkdir(parents=True, exist_ok=True)
        (tmp_path / "pkg" / "mod.py").write_text("def fn(x):\n    return x\n", encoding="utf-8")

        history_file = tmp_path / cfg.cache_dir / "history.json"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        history_file.write_text(
            json.dumps(
                [
                    {
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "drift_score": 0.20,
                        "signal_scores": {},
                        "total_files": 1,
                        "total_findings": 1,
                    },
                    {
                        "timestamp": "2026-01-02T00:00:00+00:00",
                        "drift_score": 0.70,
                        "signal_scores": {},
                        "total_files": 1,
                        "total_findings": 1,
                        "scope": "diff",
                    },
                    {
                        "timestamp": "2026-01-03T00:00:00+00:00",
                        "drift_score": 0.30,
                        "signal_scores": {},
                        "total_files": 1,
                        "total_findings": 1,
                        "scope": "repo",
                    },
                ]
            ),
            encoding="utf-8",
        )

        analysis = analyze_repo(tmp_path, config=cfg, workers=1)

        assert analysis.trend is not None
        # Legacy snapshots without scope must stay compatible and count as repo scope.
        assert analysis.trend.history_depth == 2

        updated = json.loads(history_file.read_text(encoding="utf-8"))
        assert updated[-1]["scope"] == "repo"
        assert len(updated) == 4


# ── Config ────────────────────────────────────────────────────────────────


class TestDeltaConfig:
    def test_default_delta_config(self):
        from drift.config import DriftConfig

        cfg = DriftConfig()
        assert cfg.fail_on_delta is None
        assert cfg.fail_on_delta_window == 5

    def test_load_delta_config_from_dict(self):
        from drift.config import DriftConfig

        cfg = DriftConfig.model_validate(
            {
                "fail_on_delta": 0.05,
                "fail_on_delta_window": 10,
            }
        )
        assert cfg.fail_on_delta == 0.05
        assert cfg.fail_on_delta_window == 10


# ── JSON output ───────────────────────────────────────────────────────────


class TestJsonTrendOutput:
    def _make_analysis(self, trend: TrendContext | None = None) -> RepoAnalysis:
        import datetime

        return RepoAnalysis(
            repo_path=Path("/tmp/test"),
            analyzed_at=datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC),
            drift_score=0.442,
            trend=trend,
        )

    def test_json_includes_trend(self):
        from drift.output.json_output import analysis_to_json

        trend = TrendContext(
            previous_score=0.457,
            delta=-0.015,
            direction="improving",
            recent_scores=[0.472, 0.457, 0.442],
            history_depth=3,
            transition_ratio=0.0,
        )
        raw = analysis_to_json(self._make_analysis(trend))
        data = json.loads(raw)
        assert data["trend"]["direction"] == "improving"
        assert data["trend"]["delta"] == -0.015
        assert data["trend"]["previous_score"] == 0.457
        assert len(data["trend"]["recent_scores"]) == 3

    def test_json_trend_null_when_no_trend(self):
        from drift.output.json_output import analysis_to_json

        raw = analysis_to_json(self._make_analysis(None))
        data = json.loads(raw)
        assert data["trend"] is None

    def test_sarif_includes_trend_properties(self):
        from drift.output.json_output import findings_to_sarif

        trend = TrendContext(
            previous_score=0.457,
            delta=-0.015,
            direction="improving",
            recent_scores=[0.472, 0.457, 0.442],
            history_depth=3,
            transition_ratio=0.0,
        )
        raw = findings_to_sarif(self._make_analysis(trend))
        data = json.loads(raw)
        run = data["runs"][0]
        assert "properties" in run
        assert run["properties"]["drift:trend"]["direction"] == "improving"

    def test_sarif_no_properties_for_baseline(self):
        from drift.output.json_output import findings_to_sarif

        trend = TrendContext(
            previous_score=None,
            delta=None,
            direction="baseline",
            recent_scores=[],
            history_depth=0,
            transition_ratio=0.0,
        )
        raw = findings_to_sarif(self._make_analysis(trend))
        data = json.loads(raw)
        run = data["runs"][0]
        assert "properties" in run
        assert run["properties"]["drift:analysisStatus"]["status"] == "complete"
        assert "drift:trend" not in run["properties"]
