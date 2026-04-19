"""Agent-tasks output format — translates findings into machine-readable repair tasks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from drift import __version__
from drift.api_helpers import build_drift_score_scope
from drift.fix_intent import (
    _EDIT_KIND_FOR_SIGNAL,
    _refine_edit_kind,
    is_cross_file_risky,
)
from drift.models import (
    AgentTask,
    AutomationFit,
    ChangeScope,
    Finding,
    RegressionPattern,
    RepairMaturity,
    RepoAnalysis,
    ReviewRisk,
    Severity,
    SignalType,
    TaskComplexity,
    VerificationStrength,
)
from drift.negative_context import findings_to_negative_context, negative_context_to_dict
from drift.recommendations import Recommendation, generate_recommendations
from drift.repair_template_registry import get_registry
from drift.signal_registry import get_meta

# ---------------------------------------------------------------------------
# Deterministic task ID
# ---------------------------------------------------------------------------

_SIGNAL_PREFIX: dict[str, str] = {
    SignalType.PATTERN_FRAGMENTATION: "pfs",
    SignalType.ARCHITECTURE_VIOLATION: "avs",
    SignalType.MUTANT_DUPLICATE: "mds",
    SignalType.EXPLAINABILITY_DEFICIT: "eds",
    SignalType.TEMPORAL_VOLATILITY: "tvs",
    SignalType.SYSTEM_MISALIGNMENT: "sms",
    SignalType.DOC_IMPL_DRIFT: "dia",
    SignalType.BROAD_EXCEPTION_MONOCULTURE: "bem",
    SignalType.TEST_POLARITY_DEFICIT: "tpd",
    SignalType.GUARD_CLAUSE_DEFICIT: "gcd",
    SignalType.COHESION_DEFICIT: "cod",
    SignalType.NAMING_CONTRACT_VIOLATION: "nbv",
    SignalType.BYPASS_ACCUMULATION: "bat",
    SignalType.EXCEPTION_CONTRACT_DRIFT: "ecm",
    SignalType.CO_CHANGE_COUPLING: "ccc",
    SignalType.TS_ARCHITECTURE: "tsa",
    SignalType.COGNITIVE_COMPLEXITY: "cxs",
    SignalType.FAN_OUT_EXPLOSION: "foe",
    SignalType.CIRCULAR_IMPORT: "cir",
    SignalType.DEAD_CODE_ACCUMULATION: "dca",
    SignalType.MISSING_AUTHORIZATION: "maz",
    SignalType.INSECURE_DEFAULT: "isd",
    SignalType.HARDCODED_SECRET: "hsc",
}


def _task_id(finding: Finding) -> str:
    """Generate a deterministic, human-readable task ID."""
    prefix = _SIGNAL_PREFIX.get(finding.signal_type, finding.signal_type[:3])
    fp = finding.file_path.as_posix() if finding.file_path else ""
    blob = f"{finding.signal_type}:{fp}:{finding.title}"
    short_hash = hashlib.sha256(blob.encode()).hexdigest()[:10]
    return f"{prefix}-{short_hash}"


def _finding_fingerprint(finding: Finding) -> str:
    """Return a stable key for correlating findings and recommendations."""
    file_path = finding.file_path.as_posix() if finding.file_path else ""
    start_line = finding.start_line if finding.start_line is not None else -1
    return f"{finding.signal_type}:{file_path}:{start_line}:{finding.title}"


# ---------------------------------------------------------------------------
# Repair maturity matrix (Phase 4)
# ---------------------------------------------------------------------------
# Derived from signal_registry.SignalMeta.repair_level.
# Maps the 4-level repair taxonomy to legacy 3-level maturity strings
# so that downstream consumers (API, tests, agents) remain compatible.

_REPAIR_LEVEL_TO_MATURITY: dict[str, str] = {
    "verifiable": "verified",
    "example_based": "verified",
    "plannable": "experimental",
    "diagnosis": "indirect-only",
}


def _build_repair_maturity() -> dict[str, dict[str, str | bool]]:
    """Build REPAIR_MATURITY dict from signal registry metadata."""
    from drift.signal_registry import get_all_meta

    result: dict[str, dict[str, str | bool]] = {}
    for meta in get_all_meta():
        result[meta.signal_id] = {
            "maturity": _REPAIR_LEVEL_TO_MATURITY.get(
                meta.repair_level, "indirect-only",
            ),
            "repair_level": meta.repair_level,
            "benchmark_coverage": meta.benchmark_coverage,
            "has_recommender": meta.has_recommender,
            "has_fix_field": meta.has_fix_field,
            "has_verify_plan": meta.has_verify_plan,
            "real_world": meta.benchmark_coverage in ("strong",),
        }
    return result


REPAIR_MATURITY: dict[str, dict[str, str | bool]] = _build_repair_maturity()


# ---------------------------------------------------------------------------
# Automation fitness classification (Phase 1)
# ---------------------------------------------------------------------------

# Base classification per signal — overridden by dynamic modifiers
_SIGNAL_CLASSIFICATION: dict[str, dict[str, str]] = {
    SignalType.MUTANT_DUPLICATE: {
        "automation_fit": "high",
        "review_risk": "low",
        "change_scope": "local",
        "verification_strength": "strong",
    },
    SignalType.DOC_IMPL_DRIFT: {
        "automation_fit": "high",
        "review_risk": "low",
        "change_scope": "local",
        "verification_strength": "strong",
    },
    SignalType.DEAD_CODE_ACCUMULATION: {
        "automation_fit": "high",
        "review_risk": "low",
        "change_scope": "local",
        "verification_strength": "strong",
    },
    SignalType.NAMING_CONTRACT_VIOLATION: {
        "automation_fit": "high",
        "review_risk": "low",
        "change_scope": "local",
        "verification_strength": "strong",
    },
    SignalType.GUARD_CLAUSE_DEFICIT: {
        "automation_fit": "high",
        "review_risk": "low",
        "change_scope": "local",
        "verification_strength": "strong",
    },
    SignalType.BROAD_EXCEPTION_MONOCULTURE: {
        "automation_fit": "high",
        "review_risk": "low",
        "change_scope": "local",
        "verification_strength": "strong",
    },
    SignalType.BYPASS_ACCUMULATION: {
        "automation_fit": "medium",
        "review_risk": "low",
        "change_scope": "local",
        "verification_strength": "moderate",
    },
    SignalType.PATTERN_FRAGMENTATION: {
        "automation_fit": "medium",
        "review_risk": "low",
        "change_scope": "module",
        "verification_strength": "strong",
    },
    SignalType.EXPLAINABILITY_DEFICIT: {
        "automation_fit": "medium",
        "review_risk": "medium",
        "change_scope": "local",
        "verification_strength": "moderate",
    },
    SignalType.ARCHITECTURE_VIOLATION: {
        "automation_fit": "medium",
        "review_risk": "medium",
        "change_scope": "module",
        "verification_strength": "moderate",
    },
    SignalType.TEST_POLARITY_DEFICIT: {
        "automation_fit": "medium",
        "review_risk": "low",
        "change_scope": "local",
        "verification_strength": "strong",
    },
    SignalType.EXCEPTION_CONTRACT_DRIFT: {
        "automation_fit": "medium",
        "review_risk": "medium",
        "change_scope": "module",
        "verification_strength": "moderate",
    },
    SignalType.COGNITIVE_COMPLEXITY: {
        "automation_fit": "medium",
        "review_risk": "medium",
        "change_scope": "local",
        "verification_strength": "moderate",
    },
    SignalType.HARDCODED_SECRET: {
        "automation_fit": "medium",
        "review_risk": "medium",
        "change_scope": "local",
        "verification_strength": "strong",
    },
    SignalType.INSECURE_DEFAULT: {
        "automation_fit": "medium",
        "review_risk": "medium",
        "change_scope": "local",
        "verification_strength": "moderate",
    },
    SignalType.MISSING_AUTHORIZATION: {
        "automation_fit": "low",
        "review_risk": "high",
        "change_scope": "module",
        "verification_strength": "weak",
    },
    SignalType.CIRCULAR_IMPORT: {
        "automation_fit": "medium",
        "review_risk": "medium",
        "change_scope": "module",
        "verification_strength": "moderate",
    },
    SignalType.FAN_OUT_EXPLOSION: {
        "automation_fit": "low",
        "review_risk": "high",
        "change_scope": "cross-module",
        "verification_strength": "weak",
    },
    SignalType.TEMPORAL_VOLATILITY: {
        "automation_fit": "low",
        "review_risk": "high",
        "change_scope": "cross-module",
        "verification_strength": "weak",
    },
    SignalType.SYSTEM_MISALIGNMENT: {
        "automation_fit": "low",
        "review_risk": "medium",
        "change_scope": "module",
        "verification_strength": "moderate",
    },
    SignalType.COHESION_DEFICIT: {
        "automation_fit": "low",
        "review_risk": "high",
        "change_scope": "cross-module",
        "verification_strength": "weak",
    },
    SignalType.CO_CHANGE_COUPLING: {
        "automation_fit": "low",
        "review_risk": "high",
        "change_scope": "cross-module",
        "verification_strength": "weak",
    },
    SignalType.TS_ARCHITECTURE: {
        "automation_fit": "medium",
        "review_risk": "medium",
        "change_scope": "module",
        "verification_strength": "moderate",
    },
}

_FIT_LEVELS = ["low", "medium", "high"]
_RISK_LEVELS = ["low", "medium", "high"]
_SCOPE_LEVELS = ["local", "module", "cross-module"]
_VERIF_LEVELS = ["weak", "moderate", "strong"]


def _clamp(value: str, levels: list[str]) -> str:
    """Clamp to valid level range."""
    idx = levels.index(value) if value in levels else 1
    return levels[max(0, min(idx, len(levels) - 1))]


def _classify_task(finding: Finding, task: AgentTask) -> None:
    """Apply automation fitness classification to a task (mutates in place).

    Uses signal-specific base classification, then applies dynamic modifiers
    based on finding metadata.
    """
    base = _SIGNAL_CLASSIFICATION.get(finding.signal_type, {})
    fit = base.get("automation_fit", "medium")
    risk = base.get("review_risk", "medium")
    scope = base.get("change_scope", "local")
    verif = base.get("verification_strength", "moderate")

    # Dynamic modifier: PFS with clear canonical → higher automation fit
    if finding.signal_type == SignalType.PATTERN_FRAGMENTATION:
        meta = finding.metadata
        if meta.get("canonical_variant") and meta.get("variant_count", 0) >= 3:
            fit = "high"

    # Dynamic modifier: many related files → broader scope
    if len(finding.related_files) > 3:
        scope_idx = _SCOPE_LEVELS.index(scope) if scope in _SCOPE_LEVELS else 0
        scope = _SCOPE_LEVELS[min(scope_idx + 1, len(_SCOPE_LEVELS) - 1)]

    # Dynamic modifier: has dependencies → higher review risk
    if task.depends_on:
        risk_idx = _RISK_LEVELS.index(risk) if risk in _RISK_LEVELS else 1
        risk = _RISK_LEVELS[min(risk_idx + 1, len(_RISK_LEVELS) - 1)]

    # Dynamic modifier: high complexity → lower automation fit
    if task.complexity == "high":
        fit_idx = _FIT_LEVELS.index(fit) if fit in _FIT_LEVELS else 1
        fit = _FIT_LEVELS[max(fit_idx - 1, 0)]

    # Dynamic modifier: MDS cross-file → module scope
    if finding.signal_type == SignalType.MUTANT_DUPLICATE:
        meta = finding.metadata
        if meta.get("file_a") and meta.get("file_b") and meta["file_a"] != meta["file_b"]:
            scope = "module"

    task.automation_fit = AutomationFit(_clamp(fit, _FIT_LEVELS))
    task.review_risk = ReviewRisk(_clamp(risk, _RISK_LEVELS))
    task.change_scope = ChangeScope(_clamp(scope, _SCOPE_LEVELS))
    task.verification_strength = VerificationStrength(_clamp(verif, _VERIF_LEVELS))


# ---------------------------------------------------------------------------
# Do-not-over-fix constraints (Phase 2)
# ---------------------------------------------------------------------------

_UNIVERSAL_CONSTRAINTS = [
    "No refactoring beyond the directly affected root cause",
    "No API signature changes unless explicitly required by the fix",
    "No style or formatting changes unrelated to the root cause",
    "Minimal change only — fix the named finding, nothing more",
]

_SIGNAL_CONSTRAINTS: dict[str, list[str]] = {
    SignalType.MUTANT_DUPLICATE: [
        "Do not rename without changing the function body — Drift uses SHA256(body), not names",
        "Do not introduce new abstractions solely to deduplicate — prefer direct consolidation",
    ],
    SignalType.DOC_IMPL_DRIFT: [
        "Do not introduce new phantom references — only remove or fix existing ones",
        "Do not rewrite documentation beyond correcting the identified mismatch",
    ],
    SignalType.PATTERN_FRAGMENTATION: [
        "Do not consolidate variants that intentionally serve divergent contexts",
        "Preserve the canonical variant as-is — align others toward it",
    ],
    SignalType.EXPLAINABILITY_DEFICIT: [
        "Do not add trivial docstrings (e.g., 'This function does X') — address actual complexity",
        "Do not split functions unless complexity genuinely exceeds threshold",
    ],
    SignalType.ARCHITECTURE_VIOLATION: [
        "Do not introduce new layer violations while resolving existing ones",
        "Do not move code to a layer that creates a new circular dependency",
    ],
    SignalType.TEMPORAL_VOLATILITY: [
        "Do not add unnecessary stabilization commits — each commit must have structural value",
        "Do not lock interfaces prematurely — stabilize through tests and contracts",
    ],
    SignalType.SYSTEM_MISALIGNMENT: [
        "Do not remove dependencies that are intentionally novel — only relocate misplaced ones",
        "Verify alignment with module intent before moving imports",
    ],
}


def _generate_constraints(finding: Finding) -> list[str]:
    """Generate do-not-over-fix constraints for a task."""
    constraints = list(_UNIVERSAL_CONSTRAINTS)
    signal_specific = _SIGNAL_CONSTRAINTS.get(finding.signal_type, [])
    constraints.extend(signal_specific)
    return constraints


# ---------------------------------------------------------------------------
# Signal-specific verify plan (machine-executable verification steps)
# ---------------------------------------------------------------------------

_NUDGE_STEP: dict[str, Any] = {
    "tool": "drift_nudge",
    "action": "Confirm that the fix does not increase the drift score",
    "predicate": "safe_to_commit == true",
    "target": {},
}

_SHADOW_VERIFY_STEP_TEMPLATE: dict[str, Any] = {
    "tool": "drift_shadow_verify",
    "action": (
        "Run a scope-bounded full re-scan on allowed_files + related_files + "
        "task_graph neighbours — cross-file signals are estimated by drift_nudge "
        "and unreliable for this edit_kind"
    ),
    "predicate": "shadow_clean == true",
}


@dataclass(frozen=True)
class _VerifyPlanContext:
    """Typed context used while building a signal-specific verify plan."""

    signal_type: str
    metadata: dict[str, Any]
    file_path: str
    needs_shadow: bool


def _finalize_verify_steps(
    steps: list[dict[str, Any]],
    *,
    needs_shadow: bool,
    shadow_step_builder: Any,
    nudge_step_builder: Any,
) -> list[dict[str, Any]]:
    """Append optional shadow verify and mandatory nudge step."""
    finalized = list(steps)
    if needs_shadow:
        finalized.append(shadow_step_builder(len(finalized) + 1))
    finalized.append(nudge_step_builder(len(finalized) + 1))
    return finalized


def _shadow_verify_step(n: int, scope_files: list[str]) -> dict[str, Any]:
    """Build a shadow_verify verification step at the given 1-based index."""
    return {
        "step": n,
        **_SHADOW_VERIFY_STEP_TEMPLATE,
        "target": {"scope_files": list(scope_files)},
    }


def _compute_shadow_verify_scope(
    task: AgentTask,
    all_tasks: list[AgentTask],
) -> list[str]:
    """Compute the scope for a shadow-verify run.

    The scope is the union of:
    - task.file_path (primary file of this task)
    - task.related_files
    - related_files of all directly adjacent tasks in the task graph
      (tasks listed in task.depends_on or task.blocks)

    The result is deduplicated and sorted for stable output.
    """
    seen: dict[str, None] = {}  # ordered dedup via insertion-ordered dict
    if task.file_path:
        seen[task.file_path] = None
    for f in task.related_files:
        seen[f] = None

    neighbour_ids: set[str] = set(task.depends_on) | set(task.blocks)
    if neighbour_ids:
        task_by_id: dict[str, AgentTask] = {t.id: t for t in all_tasks}
        for nid in neighbour_ids:
            neighbour = task_by_id.get(nid)
            if neighbour is None:
                continue
            if neighbour.file_path:
                seen[neighbour.file_path] = None
            for f in neighbour.related_files:
                seen[f] = None

    return sorted(seen.keys())


def _verify_plan_for(
    finding: Finding,
    *,
    shadow_verify_scope: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return an ordered list of machine-executable verification steps.

    Each step has:
      step    — 1-based index
      tool    — logical tool name (drift_scan / grep / ast_check / import_check / drift_nudge)
      action  — imperative description of what the agent must check
      predicate — the condition that must hold true for the step to pass
      target  — signal-specific lookup data (symbol, file_path, module, etc.)

    The final step is always a drift_nudge check.
    """
    context = _VerifyPlanContext(
        signal_type=finding.signal_type,
        metadata=finding.metadata,
        file_path=finding.file_path.as_posix() if finding.file_path else "",
        needs_shadow=bool(shadow_verify_scope),
    )
    st = context.signal_type
    meta = context.metadata
    path_str = context.file_path
    needs_shadow = context.needs_shadow

    def nudge(n: int) -> dict[str, Any]:
        return {"step": n, **_NUDGE_STEP}

    def shadow(n: int) -> dict[str, Any]:
        return _shadow_verify_step(n, shadow_verify_scope or [])

    def scan_zero(n: int, **extra_target: Any) -> dict[str, Any]:
        target: dict[str, Any] = {"signal": st, "file_path": path_str}
        target.update(extra_target)
        return {
            "step": n,
            "tool": "drift_scan",
            "action": f"Re-scan and assert no {st} finding for this target",
            "predicate": "finding_count == 0",
            "target": target,
        }

    if st == SignalType.DEAD_CODE_ACCUMULATION:
        symbol = finding.symbol or meta.get("symbol", "?")
        steps: list[dict[str, Any]] = [
            {
                "step": 1,
                "tool": "grep",
                "action": (
                    f"Assert that '{symbol}' is referenced at least once "
                    "or no longer exported"
                ),
                "predicate": "reference_count >= 1 OR symbol_absent_from_exports",
                "target": {"symbol": symbol, "file_path": path_str, "scope": "repo"},
            },
            scan_zero(2),
        ]
        return _finalize_verify_steps(
            steps,
            needs_shadow=needs_shadow,
            shadow_step_builder=shadow,
            nudge_step_builder=nudge,
        )

    if st == SignalType.CO_CHANGE_COUPLING:
        file_a = meta.get("file_a", path_str)
        file_b = meta.get("file_b", meta.get("coupled_file", "?"))
        steps = [
            {
                "step": 1,
                "tool": "ast_check",
                "action": (
                    f"Assert that an explicit import edge exists between '{file_a}' and '{file_b}'"
                    " (or the co-change coupling is intentionally eliminated)"
                ),
                "predicate": "explicit_import_edge_present == true OR coupling_removed == true",
                "target": {"file_a": file_a, "file_b": file_b},
            },
            scan_zero(2, file_a=file_a, file_b=file_b),
        ]
        return _finalize_verify_steps(
            steps,
            needs_shadow=needs_shadow,
            shadow_step_builder=shadow,
            nudge_step_builder=nudge,
        )

    if st == SignalType.PATTERN_FRAGMENTATION:
        module = meta.get("module", path_str)
        return [
            {
                "step": 1,
                "tool": "drift_scan",
                "action": f"Assert that variant_count for the pattern in '{module}' is at most 1",
                "predicate": "metadata.variant_count <= 1",
                "target": {"signal": st, "module": module},
            },
            scan_zero(2, module=module),
            nudge(3),
        ]

    if st == SignalType.ARCHITECTURE_VIOLATION:
        if "circular" in finding.title.lower():
            cycle = meta.get("cycle", [])
            steps = [
                {
                    "step": 1,
                    "tool": "import_check",
                    "action": "Assert that the circular import cycle is fully broken",
                    "predicate": "cycle_length == 0",
                    "target": {"modules": [str(m) for m in cycle[:5]], "kind": "circular"},
                },
                scan_zero(2, kind="circular", modules=[str(m) for m in cycle[:5]]),
            ]
            return _finalize_verify_steps(
                steps,
                needs_shadow=needs_shadow,
                shadow_step_builder=shadow,
                nudge_step_builder=nudge,
            )
        # layer violation or blast radius
        if needs_shadow:
            return [scan_zero(1), shadow(2), nudge(3)]
        return [
            scan_zero(1),
            nudge(2),
        ]

    if st == SignalType.CIRCULAR_IMPORT:
        cycle = meta.get("cycle", [])
        steps = [
            {
                "step": 1,
                "tool": "import_check",
                "action": "Assert that the circular import cycle is fully broken",
                "predicate": "cycle_length == 0",
                "target": {"modules": [str(m) for m in cycle[:5]], "kind": "circular"},
            },
            scan_zero(2),
        ]
        return _finalize_verify_steps(
            steps,
            needs_shadow=needs_shadow,
            shadow_step_builder=shadow,
            nudge_step_builder=nudge,
        )

    if st == SignalType.TYPE_SAFETY_BYPASS:
        bypass_kinds = list(
            dict.fromkeys(b.get("kind") for b in meta.get("bypasses", []) if b.get("kind"))
        )
        return [
            {
                "step": 1,
                "tool": "ast_check",
                "action": (
                    f"Assert that effective_bypass_count in '{path_str}' is 0"
                    " or meaningfully reduced"
                ),
                "predicate": "effective_bypass_count == 0 OR count_reduced == true",
                "target": {"file_path": path_str, "bypass_kinds": bypass_kinds},
            },
            scan_zero(2),
            nudge(3),
        ]

    if st == SignalType.MUTANT_DUPLICATE:
        func_a = meta.get("function_a", "?")
        func_b = meta.get("function_b", "?")
        return [
            {
                "step": 1,
                "tool": "ast_check",
                "action": (
                    f"Assert that only one definition of '{func_a}'/'{func_b}' remains"
                    " and its body hash differs from both originals"
                ),
                "predicate": "single_definition_remains == true AND body_hash_differs == true",
                "target": {"function_a": func_a, "function_b": func_b, "file_path": path_str},
            },
            scan_zero(2),
            nudge(3),
        ]

    if st == SignalType.SYSTEM_MISALIGNMENT:
        packages = meta.get("novel_packages", [])
        return [
            {
                "step": 1,
                "tool": "grep",
                "action": (
                    f"Assert that novel imports {packages!r} in '{path_str}' are either "
                    "removed or added to drift config allowed_imports"
                ),
                "predicate": "novel_import_count == 0 OR imports_in_allowed_list == true",
                "target": {"novel_packages": packages, "file_path": path_str, "scope": "module"},
            },
            scan_zero(2),
            nudge(3),
        ]

    if st == SignalType.TEMPORAL_VOLATILITY:
        freq = meta.get("change_frequency_30d", 0)
        return [
            {
                "step": 1,
                "tool": "drift_scan",
                "action": (
                    f"Re-scan '{path_str}' and assert temporal_volatility score "
                    "is reduced (churn stabilised or file refactored)"
                ),
                "predicate": "finding_count == 0 OR score < previous_score",
                "target": {"signal": st, "file_path": path_str, "previous_freq": freq},
            },
            nudge(2),
        ]

    if st == SignalType.NAMING_CONTRACT_VIOLATION:
        func_name = meta.get("function_name", finding.symbol or "?")
        prefix = meta.get("prefix_rule", "")
        steps = [
            {
                "step": 1,
                "tool": "ast_check",
                "action": (
                    f"Assert that '{func_name}' either satisfies the '{prefix}' "
                    "contract or has been renamed to match its behaviour"
                ),
                "predicate": "contract_satisfied == true OR function_renamed == true",
                "target": {
                    "function_name": func_name,
                    "prefix_rule": prefix,
                    "file_path": path_str,
                },
            },
            scan_zero(2),
        ]
        return _finalize_verify_steps(
            steps,
            needs_shadow=needs_shadow,
            shadow_step_builder=shadow,
            nudge_step_builder=nudge,
        )

    if st == SignalType.BROAD_EXCEPTION_MONOCULTURE:
        broad = meta.get("broad_count", 0)
        total = meta.get("total_handlers", 0)
        return [
            {
                "step": 1,
                "tool": "grep",
                "action": (
                    f"Assert that broad exception handlers in '{path_str}' are reduced "
                    f"(was {broad}/{total} broad)"
                ),
                "predicate": "broad_handler_count < previous_broad_count",
                "target": {"file_path": path_str, "previous_broad": broad, "previous_total": total},
            },
            scan_zero(2),
            nudge(3),
        ]

    if st == SignalType.GUARD_CLAUSE_DEFICIT:
        if meta.get("nesting_depth"):
            func_name = meta.get("function_name", finding.symbol or "?")
            depth = meta.get("nesting_depth", 0)
            return [
                {
                    "step": 1,
                    "tool": "ast_check",
                    "action": (
                        f"Assert that nesting depth of '{func_name}' in '{path_str}' "
                        f"is at or below threshold (was {depth})"
                    ),
                    "predicate": "nesting_depth <= threshold",
                    "target": {
                        "function_name": func_name,
                        "file_path": path_str,
                        "previous_depth": depth,
                    },
                },
                scan_zero(2),
                nudge(3),
            ]
        guarded_ratio = meta.get("guarded_ratio", 0)
        return [
            {
                "step": 1,
                "tool": "drift_scan",
                "action": (
                    f"Re-scan '{path_str}' and assert guarded_ratio is improved "
                    f"(was {guarded_ratio:.1%})"
                ),
                "predicate": "finding_count == 0 OR metadata.guarded_ratio > previous_ratio",
                "target": {"signal": st, "file_path": path_str, "previous_ratio": guarded_ratio},
            },
            nudge(2),
        ]

    if st == SignalType.COGNITIVE_COMPLEXITY:
        func_name = meta.get("function_name", finding.symbol or "?")
        cc = meta.get("cognitive_complexity", 0)
        threshold = meta.get("threshold", 15)
        return [
            {
                "step": 1,
                "tool": "ast_check",
                "action": (
                    f"Assert that cognitive complexity of '{func_name}' in '{path_str}' "
                    f"is at or below threshold (was {cc}, threshold {threshold})"
                ),
                "predicate": "cognitive_complexity <= threshold",
                "target": {
                    "function_name": func_name,
                    "file_path": path_str,
                    "previous_cc": cc,
                    "threshold": threshold,
                },
            },
            scan_zero(2),
            nudge(3),
        ]

    if st == SignalType.HARDCODED_SECRET:
        var_name = meta.get("variable", finding.symbol or "?")
        return [
            {
                "step": 1,
                "tool": "grep",
                "action": (
                    f"Assert that '{var_name}' in '{path_str}' no longer contains "
                    "a hardcoded literal value (replaced by env-var or secrets manager)"
                ),
                "predicate": "hardcoded_literal_count == 0",
                "target": {"variable": var_name, "file_path": path_str, "scope": "file"},
            },
            scan_zero(2),
            nudge(3),
        ]

    if st == SignalType.MISSING_AUTHORIZATION:
        endpoint = meta.get("endpoint_name", finding.symbol or "?")
        framework = meta.get("framework", "unknown")
        return [
            {
                "step": 1,
                "tool": "ast_check",
                "action": (
                    f"Assert that endpoint '{endpoint}' in '{path_str}' now has "
                    f"an authorization decorator or middleware ({framework})"
                ),
                "predicate": "auth_mechanism != 'none'",
                "target": {
                    "endpoint_name": endpoint,
                    "framework": framework,
                    "file_path": path_str,
                },
            },
            scan_zero(2),
            nudge(3),
        ]

    if st == SignalType.BYPASS_ACCUMULATION:
        total = meta.get("total_markers", 0)
        density = meta.get("bypass_density", 0)
        return [
            {
                "step": 1,
                "tool": "grep",
                "action": (
                    f"Assert that bypass markers in '{path_str}' are reduced "
                    f"(was {total} markers, density {density:.4f})"
                ),
                "predicate": "total_markers < previous_total OR bypass_density < previous_density",
                "target": {
                    "file_path": path_str,
                    "previous_total": total,
                    "previous_density": density,
                },
            },
            scan_zero(2),
            nudge(3),
        ]

    if st == SignalType.EXCEPTION_CONTRACT_DRIFT:
        funcs = meta.get("diverged_functions", [])
        ref = meta.get("comparison_ref", "HEAD~5")
        return [
            {
                "step": 1,
                "tool": "ast_check",
                "action": (
                    f"Assert that exception contracts in '{path_str}' for "
                    f"{funcs[:3]!r} are restored or intentionally updated"
                ),
                "predicate": "divergence_count == 0 OR contracts_documented == true",
                "target": {
                    "file_path": path_str,
                    "diverged_functions": funcs[:5],
                    "comparison_ref": ref,
                },
            },
            scan_zero(2),
            nudge(3),
        ]

    if st == SignalType.FAN_OUT_EXPLOSION:
        count = meta.get("unique_import_count", 0)
        threshold = meta.get("threshold", 15)
        return [
            {
                "step": 1,
                "tool": "import_check",
                "action": (
                    f"Assert that import fan-out of '{path_str}' is at or below "
                    f"threshold (was {count}, threshold {threshold})"
                ),
                "predicate": "unique_import_count <= threshold",
                "target": {
                    "file_path": path_str,
                    "previous_count": count,
                    "threshold": threshold,
                },
            },
            scan_zero(2),
            nudge(3),
        ]

    if st == SignalType.PHANTOM_REFERENCE:
        names = [
            p.get("name", "?") if isinstance(p, dict) else str(p)
            for p in meta.get("phantom_names", [])[:5]
        ]
        count = meta.get("phantom_count", 0)
        return [
            {
                "step": 1,
                "tool": "ast_check",
                "action": (
                    f"Assert that phantom references {names!r} in '{path_str}' "
                    "are now resolvable (imported, implemented, or removed)"
                ),
                "predicate": "phantom_count == 0 OR all_names_resolvable == true",
                "target": {
                    "file_path": path_str,
                    "phantom_names": names,
                    "previous_count": count,
                },
            },
            scan_zero(2),
            nudge(3),
        ]

    if st == SignalType.TEST_POLARITY_DEFICIT:
        neg_ratio = meta.get("negative_ratio", 0)
        neg_count = meta.get("negative_assertions", 0)
        zero_tests = meta.get("zero_assertion_tests", [])
        if zero_tests:
            return [
                {
                    "step": 1,
                    "tool": "ast_check",
                    "action": (
                        f"Assert that zero-assertion tests in '{path_str}' "
                        f"now contain at least one assertion each ({zero_tests[:3]!r})"
                    ),
                    "predicate": "zero_assertion_count == 0",
                    "target": {
                        "file_path": path_str,
                        "zero_assertion_tests": zero_tests[:5],
                    },
                },
                scan_zero(2),
                nudge(3),
            ]
        return [
            {
                "step": 1,
                "tool": "ast_check",
                "action": (
                    f"Assert that negative_ratio in '{path_str}' is improved "
                    f"(was {neg_ratio:.1%}, {neg_count} negative assertions)"
                ),
                "predicate": "negative_ratio > previous_ratio",
                "target": {
                    "file_path": path_str,
                    "previous_ratio": neg_ratio,
                    "previous_negative": neg_count,
                },
            },
            scan_zero(2),
            nudge(3),
        ]

    if st == SignalType.TS_ARCHITECTURE:
        rule_id = meta.get("rule_id", "")
        if rule_id == "circular-module-detection":
            cycle_nodes = meta.get("cycle_nodes", [])
            return [
                {
                    "step": 1,
                    "tool": "import_check",
                    "action": "Assert that the circular module dependency is broken",
                    "predicate": "cycle_length == 0",
                    "target": {
                        "modules": [str(n) for n in cycle_nodes[:5]],
                        "kind": "circular",
                    },
                },
                scan_zero(2),
                nudge(3),
            ]
        # cross-package, layer-leak, ui-to-infra — all re-scan verifiable
        return [
            scan_zero(1, rule_id=rule_id),
            nudge(2),
        ]

    # Generic fallback: re-scan + [shadow +] nudge
    if needs_shadow:
        return [scan_zero(1), shadow(2), nudge(3)]
    return [
        scan_zero(1),
        nudge(2),
    ]


