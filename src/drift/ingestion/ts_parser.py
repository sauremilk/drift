"""TypeScript/TSX parser using tree-sitter (optional dependency).

Extracts functions, classes, imports, and error-handling patterns from
TypeScript and TSX files — the same structural information that
ast_parser.py extracts for Python.

Requires: ``pip install -q drift-analyzer[typescript]`` (use -q for clean output)
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from drift.models import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    ParseResult,
    PatternCategory,
    PatternInstance,
)

logger = logging.getLogger("drift")

# ---------------------------------------------------------------------------
# tree-sitter availability check
# ---------------------------------------------------------------------------

_ts_available: bool | None = None


def tree_sitter_available() -> bool:
    """Return True if tree-sitter + TypeScript grammar are installed."""
    global _ts_available
    if _ts_available is not None:
        return _ts_available
    try:
        import tree_sitter  # noqa: F401
        import tree_sitter_typescript  # noqa: F401

        _ts_available = True
    except ImportError:
        _ts_available = False
    return _ts_available


# ---------------------------------------------------------------------------
# Lazy-initialised parsers (created once per process)
# ---------------------------------------------------------------------------

_parsers: dict[str, Any] = {}


def _get_parser(language: str) -> Any:
    """Return a tree-sitter Parser for the given language ('typescript' or 'tsx')."""
    if language in _parsers:
        return _parsers[language]

    import tree_sitter_typescript as tsts
    from tree_sitter import Language, Parser

    if language == "tsx":
        lang = Language(tsts.language_tsx())
    else:
        lang = Language(tsts.language_typescript())

    parser = Parser(lang)
    _parsers[language] = parser
    return parser


# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------


def _node_text(node: Any, source: bytes) -> str:
    """Extract the UTF-8 text of a tree-sitter node."""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _child_by_field(node: Any, name: str) -> Any | None:
    return node.child_by_field_name(name)


def _children_of_type(node: Any, *types: str) -> list[Any]:
    return [c for c in node.children if c.type in types]


def _walk(node: Any) -> list[Any]:
    """Depth-first walk of all descendants."""
    result = []
    stack = [node]
    while stack:
        n = stack.pop()
        result.append(n)
        stack.extend(reversed(n.children))
    return result


# ---------------------------------------------------------------------------
# AST n-gram computation (for Mutant Duplicate detection)
# ---------------------------------------------------------------------------

_NGRAM_N = 3


def _compute_ts_ast_ngrams(node: Any) -> list[list[str]]:
    """Extract n-grams of tree-sitter node types from a function node.

    Mirrors the Python ``_compute_ast_ngrams`` logic: names and literals are
    normalised away so that renaming variables does not affect the fingerprint.
    The result is stored in ``FunctionInfo.ast_fingerprint["ngrams"]``.
    """
    node_types: list[str] = []
    for child in _walk(node):
        # Normalise identifiers and literals to generic tokens
        if child.type in ("identifier", "property_identifier", "shorthand_property_identifier"):
            node_types.append("Identifier")
        elif child.type in ("string", "template_string", "number", "true", "false", "null"):
            node_types.append("Literal")
        else:
            node_types.append(child.type)

    if len(node_types) < _NGRAM_N:
        return [node_types] if node_types else []

    return [node_types[i : i + _NGRAM_N] for i in range(len(node_types) - _NGRAM_N + 1)]


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _extract_functions(
    root: Any,
    source: bytes,
    file_path: Path,
    language: str,
) -> list[FunctionInfo]:
    """Extract named functions and arrow-function assignments."""
    functions: list[FunctionInfo] = []

    for node in _walk(root):
        name: str | None = None
        func_node: Any | None = None
        is_method = False

        if node.type == "function_declaration":
            name_node = _child_by_field(node, "name")
            name = _node_text(name_node, source) if name_node else None
            func_node = node

        elif node.type == "method_definition":
            name_node = _child_by_field(node, "name")
            name = _node_text(name_node, source) if name_node else None
            func_node = node
            is_method = True

        elif node.type in ("lexical_declaration", "variable_declaration"):
            # const foo = (...) => { ... }
            for decl in _children_of_type(node, "variable_declarator"):
                name_nd = _child_by_field(decl, "name")
                value_nd = _child_by_field(decl, "value")
                if name_nd and value_nd and value_nd.type == "arrow_function":
                    name = _node_text(name_nd, source)
                    func_node = value_nd
                    break

        if name is None or func_node is None:
            continue

        # Params
        params_node = _child_by_field(func_node, "parameters")
        params: list[str] = []
        if params_node:
            for p in params_node.children:
                if p.type in (
                    "required_parameter",
                    "optional_parameter",
                    "rest_parameter",
                ):
                    pname = _child_by_field(p, "pattern") or _child_by_field(p, "name")
                    if pname:
                        params.append(_node_text(pname, source))
                elif p.type == "identifier":
                    params.append(_node_text(p, source))

        # Return type
        ret_node = _child_by_field(func_node, "return_type")
        return_type = _node_text(ret_node, source).lstrip(": ") if ret_node else None

        # Body hash
        body_node = _child_by_field(func_node, "body")
        body_text = _node_text(body_node, source) if body_node else ""
        body_hash = hashlib.sha256(body_text.encode()).hexdigest()[:16]

        # LOC
        start_line = func_node.start_point[0] + 1
        end_line = func_node.end_point[0] + 1
        loc = end_line - start_line + 1

        # Complexity (simple heuristic: count branching keywords)
        complexity = 1
        for child in _walk(func_node):
            if child.type in (
                "if_statement",
                "else_clause",
                "for_statement",
                "for_in_statement",
                "while_statement",
                "do_statement",
                "catch_clause",
                "ternary_expression",
                "switch_case",
            ):
                complexity += 1
            elif child.type == "binary_expression":
                op = _child_by_field(child, "operator")
                if op and _node_text(op, source) in ("&&", "||", "??"):
                    complexity += 1

        # Decorators (TypeScript only has limited decorator support)
        decorators: list[str] = []
        if is_method and node.parent:
            for sib in node.parent.children:
                if sib.type == "decorator" and sib.end_point[0] < node.start_point[0]:
                    decorators.append(_node_text(sib, source).lstrip("@"))

        # Docstring check (JSDoc comment preceding the function)
        has_docstring = False
        if func_node.prev_sibling and func_node.prev_sibling.type == "comment":
            has_docstring = _node_text(func_node.prev_sibling, source).startswith("/**")

        # If method inside a class, prefix with class name
        if is_method and node.parent and node.parent.type == "class_body":
            class_node = node.parent.parent
            if class_node and class_node.type == "class_declaration":
                cls_name = _child_by_field(class_node, "name")
                if cls_name:
                    name = f"{_node_text(cls_name, source)}.{name}"

        # Pre-compute AST n-grams for MDS signal
        ast_fp: dict[str, Any] = {}
        ngrams = _compute_ts_ast_ngrams(func_node)
        if ngrams:
            ast_fp["ngrams"] = ngrams

        # Export detection
        is_exported = False
        if not is_method:
            parent = node.parent
            if parent and parent.type == "export_statement":
                is_exported = True

        functions.append(
            FunctionInfo(
                name=name,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                language=language,
                complexity=complexity,
                loc=loc,
                parameters=params,
                return_type=return_type,
                decorators=decorators,
                has_docstring=has_docstring,
                body_hash=body_hash,
                ast_fingerprint=ast_fp,
                is_exported=is_exported,
            )
        )

    return functions


def _extract_interfaces(
    root: Any,
    source: bytes,
    file_path: Path,
    language: str,
) -> list[ClassInfo]:
    """Extract interface declarations and type alias declarations."""
    interfaces: list[ClassInfo] = []

    for node in _walk(root):
        if node.type == "interface_declaration":
            name_node = _child_by_field(node, "name")
            name = _node_text(name_node, source) if name_node else "anonymous"

            # Extends clause
            bases: list[str] = []
            for child in node.children:
                if child.type == "extends_type_clause":
                    for sub in child.children:
                        if sub.type in ("type_identifier", "identifier", "generic_type"):
                            txt = _node_text(sub, source)
                            # For generic_type, extract just the name part
                            if sub.type == "generic_type":
                                id_node = next(
                                    (
                                        c
                                        for c in sub.children
                                        if c.type in ("type_identifier", "identifier")
                                    ),
                                    None,
                                )
                                if id_node:
                                    txt = _node_text(id_node, source)
                            bases.append(txt)

            # Extract method signatures from interface body
            methods: list[FunctionInfo] = []
            body = _child_by_field(node, "body")
            if body is None:
                for child in node.children:
                    if child.type == "interface_body":
                        body = child
                        break

            if body:
                for member in body.children:
                    if member.type in ("method_signature", "call_signature"):
                        mname_node = _child_by_field(member, "name")
                        mname = _node_text(mname_node, source) if mname_node else None
                        if mname is None:
                            continue

                        # Parameters
                        params_node = _child_by_field(member, "parameters")
                        params: list[str] = []
                        if params_node:
                            for p in params_node.children:
                                if p.type in (
                                    "required_parameter",
                                    "optional_parameter",
                                    "rest_parameter",
                                ):
                                    pname = _child_by_field(
                                        p, "pattern"
                                    ) or _child_by_field(p, "name")
                                    if pname:
                                        params.append(_node_text(pname, source))
                                elif p.type == "identifier":
                                    params.append(_node_text(p, source))

                        # Return type
                        ret_node = _child_by_field(member, "return_type")
                        return_type = (
                            _node_text(ret_node, source).lstrip(": ")
                            if ret_node
                            else None
                        )

                        methods.append(
                            FunctionInfo(
                                name=f"{name}.{mname}",
                                file_path=file_path,
                                start_line=member.start_point[0] + 1,
                                end_line=member.end_point[0] + 1,
                                language=language,
                                parameters=params,
                                return_type=return_type,
                            )
                        )

            # Docstring
            has_docstring = False
            if node.prev_sibling and node.prev_sibling.type == "comment":
                has_docstring = _node_text(node.prev_sibling, source).startswith("/**")

            interfaces.append(
                ClassInfo(
                    name=name,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language=language,
                    bases=bases,
                    methods=methods,
                    has_docstring=has_docstring,
                    is_interface=True,
                )
            )

        elif node.type == "type_alias_declaration":
            name_node = _child_by_field(node, "name")
            name = _node_text(name_node, source) if name_node else "anonymous"

            # Docstring
            has_docstring = False
            if node.prev_sibling and node.prev_sibling.type == "comment":
                has_docstring = _node_text(node.prev_sibling, source).startswith("/**")

            interfaces.append(
                ClassInfo(
                    name=name,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language=language,
                    bases=[],
                    methods=[],
                    has_docstring=has_docstring,
                    is_interface=True,
                )
            )

    return interfaces


def _extract_classes(
    root: Any,
    source: bytes,
    file_path: Path,
    language: str,
    functions: list[FunctionInfo],
) -> list[ClassInfo]:
    """Extract class declarations."""
    classes: list[ClassInfo] = []

    for node in _walk(root):
        if node.type != "class_declaration":
            continue

        name_node = _child_by_field(node, "name")
        name = _node_text(name_node, source) if name_node else "anonymous"

        # Base classes / implements
        bases: list[str] = []
        heritage = _child_by_field(node, "heritage") or None
        if heritage is None:
            for c in node.children:
                if c.type == "class_heritage":
                    heritage = c
                    break
        if heritage:
            for clause in heritage.children:
                if clause.type in ("extends_clause", "implements_clause"):
                    for child in clause.children:
                        if child.type in ("type_identifier", "identifier"):
                            bases.append(_node_text(child, source))

        # Docstring
        has_docstring = False
        if node.prev_sibling and node.prev_sibling.type == "comment":
            has_docstring = _node_text(node.prev_sibling, source).startswith("/**")

        methods = [f for f in functions if f.name.startswith(f"{name}.")]

        classes.append(
            ClassInfo(
                name=name,
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language=language,
                bases=bases,
                methods=methods,
                has_docstring=has_docstring,
            )
        )

    return classes


def _extract_imports(
    root: Any,
    source: bytes,
    file_path: Path,
) -> list[ImportInfo]:
    """Extract import statements."""
    imports: list[ImportInfo] = []

    for node in _walk(root):
        if node.type != "import_statement":
            continue

        # import X from "module"  /  import { A, B } from "module"
        source_node = _child_by_field(node, "source")
        if source_node is None:
            # try children with type "string"
            for c in node.children:
                if c.type == "string":
                    source_node = c
                    break
        if source_node is None:
            continue

        module = _node_text(source_node, source).strip("'\"")

        names: list[str] = []
        for child in node.children:
            if child.type == "import_clause":
                for sub in _walk(child):
                    if sub.type == "identifier":
                        names.append(_node_text(sub, source))

        if not names:
            names = [module.rsplit("/", 1)[-1]]

        imports.append(
            ImportInfo(
                source_file=file_path,
                imported_module=module,
                imported_names=names,
                line_number=node.start_point[0] + 1,
                is_relative=module.startswith("."),
                is_module_level=True,
            )
        )

    return imports


def _extract_patterns(
    root: Any,
    source: bytes,
    file_path: Path,
    functions: list[FunctionInfo],
) -> list[PatternInstance]:
    """Extract error-handling and API endpoint patterns."""
    patterns: list[PatternInstance] = []

    for node in _walk(root):
        if node.type != "try_statement":
            continue

        # Find enclosing function name
        fn_name = "<module>"
        for func in functions:
            if func.start_line <= node.start_point[0] + 1 <= func.end_line:
                fn_name = func.name
                break

        # Fingerprint the catch clauses
        handlers: list[dict[str, Any]] = []
        for child in node.children:
            if child.type == "catch_clause":
                param = _child_by_field(child, "parameter")
                if param is None:
                    exc_type = "bare"
                else:
                    # Look for an explicit type annotation on the catch clause
                    type_ann = next(
                        (c for c in child.children if c.type == "type_annotation"),
                        None,
                    )
                    if type_ann:
                        exc_type = _node_text(type_ann, source).lstrip(": ").strip()
                    else:
                        # No type annotation → untyped catch; catches everything
                        exc_type = "bare"

                body = _child_by_field(child, "body")
                actions: list[str] = []
                if body:
                    for stmt in _walk(body):
                        if stmt.type == "throw_statement":
                            actions.append("throw")
                        elif stmt.type == "return_statement":
                            actions.append("return")
                        elif stmt.type == "call_expression":
                            fn = _child_by_field(stmt, "function")
                            if fn:
                                txt = _node_text(fn, source)
                                if any(k in txt for k in ("log", "error", "warn", "console")):
                                    actions.append("log")
                                else:
                                    actions.append("call")

                handlers.append(
                    {
                        "exception_type": exc_type,
                        "actions": actions,
                    }
                )

        has_finally = any(c.type == "finally_clause" for c in node.children)

        patterns.append(
            PatternInstance(
                category=PatternCategory.ERROR_HANDLING,
                file_path=file_path,
                function_name=fn_name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                fingerprint={
                    "handler_count": len(handlers),
                    "handlers": handlers,
                    "has_finally": has_finally,
                },
            )
        )

    return patterns


# ---------------------------------------------------------------------------
# API endpoint pattern extraction (Express / Fastify / NestJS / Koa)
# ---------------------------------------------------------------------------

# HTTP method names used in framework router calls and decorators
_TS_ROUTE_METHODS: frozenset[str] = frozenset({
    "get", "post", "put", "patch", "delete", "head", "options", "all",
    # NestJS decorators
    "Get", "Post", "Put", "Patch", "Delete", "Head", "Options",
})


def _extract_api_patterns(
    root: Any,
    source: bytes,
    file_path: Path,
    functions: list[FunctionInfo],
) -> list[PatternInstance]:
    """Extract API endpoint patterns from Express/Fastify/NestJS-style routes."""
    patterns: list[PatternInstance] = []

    for node in _walk(root):
        is_route = False
        method = ""

        # app.get("/path", handler) / router.post("/path", handler)
        if node.type == "call_expression":
            fn_node = _child_by_field(node, "function")
            if fn_node and fn_node.type == "member_expression":
                prop = _child_by_field(fn_node, "property")
                if prop:
                    method = _node_text(prop, source)
                    if method.lower() in _TS_ROUTE_METHODS:
                        is_route = True

        # @Get("/path") / @Post("/path") NestJS decorators
        elif node.type == "decorator":
            dec_text = _node_text(node, source).lstrip("@")
            dec_name = dec_text.split("(")[0]
            if dec_name in _TS_ROUTE_METHODS:
                is_route = True
                method = dec_name

        if not is_route:
            continue

        fn_name = "<module>"
        for func in functions:
            if func.start_line <= node.start_point[0] + 1 <= func.end_line:
                fn_name = func.name
                break

        # Extract route path argument if present
        route_path = ""
        args_node = _child_by_field(node, "arguments")
        if args_node:
            for arg in args_node.children:
                if arg.type in ("string", "template_string"):
                    route_path = _node_text(arg, source).strip("'\"`")
                    break

        patterns.append(
            PatternInstance(
                category=PatternCategory.API_ENDPOINT,
                file_path=file_path,
                function_name=fn_name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                fingerprint={
                    "method": method.upper(),
                    "route": route_path,
                    "framework": "express",  # generic label
                },
            )
        )

    return patterns


# ---------------------------------------------------------------------------
# React Hook pattern extraction
# ---------------------------------------------------------------------------

_REACT_HOOKS_WITH_DEPS = frozenset({
    "useEffect",
    "useCallback",
    "useMemo",
    "useLayoutEffect",
    "useImperativeHandle",
})


def _extract_hook_patterns(
    root: Any,
    source: bytes,
    file_path: Path,
    language: str,
) -> list[PatternInstance]:
    """Extract React Hook anti-patterns: missing deps, stale closures, placement."""
    patterns: list[PatternInstance] = []

    for node in _walk(root):
        if node.type != "call_expression":
            continue

        func_node = _child_by_field(node, "function")
        if func_node is None:
            continue
        callee = _node_text(func_node, source)

        if callee not in _REACT_HOOKS_WITH_DEPS:
            continue

        args = _child_by_field(node, "arguments")
        if args is None:
            continue

        # Collect actual arguments (skip parentheses and commas)
        arg_nodes = [
            c for c in args.children
            if c.type not in ("(", ")", ",")
        ]

        if len(arg_nodes) == 1:
            # Missing dependency array
            patterns.append(
                PatternInstance(
                    category=PatternCategory.REACT_HOOK,
                    file_path=file_path,
                    function_name=callee,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    fingerprint={
                        "hook": callee,
                        "issue": "missing_dependency_array",
                    },
                    variant_id="MISSING_DEPENDENCY_ARRAY",
                )
            )

        elif len(arg_nodes) >= 2:
            deps_node = arg_nodes[1]
            if deps_node.type == "array":
                dep_items = [
                    c for c in deps_node.children
                    if c.type not in ("[", "]", ",")
                ]
                if not dep_items:
                    # Empty deps array — check for stale closure
                    callback = arg_nodes[0]
                    callback_ids = _collect_identifiers(callback, source)
                    # Heuristic: if callback references identifiers that look
                    # like state/props (any lowercase identifier) → stale closure risk
                    if callback_ids:
                        patterns.append(
                            PatternInstance(
                                category=PatternCategory.REACT_HOOK,
                                file_path=file_path,
                                function_name=callee,
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                                fingerprint={
                                    "hook": callee,
                                    "issue": "stale_closure",
                                    "referenced_ids": list(callback_ids)[:10],
                                },
                                variant_id="STALE_CLOSURE",
                            )
                        )

    # Hook placement: custom hooks (use* functions) outside hooks/ directory
    hooks_dir_tokens = {"hooks", "use-hooks", "hook"}
    path_parts = {p.lower() for p in file_path.parts}
    in_hooks_dir = bool(path_parts & hooks_dir_tokens)

    if not in_hooks_dir:
        for node in _walk(root):
            if node.type == "function_declaration":
                name_node = _child_by_field(node, "name")
                if name_node:
                    fname = _node_text(name_node, source)
                    if fname.startswith("use") and len(fname) > 3 and fname[3].isupper():
                        patterns.append(
                            PatternInstance(
                                category=PatternCategory.REACT_HOOK,
                                file_path=file_path,
                                function_name=fname,
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                                fingerprint={
                                    "hook_name": fname,
                                    "issue": "hook_placement_violation",
                                },
                                variant_id="HOOK_PLACEMENT_VIOLATION",
                            )
                        )

    return patterns


def _collect_identifiers(node: Any, source: bytes) -> set[str]:
    """Collect non-builtin identifier names from a callback node."""
    builtins = frozenset({
        "console", "document", "window", "setTimeout", "setInterval",
        "clearTimeout", "clearInterval", "fetch", "JSON", "Math",
        "Promise", "Array", "Object", "String", "Number", "Boolean",
        "undefined", "null", "true", "false", "this",
    })
    ids: set[str] = set()
    for child in _walk(node):
        if child.type == "identifier":
            name = _node_text(child, source)
            if name not in builtins and not name.startswith("_"):
                ids.add(name)
    return ids


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_typescript_file(
    file_path: Path,
    repo_path: Path,
    language: str = "typescript",
) -> ParseResult:
    """Parse a TypeScript/TSX file using tree-sitter.

    Falls back to a minimal regex-based parser if tree-sitter is not installed.
    """
    if not tree_sitter_available():
        # Delegate to the regex stub in ast_parser
        from drift.ingestion.ast_parser import _parse_typescript_stub

        return _parse_typescript_stub(file_path, repo_path, language=language)

    full_path = repo_path / file_path
    try:
        source_text = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return ParseResult(
            file_path=file_path,
            language=language,
            parse_errors=[f"{type(exc).__name__}: {exc}"],
        )
    source_bytes = source_text.encode("utf-8")

    ts_lang = "tsx" if language in ("tsx", "jsx") else "typescript"
    parser = _get_parser(ts_lang)
    tree = parser.parse(source_bytes)
    root = tree.root_node

    functions = _extract_functions(root, source_bytes, file_path, language)
    classes = _extract_classes(root, source_bytes, file_path, language, functions)
    classes.extend(_extract_interfaces(root, source_bytes, file_path, language))
    imports = _extract_imports(root, source_bytes, file_path)
    patterns = _extract_patterns(root, source_bytes, file_path, functions)
    patterns.extend(_extract_api_patterns(root, source_bytes, file_path, functions))
    if language in ("tsx", "jsx"):
        patterns.extend(_extract_hook_patterns(root, source_bytes, file_path, language))

    return ParseResult(
        file_path=file_path,
        language=language,
        functions=functions,
        classes=classes,
        imports=imports,
        patterns=patterns,
        line_count=len(source_text.splitlines()),
    )
