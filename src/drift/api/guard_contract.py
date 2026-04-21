"""Guard Contract API — pre-edit guard contracts and module-boundary contracts.

Given a target file or module, returns a machine-readable contract that an
AI agent should read **before** editing.  The contract combines:

- Architecture context from ``steer()`` (Phase B)
- Decision constraints from ``ArchGraph`` (Phase D)
- Module-boundary inference (allowed/forbidden imports, public API surface)
- Optionally: existing findings from ``scan()``

Design goals:
- Prevent drift *before it happens* (proactive, not reactive).
- Agent-consumable — flat JSON dict with ``agent_instruction``.
- Fast — reads from persisted ArchGraph, no full analysis unless requested.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

from drift.next_step_contract import _error_response, _next_step_contract
from drift.response_shaping import shape_for_profile
from drift.telemetry import timed_call

_log = logging.getLogger("drift")


# ---------------------------------------------------------------------------
# Boundary inference helpers
# ---------------------------------------------------------------------------


def _infer_layer(module_path: str) -> str:
    """Infer an architectural layer from the module path convention."""
    parts = module_path.replace("\\", "/").split("/")
    # Common layer names
    layer_keywords = {
        "api": "api",
        "commands": "commands",
        "cli": "commands",
        "signals": "signals",
        "models": "models",
        "output": "output",
        "ingestion": "ingestion",
        "config": "config",
        "serve": "serve",
        "scoring": "scoring",
        "calibration": "calibration",
        "arch_graph": "arch_graph",
    }
    for part in reversed(parts):
        if part in layer_keywords:
            return layer_keywords[part]
    return "unknown"


# Typical layer-boundary rules for drift-like Python projects
_LAYER_ALLOWED_IMPORTS: dict[str, list[str]] = {
    "signals": ["models", "ingestion", "config"],
    "api": ["models", "signals", "ingestion", "config", "output", "scoring", "arch_graph"],
    "commands": ["api", "models", "config", "output"],
    "output": ["models", "config"],
    "ingestion": ["models", "config"],
    "scoring": ["models", "config"],
    "models": ["config"],
    "config": [],
    "serve": ["api", "models", "config"],
    "calibration": ["models", "config", "scoring"],
    "arch_graph": ["models", "config"],
}

_LAYER_FORBIDDEN_IMPORTS: dict[str, list[str]] = {
    "signals": ["output", "commands", "api", "serve"],
    "models": ["signals", "api", "commands", "output", "serve", "ingestion"],
    "output": ["signals", "commands", "api", "serve", "ingestion"],
    "ingestion": ["signals", "api", "commands", "output", "serve"],
    "config": ["signals", "api", "commands", "output", "serve", "ingestion", "models"],
}


def _extract_public_api(init_path: Path) -> list[str]:
    """Extract __all__ or top-level imports from an __init__.py file."""
    if not init_path.exists():
        return []
    try:
        source = init_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []

    # Try __all__
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, (ast.List, ast.Tuple))
                ):
                    return [
                        elt.value
                        for elt in node.value.elts
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    ]

    # Fallback: names from import statements
    names: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.names:
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                if not name.startswith("_"):
                    names.append(name)
    return names


def _find_related_tests(repo_root: Path, target: str) -> list[str]:
    """Find test files that likely cover the target."""
    target_norm = target.replace("\\", "/")
    tests_dir = repo_root / "tests"
    if not tests_dir.is_dir():
        return []

    # Derive expected test file names
    target_path = Path(target_norm)
    stem = target_path.stem
    candidates = [
        f"test_{stem}.py",
        f"test_{stem.replace('.', '_')}.py",
    ]

    found: list[str] = []
    for test_file in tests_dir.rglob("test_*.py"):
        if test_file.name in candidates:
            found.append(str(test_file.relative_to(repo_root)).replace("\\", "/"))

    return sorted(found)


def _extract_imports(file_path: Path) -> list[str]:
    """Extract imported module names from a Python file."""
    if not file_path.exists() or file_path.suffix != ".py":
        return []
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []

    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return sorted(set(modules))


# ---------------------------------------------------------------------------
# Public aliases for layer-boundary data (used by drift_brief and tests)
# ---------------------------------------------------------------------------

infer_layer = _infer_layer
LAYER_ALLOWED_IMPORTS = _LAYER_ALLOWED_IMPORTS
LAYER_FORBIDDEN_IMPORTS = _LAYER_FORBIDDEN_IMPORTS
find_related_tests = _find_related_tests


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _build_guard_contract(
    repo_root: Path,
    target: str,
    *,
    steer_result: dict[str, Any] | None,
    decision_constraints: list[dict[str, Any]],
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the guard contract from gathered data."""
    target_norm = target.replace("\\", "/")

    # Determine module
    module = "unknown"
    layer = "unknown"
    if steer_result and steer_result.get("modules"):
        mod_info = steer_result["modules"][0]
        module = mod_info.get("path", "unknown")
        layer = mod_info.get("layer") or _infer_layer(module)
    else:
        layer = _infer_layer(target_norm)
        # Derive module from path
        parts = target_norm.split("/")
        # Find src/package boundary
        for i, part in enumerate(parts):
            if part == "src" and i + 1 < len(parts):
                module = "/".join(parts[i : max(i + 3, len(parts) - 1)])
                break
        if module == "unknown":
            module = "/".join(parts[:-1]) if len(parts) > 1 else target_norm

    # Dependencies from actual imports
    target_path = repo_root / target_norm
    imports = _extract_imports(target_path)
    dependencies = sorted(set(
        imp.split(".")[1] if imp.startswith("drift.") and len(imp.split(".")) > 1 else imp
        for imp in imports
        if imp.startswith("drift.")
    ))

    # Invariants from steer context
    invariants: list[str] = []
    if steer_result:
        if steer_result.get("hotspots"):
            degrading = [h for h in steer_result["hotspots"] if h.get("trend") == "degrading"]
            if degrading:
                invariants.append(
                    f"CAUTION: {len(degrading)} degrading hotspot(s) in this module"
                )
        if steer_result.get("abstractions"):
            n = len(steer_result["abstractions"])
            invariants.append(
                f"{n} reusable abstractions available — prefer reuse"
            )

    # Active signals affecting this target
    active_signals: list[str] = []
    if steer_result and steer_result.get("hotspots"):
        for hs in steer_result["hotspots"]:
            if hs.get("recurring_signals"):
                active_signals.extend(hs["recurring_signals"].keys())
        active_signals = sorted(set(active_signals))

    # Related tests
    related_tests = _find_related_tests(repo_root, target_norm)

    # Boundary contract
    allowed = _LAYER_ALLOWED_IMPORTS.get(layer, [])
    forbidden = _LAYER_FORBIDDEN_IMPORTS.get(layer, [])

    # Public API surface from __init__.py
    module_dir = target_path.parent if target_path.suffix else target_path
    init_file = module_dir / "__init__.py"
    public_api = _extract_public_api(init_file)

    # Arch decisions
    arch_decisions = [
        {"id": d.get("id", ""), "constraint": d.get("rule", "")}
        for d in decision_constraints
    ]

    # Neighbours
    neighbors = steer_result.get("neighbors", []) if steer_result else []

    return {
        "schema_version": "1.0",
        "type": "guard_contract",
        "target": target_norm,
        "module": module,
        "pre_edit_guard": {
            "invariants": invariants,
            "active_signals_affecting": active_signals,
            "known_findings": findings or [],
            "related_tests": related_tests,
            "dependencies": dependencies,
        },
        "boundary_contract": {
            "layer": layer,
            "allowed_imports_from": allowed,
            "forbidden_imports_from": forbidden,
            "public_api_surface": public_api,
            "arch_decisions": arch_decisions,
            "neighbors": neighbors,
        },
    }


