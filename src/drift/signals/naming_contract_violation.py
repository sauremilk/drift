"""Signal 11: Naming Contract Violation (NBV).

Detects functions whose name implies a behaviour contract that the
AST does not fulfil — e.g. ``validate_*`` without a raise/return-False
path, ``is_*`` without a bool return type.

This is a proxy for *intention drift* (EPISTEMICS §2): when a
function's name promises one thing and its body delivers another,
the declared intention and the implementation have diverged.
"""

from __future__ import annotations

import ast
import re
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    FunctionInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals._utils import (
    _SUPPORTED_LANGUAGES,
    _TS_LANGUAGES,
    is_library_finding_path,
    is_likely_library_repo,
    is_test_file,
    ts_node_text,
    ts_parse_source,
    ts_walk,
)
from drift.signals.base import BaseSignal, register_signal


def _resolve_source_path(file_path: Path, repo_path: Path | None) -> Path:
    """Resolve a potentially relative file_path using the repo root."""
    if repo_path and not file_path.is_absolute():
        return repo_path / file_path
    return file_path

# ── Naming rules ──────────────────────────────────────────────────
# Each rule: (prefix_set, description, checker_function_name)

_RULES: list[tuple[frozenset[str], str, str]] = [
    (
        frozenset({"validate_", "check_"}),
        "validate_*/check_* expects at least one raise or return False/None",
        "_has_rejection_path",
    ),
    (
        frozenset({"ensure_"}),
        "ensure_* expects at least one raise statement",
        "_has_raise",
    ),
    (
        frozenset({"get_or_create_"}),
        "get_or_create_* expects a creation path after a conditional",
        "_has_create_path",
    ),
    (
        frozenset({"is_", "has_"}),
        "is_*/has_* expects bool return type",
        "_has_bool_return",
    ),
    (
        frozenset({"try_"}),
        "try_* expects a try/except block",
        "_has_try_except",
    ),
]


def _bare_name(fn_name: str) -> str:
    """Strip class prefix: 'ClassName.method' -> 'method'."""
    return fn_name.rsplit(".", 1)[-1]


# ── AST checkers ──────────────────────────────────────────────────


def _has_rejection_path(tree: ast.Module) -> bool:
    """Return True if the function body contains raise or return False/None."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Return) and node.value is not None:
            # return False
            if isinstance(node.value, ast.Constant) and node.value.value is False:
                return True
            # return None
            if isinstance(node.value, ast.Constant) and node.value.value is None:
                return True
    return False


def _has_raise(tree: ast.Module) -> bool:
    """Return True if the function body contains at least one raise."""
    return any(isinstance(node, ast.Raise) for node in ast.walk(tree))


def _has_create_path(tree: ast.Module) -> bool:
    """Return True if there is an assignment/call after a conditional (heuristic)."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        has_conditional = False
        for stmt in node.body:
            if isinstance(stmt, ast.If | ast.Try):
                has_conditional = True
            elif has_conditional and isinstance(stmt, ast.Assign | ast.Return):
                return True
            # Also: if/else with assignment in else branch
            if isinstance(stmt, ast.If) and stmt.orelse:
                for s in stmt.orelse:
                    if isinstance(s, ast.Assign | ast.Return | ast.Expr):
                        return True
        # Check inside if bodies for creation patterns
        for child in ast.walk(node):
            if isinstance(child, ast.If) and child.orelse:
                return True  # has branching → plausible get-or-create
    return False


def _is_bool_like_return_type(return_type: str | None) -> bool:
    """Return True for bool-like annotations, including async TS wrappers.

    Accepted examples:
    - bool, builtins.bool, boolean
    - Promise<boolean>, PromiseLike<boolean>, Observable<boolean>
    - nested wrappers like Promise<PromiseLike<boolean>>
    """
    if not return_type:
        return False

    # TS type predicates (for example: "x is BrowserNode") are bool-compatible.
    compact = " ".join(return_type.strip().split())
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s+is\s+.+$", compact):
        return True

    normalized = "".join(return_type.strip().split())
    lowered = normalized.lower()
    if lowered in {"bool", "builtins.bool", "boolean"}:
        return True

    # TS assertion signatures (for example: "asserts x is AuthenticatedContext")
    # are valid ensure-style contracts.
    if lowered.startswith("asserts"):
        return True

    wrapper_names = {"promise", "promiselike", "observable"}
    current = lowered
    max_unwrap = 6
    for _ in range(max_unwrap):
        if "<" not in current or not current.endswith(">"):
            break
        wrapper, inner = current.split("<", 1)
        wrapper_name = wrapper.rsplit(".", 1)[-1]
        if wrapper_name not in wrapper_names:
            break
        current = inner[:-1].strip()
        if current in {"bool", "builtins.bool", "boolean"}:
            return True

    return False


