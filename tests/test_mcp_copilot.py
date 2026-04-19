"""Tests for drift MCP server and copilot-context modules."""

from __future__ import annotations

import asyncio
import datetime
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from drift.copilot_context import (
    MARKER_BEGIN,
    MARKER_END,
    generate_constraints_payload,
    generate_instructions,
    merge_into_file,
)
from drift.models import (
    Finding,
    ModuleScore,
    RepoAnalysis,
    Severity,
    SignalType,
    TrendContext,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _analysis(tmp_path: Path) -> RepoAnalysis:
    """Build a minimal RepoAnalysis with diverse findings."""
    findings = [
        Finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            severity=Severity.HIGH,
            score=0.7,
            title="Layer violation: api → db",
            description="api/routes.py imports directly from db/models.py",
            file_path=Path("api/routes.py"),
            start_line=2,
            fix="Use service layer instead of importing db models directly.",
            impact=0.8,
        ),
        Finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            severity=Severity.MEDIUM,
            score=0.5,
            title="Layer violation: api → db (second)",
            description="Another violation",
            file_path=Path("api/handlers.py"),
            start_line=5,
            fix="Route through service layer.",
            impact=0.6,
        ),
        Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.MEDIUM,
            score=0.5,
            title="3 error-handling variants in services/",
            description="Inconsistent exception patterns",
            file_path=Path("services/payment.py"),
            start_line=10,
            fix="Consolidate to one error-handling pattern per module.",
            impact=0.5,
        ),
        Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.MEDIUM,
            score=0.45,
            title="2 HTTP client patterns",
            description="Mixed httpx and requests usage",
            file_path=Path("services/external.py"),
            start_line=1,
            fix="Standardize on httpx for HTTP requests.",
            impact=0.4,
        ),
        Finding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            severity=Severity.MEDIUM,
            score=0.45,
            title="Bare except in services/",
            description="10 broad exception handlers",
            file_path=Path("services/payment.py"),
            start_line=30,
            impact=0.3,
        ),
        Finding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            severity=Severity.MEDIUM,
            score=0.42,
            title="Bare except in api/",
            description="5 broad exception handlers",
            file_path=Path("api/routes.py"),
            start_line=15,
            impact=0.25,
        ),
        # Low-score finding (should be filtered out)
        Finding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            severity=Severity.LOW,
            score=0.2,
            title="Missing guards",
            description="Low score finding",
            file_path=Path("utils/helpers.py"),
            impact=0.1,
        ),
        # Temporal signal (should be excluded — not actionable)
        Finding(
            signal_type=SignalType.TEMPORAL_VOLATILITY,
            severity=Severity.HIGH,
            score=0.8,
            title="High churn on payment.py",
            description="47 commits in 30 days",
            file_path=Path("services/payment.py"),
            impact=0.7,
        ),
    ]

    modules = [
        ModuleScore(
            path=Path("services"),
            drift_score=0.65,
            findings=findings[:3],
        ),
        ModuleScore(
            path=Path("api"),
            drift_score=0.45,
            findings=findings[3:5],
        ),
    ]

    return RepoAnalysis(
        repo_path=tmp_path,
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=0.55,
        findings=findings,
        module_scores=modules,
        total_files=20,
        total_functions=50,
        trend=TrendContext(
            previous_score=0.52,
            delta=0.03,
            direction="degrading",
            recent_scores=[0.50, 0.52, 0.55],
            history_depth=3,
            transition_ratio=0.6,
        ),
    )


# ---------------------------------------------------------------------------
# copilot_context — generate_instructions
# ---------------------------------------------------------------------------


