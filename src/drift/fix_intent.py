"""Fix-Intent: maschinenlesbarer Vertrag pro Agent-Task (ADR-063).

Leitet aus Signal-Typ und Finding-Metadaten ein strukturiertes ``fix_intent``-Objekt ab,
das ein Coding-Agent als präzise Patch-Boundary-Spezifikation konsumieren kann.

Das Modul wird ausschließlich in der Serialisierungsschicht genutzt
(``_task_to_api_dict`` in ``api_helpers.py`` und ``task_graph.py``).
Es mutiert keine Analyse-Daten und beeinflusst nicht das Scoring.
"""

from __future__ import annotations

from typing import Any

from drift.models import SignalType

# ---------------------------------------------------------------------------
# edit_kind — geschlossene Wertemenge (closed enum als Strings)
# ---------------------------------------------------------------------------

EDIT_KIND_MERGE_FUNCTION_BODY = "merge_function_body"
EDIT_KIND_UPDATE_DOCSTRING = "update_docstring"
EDIT_KIND_NORMALIZE_PATTERN = "normalize_pattern"
EDIT_KIND_ADD_DOCSTRING = "add_docstring"
EDIT_KIND_ADD_TYPE_ANNOTATION = "add_type_annotation"
EDIT_KIND_EXTRACT_FUNCTION = "extract_function"
EDIT_KIND_REMOVE_IMPORT = "remove_import"
EDIT_KIND_DELETE_SYMBOL = "delete_symbol"
EDIT_KIND_RENAME_SYMBOL = "rename_symbol"
EDIT_KIND_ADD_GUARD_CLAUSE = "add_guard_clause"
EDIT_KIND_NARROW_EXCEPTION = "narrow_exception"
EDIT_KIND_REMOVE_BYPASS = "remove_bypass"
EDIT_KIND_ADD_TEST = "add_test"
EDIT_KIND_RELOCATE_IMPORT = "relocate_import"
EDIT_KIND_REPLACE_LITERAL = "replace_literal"
EDIT_KIND_CHANGE_DEFAULT = "change_default"
EDIT_KIND_ADD_AUTHORIZATION_CHECK = "add_authorization_check"
EDIT_KIND_REDUCE_DEPENDENCIES = "reduce_dependencies"
EDIT_KIND_EXTRACT_MODULE = "extract_module"
EDIT_KIND_DECOUPLE_MODULES = "decouple_modules"
EDIT_KIND_UPDATE_EXCEPTION_CONTRACT = "update_exception_contract"
EDIT_KIND_SCOPE_PROMPT_BOUNDARY = "scope_prompt_boundary"
EDIT_KIND_UNSPECIFIED = "unspecified"

# forbidden_changes — geschlossene Wertemenge
FORBIDDEN_SIGNATURE_CHANGE = "signature_change"
FORBIDDEN_NEW_ABSTRACTION = "new_abstraction"
FORBIDDEN_IMPLEMENTATION_CHANGE = "implementation_change"
FORBIDDEN_CROSS_FILE_EDIT = "cross_file_edit"
FORBIDDEN_PRODUCTION_CODE_CHANGE = "production_code_change"
FORBIDDEN_STYLE_CHANGE = "style_change"
FORBIDDEN_UNRELATED_REFACTOR = "unrelated_refactor"

# Immer angehängte universelle Verbote
_UNIVERSAL_FORBIDDEN_CHANGES: list[str] = [
    FORBIDDEN_STYLE_CHANGE,
    FORBIDDEN_UNRELATED_REFACTOR,
]

# ---------------------------------------------------------------------------
# Cross-file-riskante edit_kinds — Shadow-Verify-Pflicht nach Edits
# ---------------------------------------------------------------------------

#: Edit-Klassen, bei denen drift_nudge (inkrementell/estimated) für die
#: Cross-File-Signale nicht hinreichend ist. Nach Edits dieser Klassen muss
#: ein vollständiger, scope-gebundener Verify-Lauf auf allowed_files +
#: related_files + direkte task_graph-Nachbarn ausgeführt werden.
CROSS_FILE_RISKY_EDIT_KINDS: frozenset[str] = frozenset(
    {
        EDIT_KIND_REMOVE_IMPORT,
        EDIT_KIND_RELOCATE_IMPORT,
        EDIT_KIND_REDUCE_DEPENDENCIES,
        EDIT_KIND_EXTRACT_MODULE,
        EDIT_KIND_DECOUPLE_MODULES,
        EDIT_KIND_SCOPE_PROMPT_BOUNDARY,
        EDIT_KIND_DELETE_SYMBOL,
        EDIT_KIND_RENAME_SYMBOL,
    }
)


