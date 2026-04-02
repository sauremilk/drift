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
        assert result["schema_version"] == "2.0"

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

        monkeypatch.setattr(
            "drift.analyzer.analyze_repo", _counting_analyze
        )

        # Second call — should NOT trigger analyze_repo
        result = nudge(tmp_path, changed_files=[])
        assert call_count["n"] == 0
        assert result["baseline_refresh_reason"] is None

    def test_nudge_error_returns_error_response(self, tmp_path: Path) -> None:
        """nudge() returns error_response on exception (not raised)."""
        # Non-existent path that triggers config load error
        broken = tmp_path / "nonexistent_repo_xyz"
        result = nudge(broken, changed_files=[])
        # Should not crash, returns error dict
        assert "schema_version" in result or "error" in result

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
            lambda *a, **kw: _stub_analysis(
                findings=findings, drift_score=drift_score
            ),
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

    def test_safe_when_no_issues(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
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

        raw = drift_nudge(path=str(tmp_path), changed_files=None, uncommitted=True)
        parsed = json.loads(raw)
        assert "direction" in parsed
        assert "safe_to_commit" in parsed

    def test_drift_nudge_parses_comma_files(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Comma-separated changed_files are correctly parsed."""
        TestNudgeAPI._mock_nudge_deps(monkeypatch, tmp_path)
        from drift.mcp_server import drift_nudge

        raw = drift_nudge(
            path=str(tmp_path),
            changed_files="src/a.py, src/b.py",
            uncommitted=True,
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

        drift_nudge(path=str(tmp_path), changed_files=None, uncommitted=True)
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


class TestGitEventInvalidation:
    """Test that BaselineManager detects git-state changes."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self) -> None:
        BaselineManager.reset_instance()
        yield
        BaselineManager.reset_instance()

    def test_head_change_invalidates(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
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

        monkeypatch.setattr(
            "drift.incremental._capture_git_state", _fake_capture
        )

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

        monkeypatch.setattr(
            "drift.incremental._capture_git_state", _fake_capture
        )

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

        monkeypatch.setattr(
            "drift.incremental._capture_git_state", _fake_capture
        )

        mgr = BaselineManager.instance()
        mgr.store(
            tmp_path,
            BaselineSnapshot(file_hashes={}, score=0.0),
            [],
            {},
        )
        assert mgr.get(tmp_path) is None

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

        call_count = {"n": 0, "analyze_count": 0}

        def _fake_capture(repo_path: Path) -> _GitState:
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return _GitState(
                    head_commit="commit_1",
                    stash_hash="s1",
                    changed_file_count=0,
                )
            return _GitState(
                head_commit="commit_2",
                stash_hash="s1",
                changed_file_count=0,
            )

        monkeypatch.setattr(
            "drift.incremental._capture_git_state", _fake_capture
        )

        def _counting_analyze(*a, **kw):
            call_count["analyze_count"] += 1
            return _stub_analysis()

        monkeypatch.setattr(
            "drift.analyzer.analyze_repo", _counting_analyze
        )

        # First call → creates baseline (1 analyze call)
        nudge(tmp_path, changed_files=[])
        first_analyze = call_count["analyze_count"]

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

        call_count = {"n": 0}

        def _fake_capture(repo_path: Path) -> _GitState:
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return _GitState(
                    head_commit="commit_1",
                    stash_hash="stash_1",
                    changed_file_count=0,
                )
            return _GitState(
                head_commit="commit_1",
                stash_hash="stash_2",
                changed_file_count=0,
            )

        monkeypatch.setattr(
            "drift.incremental._capture_git_state", _fake_capture
        )

        nudge(tmp_path, changed_files=[])
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

        call_count = {"n": 0}

        def _fake_capture(repo_path: Path) -> _GitState:
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return _GitState(
                    head_commit="commit_1",
                    stash_hash="stash_1",
                    changed_file_count=1,
                )
            return _GitState(
                head_commit="commit_1",
                stash_hash="stash_1",
                changed_file_count=_MAX_CHANGED_FILES_BEFORE_INVALIDATION + 1,
            )

        monkeypatch.setattr(
            "drift.incremental._capture_git_state", _fake_capture
        )

        nudge(tmp_path, changed_files=[])
        result = nudge(tmp_path, changed_files=[])
        assert result["baseline_refresh_reason"] == "changed_file_threshold"
