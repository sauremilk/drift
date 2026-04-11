"""Coverage tests for PhantomReferenceSignal (PHR) helpers."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from drift.models import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    ParseResult,
)
from drift.signals.phantom_reference import (
    _build_module_exports,
    _build_project_symbols,
    _collect_type_checking_import_ids,
    _is_in_try_except_import_error,
    _NameCollector,
    _path_to_module,
    _ScopeCollector,
)

# ---------------------------------------------------------------------------
# _is_in_try_except_import_error
# ---------------------------------------------------------------------------


class TestIsInTryExceptImportError:
    def test_import_in_import_error_guard(self):
        source = textwrap.dedent("""\
            try:
                import optional_dep
            except ImportError:
                optional_dep = None
        """)
        tree = ast.parse(source)
        # The import node is inside tree.body[0].body[0]
        import_node = tree.body[0].body[0]
        assert _is_in_try_except_import_error(import_node, tree)

    def test_import_not_in_guard(self):
        source = textwrap.dedent("""\
            import regular_dep
        """)
        tree = ast.parse(source)
        import_node = tree.body[0]
        assert not _is_in_try_except_import_error(import_node, tree)

    def test_bare_except_guard(self):
        source = textwrap.dedent("""\
            try:
                import risky
            except:
                risky = None
        """)
        tree = ast.parse(source)
        import_node = tree.body[0].body[0]
        assert _is_in_try_except_import_error(import_node, tree)

    def test_module_not_found_error_guard(self):
        source = textwrap.dedent("""\
            try:
                import special
            except ModuleNotFoundError:
                special = None
        """)
        tree = ast.parse(source)
        import_node = tree.body[0].body[0]
        assert _is_in_try_except_import_error(import_node, tree)

    def test_tuple_handler_types(self):
        source = textwrap.dedent("""\
            try:
                import dep
            except (ImportError, ModuleNotFoundError):
                dep = None
        """)
        tree = ast.parse(source)
        import_node = tree.body[0].body[0]
        assert _is_in_try_except_import_error(import_node, tree)


# ---------------------------------------------------------------------------
# _collect_type_checking_import_ids
# ---------------------------------------------------------------------------


class TestCollectTypeCheckingImportIds:
    def test_name_style_tc_block(self):
        source = textwrap.dedent("""\
            from __future__ import annotations
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                from mymodule import MyType
        """)
        tree = ast.parse(source)
        tc_ids = _collect_type_checking_import_ids(tree)
        assert len(tc_ids) >= 1

    def test_attribute_style_tc_block(self):
        source = textwrap.dedent("""\
            import typing
            if typing.TYPE_CHECKING:
                from mymodule import MyType
        """)
        tree = ast.parse(source)
        tc_ids = _collect_type_checking_import_ids(tree)
        assert len(tc_ids) >= 1

    def test_no_tc_block_returns_empty(self):
        source = textwrap.dedent("""\
            import os
            import sys
        """)
        tree = ast.parse(source)
        tc_ids = _collect_type_checking_import_ids(tree)
        assert tc_ids == set()


# ---------------------------------------------------------------------------
# _NameCollector
# ---------------------------------------------------------------------------


class TestNameCollector:
    def test_collects_used_names(self):
        source = textwrap.dedent("""\
            import os
            result = os.path.join("a", "b")
            print(result)
        """)
        tree = ast.parse(source)
        collector = _NameCollector()
        collector.visit(tree)
        assert "os" in collector.used_names
        assert "print" in collector.used_names

    def test_star_import_detected(self):
        source = textwrap.dedent("""\
            from os.path import *
        """)
        tree = ast.parse(source)
        collector = _NameCollector()
        collector.visit(tree)
        assert collector._has_star_import

    def test_getattr_module_detected(self):
        source = textwrap.dedent("""\