def is_cross_file_risky(edit_kind: str) -> bool:
    """Return True when an edit_kind requires shadow-verify after editing.

    drift_nudge uses incremental/estimated analysis for cross-file signals.
    For edit_kinds listed in CROSS_FILE_RISKY_EDIT_KINDS this estimation is
    insufficient; a full scope-bounded re-scan is needed.
    """
    return edit_kind in CROSS_FILE_RISKY_EDIT_KINDS

# ---------------------------------------------------------------------------
# Signal → default edit_kind
# ---------------------------------------------------------------------------

_EDIT_KIND_FOR_SIGNAL: dict[str, str] = {
    SignalType.MUTANT_DUPLICATE: EDIT_KIND_MERGE_FUNCTION_BODY,
    SignalType.DOC_IMPL_DRIFT: EDIT_KIND_UPDATE_DOCSTRING,
    SignalType.PATTERN_FRAGMENTATION: EDIT_KIND_NORMALIZE_PATTERN,
    SignalType.EXPLAINABILITY_DEFICIT: EDIT_KIND_ADD_DOCSTRING,
    SignalType.ARCHITECTURE_VIOLATION: EDIT_KIND_REMOVE_IMPORT,
    SignalType.DEAD_CODE_ACCUMULATION: EDIT_KIND_DELETE_SYMBOL,
    SignalType.NAMING_CONTRACT_VIOLATION: EDIT_KIND_RENAME_SYMBOL,
    SignalType.GUARD_CLAUSE_DEFICIT: EDIT_KIND_ADD_GUARD_CLAUSE,
    SignalType.BROAD_EXCEPTION_MONOCULTURE: EDIT_KIND_NARROW_EXCEPTION,
    SignalType.BYPASS_ACCUMULATION: EDIT_KIND_REMOVE_BYPASS,
    SignalType.TEMPORAL_VOLATILITY: EDIT_KIND_ADD_TEST,
    SignalType.TEST_POLARITY_DEFICIT: EDIT_KIND_ADD_TEST,
    SignalType.SYSTEM_MISALIGNMENT: EDIT_KIND_RELOCATE_IMPORT,
    SignalType.HARDCODED_SECRET: EDIT_KIND_REPLACE_LITERAL,
    SignalType.INSECURE_DEFAULT: EDIT_KIND_CHANGE_DEFAULT,
    SignalType.MISSING_AUTHORIZATION: EDIT_KIND_ADD_AUTHORIZATION_CHECK,
    SignalType.COGNITIVE_COMPLEXITY: EDIT_KIND_EXTRACT_FUNCTION,
    SignalType.FAN_OUT_EXPLOSION: EDIT_KIND_REDUCE_DEPENDENCIES,
    SignalType.COHESION_DEFICIT: EDIT_KIND_EXTRACT_MODULE,
    SignalType.CO_CHANGE_COUPLING: EDIT_KIND_DECOUPLE_MODULES,
    SignalType.CIRCULAR_IMPORT: EDIT_KIND_REMOVE_IMPORT,
    SignalType.EXCEPTION_CONTRACT_DRIFT: EDIT_KIND_UPDATE_EXCEPTION_CONTRACT,
    SignalType.TS_ARCHITECTURE: EDIT_KIND_REMOVE_IMPORT,
    SignalType.PHANTOM_REFERENCE: EDIT_KIND_UPDATE_DOCSTRING,
    SignalType.TYPE_SAFETY_BYPASS: EDIT_KIND_REMOVE_BYPASS,
}

# ---------------------------------------------------------------------------
# edit_kind → expected_ast_delta
# ---------------------------------------------------------------------------

