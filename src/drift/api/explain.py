"""Explain endpoint — signal, rule, and error code documentation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

from drift.api._config import _emit_api_telemetry, _load_config_cached
from drift.api_helpers import (
    VALID_SIGNAL_IDS,
    _base_response,
    _error_response,
    _finding_detailed,
    resolve_signal,
    shape_for_profile,
    signal_abbrev,
)

# Regex for finding fingerprint: 8-16 lowercase hex chars.
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{8,16}$")


def _repo_examples_for_signal(
    signal_abbr: str,
    repo_root: Path,
    *,
    max_examples: int = 5,
) -> list[dict[str, Any]]:
    """Return top findings for *signal_abbr* from this repo (best-effort).

    Runs a lightweight analysis.  If the analysis fails (e.g. no git repo),
    returns an empty list instead of raising.
    """
    try:
        from drift.analyzer import analyze_repo
        cfg = _load_config_cached(repo_root)
        analysis = analyze_repo(repo_root, config=cfg)
        sig_type = resolve_signal(signal_abbr)
        if sig_type is None:
            return []
        matches = [f for f in analysis.findings if f.signal_type == sig_type]
        matches.sort(key=lambda f: f.impact, reverse=True)
        examples: list[dict[str, Any]] = []
        for f in matches[:max_examples]:
            examples.append({
                "file": f.file_path.as_posix() if f.file_path else None,
                "line": f.start_line,
                "finding": f.title,
                "next_action": f.fix or f.description,
            })
        return examples
    except Exception:
        return []


def explain(
    topic: str,
    *,
    repo_path: str | Path | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Explain a signal, rule, or error code.

    Parameters
    ----------
    topic:
        A signal abbreviation (``"PFS"``), signal type name
        (``"pattern_fragmentation"``), error code (``"DRIFT-1001"``),
        or a finding fingerprint (16-char hex string from ``finding_id``).
    repo_path:
        Optional repository root.  When provided, a lightweight scan is
        performed and the top findings for the signal are included as
        ``repo_examples`` in the response.  Required when *topic* is a
        finding fingerprint.
    """
    import importlib

    explain_mod = importlib.import_module("drift.commands.explain")
    signal_info = cast(dict[str, dict[str, Any]], getattr(explain_mod, "_SIGNAL_INFO", {}))
    from drift.telemetry import timed_call

    elapsed_ms = timed_call()
    params = {"topic": topic, "repo_path": str(repo_path) if repo_path else None}

    try:
        # Try as signal abbreviation first
        upper = topic.upper()
        if upper in signal_info:
            info = signal_info[upper]
            result = _base_response(
                type="signal",
                signal=upper,
                name=info.get("name", upper),
                weight=float(info.get("weight", "0")),
                description=info.get("description", ""),
                detection_logic=info.get("detects", ""),
                typical_cause="Multiple AI sessions or copy-paste-modify patterns.",
                remediation_approach=info.get("fix_hint", ""),
                trigger_contract=info.get("trigger_contract"),
                related_signals=_related_signals(upper),
            )
            if repo_path:
                result["repo_examples"] = _repo_examples_for_signal(
                    upper, Path(repo_path).resolve(),
                )
            _emit_api_telemetry(
                tool_name="api.explain",
                params=params,
                status="ok",
                elapsed_ms=elapsed_ms(),
                result=result,
                error=None,
                repo_root=Path(repo_path).resolve() if repo_path else Path.cwd(),
            )
            return result

        # Try as SignalType value
        resolved = resolve_signal(topic)
        if resolved:
            abbr = signal_abbrev(resolved)
            if abbr in signal_info:
                result = explain(abbr, repo_path=repo_path)
                _emit_api_telemetry(
                    tool_name="api.explain",
                    params=params,
                    status="ok",
                    elapsed_ms=elapsed_ms(),
                    result=result,
                    error=None,
                    repo_root=Path(repo_path).resolve() if repo_path else Path.cwd(),
                )
                return result
            result = _base_response(
                type="signal",
                signal=abbr,
                name=resolved.value,
                description=f"Signal: {resolved.value}",
            )
            _emit_api_telemetry(
                tool_name="api.explain",
                params=params,
                status="ok",
                elapsed_ms=elapsed_ms(),
                result=result,
                error=None,
                repo_root=Path.cwd(),
            )
            return result

        # Try as error code
        from drift.errors import ERROR_REGISTRY, format_error_info_for_explain

        if topic.upper() in ERROR_REGISTRY:
            err = ERROR_REGISTRY[topic.upper()]
            summary, why, action = format_error_info_for_explain(topic.upper(), err)
            result = _base_response(
                type="error_code",
                error_code=err.code,
                category=err.category,
                summary=summary,
                why=why,
                action=action,
            )
            _emit_api_telemetry(
                tool_name="api.explain",
                params=params,
                status="ok",
                elapsed_ms=elapsed_ms(),
                result=result,
                error=None,
                repo_root=Path.cwd(),
            )
            return result

        # ADR-042: Try as finding fingerprint (8-16 hex chars)
        if _FINGERPRINT_RE.match(topic.lower()):
            finding_result = _explain_finding_by_fingerprint(
                topic.lower(), repo_path,
            )
            if finding_result is not None:
                _emit_api_telemetry(
                    tool_name="api.explain",
                    params=params,
                    status="ok",
                    elapsed_ms=elapsed_ms(),
                    result=finding_result,
                    error=None,
                    repo_root=Path(repo_path).resolve() if repo_path else Path.cwd(),
                )
                return shape_for_profile(finding_result, response_profile)

        # Not found — helpful error
        result = _error_response(
            "DRIFT-1003",
            f"Unknown topic: '{topic}'",
            invalid_fields=[{
                "field": "topic", "value": topic,
                "reason": "Not a valid signal, rule, or error code",
            }],
            suggested_fix={
                "action": "Use a valid signal abbreviation or error code",
                "valid_values": VALID_SIGNAL_IDS,
                "example_call": {"tool": "drift_explain", "params": {"topic": "PFS"}},
            },
        )
        _emit_api_telemetry(
            tool_name="api.explain",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=Path.cwd(),
        )
        return shape_for_profile(result, response_profile)
    except Exception as exc:
        _emit_api_telemetry(
            tool_name="api.explain",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=Path.cwd(),
        )
        raise


