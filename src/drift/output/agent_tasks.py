"""Agent-tasks output format — translates findings into machine-readable repair tasks."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from drift import __version__
from drift.api_helpers import build_drift_score_scope
from drift.models import AgentTask, Finding, RepoAnalysis, Severity, SignalType
from drift.negative_context import findings_to_negative_context, negative_context_to_dict
from drift.recommendations import Recommendation, generate_recommendations

# ---------------------------------------------------------------------------
# Deterministic task ID
# ---------------------------------------------------------------------------

_SIGNAL_PREFIX = {
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

REPAIR_MATURITY: dict[str, dict[str, str | bool]] = {
    SignalType.MUTANT_DUPLICATE: {
        "maturity": "verified",
        "benchmark_coverage": "strong",
        "real_world": True,
    },
    SignalType.DOC_IMPL_DRIFT: {
        "maturity": "verified",
        "benchmark_coverage": "strong",
        "real_world": True,
    },
    SignalType.PATTERN_FRAGMENTATION: {
        "maturity": "verified",
        "benchmark_coverage": "moderate",
        "real_world": False,
    },
    SignalType.EXPLAINABILITY_DEFICIT: {
        "maturity": "verified",
        "benchmark_coverage": "moderate",
        "real_world": False,
    },
    SignalType.ARCHITECTURE_VIOLATION: {
        "maturity": "experimental",
        "benchmark_coverage": "limited",
        "real_world": False,
    },
    SignalType.TEMPORAL_VOLATILITY: {
        "maturity": "indirect-only",
        "benchmark_coverage": "cascade",
        "real_world": False,
    },
    SignalType.SYSTEM_MISALIGNMENT: {
        "maturity": "indirect-only",
        "benchmark_coverage": "cascade",
        "real_world": False,
    },
}


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

    task.automation_fit = _clamp(fit, _FIT_LEVELS)
    task.review_risk = _clamp(risk, _RISK_LEVELS)
    task.change_scope = _clamp(scope, _SCOPE_LEVELS)
    task.verification_strength = _clamp(verif, _VERIF_LEVELS)


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
    maturity = str(maturity_entry.get("maturity", "experimental"))

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
        complexity=complexity,
        expected_effect=_expected_effect_for(finding),
        success_criteria=_success_criteria_for(finding),
        metadata={
            k: v
            for k, v in finding.metadata.items()
            if k not in ("ast_fingerprint", "body_hash")
        },
        constraints=_generate_constraints(finding),
        repair_maturity=maturity,
        negative_context=findings_to_negative_context(
            [finding], max_items=5,
        ),
        expected_score_delta=round(finding.score_contribution, 4),
    )

    # Apply automation fitness classification (mutates task in place)
    _classify_task(finding, task)

    return task


def analysis_to_agent_tasks(analysis: RepoAnalysis) -> list[AgentTask]:
    """Convert analysis findings into a prioritized list of agent tasks.

    Only findings with recommendation coverage are included (report-only
    signals without recommenders are excluded — they don't yet have
    actionable remediation patterns).
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
            t.review_risk = _RISK_LEVELS[min(risk_idx + 1, len(_RISK_LEVELS) - 1)]

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


def _task_to_dict(t: AgentTask) -> dict[str, Any]:
    return {
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
        "depends_on": t.depends_on,
        "metadata": t.metadata,
        "automation_fit": t.automation_fit,
        "review_risk": t.review_risk,
        "change_scope": t.change_scope,
        "verification_strength": t.verification_strength,
        "constraints": t.constraints,
        "repair_maturity": t.repair_maturity,
        "negative_context": [negative_context_to_dict(nc) for nc in t.negative_context],
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
    }

    return json.dumps(data, indent=indent, default=str)
