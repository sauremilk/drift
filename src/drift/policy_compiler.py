"""Policy Compiler — task-specific policy packages from repo state.

Compiles a short, focused set of operative rules for an AI agent by combining:

- Task intent (free-text + optional TaskSpec)
- Git context (changed files)
- Architecture knowledge (ArchGraph decisions, hotspots, abstractions)
- Calibration feedback (signal confidence, FP rates)

The output is a :class:`CompiledPolicy` containing max *max_rules* rules
(default 15, max 5 per category) plus a Markdown agent instruction block.
"""

from __future__ import annotations

import logging
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from drift.models._policy import CompiledPolicy, PolicyRule

if TYPE_CHECKING:
    from drift.arch_graph._models import (
        ArchAbstraction,
        ArchGraph,
    )
    from drift.task_spec import TaskSpec

_log = logging.getLogger("drift")

# ---------------------------------------------------------------------------
# Compile scope — resolved paths & modules for the task
# ---------------------------------------------------------------------------

_MAX_RULES_PER_CATEGORY = 5


@dataclass(slots=True)
class CompileScope:
    """Resolved scope for a policy compilation."""

    allowed_paths: list[str] = field(default_factory=list)
    forbidden_paths: list[str] = field(default_factory=list)
    affected_modules: list[str] = field(default_factory=list)
    affected_layers: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 1. Scope resolution
# ---------------------------------------------------------------------------


def resolve_compile_scope(
    task: str,
    repo_path: Path,
    *,
    task_spec: TaskSpec | None = None,
    git_diff_paths: list[str] | None = None,
) -> CompileScope:
    """Resolve the compilation scope from available inputs.

    Priority:
    1. TaskSpec boundaries (highest confidence)
    2. Git diff paths (derive modules from changed files)
    3. Free-text scope resolution (fallback)
    """
    scope = CompileScope()

    # --- TaskSpec: explicit boundaries ---
    if task_spec is not None:
        scope.allowed_paths = list(task_spec.scope_boundaries)
        scope.forbidden_paths = list(task_spec.forbidden_paths)
        scope.affected_layers = [str(layer) for layer in task_spec.affected_layers]
        # Derive modules from scope boundaries
        scope.affected_modules = _paths_to_modules(scope.allowed_paths)
        return scope

    # --- Git diff: derive from changed files ---
    if git_diff_paths:
        scope.allowed_paths = list(git_diff_paths)
        scope.affected_modules = _paths_to_modules(git_diff_paths)
        return scope

    # --- Free-text fallback: use scope resolver ---
    try:
        from drift.scope_resolver import resolve_scope

        resolved = resolve_scope(task, repo_path)
        scope.allowed_paths = list(resolved.paths)
        scope.affected_modules = _paths_to_modules(resolved.paths)
    except Exception:
        _log.debug("Scope resolution from task text failed, using empty scope")

    return scope


def _paths_to_modules(paths: list[str]) -> list[str]:
    """Extract unique module directory prefixes from file/dir paths."""
    modules: set[str] = set()
    for p in paths:
        normalised = p.replace("\\", "/").strip("/")
        # Take up to 3 path segments as module prefix
        parts = normalised.split("/")
        if len(parts) >= 2:
            modules.add("/".join(parts[:3]) if len(parts) >= 3 else "/".join(parts[:2]))
        elif parts:
            modules.add(parts[0])
    return sorted(modules)


# ---------------------------------------------------------------------------
# 2. Git context helpers
# ---------------------------------------------------------------------------


