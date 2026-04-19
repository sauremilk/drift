"""Diff endpoint — analyze drift changes since a git ref or baseline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from drift.api._config import (
    _emit_api_telemetry,
    _load_config_cached,
    _warn_config_issues,
)
from drift.api_helpers import (
    DONE_ACCEPT_CHANGE,
    DONE_STAGED_EXISTS,
    _base_response,
    _error_response,
    _finding_concise,
    _finding_detailed,
    _next_step_contract,
    apply_output_mode,
    shape_for_profile,
    signal_abbrev,
)


@dataclass(frozen=True)
class _DiffScopeState:
    """Target-path scoped view of diff findings."""

    scoped_new: list[Any]
    scoped_resolved: list[Any]
    out_of_scope_new: list[Any]
    normalized_target: str | None


@dataclass(frozen=True)
class _DiffDecisionState:
    """Typed decision state for change acceptance."""

    in_scope_blocking: list[str]
    blocking_reasons: list[str]
    accept_change: bool
    in_scope_accept: bool
    decision_reason_code: str
    decision_reason: str


@dataclass(frozen=True)
class _SnapshotFinding:
    """Normalized finding entry parsed from saved JSON analysis output."""

    fingerprint: str
    severity: str
    severity_level: int
    signal: str | None
    title: str | None
    file: str | None
    start_line: int | None


_SEVERITY_LEVELS: dict[str, int] = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _severity_level(value: str) -> int:
    """Return numeric severity level for stable cross-run comparisons."""
    return _SEVERITY_LEVELS.get(value.lower().strip(), _SEVERITY_LEVELS["info"])


def _highest_snapshot_severity(findings: list[_SnapshotFinding]) -> str:
    """Return highest severity value across snapshot findings."""
    if not findings:
        return "low"
    top = max(findings, key=lambda item: item.severity_level)
    return top.severity


def _snapshot_finding_dict(
    finding: _SnapshotFinding,
    *,
    response_detail: str,
) -> dict[str, Any]:
    """Serialize normalized snapshot findings for API output."""
    payload: dict[str, Any] = {
        "finding_id": finding.fingerprint,
        "fingerprint": finding.fingerprint,
        "severity": finding.severity,
        "signal": finding.signal,
        "title": finding.title,
        "file": finding.file,
        "start_line": finding.start_line,
    }
    if response_detail == "detailed":
        payload["source"] = "snapshot"
    return payload


def _load_snapshot_findings(path: Path) -> tuple[dict[str, _SnapshotFinding], float]:
    """Load a saved ``drift analyze --format json`` file by finding fingerprint."""
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        msg = f"Invalid analyze JSON in {path}: root object must be a JSON object."
        raise ValueError(msg)

    findings_raw = data.get("findings")
    if not isinstance(findings_raw, list):
        msg = f"Invalid analyze JSON in {path}: missing 'findings' array."
        raise ValueError(msg)

    score_raw = data.get("drift_score", 0.0)
    try:
        drift_score = float(score_raw)
    except (TypeError, ValueError):
        drift_score = 0.0

    findings: dict[str, _SnapshotFinding] = {}
    for entry in findings_raw:
        if not isinstance(entry, dict):
            continue
        fingerprint_raw = entry.get("fingerprint") or entry.get("finding_id")
        fingerprint = str(fingerprint_raw or "").strip()
        if not fingerprint:
            continue

        severity_value = str(entry.get("severity") or "info").strip().lower()
        if severity_value not in _SEVERITY_LEVELS:
            severity_value = "info"

        line_value = entry.get("start_line", entry.get("line"))
        start_line: int | None = None
        try:
            if line_value is not None:
                start_line = int(line_value)
        except (TypeError, ValueError):
            start_line = None

        signal_raw = entry.get("signal") or entry.get("signal_type") or entry.get("rule_id")
        file_raw = entry.get("file") or entry.get("file_path")

        findings[fingerprint] = _SnapshotFinding(
            fingerprint=fingerprint,
            severity=severity_value,
            severity_level=_severity_level(severity_value),
            signal=str(signal_raw) if signal_raw is not None else None,
            title=str(entry.get("title")) if entry.get("title") is not None else None,
            file=str(file_raw) if file_raw is not None else None,
            start_line=start_line,
        )

    return findings, drift_score


def _build_snapshot_diff_response(
    *,
    from_path: Path,
    to_path: Path,
    from_findings: dict[str, _SnapshotFinding],
    to_findings: dict[str, _SnapshotFinding],
    score_before: float,
    score_after: float,
    max_findings: int,
    response_detail: str,
) -> dict[str, Any]:
    """Build diff response for offline comparison of two saved JSON snapshots."""
    new_fps = sorted(set(to_findings) - set(from_findings))
    resolved_fps = sorted(set(from_findings) - set(to_findings))
    shared_fps = sorted(set(from_findings) & set(to_findings))

    new_items = [to_findings[fp] for fp in new_fps]
    resolved_items = [from_findings[fp] for fp in resolved_fps]

    changed_entries: list[dict[str, Any]] = []
    for fp in shared_fps:
        before = from_findings[fp]
        after = to_findings[fp]
        level_delta = after.severity_level - before.severity_level
        if abs(level_delta) >= 1:
            changed_entries.append(
                {
                    "finding_id": fp,
                    "fingerprint": fp,
                    "signal": after.signal or before.signal,
                    "title": after.title or before.title,
                    "file": after.file or before.file,
                    "start_line": after.start_line or before.start_line,
                    "severity_before": before.severity,
                    "severity_after": after.severity,
                    "severity_delta_levels": level_delta,
                }
            )

    new_items_sorted = sorted(new_items, key=lambda item: item.severity_level, reverse=True)
    resolved_items_sorted = sorted(
        resolved_items,
        key=lambda item: item.severity_level,
        reverse=True,
    )
    changed_sorted = sorted(
        changed_entries,
        key=lambda item: abs(int(item["severity_delta_levels"])),
        reverse=True,
    )

    new_high_or_critical = sum(
        1 for item in new_items if item.severity in ("high", "critical")
    )

    delta = round(score_after - score_before, 4)
    status = "stable"
    if new_high_or_critical > 0:
        status = "new_critical"
    elif delta > 0.01 or changed_entries:
        status = "degraded"
    elif delta < -0.01 or resolved_items:
        status = "improved"

    blocking_reasons: list[str] = []
    if new_high_or_critical > 0:
        blocking_reasons.append("new_high_or_critical_findings")
    if delta > 0.0:
        blocking_reasons.append("drift_score_regressed")

    accept_change = not blocking_reasons
    decision_reason_code, decision_reason = _diff_decision_reason(
        accept_change=accept_change,
        in_scope_accept=accept_change,
        has_out_of_scope_noise=False,
    )

    summary_parts = [
        f"{len(new_items)} new",
        f"{len(resolved_items)} resolved",
        f"{len(changed_entries)} changed",
        f"drift score {'+' if delta >= 0 else ''}{delta:.3f}",
    ]

    response = _base_response(
        drift_detected=bool(new_items or resolved_items or changed_entries),
        status=status,
        severity=_highest_snapshot_severity(list(to_findings.values())),
        score_before=round(score_before, 4),
        score_after=round(score_after, 4),
        delta=delta,
        score_basis="snapshot",
        score_regressed=delta > 0.0,
        confidence="high",
        diff_ref="snapshot",
        diff_mode="file",
        from_file=from_path.as_posix(),
        to_file=to_path.as_posix(),
        new_findings=[
            _snapshot_finding_dict(item, response_detail=response_detail)
            for item in new_items_sorted[:max_findings]
        ],
        resolved_findings=[
            _snapshot_finding_dict(item, response_detail=response_detail)
            for item in resolved_items_sorted[:max_findings]
        ],
        changed_findings=changed_sorted[:max_findings],
        new_finding_count=len(new_items),
        new_high_or_critical=new_high_or_critical,
        resolved_count=len(resolved_items),
        changed_count=len(changed_entries),
        out_of_scope_new_count=0,
        noise_context={
            "pre_existing_count": 0,
            "explanation": "Offline snapshot comparison mode.",
        },
        baseline_recommended=False,
        baseline_reason="none",
        drift_categories=[],
        affected_components=sorted(
            {
                item.file.rsplit("/", 1)[0]
                for item in new_items
                if item.file and "/" in item.file
            }
        ),
        summary=", ".join(summary_parts),
        accept_change=accept_change,
        in_scope_accept=accept_change,
        blocking_reasons=blocking_reasons,
        decision_reason_code=decision_reason_code,
        decision_reason=decision_reason,
        suggested_next_batch_targets=[],
        recommended_next_actions=(
            ["Review new HIGH/CRITICAL findings before merge"]
            if new_high_or_critical > 0
            else ["No immediate action required"]
        ),
        response_truncated=(
            len(new_items) > max_findings
            or len(resolved_items) > max_findings
            or len(changed_entries) > max_findings
        ),
        agent_instruction=(
            "Offline diff shows new HIGH/CRITICAL findings. Resolve them before proceeding."
            if new_high_or_critical > 0
            else "Offline diff is within threshold. Safe to proceed."
        ),
    )
    response.update(
        _diff_next_step_contract(
            status=status,
            accept_change=accept_change,
            no_staged_files=False,
            decision_reason_code=decision_reason_code,
            batch_targets=[],
        )
    )
    return response


def _scope_findings(
    *,
    new: list[Any],
    resolved: list[Any],
    target_path: str | None,
) -> _DiffScopeState:
    """Return scoped and out-of-scope findings for a target path."""
    if not target_path:
        return _DiffScopeState(
            scoped_new=new,
            scoped_resolved=resolved,
            out_of_scope_new=[],
            normalized_target=None,
        )

    normalized_target = Path(target_path).as_posix().strip("/")

    def _in_scope(finding: Any) -> bool:
        raw_file_path = getattr(finding, "file_path", None)
        if raw_file_path is None or not normalized_target:
            return False
        file_path = Path(raw_file_path).as_posix().strip("/")
        return bool(
            file_path == normalized_target
            or file_path.startswith(normalized_target + "/")
        )

    scoped_new = [finding for finding in new if _in_scope(finding)]
    scoped_resolved = [finding for finding in resolved if _in_scope(finding)]
    out_of_scope_new = [finding for finding in new if not _in_scope(finding)]
    return _DiffScopeState(
        scoped_new=scoped_new,
        scoped_resolved=scoped_resolved,
        out_of_scope_new=out_of_scope_new,
        normalized_target=normalized_target,
    )


def _build_diff_decision_state(
    *,
    scoped_new: list[Any],
    out_of_scope_new: list[Any],
    delta: float,
) -> _DiffDecisionState:
    """Build acceptance decision fields for diff responses."""
    high_count = sum(
        1 for finding in scoped_new if finding.severity.value in ("critical", "high")
    )
    in_scope_blocking: list[str] = []
    if high_count:
        in_scope_blocking.append("new_high_or_critical_findings")
    if delta > 0.0:
        in_scope_blocking.append("drift_score_regressed")

    blocking_reasons: list[str] = list(in_scope_blocking)
    if out_of_scope_new:
        blocking_reasons.append("out_of_scope_diff_noise")

    accept_change = not blocking_reasons
    in_scope_accept = not in_scope_blocking
    decision_reason_code, decision_reason = _diff_decision_reason(
        accept_change=accept_change,
        in_scope_accept=in_scope_accept,
        has_out_of_scope_noise=bool(out_of_scope_new),
    )
    return _DiffDecisionState(
        in_scope_blocking=in_scope_blocking,
        blocking_reasons=blocking_reasons,
        accept_change=accept_change,
        in_scope_accept=in_scope_accept,
        decision_reason_code=decision_reason_code,
        decision_reason=decision_reason,
    )
def _diff_decision_reason(
    *,
    accept_change: bool,
    in_scope_accept: bool,
    has_out_of_scope_noise: bool,
) -> tuple[str, str]:
    """Return a stable code/text reason for the diff decision.

    This gives agents a single unambiguous explanation for accept/reject,
    instead of requiring interpretation of multiple boolean fields.
    """
    if accept_change:
        return (
            "accepted_no_blockers",
            "Accepted: no in-scope blockers detected.",
        )
    if not in_scope_accept:
        return (
            "rejected_in_scope_blockers",
            "Rejected due to in-scope high findings or score regression.",
        )
    if has_out_of_scope_noise:
        return (
            "rejected_out_of_scope_noise_only",
            "Rejected due to out-of-scope noise only.",
        )
    return (
        "rejected_unknown",
        "Rejected: blocking conditions detected.",
    )


def diff(
    path: str | Path = ".",
    *,
    diff_ref: str = "HEAD~1",
    uncommitted: bool = False,
    staged_only: bool = False,
    baseline_file: str | None = None,
    from_file: str | None = None,
    to_file: str | None = None,
    target_path: str | None = None,
    max_findings: int = 10,
    response_detail: str = "concise",
    signals: list[str] | None = None,
    exclude_signals: list[str] | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Analyze drift changes since a git ref or baseline.

    Parameters
    ----------
    path:
        Repository root directory.
    diff_ref:
        Git ref to diff against (e.g. ``"HEAD~1"``, ``"main"``).
    uncommitted:
        Compare current working tree changes against ``HEAD``.
    staged_only:
        Compare only staged changes.
    baseline_file:
        Path to a ``.drift-baseline.json`` file for comparison.
    target_path:
        Restrict decision logic to findings inside this subpath while still
        reporting whether out-of-scope diff noise exists.
    max_findings:
        Maximum findings in the response.
    response_detail:
        ``"concise"`` or ``"detailed"``.
    """
    from drift.analyzer import analyze_diff as _analyze_diff
    from drift.telemetry import timed_call

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params = {
        "path": str(path),
        "diff_ref": diff_ref,
        "uncommitted": uncommitted,
        "staged_only": staged_only,
        "baseline_file": baseline_file,
        "from_file": from_file,
        "to_file": to_file,
        "target_path": target_path,
        "max_findings": max_findings,
        "response_detail": response_detail,
        "signals": signals,
        "exclude_signals": exclude_signals,
    }

    try:
        cfg = _load_config_cached(repo_path)
        _warn_config_issues(cfg)

        if uncommitted and staged_only:
            raise ValueError("Options 'uncommitted' and 'staged_only' are mutually exclusive.")

        if (from_file is None) ^ (to_file is None):
            result = _error_response(
                "DRIFT-1003",
                "Options 'from_file' and 'to_file' must be provided together.",
                invalid_fields=[
                    {
                        "field": "from_file/to_file",
                        "value": {"from_file": from_file, "to_file": to_file},
                        "reason": "Both snapshot files are required for offline diff mode",
                    }
                ],
            )
            _emit_api_telemetry(
                tool_name="api.diff",
                params=params,
                status="ok",
                elapsed_ms=elapsed_ms(),
                result=result,
                error=None,
                repo_root=repo_path,
            )
            return result

        if from_file and to_file:
            try:
                from_path = Path(from_file).resolve()
                to_path = Path(to_file).resolve()
                from_findings, snapshot_score_before = _load_snapshot_findings(from_path)
                to_findings, snapshot_score_after = _load_snapshot_findings(to_path)
                result = _build_snapshot_diff_response(
                    from_path=from_path,
                    to_path=to_path,
                    from_findings=from_findings,
                    to_findings=to_findings,
                    score_before=snapshot_score_before,
                    score_after=snapshot_score_after,
                    max_findings=max_findings,
                    response_detail=response_detail,
                )
                _emit_api_telemetry(
                    tool_name="api.diff",
                    params=params,
                    status="ok",
                    elapsed_ms=elapsed_ms(),
                    result=result,
                    error=None,
                    repo_root=repo_path,
                )
                result = apply_output_mode(result, getattr(cfg, "output_mode", "full"))
                return shape_for_profile(result, response_profile)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                result = _error_response(
                    "DRIFT-1003",
                    f"Failed to read snapshot diff input: {exc}",
                    invalid_fields=[
                        {
                            "field": "from_file/to_file",
                            "value": {"from_file": from_file, "to_file": to_file},
                            "reason": "Files must be valid drift analyze JSON reports",
                        }
                    ],
                )
                _emit_api_telemetry(
                    tool_name="api.diff",
                    params=params,
                    status="ok",
                    elapsed_ms=elapsed_ms(),
                    result=result,
                    error=None,
                    repo_root=repo_path,
                )
                return result

        if not uncommitted and not staged_only and diff_ref.startswith("--"):
            result = _error_response(
                "DRIFT-1003",
                f"Invalid diff_ref value: '{diff_ref}' looks like a command-line option.",
                invalid_fields=[{
                    "field": "diff_ref",
                    "value": diff_ref,
                    "reason": (
                        "Must be a valid git ref (e.g. HEAD~1, main, a1b2c3d),"
                        " not an option flag"
                    ),
                }],
                suggested_fix={
                    "action": "Pass a valid git ref",
                    "example_call": {"tool": "drift_diff", "params": {"diff_ref": "HEAD~1"}},
                },
            )
            _emit_api_telemetry(
                tool_name="api.diff",
                params=params,
                status="ok",
                elapsed_ms=elapsed_ms(),
                result=result,
                error=None,
                repo_root=repo_path,
            )
            return result

        diff_mode = "ref"
        if staged_only:
            diff_mode = "staged"
            diff_ref = "HEAD"
        elif uncommitted:
            diff_mode = "uncommitted"
            diff_ref = "HEAD"

        # Current analysis (diff scope)
        diff_analysis = _analyze_diff(
            repo_path,
            config=cfg,
            diff_ref=diff_ref,
            diff_mode=diff_mode,
        )

        # Baseline comparison
        if baseline_file:
            bl_path = Path(baseline_file).resolve()
            if not bl_path.is_relative_to(repo_path):
                result = _error_response(
                    "DRIFT-1003",
                    "baseline_file must reside inside the repository root.",
                    invalid_fields=[{
                        "field": "baseline_file",
                        "value": baseline_file,
                        "reason": "Path traversal outside repository root",
                    }],
                )
                _emit_api_telemetry(
                    tool_name="api.diff",
                    params=params,
                    status="ok",
                    elapsed_ms=elapsed_ms(),
                    result=result,
                    error=None,
                    repo_root=repo_path,
                )
                return result

            from drift.baseline import baseline_diff as _bl_diff
            from drift.baseline import load_baseline

            fps = load_baseline(bl_path)
            new, _known = _bl_diff(diff_analysis.findings, fps)
            resolved = [f for f in _known]
        else:
            new = diff_analysis.findings
            resolved = []

        # For uncommitted/staged diff modes without a baseline, subtract
        # findings that already exist in HEAD so that pre-existing findings
        # in changed files are not incorrectly reported as newly introduced
        # by the working-tree changes.  This is a best-effort comparison that
        # degrades safely: on any error the full finding list is kept. (#525)
        pre_existing_head_count = 0
        if diff_mode in ("uncommitted", "staged") and not baseline_file and new:
            try:
                import subprocess as _sp

                from drift.analyzer import get_head_fingerprints_for_diff as _head_fps
                from drift.baseline import finding_fingerprint as _fp

                _git_cmd = (
                    ["git", "diff", "--cached", "--name-only"]
                    if diff_mode == "staged"
                    else ["git", "diff", "--name-only", "HEAD"]
                )
                _git_result = _sp.run(
                    _git_cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=repo_path,
                    check=True,
                    stdin=_sp.DEVNULL,
                )
                _changed_files = [
                    line
                    for line in _git_result.stdout.strip().splitlines()
                    if line
                ]
                if _changed_files:
                    _head_fingerprints = _head_fps(repo_path, _changed_files, cfg)
                    if _head_fingerprints:
                        _pre_existing = [
                            f for f in new if _fp(f) in _head_fingerprints
                        ]
                        new = [f for f in new if _fp(f) not in _head_fingerprints]
                        pre_existing_head_count = len(_pre_existing)
            except Exception:
                pass  # Safe fallback: report all findings as new

        # Signal filter: include/exclude by signal abbreviation
        if signals:
            _incl = {s.upper() for s in signals}
            new = [f for f in new if signal_abbrev(f.signal_type) in _incl]
            resolved = [f for f in resolved if signal_abbrev(f.signal_type) in _incl]
        if exclude_signals:
            _excl = {s.upper() for s in exclude_signals}
            new = [f for f in new if signal_abbrev(f.signal_type) not in _excl]
            resolved = [f for f in resolved if signal_abbrev(f.signal_type) not in _excl]

        scope_state = _scope_findings(
            new=new,
            resolved=resolved,
            target_path=target_path,
        )
        scoped_new = scope_state.scoped_new
        scoped_resolved = scope_state.scoped_resolved
        out_of_scope_new = scope_state.out_of_scope_new
        normalized_target = scope_state.normalized_target

        # Score comparison via trend context
        score_after = diff_analysis.drift_score
        score_before: float = 0.0
        if (
            diff_analysis.trend is not None
            and diff_analysis.trend.previous_score is not None
        ):
            score_before = diff_analysis.trend.previous_score
            has_trend_baseline = True
        else:
            has_trend_baseline = False
        delta = round(score_after - score_before, 4)

        # When no historical baseline exists, flag the score fields as
        # synthetic so agents don't misinterpret zero as the repo baseline (#119).
        score_basis = "historical" if has_trend_baseline else "zero_default"

        from drift.finding_priority import _priority_class

        drift_categories = sorted({_priority_class(f) for f in scoped_new}) if scoped_new else []
        affected = sorted({
            f.file_path.as_posix().rsplit("/", 1)[0]
            for f in scoped_new
            if f.file_path
        })

        status = "stable"
        if delta > 0.01:
            status = "new_critical" if any(
                f.severity.value in ("critical", "high") for f in scoped_new
            ) else "degraded"
        elif delta < -0.01:
            status = "improved"

        confidence = "high"
        if diff_analysis.is_degraded:
            confidence = "low"
        elif diff_analysis.total_files < 5:
            confidence = "medium"

        if response_detail == "concise":
            ranked_new = sorted(scoped_new, key=lambda f: f.impact, reverse=True)[:max_findings]
            new_list = [_finding_concise(f) for f in ranked_new]
            resolved_list = [_finding_concise(f) for f in scoped_resolved[:max_findings]]
        else:
            ranked_new = sorted(scoped_new, key=lambda f: f.impact, reverse=True)[:max_findings]
            new_list = [_finding_detailed(f) for f in ranked_new]
            resolved_list = [_finding_detailed(f) for f in scoped_resolved[:max_findings]]

        n_new = len(scoped_new)
        summary_parts = [f"{n_new} new finding{'s' if n_new != 1 else ''}"]
        high_count = sum(
            1 for f in scoped_new if f.severity.value in ("critical", "high")
        )
        if high_count:
            summary_parts.append(f"{high_count} high/critical")
        if out_of_scope_new:
            summary_parts.append(f"{len(out_of_scope_new)} out-of-scope")
        if pre_existing_head_count > 0:
            summary_parts.append(f"{pre_existing_head_count} pre-existing-in-head")
        summary_parts.append(f"drift score {'+' if delta >= 0 else ''}{delta:.3f}")

        decision_state = _build_diff_decision_state(
            scoped_new=scoped_new,
            out_of_scope_new=out_of_scope_new,
            delta=delta,
        )
        blocking_reasons = decision_state.blocking_reasons

        # Resolved-count-by-rule: helps agents gauge batch fix efficiency
        _resolved_by_rule: dict[str, int] = {}
        for _rf in scoped_resolved:
            _rk = signal_abbrev(_rf.signal_type)
            _resolved_by_rule[_rk] = _resolved_by_rule.get(_rk, 0) + 1

        # Noise context: help agents distinguish pre-existing findings from
        # change-caused findings when drift_detected=false but counts > 0.
        pre_existing_count = len(out_of_scope_new)
        noise_explanation = None
        if pre_existing_head_count > 0 and not baseline_file:
            noise_explanation = (
                f"{pre_existing_head_count} finding(s) already existed in HEAD and "
                f"were excluded from new_findings. They are pre-existing and not "
                f"caused by the current working-tree change."
            )
        elif not baseline_file and pre_existing_count > 0:
            noise_explanation = (
                f"{pre_existing_count} finding(s) are pre-existing out-of-scope noise, "
                f"not caused by this change. Use 'drift baseline save' then "
                f"'drift diff --baseline .drift-baseline.json' to suppress them."
            )
        elif not scoped_new and not out_of_scope_new:
            noise_explanation = "No new findings detected."
        noise_context = {
            "pre_existing_count": pre_existing_count + pre_existing_head_count,
            "pre_existing_head_count": pre_existing_head_count,
            "explanation": noise_explanation,
        }

        thresholds = getattr(cfg, "thresholds", None)
        max_changed_files = getattr(
            thresholds,
            "diff_baseline_recommend_max_changed_files",
            50,
        )
        max_new_findings = getattr(
            thresholds,
            "diff_baseline_recommend_max_new_findings",
            100,
        )
        max_out_of_scope_findings = getattr(
            thresholds,
            "diff_baseline_recommend_max_out_of_scope_findings",
            50,
        )

        baseline_reasons: list[str] = []
        if not baseline_file:
            if diff_analysis.total_files >= max_changed_files:
                baseline_reasons.append("large_working_tree")
            if n_new >= max_new_findings:
                baseline_reasons.append("high_new_finding_volume")
            if (
                target_path
                and len(out_of_scope_new)
                >= max_out_of_scope_findings
            ):
                baseline_reasons.append("out_of_scope_noise")

        baseline_recommended = bool(baseline_reasons)
        baseline_reason = baseline_reasons[0] if baseline_reasons else "none"

        accept_change = decision_state.accept_change
        in_scope_accept = decision_state.in_scope_accept
        decision_reason_code = decision_state.decision_reason_code
        decision_reason = decision_state.decision_reason

        staged_file_count = diff_analysis.total_files if diff_mode == "staged" else None
        no_staged_files = bool(diff_mode == "staged" and diff_analysis.total_files == 0)

        if not accept_change:
            if decision_reason_code == "rejected_out_of_scope_noise_only":
                _agent_hint = (
                    "No in-scope blockers detected, but out-of-scope drift noise "
                    "is present. Use in_scope_accept for scoped gating and "
                    "consider creating or refreshing a baseline."
                )
            else:
                _agent_hint = (
                    "Change rejected due to in-scope drift blockers. Call "
                    "drift_fix_plan and address blockers before proceeding."
                )
        elif no_staged_files:
            _agent_hint = (
                "No staged files were analyzed (staged_file_count=0). "
                "Stage changes before relying on accept_change."
            )
        elif status == "improved":
            _agent_hint = (
                "Score is improving. Continue with the next batch_eligible "
                "group or next fix_plan task. Use drift_nudge between edits "
                "for fast feedback."
            )
        elif len(scoped_new) > 0:
            _agent_hint = (
                "New findings exist but are within acceptance threshold. "
                "Review the new_findings list before proceeding to ensure "
                "they are acceptable."
            )
        else:
            _agent_hint = (
                "No drift change detected. Safe to proceed to the next task."
            )
        # Suggested next batch targets: signals with remaining new findings
        _new_by_signal: dict[str, int] = {}
        for _nf in scoped_new:
            _nk = signal_abbrev(_nf.signal_type)
            _new_by_signal[_nk] = _new_by_signal.get(_nk, 0) + 1
        _batch_targets = [
            {"signal": sig, "remaining": cnt}
            for sig, cnt in sorted(_new_by_signal.items(), key=lambda x: -x[1])
        ]

        result = _base_response(
            drift_detected=delta > 0.0,
            status=status,
            severity=diff_analysis.severity.value,
            score_before=round(score_before, 4),
            score_after=round(score_after, 4),
            delta=delta,
            score_basis=score_basis,
            score_regressed=delta > 0.0,
            confidence=confidence,
            diff_ref=diff_ref,
            diff_mode=diff_mode,
            staged_file_count=staged_file_count,
            no_staged_files=no_staged_files,
            target_path=normalized_target,
            new_findings=new_list,
            resolved_findings=resolved_list,
            new_finding_count=len(scoped_new),
            new_high_or_critical=high_count,
            resolved_count=len(scoped_resolved),
            resolved_count_by_rule=_resolved_by_rule,
            out_of_scope_new_count=len(out_of_scope_new),
            noise_context=noise_context,
            baseline_recommended=baseline_recommended,
            baseline_reason=baseline_reason,
            drift_categories=drift_categories,
            affected_components=affected,
            summary=", ".join(summary_parts),
            accept_change=accept_change,
            in_scope_accept=in_scope_accept,
            blocking_reasons=blocking_reasons,
            decision_reason_code=decision_reason_code,
            decision_reason=decision_reason,
            suggested_next_batch_targets=_batch_targets,
            recommended_next_actions=_diff_next_actions(
                scoped_new, status, blocking_reasons,
                in_scope_accept=in_scope_accept,
                has_baseline=baseline_file is not None,
                baseline_recommended=baseline_recommended,
                baseline_reason=baseline_reason,
            ),
            response_truncated=len(scoped_new) > max_findings,
            agent_instruction=_agent_hint,
        )
        result.update(_diff_next_step_contract(
            status=status,
            accept_change=accept_change,
            no_staged_files=no_staged_files,
            decision_reason_code=decision_reason_code,
            batch_targets=_batch_targets,
        ))
        _emit_api_telemetry(
            tool_name="api.diff",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )
        result = apply_output_mode(result, getattr(cfg, "output_mode", "full"))
        return shape_for_profile(result, response_profile)
    except Exception as exc:
        _emit_api_telemetry(
            tool_name="api.diff",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        raise


def _diff_next_actions(
    new_findings: list,
    status: str,
    blocking_reasons: list[str],
    *,
    in_scope_accept: bool = False,
    has_baseline: bool = False,
    baseline_recommended: bool = False,
    baseline_reason: str = "none",
) -> list[str]:
    """Derive next actions from diff results."""
    actions: list[str] = []
    if status in ("degraded", "new_critical"):
        actions.append("drift_fix_plan for new findings")
    if any(f.severity.value in ("critical", "high") for f in new_findings):
        actions.append("drift_explain for high-severity signals")
    if baseline_recommended and not has_baseline:
        actions.append(
            "Run 'drift baseline save' before retrying diff "
            f"(baseline_reason={baseline_reason})"
        )
    if "out_of_scope_diff_noise" in blocking_reasons and not has_baseline:
        actions.append(
            "Use 'drift baseline save' then 'drift diff --baseline "
            ".drift-baseline.json' to suppress pre-existing noise"
        )
    if "out_of_scope_diff_noise" in blocking_reasons and in_scope_accept:
        actions.append(
            "accept_change is false due to out-of-scope noise only — "
            "use in_scope_accept (true) as the scoped gate decision"
        )
    elif "out_of_scope_diff_noise" in blocking_reasons:
        actions.append(
            "out_of_scope_diff_noise is pre-existing — check in_scope_accept "
            "for the scoped decision; use 'drift diff --diff-ref HEAD' for "
            "uncommitted changes"
        )
    if status == "improved":
        actions.append("No action needed — drift is improving")
    return actions or ["No immediate action required"]


def _diff_next_step_contract(
    *,
    status: str,
    accept_change: bool,
    no_staged_files: bool,
    decision_reason_code: str,
    batch_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the next-step contract for diff responses (ADR-024)."""
    if no_staged_files:
        return _next_step_contract(next_tool=None, done_when=DONE_STAGED_EXISTS)
    if accept_change and status == "improved" and batch_targets:
        top = batch_targets[0]
        return _next_step_contract(
            next_tool="drift_fix_plan",
            next_params={"signal": top["signal"]},
            done_when=DONE_ACCEPT_CHANGE,
        )
    if accept_change:
        return _next_step_contract(next_tool=None, done_when=DONE_ACCEPT_CHANGE)
    if decision_reason_code == "rejected_out_of_scope_noise_only":
        return _next_step_contract(
            next_tool="drift_diff",
            next_params={"uncommitted": True, "baseline_file": ".drift-baseline.json"},
            done_when=DONE_ACCEPT_CHANGE,
            fallback_tool="drift_scan",
            fallback_params={"response_detail": "concise"},
        )
    # degraded / new_critical / rejected
    return _next_step_contract(
        next_tool="drift_fix_plan",
        next_params={},
        done_when=DONE_ACCEPT_CHANGE,
        fallback_tool="drift_scan",
        fallback_params={"response_detail": "concise"},
    )
