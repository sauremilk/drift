"""Shared configuration and telemetry helpers for the drift API package."""

from __future__ import annotations

import logging as _logging
import threading
from pathlib import Path
from typing import Any

_log = _logging.getLogger("drift")

_CONFIG_CACHE_LOCK = threading.RLock()
_CONFIG_CACHE: dict[tuple[str, str | None], tuple[int | None, Any]] = {}


def _emit_api_telemetry(
    *,
    tool_name: str,
    params: dict[str, Any],
    status: str,
    elapsed_ms: int,
    result: dict[str, Any] | None,
    error: Exception | None,
    repo_root: Path | None,
) -> None:
    """Emit non-blocking telemetry for API calls."""
    from drift.telemetry import log_tool_event

    log_tool_event(
        tool_name=tool_name,
        params=params,
        status=status,
        duration_ms=elapsed_ms,
        result=result,
        error=str(error) if error else None,
        repo_root=repo_root,
    )


def _config_mtime_ns(config_path: Path | None) -> int | None:
    """Return config mtime for cache invalidation, or None when unavailable."""
    if config_path is None:
        return None
    try:
        return config_path.stat().st_mtime_ns
    except OSError:
        return None


def _load_config_cached(
    repo_path: Path,
    config_file: Path | None = None,
) -> Any:
    """Load DriftConfig with a tiny in-process cache keyed by path+mtime."""
    from drift.config import DriftConfig

    resolved_repo = repo_path.resolve()
    resolved_config = (
        config_file.resolve()
        if config_file is not None
        else DriftConfig._find_config_file(resolved_repo)
    )
    key = (
        resolved_repo.as_posix(),
        resolved_config.as_posix() if resolved_config is not None else None,
    )
    mtime_ns = _config_mtime_ns(resolved_config)

    with _CONFIG_CACHE_LOCK:
        cached = _CONFIG_CACHE.get(key)
        if cached is not None and cached[0] == mtime_ns:
            return cached[1]

    cfg = DriftConfig.load(resolved_repo, resolved_config)

    with _CONFIG_CACHE_LOCK:
        _CONFIG_CACHE[key] = (mtime_ns, cfg)

    return cfg


def _warn_config_issues(cfg: Any) -> list[str]:
    """Return human-readable warnings for dangerous config values.

    Designed to be cheap enough to call on every API entry-point so that
    mis-configurations surface early instead of producing silently wrong
    results.
    """
    warnings: list[str] = []
    weights = getattr(cfg, "weights", None)
    if weights is not None and hasattr(weights, "as_dict"):
        for key, val in weights.as_dict().items():
            if val < 0:
                warnings.append(
                    f"Negative signal weight '{key}' = {val} — findings will be inverted"
                )
    thresholds = getattr(cfg, "thresholds", None)
    if thresholds is not None:
        thresh = getattr(thresholds, "similarity_threshold", None)
        if thresh is not None and (thresh < 0 or thresh > 1):
            warnings.append(f"similarity_threshold={thresh} outside valid range [0, 1]")
    if warnings:
        _log.warning("Config issues detected: %s", "; ".join(warnings))
    return warnings