# ---------------------------------------------------------------------------
# Signal-specific success criteria (Phase 3 enrichment)
# ---------------------------------------------------------------------------


def _success_criteria_for(finding: Finding) -> list[str]:
    """Return machine-verifiable success criteria for a finding."""
    st = finding.signal_type
    meta = finding.metadata
    path_str = finding.file_path.as_posix() if finding.file_path else "the affected module"

    base = ["All existing tests pass after the change"]

    if st == SignalType.PATTERN_FRAGMENTATION:
        module = meta.get("module", path_str)
        return [
            f"Pattern variants in {module} reduced to 1 (canonical)",
            f"`drift scan` reports no pattern_fragmentation finding for {module}",
            *base,
            "FALSE-FIX CHECK: if variant_count unchanged but score drops, the fix is cosmetic",
        ]

    if st == SignalType.ARCHITECTURE_VIOLATION:
        if "circular" in finding.title.lower():
            cycle = meta.get("cycle", [])
            cycle_str = " → ".join(str(c) for c in cycle[:5])
            return [
                f"Circular dependency resolved: no cycle between {cycle_str}",
                "`drift scan` reports no circular dependency for these modules",
                *base,
                "FALSE-FIX CHECK: if cycle length unchanged, the fix merely relocated the cycle",
            ]
        if "blast" in finding.title.lower():
            return [
                f"Blast radius of {path_str} reduced below threshold",
                "`drift scan` reports no blast_radius finding for this module",
                *base,
            ]
        # layer violation
        return [
            f"No upward layer import from {path_str}",
            "`drift scan` reports no layer violation for this file",
            *base,
            "FALSE-FIX CHECK: if new upward imports appear elsewhere,"
            " the violation was shifted not fixed",
        ]

    if st == SignalType.MUTANT_DUPLICATE:
        func_a = meta.get("function_a", "?")
        func_b = meta.get("function_b", "?")
        return [
            f"Functions '{func_a}' and '{func_b}' merged into a single implementation",
            "No mutant_duplicate finding for these functions in `drift scan`",
            *base,
            "FALSE-FIX CHECK: renaming without body change will not resolve this"
            " — body hash must differ",
        ]

    if st == SignalType.EXPLAINABILITY_DEFICIT:
        func_name = meta.get("function_name", "?")
        criteria = [*base]
        if not meta.get("has_docstring", True):
            criteria.insert(0, f"Function '{func_name}' has a docstring")
        if not meta.get("has_return_type", True):
            criteria.insert(0, f"Function '{func_name}' has a return type annotation")
        if meta.get("complexity", 0) > 10:
            criteria.insert(
                0, f"Function '{func_name}' complexity ≤ 10 or split into sub-functions"
            )
        criteria.append(
            "FALSE-FIX CHECK: trivial docstrings without addressing complexity are insufficient"
        )
        return criteria

    if st == SignalType.TEMPORAL_VOLATILITY:
        return [
            f"Integration tests exist for {path_str}",
            "Module churn stabilized (no unnecessary refactoring commits)",
            *base,
            "SIDE-EFFECT NOTE: repair commits may cause transient TVS findings"
            " — this stabilizes over time",
        ]

    if st == SignalType.SYSTEM_MISALIGNMENT:
        novel = meta.get("novel_imports", meta.get("novel_dependencies", []))
        dep_str = ", ".join(str(d) for d in novel[:5]) if novel else "novel dependencies"
        return [
            f"Dependencies ({dep_str}) documented or moved to appropriate module",
            *base,
            "FALSE-FIX CHECK: moving imports without aligning module responsibility"
            " is insufficient",
        ]

    if st == SignalType.DOC_IMPL_DRIFT:
        return [
            f"Documentation and implementation aligned for {path_str}",
            "`drift scan` reports no doc_impl_drift finding for this file",
            *base,
        ]

    if st == SignalType.BROAD_EXCEPTION_MONOCULTURE:
        return [
            f"Broad exception handlers in {path_str} replaced with specific catches",
            "`drift scan` reports no broad_exception_monoculture finding for this module",
            *base,
            "FALSE-FIX CHECK: wrapping bare except in a new try/except is insufficient",
        ]

    if st == SignalType.TEST_POLARITY_DEFICIT:
        return [
            f"Negative-path tests added for {path_str} (pytest.raises or boundary checks)",
            "`drift scan` reports no test_polarity_deficit finding for this test file",
            *base,
        ]

    if st == SignalType.GUARD_CLAUSE_DEFICIT:
        return [
            f"Guard clauses added to public functions in {path_str}",
            "`drift scan` reports no guard_clause_deficit finding for this module",
            *base,
        ]

    if st == SignalType.NAMING_CONTRACT_VIOLATION:
        func_name = meta.get("function_name", finding.symbol or "?")
        return [
            f"Function '{func_name}' behaviour matches its naming contract",
            "`drift scan` reports no naming_contract_violation for this function",
            *base,
            "FALSE-FIX CHECK: renaming without behaviour change may be valid if"
            " the new name accurately describes the implementation",
        ]

    if st == SignalType.BYPASS_ACCUMULATION:
        density = meta.get("density", 0)
        return [
            f"Bypass marker density in {path_str} reduced below 0.05/LOC"
            f" (current: {density:.3f})" if density else
            f"Bypass marker density in {path_str} reduced below 0.05/LOC",
            "`drift scan` reports no bypass_accumulation finding for this module",
            *base,
        ]

    if st == SignalType.EXCEPTION_CONTRACT_DRIFT:
        func_name = meta.get("function_name", finding.symbol or "?")
        return [
            f"Exception contract of '{func_name}' documented and stable",
            "`drift scan` reports no exception_contract_drift for this function",
            *base,
        ]

    if st == SignalType.COHESION_DEFICIT:
        return [
            f"Cohesion improved: {path_str} split or members regrouped by responsibility",
            "`drift scan` reports no cohesion_deficit finding for this module",
            *base,
        ]

    if st == SignalType.CO_CHANGE_COUPLING:
        coupled = meta.get("coupled_file", "?")
        return [
            f"Hidden coupling between {path_str} and {coupled} made explicit or eliminated",
            "`drift scan` reports no co_change_coupling finding for this file pair",
            *base,
        ]

    if st == SignalType.COGNITIVE_COMPLEXITY:
        func_name = meta.get("function_name", finding.symbol or "?")
        threshold = meta.get("threshold", 15)
        return [
            f"Cognitive complexity of '{func_name}' drops below {threshold}",
            "`drift scan` reports no cognitive_complexity finding for this function",
            *base,
        ]

    if st == SignalType.FAN_OUT_EXPLOSION:
        return [
            f"Import fan-out of {path_str} reduced below repository median threshold",
            "`drift scan` reports no fan_out_explosion finding for this module",
            *base,
        ]

    if st == SignalType.CIRCULAR_IMPORT:
        cycle = meta.get("cycle", [])
        cycle_str = " → ".join(str(c) for c in cycle[:5]) if cycle else path_str
        return [
            f"Circular import cycle broken: {cycle_str}",
            "`drift scan` reports no circular_import finding for these modules",
            *base,
            "FALSE-FIX CHECK: if cycle length unchanged, the fix merely relocated the cycle",
        ]

    if st == SignalType.DEAD_CODE_ACCUMULATION:
        symbol = finding.symbol or meta.get("symbol", "?")
        return [
            f"Dead symbol '{symbol}' removed or referenced by at least one import",
            "`drift scan` reports no dead_code_accumulation finding for this symbol",
            *base,
        ]

    if st == SignalType.MISSING_AUTHORIZATION:
        endpoint = meta.get("endpoint", finding.symbol or "?")
        return [
            f"Endpoint '{endpoint}' has an authentication/authorization check",
            "`drift scan` reports no missing_authorization finding for this endpoint",
            *base,
        ]

    if st == SignalType.INSECURE_DEFAULT:
        setting = meta.get("setting", finding.symbol or "?")
        return [
            f"Insecure default '{setting}' replaced with secure value",
            "`drift scan` reports no insecure_default finding for this setting",
            *base,
        ]

    if st == SignalType.HARDCODED_SECRET:
        return [
            f"Hardcoded secret in {path_str} moved to environment variable or secrets manager",
            "`drift scan` reports no hardcoded_secret finding for this file",
            *base,
        ]

    if st == SignalType.TS_ARCHITECTURE:
        return [
            f"TypeScript layer violation in {path_str} resolved",
            "`drift scan` reports no ts_architecture finding for this file",
            *base,
        ]

    if st == SignalType.PHANTOM_REFERENCE:
        phantoms = meta.get("phantom_names", [])
        phantoms_str = ", ".join(f"'{p}'" for p in phantoms[:5]) if phantoms else "phantom names"
        return [
            f"Phantom references ({phantoms_str}) in {path_str} resolved: "
            "either import added, function defined, or dead call removed",
            "`drift scan` reports no phantom_reference finding for this file",
            *base,
        ]

    if st == SignalType.TYPE_SAFETY_BYPASS:
        return [
            f"Type safety bypass count in {path_str} reduced below threshold",
            "`drift scan` reports no type_safety_bypass finding for this file",
            *base,
        ]

    return base


