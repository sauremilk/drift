"""Signal 13: Exception Contract Drift (ECM).

Detects public functions whose exception profile changed across
recent commits while their signature (name + parameter count) remained
stable.  This is a proxy for *contract drift* (ADR-008 Phase 3):
callers depend on the exception contract, and silent changes break
that implicit agreement.

MVP implementation: uses ``git show`` to retrieve the previous version
of each file, then compares per-function exception profiles via AST
inspection.  Gracefully skips files that cannot be retrieved (e.g.
shallow clones, new files, binary files).
"""

from __future__ import annotations

import ast
import logging
import subprocess
from collections import defaultdict
from pathlib import Path, PurePosixPath

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals._utils import (
    _SUPPORTED_LANGUAGES,
    _TS_LANGUAGES,
    ts_node_text,
    ts_parse_source,
    ts_walk,
)
from drift.signals.base import BaseSignal, register_signal

logger = logging.getLogger("drift")

# ---------------------------------------------------------------------------
# AST helpers — exception profile extraction
# ---------------------------------------------------------------------------


def _extract_exception_profile(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    """Extract the exception profile of a function AST node.

    Returns a dict with:
      - raise_types: sorted list of exception type names raised
      - handler_types: sorted list of exception type names caught
      - has_bare_except: bool
      - has_bare_raise: bool (raise without argument)
    """
    raise_types: set[str] = set()
    handler_types: set[str] = set()
    has_bare_except = False
    has_bare_raise = False

    for node in ast.walk(func_node):
        if isinstance(node, ast.Raise):
            if node.exc is None:
                has_bare_raise = True
            elif isinstance(node.exc, ast.Call):
                if isinstance(node.exc.func, ast.Name):
                    raise_types.add(node.exc.func.id)
                elif isinstance(node.exc, ast.Attribute):
                    raise_types.add(node.exc.attr)
            elif isinstance(node.exc, ast.Name):
                raise_types.add(node.exc.id)

        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                has_bare_except = True
            elif isinstance(node.type, ast.Name):
                handler_types.add(node.type.id)
            elif isinstance(node.type, ast.Tuple):
                for elt in node.type.elts:
                    if isinstance(elt, ast.Name):
                        handler_types.add(elt.id)

    return {
        "raise_types": sorted(raise_types),
        "handler_types": sorted(handler_types),
        "has_bare_except": has_bare_except,
        "has_bare_raise": has_bare_raise,
    }


def _extract_functions_from_source(source: str) -> dict[str, dict]:
    """Parse Python source and return {func_name: {param_count, profile}} for public functions."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    functions: dict[str, dict] = {}
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name
        if name.startswith("_"):
            continue
        param_count = len(node.args.args) + len(node.args.posonlyargs) + len(node.args.kwonlyargs)
        profile = _extract_exception_profile(node)
        functions[name] = {
            "param_count": param_count,
            "profile": profile,
        }
    return functions


# ---------------------------------------------------------------------------
# Tree-sitter helpers — TS/JS exception profile extraction
# ---------------------------------------------------------------------------


def _ts_extract_exception_profile(func_node: object, src: bytes) -> dict:
    """Extract exception profile from a tree-sitter function node."""
    raise_types: set[str] = set()
    handler_types: set[str] = set()
    has_bare_except = False
    has_bare_raise = False

    for node in ts_walk(func_node):
        if node.type == "throw_statement":
            # throw; (bare) vs throw new ErrorType(...)
            children = [c for c in node.children if c.type not in ("throw", ";")]
            if not children:
                has_bare_raise = True
            else:
                expr = children[0]
                if expr.type == "new_expression":
                    constructor = expr.child_by_field_name("constructor")
                    if constructor:
                        raise_types.add(ts_node_text(constructor, src))
                elif expr.type == "identifier":
                    raise_types.add(ts_node_text(expr, src))

        if node.type == "catch_clause":
            param = node.child_by_field_name("parameter")
            if param is None:
                has_bare_except = True
            else:
                type_ann = next(
                    (c for c in node.children if c.type == "type_annotation"),
                    None,
                )
                if type_ann:
                    handler_types.add(
                        ts_node_text(type_ann, src).lstrip(": ").strip()
                    )
                else:
                    has_bare_except = True  # untyped → catches everything

    return {
        "raise_types": sorted(raise_types),
        "handler_types": sorted(handler_types),
        "has_bare_except": has_bare_except,
        "has_bare_raise": has_bare_raise,
    }


def _ts_extract_functions_from_source(
    source: str, language: str,
) -> dict[str, dict]:
    """Parse TS/JS source via tree-sitter and return {func_name: {param_count, profile}}."""
    result = ts_parse_source(source, language)
    if result is None:
        return {}

    root, src = result
    functions: dict[str, dict] = {}

    for node in ts_walk(root):
        name: str | None = None
        func_node = None

        if node.type == "function_declaration" or node.type == "method_definition":
            name_nd = node.child_by_field_name("name")
            name = ts_node_text(name_nd, src) if name_nd else None
            func_node = node

        elif node.type in ("lexical_declaration", "variable_declaration"):
            for decl in node.children:
                if decl.type != "variable_declarator":
                    continue
                name_nd = decl.child_by_field_name("name")
                value_nd = decl.child_by_field_name("value")
                if (
                    name_nd
                    and value_nd
                    and value_nd.type == "arrow_function"
                ):
                    name = ts_node_text(name_nd, src)
                    func_node = value_nd
                    break

        if name is None or func_node is None:
            continue
        if name.startswith("_"):
            continue

        # Count parameters
        params_node = func_node.child_by_field_name("parameters")
        param_count = 0
        if params_node:
            param_count = sum(
                1 for c in params_node.children
                if c.type in (
                    "required_parameter", "optional_parameter",
                    "rest_parameter", "identifier",
                )
            )

        profile = _ts_extract_exception_profile(func_node, src)
        functions[name] = {
            "param_count": param_count,
            "profile": profile,
        }

    return functions


def _profiles_diverged(old_profile: dict, new_profile: dict) -> bool:
    """Return True if two exception profiles meaningfully diverge."""
    if old_profile == new_profile:
        return False

    # Check raise types changed
    if old_profile["raise_types"] != new_profile["raise_types"]:
        return True
    # Check handler types changed
    if old_profile["handler_types"] != new_profile["handler_types"]:
        return True
    # Check bare except added or removed
    if old_profile["has_bare_except"] != new_profile["has_bare_except"]:
        return True
    # Check bare raise added or removed
    return bool(old_profile["has_bare_raise"] != new_profile["has_bare_raise"])


def _git_show_file(repo_path: Path, ref: str, file_posix: str) -> str | None:
    """Retrieve file content at a given git ref. Returns None on failure."""
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{file_posix}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(repo_path),
            check=True,
            timeout=10,
        )
        return result.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _git_show_files_batch(
    repo_path: Path, ref: str, file_posix_list: list[str],
) -> dict[str, str | None]:
    """Retrieve multiple file contents at *ref* in a single git process.

    Uses ``git cat-file --batch`` which is dramatically faster than
    spawning one ``git show`` subprocess per file (O(1) process instead
    of O(n)).  Falls back per-file on parse error.
    """
    if not file_posix_list:
        return {}

    results: dict[str, str | None] = {}
    queries = [f"{ref}:{fp}" for fp in file_posix_list]
    stdin_data = "\n".join(queries) + "\n"

    try:
        proc = subprocess.run(
            ["git", "cat-file", "--batch"],
            input=stdin_data.encode(),
            capture_output=True,
            cwd=str(repo_path),
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # Fallback: individual calls
        for fp in file_posix_list:
            results[fp] = _git_show_file(repo_path, ref, fp)
        return results

    # Parse batch output: each object is
    #   <sha> blob <size>\n<content>\n   (on success)
    #   <query> missing\n                (on miss)
    raw = proc.stdout
    offset = 0
    for fp in file_posix_list:
        if offset >= len(raw):
            results[fp] = None
            continue

        # Find the header line end
        newline_pos = raw.find(b"\n", offset)
        if newline_pos == -1:
            results[fp] = None
            continue

        header = raw[offset:newline_pos]
        if header.endswith(b"missing"):
            results[fp] = None
            offset = newline_pos + 1
            continue

        # Parse "<sha> blob <size>"
        parts = header.split()
        if len(parts) < 3:
            results[fp] = None
            offset = newline_pos + 1
            continue

        try:
            blob_size = int(parts[2])
        except (ValueError, IndexError):
            results[fp] = None
            offset = newline_pos + 1
            continue

        content_start = newline_pos + 1
        content_end = content_start + blob_size
        if content_end > len(raw):
            results[fp] = None
            break

        try:
            results[fp] = raw[content_start:content_end].decode("utf-8", errors="replace")
        except Exception:
            results[fp] = None

        # Skip past content + trailing newline
        offset = content_end + 1

    # Fill any remaining files not covered by the batch response
    for fp in file_posix_list:
        if fp not in results:
            results[fp] = None

    return results


@register_signal
class ExceptionContractDriftSignal(BaseSignal):
    """Detect public functions with changed exception profiles."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.EXCEPTION_CONTRACT_DRIFT

    @property
    def name(self) -> str:
        return "Exception Contract Drift"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        max_files = config.thresholds.ecm_max_files
        lookback = config.thresholds.ecm_lookback_commits
        repo_path = self._repo_path
        findings: list[Finding] = []

        if repo_path is None:
            return findings

        # Only analyse files with supported languages that have git history
        candidates: list[ParseResult] = []
        for pr in parse_results:
            if pr.language not in _SUPPORTED_LANGUAGES:
                continue
            posix = pr.file_path.as_posix()
            hist = file_histories.get(posix)
            if hist is None or hist.total_commits < 2:
                continue
            candidates.append(pr)

        if not candidates:
            return findings

        # Respect performance guardrail
        if len(candidates) > max_files:
            candidates = sorted(
                candidates,
                key=lambda pr: file_histories.get(
                    pr.file_path.as_posix(), FileHistory(path=pr.file_path)
                ).total_commits,
                reverse=True,
            )[:max_files]

        # Determine comparison ref — use first available lookback commit
        ref = f"HEAD~{min(lookback, 5)}"

        # Batch-fetch all old file contents in a single git process
        candidate_posix = [pr.file_path.as_posix() for pr in candidates]
        old_sources = _git_show_files_batch(repo_path, ref, candidate_posix)

        # Group divergences by module
        module_divergences: dict[str, list[tuple[ParseResult, str, dict, dict]]] = defaultdict(list)

        for pr in candidates:
            posix = pr.file_path.as_posix()

            # Get current source
            try:
                current_source = (repo_path / pr.file_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            # Get old source from batch result
            old_source = old_sources.get(posix)
            if old_source is None:
                continue

            if pr.language in _TS_LANGUAGES:
                current_funcs = _ts_extract_functions_from_source(
                    current_source, pr.language,
                )
                old_funcs = _ts_extract_functions_from_source(
                    old_source, pr.language,
                )
            else:
                current_funcs = _extract_functions_from_source(current_source)
                old_funcs = _extract_functions_from_source(old_source)

            if not current_funcs or not old_funcs:
                continue

            for func_name, current_info in current_funcs.items():
                old_info = old_funcs.get(func_name)
                if old_info is None:
                    continue  # new function — no contract to compare

                # Signature must be stable (same param count)
                if current_info["param_count"] != old_info["param_count"]:
                    continue  # signature changed — intentional refactor

                if _profiles_diverged(old_info["profile"], current_info["profile"]):
                    module_key = PurePosixPath(pr.file_path.parent).as_posix()
                    module_divergences[module_key].append(
                        (pr, func_name, old_info["profile"], current_info["profile"])
                    )

        # Emit findings per module
        for module_key, divergences in module_divergences.items():
            if len(divergences) < 1:
                continue

            # Score: fraction of checked functions that diverged
            all_checked: set[str] = set()
            for pr_item in candidates:
                if PurePosixPath(pr_item.file_path.parent).as_posix() == module_key:
                    try:
                        src = (repo_path / pr_item.file_path).read_text(encoding="utf-8")
                        if pr_item.language in _TS_LANGUAGES:
                            all_checked.update(
                                _ts_extract_functions_from_source(
                                    src, pr_item.language,
                                ).keys()
                            )
                        else:
                            all_checked.update(
                                _extract_functions_from_source(src).keys()
                            )
                    except (OSError, UnicodeDecodeError):
                        pass

            ratio = len(divergences) / max(1, len(all_checked))
            score = min(1.0, ratio * 2)  # scale: 50% diverged → 1.0

            func_names = [d[1] for d in divergences]
            first_pr = divergences[0][0]
            first_old = divergences[0][2]
            first_new = divergences[0][3]

            severity = Severity.HIGH if score >= 0.6 else Severity.MEDIUM

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity,
                    score=round(score, 3),
                    title=(
                        f"Exception contract drift in {module_key}/ "
                        f"({len(divergences)} function(s))"
                    ),
                    description=(
                        f"In module '{module_key}/', {len(divergences)} public "
                        f"function(s) changed their exception profile while "
                        f"keeping a stable signature: {', '.join(func_names[:5])}. "
                        f"Example: {func_names[0]}() — "
                        f"raises {first_old.get('raise_types', [])} -> "
                        f"{first_new.get('raise_types', [])}, "
                        f"catches {first_old.get('handler_types', [])} -> "
                        f"{first_new.get('handler_types', [])}."
                    ),
                    file_path=first_pr.file_path,
                    start_line=None,
                    end_line=None,
                    related_files=[
                        d[0].file_path for d in divergences[1:]
                    ],
                    fix=(
                        f"Review exception handling changes in "
                        f"{', '.join(func_names[:3])}. If the change is "
                        f"intentional, update callers and documentation. "
                        f"If accidental, restore the original exception contract."
                    ),
                    metadata={
                        "diverged_functions": func_names,
                        "divergence_count": len(divergences),
                        "module_function_count": len(all_checked),
                        "comparison_ref": ref,
                    },
                )
            )

        return findings
