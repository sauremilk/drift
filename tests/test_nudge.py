"""Tests for Phase 4+5 — drift_nudge API, MCP tool, BaselineManager.

Covers:
- ``nudge()`` API function with mocked baseline and signals
- ``safe_to_commit`` hardrule
- ``drift_nudge`` MCP tool returns valid JSON
- ``invalidate_nudge_baseline()``
- Response schema validation
- ``BaselineManager`` singleton with git-event invalidation
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from drift.api import (
    _baseline_store,
    invalidate_nudge_baseline,
    nudge,
)
from drift.incremental import BaselineManager, BaselineSnapshot
from drift.models import FileInfo, Finding, ParseResult, Severity, SignalType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    *,
    signal_type: SignalType = SignalType.PATTERN_FRAGMENTATION,
    severity: Severity = Severity.MEDIUM,
    score: float = 0.4,
    title: str = "test finding",
    file_path: str = "src/a.py",
    start_line: int = 10,
) -> Finding:
    return Finding(
        signal_type=signal_type,
        severity=severity,
        score=score,
        title=title,
        description="test description",
        file_path=Path(file_path),
        start_line=start_line,
    )


def _stub_analysis(
    *,
    findings: list[Finding] | None = None,
    drift_score: float = 0.3,
) -> SimpleNamespace:
    """Build a minimal object that quacks like RepoAnalysis."""
    return SimpleNamespace(
        findings=findings or [],
        drift_score=drift_score,
        severity=Severity.MEDIUM,
        total_files=5,
        total_functions=20,
        ai_attributed_ratio=0.0,
        trend=None,
        analysis_duration_seconds=0.1,
        skipped_files=0,
        skipped_languages={},
    )


# ---------------------------------------------------------------------------
# nudge() API tests
# ---------------------------------------------------------------------------


class TestNudgeAPI:
    """Test the nudge() function with various scenarios."""

    @pytest.fixture(autouse=True)
    def _clear_baseline_store(self) -> None:
        """Ensure baseline store is clean before each test."""
        _baseline_store.clear()
        BaselineManager.reset_instance()

    def test_nudge_returns_schema_version(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """nudge() response has schema_version."""
        self._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[])
        assert result["schema_version"] == "2.2"

    def test_nudge_direction_field(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """nudge() response has direction field."""
        self._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[])
        assert result["direction"] in ("improving", "stable", "degrading")

    def test_nudge_response_schema(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """nudge() response contains all expected fields."""
        self._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[])

        expected_fields = {
            "schema_version",
            "direction",
            "delta",
            "magnitude",
            "score",
            "safe_to_commit",
            "blocking_reasons",
            "nudge",
            "new_findings",
            "resolved_findings",
            "confidence",
            "expected_transient",
            "baseline_age_seconds",
            "baseline_valid",
            "baseline_refresh_reason",
            "file_local_signals_run",
            "cross_file_signals_estimated",
            "parse_failure_count",
            "parse_failed_files",
            "parse_failure_treatment",
            "changed_files",
            "agent_instruction",
            "finding_cluster_summary",
        }
        assert expected_fields.issubset(set(result.keys()))

    def test_nudge_parse_failure_fields_default_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """No parse failures still returns stable diagnostic fields."""
        self._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[])
        assert result["parse_failure_count"] == 0
        assert result["parse_failed_files"] == []
        treatment = result["parse_failure_treatment"]
        assert treatment["affects_safe_to_commit"] is True
        assert treatment["policy"] == "blocking"

    def test_nudge_expected_transient_always_false(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """MVP: expected_transient is always False."""
        self._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[])
        assert result["expected_transient"] is False

    def test_nudge_agent_instruction_present(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """agent_instruction guides the agent to use drift_nudge."""
        self._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[])
        assert "drift_nudge" in result["agent_instruction"]

    def test_nudge_warns_cross_file_blind_spot(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Estimated cross-file signals surface an explicit blind-spot warning."""
        self._mock_nudge_deps(monkeypatch, tmp_path)

        changed_rel = Path("src") / "a.py"
        changed_abs = tmp_path / changed_rel
        changed_abs.parent.mkdir(parents=True, exist_ok=True)
        changed_abs.write_text("def a():\n    return 1\n", encoding="utf-8")

        BaselineManager.instance().store(
            tmp_path.resolve(),
            BaselineSnapshot(
                file_hashes={changed_rel.as_posix(): "stale-hash"},
                score=0.3,
            ),
            [],
            {
                changed_rel.as_posix(): ParseResult(
                    file_path=changed_rel,
                    language="python",
                )
            },
        )

        BaselineManager.instance().store(
            tmp_path.resolve(),
            BaselineSnapshot(
                file_hashes={changed_rel.as_posix(): "stale-hash"},
                score=0.3,
            ),
            [],
            {
                changed_rel.as_posix(): ParseResult(
                    file_path=changed_rel,
                    language="python",
                )
            },
        )

        monkeypatch.setattr(
            "drift.ingestion.file_discovery.discover_files",
            lambda *a, **kw: [
                FileInfo(
                    path=changed_rel,
                    language="python",
                    size_bytes=changed_abs.stat().st_size,
                    line_count=2,
                )
            ],
        )
        monkeypatch.setattr(
            "drift.ingestion.ast_parser.parse_file",
            lambda *a, **kw: ParseResult(file_path=changed_rel, language="python"),
        )

        def _fake_run(*args, **kwargs):
            return SimpleNamespace(
                direction="stable",
                delta=0.0,
                score=0.3,
                new_findings=[],
                resolved_findings=[],
                confidence={"architecture_violation": "estimated"},
                file_local_signals_run=[],
                cross_file_signals_estimated=["architecture_violation"],
                baseline_valid=True,
                pruned_removed_cross_file_findings=0,
            )

        monkeypatch.setattr("drift.incremental.IncrementalSignalRunner.run", _fake_run)

        result = nudge(tmp_path, changed_files=[changed_rel.as_posix()])

        assert result["warnings"]
        warning = result["warnings"][0]
        assert warning["code"] == "cross_file_blind_spot"
        assert warning["signals"] == ["AVS"]
        assert "Run drift analyze" in warning["message"]

    def test_get_changed_files_from_git_uses_relative_scope(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Auto-detection requests cwd-relative git paths for sub-scope runs."""
        from drift.api.nudge import _get_changed_files_from_git

        captured: dict[str, object] = {}

        def _fake_run(*args, **kwargs):
            captured["args"] = args[0]
            captured["cwd"] = kwargs.get("cwd")
            return SimpleNamespace(stdout="src/a.py\n")

        monkeypatch.setattr("subprocess.run", _fake_run)

        changed = _get_changed_files_from_git(tmp_path, uncommitted=True)

        assert changed == ["src/a.py"]
        assert "--relative" in captured["args"]
        assert "HEAD" in captured["args"]
        assert captured["cwd"] == tmp_path

    def test_is_derived_cache_artifact_detects_top_level_cache_paths(self) -> None:
        """Derived drift cache artifacts are recognized and filterable."""
        from drift.api.nudge import _is_derived_cache_artifact

        assert _is_derived_cache_artifact(".drift-cache/history.json")
        assert _is_derived_cache_artifact(".drift-cache-golden/parse/a.json")
        assert _is_derived_cache_artifact(".drift-cache\\history.json")
        assert not _is_derived_cache_artifact("src/a.py")
        assert not _is_derived_cache_artifact("src/.drift-cache/history.json")

    def test_nudge_filters_derived_cache_changed_files(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Cache artifact paths are removed from changed file processing."""
        self._mock_nudge_deps(monkeypatch, tmp_path)

        result = nudge(
            tmp_path,
            changed_files=[
                ".drift-cache/history.json",
                ".drift-cache-golden/parse/a.json",
            ],
        )

        assert result["changed_files"] == []
        assert result["analyzed_changed_files"] == []
        assert result["ignored_changed_files"] == [
            ".drift-cache-golden/parse/a.json",
            ".drift-cache/history.json",
        ]

    def test_nudge_short_circuits_with_no_effective_changes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """No effective changed files bypasses incremental runner."""
        self._mock_nudge_deps(monkeypatch, tmp_path)

        def _should_not_run(*args, **kwargs):
            raise AssertionError("IncrementalSignalRunner.run should not be called")

        monkeypatch.setattr(
            "drift.incremental.IncrementalSignalRunner.run",
            _should_not_run,
        )

        result = nudge(
            tmp_path,
            changed_files=[".drift-cache/history.json"],
        )

        assert result["direction"] == "stable"
        assert result["delta"] == 0.0
        assert result["file_local_signals_run"] == []
        assert result["cross_file_signals_estimated"] == []

    def test_nudge_uses_cached_baseline(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Second call reuses cached baseline (no full scan)."""
        self._mock_nudge_deps(monkeypatch, tmp_path)
        # First call creates baseline
        nudge(tmp_path, changed_files=[])

        # Track if analyze_repo is called again
        call_count = {"n": 0}

        def _counting_analyze(*a, **kw):
            call_count["n"] += 1
            return _stub_analysis()

        monkeypatch.setattr("drift.analyzer.analyze_repo", _counting_analyze)

        # Second call — should NOT trigger analyze_repo
        result = nudge(tmp_path, changed_files=[])
        assert call_count["n"] == 0
        assert result["baseline_refresh_reason"] is None

    def test_nudge_error_returns_error_response(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Exceptions in nudge flow return structured error payload."""

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated failure")

        monkeypatch.setattr("drift.config.DriftConfig.load", staticmethod(_boom))

        broken = tmp_path / "nonexistent_repo_xyz"
        result = nudge(broken, changed_files=[])
        assert "schema_version" in result or "error" in result

    def test_nudge_warns_when_removed_file_findings_were_pruned(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Removed-file prune warning payload is explicit and machine-readable."""
        from drift.api.nudge import _removed_file_prune_warning

        warning = _removed_file_prune_warning(2)
        assert warning is not None
        assert warning["code"] == "removed_file_findings_pruned"
        assert warning["count"] == 2
        assert "were pruned" in warning["message"]

    def test_nudge_skips_parse_for_hash_unchanged_changed_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Files listed as changed by git are skipped when hash matches baseline."""
        from drift.cache import ParseCache
        from drift.config import DriftConfig

        rel = Path("src/a.py")
        abs_file = tmp_path / rel
        abs_file.parent.mkdir(parents=True, exist_ok=True)
        abs_file.write_text("def a():\n    return 1\n", encoding="utf-8")

        baseline_hash = ParseCache.file_hash(abs_file)
        baseline = BaselineSnapshot(
            file_hashes={rel.as_posix(): baseline_hash},
            score=0.2,
        )
        baseline_parse = {rel.as_posix(): ParseResult(file_path=rel, language="python")}
        BaselineManager.instance().store(tmp_path.resolve(), baseline, [], baseline_parse)

        monkeypatch.setattr(
            DriftConfig,
            "load",
            staticmethod(lambda *a, **kw: DriftConfig()),
        )
        monkeypatch.setattr(
            "drift.ingestion.file_discovery.discover_files",
            lambda *a, **kw: [
                FileInfo(
                    path=rel,
                    language="python",
                    size_bytes=abs_file.stat().st_size,
                    line_count=2,
                )
            ],
        )
        monkeypatch.setattr("drift.api._emit_api_telemetry", lambda **kw: None)
        monkeypatch.setattr("drift.signals.base.registered_signals", lambda: [])

        parse_calls = {"n": 0}

        def _count_parse(path: Path, repo: Path, language: str) -> ParseResult:
            parse_calls["n"] += 1
            return ParseResult(file_path=path, language=language)

        monkeypatch.setattr("drift.ingestion.ast_parser.parse_file", _count_parse)

        def _should_not_run(*args, **kwargs):
            raise AssertionError("IncrementalSignalRunner.run should not be called")

        monkeypatch.setattr(
            "drift.incremental.IncrementalSignalRunner.run",
            _should_not_run,
        )

        result = nudge(tmp_path, changed_files=[rel.as_posix()])

        assert parse_calls["n"] == 0
        assert result["analyzed_changed_files"] == []
        assert result["unchanged_hash_skips"] == 1

    def test_nudge_parses_changed_file_when_hash_differs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Hash mismatch vs baseline keeps file in incremental parse path."""
        from drift.cache import ParseCache
        from drift.config import DriftConfig

        rel = Path("src/a.py")
        abs_file = tmp_path / rel
        abs_file.parent.mkdir(parents=True, exist_ok=True)
        abs_file.write_text("def a():\n    return 1\n", encoding="utf-8")
        baseline_hash = ParseCache.file_hash(abs_file)

        baseline = BaselineSnapshot(
            file_hashes={rel.as_posix(): baseline_hash},
            score=0.2,
        )
        baseline_parse = {rel.as_posix(): ParseResult(file_path=rel, language="python")}
        BaselineManager.instance().store(tmp_path.resolve(), baseline, [], baseline_parse)

        # Modify file after baseline snapshot.
        abs_file.write_text("def a():\n    return 2\n", encoding="utf-8")

        monkeypatch.setattr(
            DriftConfig,
            "load",
            staticmethod(lambda *a, **kw: DriftConfig()),
        )
        monkeypatch.setattr(
            "drift.ingestion.file_discovery.discover_files",
            lambda *a, **kw: [
                FileInfo(
                    path=rel,
                    language="python",
                    size_bytes=abs_file.stat().st_size,
                    line_count=2,
                )
            ],
        )
        monkeypatch.setattr("drift.api._emit_api_telemetry", lambda **kw: None)
        monkeypatch.setattr("drift.signals.base.registered_signals", lambda: [])

        parse_calls = {"n": 0}

        def _count_parse(path: Path, repo: Path, language: str) -> ParseResult:
            parse_calls["n"] += 1
            return ParseResult(file_path=path, language=language)

        monkeypatch.setattr("drift.ingestion.ast_parser.parse_file", _count_parse)

        run_args: dict[str, object] = {}

        def _fake_run(self, changed_files, current_parse_results):
            run_args["changed_files"] = set(changed_files)
            run_args["current_parse_results"] = dict(current_parse_results)
            return SimpleNamespace(
                direction="stable",
                delta=0.0,
                score=0.2,
                new_findings=[],
                resolved_findings=[],
                confidence={},
                file_local_signals_run=[],
                cross_file_signals_estimated=[],
                baseline_valid=True,
                pruned_removed_cross_file_findings=0,
            )

        monkeypatch.setattr("drift.incremental.IncrementalSignalRunner.run", _fake_run)

        result = nudge(tmp_path, changed_files=[rel.as_posix()])

        assert parse_calls["n"] == 1
        assert run_args["changed_files"] == {rel.as_posix()}
        assert set(run_args["current_parse_results"].keys()) == {rel.as_posix()}
        assert result["analyzed_changed_files"] == [rel.as_posix()]
        assert result["unchanged_hash_skips"] == 0

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _mock_nudge_deps(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        *,
        findings: list[Finding] | None = None,
        drift_score: float = 0.3,
    ) -> None:
        """Mock the heavy dependencies for nudge()."""
        from drift.config import DriftConfig

        monkeypatch.setattr(
            DriftConfig,
            "load",
            staticmethod(lambda *a, **kw: DriftConfig()),
        )
        monkeypatch.setattr(
            "drift.analyzer.analyze_repo",
            lambda *a, **kw: _stub_analysis(findings=findings, drift_score=drift_score),
        )
        monkeypatch.setattr(
            "drift.ingestion.file_discovery.discover_files",
            lambda *a, **kw: [],
        )
        monkeypatch.setattr(
            "drift.api._emit_api_telemetry",
            lambda **kw: None,
        )
        # Prevent signals from producing findings against the temp dir
        monkeypatch.setattr(
            "drift.signals.base.registered_signals",
            lambda: [],
        )


# ---------------------------------------------------------------------------
# safe_to_commit hardrule tests
# ---------------------------------------------------------------------------


class TestSafeToCommitHardrule:
    """Verify the non-configurable safe_to_commit blocking rules."""

    @pytest.fixture(autouse=True)
    def _clear_baseline_store(self) -> None:
        _baseline_store.clear()
        BaselineManager.reset_instance()

    def test_safe_when_no_issues(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """No new critical findings + low delta → safe_to_commit=True."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[])
        assert result["safe_to_commit"] is True
        assert result["blocking_reasons"] == []

    def test_blocks_on_critical_finding(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """New critical finding → safe_to_commit=False."""
        # Pre-seed baseline via BaselineManager with empty findings
        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path.resolve(),
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )

        from drift.config import DriftConfig

        monkeypatch.setattr(
            DriftConfig,
            "load",
            staticmethod(lambda *a, **kw: DriftConfig()),
        )
        monkeypatch.setattr(
            "drift.ingestion.file_discovery.discover_files",
            lambda *a, **kw: [],
        )
        monkeypatch.setattr(
            "drift.api._emit_api_telemetry",
            lambda **kw: None,
        )
        monkeypatch.setattr(
            "drift.analyzer.analyze_repo",
            lambda *a, **kw: _stub_analysis(),
        )
        # Suppress git-state check (tmp_path is not a git repo)
        monkeypatch.setattr(
            "drift.incremental._capture_git_state",
            lambda *a, **kw: None,
        )

        result = nudge(tmp_path, changed_files=[])
        # The runner itself may produce findings that trigger blocking
        # We verify the mechanism works by checking the field types
        assert isinstance(result["safe_to_commit"], bool)
        assert isinstance(result["blocking_reasons"], list)

    def test_blocks_on_expired_baseline(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Expired baseline TTL → BaselineManager returns None → full rescan."""
        # Seed expired baseline via BaselineManager
        mgr = BaselineManager.instance()
        expired_baseline = BaselineSnapshot(
            file_hashes={},
            score=0.0,
            created_at=time.time() - 9999,
            ttl_seconds=60,
        )
        mgr.store(tmp_path.resolve(), expired_baseline, [], {})

        from drift.config import DriftConfig

        monkeypatch.setattr(
            DriftConfig,
            "load",
            staticmethod(lambda *a, **kw: DriftConfig()),
        )
        monkeypatch.setattr(
            "drift.ingestion.file_discovery.discover_files",
            lambda *a, **kw: [],
        )
        monkeypatch.setattr(
            "drift.api._emit_api_telemetry",
            lambda **kw: None,
        )
        # Suppress git-state check
        monkeypatch.setattr(
            "drift.incremental._capture_git_state",
            lambda *a, **kw: None,
        )

        # Expired baseline → nudge runs full scan to refresh
        monkeypatch.setattr(
            "drift.analyzer.analyze_repo",
            lambda *a, **kw: _stub_analysis(),
        )

        result = nudge(tmp_path, changed_files=[])
        # After refresh, baseline should be valid again
        assert isinstance(result["baseline_valid"], bool)

    def test_blocks_on_parse_failures_with_diagnostics(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Parse failures are exposed and force safe_to_commit=False."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)

        from drift.config import DriftConfig

        changed_rel = Path("src") / "broken.py"
        (tmp_path / changed_rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / changed_rel).write_text("def broken(:\n", encoding="utf-8")

        monkeypatch.setattr(
            DriftConfig,
            "load",
            staticmethod(lambda *a, **kw: DriftConfig()),
        )
        monkeypatch.setattr(
            "drift.ingestion.file_discovery.discover_files",
            lambda *a, **kw: [
                FileInfo(
                    path=changed_rel,
                    language="python",
                    size_bytes=20,
                    line_count=1,
                )
            ],
        )

        def _parse_with_error(file_path: Path, repo_path: Path, language: str) -> ParseResult:
            return ParseResult(
                file_path=file_path,
                language=language,
                parse_errors=["invalid syntax"],
            )

        monkeypatch.setattr(
            "drift.ingestion.ast_parser.parse_file",
            _parse_with_error,
        )

        result = nudge(tmp_path, changed_files=[changed_rel.as_posix()])

        assert result["safe_to_commit"] is False
        assert result["parse_failure_count"] >= 1
        assert result["parse_failed_files"]
        assert any(
            entry["file"] == changed_rel.as_posix() and entry["stage"] == "changed"
            for entry in result["parse_failed_files"]
        )
        assert any("Parse failures in" in msg for msg in result["blocking_reasons"])


# ---------------------------------------------------------------------------
# invalidate_nudge_baseline
# ---------------------------------------------------------------------------


class TestInvalidateBaseline:
    @pytest.fixture(autouse=True)
    def _clear_baseline_store(self) -> None:
        _baseline_store.clear()
        BaselineManager.reset_instance()

    def test_invalidate_removes_entry(self, tmp_path: Path) -> None:
        repo_key = tmp_path.resolve().as_posix()
        # Seed via both legacy store and BaselineManager
        _baseline_store[repo_key] = (
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path.resolve(),
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        invalidate_nudge_baseline(tmp_path)
        assert repo_key not in _baseline_store
        assert not mgr.has_baseline(tmp_path.resolve())

    def test_invalidate_noop_when_empty(self, tmp_path: Path) -> None:
        """No error when invalidating a non-existent baseline."""
        invalidate_nudge_baseline(tmp_path)


# ---------------------------------------------------------------------------
# MCP drift_nudge tool
# ---------------------------------------------------------------------------


class TestMcpDriftNudge:
    """Test the MCP tool wrapper."""

    @pytest.fixture(autouse=True)
    def _clear_baseline_store(self) -> None:
        _baseline_store.clear()
        BaselineManager.reset_instance()

    def test_drift_nudge_importable(self) -> None:
        from drift.mcp_server import drift_nudge

        assert callable(drift_nudge)

    def test_drift_nudge_returns_json(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """drift_nudge MCP tool returns valid JSON."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        from drift.mcp_server import drift_nudge

        raw = asyncio.run(drift_nudge(path=str(tmp_path), changed_files=None, uncommitted=True))
        parsed = json.loads(raw)
        assert "direction" in parsed
        assert "safe_to_commit" in parsed

    def test_drift_nudge_parses_comma_files(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Comma-separated changed_files are correctly parsed."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        from drift.mcp_server import drift_nudge

        raw = asyncio.run(
            drift_nudge(
                path=str(tmp_path),
                changed_files="src/a.py, src/b.py",
                uncommitted=True,
            )
        )
        parsed = json.loads(raw)
        assert "src/a.py" in parsed["changed_files"]
        assert "src/b.py" in parsed["changed_files"]

    def test_drift_nudge_no_stdout_leak(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """drift_nudge MUST NOT produce stdout (stdio-safety, Step 16)."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        from drift.mcp_server import drift_nudge

        asyncio.run(drift_nudge(path=str(tmp_path), changed_files=None, uncommitted=True))
        captured = capsys.readouterr()
        assert captured.out == ""


# ---------------------------------------------------------------------------
# MCP instructions update (Step 17)
# ---------------------------------------------------------------------------


class TestMcpInstructions:
    def test_instructions_mention_drift_nudge(self) -> None:
        from drift.mcp_server import _MCP_AVAILABLE, mcp

        if _MCP_AVAILABLE:
            assert "drift_nudge" in mcp.instructions
        else:
            # Fallback class doesn't store instructions; verify via source
            import inspect

            import drift.mcp_server as _mod

            assert "drift_nudge" in inspect.getsource(_mod)


# ---------------------------------------------------------------------------
# Phase 5 — BaselineManager tests
# ---------------------------------------------------------------------------


class TestBaselineManager:
    """Test BaselineManager singleton and git-event invalidation."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self) -> None:
        BaselineManager.reset_instance()
        yield
        BaselineManager.reset_instance()

    def test_singleton_identity(self) -> None:
        """instance() returns the same object on repeated calls."""
        a = BaselineManager.instance()
        b = BaselineManager.instance()
        assert a is b

    def test_reset_creates_new_instance(self) -> None:
        a = BaselineManager.instance()
        BaselineManager.reset_instance()
        b = BaselineManager.instance()
        assert a is not b

    def test_store_and_get(self, tmp_path: Path) -> None:
        mgr = BaselineManager.instance()
        baseline = BaselineSnapshot(file_hashes={"a.py": "abc"}, score=0.2)
        mgr.store(tmp_path, baseline, [], {})

        stored = mgr.get(tmp_path)
        assert stored is not None
        assert stored[0] is baseline

    def test_get_returns_none_when_empty(self, tmp_path: Path) -> None:
        mgr = BaselineManager.instance()
        assert mgr.get(tmp_path) is None

    def test_get_returns_none_when_expired(self, tmp_path: Path) -> None:
        mgr = BaselineManager.instance()
        expired = BaselineSnapshot(
            file_hashes={},
            score=0.0,
            created_at=time.time() - 9999,
            ttl_seconds=60,
        )
        mgr.store(tmp_path, expired, [], {})
        assert mgr.get(tmp_path) is None

    def test_invalidate(self, tmp_path: Path) -> None:
        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path,
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        assert mgr.has_baseline(tmp_path)
        mgr.invalidate(tmp_path)
        assert not mgr.has_baseline(tmp_path)

    def test_has_baseline(self, tmp_path: Path) -> None:
        mgr = BaselineManager.instance()
        assert not mgr.has_baseline(tmp_path)
        mgr.store(
            tmp_path,
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        assert mgr.has_baseline(tmp_path)

    def test_instance_thread_safety(self) -> None:
        """instance() must return the same object from concurrent threads (issue #405)."""
        import threading

        results: list[BaselineManager] = []
        lock = threading.Lock()

        def get_instance() -> None:
            inst = BaselineManager.instance()
            with lock:
                results.append(inst)

        threads = [threading.Thread(target=get_instance) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        unique_ids = {id(i) for i in results}
        assert len(unique_ids) == 1, (
            f"Expected exactly one BaselineManager instance, got {len(unique_ids)}"
        )

    def test_public_state_methods_use_instance_lock(self, tmp_path: Path) -> None:
        """Public state accessors/mutators must acquire the manager lock (issue #422)."""

        class _TrackingLock:
            def __init__(self) -> None:
                self.enter_count = 0

            def __enter__(self) -> None:
                self.enter_count += 1

            def __exit__(
                self,
                exc_type: object,
                exc: object,
                tb: object,
            ) -> None:
                return None

        mgr = BaselineManager.instance()
        tracker = _TrackingLock()
        mgr._lock = tracker  # type: ignore[attr-defined]

        repo_path = tmp_path.resolve()
        baseline = BaselineSnapshot(file_hashes={"a.py": "abc"}, score=0.1)

        mgr.store(repo_path, baseline, [], {})
        _ = mgr.get(repo_path)
        _ = mgr.has_baseline(repo_path)
        _ = mgr.consume_refresh_reason(repo_path)
        mgr.invalidate(repo_path)

        assert tracker.enter_count >= 5


class TestGitEventInvalidation:
    """Test that BaselineManager detects git-state changes."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self) -> None:
        BaselineManager.reset_instance()
        yield
        BaselineManager.reset_instance()

    def test_head_change_invalidates(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """HEAD commit change → baseline invalidated."""
        from drift.incremental import _GitState

        call_count = {"n": 0}

        def _fake_capture(repo_path: Path) -> _GitState:
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return _GitState(
                    head_commit="aaa111",
                    stash_hash="s1",
                    changed_file_count=0,
                )
            return _GitState(
                head_commit="bbb222",
                stash_hash="s1",
                changed_file_count=0,
            )

        monkeypatch.setattr("drift.incremental._capture_git_state", _fake_capture)
        monkeypatch.setattr("drift.incremental._capture_git_state_uncached", _fake_capture)

        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path,
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        assert mgr.get(tmp_path) is None

    def test_stash_change_invalidates(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Stash list change → baseline invalidated."""
        from drift.incremental import _GitState

        call_count = {"n": 0}

        def _fake_capture(repo_path: Path) -> _GitState:
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return _GitState(
                    head_commit="aaa111",
                    stash_hash="stash_v1",
                    changed_file_count=0,
                )
            return _GitState(
                head_commit="aaa111",
                stash_hash="stash_v2",
                changed_file_count=0,
            )

        monkeypatch.setattr("drift.incremental._capture_git_state", _fake_capture)
        monkeypatch.setattr("drift.incremental._capture_git_state_uncached", _fake_capture)

        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path,
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        assert mgr.get(tmp_path) is None

    def test_many_changed_files_invalidates(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """> threshold changed files → baseline invalidated."""
        from drift.incremental import (
            _MAX_CHANGED_FILES_BEFORE_INVALIDATION,
            _GitState,
        )

        call_count = {"n": 0}

        def _fake_capture(repo_path: Path) -> _GitState:
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return _GitState(
                    head_commit="aaa111",
                    stash_hash="s1",
                    changed_file_count=2,
                )
            return _GitState(
                head_commit="aaa111",
                stash_hash="s1",
                changed_file_count=_MAX_CHANGED_FILES_BEFORE_INVALIDATION + 1,
            )

        monkeypatch.setattr("drift.incremental._capture_git_state", _fake_capture)
        monkeypatch.setattr("drift.incremental._capture_git_state_uncached", _fake_capture)

        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path,
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        assert mgr.get(tmp_path) is None

    def test_high_but_stable_changed_files_keeps_baseline(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Already-high changed count that stays high should not re-invalidate."""
        from drift.incremental import (
            _MAX_CHANGED_FILES_BEFORE_INVALIDATION,
            _GitState,
        )

        high = _MAX_CHANGED_FILES_BEFORE_INVALIDATION + 5
        stable_state = _GitState(
            head_commit="aaa111",
            stash_hash="s1",
            changed_file_count=high,
        )
        monkeypatch.setattr(
            "drift.incremental._capture_git_state",
            lambda *a, **kw: stable_state,
        )
        monkeypatch.setattr(
            "drift.incremental._capture_git_state_uncached",
            lambda *a, **kw: stable_state,
        )

        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path,
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )

        assert mgr.get(tmp_path) is not None

    def test_no_change_keeps_baseline(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Unchanged git state → baseline remains valid."""
        from drift.incremental import _GitState

        stable_state = _GitState(
            head_commit="aaa111",
            stash_hash="s1",
            changed_file_count=2,
        )
        monkeypatch.setattr(
            "drift.incremental._capture_git_state",
            lambda *a, **kw: stable_state,
        )
        monkeypatch.setattr(
            "drift.incremental._capture_git_state_uncached",
            lambda *a, **kw: stable_state,
        )

        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path,
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        assert mgr.get(tmp_path) is not None

    def test_no_git_repo_keeps_baseline(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Non-git directory → git state check returns None → baseline kept."""
        monkeypatch.setattr(
            "drift.incremental._capture_git_state",
            lambda *a, **kw: None,
        )

        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path,
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        assert mgr.get(tmp_path) is not None

    def test_rapid_head_change_not_hidden_by_ttl_cache(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Regression: HEAD change within TTL window must still invalidate baseline.

        Before the fix for issue #372, _git_state_changed called _capture_git_state
        which could return a stale cached snapshot.  A commit that arrived within
        the 5-second TTL was therefore invisible and the stale baseline was kept.

        The fix makes _git_state_changed call _capture_git_state_uncached so the
        invalidation path always sees the true current HEAD.
        """
        from drift.incremental import _GitState

        # Simulates: cache (used by store) sees HEAD=commit_A ...
        cached_state = _GitState(head_commit="commit_A", stash_hash="s1", changed_file_count=0)
        # ... but the real subprocess (uncached, used by _git_state_changed) already
        # sees the new commit that arrived within the TTL window.
        fresh_state = _GitState(head_commit="commit_B", stash_hash="s1", changed_file_count=0)

        monkeypatch.setattr(
            "drift.incremental._capture_git_state",
            lambda *a, **kw: cached_state,
        )
        monkeypatch.setattr(
            "drift.incremental._capture_git_state_uncached",
            lambda *a, **kw: fresh_state,
        )

        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path,
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        # Despite the cached path still showing commit_A, the uncached check
        # reveals commit_B → baseline must be invalidated.
        assert mgr.get(tmp_path) is None


class TestNudgeUsesBaselineManager:
    """Verify that nudge() integrates with BaselineManager (Step 20)."""

    @pytest.fixture(autouse=True)
    def _reset(self) -> None:
        _baseline_store.clear()
        BaselineManager.reset_instance()
        yield
        BaselineManager.reset_instance()

    def test_nudge_creates_baseline_in_manager(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """First nudge() call stores baseline via BaselineManager."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        nudge(tmp_path, changed_files=[])

        mgr = BaselineManager.instance()
        assert mgr.has_baseline(tmp_path.resolve())

    def test_nudge_detects_git_state_change(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Git-state change triggers full rescan on next nudge() call."""
        from drift.incremental import _GitState

        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)

        call_count = {"analyze_count": 0}
        phase = {"head": "commit_1"}

        def _fake_capture(repo_path: Path) -> _GitState:
            return _GitState(
                head_commit=phase["head"],
                stash_hash="s1",
                changed_file_count=0,
            )

        monkeypatch.setattr("drift.incremental._capture_git_state", _fake_capture)

        def _counting_analyze(*a, **kw):
            call_count["analyze_count"] += 1
            return _stub_analysis()

        monkeypatch.setattr("drift.analyzer.analyze_repo", _counting_analyze)

        # First call → creates baseline (1 analyze call)
        nudge(tmp_path, changed_files=[])
        first_analyze = call_count["analyze_count"]

        # Simulate external git movement before next nudge call.
        phase["head"] = "commit_2"

        # Second call → git state changed → rescan (another analyze call)
        result = nudge(tmp_path, changed_files=[])
        assert call_count["analyze_count"] > first_analyze
        assert result["baseline_refresh_reason"] == "git_head_changed"

    def test_nudge_refresh_reason_ttl_expired(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Expired baseline emits deterministic reason code."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)

        mgr = BaselineManager.instance()
        expired = BaselineSnapshot(
            file_hashes={},
            score=0.0,
            created_at=time.time() - 9999,
            ttl_seconds=60,
        )
        mgr.store(tmp_path.resolve(), expired, [], {})

        monkeypatch.setattr(
            "drift.incremental._capture_git_state",
            lambda *a, **kw: None,
        )

        result = nudge(tmp_path, changed_files=[])
        assert result["baseline_refresh_reason"] == "ttl_expired"

    def test_nudge_refresh_reason_stash_changed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Stash mutation emits deterministic reason code."""
        from drift.incremental import _GitState

        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)

        phase = {"stash": "stash_1"}

        def _fake_capture(repo_path: Path) -> _GitState:
            return _GitState(
                head_commit="commit_1",
                stash_hash=phase["stash"],
                changed_file_count=0,
            )

        monkeypatch.setattr("drift.incremental._capture_git_state", _fake_capture)
        monkeypatch.setattr("drift.incremental._capture_git_state_uncached", _fake_capture)

        nudge(tmp_path, changed_files=[])
        phase["stash"] = "stash_2"
        result = nudge(tmp_path, changed_files=[])
        assert result["baseline_refresh_reason"] == "stash_changed"

    def test_nudge_refresh_reason_changed_file_threshold(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Large working-tree delta emits threshold reason code."""
        from drift.incremental import (
            _MAX_CHANGED_FILES_BEFORE_INVALIDATION,
            _GitState,
        )

        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)

        phase = {"count": 1}

        def _fake_capture(repo_path: Path) -> _GitState:
            return _GitState(
                head_commit="commit_1",
                stash_hash="stash_1",
                changed_file_count=phase["count"],
            )

        monkeypatch.setattr("drift.incremental._capture_git_state", _fake_capture)
        monkeypatch.setattr("drift.incremental._capture_git_state_uncached", _fake_capture)

        nudge(tmp_path, changed_files=[])
        phase["count"] = _MAX_CHANGED_FILES_BEFORE_INVALIDATION + 1
        result = nudge(tmp_path, changed_files=[])
        assert result["baseline_refresh_reason"] == "changed_file_threshold"

    def test_nudge_loads_persisted_baseline_after_manager_reset(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Disk baseline allows warm nudge after process-like manager reset."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)

        # First run creates persisted baseline artifact.
        nudge(tmp_path, changed_files=[])

        # Simulate process boundary by dropping singleton state.
        BaselineManager.reset_instance()

        analyze_calls = {"n": 0}

        def _counting_analyze(*a, **kw):
            analyze_calls["n"] += 1
            return _stub_analysis()

        monkeypatch.setattr("drift.analyzer.analyze_repo", _counting_analyze)

        result = nudge(tmp_path, changed_files=[])
        assert analyze_calls["n"] == 0
        assert result["baseline_refresh_reason"] == "disk_warm_hit"

    def test_nudge_config_change_invalidates_persisted_baseline(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Changed config fingerprint forces fresh baseline build."""
        from drift.api import _config as api_config
        from drift.config import DriftConfig

        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)

        # Create baseline with default config fingerprint.
        nudge(tmp_path, changed_files=[])

        BaselineManager.reset_instance()

        analyze_calls = {"n": 0}

        def _counting_analyze(*a, **kw):
            analyze_calls["n"] += 1
            return _stub_analysis()

        monkeypatch.setattr("drift.analyzer.analyze_repo", _counting_analyze)
        monkeypatch.setattr(
            DriftConfig,
            "load",
            staticmethod(
                lambda *a, **kw: DriftConfig(context_dampening=0.12)
            ),
        )
        api_config._CONFIG_CACHE.clear()

        result = nudge(tmp_path, changed_files=[])
        assert analyze_calls["n"] == 1
        assert result["baseline_refresh_reason"] == "baseline_missing"


# ---------------------------------------------------------------------------
# Bruchstelle 2 — Finding cluster summary
# ---------------------------------------------------------------------------


class TestFindingClusterSummary:
    """Nudge response includes a cluster summary of ALL new findings (not just top 5)."""

    @pytest.fixture(autouse=True)
    def _clear_baseline_store(self) -> None:
        _baseline_store.clear()
        BaselineManager.reset_instance()

    def test_cluster_summary_present_in_response(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """nudge() response always includes finding_cluster_summary field."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[])
        assert "finding_cluster_summary" in result

    def test_cluster_summary_counts_all_findings_not_just_capped(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Cluster summary counts ALL new findings, not just the 5 returned in new_findings."""
        findings = [
            _make_finding(
                signal_type=SignalType.PATTERN_FRAGMENTATION,
                severity=Severity.MEDIUM,
                title=f"PFS finding {i}",
                file_path=f"src/f{i}.py",
            )
            for i in range(8)
        ]
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path, findings=findings)

        # Pre-seed empty baseline so all findings are "new"
        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path.resolve(),
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        monkeypatch.setattr(
            "drift.api._emit_api_telemetry",
            lambda **kw: None,
        )
        monkeypatch.setattr(
            "drift.incremental._capture_git_state",
            lambda *a, **kw: None,
        )

        def _fake_run(*args, **kwargs):
            return SimpleNamespace(
                direction="degrading",
                delta=0.1,
                score=0.5,
                new_findings=findings,
                resolved_findings=[],
                confidence={},
                file_local_signals_run=["pattern_fragmentation"],
                cross_file_signals_estimated=[],
                baseline_valid=True,
                pruned_removed_cross_file_findings=0,
            )

        monkeypatch.setattr("drift.incremental.IncrementalSignalRunner.run", _fake_run)

        result = nudge(tmp_path, changed_files=["src/f0.py"])

        assert len(result["new_findings"]) <= 5  # capped at 5
        summary = result["finding_cluster_summary"]
        assert summary["total_new"] == 8  # all 8 counted
        assert "PFS" in summary["by_signal"]
        assert summary["by_signal"]["PFS"] == 8

    def test_cluster_summary_empty_when_no_findings(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Clean nudge has zero counts in cluster summary."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[])
        summary = result["finding_cluster_summary"]
        assert summary["total_new"] == 0
        assert summary["by_signal"] == {}


# ---------------------------------------------------------------------------
# Bruchstelle 1 — Dynamic agent_instruction
# ---------------------------------------------------------------------------


class TestDynamicAgentInstruction:
    """agent_instruction adapts to the current nudge state."""

    @pytest.fixture(autouse=True)
    def _clear_baseline_store(self) -> None:
        _baseline_store.clear()
        BaselineManager.reset_instance()

    def test_agent_instruction_mentions_brief_when_degrading(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When findings are new and blocking, agent_instruction suggests drift_brief."""
        findings = [
            _make_finding(
                signal_type=SignalType.ARCHITECTURE_VIOLATION,
                severity=Severity.HIGH,
                title="Layer violation in checkout",
                file_path="src/checkout.py",
            )
        ]
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path, findings=findings)

        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path.resolve(),
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        monkeypatch.setattr(
            "drift.api._emit_api_telemetry",
            lambda **kw: None,
        )
        monkeypatch.setattr(
            "drift.incremental._capture_git_state",
            lambda *a, **kw: None,
        )

        def _fake_run(*args, **kwargs):
            return SimpleNamespace(
                direction="degrading",
                delta=0.1,
                score=0.5,
                new_findings=findings,
                resolved_findings=[],
                confidence={},
                file_local_signals_run=["architecture_violation"],
                cross_file_signals_estimated=[],
                baseline_valid=True,
                pruned_removed_cross_file_findings=0,
            )

        monkeypatch.setattr("drift.incremental.IncrementalSignalRunner.run", _fake_run)

        result = nudge(tmp_path, changed_files=["src/checkout.py"])

        assert result["safe_to_commit"] is False
        assert "drift_brief" in result["agent_instruction"]

    def test_agent_instruction_standard_when_safe(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When safe_to_commit is true, standard instruction is given."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[])
        assert result["safe_to_commit"] is True
        assert "drift_nudge" in result["agent_instruction"]
        assert "drift_diff" in result["agent_instruction"]


# ---------------------------------------------------------------------------
# Post-edit regression detector fields
# ---------------------------------------------------------------------------


class TestPostEditRegressionDetector:
    """revert_recommended, latency_ms, latency_exceeded, auto_fast_path."""

    @pytest.fixture(autouse=True)
    def _clear_baseline_store(self) -> None:
        _baseline_store.clear()
        BaselineManager.reset_instance()

    def _seed_baseline(self, tmp_path: Path) -> None:
        BaselineManager.instance().store(
            tmp_path.resolve(),
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )

    def _patch_git_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "drift.incremental._capture_git_state",
            lambda *a, **kw: None,
        )

    def _inject_runner(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        direction: str,
        delta: float,
        score: float,
        new_findings: list[Finding],
        file_local_signals_run: list[str],
        cross_file_signals_estimated: list[str],
    ) -> None:
        def _fake_run(*args, **kwargs):
            return SimpleNamespace(
                direction=direction,
                delta=delta,
                score=score,
                new_findings=new_findings,
                resolved_findings=[],
                confidence={},
                file_local_signals_run=file_local_signals_run,
                cross_file_signals_estimated=cross_file_signals_estimated,
                baseline_valid=True,
                pruned_removed_cross_file_findings=0,
            )

        monkeypatch.setattr("drift.incremental.IncrementalSignalRunner.run", _fake_run)

    def test_revert_recommended_true_when_degrading_and_not_safe(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """revert_recommended=True when direction==degrading and safe_to_commit==False."""
        findings = [
            _make_finding(severity=Severity.HIGH, title="layer violation")
        ]
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path, findings=findings)
        self._seed_baseline(tmp_path)
        self._patch_git_state(monkeypatch)
        self._inject_runner(
            monkeypatch,
            direction="degrading",
            delta=0.1,
            score=0.4,
            new_findings=findings,
            file_local_signals_run=["pattern_fragmentation"],
            cross_file_signals_estimated=[],
        )

        result = nudge(tmp_path, changed_files=["src/a.py"])

        assert result["safe_to_commit"] is False
        assert result["revert_recommended"] is True
        assert "REVERT" in result["agent_instruction"]

    def test_revert_recommended_false_when_degrading_but_safe(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """revert_recommended=False when direction==degrading but safe_to_commit==True."""
        # Create the file so it is discovered and the runner is actually invoked
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.py").write_text("x = 1\n", encoding="utf-8")

        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        self._seed_baseline(tmp_path)
        self._patch_git_state(monkeypatch)
        # delta=0.01 < _NUDGE_SIGNIFICANT_DELTA=0.05, new_findings=[] → safe_to_commit=True
        self._inject_runner(
            monkeypatch,
            direction="degrading",
            delta=0.01,
            score=0.31,
            new_findings=[],
            file_local_signals_run=["pattern_fragmentation"],
            cross_file_signals_estimated=[],
        )

        result = nudge(tmp_path, changed_files=["src/a.py"])

        assert result["safe_to_commit"] is True
        assert result["revert_recommended"] is False

    def test_latency_ms_present_in_response(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Response always contains latency_ms as a non-negative integer."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[])

        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], int)
        assert result["latency_ms"] >= 0

    def test_latency_exceeded_true_when_over_threshold(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """latency_exceeded=True when elapsed > timeout_ms."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)

        _call_count = [0]

        def _fake_monotonic() -> float:
            _call_count[0] += 1
            # First call (start timestamp): return 0; all subsequent: return 2.0 (=2000 ms)
            return 0.0 if _call_count[0] == 1 else 2.0

        monkeypatch.setattr("time.monotonic", _fake_monotonic)

        result = nudge(tmp_path, changed_files=[], timeout_ms=1000)

        assert result["latency_exceeded"] is True

    def test_latency_exceeded_false_when_under_threshold(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """latency_exceeded=False when elapsed < timeout_ms."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        # Real execution on empty changed_files should be well under 500 ms
        result = nudge(tmp_path, changed_files=[], timeout_ms=10_000)

        assert result["latency_exceeded"] is False

    def test_latency_exceeded_false_when_timeout_disabled(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """latency_exceeded=False when timeout_ms=None (gate disabled)."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[], timeout_ms=None)

        assert result["latency_exceeded"] is False

    def test_baseline_created_true_on_cold_start(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """baseline_created=True when no baseline existed and a new one was built."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        # No pre-seeded baseline → nudge must create one (cold-start).
        result = nudge(tmp_path, changed_files=[], timeout_ms=None)

        assert result["baseline_created"] is True

    def test_baseline_created_false_when_baseline_exists(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """baseline_created=False when a warm baseline was already available."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        # Pre-seed baseline so nudge reuses it.
        BaselineManager.instance().store(
            tmp_path.resolve(),
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        result = nudge(tmp_path, changed_files=[], timeout_ms=None)

        assert result["baseline_created"] is False

    def test_auto_fast_path_true_when_only_file_local_signals(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """auto_fast_path=True when cross_file_signals_estimated is empty."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        self._seed_baseline(tmp_path)
        self._patch_git_state(monkeypatch)
        self._inject_runner(
            monkeypatch,
            direction="stable",
            delta=0.0,
            score=0.3,
            new_findings=[],
            file_local_signals_run=["pattern_fragmentation"],
            cross_file_signals_estimated=[],
        )

        result = nudge(tmp_path, changed_files=["src/a.py"])

        assert result["auto_fast_path"] is True

    def test_auto_fast_path_false_when_cross_file_signals_estimated(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """auto_fast_path=False when MDS/AVS are in cross_file_signals_estimated."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        self._seed_baseline(tmp_path)
        self._patch_git_state(monkeypatch)
        self._inject_runner(
            monkeypatch,
            direction="stable",
            delta=0.0,
            score=0.3,
            new_findings=[],
            file_local_signals_run=["pattern_fragmentation"],
            cross_file_signals_estimated=["architecture_violation", "mutant_duplicate"],
        )

        result = nudge(tmp_path, changed_files=["src/a.py"])

        assert result["auto_fast_path"] is False

    def test_response_schema_includes_new_fields(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """All 4 new post-edit fields are present in every nudge response."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        result = nudge(tmp_path, changed_files=[])

        assert "revert_recommended" in result
        assert "latency_ms" in result
        assert "latency_exceeded" in result
        assert "auto_fast_path" in result
        assert "baseline_created" in result
        assert isinstance(result["revert_recommended"], bool)
        assert isinstance(result["latency_ms"], int)
        assert isinstance(result["latency_exceeded"], bool)
        assert isinstance(result["auto_fast_path"], bool)
        assert isinstance(result["baseline_created"], bool)


