"""Fix-plan endpoint — prioritized repair tasks with constraints."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from drift.api._config import (
    _emit_api_telemetry,
    _load_config_cached,
    _warn_config_issues,
)
from drift.api_helpers import (
    DONE_DIFF_ACCEPT,
    VALID_SIGNAL_IDS,
    _base_response,
    _error_response,
    _next_step_contract,
    _task_to_api_dict,
    build_drift_score_scope,
    build_task_graph,
    build_workflow_plan,
    resolve_signal,
    shape_for_profile,
    signal_abbrev,
    signal_scope_label,
)
from drift.finding_context import is_non_operational_context

if TYPE_CHECKING:
    from drift.analyzer import ProgressCallback


def _fix_plan_agent_instruction(tasks: list) -> str:
    """Build context-dependent agent_instruction for fix_plan responses."""
    batch_count = sum(1 for t in tasks if getattr(t, "metadata", {}).get("batch_eligible"))
    if batch_count > 0:
        return (
            "Tasks with batch_eligible=true share a fix pattern. "
            "Apply the fix to ALL affected_files_for_pattern, then verify "
            "with a single drift_diff(uncommitted=True). "
            "For non-batch tasks, use drift_nudge after each edit for fast "
            "directional feedback. Use drift_diff only for batch verification "
            "or before committing."
        )
    return (
        "After each fix, call drift_nudge for fast directional feedback. "
        "Use drift_diff for full regression analysis before committing. "
        "Do not batch changes across unrelated findings."
    )


def _fix_plan_next_step_contract(tasks: list) -> dict[str, Any]:
    """Build the next-step contract for fix_plan responses (ADR-024)."""
    batch_count = sum(1 for t in tasks if getattr(t, "metadata", {}).get("batch_eligible"))
    if batch_count > 0:
        return _next_step_contract(
            next_tool="drift_diff",
            next_params={"uncommitted": True},
            done_when=DONE_DIFF_ACCEPT,
            fallback_tool="drift_nudge",
        )
    return _next_step_contract(
        next_tool="drift_nudge",
        done_when=DONE_DIFF_ACCEPT,
        fallback_tool="drift_diff",
        fallback_params={"uncommitted": True},
    )


def _build_fix_plan_response_from_analysis(
    *,
    analysis: Any,
    cfg: Any,
    repo_path: Path,
    finding_id: str | None,
    signal: str | None,
    max_tasks: int,
    automation_fit_min: str | None,
    target_path: str | None,
    exclude_paths: list[str] | None,
    include_deferred: bool,
    include_non_operational: bool,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build fix-plan response from a precomputed repo analysis.

    This helper allows callers (for example MCP autopilot orchestration)
    to reuse a single full analysis across multiple API surfaces.
    """
    from drift.output.agent_tasks import analysis_to_agent_tasks

    out_warnings = list(warnings or [])

    def _normalize_rel_path(raw: str | None) -> str:
        if not raw:
            return ""
        return Path(str(raw).replace("\\", "/")).as_posix().strip("/")

    def _in_scope(file_path: str | None, scope_path: str) -> bool:
        if not file_path:
            return False
        normalized_file = _normalize_rel_path(file_path)
        normalized_scope = _normalize_rel_path(scope_path)
        return (
            normalized_file == normalized_scope
            or normalized_file.startswith(normalized_scope + "/")
        )

    normalized_excludes = [
        _normalize_rel_path(p)
        for p in (exclude_paths or [])
        if _normalize_rel_path(p)
    ]

    # Validate target/exclude paths
    if target_path and not (repo_path / target_path).exists():
        out_warnings.append(
            f"target_path '{target_path}' does not exist in repository"
        )
    for excluded_path in normalized_excludes:
        if not (repo_path / excluded_path).exists():
            out_warnings.append(
                f"exclude path '{excluded_path}' does not exist in repository"
            )

    tasks = analysis_to_agent_tasks(analysis)

    # Filter by target_path
    if target_path:
        tasks = [
            t for t in tasks
            if t.file_path and _in_scope(t.file_path, target_path)
        ]

    # Filter by exclude_paths
    if normalized_excludes:
        tasks = [
            t
            for t in tasks
            if not (
                t.file_path
                and any(_in_scope(t.file_path, excluded) for excluded in normalized_excludes)
            )
        ]

    # Filter by signal
    finding_id_diagnostic: str | None = None
    finding_id_message: str | None = None
    finding_id_suggested_fix: dict[str, Any] | None = None
    if signal:
        resolved = resolve_signal(signal)
        if resolved is None:
            return _error_response(
                "DRIFT-1003",
                f"Unknown signal: '{signal}'",
                invalid_fields=[{
                    "field": "signal", "value": signal,
                    "reason": "Not a valid signal ID",
                }],
                suggested_fix={
                    "action": "Use a valid signal abbreviation",
                    "valid_values": VALID_SIGNAL_IDS,
                    "example_call": {"tool": "drift_fix_plan", "params": {"signal": "PFS"}},
                },
            )
        tasks = [t for t in tasks if t.signal_type == resolved]

    deferred_task_keys: set[tuple[str, str | None, str]] = set()
    for finding in analysis.findings:
        if not getattr(finding, "deferred", False):
            continue
        fp = finding.file_path.as_posix() if finding.file_path else None
        deferred_task_keys.add((finding.signal_type, fp, finding.title))

    excluded_deferred = 0
    if not include_deferred and deferred_task_keys:
        before = len(tasks)
        tasks = [
            t
            for t in tasks
            if (t.signal_type, t.file_path, t.title) not in deferred_task_keys
        ]
        excluded_deferred = before - len(tasks)
        if excluded_deferred > 0:
            out_warnings.append(
                f"Excluded {excluded_deferred} deferred finding(s) from fix-plan scope"
            )

    # Filter by finding_id
    if finding_id:
        id_matches = [t for t in tasks if t.id == finding_id]
        if id_matches:
            tasks = id_matches
        else:
            # Convenience: accept rule_id/signal-style IDs from scan output.
            resolved_finding = resolve_signal(finding_id)
            if resolved_finding is not None:
                rule_matches = [t for t in tasks if t.signal_type == resolved_finding]
                if rule_matches:
                    tasks = rule_matches
                    finding_id_diagnostic = "finding_id_interpreted_as_rule_id"
                    finding_id_message = (
                        f"'{finding_id}' was interpreted as rule_id/signal and matched "
                        f"{len(tasks)} task(s)."
                    )
                else:
                    available_rule_ids = sorted({t.signal_type for t in tasks})
                    available_task_ids = [t.id for t in tasks]
                    tasks = []
                    finding_id_diagnostic = "finding_id_no_match"
                    finding_id_message = (
                        f"No findings matched finding_id '{finding_id}' in the current scope."
                    )
                    finding_id_suggested_fix = {
                        "action": (
                            "Use a task id from fix-plan output, or pass a valid "
                            "rule_id/signal "
                            "from scan output."
                        ),
                        "expected_formats": ["<signal>-<hash>", "<rule_id>", "<signal_abbrev>"],
                        "valid_task_ids_sample": available_task_ids[:10],
                        "valid_rule_ids": available_rule_ids,
                        "example_call": {
                            "tool": "drift_fix_plan",
                            "params": {"finding_id": "explainability_deficit", "max_tasks": 1},
                        },
                    }
            else:
                available_rule_ids = sorted({t.signal_type for t in tasks})
                available_task_ids = [t.id for t in tasks]
                tasks = []
                finding_id_diagnostic = "finding_id_no_match"
                finding_id_message = (
                    f"No findings matched finding_id '{finding_id}' in the current scope."
                )
                finding_id_suggested_fix = {
                    "action": (
                        "Use a task id from fix-plan output, or pass a valid rule_id/signal "
                        "from scan output."
                    ),
                    "expected_formats": ["<signal>-<hash>", "<rule_id>", "<signal_abbrev>"],
                    "valid_task_ids_sample": available_task_ids[:10],
                    "valid_rule_ids": available_rule_ids,
                    "example_call": {
                        "tool": "drift_fix_plan",
                        "params": {"finding_id": "explainability_deficit", "max_tasks": 1},
                    },
                }

    # Filter by automation fitness
    fit_levels = {"low": 0, "medium": 1, "high": 2}
    skipped_low = 0
    if automation_fit_min and automation_fit_min in fit_levels:
        min_level = fit_levels[automation_fit_min]
        filtered = []
        for t in tasks:
            if fit_levels.get(t.automation_fit, 0) >= min_level:
                filtered.append(t)
            else:
                skipped_low += 1
        tasks = filtered

    context_counts: dict[str, int] = {}
    excluded_non_operational = 0
    if not include_non_operational:
        filtered_tasks = []
        for t in tasks:
            context = str(t.metadata.get("finding_context", "production"))
            context_counts[context] = context_counts.get(context, 0) + 1
            if is_non_operational_context(context, cfg):
                excluded_non_operational += 1
                continue
            filtered_tasks.append(t)
        tasks = filtered_tasks
    else:
        for t in tasks:
            context = str(t.metadata.get("finding_context", "production"))
            context_counts[context] = context_counts.get(context, 0) + 1

    limited = tasks[:max_tasks]

    # Path diagnostic: explain empty results when target_path was used
    next_actions = ["drift_diff after applying fixes to verify improvement"]
    path_diagnostic = None
    if target_path and not tasks:
        normalized = Path(target_path).as_posix().strip("/")
        # Check if the path had any files in the analysis
        analyzed_paths = {
            f.file_path.as_posix().strip("/")
            for f in analysis.findings
            if f.file_path
        }
        if not any(
            p == normalized or p.startswith(normalized + "/")
            for p in analyzed_paths
        ):
            path_diagnostic = "no_matching_files"
            next_actions = [
                f"Path '{target_path}' matched no analyzed files. "
                f"Check spelling or use 'drift scan' to see available paths."
            ]
        else:
            path_diagnostic = "no_findings_in_path"
            next_actions = [
                f"Path '{target_path}' contains analyzed files but has no actionable findings."
            ]

    # Compute remaining-by-signal for truncated tasks
    _remaining_tasks = tasks[len(limited):]
    _remaining_by_signal: dict[str, int] = {}
    for _rt in _remaining_tasks:
        _sig = signal_abbrev(_rt.signal_type)
        _remaining_by_signal[_sig] = _remaining_by_signal.get(_sig, 0) + 1

    # ADR-025 Phase A: build task dependency graph
    graph = build_task_graph(limited)

    # ADR-025 Phase C: build executable workflow plan
    workflow = build_workflow_plan(
        graph,
        repo_path=str(repo_path) if repo_path else ".",
    )

    result = _base_response(
        drift_score=round(analysis.drift_score, 3),
        drift_score_scope=build_drift_score_scope(
            context="fix-plan",
            path=target_path,
            signal_scope=signal_scope_label(selected=[signal] if signal else None),
        ),
        tasks=[_task_to_api_dict(t) for t in graph.tasks],
        task_count=len(limited),
        total_available=len(tasks),
        remaining_by_signal=_remaining_by_signal,
        skipped_low_automation=skipped_low,
        finding_context={
            "counts": dict(sorted(context_counts.items())),
            "non_operational_contexts": sorted(
                set(cfg.finding_context.non_operational_contexts)
            ),
            "include_non_operational": include_non_operational,
            "excluded_from_fix_plan": excluded_non_operational,
        },
        path_diagnostic=path_diagnostic,
        finding_id_diagnostic=finding_id_diagnostic,
        message=finding_id_message,
        suggested_fix=finding_id_suggested_fix,
        recommended_next_actions=next_actions,
        agent_instruction=_fix_plan_agent_instruction(limited),
        task_graph=graph.to_api_dict(),
        workflow_plan=workflow.to_api_dict(),
    )
    result.update(_fix_plan_next_step_contract(limited))
    if out_warnings:
        result["warnings"] = out_warnings
    if finding_id and finding_id_message and not finding_id_suggested_fix:
        result.setdefault("warnings", []).append(finding_id_message)
    if finding_id and finding_id_suggested_fix:
        result.setdefault("invalid_fields", []).append(
            {
                "field": "finding_id",
                "value": finding_id,
                "reason": "No task id or rule_id match in current scope",
            }
        )

    return result