# ---------------------------------------------------------------------------
# Signal-specific expected effect
# ---------------------------------------------------------------------------


def _expected_effect_for(finding: Finding) -> str:
    """Describe the expected structural improvement."""
    st = finding.signal_type
    meta = finding.metadata

    if st == SignalType.PATTERN_FRAGMENTATION:
        variants = meta.get("variant_count", 0)
        module = meta.get("module", "the module")
        return (
            f"Reduces pattern variants from {variants} to 1 in {module}, "
            f"lowering PFS signal contribution to the drift score"
        )

    if st == SignalType.ARCHITECTURE_VIOLATION:
        if "circular" in finding.title.lower():
            return "Eliminates circular dependency, enabling independent module evolution"
        if "blast" in finding.title.lower():
            return "Reduces blast radius, limiting change propagation across the codebase"
        return "Restores layer boundary, preventing upward coupling"

    if st == SignalType.MUTANT_DUPLICATE:
        sim = meta.get("similarity", 0.0)
        return f"Eliminates near-duplicate ({sim:.0%} similar), reducing maintenance surface"

    if st == SignalType.EXPLAINABILITY_DEFICIT:
        return "Improves code explainability, reducing onboarding cost and review friction"

    if st == SignalType.TEMPORAL_VOLATILITY:
        return "Stabilizes a high-churn module, reducing regression risk"

    if st == SignalType.SYSTEM_MISALIGNMENT:
        return "Aligns dependencies with established module patterns"

    return "Reduces architectural drift score"