# ---------------------------------------------------------------------------
# Public API endpoint
# ---------------------------------------------------------------------------


def guard_contract(
    path: str | Path = ".",
    *,
    target: str,
    include_findings: bool = False,
    max_findings: int = 10,
    cache_dir: str | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Return a pre-edit guard contract and module-boundary contract.

    Agents should call this **before** editing a file to understand the
    architectural constraints, invariants, and boundaries that apply.

    Parameters
    ----------
    path:
        Repository root path.
    target:
        File or module path to generate the contract for.
    include_findings:
        When ``True``, include existing drift findings for the target.
    max_findings:
        Cap on the number of findings included (only when *include_findings*).
    cache_dir:
        Explicit cache directory for the ArchGraph store.
    response_profile:
        Optional profile for response shaping.

    Returns
    -------
    dict[str, Any]
        Guard contract with ``pre_edit_guard`` and ``boundary_contract``.
    """
    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params: dict[str, Any] = {
        "path": str(path),
        "target": target,
        "include_findings": include_findings,
        "cache_dir": cache_dir,
    }

    try:
        from drift.api._config import _emit_api_telemetry

        # 1. Get steer context (fast, from ArchGraph cache)
        steer_result: dict[str, Any] | None = None
        try:
            from drift.api.steer import steer as _steer
            steer_result = _steer(
                path=str(repo_path),
                target=target,
                cache_dir=cache_dir,
            )
            if steer_result.get("status") != "ok":
                steer_result = None
        except Exception:
            _log.debug("guard_contract: steer() unavailable", exc_info=True)

        # 2. Get decision constraints
        decision_constraints: list[dict[str, Any]] = []
        if steer_result and steer_result.get("decision_constraints"):
            decision_constraints = steer_result["decision_constraints"]

        # 3. Optionally fetch findings
        findings: list[dict[str, Any]] | None = None
        if include_findings:
            try:
                from drift.api.scan import scan as _scan
                scan_result = _scan(
                    path=str(repo_path),
                    target_path=target,
                    max_findings=max_findings,
                    response_detail="concise",
                )
                if scan_result.get("status") == "ok":
                    findings = scan_result.get("findings", [])
            except Exception:
                _log.debug("guard_contract: scan() failed", exc_info=True)

        # 4. Build the contract
        contract = _build_guard_contract(
            repo_root=repo_path,
            target=target,
            steer_result=steer_result,
            decision_constraints=decision_constraints,
            findings=findings,
        )

        # 5. Add agent instruction
        agent_instruction = _build_agent_instruction(contract)

        result: dict[str, Any] = {
            "status": "ok",
            **contract,
            "agent_instruction": agent_instruction,
            **_next_step_contract(
                next_tool="drift_nudge",
                done_when="task completed AND drift_nudge.safe_to_commit == true",
                fallback_tool="drift_scan",
            ),
        }

        _emit_api_telemetry(
            tool_name="api.guard_contract",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )

        return shape_for_profile(result, response_profile)

    except Exception as exc:
        _log.debug("guard_contract() error: %s", exc, exc_info=True)
        try:
            from drift.api._config import _emit_api_telemetry
            _emit_api_telemetry(
                tool_name="api.guard_contract",
                params=params,
                status="error",
                elapsed_ms=elapsed_ms(),
                result=None,
                error=exc,
                repo_root=repo_path,
            )
        except Exception:
            pass
        return _error_response("DRIFT-7001", str(exc), recoverable=True)


def _build_agent_instruction(contract: dict[str, Any]) -> str:
    """Build a context-sensitive agent instruction from the contract."""
    parts: list[str] = []

    target = contract.get("target", "unknown")
    layer = contract.get("boundary_contract", {}).get("layer", "unknown")
    parts.append(f"Guard contract for '{target}' in the '{layer}' layer.")

    boundary = contract.get("boundary_contract", {})
    forbidden = boundary.get("forbidden_imports_from", [])
    if forbidden:
        parts.append(
            f"CONSTRAINT: Do NOT import from layers: {', '.join(forbidden)}."
        )

    allowed = boundary.get("allowed_imports_from", [])
    if allowed:
        parts.append(f"Allowed imports from: {', '.join(allowed)}.")

    decisions = boundary.get("arch_decisions", [])
    if decisions:
        rules = "; ".join(d.get("constraint", "") for d in decisions if d.get("constraint"))
        if rules:
            parts.append(f"ARCH RULES: {rules}")

    guard = contract.get("pre_edit_guard", {})
    tests = guard.get("related_tests", [])
    if tests:
        parts.append(f"Run these tests after editing: {', '.join(tests)}.")

    findings = guard.get("known_findings", [])
    if findings:
        parts.append(f"WARNING: {len(findings)} existing finding(s) in this file.")

    invariants = guard.get("invariants", [])
    for inv in invariants:
        parts.append(inv)

    parts.append("After editing, call drift_nudge to verify no regressions.")

    return " ".join(parts)