def _has_bool_return(tree: ast.Module, fn_info: FunctionInfo) -> bool:
    """Return True if function has bool return type or only returns bool literals."""
    # Check annotation first
    if _is_bool_like_return_type(fn_info.return_type):
        return True

    # Check actual return statements — all must be bool constants
    returns: list[ast.Return] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and child.value is not None:
                    returns.append(child)

    if not returns:
        return False  # no explicit returns → not bool

    return all(
        isinstance(r.value, ast.Constant) and isinstance(r.value.value, bool) for r in returns
    )


def _has_try_except(tree: ast.Module) -> bool:
    """Return True if the function body contains a try/except block."""
    return any(isinstance(node, ast.Try) for node in ast.walk(tree))


def _is_utility_context(file_path: Path) -> bool:
    """Return True when a file path suggests utility/helper intent."""
    utility_tokens = {
        "utils",
        "util",
        "helpers",
        "helper",
        "common",
    }
    parts = {p.lower() for p in file_path.parts}
    stem = file_path.stem.lower()
    return bool(parts.intersection(utility_tokens)) or stem in utility_tokens


def _looks_like_comparison_semantics(tree: ast.Module, source: str) -> bool:
    """Return True if source/body looks like comparison/checking utility code."""
    if any(isinstance(node, ast.Compare) for node in ast.walk(tree)):
        return True
    return bool(re.search(r"\bis\s+None\b|\bisinstance\s*\(", source))


# Map checker names to functions (typed for mypy-safe dispatch)
_CHECKERS_SIMPLE: dict[str, Callable[[ast.Module], bool]] = {
    "_has_rejection_path": _has_rejection_path,
    "_has_raise": _has_raise,
    "_has_create_path": _has_create_path,
    "_has_try_except": _has_try_except,
}

_CHECKERS_WITH_FN_INFO: dict[str, Callable[[ast.Module, FunctionInfo], bool]] = {
    "_has_bool_return": _has_bool_return,
}


# ── TypeScript AST checkers (tree-sitter) ─────────────────────────


def _ts_has_rejection_path(root: Any, src: bytes, fn_info: FunctionInfo) -> bool:
    """Return True if TS/JS validation code exposes a rejection path.

    Besides throw and ``return false|null|undefined``, this accepts common
    validation idioms like returning error strings, structured error objects,
    bare early ``return;`` and explicit Promise rejection calls.
    """
    def _looks_like_rejection_object(expr_text: str) -> bool:
        compact = " ".join(expr_text.split()).lower()
        if not compact.startswith("{"):
            return False
        if re.search(r"\b(valid|ok)\s*:\s*false\b", compact):
            return True
        return bool(re.search(r"\b(error|errors|message|reason)\s*:", compact))

    normalized_return_type = (fn_info.return_type or "").replace(" ", "").lower()
    allows_error_string = (
        "string" in normalized_return_type
        and ("null" in normalized_return_type or "undefined" in normalized_return_type)
    )
    allows_bare_return = (
        not normalized_return_type
        or "void" in normalized_return_type
        or "undefined" in normalized_return_type
        or "null" in normalized_return_type
    )

    for node in ts_walk(root):
        if node.type == "throw_statement":
            return True

        if node.type == "return_statement":
            value_children = [c for c in node.children if c.type not in ("return", ";")]
            if not value_children:
                if allows_bare_return:
                    # In validate/check-style TS functions, bare early return is
                    # commonly used to signal rejection/failure.
                    return True
                # Bare return in non-void contracts is not a valid rejection path.
                continue

            value = value_children[0]
            if value.type in ("false", "null", "undefined"):
                return True
            if value.type in ("string", "template_string") and allows_error_string:
                return True

            value_text = ts_node_text(value, src)
            if _looks_like_rejection_object(value_text):
                return True

        if node.type == "call_expression":
            func = node.child_by_field_name("function")
            if func is None:
                continue
            func_text = ts_node_text(func, src).replace(" ", "").lower()
            if func_text in {"reject", "promise.reject"} or func_text.endswith(".reject"):
                    return True
    return False