_EXPECTED_AST_DELTA_FOR_EDIT_KIND: dict[str, dict[str, Any]] = {
    EDIT_KIND_MERGE_FUNCTION_BODY: {
        "type": "body_replace",
        "scope": "function",
        "touches_signature": False,
    },
    EDIT_KIND_UPDATE_DOCSTRING: {
        "type": "docstring_update",
        "scope": "function",
        "touches_signature": False,
    },
    EDIT_KIND_NORMALIZE_PATTERN: {
        "type": "body_replace",
        "scope": "function",
        "touches_signature": False,
    },
    EDIT_KIND_ADD_DOCSTRING: {
        "type": "annotation_add",
        "scope": "function",
        "touches_signature": False,
    },
    EDIT_KIND_ADD_TYPE_ANNOTATION: {
        "type": "annotation_add",
        "scope": "function",
        "touches_signature": True,
    },
    EDIT_KIND_EXTRACT_FUNCTION: {
        "type": "symbol_extract",
        "scope": "module",
        "touches_signature": False,
    },
    EDIT_KIND_REMOVE_IMPORT: {
        "type": "import_remove",
        "scope": "module",
        "touches_signature": False,
    },
    EDIT_KIND_DELETE_SYMBOL: {
        "type": "symbol_delete",
        "scope": "module",
        "touches_signature": False,
    },
    EDIT_KIND_RENAME_SYMBOL: {
        "type": "symbol_rename",
        "scope": "module",
        "touches_signature": True,
    },
    EDIT_KIND_ADD_GUARD_CLAUSE: {
        "type": "guard_add",
        "scope": "function",
        "touches_signature": False,
    },
    EDIT_KIND_NARROW_EXCEPTION: {
        "type": "body_replace",
        "scope": "function",
        "touches_signature": False,
    },
    EDIT_KIND_REMOVE_BYPASS: {
        "type": "comment_remove",
        "scope": "line",
        "touches_signature": False,
    },
    EDIT_KIND_ADD_TEST: {
        "type": "test_add",
        "scope": "file",
        "touches_signature": False,
    },
    EDIT_KIND_RELOCATE_IMPORT: {
        "type": "import_move",
        "scope": "module",
        "touches_signature": False,
    },
    EDIT_KIND_REPLACE_LITERAL: {
        "type": "literal_replace",
        "scope": "function",
        "touches_signature": False,
    },
    EDIT_KIND_CHANGE_DEFAULT: {
        "type": "literal_replace",
        "scope": "function",
        "touches_signature": False,
    },
    EDIT_KIND_ADD_AUTHORIZATION_CHECK: {
        "type": "guard_add",
        "scope": "function",
        "touches_signature": False,
    },
    EDIT_KIND_REDUCE_DEPENDENCIES: {
        "type": "import_remove",
        "scope": "module",
        "touches_signature": False,
    },
    EDIT_KIND_EXTRACT_MODULE: {
        "type": "file_create",
        "scope": "cross-module",
        "touches_signature": False,
    },
    EDIT_KIND_DECOUPLE_MODULES: {
        "type": "import_remove",
        "scope": "cross-module",
        "touches_signature": False,
    },
    EDIT_KIND_UPDATE_EXCEPTION_CONTRACT: {
        "type": "body_replace",
        "scope": "function",
        "touches_signature": False,
    },
    EDIT_KIND_SCOPE_PROMPT_BOUNDARY: {
        "type": "boundary_add",
        "scope": "cross-module",
        "touches_signature": False,
    },
    EDIT_KIND_UNSPECIFIED: {
        "type": "unspecified",
        "scope": "local",
        "touches_signature": False,
    },
}

# ---------------------------------------------------------------------------
# edit_kind → forbidden_changes (signal-spezifisch, ohne universelle Verbote)
# ---------------------------------------------------------------------------

