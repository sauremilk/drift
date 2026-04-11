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


def _has_bool_return(tree: ast.Module, fn_info: FunctionInfo) -> bool:
    """Return True if function has bool return type or only returns bool literals."""
    # Check annotation first
    if fn_info.return_type:
        rt = fn_info.return_type.lower().strip()
        if rt in ("bool", "builtins.bool"):
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


def _ts_has_rejection_path(root: Any, src: bytes) -> bool:
    """Return True if the TS body contains throw or return false/null."""
    for node in ts_walk(root):
        if node.type == "throw_statement":
            return True
        if node.type == "return_statement":
            for child in node.children:
                if child.type in ("false", "null"):
                    return True
    return False


def _ts_has_raise(root: Any, src: bytes) -> bool:
    """Return True if the TS body contains at least one throw statement."""
    return any(n.type == "throw_statement" for n in ts_walk(root))


def _ts_has_create_path(root: Any, src: bytes) -> bool:
    """Return True if there is branching (if/else) — heuristic for get-or-create."""
    for node in ts_walk(root):
        if node.type == "if_statement" and any(c.type == "else_clause" for c in node.children):
            return True
    return False


def _ts_has_bool_return(root: Any, src: bytes, fn_info: FunctionInfo) -> bool:
    """Return True if TS function has boolean return type or only returns booleans."""
    if fn_info.return_type and fn_info.return_type.lower().strip() == "boolean":
        return True

    returns = [n for n in ts_walk(root) if n.type == "return_statement"]
    if not returns:
        return False

    for ret in returns:
        value_children = [c for c in ret.children if c.type not in ("return", ";")]
        if not value_children:
            return False  # bare return
        if value_children[0].type not in ("true", "false"):
            return False
    return True