def _related_signals(abbr: str) -> list[str]:
    """Return related signal abbreviations."""
    relations: dict[str, list[str]] = {
        "PFS": ["MDS"],
        "MDS": ["PFS"],
        "AVS": ["CCC", "COD"],
        "CCC": ["AVS"],
        "COD": ["AVS", "CCC"],
        "EDS": ["BEM"],
        "BEM": ["EDS"],
        "TVS": ["ECM"],
        "ECM": ["TVS"],
    }
    return relations.get(abbr, [])


def _explain_finding_by_fingerprint(
    fingerprint: str,
    repo_path: str | Path | None,
) -> dict[str, Any] | None:
    """Resolve a finding fingerprint and return a detailed explanation.

    Performs a lightweight scan of *repo_path* (or cwd) and matches the
    fingerprint against all findings.  Returns ``None`` if no match is found.
    """
    from drift.baseline import finding_fingerprint

    root = Path(repo_path).resolve() if repo_path else Path.cwd()
    try:
        from drift.analyzer import analyze_repo

        cfg = _load_config_cached(root)
        analysis = analyze_repo(root, config=cfg)
    except Exception:
        return None

    for f in analysis.findings:
        fp = finding_fingerprint(f)
        if fp == fingerprint or fp.startswith(fingerprint):
            sig_abbr = signal_abbrev(f.signal_type)
            detail = _finding_detailed(f)

            # Enrich with signal-level context
            import importlib

            explain_mod = importlib.import_module("drift.commands.explain")
            signal_info = cast(
                dict[str, dict[str, Any]],
                getattr(explain_mod, "_SIGNAL_INFO", {}),
            )
            sig_info = signal_info.get(sig_abbr, {})

            return _base_response(
                type="finding",
                finding_id=fp,
                finding=detail,
                signal=sig_abbr,
                signal_name=sig_info.get("name", f.signal_type),
                signal_description=sig_info.get("description", ""),
                detection_logic=sig_info.get("detects", ""),
                remediation_approach=sig_info.get("fix_hint", ""),
                related_signals=_related_signals(sig_abbr),
            )

    return None
