"""Tests for Python AST parser."""

from pathlib import Path

from drift.ingestion.ast_parser import parse_python_file
from drift.models import PatternCategory


def test_parse_functions(tmp_path: Path, sample_python_source: str):
    (tmp_path / "sample.py").write_text(sample_python_source)
    result = parse_python_file(Path("sample.py"), tmp_path)

    assert result.language == "python"
    assert len(result.parse_errors) == 0

    func_names = [f.name for f in result.functions]
    assert "MyService.__init__" in func_names
    assert "MyService.process" in func_names
    assert "MyService._validate" in func_names
    assert "MyService.fetch_remote" in func_names
    assert "standalone_function" in func_names


def test_parse_classes(tmp_path: Path, sample_python_source: str):
    (tmp_path / "sample.py").write_text(sample_python_source)
    result = parse_python_file(Path("sample.py"), tmp_path)

    class_names = [c.name for c in result.classes]
    assert "MyService" in class_names
    assert "ServiceError" in class_names

    my_service = next(c for c in result.classes if c.name == "MyService")
    assert my_service.has_docstring is True
    assert len(my_service.methods) >= 3


def test_parse_imports(tmp_path: Path, sample_python_source: str):
    (tmp_path / "sample.py").write_text(sample_python_source)
    result = parse_python_file(Path("sample.py"), tmp_path)

    modules = [i.imported_module for i in result.imports]
    assert "os" in modules
    assert "pathlib" in modules
    assert "typing" in modules


def test_parse_error_handling_patterns(tmp_path: Path, sample_python_source: str):
    (tmp_path / "sample.py").write_text(sample_python_source)
    result = parse_python_file(Path("sample.py"), tmp_path)

    error_patterns = [
        p for p in result.patterns if p.category == PatternCategory.ERROR_HANDLING
    ]
    # Two try/except blocks in the sample code
    assert len(error_patterns) >= 2

    # Check fingerprints differ
    fps = [p.fingerprint for p in error_patterns]
    # One raises, one logs — different handler actions
    actions_set = set()
    for fp in fps:
        for handler in fp.get("handlers", []):
            for action in handler.get("actions", []):
                actions_set.add(action)
    assert len(actions_set) >= 2  # At least raise + log


def test_complexity(tmp_path: Path):
    source = """\
def complex_function(x, y, z):
    if x > 0:
        for i in range(y):
            if i % 2 == 0:
                try:
                    result = x / i
                except ZeroDivisionError:
                    continue
            elif i > 10:
                break
        while z > 0:
            z -= 1
    return z
"""
    (tmp_path / "complex.py").write_text(source)
    result = parse_python_file(Path("complex.py"), tmp_path)

    func = result.functions[0]
    # if + for + if + except + elif + while = 6, base = 1 → 7
    assert func.complexity >= 6


def test_docstring_detection(tmp_path: Path):
    source = '''\
def with_doc():
    """Has a docstring."""
    pass

def without_doc():
    pass
'''
    (tmp_path / "docs.py").write_text(source)
    result = parse_python_file(Path("docs.py"), tmp_path)

    by_name = {f.name: f for f in result.functions}
    assert by_name["with_doc"].has_docstring is True
    assert by_name["without_doc"].has_docstring is False


def test_syntax_error_handling(tmp_path: Path):
    (tmp_path / "bad.py").write_text("def foo(:\n  pass")
    result = parse_python_file(Path("bad.py"), tmp_path)
    assert len(result.parse_errors) > 0