def fix_plan(
    path: str | Path = ".",
    *,
    finding_id: str | None = None,
    signal: str | None = None,
    max_tasks: int = 5,
    automation_fit_min: str | None = None,
    target_path: str | None = None,
    exclude_paths: list[str] | None = None,
    include_deferred: bool = False,
    include_non_operational: bool = False,
    on_progress: ProgressCallback | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Generate a prioritized fix plan with constraints and success criteria.

    Parameters
    ----------
    path:
        Repository root directory.
    finding_id:
        Target a specific finding by its task ID.
    signal:
        Filter to findings of this signal (abbreviation or full name).
    max_tasks:
        Maximum tasks to return.
    automation_fit_min:
        Minimum automation fitness level: ``"low"``, ``"medium"``, or ``"high"``.
    target_path:
        Restrict tasks to findings inside this subpath.
    exclude_paths:
        Exclude tasks whose file path is inside one of these subpaths.
    include_deferred:
        Include findings marked as ``deferred`` by config when ``True``.
    include_non_operational:
        Include non-operational contexts (fixture/generated/migration/docs)
        in prioritization when ``True``.
    """
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig
    from drift.telemetry import timed_call

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params = {
        "path": str(path),
        "finding_id": finding_id,
        "signal": signal,
        "max_tasks": max_tasks,
        "automation_fit_min": automation_fit_min,
        "target_path": target_path,
        "exclude_paths": exclude_paths,
        "include_deferred": include_deferred,
        "include_non_operational": include_non_operational,
    }

    _valid_automation_fit = {"low", "medium", "high"}

    try:
        if automation_fit_min is not None and automation_fit_min not in _valid_automation_fit:
            result = _error_response(
                "DRIFT-1003",
                f"Unknown automation_fit_min value: '{automation_fit_min}'",
                invalid_fields=[{
                    "field": "automation_fit_min",
                    "value": automation_fit_min,
                    "reason": "Must be one of: low, medium, high",
                }],
                suggested_fix={
                    "action": "Use a valid automation fitness level",
                    "valid_values": sorted(_valid_automation_fit),
                    "example_call": {
                        "tool": "drift_fix_plan",
                        "params": {"automation_fit_min": "medium"},
                    },
                },
            )
            _emit_api_telemetry(
                tool_name="api.fix_plan",
                params=params,
                status="ok",
                elapsed_ms=elapsed_ms(),
                result=result,
                error=None,
                repo_root=repo_path,
            )
            return result

        cfg = _load_config_cached(repo_path)
        if not hasattr(cfg, "finding_context"):
            cfg = DriftConfig()
        cfg_warnings = _warn_config_issues(cfg)

        analysis = analyze_repo(repo_path, config=cfg, on_progress=on_progress)
        result = _build_fix_plan_response_from_analysis(
            analysis=analysis,
            cfg=cfg,
            repo_path=repo_path,
            finding_id=finding_id,
            signal=signal,
            max_tasks=max_tasks,
            automation_fit_min=automation_fit_min,
            target_path=target_path,
            exclude_paths=exclude_paths,
            include_deferred=include_deferred,
            include_non_operational=include_non_operational,
            warnings=list(cfg_warnings),
        )
        _emit_api_telemetry(
            tool_name="api.fix_plan",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )
        return shape_for_profile(result, response_profile)
    except Exception as exc:
        _emit_api_telemetry(
            tool_name="api.fix_plan",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        raise