class TestGenerateInstructions:
    def test_contains_markers(self, _analysis: RepoAnalysis) -> None:
        result = generate_instructions(_analysis)
        assert MARKER_BEGIN in result
        assert MARKER_END in result

    def test_includes_actionable_signals(self, _analysis: RepoAnalysis) -> None:
        result = generate_instructions(_analysis)
        assert "### Layer Boundaries (AVS)" in result
        assert "### Code Pattern Consistency (PFS)" in result
        assert "### Exception Handling (BEM)" in result

    def test_excludes_temporal_signals(self, _analysis: RepoAnalysis) -> None:
        result = generate_instructions(_analysis)
        # Temporal volatility is not actionable for instructions
        assert "High churn" not in result
        assert "47 commits" not in result

    def test_excludes_low_score_findings(self, _analysis: RepoAnalysis) -> None:
        result = generate_instructions(_analysis)
        # Guard clause finding has score 0.2, should be filtered
        assert "Missing guards" not in result

    def test_includes_drift_status(self, _analysis: RepoAnalysis) -> None:
        result = generate_instructions(_analysis)
        assert "Drift Score" in result
        assert "0.55" in result
        assert "degrading" in result

    def test_includes_worst_module(self, _analysis: RepoAnalysis) -> None:
        result = generate_instructions(_analysis)
        assert "services" in result

    def test_excludes_non_operational_work_artifacts_from_guidance(self, tmp_path: Path) -> None:
        noisy = Finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            severity=Severity.HIGH,
            score=0.9,
            title="Archived repo violation",
            description="work artifact imports production internals",
            file_path=Path("work_artifacts/agent-framework-target/demo/app.py"),
            start_line=8,
            fix="Do not import runtime internals from archived copies.",
            impact=0.9,
        )
        second_noisy = Finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            severity=Severity.MEDIUM,
            score=0.6,
            title="Archived repo violation 2",
            description="another archived copy import",
            file_path=Path("work_artifacts/agent-framework-target/demo/routes.py"),
            start_line=4,
            fix="Keep archived copies out of runtime guidance.",
            impact=0.5,
        )
        prod_a = Finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            severity=Severity.HIGH,
            score=0.8,
            title="Real api violation",
            description="src/api/routes.py imports db code",
            file_path=Path("src/api/routes.py"),
            start_line=3,
            fix="Use the service layer.",
            impact=0.8,
        )
        prod_b = Finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            severity=Severity.MEDIUM,
            score=0.5,
            title="Real api violation 2",
            description="src/api/handlers.py imports db code",
            file_path=Path("src/api/handlers.py"),
            start_line=7,
            fix="Route through services.",
            impact=0.5,
        )
        analysis = RepoAnalysis(
            repo_path=tmp_path,
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.61,
            findings=[noisy, second_noisy, prod_a, prod_b],
            module_scores=[
                ModuleScore(
                    path=Path("work_artifacts/agent-framework-target/demo"),
                    drift_score=0.95,
                    findings=[noisy, second_noisy],
                ),
                ModuleScore(
                    path=Path("src/api"),
                    drift_score=0.72,
                    findings=[prod_a, prod_b],
                ),
            ],
        )

        result = generate_instructions(analysis)

        assert "Use the service layer." in result
        assert "src/api" in result
        assert "work_artifacts/agent-framework-target/demo/app.py" not in result
        assert "Most eroded module" in result
        assert "work_artifacts/agent-framework-target/demo" not in result

    def test_empty_findings_produces_clean_output(self, tmp_path: Path) -> None:
        analysis = RepoAnalysis(
            repo_path=tmp_path,
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.1,
        )
        result = generate_instructions(analysis)
        assert MARKER_BEGIN in result
        assert "No significant architectural issues" in result

    def test_cross_reference_to_export_context(self, _analysis: RepoAnalysis) -> None:
        """Issue #112: copilot-context should mention export-context."""
        result = generate_instructions(_analysis)
        assert "drift export-context" in result
        assert "Security" in result or "security" in result


class TestGenerateConstraintsPayload:
    def test_payload_contains_expected_shape(self, _analysis: RepoAnalysis) -> None:
        payload = generate_constraints_payload(_analysis)

        assert "constraints" in payload
        assert "summary" in payload
        constraints = payload["constraints"]
        assert isinstance(constraints, list)
        assert len(constraints) >= 1

        first = constraints[0]
        assert first["signal"] in {"AVS", "PFS", "BEM"}
        assert "severity" in first
        assert "scope" in first
        assert "constraint" in first

    def test_payload_excludes_temporal_and_low_score_findings(
        self,
        _analysis: RepoAnalysis,
    ) -> None:
        payload = generate_constraints_payload(_analysis)
        constraints = payload["constraints"]
        assert all(c["signal_type"] != "temporal_volatility" for c in constraints)
        assert all(c["signal_type"] != "guard_clause_deficit" for c in constraints)


# ---------------------------------------------------------------------------
# copilot_context — merge_into_file
# ---------------------------------------------------------------------------