# ---------------------------------------------------------------------------
# Signal-specific root cause (why the problem arose)
# ---------------------------------------------------------------------------


def _root_cause_for(finding: Finding) -> str | None:
    """Return a concise root-cause string explaining why this finding arose.

    Distinct from ``description`` (what was detected) and ``fix`` (what to do):
    this answers *why* the problem occurred so agents address the underlying
    cause rather than only the immediate symptom.
    """
    st = finding.signal_type
    meta = finding.metadata

    if st == SignalType.PATTERN_FRAGMENTATION:
        variants = meta.get("variant_count", 0)
        return (
            f"Multiple independent coding sessions applied {variants} incompatible variants "
            "of the same pattern without consulting the existing canonical approach"
        )

    if st == SignalType.MUTANT_DUPLICATE:
        return (
            "A function was copy-pasted across files and both copies evolved independently "
            "instead of being consolidated into a shared abstraction from the start"
        )

    if st == SignalType.ARCHITECTURE_VIOLATION:
        if "circular" in finding.title.lower():
            return (
                "Mutual dependency between modules grew through incremental feature additions "
                "where each addition imported from a layer it should not depend on"
            )
        return (
            "Code was placed in the wrong architectural layer — typically a convenience import "
            "that bypassed the defined layer boundaries"
        )

    if st == SignalType.EXPLAINABILITY_DEFICIT:
        return (
            "Function complexity grew incrementally without corresponding documentation updates; "
            "no return type annotation was added when the function's contract became non-obvious"
        )

    if st == SignalType.TEMPORAL_VOLATILITY:
        return (
            "The file is modified too frequently relative to its stability contract — "
            "often caused by insufficient abstraction or missing tests that force exploratory edits"
        )

    if st == SignalType.SYSTEM_MISALIGNMENT:
        return (
            "New dependencies were added to a module without checking its established import "
            "profile, causing the module to drift from its original responsibility"
        )

    if st == SignalType.DEAD_CODE_ACCUMULATION:
        return (
            "The symbol was never removed after its callers were refactored or deleted — "
            "cleanup was deferred and then forgotten"
        )

    if st == SignalType.NAMING_CONTRACT_VIOLATION:
        prefix = meta.get("prefix_rule", "the naming prefix")
        return (
            f"A function was named with {prefix!r} implying behaviour it does not implement; "
            "the name was chosen for familiarity rather than accuracy"
        )

    if st == SignalType.GUARD_CLAUSE_DEFICIT:
        return (
            "Validation logic was added inline via nested if-blocks instead of early-return "
            "guard clauses — each condition was added reactively to handle a new edge case"
        )

    if st == SignalType.BROAD_EXCEPTION_MONOCULTURE:
        return (
            "Exception handling was added hastily using `except Exception` or bare `except` "
            "because the specific error types were not known or enumerated at the time"
        )

    if st == SignalType.DOC_IMPL_DRIFT:
        return (
            "Documentation was written for an earlier API version and not updated when the "
            "implementation changed — docs and code were modified in separate, unlinked PRs"
        )

    if st == SignalType.TEST_POLARITY_DEFICIT:
        return (
            "Test cases assert only that code runs without error; boundary conditions and "
            "error paths were not tested because the happy path was the only concern during "
            "initial implementation"
        )

    if st == SignalType.EXCEPTION_CONTRACT_DRIFT:
        return (
            "The exception-raising contract of a function changed (raises added or removed) "
            "without updating callers or documentation — callers now make incorrect assumptions"
        )

    if st == SignalType.CO_CHANGE_COUPLING:
        return (
            "Two files are always modified together in the same commit, revealing hidden "
            "semantic coupling that was never made explicit through an import or shared abstraction"
        )

    if st == SignalType.COHESION_DEFICIT:
        return (
            "Module responsibilities expanded over time through feature additions without "
            "splitting into sub-modules, reducing cohesion below the original design intent"
        )

    if st == SignalType.FAN_OUT_EXPLOSION:
        return (
            "The module accumulated imports from many unrelated packages — each feature "
            "addition required one more dependency without questioning whether it belongs here"
        )

    if st == SignalType.CIRCULAR_IMPORT:
        return (
            "A circular import was created when a lower-level module imported from a "
            "higher-level module to avoid code duplication, violating the dependency direction"
        )

    if st == SignalType.HARDCODED_SECRET:
        return (
            "A secret value was hardcoded directly in source during initial development "
            "and was never migrated to an environment variable or secrets manager"
        )

    if st == SignalType.INSECURE_DEFAULT:
        return (
            "An insecure default value was set for convenience during initial implementation "
            "and was never updated for production use"
        )

    if st == SignalType.MISSING_AUTHORIZATION:
        return (
            "An authorization check was omitted during initial endpoint creation, or was "
            "inadvertently removed during a refactoring that changed the middleware stack"
        )

    if st == SignalType.TYPE_SAFETY_BYPASS:
        return (
            "A type safety bypass (cast / ignore / Any) was added to unblock a type error "
            "without addressing the underlying type mismatch"
        )

    if st == SignalType.PHANTOM_REFERENCE:
        return (
            "A symbol is referenced in documentation or code comments but is not defined or "
            "imported in the current scope — the reference was invalidated by a rename or deletion"
        )

    if st == SignalType.COGNITIVE_COMPLEXITY:
        return (
            "Cognitive complexity grew through nested conditionals and loops added "
            "incrementally to handle edge cases, with no refactoring checkpoint"
        )

    if st == SignalType.BYPASS_ACCUMULATION:
        return (
            "Bypass markers (noqa, type: ignore, pragma) accumulated as short-term workarounds "
            "that were deferred for resolution but never revisited"
        )

    if st == SignalType.TS_ARCHITECTURE:
        return (
            "A TypeScript layer boundary was violated — a UI component imported infrastructure "
            "code directly instead of going through the service layer"
        )

    return None


