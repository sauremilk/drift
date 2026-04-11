"""Validate endpoint — config and environment checks before analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from drift.api._config import _emit_api_telemetry, _load_config_cached
from drift.api_helpers import (
    _base_response,
    _error_response,
    shape_for_profile,
)


def validate(
    path: str | Path = ".",
    *,
    config_file: str | None = None,
    baseline_file: str | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Validate configuration and environment before analysis.

    Parameters
    ----------
    path:
        Repository root directory.
    config_file:
        Explicit config file path (auto-discovered if ``None``).
    baseline_file:
        Optional baseline file for progress comparison.  When provided,
        a quick scan is performed and the result is compared against the
        baseline to report score progress, resolved/new finding counts.
    """
    import subprocess

    from drift.telemetry import timed_call

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params = {"path": str(path), "config_file": config_file, "baseline_file": baseline_file}

    try:
        # Path sandbox: config_file / baseline_file must be inside repo root
        for _field, _val in [("config_file", config_file), ("baseline_file", baseline_file)]:
            if _val is not None and not Path(_val).resolve().is_relative_to(repo_path):
                result = _error_response(
                    "DRIFT-1003",
                    f"{_field} must reside inside the repository root.",
                    invalid_fields=[{
                        "field": _field,
                        "value": _val,
                        "reason": "Path traversal outside repository root",
                    }],
                )
                _emit_api_telemetry(
                    tool_name="api.validate",
                    params=params,
                    status="ok",
                    elapsed_ms=elapsed_ms(),
                    result=result,
                    error=None,
                    repo_root=repo_path,
                )
                return result

        # Check git availability
        git_available = False
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=repo_path,
                capture_output=True,
                check=True,
                timeout=5,
                stdin=subprocess.DEVNULL,
            )
            git_available = True
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            pass

        # Load and validate config
        warnings: list[str] = []
        config_source: str | None = None
        valid = True
        cfg = None

        try:
            from drift.config import DriftConfig

            cfg = _load_config_cached(repo_path, Path(config_file) if config_file else None)
            cfg_path = DriftConfig._find_config_file(repo_path)
            config_source = str(cfg_path) if cfg_path else "defaults"

            # Weight checks
            weight_sum = sum(cfg.weights.as_dict().values())
            if weight_sum < 0.5 or weight_sum > 2.0:
                warnings.append(
                    f"Weight sum {weight_sum:.3f} outside [0.5, 2.0] "
                    "— auto-calibration will normalize"
                )
            for key, val in cfg.weights.as_dict().items():
                if val < 0:
                    warnings.append(f"Weight '{key}' is negative ({val})")
                    valid = False

            # Threshold checks
            thresh = cfg.thresholds.similarity_threshold
            if thresh < 0 or thresh > 1:
                warnings.append(f"similarity_threshold={thresh} outside [0, 1]")
                valid = False

        except Exception as exc:
            valid = False
            warnings.append(f"Config error: {exc}")

        # File discovery check
        files_discoverable = 0
        capabilities: list[str] = []
        if cfg is not None:
            try:
                from drift.ingestion.file_discovery import discover_files

                files = discover_files(repo_path, cfg.include, cfg.exclude)
                files_discoverable = len(files)
                langs = {f.language for f in files}
                if "python" in langs:
                    capabilities.append("python")
                if langs & {"typescript", "javascript"}:
                    capabilities.append("typescript")
            except Exception:
                pass

        # Embeddings check
        embeddings_available = False
        if cfg is not None:
            try:
                import importlib.util

                embeddings_available = (
                    cfg.embeddings_enabled
                    and importlib.util.find_spec("sentence_transformers") is not None
                )
            except Exception:
                pass

        result = _base_response(
            valid=valid,
            config_source=config_source,
            git_available=git_available,
            files_discoverable=files_discoverable,
            embeddings_available=embeddings_available,
            warnings=warnings,
            capabilities=capabilities,
        )

        # Optional baseline progress comparison
        if baseline_file and valid:
            try:
                from drift.baseline import load_baseline

                bl_fingerprints = load_baseline(Path(baseline_file))

                # Access scan via package attribute so monkeypatch targets work
                import drift.api as _api_pkg

                scan_result = _api_pkg.scan(repo_path, max_findings=9999, response_detail="concise")
                score_after = scan_result.get("drift_score", 0.0)

                # Read baseline score from file
                import json as _json

                bl_data = _json.loads(Path(baseline_file).read_text(encoding="utf-8"))
                score_before = bl_data.get("drift_score", 0.0)

                # Count new vs resolved via fingerprints
                from drift.analyzer import analyze_repo
                from drift.baseline import baseline_diff as _bl_diff
                from drift.config import DriftConfig

                _cfg = _load_config_cached(repo_path)
                _analysis = analyze_repo(repo_path, config=_cfg)
                new_findings, known_findings = _bl_diff(
                    _analysis.findings, bl_fingerprints
                )

                delta = round(score_after - score_before, 4)
                direction = "improved" if delta < -0.01 else (
                    "degraded" if delta > 0.01 else "stable"
                )
                resolved_count = max(0, len(bl_fingerprints) - len(known_findings))
                known_count = len(known_findings)
                result["progress"] = {
                    "baseline_file": str(baseline_file),
                    "score_before": round(score_before, 4),
                    "score_after": round(score_after, 4),
                    "delta": delta,
                    "direction": direction,
                    "resolved_count": resolved_count,
                    "known_count": known_count,
                    "new_count": len(new_findings),
                    "progress_summary": (
                        f"{resolved_count} finding(s) resolved, "
                        f"{len(new_findings)} new, "
                        f"score {'improved' if delta < 0 else 'worsened'} by "
                        f"{abs(delta):.4f}"
                    ),
                }
            except Exception as exc_bl:
                result["progress"] = {
                    "error": f"Baseline comparison failed: {exc_bl}",
                }

        _emit_api_telemetry(
            tool_name="api.validate",
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
            tool_name="api.validate",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        raise