class TestMergeIntoFile:
    def test_creates_new_file(self, tmp_path: Path) -> None:
        target = tmp_path / ".github" / "copilot-instructions.md"
        section = f"{MARKER_BEGIN}\ntest content\n{MARKER_END}\n"
        changed = merge_into_file(target, section)
        assert changed is True
        assert target.exists()
        assert "test content" in target.read_text()

    def test_replaces_existing_markers(self, tmp_path: Path) -> None:
        target = tmp_path / "instructions.md"
        original = (
            "# My Instructions\n\nHand-written stuff.\n\n"
            f"{MARKER_BEGIN}\nold drift content\n{MARKER_END}\n\n"
            "More hand-written content.\n"
        )
        target.write_text(original)

        new_section = f"{MARKER_BEGIN}\nnew drift content\n{MARKER_END}\n"
        changed = merge_into_file(target, new_section)
        assert changed is True

        result = target.read_text()
        assert "new drift content" in result
        assert "old drift content" not in result
        assert "Hand-written stuff." in result
        assert "More hand-written content." in result

    def test_appends_when_no_markers(self, tmp_path: Path) -> None:
        target = tmp_path / "instructions.md"
        target.write_text("# Existing content\n")

        section = f"{MARKER_BEGIN}\ndrift section\n{MARKER_END}\n"
        changed = merge_into_file(target, section)
        assert changed is True

        result = target.read_text()
        assert "# Existing content" in result
        assert "drift section" in result

    def test_no_change_when_identical(self, tmp_path: Path) -> None:
        target = tmp_path / "instructions.md"
        section = f"{MARKER_BEGIN}\ncontent\n{MARKER_END}\n"
        target.write_text(section)

        changed = merge_into_file(target, section)
        assert changed is False

    def test_no_merge_overwrites(self, tmp_path: Path) -> None:
        target = tmp_path / "instructions.md"
        target.write_text("old content that should disappear")

        section = f"{MARKER_BEGIN}\nnew only\n{MARKER_END}\n"
        changed = merge_into_file(target, section, no_merge=True)
        assert changed is True
        assert target.read_text() == section


# ---------------------------------------------------------------------------
# MCP server — tool handlers (unit tests, no MCP transport)
# ---------------------------------------------------------------------------


def _run_tool(result: object) -> object:
    """Transparently await async MCP tool results in sync test context."""
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