def _ts_has_raise(root: Any, src: bytes) -> bool:
    """Return True if the TS body contains at least one throw statement."""
    return any(n.type == "throw_statement" for n in ts_walk(root))


def _ts_has_return_value(root: Any, src: bytes) -> bool:
    """Return True if TS function has a return statement with a value."""
    for node in ts_walk(root):
        if node.type != "return_statement":
            continue
        value_children = [c for c in node.children if c.type not in ("return", ";")]
        if value_children:
            return True
    return False


def _ts_has_idempotent_side_effect(root: Any, src: bytes) -> bool:
    """Return True for TS ensure-style side effects that establish state.

    This accepts common TS/JS ensure-by-creation patterns (for example
    property/index assignment, nullish assignment on object slots, and
    mutating API calls like ``mkdirSync``/``set``/``push``/``register``).
    """

    mutating_call_markers = (
        "mkdir",
        "mkdirsync",
        "set",
        "add",
        "push",
        "unshift",
        "splice",
        "assign",
        "defineproperty",
        "writefile",
        "writefilesync",
        "appendfile",
        "appendfilesync",
        "register",
        "initialize",
        "init",
        "create",
        "attachshadow",
        "load",
        "configure",
        "start",
    )

    for node in ts_walk(root):
        if node.type == "assignment_expression":
            left = node.child_by_field_name("left")
            if left is not None:
                left_text = ts_node_text(left, src)
                # Local rebind (e.g. `next = {}`) is not enough; we require
                # stateful targets like `obj.key` or `obj[key]`.
                if "." in left_text or "[" in left_text:
                    return True

            assignment_text = ts_node_text(node, src)
            if "??=" in assignment_text or "||=" in assignment_text or "&&=" in assignment_text:
                return True

        if node.type == "update_expression":
            arg = node.child_by_field_name("argument")
            if arg is not None:
                arg_text = ts_node_text(arg, src)
                if "." in arg_text or "[" in arg_text:
                    return True

        if node.type == "call_expression":
            func = node.child_by_field_name("function")
            if func is None:
                continue
            func_text = ts_node_text(func, src).lower()
            if any(marker in func_text for marker in mutating_call_markers):
                return True

    return False


def _ts_has_ensure_contract(root: Any, src: bytes) -> bool:
    """TS/JS ensure_* allows throw, value-return, or idempotent init side-effects."""
    return (
        _ts_has_raise(root, src)
        or _ts_has_return_value(root, src)
        or _ts_has_idempotent_side_effect(root, src)
    )


def _ts_has_create_path(root: Any, src: bytes) -> bool:
    """Return True if there is branching (if/else) — heuristic for get-or-create."""
    for node in ts_walk(root):
        if node.type == "if_statement" and any(c.type == "else_clause" for c in node.children):
            return True
    return False


def _ts_has_bool_return(root: Any, src: bytes, fn_info: FunctionInfo) -> bool:
    """Return True if TS function has boolean return type or only returns booleans."""
    def _unwrap_expression(node: Any) -> Any:
        """Unwrap wrapper nodes around an expression for robust type checks."""
        current = node
        while current is not None:
            if current.type in {
                "parenthesized_expression",
                "as_expression",
                "type_assertion",
                "satisfies_expression",
                "non_null_expression",
            }:
                expr = current.child_by_field_name("expression")
                if expr is None:
                    # Fallback for nodes without a named expression field.
                    children = [c for c in current.children if c.type not in {"(", ")", "as", "!"}]
                    expr = children[0] if children else None
                if expr is None:
                    break
                current = expr
                continue
            break
        return current

    def _classify_ts_bool_expression(node: Any) -> str:
        """Classify TS expression as bool-like, non-bool, or unknown."""
        n = _unwrap_expression(node)
        if n is None:
            return "unknown"

        if n.type in {"true", "false"}:
            return "bool"

        if n.type in {
            "string",
            "template_string",
            "number",
            "bigint",
            "object",
            "array",
            "new_expression",
            "function",
            "arrow_function",
            "class",
        }:
            return "non_bool"

        if n.type == "unary_expression":
            txt = ts_node_text(n, src).lstrip()
            # !x and !!x are always boolean in JS/TS.
            return "bool" if txt.startswith("!") else "unknown"

        if n.type == "binary_expression":
            expr_text = ts_node_text(n, src)
            comparison_ops = ("===", "!==", "==", "!=", "<=", ">=", "<", ">", "instanceof")
            if any(op in expr_text for op in comparison_ops):
                return "bool"
            if re.search(r"\bin\b", expr_text):
                return "bool"
            return "unknown"

        if n.type == "call_expression":
            callee = n.child_by_field_name("function")
            if callee is not None:
                callee_text = ts_node_text(callee, src).strip()
                if callee_text == "Boolean":
                    return "bool"
            # Unknown call result: in TS this is often inferred boolean for
            # predicate helpers; treat as unknown, not non-bool.
            return "unknown"

        if n.type in {
            "identifier",
            "member_expression",
            "subscript_expression",
            "await_expression",
        }:
            return "unknown"

        return "unknown"

    if _is_bool_like_return_type(fn_info.return_type):
        return True

    # Explicit TS return annotations take precedence over body heuristics.
    if (fn_info.return_type or "").strip():
        return False

    returns = [n for n in ts_walk(root) if n.type == "return_statement"]
    if not returns:
        return False

    # Without explicit type annotations, be conservative for TS predicates:
    # only fail when there is clear non-boolean evidence in returns.
    for ret in returns:
        value_children = [c for c in ret.children if c.type not in ("return", ";")]
        if not value_children:
            return False  # bare return
        classification = _classify_ts_bool_expression(value_children[0])
        if classification == "non_bool":
            return False
    return True


