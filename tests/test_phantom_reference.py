"""Targeted tests for Phantom Reference (PHR) signal.

Tests critical heuristics, edge cases, and regression scenarios.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from drift.config import DriftConfig
from drift.models import ParseResult, SignalType
from drift.signals.phantom_reference import (
    PhantomReferenceSignal,
    _NameCollector,
    _ScopeCollector,
)


def _run_phr(
    files: dict[str, str],
    tmp_path: Path,
) -> list:
    """Run PHR signal on a dict of {path: source} and return findings."""
    from drift.ingestion.ast_parser import parse_python_file

    # Write files to disk so _read_source works
    parse_results = []
    for rel_path, source in files.items():
        full_path = tmp_path / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(textwrap.dedent(source), encoding="utf-8")
        pr = parse_python_file(Path(rel_path), tmp_path)
        parse_results.append(pr)

    signal = PhantomReferenceSignal()
    from drift.signals.base import SignalCapabilities

    caps = SignalCapabilities(
        repo_path=tmp_path,
        embedding_service=None,
        commits=[],
    )
    signal.bind_context(caps)

    config = DriftConfig()
    return signal.analyze(parse_results, {}, config)


class TestNameCollector:
    """Unit tests for _NameCollector AST visitor."""

    def test_collects_call_targets(self):
        import ast

        source = textwrap.dedent("""\
            def main():
                result = process_data(x)
                output = format_output(result)
        """)
        tree = ast.parse(source)
        collector = _NameCollector()
        collector.visit(tree)
        assert "process_data" in collector.used_names
        assert "format_output" in collector.used_names

    def test_collects_chained_attribute_root(self):
        import ast

        source = textwrap.dedent("""\
            def main():
                result = foo.bar.baz()
        """)
        tree = ast.parse(source)
        collector = _NameCollector()
        collector.visit(tree)
        assert "foo" in collector.used_names
        # bar and baz are attributes, not root names
        assert "bar" not in collector.used_names

    def test_skips_type_checking_block(self):
        import ast

        source = textwrap.dedent("""\
            from __future__ import annotations
            TYPE_CHECKING = False
            if TYPE_CHECKING:
                from missing_module import MissingType

            def func() -> None:
                pass
        """)
        tree = ast.parse(source)
        collector = _NameCollector()
        collector.visit(tree)
        # MissingType should not appear as used
        assert "MissingType" not in collector.used_names

    def test_detects_star_import(self):
        import ast

        source = "from os.path import *\n"
        tree = ast.parse(source)
        collector = _NameCollector()
        collector.visit(tree)
        assert collector._has_star_import is True

    def test_detects_module_getattr(self):
        import ast

        source = textwrap.dedent("""\
            def __getattr__(name):
                return globals()[name]
        """)
        tree = ast.parse(source)
        collector = _NameCollector()
        collector.visit(tree)
        assert collector._has_getattr_module is True


class TestScopeCollector:
    """Unit tests for _ScopeCollector AST visitor."""

    def test_collects_function_defs(self):
        import ast

        source = textwrap.dedent("""\
            def helper():
                pass

            async def async_helper():
                pass
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "helper" in collector.defined_names
        assert "async_helper" in collector.defined_names

    def test_collects_class_defs(self):
        import ast

        source = "class MyClass:\n    pass\n"
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "MyClass" in collector.defined_names

    def test_collects_assignments(self):
        import ast

        source = textwrap.dedent("""\
            x = 10
            y: int = 20
            a, b = 1, 2
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert {"x", "y", "a", "b"}.issubset(collector.defined_names)

    def test_collects_for_targets(self):
        import ast

        source = "for item in items:\n    pass\n"
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "item" in collector.defined_names

    def test_collects_with_as(self):
        import ast

        source = "with open('f') as fh:\n    pass\n"
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "fh" in collector.defined_names

    def test_collects_except_handler(self):
        import ast

        source = textwrap.dedent("""\
            try:
                pass
            except ValueError as err:
                pass
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "err" in collector.defined_names

    def test_collects_imports(self):
        import ast

        source = textwrap.dedent("""\
            import os
            from pathlib import Path
            import json as j
        """)
        tree = ast.parse(source)
        collector = _ScopeCollector()
        collector.visit(tree)
        assert "os" in collector.defined_names
        assert "Path" in collector.defined_names
        assert "j" in collector.defined_names


class TestPhantomReferenceSignal:
    """Integration tests for the PHR signal."""

    def test_detects_phantom_calls(self, tmp_path: Path):
        """Phantom function calls should be flagged."""
        files = {
            "app/__init__.py": "",
            "app/service.py": """\
                def process():
                    data = fetch_remote_data()
                    cleaned = sanitize_input(data)
                    return cleaned
            """,
        }
        findings = _run_phr(files, tmp_path)
        assert len(findings) >= 1
        assert findings[0].signal_type == SignalType.PHANTOM_REFERENCE
        phantom_names = [p["name"] for p in findings[0].metadata["phantom_names"]]
        assert "fetch_remote_data" in phantom_names
        assert "sanitize_input" in phantom_names

    def test_no_findings_when_all_resolved(self, tmp_path: Path):
        """All imports resolved → no findings."""
        files = {
            "utils/__init__.py": "",
            "utils/helpers.py": """\
                def clean(s):
                    return s.strip()
            """,
            "utils/main.py": """\
                from utils.helpers import clean

                def run(value):
                    return clean(value)
            """,
        }
        findings = _run_phr(files, tmp_path)
        phr_findings = [f for f in findings if f.signal_type == SignalType.PHANTOM_REFERENCE]
        assert len(phr_findings) == 0

    def test_skips_star_import_files(self, tmp_path: Path):
        """Files with star imports are conservatively skipped."""
        files = {
            "pkg/__init__.py": """\
                def secret():
                    pass
            """,
            "pkg/mod.py": """\
                from pkg import *

                def run():
                    return secret()
            """,
        }
        findings = _run_phr(files, tmp_path)
        phr = [f for f in findings if f.signal_type == SignalType.PHANTOM_REFERENCE]
        # pkg/mod.py should be skipped due to star import
        for f in phr:
            assert "mod.py" not in str(f.file_path)

    def test_skips_module_getattr(self, tmp_path: Path):
        """Modules with __getattr__ are conservatively skipped."""
        files = {
            "dynamic/__init__.py": "",
            "dynamic/mod.py": """\
                def __getattr__(name):
                    return None

                def use():
                    return phantom_func()
            """,
        }
        findings = _run_phr(files, tmp_path)
        phr = [f for f in findings if f.signal_type == SignalType.PHANTOM_REFERENCE]
        for f in phr:
            assert "mod.py" not in str(f.file_path)

    def test_builtins_not_flagged(self, tmp_path: Path):
        """Builtin functions should never be flagged."""
        files = {
            "utils/__init__.py": "",
            "utils/basics.py": """\
                def summarize(items):
                    count = len(items)
                    total = sum(items)
                    types = set(type(i).__name__ for i in items)
                    output = dict(count=count, total=total)
                    return str(output)
            """,
        }
        findings = _run_phr(files, tmp_path)
        phr = [f for f in findings if f.signal_type == SignalType.PHANTOM_REFERENCE]
        assert len(phr) == 0

    def test_skips_test_files(self, tmp_path: Path):
        """Test files should be excluded from analysis."""
        files = {
            "app/__init__.py": "",
            "tests/test_something.py": """\
                def test_it():
                    result = nonexistent_helper()
                    assert result is not None
            """,
        }
        findings = _run_phr(files, tmp_path)
        phr = [f for f in findings if f.signal_type == SignalType.PHANTOM_REFERENCE]
        assert len(phr) == 0

    def test_skips_dunder_names(self, tmp_path: Path):
        """Dunder names should not be flagged."""
        files = {
            "app/__init__.py": "",
            "app/meta.py": """\
                def info():
                    return __name__
            """,
        }
        findings = _run_phr(files, tmp_path)
        phr = [f for f in findings if f.signal_type == SignalType.PHANTOM_REFERENCE]
        assert len(phr) == 0

    def test_skips_non_python(self, tmp_path: Path):
        """Non-Python files should be excluded."""
        pr = ParseResult(file_path=Path("app/index.ts"), language="typescript")
        signal = PhantomReferenceSignal()
        config = DriftConfig()
        findings = signal.analyze([pr], {}, config)
        assert len(findings) == 0

    def test_cross_file_resolution(self, tmp_path: Path):
        """Names defined in other project files should be resolvable."""
        files = {
            "pkg/__init__.py": "",
            "pkg/models.py": """\
                class UserModel:
                    pass

                def create_user(name):
                    return UserModel()
            """,
            "pkg/service.py": """\
                from pkg.models import UserModel, create_user

                def handle():
                    user = create_user("test")
                    return user
            """,
        }
        findings = _run_phr(files, tmp_path)
        phr = [f for f in findings if f.signal_type == SignalType.PHANTOM_REFERENCE]
        assert len(phr) == 0

    def test_local_assignment_resolves(self, tmp_path: Path):
        """Variables assigned locally should not be flagged."""
        files = {
            "app/__init__.py": "",
            "app/compute.py": """\
                config = {"key": "value"}
                threshold = 0.5

                def check():
                    if config["key"]:
                        return threshold > 0.3
            """,
        }
        findings = _run_phr(files, tmp_path)
        phr = [f for f in findings if f.signal_type == SignalType.PHANTOM_REFERENCE]
        assert len(phr) == 0

    # --- Regression tests for FP bug fixes ---

    def test_comprehension_variables_not_flagged(self, tmp_path: Path):
        """Comprehension iteration variables must not be flagged as phantom."""
        files = {
            "app/__init__.py": "",
            "app/utils.py": """\
                def transform(items):
                    upper = [item.strip().upper() for item in items]
                    pairs = {k: v.lower() for k, v in enumerate(items)}
                    total = sum(x.count("a") for x in items)
                    return upper, pairs, total
            """,
        }
        findings = _run_phr(files, tmp_path)
        phr = [f for f in findings if f.signal_type == SignalType.PHANTOM_REFERENCE]
        assert len(phr) == 0

    def test_lambda_parameters_not_flagged(self, tmp_path: Path):
        """Lambda parameter names must not be flagged as phantom."""
        files = {
            "app/__init__.py": "",
            "app/sort.py": """\
                data = [{"path": "a"}, {"path": "b"}]

                def sorted_data():
                    return sorted(data, key=lambda item: str(item["path"]))
            """,
        }
        findings = _run_phr(files, tmp_path)
        phr = [f for f in findings if f.signal_type == SignalType.PHANTOM_REFERENCE]
        assert len(phr) == 0

    def test_import_from_phantom_detected(self, tmp_path: Path):
        """Importing a non-existent name from a project module is phantom."""
        files = {
            "pkg/__init__.py": "",
            "pkg/helpers.py": """\
                def actual_func():
                    return 42
            """,
            "pkg/main.py": """\
                from pkg.helpers import nonexistent_func

                def run():
                    return nonexistent_func()
            """,
        }
        findings = _run_phr(files, tmp_path)
        phr = [f for f in findings if f.signal_type == SignalType.PHANTOM_REFERENCE]
        assert len(phr) >= 1
        phantom_names = [p["name"] for p in phr[0].metadata["phantom_names"]]
        assert "nonexistent_func" in phantom_names

    def test_import_from_constant_not_flagged(self, tmp_path: Path):
        """Importing a module-level constant should not be flagged."""
        files = {
            "pkg/__init__.py": "",
            "pkg/constants.py": """\
                MAX_SIZE = 100
                VERSION = "1.0"
            """,
            "pkg/main.py": """\
                from pkg.constants import MAX_SIZE

                def check(size):
                    return size < MAX_SIZE
            """,
        }
        findings = _run_phr(files, tmp_path)
        phr = [f for f in findings if f.signal_type == SignalType.PHANTOM_REFERENCE]
        assert len(phr) == 0