# ---------------------------------------------------------------------------
# Dependency computation
# ---------------------------------------------------------------------------


def _compute_dependencies(tasks: list[AgentTask]) -> None:
    """Set intra-module depends_on edges and dependency_depth (mutates tasks in place).

    Rule: AVS circular-dependency tasks block AVS blast-radius / layer tasks
    in the same module (solving the cycle first makes other fixes feasible).

    After edges are computed, a BFS pass assigns ``dependency_depth`` metadata:
    tasks with no dependencies get depth 0; tasks that depend only on depth-0
    tasks get depth 1, and so on.  Agents should fix depth-0 tasks first.
    """
    # Index circular-dep task IDs by their module path
    circular_ids_by_module: dict[str, list[str]] = {}
    for t in tasks:
        if (
            t.signal_type == SignalType.ARCHITECTURE_VIOLATION
            and "circular" in t.title.lower()
            and t.file_path
        ):
            module = str(t.file_path).rsplit("/", 1)[0] if "/" in str(t.file_path) else ""
            circular_ids_by_module.setdefault(module, []).append(t.id)

    if not circular_ids_by_module:
        # No dependencies → all tasks at depth 0
        for t in tasks:
            t.metadata["dependency_depth"] = 0
        return

    for t in tasks:
        if (
            t.signal_type == SignalType.ARCHITECTURE_VIOLATION
            and "circular" not in t.title.lower()
            and t.file_path
        ):
            module = str(t.file_path).rsplit("/", 1)[0] if "/" in str(t.file_path) else ""
            deps = circular_ids_by_module.get(module, [])
            if deps:
                t.depends_on = [d for d in deps if d != t.id]

    # BFS depth computation
    depth: dict[str, int] = {}
    # Seed: tasks with no dependencies are depth 0
    queue = [t.id for t in tasks if not t.depends_on]
    for tid in queue:
        depth[tid] = 0
    visited = set(queue)
    while queue:
        current_id = queue.pop(0)
        for t in tasks:
            if (
                current_id in t.depends_on
                and t.id not in visited
                and all(d in depth for d in t.depends_on)
            ):
                depth[t.id] = max(depth[d] for d in t.depends_on) + 1
                visited.add(t.id)
                queue.append(t.id)
    # Assign depth metadata (unresolvable cycles get depth -1)
    for t in tasks:
        t.metadata["dependency_depth"] = depth.get(t.id, -1)