def _ts_is_assertion_return_contract(fn_info: FunctionInfo) -> bool:
    """Return True if TS return type is an assertion signature."""
    return_type = " ".join((fn_info.return_type or "").strip().split()).lower()
    return bool(return_type) and return_type.startswith("asserts ")


def _ts_has_try_except(root: Any, src: bytes) -> bool:
    """Return True for TS try_* contracts with graceful-failure semantics.

    Besides explicit ``try { ... } catch { ... }``, this accepts common
    TS/JS attempt-style patterns such as Promise ``.catch(...)``, optional
    chaining with fallback, nullish-coalescing fallback, and conditional
    early fallback returns.
    """
    source_text = src.decode("utf-8", errors="ignore")

    def _is_fallback_literal(expr_text: str) -> bool:
        normalized = " ".join(expr_text.strip().split()).lower()
        return normalized in {"", "undefined", "null", "false"}

    def _return_expr(ret_node: Any) -> str:
        value_children = [c for c in ret_node.children if c.type not in ("return", ";")]
        if not value_children:
            return ""
        return ts_node_text(value_children[0], src)

    # 1) Canonical try/catch.
    if any(n.type == "try_statement" for n in ts_walk(root)):
        return True

    # 2) Promise-style handling: foo().catch(...)
    if re.search(r"\.catch\s*\(", source_text):
        return True

    returns = [n for n in ts_walk(root) if n.type == "return_statement"]

    # 3) Optional chaining + fallback and nullish fallback expressions.
    for ret in returns:
        expr_text = _return_expr(ret)
        compact = "".join(expr_text.split())
        if "?." in compact and ("??" in compact or "||" in compact):
            return True
        if "??" in compact and not compact.endswith("??undefined"):
            return True

    # 4) Conditional early return with explicit fallback value.
    if len(returns) >= 2:
        for node in ts_walk(root):
            if node.type != "if_statement":
                continue
            for child in ts_walk(node):
                if child.type != "return_statement":
                    continue
                if _is_fallback_literal(_return_expr(child)):
                    return True

    return False


def _ts_has_nullable_return_contract(fn_info: FunctionInfo) -> bool:
    """Return True for TS/JS try_* nullable getter return signatures.

    In TS/JS, ``try*`` is frequently used for best-effort getters that
    communicate failure via ``null``/``undefined`` unions instead of exceptions.
    """
    return_type = (fn_info.return_type or "").replace(" ", "").lower()
    if not return_type:
        return False
    return "|undefined" in return_type or "|null" in return_type


def _read_function_source(
    file_path: Path,
    fn: FunctionInfo,
    repo_path: Path | None = None,
) -> str | None:
    """Read source lines for a single function."""
    try:
        target = file_path
        if repo_path and not file_path.is_absolute():
            target = repo_path / file_path
        lines = target.read_text(encoding="utf-8").splitlines()
        start = fn.start_line - 1
        end = fn.end_line
        return "\n".join(lines[start:end])
    except (OSError, UnicodeDecodeError, AttributeError):
        return None