def get_git_diff_paths(repo_path: Path, diff_ref: str = "HEAD") -> list[str]:
    """Return changed file paths relative to *diff_ref*.

    Falls back to staged files if *diff_ref* comparison fails.
    Returns an empty list on any error.
    """
    try:
        result = subprocess.run(  # noqa: S603, S607
            ["git", "diff", "--name-only", diff_ref],
            capture_output=True,
            text=True,
            cwd=str(repo_path),
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
        paths = [p.strip() for p in result.stdout.strip().splitlines() if p.strip()]
        if paths:
            return paths
    except Exception:
        _log.debug("git diff --name-only %s failed", diff_ref)

    # Fallback: staged files
    try:
        result = subprocess.run(  # noqa: S603, S607
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=str(repo_path),
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
        return [p.strip() for p in result.stdout.strip().splitlines() if p.strip()]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 3. Rule generators — each produces a list of PolicyRule
# ---------------------------------------------------------------------------


def compile_decision_rules(
    graph: ArchGraph,
    scope: CompileScope,
) -> list[PolicyRule]:
    """Generate rules from ArchGraph decisions that match the scope."""
    from drift.arch_graph._decisions import match_decisions

    rules: list[PolicyRule] = []
    seen_ids: set[str] = set()

    for target in scope.allowed_paths + scope.affected_modules:
        matched = match_decisions(graph.decisions, target)
        for dec in matched:
            if dec.id in seen_ids:
                continue
            seen_ids.add(dec.id)

            category = "prohibition" if dec.enforcement == "block" else "invariant"
            rules.append(PolicyRule(
                id=f"decision-{dec.id}",
                category=category,
                rule=dec.rule,
                enforcement=dec.enforcement,
                source=dec.source,
                confidence=1.0,
            ))

    return rules


def compile_hotspot_rules(
    graph: ArchGraph,
    scope: CompileScope,
) -> list[PolicyRule]:
    """Generate review-trigger rules for hotspots in scope."""
    rules: list[PolicyRule] = []

    for hs in graph.hotspots:
        hs_norm = hs.path.replace("\\", "/")
        if not _in_scope(hs_norm, scope):
            continue

        if hs.trend == "degrading" or hs.total_occurrences >= 5:
            top_signal = (
                max(hs.recurring_signals, key=hs.recurring_signals.get)
                if hs.recurring_signals
                else "unknown"
            )
            rules.append(PolicyRule(
                id=f"hotspot-{hs_norm.replace('/', '-')}",
                category="review_trigger",
                rule=(
                    f"File {hs.path} is a hotspot "
                    f"({hs.total_occurrences} recurring findings, trend: {hs.trend}, "
                    f"dominant signal: {top_signal}). "
                    "Changes here need extra review."
                ),
                enforcement="warn",
                confidence=min(hs.total_occurrences / 10, 1.0),
            ))

    return rules


def compile_layer_policy_rules(
    graph: ArchGraph,
    scope: CompileScope,
) -> list[PolicyRule]:
    """Generate prohibition rules from layer-boundary violations."""
    rules: list[PolicyRule] = []
    module_set = set(scope.affected_modules)

    for dep in graph.dependencies:
        if dep.from_module in module_set and dep.policy:
            rules.append(PolicyRule(
                id=f"layer-{dep.from_module}-{dep.to_module}".replace("/", "-"),
                category="prohibition",
                rule=(
                    f"Layer policy: {dep.from_module} → {dep.to_module} "
                    f"is '{dep.policy}'. Do not add new imports in this direction."
                ),
                enforcement="block" if dep.policy == "forbidden" else "warn",
                confidence=1.0,
            ))

    return rules


def compile_calibration_rules(
    calibration_weights: dict[str, float] | None,
    calibration_confidence: dict[str, float] | None,
    top_signals: list[str],
) -> list[PolicyRule]:
    """Generate rules from calibration data (FP awareness).

    Low-confidence signals get review_trigger rules so the agent knows
    to be cautious about findings from those signals.
    """
    if not calibration_confidence:
        return []

    rules: list[PolicyRule] = []
    for sig in top_signals:
        conf = calibration_confidence.get(sig, 1.0)
        if conf < 0.5:
            rules.append(PolicyRule(
                id=f"cal-low-conf-{sig}",
                category="review_trigger",
                rule=(
                    f"Signal {sig} has low calibration confidence ({conf:.0%}). "
                    "Findings from this signal may have a higher false-positive rate. "
                    "Verify manually before acting."
                ),
                enforcement="warn",
                source="calibration",
                confidence=conf,
            ))

    return rules


def compile_reuse_rules(
    graph: ArchGraph,
    scope: CompileScope,
    *,
    max_suggestions: int = 5,
) -> tuple[list[PolicyRule], list[dict[str, Any]]]:
    """Generate reuse rules from high-usage abstractions in scope.

    Returns (rules, reuse_target_dicts) — the targets are for the
    ``reuse_targets`` field in CompiledPolicy.
    """
    relevant_modules = set(scope.affected_modules)

    # Collect abstractions from scope modules
    candidates: list[ArchAbstraction] = []
    for mp in relevant_modules:
        candidates.extend(graph.abstractions_in(mp))

    # Also check neighbour modules for reuse opportunities
    for mp in relevant_modules:
        for n in graph.neighbors(mp):
            candidates.extend(graph.abstractions_in(n))

    # Deduplicate, sort by usage
    seen: set[str] = set()
    unique: list[ArchAbstraction] = []
    for a in candidates:
        key = f"{a.module_path}:{a.symbol}"
        if key not in seen:
            seen.add(key)
            unique.append(a)
    unique.sort(key=lambda a: a.usage_count, reverse=True)
    top = unique[:max_suggestions]

    rules: list[PolicyRule] = []
    targets: list[dict[str, Any]] = []

    for a in top:
        if a.usage_count < 3:
            continue
        rules.append(PolicyRule(
            id=f"reuse-{a.symbol}",
            category="reuse",
            rule=(
                f"Prefer reusing {a.kind} '{a.symbol}' "
                f"(from {a.module_path}, used {a.usage_count}× across the codebase) "
                f"instead of creating a new similar abstraction."
            ),
            enforcement="info",
            confidence=min(a.usage_count / 10, 1.0),
        ))
        targets.append({
            "symbol": a.symbol,
            "kind": a.kind,
            "module_path": a.module_path,
            "file_path": a.file_path,
            "usage_count": a.usage_count,
            "has_docstring": a.has_docstring,
        })

    return rules, targets


def compile_scope_rules(scope: CompileScope) -> list[PolicyRule]:
    """Generate scope-boundary rules from allowed/forbidden paths."""
    rules: list[PolicyRule] = []

    if scope.forbidden_paths:
        for fp in scope.forbidden_paths:
            rules.append(PolicyRule(
                id=f"scope-forbidden-{fp.replace('/', '-').replace('*', 'x')}",
                category="scope",
                rule=f"Do not modify files matching '{fp}'.",
                enforcement="block",
                confidence=1.0,
            ))

    if scope.allowed_paths:
        paths_display = ", ".join(scope.allowed_paths[:5])
        if len(scope.allowed_paths) > 5:
            paths_display += f" (+{len(scope.allowed_paths) - 5} more)"
        rules.append(PolicyRule(
            id="scope-boundary",
            category="scope",
            rule=f"Restrict changes to: {paths_display}.",
            enforcement="warn",
            confidence=0.9,
        ))

    return rules


def compile_finding_rules(
    scoped_findings: list[Any],
    *,
    max_rules: int = 3,
) -> list[PolicyRule]:
    """Generate stop-condition rules from existing findings in scope."""
    if not scoped_findings:
        return []

    # Count by signal type
    signal_counts: Counter[str] = Counter()
    for f in scoped_findings:
        sig = getattr(f, "signal_type", None)
        if sig:
            signal_counts[str(sig)] += 1

    rules: list[PolicyRule] = []
    for sig, count in signal_counts.most_common(max_rules):
        rules.append(PolicyRule(
            id=f"finding-{sig.lower().replace(' ', '-')}",
            category="stop_condition",
            rule=(
                f"There are {count} existing {sig} findings in scope. "
                "Do not introduce new instances of this pattern."
            ),
            enforcement="warn",
            confidence=0.8,
        ))

    return rules


# ---------------------------------------------------------------------------
# 4. Rule assembly
# ---------------------------------------------------------------------------


def assemble_rules(
    all_rules: list[PolicyRule],
    *,
    max_rules: int = 15,
    max_per_category: int = _MAX_RULES_PER_CATEGORY,
) -> list[PolicyRule]:
    """Deduplicate, prioritise, and cap rules.

    Priority order: block > warn > info.
    Within same enforcement: higher confidence first.
    Cap at *max_per_category* rules per category and *max_rules* total.
    """
    _enforcement_rank = {"block": 0, "warn": 1, "info": 2}

    # Deduplicate by (category, rule text)
    seen: set[tuple[str, str]] = set()
    unique: list[PolicyRule] = []
    for r in all_rules:
        key = (r.category, r.rule)
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    # Sort: enforcement priority, then confidence desc
    unique.sort(key=lambda r: (_enforcement_rank.get(r.enforcement, 99), -r.confidence))

    # Cap per category
    category_counts: dict[str, int] = defaultdict(int)
    capped: list[PolicyRule] = []
    for r in unique:
        if category_counts[r.category] >= max_per_category:
            continue
        category_counts[r.category] += 1
        capped.append(r)

    return capped[:max_rules]


# ---------------------------------------------------------------------------
# 5. Markdown renderer
# ---------------------------------------------------------------------------

_CATEGORY_LABELS: dict[str, str] = {
    "prohibition": "🚫 Prohibitions",
    "scope": "📐 Scope Boundaries",
    "invariant": "📌 Invariants",
    "review_trigger": "👁️ Review Triggers",
    "reuse": "♻️ Reuse Targets",
    "stop_condition": "🛑 Stop Conditions",
}

_CATEGORY_ORDER = ["prohibition", "scope", "invariant", "review_trigger", "stop_condition", "reuse"]


def render_policy_markdown(policy: CompiledPolicy) -> str:
    """Render a compiled policy as a compact Markdown block for agent prompts.

    Target: <500 words.
    """
    lines: list[str] = []
    lines.append(f"## Compiled Policy for: {policy.task}")
    lines.append("")

    # Scope summary
    if policy.scope:
        allowed = policy.scope.get("allowed_paths", [])
        forbidden = policy.scope.get("forbidden_paths", [])
        modules = policy.scope.get("affected_modules", [])
        if modules:
            lines.append(f"**Affected modules:** {', '.join(modules)}")
        if allowed:
            display = allowed[:5]
            lines.append(f"**Allowed paths:** {', '.join(display)}")
        if forbidden:
            lines.append(f"**Forbidden paths:** {', '.join(forbidden)}")
        lines.append("")

    # Rules grouped by category
    rules_by_cat: dict[str, list[PolicyRule]] = defaultdict(list)
    for r in policy.rules:
        rules_by_cat[r.category].append(r)

    for cat in _CATEGORY_ORDER:
        cat_rules = rules_by_cat.get(cat)
        if not cat_rules:
            continue
        label = _CATEGORY_LABELS.get(cat, cat)
        lines.append(f"### {label}")
        for r in cat_rules:
            enforcement_badge = f"[{r.enforcement.upper()}]" if r.enforcement != "info" else ""
            source_ref = f" (ref: {r.source})" if r.source else ""
            lines.append(f"- {enforcement_badge} {r.rule}{source_ref}")
        lines.append("")

    # Reuse targets
    if policy.reuse_targets:
        lines.append("### ♻️ Preferred Abstractions")
        for t in policy.reuse_targets[:5]:
            lines.append(
                f"- `{t['symbol']}` ({t['kind']} in {t['module_path']}, "
                f"used {t['usage_count']}×)"
            )
        lines.append("")

    # Risk context
    risk = policy.risk_context
    if risk:
        finding_count = risk.get("finding_count", 0)
        if finding_count > 0:
            lines.append(
                f"**Risk:** {finding_count} existing findings in scope"
                f" (top signal: {risk.get('top_signal', 'n/a')})."
            )
            lines.append("")

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# 6. Top-level compilation
# ---------------------------------------------------------------------------


def compile_policy(
    task: str,
    repo_path: Path,
    *,
    task_spec: TaskSpec | None = None,
    git_diff_paths: list[str] | None = None,
    max_rules: int = 15,
    calibration_weights: dict[str, float] | None = None,
    calibration_confidence: dict[str, float] | None = None,
    scoped_findings: list[Any] | None = None,
) -> CompiledPolicy:
    """Compile a task-specific policy package from repo state.

    This is the pure logic function — no I/O except what's already cached.
    The API wrapper handles config loading, ArchGraph loading, etc.

    Parameters
    ----------
    task:
        Natural-language task description.
    repo_path:
        Repository root.
    task_spec:
        Optional structured TaskSpec for precise boundaries.
    git_diff_paths:
        Optional list of changed file paths from git.
    max_rules:
        Maximum number of rules in the output.
    calibration_weights:
        Per-signal calibrated weights (from build_profile).
    calibration_confidence:
        Per-signal confidence scores (from build_profile).
    scoped_findings:
        Pre-filtered findings for the scope.
    """
    from drift.arch_graph import ArchGraphStore

    # --- 1. Scope resolution ---
    scope = resolve_compile_scope(
        task, repo_path, task_spec=task_spec, git_diff_paths=git_diff_paths,
    )

    # --- 2. Load ArchGraph (may not exist) ---
    all_rules: list[PolicyRule] = []
    reuse_targets: list[dict[str, Any]] = []
    graph_available = False

    try:
        store = ArchGraphStore(repo_path / ".drift-cache")
        graph = store.load()
        graph_available = True
    except Exception:
        graph = None
        _log.debug("No ArchGraph available — skipping graph-based rules")

    # --- 3. Generate rules from all sources ---
    # Scope rules (always available)
    all_rules.extend(compile_scope_rules(scope))

    if graph is not None:
        # Decision rules
        all_rules.extend(compile_decision_rules(graph, scope))
        # Layer policy rules
        all_rules.extend(compile_layer_policy_rules(graph, scope))
        # Hotspot rules
        all_rules.extend(compile_hotspot_rules(graph, scope))
        # Reuse rules
        reuse_rules, reuse_targets = compile_reuse_rules(graph, scope)
        all_rules.extend(reuse_rules)

    # Calibration rules
    top_signals = _extract_top_signals(scoped_findings)
    all_rules.extend(compile_calibration_rules(
        calibration_weights, calibration_confidence, top_signals,
    ))

    # Finding-based stop conditions
    if scoped_findings:
        all_rules.extend(compile_finding_rules(scoped_findings))

    # --- 4. Assemble (deduplicate, prioritise, cap) ---
    assembled = assemble_rules(all_rules, max_rules=max_rules)

    # --- 5. Build risk context ---
    risk_context = _build_risk_context(scoped_findings or [])

    # --- 6. Build CompiledPolicy ---
    policy = CompiledPolicy(
        task=task,
        scope={
            "allowed_paths": scope.allowed_paths,
            "forbidden_paths": scope.forbidden_paths,
            "affected_modules": scope.affected_modules,
            "affected_layers": scope.affected_layers,
            "graph_available": graph_available,
        },
        rules=assembled,
        reuse_targets=reuse_targets,
        risk_context=risk_context,
    )

    # --- 7. Render Markdown ---
    policy.agent_instruction = render_policy_markdown(policy)

    return policy


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _in_scope(path: str, scope: CompileScope) -> bool:
    """Check if a normalised path falls within the compilation scope."""
    if not scope.allowed_paths and not scope.affected_modules:
        return True  # Empty scope = everything in scope

    targets = scope.allowed_paths + scope.affected_modules
    return any(
        path == t or path.startswith(t + "/") or t.startswith(path + "/")
        for t in targets
    )


def _extract_top_signals(findings: list[Any] | None) -> list[str]:
    """Extract the most frequent signal types from findings."""
    if not findings:
        return []

    counter: Counter[str] = Counter()
    for f in findings:
        sig = getattr(f, "signal_type", None)
        if sig:
            counter[str(sig)] += 1

    return [sig for sig, _count in counter.most_common(10)]


def _build_risk_context(findings: list[Any]) -> dict[str, Any]:
    """Build a risk summary from scoped findings."""
    if not findings:
        return {"finding_count": 0, "top_signal": None, "severity_distribution": {}}

    counter: Counter[str] = Counter()
    severity_dist: Counter[str] = Counter()
    for f in findings:
        sig = getattr(f, "signal_type", None)
        sev = getattr(f, "severity", None)
        if sig:
            counter[str(sig)] += 1
        if sev:
            severity_dist[str(sev.value if hasattr(sev, "value") else sev)] += 1

    top_signal = counter.most_common(1)[0][0] if counter else None
    return {
        "finding_count": len(findings),
        "top_signal": top_signal,
        "severity_distribution": dict(severity_dist),
    }