def _ts_has_try_except(root: Any, src: bytes) -> bool:
    """Return True if the TS body contains a try statement."""
    return any(n.type == "try_statement" for n in ts_walk(root))


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
    "_has_rejection_path": lambda root, src, _fn: _ts_has_rejection_path(root, src),
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
) -> bool:
    """Run a naming-contract checker against TS/JS source via tree-sitter."""
    result = ts_parse_source(source, language)
    if result is None:
        return True  # benefit of doubt
    root, src = result
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
                    satisfied = _ts_check_rule(source, pr.language, fn, checker_name)
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

        # 1. Interface I-Prefix consistency (cross-file)
        iface_names_2: list[tuple[str, Path, int]] = []
        for pr in parse_results:
            if pr.language not in _TS_LANGUAGES:
                continue
            if is_test_file(pr.file_path):
                continue
            for cls in pr.classes:
                if cls.is_interface:
                    iface_names_2.append((cls.name, cls.file_path, cls.start_line))

        if len(iface_names_2) >= 4:
            i_prefixed = [
                n
                for n, _, _ in iface_names_2
                if n.startswith("I") and len(n) > 1 and n[1].isupper()
            ]
            prefixed_ratio_text = f"{len(i_prefixed)}/{len(iface_names_2)}"
            ratio = len(i_prefixed) / len(iface_names_2)

            if ratio > 0.5:
                # I-prefix is dominant → flag outliers without I-prefix
                for iname, fpath, line in iface_names_2:
                    if not (iname.startswith("I") and len(iname) > 1 and iname[1].isupper()):
                        findings.append(
                            Finding(
                                signal_type=self.signal_type,
                                severity=Severity.LOW,
                                score=0.3,
                                title=f"Interface '{iname}' missing I-prefix",
                                description=(
                                    f"Interface '{iname}' at {fpath.as_posix()}:{line} "
                                    f"does not use I-prefix, but {prefixed_ratio_text} "
                                    f"interfaces in the codebase do. "
                                    f"Inconsistent naming reduces discoverability."
                                ),
                                file_path=fpath,
                                start_line=line,
                                fix=(
                                    f"Rename '{iname}' to 'I{iname}' "
                                    "to match the dominant convention."
                                ),
                                metadata={"convention": "I-prefix", "ratio": round(ratio, 2)},
                            )
                        )
            elif ratio < 0.2:
                # No-prefix is dominant → flag outliers with I-prefix
                for iname, fpath, line in iface_names_2:
                    if iname.startswith("I") and len(iname) > 1 and iname[1].isupper():
                        findings.append(
                            Finding(
                                signal_type=self.signal_type,
                                severity=Severity.LOW,
                                score=0.3,
                                title=f"Interface '{iname}' uses I-prefix against convention",
                                description=(
                                    f"Interface '{iname}' at {fpath.as_posix()}:{line} "
                                    f"uses I-prefix, but only {prefixed_ratio_text} "
                                    f"interfaces do. Inconsistent naming reduces readability."
                                ),
                                file_path=fpath,
                                start_line=line,
                                fix=(
                                    f"Rename '{iname}' to '{iname[1:]}' "
                                    "to match the dominant convention."
                                ),
                                metadata={"convention": "no-prefix", "ratio": round(ratio, 2)},
                            )
                        )

        # 2. Enum member casing consistency (per-file)
        for pr in parse_results:
            if pr.language not in _TS_LANGUAGES:
                continue
            if is_test_file(pr.file_path):
                continue

            try:
                source_text = pr.file_path.read_text(encoding="utf-8", errors="replace")
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

        # 3. Generic parameter naming mix (per-file)
        for pr in parse_results:
            if pr.language not in _TS_LANGUAGES:
                continue
            if is_test_file(pr.file_path):
                continue

            try:
                source_text = pr.file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            parsed = ts_parse_source(source_text, pr.language)
            if parsed is None:
                continue
            root, src_bytes = parsed

            single_letter: list[str] = []
            verbose: list[str] = []

            for node in ts_walk(root):
                if node.type == "type_parameter":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        pname = ts_node_text(name_node, src_bytes)
                        if len(pname) == 1 and pname.isupper():
                            single_letter.append(pname)
                        elif len(pname) > 1:
                            verbose.append(pname)

            if single_letter and verbose:
                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=Severity.LOW,
                        score=0.3,
                        title=f"Mixed generic parameter naming in {pr.file_path.name}",
                        description=(
                            f"{pr.file_path.as_posix()} mixes single-letter generics "
                            f"({', '.join(sorted(set(single_letter)))}) with verbose names "
                            f"({', '.join(sorted(set(verbose)))}). "
                            f"Pick one convention per codebase."
                        ),
                        file_path=pr.file_path,
                        start_line=1,
                        fix=(
                            "Standardise generic parameter names "
                            "to either single-letter or descriptive style."
                        ),
                        metadata={
                            "single_letter": sorted(set(single_letter)),
                            "verbose": sorted(set(verbose)),
                        },
                    )
                )

        # ── TS-specific naming convention checks ──────────────────────

        # 1. Interface I-Prefix consistency (cross-file)
        iface_names: list[tuple[str, Path, int]] = []
        for pr in parse_results:
            if pr.language not in _TS_LANGUAGES:
                continue
            if is_test_file(pr.file_path):
                continue
            for cls in pr.classes:
                if cls.is_interface:
                    iface_names.append((cls.name, cls.file_path, cls.start_line))

        if len(iface_names) >= 4:
            i_prefixed = [
                n for n, _, _ in iface_names if n.startswith("I") and len(n) > 1 and n[1].isupper()
            ]
            prefixed_ratio_text = f"{len(i_prefixed)}/{len(iface_names)}"
            ratio = len(i_prefixed) / len(iface_names)

            if ratio > 0.5:
                # I-prefix is dominant → flag outliers without I-prefix
                for iname, fpath, line in iface_names_2:
                    if not (iname.startswith("I") and len(iname) > 1 and iname[1].isupper()):
                        findings.append(
                            Finding(
                                signal_type=self.signal_type,
                                severity=Severity.LOW,
                                score=0.3,
                                title=f"Interface '{iname}' missing I-prefix",
                                description=(
                                    f"Interface '{iname}' at {fpath.as_posix()}:{line} "
                                    f"does not use I-prefix, but {prefixed_ratio_text} "
                                    f"interfaces in the codebase do. "
                                    f"Inconsistent naming reduces discoverability."
                                ),
                                file_path=fpath,
                                start_line=line,
                                fix=(
                                    f"Rename '{iname}' to 'I{iname}' "
                                    "to match the dominant convention."
                                ),
                                metadata={"convention": "I-prefix", "ratio": round(ratio, 2)},
                            )
                        )
            elif ratio < 0.2:
                # No-prefix is dominant → flag outliers with I-prefix
                for iname, fpath, line in iface_names:
                    if iname.startswith("I") and len(iname) > 1 and iname[1].isupper():
                        findings.append(
                            Finding(
                                signal_type=self.signal_type,
                                severity=Severity.LOW,
                                score=0.3,
                                title=f"Interface '{iname}' uses I-prefix against convention",
                                description=(
                                    f"Interface '{iname}' at {fpath.as_posix()}:{line} "
                                    f"uses I-prefix, but only {len(i_prefixed)}/{len(iface_names)} "
                                    f"interfaces do. Inconsistent naming reduces readability."
                                ),
                                file_path=fpath,
                                start_line=line,
                                fix=(
                                    f"Rename '{iname}' to '{iname[1:]}' "
                                    "to match the dominant convention."
                                ),
                                metadata={"convention": "no-prefix", "ratio": round(ratio, 2)},
                            )
                        )

        # 2. Enum member casing consistency (per-file)
        for pr in parse_results:
            if pr.language not in _TS_LANGUAGES:
                continue
            if is_test_file(pr.file_path):
                continue

            try:
                source_text = pr.file_path.read_text(encoding="utf-8", errors="replace")
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

                members_2: list[str] = []
                for child in ts_walk(node):
                    if child.type == "enum_assignment":
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            members_2.append(ts_node_text(name_node, src_bytes))
                    elif (
                        child.type == "property_identifier"
                        and child.parent
                        and child.parent.type == "enum_body"
                    ):
                        members_2.append(ts_node_text(child, src_bytes))

                if len(members_2) < 2:
                    continue

                screaming = sum(1 for m in members_2 if re.match(r"^[A-Z][A-Z0-9_]+$", m))
                pascal = sum(1 for m in members_2 if re.match(r"^[A-Z][a-z]", m) and "_" not in m)

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

        # 3. Generic parameter naming mix (per-file)
        for pr in parse_results:
            if pr.language not in _TS_LANGUAGES:
                continue
            if is_test_file(pr.file_path):
                continue

            try:
                source_text = pr.file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            parsed = ts_parse_source(source_text, pr.language)
            if parsed is None:
                continue
            root, src_bytes = parsed

            single_letter_2: list[str] = []
            verbose_2: list[str] = []

            for node in ts_walk(root):
                if node.type == "type_parameter":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        pname = ts_node_text(name_node, src_bytes)
                        if len(pname) == 1 and pname.isupper():
                            single_letter_2.append(pname)
                        elif len(pname) > 1:
                            verbose_2.append(pname)

            if single_letter_2 and verbose_2:
                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=Severity.LOW,
                        score=0.3,
                        title=f"Mixed generic parameter naming in {pr.file_path.name}",
                        description=(
                            f"{pr.file_path.as_posix()} mixes single-letter generics "
                            f"({', '.join(sorted(set(single_letter_2)))}) with verbose names "
                            f"({', '.join(sorted(set(verbose_2)))}). "
                            f"Pick one convention per codebase."
                        ),
                        file_path=pr.file_path,
                        start_line=1,
                        fix=(
                            "Standardise generic parameter names "
                            "to either single-letter or descriptive style."
                        ),
                        metadata={
                            "single_letter": sorted(set(single_letter_2)),
                            "verbose": sorted(set(verbose_2)),
                        },
                    )
                )

        return findings