def _snake_to_camel_prefix(snake: str) -> str:
    """Convert ``'get_or_create_'`` to ``'getOrCreate'``."""
    parts = snake.rstrip("_").split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _match_rule(
    bare: str,
) -> tuple[str, str, str] | None:
    """Return ``(matched_prefix, description, checker_name)`` or *None*.

    Matches both snake_case (``validate_email``) and camelCase
    (``validateEmail``) naming conventions.
    """
    for prefixes, description, checker_name in _RULES:
        # snake_case match
        for p in prefixes:
            if bare.startswith(p):
                return p, description, checker_name
        # camelCase match: "validateFoo" matches "validate_" rule
        for p in prefixes:
            camel = _snake_to_camel_prefix(p)
            if bare.startswith(camel) and len(bare) > len(camel) and bare[len(camel)].isupper():
                return p, description, checker_name
    return None


def _contract_suggestion(matched_prefix: str, fn_name: str) -> str:
    """Return a concrete next-step suggestion for one naming rule prefix."""
    if matched_prefix in {"validate_", "check_"}:
        return (
            "implement a rejection path (raise or return False/None), "
            "or rename the function to match non-validating behavior"
        )
    if matched_prefix == "ensure_":
        return "add at least one raise path that enforces the ensured precondition"
    if matched_prefix == "get_or_create_":
        return "add an explicit conditional create path (lookup, then create in missing branch)"
    if matched_prefix in {"is_", "has_"}:
        return "return a bool-compatible result (annotation and runtime returns)"
    if matched_prefix == "try_":
        return "wrap risky operations in try/except and return a clear fallback"
    return (
        f"implement the behavior implied by '{matched_prefix}' for '{fn_name}()', "
        "or rename the function"
    )


_TS_CHECKERS: dict[str, Callable[..., bool]] = {
    "_has_rejection_path": lambda root, src, fn: _ts_has_rejection_path(root, src, fn),
    "_has_raise": lambda root, src, _fn: _ts_has_raise(root, src),
    "_has_create_path": lambda root, src, _fn: _ts_has_create_path(root, src),
    "_has_bool_return": lambda root, src, fn: _ts_has_bool_return(root, src, fn),
    "_has_try_except": lambda root, src, _fn: _ts_has_try_except(root, src),
}


def _ts_check_rule(
    source: str,
    language: str,
    fn: FunctionInfo,
    checker_name: str,
    matched_prefix: str,
) -> bool:
    """Run a naming-contract checker against TS/JS source via tree-sitter."""
    result = ts_parse_source(source, language)

    # Method bodies extracted without class context can parse into partial trees
    # that miss return/throw nodes. Re-parse methods in a synthetic class wrapper.
    if "." in fn.name:
        wrapped_source = "class __DriftMethodWrapper__ {\n"
        wrapped_source += textwrap.indent(source, "  ")
        wrapped_source += "\n}\n"
        wrapped_result = ts_parse_source(wrapped_source, language)
        if wrapped_result is not None:
            result = wrapped_result

    if result is None:
        return True  # benefit of doubt
    root, src = result

    # TS/JS convention: ensure_* often means get-or-create/upsert.
    if matched_prefix == "ensure_":
        if _ts_is_assertion_return_contract(fn):
            return True
        return _ts_has_ensure_contract(root, src)

    # TS/JS convention: try_* can be a nullable getter contract.
    if matched_prefix == "try_" and _ts_has_nullable_return_contract(fn):
        return True

    checker = _TS_CHECKERS.get(checker_name)
    if checker is None:
        return True
    return checker(root, src, fn)


