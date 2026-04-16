"""Tests for fix_intent module (ADR-063)."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from drift.fix_intent import (
    _EDIT_KIND_FOR_SIGNAL,
    _EXPECTED_AST_DELTA_FOR_EDIT_KIND,
    EDIT_KIND_ADD_AUTHORIZATION_CHECK,
    EDIT_KIND_ADD_DOCSTRING,
    EDIT_KIND_ADD_GUARD_CLAUSE,
    EDIT_KIND_ADD_TEST,
    EDIT_KIND_ADD_TYPE_ANNOTATION,
    EDIT_KIND_CHANGE_DEFAULT,
    EDIT_KIND_DECOUPLE_MODULES,
    EDIT_KIND_DELETE_SYMBOL,
    EDIT_KIND_EXTRACT_FUNCTION,
    EDIT_KIND_EXTRACT_MODULE,
    EDIT_KIND_MERGE_FUNCTION_BODY,
    EDIT_KIND_NARROW_EXCEPTION,
    EDIT_KIND_NORMALIZE_PATTERN,
    EDIT_KIND_REDUCE_DEPENDENCIES,
    EDIT_KIND_RELOCATE_IMPORT,
    EDIT_KIND_REMOVE_BYPASS,
    EDIT_KIND_REMOVE_IMPORT,
    EDIT_KIND_RENAME_SYMBOL,
    EDIT_KIND_REPLACE_LITERAL,
    EDIT_KIND_UNSPECIFIED,
    EDIT_KIND_UPDATE_DOCSTRING,
    EDIT_KIND_UPDATE_EXCEPTION_CONTRACT,
    FORBIDDEN_IMPLEMENTATION_CHANGE,
    FORBIDDEN_NEW_ABSTRACTION,
    FORBIDDEN_PRODUCTION_CODE_CHANGE,
    FORBIDDEN_SIGNATURE_CHANGE,
    FORBIDDEN_STYLE_CHANGE,
    FORBIDDEN_UNRELATED_REFACTOR,
    _refine_edit_kind,
    derive_fix_intent,
)
from drift.models import Severity, SignalType
from drift.task_graph import _task_to_api_dict as task_graph_task_to_api_dict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeTask:
    """Minimal AgentTask-kompatibler Stub für Tests."""

    signal_type: str = SignalType.MUTANT_DUPLICATE
    severity: Any = Severity.HIGH
    priority: int = 1
    title: str = "Test Task"
    description: str = "description"
    action: str = "Fix it"
    file_path: str | None = "src/pkg/a.py"
    start_line: int | None = 10
    end_line: int | None = 30
    symbol: str | None = "process_payment"
    related_files: list[str] = field(default_factory=list)
    complexity: str = "medium"
    expected_effect: str = ""
    success_criteria: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    automation_fit: str = "high"
    review_risk: str = "low"
    change_scope: str = "local"
    verification_strength: str = "strong"
    constraints: list[str] = field(default_factory=list)
    repair_maturity: str = "verified"
    negative_context: list[Any] = field(default_factory=list)
    expected_score_delta: float = 0.0
    blocks: list[str] = field(default_factory=list)
    batch_group: str | None = None
    preferred_order: int = 0
    parallel_with: list[str] = field(default_factory=list)


def _make_task_dict(
    file: str = "src/pkg/a.py",
    related_files: list[str] | None = None,
    canonical_refs: list[dict[str, str]] | None = None,
    allowed_files: list[str] | None = None,
    title: str = "Test Task",
) -> dict[str, Any]:
    """Minimales Task-Dict wie aus _task_to_api_dict vor fix_intent."""
    _allowed: list[str] = []
    if file:
        _allowed.append(file)
    for rf in related_files or []:
        if rf not in _allowed:
            _allowed.append(rf)
    return {
        "file": file,
        "related_files": related_files or [],
        "canonical_refs": canonical_refs or [],
        "allowed_files": allowed_files if allowed_files is not None else _allowed,
        "title": title,
    }


# ---------------------------------------------------------------------------
# TestEditKindMapping — Mapping SignalType → edit_kind
# ---------------------------------------------------------------------------


class TestEditKindMapping:
    def test_mds_edit_kind(self) -> None:
        assert _EDIT_KIND_FOR_SIGNAL[SignalType.MUTANT_DUPLICATE] == EDIT_KIND_MERGE_FUNCTION_BODY

    def test_pfs_edit_kind(self) -> None:
        assert (
            _EDIT_KIND_FOR_SIGNAL[SignalType.PATTERN_FRAGMENTATION] == EDIT_KIND_NORMALIZE_PATTERN
        )

    def test_dca_edit_kind(self) -> None:
        assert _EDIT_KIND_FOR_SIGNAL[SignalType.DEAD_CODE_ACCUMULATION] == EDIT_KIND_DELETE_SYMBOL

    def test_eds_default_edit_kind(self) -> None:
        assert _EDIT_KIND_FOR_SIGNAL[SignalType.EXPLAINABILITY_DEFICIT] == EDIT_KIND_ADD_DOCSTRING

    def test_did_edit_kind(self) -> None:
        assert _EDIT_KIND_FOR_SIGNAL[SignalType.DOC_IMPL_DRIFT] == EDIT_KIND_UPDATE_DOCSTRING

    def test_avs_edit_kind(self) -> None:
        assert _EDIT_KIND_FOR_SIGNAL[SignalType.ARCHITECTURE_VIOLATION] == EDIT_KIND_REMOVE_IMPORT

    def test_ncv_edit_kind(self) -> None:
        assert (
            _EDIT_KIND_FOR_SIGNAL[SignalType.NAMING_CONTRACT_VIOLATION] == EDIT_KIND_RENAME_SYMBOL
        )

    def test_gcd_edit_kind(self) -> None:
        assert _EDIT_KIND_FOR_SIGNAL[SignalType.GUARD_CLAUSE_DEFICIT] == EDIT_KIND_ADD_GUARD_CLAUSE

    def test_bem_edit_kind(self) -> None:
        assert (
            _EDIT_KIND_FOR_SIGNAL[SignalType.BROAD_EXCEPTION_MONOCULTURE]
            == EDIT_KIND_NARROW_EXCEPTION
        )

    def test_tvs_edit_kind(self) -> None:
        assert _EDIT_KIND_FOR_SIGNAL[SignalType.TEMPORAL_VOLATILITY] == EDIT_KIND_ADD_TEST

    def test_tpd_edit_kind(self) -> None:
        assert _EDIT_KIND_FOR_SIGNAL[SignalType.TEST_POLARITY_DEFICIT] == EDIT_KIND_ADD_TEST

    def test_unknown_signal_yields_unspecified(self) -> None:
        result = _EDIT_KIND_FOR_SIGNAL.get("no_such_signal_xyz", EDIT_KIND_UNSPECIFIED)
        assert result == EDIT_KIND_UNSPECIFIED

    def test_all_signal_types_have_mapping(self) -> None:
        """Alle bekannten SignalTypes müssen im Mapping stehen."""
        for st in SignalType:
            assert st in _EDIT_KIND_FOR_SIGNAL, f"Missing edit_kind mapping for {st}"


# ---------------------------------------------------------------------------
# TestRefineEditKind — dynamische Übersteuerungen
# ---------------------------------------------------------------------------


class TestRefineEditKind:
    def test_eds_no_docstring(self) -> None:
        result = _refine_edit_kind(
            SignalType.EXPLAINABILITY_DEFICIT,
            {"has_docstring": False, "has_return_type": True},
            EDIT_KIND_ADD_DOCSTRING,
        )
        assert result == EDIT_KIND_ADD_DOCSTRING

    def test_eds_no_return_type_but_has_docstring(self) -> None:
        result = _refine_edit_kind(
            SignalType.EXPLAINABILITY_DEFICIT,
            {"has_docstring": True, "has_return_type": False},
            EDIT_KIND_ADD_DOCSTRING,
        )
        assert result == EDIT_KIND_ADD_TYPE_ANNOTATION

    def test_eds_high_complexity_with_docstring_and_return_type(self) -> None:
        result = _refine_edit_kind(
            SignalType.EXPLAINABILITY_DEFICIT,
            {"has_docstring": True, "has_return_type": True, "complexity": 15},
            EDIT_KIND_ADD_DOCSTRING,
        )
        assert result == EDIT_KIND_EXTRACT_FUNCTION

    def test_eds_low_complexity_defaults_to_add_docstring(self) -> None:
        result = _refine_edit_kind(
            SignalType.EXPLAINABILITY_DEFICIT,
            {"has_docstring": True, "has_return_type": True, "complexity": 5},
            EDIT_KIND_ADD_DOCSTRING,
        )
        assert result == EDIT_KIND_ADD_DOCSTRING

    def test_avs_blast_radius(self) -> None:
        result = _refine_edit_kind(
            SignalType.ARCHITECTURE_VIOLATION,
            {"title": "Excessive blast radius in auth module"},
            EDIT_KIND_REMOVE_IMPORT,
        )
        assert result == EDIT_KIND_REDUCE_DEPENDENCIES

    def test_avs_layer_violation(self) -> None:
        result = _refine_edit_kind(
            SignalType.ARCHITECTURE_VIOLATION,
            {"title": "Layer violation: data imports presentation"},
            EDIT_KIND_REMOVE_IMPORT,
        )
        assert result == EDIT_KIND_REMOVE_IMPORT

    def test_unrelated_signal_returns_base(self) -> None:
        result = _refine_edit_kind(
            SignalType.MUTANT_DUPLICATE,
            {},
            EDIT_KIND_MERGE_FUNCTION_BODY,
        )
        assert result == EDIT_KIND_MERGE_FUNCTION_BODY


# ---------------------------------------------------------------------------
# TestDeriveFixIntent — vollständige Objekt-Ableitung
# ---------------------------------------------------------------------------


class TestDeriveFixIntent:
    def test_target_span_populated(self) -> None:
        t = _FakeTask(start_line=10, end_line=30)
        result = derive_fix_intent(t, _make_task_dict())
        assert result["target_span"] == {"start_line": 10, "end_line": 30}

    def test_target_span_none_when_no_start_line(self) -> None:
        t = _FakeTask(start_line=None, end_line=None)
        result = derive_fix_intent(t, _make_task_dict())
        assert result["target_span"] is None

    def test_target_span_end_line_falls_back_to_start_line(self) -> None:
        t = _FakeTask(start_line=5, end_line=None)
        result = derive_fix_intent(t, _make_task_dict())
        assert result["target_span"] == {"start_line": 5, "end_line": 5}

    def test_target_symbol_from_task(self) -> None:
        t = _FakeTask(symbol="my_function")
        result = derive_fix_intent(t, _make_task_dict())
        assert result["target_symbol"] == "my_function"

    def test_target_symbol_none_when_absent(self) -> None:
        t = _FakeTask(symbol=None)
        result = derive_fix_intent(t, _make_task_dict())
        assert result["target_symbol"] is None

    def test_canonical_source_from_refs(self) -> None:
        task_dict = _make_task_dict(
            canonical_refs=[
                {"type": "file_ref", "ref": "src/canonical/base.py", "source_signal": "PFS"}
            ]
        )
        t = _FakeTask()
        result = derive_fix_intent(t, task_dict)
        assert result["canonical_source"] == "src/canonical/base.py"

    def test_canonical_source_none_when_no_refs(self) -> None:
        t = _FakeTask()
        result = derive_fix_intent(t, _make_task_dict(canonical_refs=[]))
        assert result["canonical_source"] is None

    def test_allowed_files_mirrors_task_dict(self) -> None:
        t = _FakeTask()
        task_dict = _make_task_dict(allowed_files=["src/a.py", "src/b.py"])
        result = derive_fix_intent(t, task_dict)
        assert result["allowed_files"] == ["src/a.py", "src/b.py"]

    def test_allowed_files_empty_when_task_dict_empty(self) -> None:
        t = _FakeTask()
        result = derive_fix_intent(t, _make_task_dict(allowed_files=[]))
        assert result["allowed_files"] == []

    def test_forbidden_changes_always_includes_style(self) -> None:
        t = _FakeTask(signal_type=SignalType.MUTANT_DUPLICATE)
        result = derive_fix_intent(t, _make_task_dict())
        assert FORBIDDEN_STYLE_CHANGE in result["forbidden_changes"]

    def test_forbidden_changes_always_includes_unrelated_refactor(self) -> None:
        t = _FakeTask(signal_type=SignalType.MUTANT_DUPLICATE)
        result = derive_fix_intent(t, _make_task_dict())
        assert FORBIDDEN_UNRELATED_REFACTOR in result["forbidden_changes"]

    def test_forbidden_changes_signature_change_for_mds(self) -> None:
        t = _FakeTask(signal_type=SignalType.MUTANT_DUPLICATE)
        result = derive_fix_intent(t, _make_task_dict())
        assert FORBIDDEN_SIGNATURE_CHANGE in result["forbidden_changes"]

    def test_forbidden_changes_new_abstraction_for_mds(self) -> None:
        t = _FakeTask(signal_type=SignalType.MUTANT_DUPLICATE)
        result = derive_fix_intent(t, _make_task_dict())
        assert FORBIDDEN_NEW_ABSTRACTION in result["forbidden_changes"]

    def test_forbidden_changes_no_signature_for_add_type_annotation(self) -> None:
        """Rename/NCV: Signaturen dürfen geändert werden, aber nicht impl."""
        t = _FakeTask(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            metadata={"has_docstring": True, "has_return_type": False},
        )
        result = derive_fix_intent(t, _make_task_dict())
        assert result["edit_kind"] == EDIT_KIND_ADD_TYPE_ANNOTATION
        # Für add_type_annotation ist signature_change kein Verbot — der Fix IST die Annotation
        assert FORBIDDEN_SIGNATURE_CHANGE not in result["forbidden_changes"]

    def test_forbidden_changes_production_code_for_add_test(self) -> None:
        t = _FakeTask(signal_type=SignalType.TEMPORAL_VOLATILITY)
        result = derive_fix_intent(t, _make_task_dict())
        assert result["edit_kind"] == EDIT_KIND_ADD_TEST
        assert FORBIDDEN_PRODUCTION_CODE_CHANGE in result["forbidden_changes"]

    def test_forbidden_changes_implementation_and_signature_for_add_authorization_check(
        self,
    ) -> None:
        # EDIT_KIND_ADD_AUTHORIZATION_CHECK must forbid impl and signature rewrites (Issue #385).
        t = _FakeTask(signal_type=SignalType.MISSING_AUTHORIZATION)
        result = derive_fix_intent(t, _make_task_dict())
        assert result["edit_kind"] == EDIT_KIND_ADD_AUTHORIZATION_CHECK
        assert FORBIDDEN_IMPLEMENTATION_CHANGE in result["forbidden_changes"]
        assert FORBIDDEN_SIGNATURE_CHANGE in result["forbidden_changes"]

    def test_forbidden_changes_no_duplicates(self) -> None:
        t = _FakeTask(signal_type=SignalType.MUTANT_DUPLICATE)
        result = derive_fix_intent(t, _make_task_dict())
        forbidden = result["forbidden_changes"]
        assert len(forbidden) == len(set(forbidden)), "Duplicate entries in forbidden_changes"

    def test_expected_ast_delta_has_required_keys(self) -> None:
        t = _FakeTask()
        result = derive_fix_intent(t, _make_task_dict())
        delta = result["expected_ast_delta"]
        assert "type" in delta
        assert "scope" in delta
        assert "touches_signature" in delta

    def test_add_type_annotation_touches_signature_true(self) -> None:
        t = _FakeTask(
            signal_type=SignalType.EXPLAINABILITY_DEFICIT,
            metadata={"has_docstring": True, "has_return_type": False},
        )
        result = derive_fix_intent(t, _make_task_dict())
        assert result["expected_ast_delta"]["touches_signature"] is True

    def test_merge_function_body_does_not_touch_signature(self) -> None:
        t = _FakeTask(signal_type=SignalType.MUTANT_DUPLICATE)
        result = derive_fix_intent(t, _make_task_dict())
        assert result["expected_ast_delta"]["touches_signature"] is False

    def test_unknown_signal_yields_unspecified_edit_kind(self) -> None:
        t = _FakeTask(signal_type="no_such_signal_xyz")
        result = derive_fix_intent(t, _make_task_dict())
        assert result["edit_kind"] == EDIT_KIND_UNSPECIFIED

    def test_result_contains_all_required_keys(self) -> None:
        t = _FakeTask()
        result = derive_fix_intent(t, _make_task_dict())
        required = {
            "edit_kind",
            "target_span",
            "target_symbol",
            "canonical_source",
            "expected_ast_delta",
            "allowed_files",
            "forbidden_changes",
        }
        assert required.issubset(result.keys())

    def test_avs_blast_radius_sets_reduce_dependencies(self) -> None:
        t = _FakeTask(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            metadata={},
            title="blast radius violation",
        )
        task_dict = _make_task_dict(title="blast radius violation")
        result = derive_fix_intent(t, task_dict)
        assert result["edit_kind"] == EDIT_KIND_REDUCE_DEPENDENCIES


# ---------------------------------------------------------------------------
# TestAstDeltaCompleteness — alle edit_kinds haben einen Eintrag
# ---------------------------------------------------------------------------


class TestAstDeltaCompleteness:
    def test_all_edit_kinds_have_ast_delta(self) -> None:
        """Jeder edit_kind in der Wertemenge muss in _EXPECTED_AST_DELTA_FOR_EDIT_KIND stehen."""
        all_edit_kinds = [
            EDIT_KIND_MERGE_FUNCTION_BODY,
            EDIT_KIND_UPDATE_DOCSTRING,
            EDIT_KIND_NORMALIZE_PATTERN,
            EDIT_KIND_ADD_DOCSTRING,
            EDIT_KIND_ADD_TYPE_ANNOTATION,
            EDIT_KIND_EXTRACT_FUNCTION,
            EDIT_KIND_REMOVE_IMPORT,
            EDIT_KIND_DELETE_SYMBOL,
            EDIT_KIND_RENAME_SYMBOL,
            EDIT_KIND_ADD_GUARD_CLAUSE,
            EDIT_KIND_NARROW_EXCEPTION,
            EDIT_KIND_REMOVE_BYPASS,
            EDIT_KIND_ADD_TEST,
            EDIT_KIND_RELOCATE_IMPORT,
            EDIT_KIND_REPLACE_LITERAL,
            EDIT_KIND_CHANGE_DEFAULT,
            EDIT_KIND_ADD_AUTHORIZATION_CHECK,
            EDIT_KIND_REDUCE_DEPENDENCIES,
            EDIT_KIND_EXTRACT_MODULE,
            EDIT_KIND_DECOUPLE_MODULES,
            EDIT_KIND_UPDATE_EXCEPTION_CONTRACT,
            EDIT_KIND_UNSPECIFIED,
        ]
        for ek in all_edit_kinds:
            assert ek in _EXPECTED_AST_DELTA_FOR_EDIT_KIND, f"Missing ast_delta for {ek}"


# ---------------------------------------------------------------------------
# TestIntegration — fix_intent landet in _task_to_api_dict
# ---------------------------------------------------------------------------


class TestIntegration:
    def _make_full_task(self, signal_type: str = SignalType.MUTANT_DUPLICATE) -> Any:
        """Erzeugt einen echten AgentTask über die öffentliche Pipeline."""

        from drift.models import (
            Finding,
            RepoAnalysis,
            Severity,
        )
        from drift.output.agent_tasks import analysis_to_agent_tasks

        finding = Finding(
            signal_type=signal_type,
            severity=Severity.HIGH,
            score=0.7,
            title="Duplicate function",
            description="Two identical functions",
            file_path=Path("src/pkg/a.py"),
            start_line=10,
            end_line=30,
            related_files=[],
            fix="Merge into one",
            impact=0.5,
            metadata={"function_a": "foo", "function_b": "bar"},
        )
        analysis = RepoAnalysis(
            repo_path=Path("/tmp/repo"),
            analyzed_at=datetime.datetime(2026, 4, 12, 12, 0, 0),
            drift_score=0.5,
            findings=[finding],
        )
        tasks = analysis_to_agent_tasks(analysis)
        assert tasks, "Expected at least one task"
        return tasks[0]

    def test_fix_intent_present_in_task_to_api_dict_from_api_helpers(self) -> None:
        from drift.api_helpers import _task_to_api_dict

        task = self._make_full_task()
        payload = _task_to_api_dict(task)
        assert "fix_intent" in payload

    def test_fix_intent_present_in_task_to_api_dict_from_task_graph(self) -> None:
        task = self._make_full_task()
        payload = task_graph_task_to_api_dict(task)
        assert "fix_intent" in payload

    def test_fix_intent_has_correct_edit_kind_for_mds(self) -> None:
        from drift.api_helpers import _task_to_api_dict

        task = self._make_full_task(SignalType.MUTANT_DUPLICATE)
        payload = _task_to_api_dict(task)
        assert payload["fix_intent"]["edit_kind"] == EDIT_KIND_MERGE_FUNCTION_BODY

    def test_fix_intent_allowed_files_consistent_with_top_level(self) -> None:
        from drift.api_helpers import _task_to_api_dict

        task = self._make_full_task()
        payload = _task_to_api_dict(task)
        assert payload["fix_intent"]["allowed_files"] == payload["allowed_files"]

    def test_fix_intent_forbidden_changes_includes_universals(self) -> None:
        from drift.api_helpers import _task_to_api_dict

        task = self._make_full_task()
        payload = _task_to_api_dict(task)
        forbidden = payload["fix_intent"]["forbidden_changes"]
        assert FORBIDDEN_STYLE_CHANGE in forbidden
        assert FORBIDDEN_UNRELATED_REFACTOR in forbidden