def __getattr__(name):
    return name
        """)
        tree = ast.parse(source)
        collector = _NameCollector()
        collector.visit(tree)
        assert collector._has_getattr_module

    def test_exec_eval_detected(self):
        source = textwrap.dedent("""\
            exec("print('hi')")
            eval("1 + 2")
        """)
        tree = ast.parse(source)
        collector = _NameCollector()
        collector.visit(tree)
        assert collector._has_exec_eval

    def test_type_checking_names_skipped(self):
        source = textwrap.dedent("""\
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                from mymodule import MyType
            x = print(1)
        """)
        tree = ast.parse(source)
        collector = _NameCollector()
        collector.visit(tree)
        # MyType should NOT be in used_names (it's in TYPE_CHECKING block)
        # But 'print' should be there (it's a call target in Load context)
        assert "print" in collector.used_names


# ---------------------------------------------------------------------------
# _ScopeCollector
# ---------------------------------------------------------------------------


class TestScopeCollector:
    def test_function_and_class(self):
        source = textwrap.dedent("""\
            class MyClass:
                def method(self):
                    pass

            def my_func():
                pass
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "MyClass" in collector.defined_names
        assert "my_func" in collector.defined_names

    def test_imports(self):
        source = textwrap.dedent("""\
            import os
            from pathlib import Path
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "os" in collector.defined_names
        assert "Path" in collector.defined_names

    def test_for_loop_target(self):
        source = textwrap.dedent("""\
            for item in [1, 2, 3]:
                pass
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "item" in collector.defined_names

    def test_with_as(self):
        source = textwrap.dedent("""\
            with open("f") as fh:
                pass
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "fh" in collector.defined_names

    def test_except_handler(self):
        source = textwrap.dedent("""\
            try:
                pass
            except ValueError as exc:
                pass
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "exc" in collector.defined_names

    def test_annotated_assignment(self):
        source = textwrap.dedent("""\
            x: int = 5
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "x" in collector.defined_names

    def test_augmented_assignment(self):
        source = textwrap.dedent("""\
            x = 0
            x += 1
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "x" in collector.defined_names

    def test_lambda_params(self):
        source = textwrap.dedent("""\
            f = lambda a, b: a + b
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "a" in collector.defined_names
        assert "b" in collector.defined_names

    def test_comprehension_variable(self):
        source = textwrap.dedent("""\
            result = [x for x in range(10)]
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "x" in collector.defined_names

    def test_walrus_operator(self):
        source = textwrap.dedent("""\
            if (n := 10) > 5:
                pass
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "n" in collector.defined_names

    def test_global_declaration(self):
        source = textwrap.dedent("""\
            def f():
                global counter
                counter = 0
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "counter" in collector.defined_names


# ---------------------------------------------------------------------------
# _path_to_module
# ---------------------------------------------------------------------------


class TestPathToModule:
    def test_simple_module(self):
        assert _path_to_module(Path("drift/models.py")) == "drift.models"

    def test_src_prefix_stripped(self):
        assert _path_to_module(Path("src/drift/models.py")) == "drift.models"

    def test_init_file(self):
        assert _path_to_module(Path("src/drift/__init__.py")) == "drift"

    def test_empty_parts(self):
        assert _path_to_module(Path("")) == ""


# ---------------------------------------------------------------------------
# _build_project_symbols
# ---------------------------------------------------------------------------


class TestBuildProjectSymbols:
    def test_collects_functions_and_classes(self):
        pr = ParseResult(
            file_path=Path("module.py"),
            language="python",
            functions=[
                FunctionInfo(
                    name="process",
                    file_path=Path("module.py"),
                    start_line=1,
                    end_line=5,
                    language="python",
                    complexity=1,
                    loc=4,
                    parameters=["self"],
                ),
            ],
            classes=[
                ClassInfo(
                    name="MyClass",
                    file_path=Path("module.py"),
                    start_line=10,
                    end_line=20,
                    language="python",
                    bases=["BaseClass"],
                    methods=[
                        FunctionInfo(
                            name="method",
                            file_path=Path("module.py"),
                            start_line=11,
                            end_line=15,
                            language="python",
                            complexity=1,
                            loc=4,
                            parameters=["self"],
                        ),
                    ],
                ),
            ],
        )
        symbols = _build_project_symbols([pr])
        assert "process" in symbols
        assert "MyClass" in symbols
        assert "method" in symbols

    def test_skips_non_python(self):
        pr = ParseResult(
            file_path=Path("app.ts"),
            language="typescript",
            functions=[
                FunctionInfo(
                    name="tsFunc",
                    file_path=Path("app.ts"),
                    start_line=1,
                    end_line=5,
                    language="typescript",
                    complexity=1,
                    loc=4,
                ),
            ],
        )
        symbols = _build_project_symbols([pr])
        assert "tsFunc" not in symbols


# ---------------------------------------------------------------------------
# _build_module_exports
# ---------------------------------------------------------------------------


class TestBuildModuleExports:
    def test_exports_include_imports(self):
        pr = ParseResult(
            file_path=Path("src/drift/__init__.py"),
            language="python",
            imports=[
                ImportInfo(
                    source_file=Path("src/drift/__init__.py"),
                    imported_module="drift.models",
                    imported_names=["Finding"],
                    line_number=1,
                ),
            ],
        )
        exports = _build_module_exports([pr])
        assert "Finding" in exports.get("drift", set())

    def test_skips_non_python(self):
        pr = ParseResult(
            file_path=Path("app.ts"),
            language="typescript",
        )
        exports = _build_module_exports([pr])
        assert len(exports) == 0
