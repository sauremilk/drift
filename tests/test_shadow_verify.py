"""Tests für ADR-064: Shadow-Verify für cross-file-risky edit_kinds."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from drift.fix_intent import (
    CROSS_FILE_RISKY_EDIT_KINDS,
    EDIT_KIND_ADD_TEST,
    EDIT_KIND_DECOUPLE_MODULES,
    EDIT_KIND_DELETE_SYMBOL,
    EDIT_KIND_EXTRACT_FUNCTION,
    EDIT_KIND_EXTRACT_MODULE,
    EDIT_KIND_REDUCE_DEPENDENCIES,
    EDIT_KIND_RELOCATE_IMPORT,
    EDIT_KIND_REMOVE_IMPORT,
    EDIT_KIND_RENAME_SYMBOL,
    EDIT_KIND_UNSPECIFIED,
    is_cross_file_risky,
)
from drift.models import AgentTask, Severity, SignalType

# ---------------------------------------------------------------------------
# is_cross_file_risky
# ---------------------------------------------------------------------------


class TestIsCrossFileRisky:
    """is_cross_file_risky() liefert True genau für CROSS_FILE_RISKY_EDIT_KINDS."""

    @pytest.mark.parametrize(
        "kind",
        [
            EDIT_KIND_REMOVE_IMPORT,
            EDIT_KIND_RELOCATE_IMPORT,
            EDIT_KIND_REDUCE_DEPENDENCIES,
            EDIT_KIND_EXTRACT_MODULE,
            EDIT_KIND_DECOUPLE_MODULES,
            EDIT_KIND_DELETE_SYMBOL,
            EDIT_KIND_RENAME_SYMBOL,
        ],
    )
    def test_risky_kinds_return_true(self, kind: str) -> None:
        assert is_cross_file_risky(kind) is True

    @pytest.mark.parametrize(
        "kind",
        [
            EDIT_KIND_ADD_TEST,
            EDIT_KIND_EXTRACT_FUNCTION,
            EDIT_KIND_UNSPECIFIED,
            "nonexistent_kind",
        ],
    )
    def test_non_risky_kinds_return_false(self, kind: str) -> None:
        assert is_cross_file_risky(kind) is False

    def test_frozenset_immutable(self) -> None:
        with pytest.raises((AttributeError, TypeError)):
            CROSS_FILE_RISKY_EDIT_KINDS.add("anything")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AgentTask.shadow_verify / shadow_verify_scope defaults
# ---------------------------------------------------------------------------


class TestAgentTaskFields:
    """AgentTask hat die shadow_verify-Felder mit korrekten Defaults."""

    def _task(self, **kwargs: Any) -> AgentTask:
        defaults: dict[str, Any] = dict(
            id="t1",
            signal_type=SignalType.DEAD_CODE_ACCUMULATION,
            severity=Severity.MEDIUM,
            priority=5,
            title="test",
            description="desc",
            action="act",
            file_path="src/foo.py",
        )
        defaults.update(kwargs)
        return AgentTask(**defaults)

    def test_shadow_verify_default_false(self) -> None:
        t = self._task()
        assert t.shadow_verify is False

    def test_shadow_verify_scope_default_empty(self) -> None:
        t = self._task()
        assert t.shadow_verify_scope == []

    def test_shadow_verify_can_be_set_true(self) -> None:
        t = self._task(
            shadow_verify=True,
            shadow_verify_scope=["src/foo.py", "src/bar.py"],
        )
        assert t.shadow_verify is True
        assert "src/foo.py" in t.shadow_verify_scope
        assert "src/bar.py" in t.shadow_verify_scope


# ---------------------------------------------------------------------------
# _compute_shadow_verify_scope helper
# ---------------------------------------------------------------------------


class TestComputeShadowVerifyScope:
    """_compute_shadow_verify_scope baut den Scope aus task + Nachbarn."""

    def _make_task(
        self,
        task_id: str,
        *,
        file_path: str = "src/foo.py",
        related_files: list[str] | None = None,
        depends_on: list[str] | None = None,
        blocks: list[str] | None = None,
        shadow_verify: bool = True,
    ) -> AgentTask:
        return AgentTask(
            id=task_id,
            signal_type=SignalType.CO_CHANGE_COUPLING,
            severity=Severity.MEDIUM,
            priority=5,
            title="stub",
            description="desc",
            action="act",
            file_path=file_path,
            related_files=related_files or [],
            depends_on=depends_on or [],
            blocks=blocks or [],
            shadow_verify=shadow_verify,
        )

    def test_scope_contains_primary_file(self) -> None:
        from drift.output.agent_tasks import _compute_shadow_verify_scope

        task = self._make_task("t1", file_path="src/foo.py")
        scope = _compute_shadow_verify_scope(task, [task])
        assert "src/foo.py" in scope

    def test_scope_contains_related_files(self) -> None:
        from drift.output.agent_tasks import _compute_shadow_verify_scope

        task = self._make_task("t1", related_files=["src/bar.py", "src/baz.py"])
        scope = _compute_shadow_verify_scope(task, [task])
        assert "src/bar.py" in scope
        assert "src/baz.py" in scope

    def test_scope_expands_to_task_graph_neighbors(self) -> None:
        from drift.output.agent_tasks import _compute_shadow_verify_scope

        t1 = self._make_task("t1", file_path="src/a.py", depends_on=["t2"])
        t2 = self._make_task("t2", file_path="src/b.py", related_files=["src/c.py"])
        t2 = AgentTask(
            id="t2",
            signal_type=SignalType.CO_CHANGE_COUPLING,
            severity=Severity.MEDIUM,
            priority=5,
            title="stub",
            description="desc",
            action="act",
            file_path="src/b.py",
            related_files=["src/c.py"],
        )
        scope = _compute_shadow_verify_scope(t1, [t1, t2])
        # Nachbar-Task t2 hat file_path=src/b.py und related_files=[src/c.py]
        assert "src/b.py" in scope
        assert "src/c.py" in scope

    def test_scope_no_duplicates_and_sorted(self) -> None:
        from drift.output.agent_tasks import _compute_shadow_verify_scope

        task = self._make_task(
            "t1",
            file_path="src/foo.py",
            related_files=["src/foo.py", "src/bar.py"],
        )
        scope = _compute_shadow_verify_scope(task, [task])
        assert len(scope) == len(set(scope))
        assert scope == sorted(scope)


# ---------------------------------------------------------------------------
# _derive_task_contract: completion_evidence
# ---------------------------------------------------------------------------


class TestDeriveTaskContract:
    """_derive_task_contract emittiert shadow_verify_clean für risky tasks."""

    def test_nudge_safe_for_non_risky_task(self) -> None:
        from drift.api_helpers import _derive_task_contract

        result = _derive_task_contract(
            {"file": "src/foo.py", "related_files": [], "shadow_verify": False}
        )
        assert result["completion_evidence"]["type"] == "nudge_safe"
        assert result["completion_evidence"]["tool"] == "drift_nudge"

    def test_shadow_verify_clean_for_risky_task(self) -> None:
        from drift.api_helpers import _derive_task_contract

        result = _derive_task_contract(
            {"file": "src/foo.py", "related_files": [], "shadow_verify": True}
        )
        ev = result["completion_evidence"]
        assert ev["type"] == "shadow_verify_clean"
        assert ev["tool"] == "drift_shadow_verify"
        assert ev["predicate"] == "shadow_clean == true"

    def test_allowed_files_includes_file_and_related(self) -> None:
        from drift.api_helpers import _derive_task_contract

        result = _derive_task_contract(
            {
                "file": "src/a.py",
                "related_files": ["src/b.py"],
                "shadow_verify": True,
            }
        )
        assert "src/a.py" in result["allowed_files"]
        assert "src/b.py" in result["allowed_files"]

    def test_no_shadow_verify_key_defaults_to_nudge_safe(self) -> None:
        from drift.api_helpers import _derive_task_contract

        result = _derive_task_contract({"file": "src/foo.py", "related_files": []})
        assert result["completion_evidence"]["type"] == "nudge_safe"


# ---------------------------------------------------------------------------
# shadow_verify API function (mocked analyze_repo)
# ---------------------------------------------------------------------------


class TestShadowVerifyApiFunction:
    """shadow_verify() gibt korrekte Felder zurück."""

    def _make_finding(
        self,
        signal_type: str,
        file_path: str,
        title: str,
    ) -> MagicMock:
        f = MagicMock()
        f.signal_type = signal_type
        f.file_path = Path(file_path)
        f.title = title
        return f

    def _make_analysis(self, findings: list[MagicMock], drift_score: float = 0.3) -> MagicMock:
        a = MagicMock()
        a.findings = findings
        a.drift_score = drift_score
        return a

    def _make_snapshot(self, findings: list[MagicMock], drift_score: float = 0.3) -> MagicMock:
        snap = MagicMock()
        snap.findings = findings
        snap.drift_score = drift_score
        return snap

    def _make_stored(self, findings: list[MagicMock], drift_score: float = 0.3) -> MagicMock:
        stored = MagicMock()
        stored.snapshot = self._make_snapshot(findings, drift_score)
        return stored

    @patch("drift.api.shadow_verify._emit_api_telemetry")
    @patch("drift.api.shadow_verify._warn_config_issues")
    @patch("drift.api.shadow_verify._load_config_cached")
    @patch("drift.api.shadow_verify.BaselineManager")
    @patch("drift.api.shadow_verify.analyze_repo")
    def test_shadow_clean_when_no_new_findings(
        self,
        mock_analyze: MagicMock,
        mock_mgr_cls: MagicMock,
        mock_load_cfg: MagicMock,
        mock_warn: MagicMock,
        mock_emit: MagicMock,
        tmp_path: Path,
    ) -> None:
        from drift.api.shadow_verify import shadow_verify

        finding = self._make_finding("dead_code_accumulation", "src/foo.py", "Unused foo")
        mock_analyze.return_value = self._make_analysis([finding])
        stored = self._make_stored([finding])
        mgr = MagicMock()
        mgr.get.return_value = stored
        mock_mgr_cls.instance.return_value = mgr

        result = shadow_verify(
            tmp_path,
            scope_files=["src/foo.py"],
        )

        assert result["shadow_clean"] is True
        assert result["safe_to_merge"] is True
        assert result["new_finding_count"] == 0

    @patch("drift.api.shadow_verify._emit_api_telemetry")
    @patch("drift.api.shadow_verify._warn_config_issues")
    @patch("drift.api.shadow_verify._load_config_cached")
    @patch("drift.api.shadow_verify.BaselineManager")
    @patch("drift.api.shadow_verify.analyze_repo")
    def test_not_shadow_clean_when_new_findings(
        self,
        mock_analyze: MagicMock,
        mock_mgr_cls: MagicMock,
        mock_load_cfg: MagicMock,
        mock_warn: MagicMock,
        mock_emit: MagicMock,
        tmp_path: Path,
    ) -> None:
        from drift.api.shadow_verify import shadow_verify

        existing = self._make_finding("dead_code_accumulation", "src/foo.py", "Unused foo")
        new_finding = self._make_finding("co_change_coupling", "src/foo.py", "Coupling regression")

        mock_analyze.return_value = self._make_analysis([existing, new_finding], drift_score=0.5)
        stored = self._make_stored([existing], drift_score=0.3)
        mgr = MagicMock()
        mgr.get.return_value = stored
        mock_mgr_cls.instance.return_value = mgr

        result = shadow_verify(
            tmp_path,
            scope_files=["src/foo.py"],
        )

        assert result["shadow_clean"] is False
        assert result["safe_to_merge"] is False
        assert result["new_finding_count"] == 1
        assert result["delta"] > 0

    @patch("drift.api.shadow_verify._emit_api_telemetry")
    @patch("drift.api.shadow_verify._warn_config_issues")
    @patch("drift.api.shadow_verify._load_config_cached")
    @patch("drift.api.shadow_verify.BaselineManager")
    @patch("drift.api.shadow_verify.analyze_repo")
    def test_filters_findings_outside_scope(
        self,
        mock_analyze: MagicMock,
        mock_mgr_cls: MagicMock,
        mock_load_cfg: MagicMock,
        mock_warn: MagicMock,
        mock_emit: MagicMock,
        tmp_path: Path,
    ) -> None:
        from drift.api.shadow_verify import shadow_verify

        in_scope = self._make_finding("dead_code_accumulation", "src/foo.py", "In scope")
        out_of_scope = self._make_finding("dead_code_accumulation", "src/bar.py", "Out")

        mock_analyze.return_value = self._make_analysis([in_scope, out_of_scope])
        stored = self._make_stored([in_scope])
        mgr = MagicMock()
        mgr.get.return_value = stored
        mock_mgr_cls.instance.return_value = mgr

        result = shadow_verify(
            tmp_path,
            scope_files=["src/foo.py"],
        )

        # out_of_scope finding aus Bar sollte nicht als neu gezählt werden
        assert result["new_finding_count"] == 0
        assert result["shadow_clean"] is True

    @patch("drift.api.shadow_verify._emit_api_telemetry")
    @patch("drift.api.shadow_verify._warn_config_issues")
    @patch("drift.api.shadow_verify._load_config_cached")
    @patch("drift.api.shadow_verify.BaselineManager")
    @patch("drift.api.shadow_verify.analyze_repo")
    def test_no_baseline_treats_all_findings_as_new(
        self,
        mock_analyze: MagicMock,
        mock_mgr_cls: MagicMock,
        mock_load_cfg: MagicMock,
        mock_warn: MagicMock,
        mock_emit: MagicMock,
        tmp_path: Path,
    ) -> None:
        from drift.api.shadow_verify import shadow_verify

        finding = self._make_finding("dead_code_accumulation", "src/foo.py", "Unused foo")
        mock_analyze.return_value = self._make_analysis([finding])
        mgr = MagicMock()
        mgr.get.return_value = None  # no baseline
        mock_mgr_cls.instance.return_value = mgr

        result = shadow_verify(tmp_path, scope_files=["src/foo.py"])

        assert result["shadow_clean"] is False
        assert result["new_finding_count"] == 1

    def test_agent_instruction_pass(self) -> None:
        from drift.api.shadow_verify import _shadow_verify_agent_instruction

        msg = _shadow_verify_agent_instruction(shadow_clean=True, new_count=0)
        assert "PASSED" in msg
        assert "drift_nudge" in msg

    def test_agent_instruction_fail(self) -> None:
        from drift.api.shadow_verify import _shadow_verify_agent_instruction

        msg = _shadow_verify_agent_instruction(shadow_clean=False, new_count=3)
        assert "FAILED" in msg
        assert "3" in msg
        assert "drift_fix_plan" in msg


# ---------------------------------------------------------------------------
# MCP tool catalog/schema test: drift_shadow_verify is exported
# ---------------------------------------------------------------------------


class TestMcpToolExported:
    """drift_shadow_verify ist im _EXPORTED_MCP_TOOLS-Tuple enthalten."""

    def test_drift_shadow_verify_in_exported_tools(self) -> None:
        from drift.mcp_server import _EXPORTED_MCP_TOOLS

        names = {getattr(t, "__name__", str(t)) for t in _EXPORTED_MCP_TOOLS}
        assert "drift_shadow_verify" in names