class TestMcpServerHelpers:
    """Test MCP server tool functions are importable and well-formed."""

    def test_mcp_tools_importable(self) -> None:
        """All five v2 MCP tools can be imported."""
        from drift.mcp_server import (
            drift_diff,
            drift_explain,
            drift_fix_plan,
            drift_scan,
            drift_validate,
        )

        # They should all be callable functions
        assert callable(drift_scan)
        assert callable(drift_diff)
        assert callable(drift_explain)
        assert callable(drift_fix_plan)
        assert callable(drift_validate)

    def test_drift_fix_plan_uses_session_queue_fast_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Session-scoped fix_plan can reuse queued tasks without re-analysis."""
        from drift import mcp_server
        from drift.session import SessionManager

        SessionManager.reset_instance()
        start = json.loads(_run_tool(mcp_server.drift_session_start(path=str(tmp_path))))
        sid = start["session_id"]
        session = SessionManager.instance().get(sid)
        assert session is not None
        session.selected_tasks = [
            {
                "id": "T-1",
                "signal": "PFS",
                "title": "First queued task",
                "action": "Apply first fix",
            },
            {
                "id": "T-2",
                "signal": "AVS",
                "title": "Second queued task",
                "action": "Apply second fix",
            },
        ]

        def _should_not_run_fix_plan(*_args: object, **_kwargs: object) -> dict[str, object]:
            msg = "drift.api.fix_plan should not run for session fast-path"
            raise AssertionError(msg)

        monkeypatch.setattr("drift.api.fix_plan", _should_not_run_fix_plan)

        result = json.loads(_run_tool(mcp_server.drift_fix_plan(session_id=sid, max_tasks=1)))

        assert result["status"] == "ok"
        assert result["task_count"] == 1
        assert result["total_available"] == 2
        assert result["tasks"][0]["id"] == "T-1"
        assert result["cache"]["hit"] is True
        assert result["cache"]["source"] == "session.fix_plan_queue"

    def test_drift_fix_plan_uses_session_queue_fast_path_for_coder_profile(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """response_profile='coder' remains eligible for session fast-path cache."""
        from drift import mcp_server
        from drift.session import SessionManager

        SessionManager.reset_instance()
        start = json.loads(_run_tool(mcp_server.drift_session_start(path=str(tmp_path))))
        sid = start["session_id"]
        session = SessionManager.instance().get(sid)
        assert session is not None
        session.selected_tasks = [
            {
                "id": "T-1",
                "signal": "PFS",
                "title": "Queued task",
                "action": "Apply queued fix",
            }
        ]

        def _should_not_run_fix_plan(*_args: object, **_kwargs: object) -> dict[str, object]:
            msg = "drift.api.fix_plan should not run for coder session fast-path"
            raise AssertionError(msg)

        monkeypatch.setattr("drift.api.fix_plan", _should_not_run_fix_plan)

        result = json.loads(
            _run_tool(
                mcp_server.drift_fix_plan(session_id=sid, max_tasks=1, response_profile="coder")
            )
        )
        assert result["task_count"] == 1
        assert result["tasks"][0]["id"] == "T-1"
        assert result["cache"]["hit"] is True
        assert result["cache"]["source"] == "session.fix_plan_queue"

    def test_drift_fix_plan_fast_path_excludes_claimed_and_failed_tasks(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Fast-path pending queue must omit claimed and failed tasks (Issue #486)."""
        import time

        from drift import mcp_server
        from drift.session import SessionManager

        SessionManager.reset_instance()
        start = json.loads(_run_tool(mcp_server.drift_session_start(path=str(tmp_path))))
        sid = start["session_id"]
        session = SessionManager.instance().get(sid)
        assert session is not None

        session.selected_tasks = [
            {"id": "T-pending", "signal": "PFS", "title": "Pending task"},
            {"id": "T-claimed", "signal": "AVS", "title": "Claimed task"},
            {"id": "T-failed", "signal": "MDS", "title": "Failed task"},
        ]
        session.active_leases = {
            "T-claimed": {
                "agent_id": "agent-a",
                "acquired_at": time.time(),
                "expires_at": time.time() + 120,
                "lease_ttl_seconds": 120,
                "renew_count": 0,
            }
        }
        session.failed_task_ids = ["T-failed"]

        def _should_not_run_fix_plan(*_args: object, **_kwargs: object) -> dict[str, object]:
            msg = "drift.api.fix_plan should not run for session fast-path"
            raise AssertionError(msg)

        monkeypatch.setattr("drift.api.fix_plan", _should_not_run_fix_plan)

        result = json.loads(_run_tool(mcp_server.drift_fix_plan(session_id=sid, max_tasks=5)))

        assert result["status"] == "ok"
        assert result["task_count"] == 1
        assert result["total_available"] == 1
        assert [task["id"] for task in result["tasks"]] == ["T-pending"]
        assert result["remaining_by_signal"] == {"PFS": 1}
        assert result["cache"]["hit"] is True

    def test_drift_fix_plan_falls_back_to_api_when_filtered(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Explicit filters disable fast-path and trigger the regular API call."""
        from drift import mcp_server
        from drift.session import SessionManager

        SessionManager.reset_instance()
        start = json.loads(_run_tool(mcp_server.drift_session_start(path=str(tmp_path))))
        sid = start["session_id"]
        session = SessionManager.instance().get(sid)
        assert session is not None
        session.selected_tasks = [{"id": "T-1", "signal": "PFS", "title": "Queued"}]

        called = {"value": False}

        def _fake_fix_plan(*_args: object, **_kwargs: object) -> dict[str, object]:
            called["value"] = True
            return {
                "status": "ok",
                "tasks": [],
                "task_count": 0,
                "total_available": 0,
            }

        monkeypatch.setattr("drift.api.fix_plan", _fake_fix_plan)

        result = json.loads(_run_tool(mcp_server.drift_fix_plan(session_id=sid, signal="PFS")))

        assert called["value"] is True
        assert result["status"] == "ok"
        assert "cache" not in result

    def test_drift_fix_plan_falls_back_to_api_for_verifier_profile(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """response_profile='verifier' disables fast-path and uses API response shaping."""
        from drift import mcp_server
        from drift.session import SessionManager

        SessionManager.reset_instance()
        start = json.loads(_run_tool(mcp_server.drift_session_start(path=str(tmp_path))))
        sid = start["session_id"]
        session = SessionManager.instance().get(sid)
        assert session is not None
        session.selected_tasks = [{"id": "T-1", "signal": "PFS", "title": "Queued"}]

        called = {"value": False}

        def _fake_fix_plan(*_args: object, **_kwargs: object) -> dict[str, object]:
            called["value"] = True
            return {
                "status": "ok",
                "tasks": [],
                "task_count": 0,
                "total_available": 0,
                "response_profile": "verifier",
            }

        monkeypatch.setattr("drift.api.fix_plan", _fake_fix_plan)

        result = json.loads(
            _run_tool(mcp_server.drift_fix_plan(session_id=sid, response_profile="verifier"))
        )

        assert called["value"] is True
        assert result["status"] == "ok"
        assert result.get("response_profile") == "verifier"
        assert "cache" not in result

    def test_drift_explain_returns_json(self) -> None:
        """drift_explain returns valid JSON for a known signal."""
        import json as _json

        from drift.mcp_server import drift_explain

        result = _json.loads(_run_tool(drift_explain("PFS")))
        assert "name" in result
        assert "description" in result

    def test_drift_explain_unknown_topic(self) -> None:
        """drift_explain handles unknown topics gracefully."""
        import json as _json

        from drift.mcp_server import drift_explain

        result = _json.loads(_run_tool(drift_explain("NONEXISTENT_THING")))
        # Should still return valid JSON without crashing
        assert isinstance(result, dict)

    def test_drift_explain_error_code_interpolates_defaults(self) -> None:
        """drift_explain resolves DRIFT-2010 template placeholders."""
        import json as _json

        from drift.mcp_server import drift_explain

        result = _json.loads(_run_tool(drift_explain("DRIFT-2010")))
        assert result["error_code"] == "DRIFT-2010"
        assert result["summary"] == "Optional dependency missing: mcp"
        assert result["action"] == "Install with: pip install drift-analyzer[mcp]"

    def test_drift_negative_context_uses_embedding_guard(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """MCP negative-context uses embedding-disabled mode for low latency."""
        import json as _json

        from drift import mcp_server

        captured: dict[str, object] = {}

        def _fake_negative_context(
            path: str,
            *,
            scope: str | None = None,
            target_file: str | None = None,
            max_items: int = 10,
            since_days: int = 90,
            disable_embeddings: bool = False,
        ) -> dict[str, object]:
            captured["path"] = path
            captured["scope"] = scope
            captured["target_file"] = target_file
            captured["max_items"] = max_items
            captured["since_days"] = since_days
            captured["disable_embeddings"] = disable_embeddings
            return {"status": "ok", "negative_context": []}

        monkeypatch.setattr("drift.api.negative_context", _fake_negative_context)

        result = _json.loads(
            _run_tool(
                mcp_server.drift_negative_context(
                    path=".",
                    scope="repo",
                    target_file="src/drift/commands/mcp.py",
                    max_items=7,
                )
            )
        )

        assert result["status"] == "ok"
        assert captured["disable_embeddings"] is True
        assert captured["scope"] == "repo"
        assert captured["max_items"] == 7

    def test_drift_negative_context_timeout_guard(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """MCP negative-context returns structured timeout instead of hanging."""
        import json as _json
        import time

        from drift import mcp_server

        def _slow_negative_context(
            path: str,
            *,
            scope: str | None = None,
            target_file: str | None = None,
            max_items: int = 10,
            since_days: int = 90,
            disable_embeddings: bool = False,
        ) -> dict[str, object]:
            time.sleep(0.2)
            return {"status": "ok", "negative_context": []}

        monkeypatch.setattr("drift.api.negative_context", _slow_negative_context)
        monkeypatch.setattr(mcp_server, "_NEGATIVE_CONTEXT_TIMEOUT_SECONDS", 0.0)

        result = _json.loads(_run_tool(mcp_server.drift_negative_context(path=".")))

        assert result["status"] == "error"
        assert result["error_code"] == "DRIFT-2031"

    def test_drift_brief_importable(self) -> None:
        """drift_brief can be imported from MCP server."""
        from drift.mcp_server import drift_brief

        assert callable(drift_brief)

    def test_drift_brief_returns_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """drift_brief returns valid JSON with brief type."""
        import json as _json

        from drift import mcp_server

        fake_result = {
            "schema_version": "2.1",
            "type": "brief",
            "task": "add payment",
            "scope": {
                "resolved_paths": ["src/checkout"],
                "expanded_dependency_paths": [],
                "resolution_method": "keyword_match",
                "confidence": 0.7,
            },
            "risk": {"level": "LOW", "score": 0.1, "reason": ""},
            "landscape": {"drift_score": 0.2, "top_signals": []},
            "guardrails": [],
            "guardrails_prompt_block": "",
        }

        monkeypatch.setattr("drift.api.brief", lambda *a, **kw: fake_result)

        result = _json.loads(_run_tool(mcp_server.drift_brief(path=".", task="add payment")))
        assert result["type"] == "brief"
        assert result["task"] == "add payment"

    def test_drift_brief_concise_strips_landscape(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Concise response_detail strips landscape and meta fields."""
        import json as _json

        from drift import mcp_server

        fake_result = {
            "type": "brief",
            "task": "test",
            "scope": {"resolved_paths": []},
            "risk": {"level": "LOW"},
            "landscape": {"drift_score": 0.5, "top_signals": []},
            "guardrails": [],
            "guardrails_prompt_block": "",
            "meta": {"analysis_duration_ms": 100},
        }

        monkeypatch.setattr("drift.api.brief", lambda *a, **kw: fake_result)

        result = _json.loads(
            _run_tool(mcp_server.drift_brief(path=".", task="test", response_detail="concise"))
        )
        assert "landscape" not in result
        assert "meta" not in result

    def test_drift_brief_detailed_keeps_all_fields(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Detailed response_detail keeps all fields."""
        import json as _json

        from drift import mcp_server

        fake_result = {
            "type": "brief",
            "task": "test",
            "scope": {"resolved_paths": []},
            "risk": {"level": "LOW"},
            "landscape": {"drift_score": 0.5},
            "guardrails": [],
            "guardrails_prompt_block": "",
            "meta": {"analysis_duration_ms": 100},
        }

        monkeypatch.setattr("drift.api.brief", lambda *a, **kw: fake_result)

        result = _json.loads(
            _run_tool(mcp_server.drift_brief(path=".", task="test", response_detail="detailed"))
        )
        assert "landscape" in result
        assert "meta" in result

    def test_drift_brief_error_handling(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """drift_brief returns structured error on API failure."""
        import json as _json

        from drift import mcp_server

        def _raise(*a: object, **kw: object) -> None:
            msg = "Config load failed"
            raise ValueError(msg)

        monkeypatch.setattr("drift.api.brief", _raise)

        result = _json.loads(_run_tool(mcp_server.drift_brief(path=".", task="test")))
        assert result["type"] == "error"
        assert result["error_code"] == "DRIFT-5010"
        assert result["tool"] == "drift_brief"

    def test_drift_brief_records_session_trace_entry(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """drift_brief should append a drift_brief trace entry for session workflows."""
        import json as _json

        from drift import mcp_server
        from drift.session import SessionManager

        fake_result = {
            "type": "brief",
            "task": "test",
            "scope": {"resolved_paths": []},
            "risk": {"level": "LOW"},
            "guardrails": [],
            "guardrails_prompt_block": "",
        }

        monkeypatch.setattr("drift.api.brief", lambda *a, **kw: fake_result)

        SessionManager.reset_instance()
        session_manager = SessionManager.instance()
        sid = session_manager.create(str(tmp_path))

        result = _json.loads(
            _run_tool(mcp_server.drift_brief(path=".", task="test", session_id=sid))
        )

        assert result["type"] == "brief"
        assert result["session"]["session_id"] == sid

        session = session_manager.get(sid)
        assert session is not None
        assert any(entry.get("tool") == "drift_brief" for entry in session.trace)

    def test_drift_brief_in_exported_tools(self) -> None:
        """drift_brief is included in the exported MCP tools list."""
        from drift.mcp_server import _EXPORTED_MCP_TOOLS, drift_brief

        assert drift_brief in _EXPORTED_MCP_TOOLS


# ---------------------------------------------------------------------------
# CLI command — smoke tests
# ---------------------------------------------------------------------------


class TestCLICommands:
    def test_mcp_help(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--help"])
        assert result.exit_code == 0
        assert "MCP server" in result.output

    def test_mcp_no_args_shows_usage(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["mcp"])
        assert "drift mcp --serve" in result.output
        assert "drift mcp --list" in result.output
        assert "drift-analyzer[mcp]" in result.output

    def test_mcp_list_shows_tools_without_starting_server(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--list"])

        assert result.exit_code == 0
        assert "drift_scan" in result.output
        assert "drift_diff" in result.output
        assert "drift_validate" in result.output

    def test_mcp_schema_outputs_tool_parameters(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--schema"])

        assert result.exit_code == 0
        assert '"tools"' in result.output
        assert '"name": "drift_scan"' in result.output
        assert '"parameters"' in result.output

    def test_mcp_modes_are_mutually_exclusive(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--serve", "--list"])

        assert result.exit_code != 0
        assert "Use only one mode" in result.output

    def test_mcp_missing_extra_raises_structured_error(self, monkeypatch) -> None:
        from click.testing import CliRunner

        from drift import mcp_server
        from drift.cli import main
        from drift.errors import DriftSystemError

        def _raise_missing_dependency() -> None:
            raise RuntimeError("requires optional dependency 'mcp'")

        monkeypatch.setattr(mcp_server, "main", _raise_missing_dependency)

        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--serve"])

        assert isinstance(result.exception, DriftSystemError)
        assert result.exception.code == "DRIFT-2010"

    def test_mcp_non_mcp_import_error_is_not_rewritten(self, monkeypatch) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        def _raise_non_mcp_import_error():
            raise ModuleNotFoundError("No module named 'yaml'", name="yaml")

        monkeypatch.setattr("drift.commands.mcp._load_mcp_entrypoints", _raise_non_mcp_import_error)

        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--serve"])

        assert isinstance(result.exception, ModuleNotFoundError)
        assert getattr(result.exception, "name", None) == "yaml"

    def test_mcp_allow_tty_emits_startup_handshake(self, monkeypatch) -> None:
        import json as _json

        from click.testing import CliRunner

        from drift.cli import main

        class _TTY:
            @staticmethod
            def isatty() -> bool:
                return True

        monkeypatch.setattr("sys.stdin", _TTY())
        monkeypatch.setattr("drift.mcp_server.get_tool_catalog", lambda: [{"name": "drift_scan"}])
        monkeypatch.setattr("drift.mcp_server.main", lambda: None)

        runner_kwargs: dict[str, object] = {}
        if "mix_stderr" in CliRunner.__init__.__code__.co_varnames:
            runner_kwargs["mix_stderr"] = False
        runner = CliRunner(**runner_kwargs)
        result = runner.invoke(main, ["mcp", "--serve", "--allow-tty"])

        assert result.exit_code == 0
        stdout_event = _json.loads(result.stdout.strip())
        stderr_event = _json.loads(result.stderr.strip())
        assert stdout_event == stderr_event
        event = stderr_event
        assert event["event"] == "drift.mcp.startup"
        assert event["type"] == "server_started"
        assert event["ready"] is True
        assert event["tools_count"] == 1
        assert "version" in event

    def test_copilot_context_help(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["copilot-context", "--help"])
        assert result.exit_code == 0
        assert "copilot" in result.output.lower()

    def test_copilot_context_progress_goes_to_stderr_not_stdout(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        monkeypatch.setattr(
            "drift.analyzer.analyze_repo",
            lambda *_args, **_kwargs: SimpleNamespace(),
        )
        monkeypatch.setattr(
            "drift.copilot_context.generate_instructions",
            lambda *_args, **_kwargs: "# copilot-section\n",
        )

        runner_kwargs: dict[str, object] = {}
        if "mix_stderr" in CliRunner.__init__.__code__.co_varnames:
            runner_kwargs["mix_stderr"] = False
        runner = CliRunner(**runner_kwargs)
        result = runner.invoke(
            main,
            ["copilot-context", "--repo", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert result.stdout.startswith("# copilot-section")
        assert "Running drift analysis" not in result.stdout
        assert "Running drift analysis" in result.stderr

    def test_copilot_context_json_shortcut_outputs_json(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        monkeypatch.setattr(
            "drift.analyzer.analyze_repo",
            lambda *_args, **_kwargs: SimpleNamespace(),
        )
        monkeypatch.setattr(
            "drift.copilot_context.generate_constraints_payload",
            lambda *_args, **_kwargs: {
                "constraints": [
                    {
                        "signal": "PFS",
                        "severity": "high",
                        "scope": "backend/api/routers",
                        "constraint": "Use one endpoint naming scheme.",
                    }
                ]
            },
        )

        runner_kwargs: dict[str, object] = {}
        if "mix_stderr" in CliRunner.__init__.__code__.co_varnames:
            runner_kwargs["mix_stderr"] = False
        runner = CliRunner(**runner_kwargs)
        result = runner.invoke(
            main,
            ["copilot-context", "--repo", str(tmp_path), "--json"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["constraints"][0]["signal"] == "PFS"
        assert "Running drift analysis" not in result.stdout
        assert "Running drift analysis" in result.stderr

    def test_copilot_context_format_json_matches_shortcut(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        monkeypatch.setattr(
            "drift.analyzer.analyze_repo",
            lambda *_args, **_kwargs: SimpleNamespace(),
        )
        monkeypatch.setattr(
            "drift.copilot_context.generate_constraints_payload",
            lambda *_args, **_kwargs: {"constraints": []},
        )

        runner_kwargs: dict[str, object] = {}
        if "mix_stderr" in CliRunner.__init__.__code__.co_varnames:
            runner_kwargs["mix_stderr"] = False
        runner = CliRunner(**runner_kwargs)
        result = runner.invoke(
            main,
            ["copilot-context", "--repo", str(tmp_path), "--format", "json"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["constraints"] == []


# ---------------------------------------------------------------------------
# Negative property checks
# ---------------------------------------------------------------------------


class TestMcpCopilotNegativeProperties:
    """Verify negative properties of copilot_context functions."""

    def _minimal_analysis(self) -> RepoAnalysis:
        return RepoAnalysis(
            repo_path=Path("/tmp/test-repo"),
            analyzed_at=datetime.datetime(2026, 1, 1, 12, 0, 0),
            drift_score=0.0,
            findings=[],
        )

    def test_marker_begin_not_empty(self) -> None:
        assert MARKER_BEGIN is not None
        assert MARKER_BEGIN != ""

    def test_marker_end_not_empty(self) -> None:
        assert MARKER_END is not None
        assert MARKER_END != ""

    def test_constraints_payload_no_none_for_empty(self) -> None:
        payload = generate_constraints_payload(self._minimal_analysis())
        assert payload is not None
        assert not any(v is None for k, v in payload.items() if not isinstance(v, list))

    def test_constraints_payload_constraints_not_none(self) -> None:
        payload = generate_constraints_payload(self._minimal_analysis())
        assert payload.get("constraints") is not None
        assert not any(c is None for c in payload.get("constraints", []))

    def test_generate_instructions_not_none(self) -> None:
        analysis = self._minimal_analysis()
        instructions = generate_instructions(analysis)
        assert instructions is not None
        assert instructions != ""

    def test_generate_instructions_no_marker_none(self) -> None:
        analysis = self._minimal_analysis()
        instructions = generate_instructions(analysis)
        assert not (MARKER_BEGIN not in instructions)
        assert not (MARKER_END not in instructions)

    def test_constraints_with_finding_no_none(self) -> None:
        analysis = RepoAnalysis(
            repo_path=Path("/tmp/repo"),
            analyzed_at=datetime.datetime(2026, 1, 1, 12, 0, 0),
            drift_score=0.5,
            findings=[
                Finding(
                    signal_type=SignalType.PATTERN_FRAGMENTATION,
                    severity=Severity.HIGH,
                    score=0.7,
                    title="Fragment",
                    description="desc",
                    file_path=Path("app.py"),
                    start_line=1,
                    fix="Fix it",
                    impact=0.7,
                )
            ],
        )
        payload = generate_constraints_payload(analysis)
        assert payload.get("constraints") is not None
        assert not any(c is None for c in payload.get("constraints", []))

    def test_instructions_with_finding_not_empty(self) -> None:
        analysis = RepoAnalysis(
            repo_path=Path("/tmp/repo"),
            analyzed_at=datetime.datetime(2026, 1, 1, 12, 0, 0),
            drift_score=0.5,
            findings=[
                Finding(
                    signal_type=SignalType.ARCHITECTURE_VIOLATION,
                    severity=Severity.HIGH,
                    score=0.8,
                    title="Violation",
                    description="desc",
                    file_path=Path("api.py"),
                    start_line=1,
                    fix="Fix it",
                    impact=0.8,
                )
            ],
        )
        instructions = generate_instructions(analysis)
        assert instructions is not None
        assert instructions != ""

    def test_merge_into_file_no_none_result(self, tmp_path: Path) -> None:
        target = tmp_path / "COPILOT.md"
        instructions = generate_instructions(self._minimal_analysis())
        merge_into_file(target, instructions)
        content = target.read_text(encoding="utf-8")
        assert content is not None
        assert content != ""

    def test_merge_into_file_contains_markers(self, tmp_path: Path) -> None:
        target = tmp_path / "COPILOT.md"
        instructions = generate_instructions(self._minimal_analysis())
        merge_into_file(target, instructions)
        content = target.read_text(encoding="utf-8")
        assert not (MARKER_BEGIN not in content)
        assert not (MARKER_END not in content)

    def test_constraints_no_empty_strings(self) -> None:
        analysis = RepoAnalysis(
            repo_path=Path("/tmp/repo"),
            analyzed_at=datetime.datetime(2026, 1, 1, 12, 0, 0),
            drift_score=0.4,
            findings=[
                Finding(
                    signal_type=SignalType.HARDCODED_SECRET,
                    severity=Severity.CRITICAL,
                    score=0.9,
                    title="Secret",
                    description="desc",
                    file_path=Path("config.py"),
                    start_line=1,
                    fix="Remove secret",
                    impact=0.9,
                )
            ],
        )
        payload = generate_constraints_payload(analysis)
        assert not any(c == "" for c in payload.get("constraints", []))
        assert payload.get("constraints") is not None

    def test_empty_analysis_instructions_not_none(self) -> None:
        instructions = generate_instructions(self._minimal_analysis())
        assert instructions is not None
        assert not any(line is None for line in instructions.splitlines())

    def test_constraints_payload_high_score_no_none(self) -> None:
        analysis = RepoAnalysis(
            repo_path=Path("/tmp/repo"),
            analyzed_at=datetime.datetime(2026, 1, 1, 12, 0, 0),
            drift_score=0.9,
            findings=[],
        )
        payload = generate_constraints_payload(analysis)
        assert payload is not None
        assert not any(c is None for c in payload.get("constraints", []))

    def test_instructions_lines_not_empty(self) -> None:
        instructions = generate_instructions(self._minimal_analysis())
        non_empty_lines = [line for line in instructions.splitlines() if line.strip()]
        assert not any(line is None for line in non_empty_lines)
        assert len(non_empty_lines) != 0