_FORBIDDEN_CHANGES_FOR_EDIT_KIND: dict[str, list[str]] = {
    EDIT_KIND_MERGE_FUNCTION_BODY: [
        FORBIDDEN_SIGNATURE_CHANGE,
        FORBIDDEN_NEW_ABSTRACTION,
    ],
    EDIT_KIND_UPDATE_DOCSTRING: [
        FORBIDDEN_SIGNATURE_CHANGE,
        FORBIDDEN_IMPLEMENTATION_CHANGE,
    ],
    EDIT_KIND_NORMALIZE_PATTERN: [
        FORBIDDEN_NEW_ABSTRACTION,
        FORBIDDEN_SIGNATURE_CHANGE,
    ],
    EDIT_KIND_ADD_DOCSTRING: [
        FORBIDDEN_SIGNATURE_CHANGE,
        FORBIDDEN_IMPLEMENTATION_CHANGE,
    ],
    EDIT_KIND_ADD_TYPE_ANNOTATION: [],  # Signatur-Änderung IST der Fix
    EDIT_KIND_EXTRACT_FUNCTION: [
        FORBIDDEN_SIGNATURE_CHANGE,  # bestehende Aufrufer dürfen nicht brechen
    ],
    EDIT_KIND_REMOVE_IMPORT: [
        FORBIDDEN_SIGNATURE_CHANGE,
        FORBIDDEN_NEW_ABSTRACTION,
    ],
    EDIT_KIND_DELETE_SYMBOL: [
        FORBIDDEN_NEW_ABSTRACTION,
    ],
    EDIT_KIND_RENAME_SYMBOL: [
        FORBIDDEN_IMPLEMENTATION_CHANGE,
    ],
    EDIT_KIND_ADD_GUARD_CLAUSE: [
        FORBIDDEN_SIGNATURE_CHANGE,
    ],
    EDIT_KIND_NARROW_EXCEPTION: [
        FORBIDDEN_SIGNATURE_CHANGE,
    ],
    EDIT_KIND_REMOVE_BYPASS: [
        FORBIDDEN_SIGNATURE_CHANGE,
        FORBIDDEN_IMPLEMENTATION_CHANGE,
    ],
    EDIT_KIND_ADD_TEST: [
        FORBIDDEN_PRODUCTION_CODE_CHANGE,
    ],
    EDIT_KIND_RELOCATE_IMPORT: [
        FORBIDDEN_SIGNATURE_CHANGE,
    ],
    EDIT_KIND_REPLACE_LITERAL: [
        FORBIDDEN_SIGNATURE_CHANGE,
    ],
    EDIT_KIND_CHANGE_DEFAULT: [
        FORBIDDEN_SIGNATURE_CHANGE,
    ],
    EDIT_KIND_ADD_AUTHORIZATION_CHECK: [
        FORBIDDEN_SIGNATURE_CHANGE,
        FORBIDDEN_IMPLEMENTATION_CHANGE,
    ],
    EDIT_KIND_REDUCE_DEPENDENCIES: [
        FORBIDDEN_SIGNATURE_CHANGE,
    ],
    EDIT_KIND_EXTRACT_MODULE: [],
    EDIT_KIND_DECOUPLE_MODULES: [
        FORBIDDEN_SIGNATURE_CHANGE,
    ],
    EDIT_KIND_UPDATE_EXCEPTION_CONTRACT: [],
    EDIT_KIND_SCOPE_PROMPT_BOUNDARY: [
        FORBIDDEN_SIGNATURE_CHANGE,
        FORBIDDEN_IMPLEMENTATION_CHANGE,
    ],
    EDIT_KIND_UNSPECIFIED: [],
}


# ---------------------------------------------------------------------------
# Dynamische edit_kind-Verfeinerung
# ---------------------------------------------------------------------------