# ---------------------------------------------------------------------------
# Severity to numeric weight for priority calculation
# ---------------------------------------------------------------------------

_SEVERITY_WEIGHT = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
}


# ---------------------------------------------------------------------------
# Core translation
# ---------------------------------------------------------------------------


def _finding_to_task(
    finding: Finding,
    rec: Recommendation | None,
    priority: int,
) -> AgentTask:
    """Translate a Finding + optional Recommendation into an AgentTask."""
    # Action: prefer recommendation description, fall back to finding.fix
    if rec:
        action = rec.description
        complexity = rec.effort
    elif finding.fix:
        action = finding.fix
        complexity = "medium"
    else:
        action = f"Address: {finding.description}"
        complexity = "medium"

    # Repair maturity from signal matrix
    maturity_entry = REPAIR_MATURITY.get(finding.signal_type, {})
    maturity = str(maturity_entry.get("maturity", "indirect-only"))
    repair_level = str(maturity_entry.get("repair_level", "diagnosis"))

    # Determine shadow_verify flag from base edit_kind for this signal
    base_edit_kind = _EDIT_KIND_FOR_SIGNAL.get(finding.signal_type, "unspecified")
    refined_edit_kind = _refine_edit_kind(
        finding.signal_type, finding.metadata or {}, base_edit_kind
    )
    needs_shadow_verify = is_cross_file_risky(refined_edit_kind)

    task = AgentTask(
        id=_task_id(finding),
        signal_type=finding.signal_type,
        severity=finding.severity,
        priority=priority,
        title=finding.title,
        description=finding.description,
        action=action,
        file_path=finding.file_path.as_posix() if finding.file_path else None,
        start_line=finding.start_line,
        end_line=finding.end_line,
        symbol=finding.symbol,
        related_files=list(dict.fromkeys(rf.as_posix() for rf in finding.related_files)),
        complexity=TaskComplexity(complexity),
        expected_effect=_expected_effect_for(finding),
        success_criteria=_success_criteria_for(finding),
        verify_plan=[],  # populated in second pass with shadow_verify_scope
        shadow_verify=needs_shadow_verify,
        metadata={
            k: v
            for k, v in finding.metadata.items()
            if k not in ("ast_fingerprint", "body_hash")
        } | {"repair_level": repair_level, "root_cause": _root_cause_for(finding)},
        constraints=_generate_constraints(finding),
        repair_maturity=RepairMaturity(maturity),
        negative_context=findings_to_negative_context(
            [finding], max_items=5,
        ),
        expected_score_delta=round(finding.score_contribution, 4),
    )

    # Propagate logical_location via metadata for API serialization.
    if finding.logical_location:
        task.metadata["logical_location"] = {
            "fully_qualified_name": finding.logical_location.fully_qualified_name,
            "name": finding.logical_location.name,
            "kind": finding.logical_location.kind,
            "class_name": finding.logical_location.class_name,
            "namespace": finding.logical_location.namespace,
        }

    # Apply automation fitness classification (mutates task in place)
    _classify_task(finding, task)

    # Populate Finding.root_cause for JSON serialization (enriched here, not in signals)
    if finding.root_cause is None:
        finding.root_cause = _root_cause_for(finding)

    # Repair template registry enrichment (ADR-065)
    _enrich_task_from_registry(finding, task, refined_edit_kind)

    return task