@register_signal
class NamingContractViolationSignal(BaseSignal):
    """Detect functions whose name implies a contract the body does not fulfil."""

    incremental_scope = "file_local"

    @property
    def signal_type(self) -> SignalType:
        return SignalType.NAMING_CONTRACT_VIOLATION

    @property
    def name(self) -> str:
        return "Naming Contract Violation"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        min_loc = config.thresholds.nbv_min_function_loc
        findings: list[Finding] = []
        library_repo = is_likely_library_repo(parse_results)

        for pr in parse_results:
            if pr.language not in _SUPPORTED_LANGUAGES:
                continue
            if is_test_file(pr.file_path):
                continue

            is_ts = pr.language in _TS_LANGUAGES

            for fn in pr.functions:
                if fn.loc < min_loc:
                    continue

                bare = _bare_name(fn.name)
                # Skip private functions
                if bare.startswith("_"):
                    continue

                rule = _match_rule(bare)
                if rule is None:
                    continue

                matched_prefix, description, checker_name = rule
                source = _read_function_source(pr.file_path, fn, self._repo_path)
                if source is None:
                    continue

                if is_ts:
                    satisfied = _ts_check_rule(
                        source,
                        pr.language,
                        fn,
                        checker_name,
                        matched_prefix,
                    )
                else:
                    try:
                        tree = ast.parse(textwrap.dedent(source))
                    except SyntaxError:
                        continue

                    # _has_bool_return needs fn_info for annotation check
                    if checker_name == "_has_bool_return":
                        checker_with_fn_info = _CHECKERS_WITH_FN_INFO[checker_name]
                        satisfied = checker_with_fn_info(tree, fn)
                    else:
                        checker_simple = _CHECKERS_SIMPLE[checker_name]
                        satisfied = checker_simple(tree)

                    # NBV issue #165: treat try_* "attempt" helpers conservatively.
                    if (
                        not satisfied
                        and matched_prefix == "try_"
                        and (
                            _looks_like_comparison_semantics(tree, source)
                            or _is_utility_context(pr.file_path)
                        )
                    ):
                        satisfied = True

                if satisfied:
                    continue

                # Violation found
                score = 0.6
                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=Severity.MEDIUM,
                        score=score,
                        title=f"Naming contract violation: {fn.name}()",
                        description=(
                            f"Function '{fn.name}' has prefix '{matched_prefix}' "
                            f"but does not satisfy the expected contract: "
                            f"{description}."
                        ),
                        file_path=pr.file_path,
                        start_line=fn.start_line,
                        end_line=fn.end_line,
                        fix=(
                            f"'{fn.name}()' at {pr.file_path.as_posix()}:{fn.start_line} "
                            f"does not satisfy '{matched_prefix}' naming contract. "
                            f"Suggestion: {_contract_suggestion(matched_prefix, fn.name)}."
                        ),
                        metadata={
                            "function_name": fn.name,
                            "prefix_rule": matched_prefix,
                            "expected_contract": description,
                            "checker": checker_name,
                            "library_context_candidate": library_repo
                            and is_library_finding_path(pr.file_path),
                        },
                    )
                )

        # ── TS-specific naming convention checks ──────────────────────

        # Only keep architecture-relevant enum casing consistency.
        # Generic parameter naming style and interface I-prefix style are
        # intentionally not treated as drift findings (Issue #219).

        # 1. Enum member casing consistency (per-file)
        for pr in parse_results:
            if pr.language not in _TS_LANGUAGES:
                continue
            if is_test_file(pr.file_path):
                continue

            try:
                source_text = _resolve_source_path(
                    pr.file_path, self.repo_path
                ).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            parsed = ts_parse_source(source_text, pr.language)
            if parsed is None:
                continue
            root, src_bytes = parsed

            for node in ts_walk(root):
                if node.type != "enum_declaration":
                    continue

                enum_name_node = node.child_by_field_name("name")
                enum_name = (
                    ts_node_text(enum_name_node, src_bytes) if enum_name_node else "anonymous"
                )

                members: list[str] = []
                for child in ts_walk(node):
                    if child.type == "enum_assignment":
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            members.append(ts_node_text(name_node, src_bytes))
                    elif (
                        child.type == "property_identifier"
                        and child.parent
                        and child.parent.type == "enum_body"
                    ):
                        members.append(ts_node_text(child, src_bytes))

                if len(members) < 2:
                    continue

                screaming = sum(1 for m in members if re.match(r"^[A-Z][A-Z0-9_]+$", m))
                pascal = sum(1 for m in members if re.match(r"^[A-Z][a-z]", m) and "_" not in m)

                if screaming > 0 and pascal > 0:
                    # Mixed casing
                    dominant = "SCREAMING_SNAKE" if screaming >= pascal else "PascalCase"
                    findings.append(
                        Finding(
                            signal_type=self.signal_type,
                            severity=Severity.LOW,
                            score=0.3,
                            title=f"Enum '{enum_name}' has mixed member casing",
                            description=(
                                f"Enum '{enum_name}' in {pr.file_path.as_posix()} "
                                f"mixes {screaming} SCREAMING_SNAKE and {pascal} PascalCase "
                                f"members. Dominant style: {dominant}."
                            ),
                            file_path=pr.file_path,
                            start_line=node.start_point[0] + 1,
                            fix=(f"Standardise enum '{enum_name}' member casing to {dominant}."),
                            metadata={
                                "enum_name": enum_name,
                                "screaming": screaming,
                                "pascal": pascal,
                            },
                        )
                    )

        return findings