def _refine_edit_kind(signal_type: str, metadata: dict[str, Any], base: str) -> str:
    """Verfeinert den default edit_kind anhand von Finding-Metadaten.

    Gibt den (möglicherweise geänderten) edit_kind-String zurück.
    """
    if signal_type == SignalType.EXPLAINABILITY_DEFICIT:
        has_docstring = metadata.get("has_docstring", True)
        has_return_type = metadata.get("has_return_type", True)
        complexity = metadata.get("complexity", 0)
        if not has_docstring:
            return EDIT_KIND_ADD_DOCSTRING
        if not has_return_type:
            return EDIT_KIND_ADD_TYPE_ANNOTATION
        if complexity > 10:
            return EDIT_KIND_EXTRACT_FUNCTION
        return EDIT_KIND_ADD_DOCSTRING  # Fallback: Docstring aufwerten

    if signal_type == SignalType.ARCHITECTURE_VIOLATION:
        title = metadata.get("title", "").lower()
        category = metadata.get("category", "").lower()
        violation_type = metadata.get("violation_type", "").lower()

        # Explicit routing via metadata fields
        if violation_type in ("decouple", "layer_violation") or category in (
            "coupling",
            "layer_violation",
        ):
            return EDIT_KIND_DECOUPLE_MODULES
        if violation_type == "fan_out" or category == "fan_out":
            return EDIT_KIND_REDUCE_DEPENDENCIES
        if violation_type in ("llm_prompt", "prompt_injection") or category in (
            "llm",
            "prompt_injection",
        ):
            return EDIT_KIND_SCOPE_PROMPT_BOUNDARY

        # Title heuristics
        if "blast" in title:
            return EDIT_KIND_REDUCE_DEPENDENCIES
        if any(kw in title for kw in ("layer", "coupling")):
            return EDIT_KIND_DECOUPLE_MODULES
        if any(kw in title for kw in ("inject", "service")):
            return EDIT_KIND_UNSPECIFIED
        if any(kw in title for kw in ("prompt", "llm", "agent")):
            return EDIT_KIND_SCOPE_PROMPT_BOUNDARY

        return EDIT_KIND_REMOVE_IMPORT

    return base


# ---------------------------------------------------------------------------
# Öffentliche API
# ---------------------------------------------------------------------------


def derive_fix_intent(t: Any, task_dict: dict[str, Any]) -> dict[str, Any]:
    """Leitet ein maschinenlesbares fix_intent-Objekt aus dem Task ab.

    Muss **nach** ``_derive_task_contract()`` aufgerufen werden, damit
    ``task_dict["allowed_files"]`` bereits befüllt ist.

    Args:
        t: ``AgentTask``-Instanz (oder kompatibles Objekt).
        task_dict: bereits serialisiertes Task-Dict (enthält u.a. ``allowed_files``).

    Returns:
        Ein Dict mit den Feldern ``edit_kind``, ``target_span``, ``target_symbol``,
        ``canonical_source``, ``expected_ast_delta``, ``allowed_files``,
        ``forbidden_changes``.
    """
    signal_type: str = getattr(t, "signal_type", "")
    metadata: dict[str, Any] = getattr(t, "metadata", {}) or {}

    # edit_kind ableiten
    base_edit_kind = _EDIT_KIND_FOR_SIGNAL.get(signal_type, EDIT_KIND_UNSPECIFIED)
    # Für AVS: title aus Finding-Metadaten oder task_dict injizieren
    if signal_type == SignalType.ARCHITECTURE_VIOLATION:
        metadata = dict(metadata)
        metadata.setdefault("title", task_dict.get("title", ""))
    edit_kind = _refine_edit_kind(signal_type, metadata, base_edit_kind)

    # target_span
    start_line: int | None = getattr(t, "start_line", None)
    end_line: int | None = getattr(t, "end_line", None)
    if start_line is not None:
        target_span: dict[str, int] | None = {
            "start_line": start_line,
            "end_line": end_line if end_line is not None else start_line,
        }
    else:
        target_span = None

    # target_symbol
    target_symbol: str | None = getattr(t, "symbol", None)

    # canonical_source: erster canonical_ref
    canonical_refs: list[dict[str, str]] = task_dict.get("canonical_refs", [])
    canonical_source: str | None = canonical_refs[0]["ref"] if canonical_refs else None

    # expected_ast_delta
    expected_ast_delta = _EXPECTED_AST_DELTA_FOR_EDIT_KIND.get(
        edit_kind,
        _EXPECTED_AST_DELTA_FOR_EDIT_KIND[EDIT_KIND_UNSPECIFIED],
    )

    # allowed_files — Mirror aus _derive_task_contract
    allowed_files: list[str] = list(task_dict.get("allowed_files", []))

    # forbidden_changes — signal-spezifisch + universell, dedupliziert
    specific = _FORBIDDEN_CHANGES_FOR_EDIT_KIND.get(edit_kind, [])
    combined = list(dict.fromkeys(specific + _UNIVERSAL_FORBIDDEN_CHANGES))

    return {
        "edit_kind": edit_kind,
        "target_span": target_span,
        "target_symbol": target_symbol,
        "canonical_source": canonical_source,
        "expected_ast_delta": expected_ast_delta,
        "allowed_files": allowed_files,
        "forbidden_changes": combined,
    }