def _enrich_task_from_registry(
    finding: Finding,
    task: AgentTask,
    edit_kind: str,
) -> None:
    """Populate template_confidence and regression_guidance from the repair registry.

    Mutates *task* in place.  Failures are silenced so that registry
    unavailability never breaks task generation.
    """
    try:
        context_class = finding.finding_context or "production"
        registry = get_registry()
        entry = registry.lookup(finding.signal_type, edit_kind, context_class)
        if entry is not None:
            task.template_confidence = registry.confidence(entry)
            task.regression_guidance = list(entry.regression_patterns)
    except (ImportError, AttributeError, KeyError, TypeError):  # pragma: no cover
        pass  # registry failure must never block task generation


def analysis_to_agent_tasks(analysis: RepoAnalysis) -> list[AgentTask]:
    """Convert analysis findings into a prioritized list of agent tasks.

    Only findings with recommendation coverage are included (report-only
    signals without recommenders are excluded — they don't yet have
    actionable remediation patterns).

    Returns a list of tasks. Use ``analysis_to_agent_tasks_json`` for the
    full output including ``coverage_gaps``.
    """
    # Generate recommendations and map them by stable finding fingerprint.
    recs = generate_recommendations(analysis.findings, max_recommendations=9999)
    rec_by_fingerprint: dict[str, Recommendation] = {}
    for r in recs:
        if r.related_findings:
            for f in r.related_findings:
                rec_by_fingerprint[_finding_fingerprint(f)] = r

    # Sort findings: severity weight × impact, descending
    scored = sorted(
        analysis.findings,
        key=lambda f: (_SEVERITY_WEIGHT.get(f.severity, 0) * max(f.impact, f.score)),
        reverse=True,
    )

    tasks: list[AgentTask] = []
    seen_ids: set[str] = set()
    priority = 0

    for finding in scored:
        rec = rec_by_fingerprint.get(_finding_fingerprint(finding))

        # Skip findings without recommendation coverage AND without fix text
        if rec is None and not finding.fix:
            continue

        tid = _task_id(finding)
        if tid in seen_ids:
            continue
        seen_ids.add(tid)

        priority += 1
        tasks.append(_finding_to_task(finding, rec, priority))

    # Compute intra-module dependencies
    _compute_dependencies(tasks)

    # Re-apply review_risk modifier for tasks that gained dependencies
    for t in tasks:
        if t.depends_on:
            risk_idx = _RISK_LEVELS.index(t.review_risk) if t.review_risk in _RISK_LEVELS else 1
            t.review_risk = ReviewRisk(_RISK_LEVELS[min(risk_idx + 1, len(_RISK_LEVELS) - 1)])

    # Second pass: compute shadow_verify_scope and final verify_plan for risky tasks.
    # Must run after _compute_dependencies so that depends_on/blocks are populated.
    for t in tasks:
        if t.shadow_verify:
            t.shadow_verify_scope = _compute_shadow_verify_scope(t, tasks)

    # Now that shadow_verify_scope is available, build verify_plan for all tasks.
    # We need the original finding for each task; build a lookup by task ID.
    _task_id_to_finding: dict[str, Finding] = {}
    for finding in scored:
        tid = _task_id(finding)
        if tid not in _task_id_to_finding:
            _task_id_to_finding[tid] = finding

    for t in tasks:
        task_finding = _task_id_to_finding.get(t.id)
        if task_finding is not None:
            scope = t.shadow_verify_scope if t.shadow_verify else None
            t.verify_plan = _verify_plan_for(task_finding, shadow_verify_scope=scope)

    # Compute batch metadata (fix-template equivalence classes)
    _inject_batch_metadata(tasks)

    return tasks


# ---------------------------------------------------------------------------
# Fix-template equivalence classes for batch metadata
# ---------------------------------------------------------------------------

_UNIFORM_TEMPLATE_SIGNALS: set[str] = {
    "broad_exception_monoculture",
    "guard_clause_deficit",
    "test_polarity_deficit",
    "hardcoded_secret",
    "insecure_default",
    "missing_authorization",
}


def _fix_template_class(task: AgentTask) -> str:
    """Compute a fix-template equivalence class key for a task.

    Tasks sharing the same key can be fixed with the same code pattern.
    """
    signal = task.signal_type

    # Signals where every finding uses the same fix template
    if signal in _UNIFORM_TEMPLATE_SIGNALS:
        return signal

    # PFS: group by canonical pattern name
    if signal == "pattern_fragmentation":
        canonical = task.metadata.get("canonical", "")
        return f"{signal}:{canonical}" if canonical else signal

    # MDS: group by duplicate group
    if signal == "mutant_duplicate":
        group = task.metadata.get("duplicate_group", "")
        return f"{signal}:{group}" if group else signal

    # Default: group by signal + rule_id
    rule_id = task.metadata.get("rule_id", "")
    return f"{signal}:{rule_id}" if rule_id else signal


def _inject_batch_metadata(tasks: list[AgentTask]) -> None:
    """Annotate tasks with batch eligibility and pattern instance counts.

    Groups tasks by fix-template equivalence class and injects:
    - batch_eligible: True if >1 task shares the same template class
    - pattern_instance_count: number of tasks in the same class
    - affected_files_for_pattern: sorted list of unique files in the class
    - fix_template_class: the equivalence class key
    """
    from collections import defaultdict

    groups: dict[str, list[AgentTask]] = defaultdict(list)
    for t in tasks:
        key = _fix_template_class(t)
        groups[key].append(t)

    for key, group in groups.items():
        count = len(group)
        files = sorted({t.file_path for t in group if t.file_path})
        for t in group:
            t.metadata["batch_eligible"] = count > 1
            t.metadata["pattern_instance_count"] = count
            t.metadata["affected_files_for_pattern"] = files
            t.metadata["fix_template_class"] = key


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


def _regression_pattern_to_api_dict(rp: RegressionPattern) -> dict[str, Any]:
    return {
        "edit_kind": rp.edit_kind,
        "context_feature": rp.context_feature,
        "reason_code": str(rp.reason_code),
    }


def _task_to_dict(t: AgentTask) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": t.id,
        "signal_type": t.signal_type,
        "severity": t.severity.value,
        "priority": t.priority,
        "title": t.title,
        "description": t.description,
        "action": t.action,
        "file_path": t.file_path,
        "start_line": t.start_line,
        "end_line": t.end_line,
        "symbol": t.symbol,
        "related_files": t.related_files,
        "complexity": t.complexity,
        "expected_effect": t.expected_effect,
        "success_criteria": t.success_criteria,
        "verify_plan": t.verify_plan,
        "depends_on": t.depends_on,
        "metadata": t.metadata,
        "automation_fit": t.automation_fit,
        "review_risk": t.review_risk,
        "change_scope": t.change_scope,
        "verification_strength": t.verification_strength,
        "constraints": t.constraints,
        "repair_maturity": t.repair_maturity,
        "negative_context": [negative_context_to_dict(nc) for nc in t.negative_context],
        "template_confidence": t.template_confidence,
        "regression_guidance": [
            _regression_pattern_to_api_dict(rp) for rp in t.regression_guidance
        ],
    }
    return d


# ---------------------------------------------------------------------------
# Coverage-gap summary for findings without actionable repair
# ---------------------------------------------------------------------------


def _build_coverage_gaps(
    findings: list[Finding],
    tasks: list[AgentTask],
) -> dict[str, Any]:
    """Build a summary of findings that could not be converted to tasks.

    Returns a dict suitable for inclusion in the agent-tasks JSON output.
    """
    # Simpler approach: per-signal counts
    finding_count_by_signal: dict[str, int] = {}
    task_count_by_signal: dict[str, int] = {}
    for f in findings:
        finding_count_by_signal[f.signal_type] = finding_count_by_signal.get(f.signal_type, 0) + 1
    for t in tasks:
        task_count_by_signal[t.signal_type] = task_count_by_signal.get(t.signal_type, 0) + 1

    gaps: list[dict[str, Any]] = []
    for signal_id, finding_count in sorted(finding_count_by_signal.items()):
        task_count = task_count_by_signal.get(signal_id, 0)
        skipped = finding_count - task_count
        if skipped <= 0:
            continue

        meta = get_meta(signal_id)
        repair_level = meta.repair_level if meta else "diagnosis"
        gaps.append({
            "signal": signal_id,
            "abbrev": meta.abbrev if meta else signal_id[:3].upper(),
            "findings_total": finding_count,
            "findings_actionable": task_count,
            "findings_skipped": skipped,
            "repair_level": repair_level,
            "reason": "no_recommender_no_fix",
        })

    # Aggregate
    total_findings = len(findings)
    total_actionable = len(tasks)
    level_counts: dict[str, int] = {}
    for meta in (get_meta(s) for s in finding_count_by_signal):
        if meta:
            level_counts[meta.repair_level] = level_counts.get(meta.repair_level, 0) + 1

    return {
        "total_findings": total_findings,
        "total_actionable": total_actionable,
        "total_skipped": total_findings - total_actionable,
        "actionable_ratio": round(total_actionable / max(total_findings, 1), 3),
        "repair_level_distribution": level_counts,
        "gaps": gaps,
    }


def analysis_to_agent_tasks_json(analysis: RepoAnalysis, indent: int = 2) -> str:
    """Serialize a RepoAnalysis to agent-tasks JSON."""
    tasks = analysis_to_agent_tasks(analysis)

    data: dict[str, Any] = {
        "version": __version__,
        "schema": "agent-tasks-v2",
        "repo": analysis.repo_path.as_posix(),
        "analyzed_at": analysis.analyzed_at.isoformat(),
        "drift_score": analysis.drift_score,
        "drift_score_scope": build_drift_score_scope(context="repo"),
        "severity": analysis.severity.value,
        "task_count": len(tasks),
        "tasks": [_task_to_dict(t) for t in tasks],
        "coverage_gaps": _build_coverage_gaps(analysis.findings, tasks),
    }

    return json.dumps(data, indent=indent, default=str)
