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


def test_import_scope_marks_module_level_and_local_imports(tmp_path: Path):
    source = """\
import os

def load_model():
    import torch
    return torch
"""
    (tmp_path / "sample.py").write_text(source)
    result = parse_python_file(Path("sample.py"), tmp_path)

    imports = {i.imported_module: i for i in result.imports}
    assert imports["os"].is_module_level is True
    assert imports["torch"].is_module_level is False


def test_parse_error_handling_patterns(tmp_path: Path, sample_python_source: str):
    (tmp_path / "sample.py").write_text(sample_python_source)
    result = parse_python_file(Path("sample.py"), tmp_path)

    error_patterns = [p for p in result.patterns if p.category == PatternCategory.ERROR_HANDLING]
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


def test_parse_error_handling_fallback_assignment_action(tmp_path: Path):
    source = """\
def optional_import():
    try:
        import missing_runtime
    except Exception:
        available = False
"""
    (tmp_path / "fallback_assign.py").write_text(source)
    result = parse_python_file(Path("fallback_assign.py"), tmp_path)

    error_patterns = [p for p in result.patterns if p.category == PatternCategory.ERROR_HANDLING]
    assert len(error_patterns) == 1
    handlers = error_patterns[0].fingerprint.get("handlers", [])
    assert handlers
    assert "fallback_assign" in handlers[0].get("actions", [])


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


# ---------------------------------------------------------------------------
# Return-strategy pattern extraction
# ---------------------------------------------------------------------------


def test_return_strategy_multiple_strategies_detected(tmp_path: Path):
    """Function with return-None + raise → two distinct strategies → pattern emitted."""
    source = """\
def get_user(user_id: int):
    if user_id <= 0:
        return None
    if user_id > 9999:
        raise ValueError("invalid id")
    return {"id": user_id}
"""
    (tmp_path / "models.py").write_text(source)
    result = parse_python_file(Path("models.py"), tmp_path)

    ret_patterns = [p for p in result.patterns if p.category == PatternCategory.RETURN_PATTERN]
    assert len(ret_patterns) == 1
    strategies = ret_patterns[0].fingerprint["strategies"]
    assert "return_none" in strategies
    assert "raise" in strategies


def test_return_strategy_single_strategy_not_emitted(tmp_path: Path):
    """Function with only one return strategy → no pattern emitted."""
    source = """\
def add(a: int, b: int) -> int:
    return a + b

def multiply(a: int, b: int) -> int:
    return a * b
"""
    (tmp_path / "math_utils.py").write_text(source)
    result = parse_python_file(Path("math_utils.py"), tmp_path)

    ret_patterns = [p for p in result.patterns if p.category == PatternCategory.RETURN_PATTERN]
    assert len(ret_patterns) == 0


def test_return_strategy_tuple_and_dict_and_raise(tmp_path: Path):
    """Function with return_none + raise + return_dict → three distinct strategies."""
    source = """\
def get_data(key: str):
    if not key:
        return None
    if key == "missing":
        raise KeyError(key)
    return {"key": key, "value": 42}
"""
    (tmp_path / "models.py").write_text(source)
    result = parse_python_file(Path("models.py"), tmp_path)

    ret_patterns = [p for p in result.patterns if p.category == PatternCategory.RETURN_PATTERN]
    assert len(ret_patterns) == 1
    strategies = ret_patterns[0].fingerprint["strategies"]
    assert "raise" in strategies
    assert "return_none" in strategies
    assert "return_dict" in strategies


def test_return_strategy_ignores_nested_functions(tmp_path: Path):
    """Nested function returns should not affect the outer function's strategies."""
    source = """\
def outer():
    def inner():
        raise ValueError("boom")
    return inner()
"""
    (tmp_path / "nested.py").write_text(source)
    result = parse_python_file(Path("nested.py"), tmp_path)

    ret_patterns = [p for p in result.patterns if p.category == PatternCategory.RETURN_PATTERN]
    # outer has only return_value, inner has only raise → neither has ≥2 strategies
    outer_patterns = [p for p in ret_patterns if p.function_name == "outer"]
    assert len(outer_patterns) == 0


def test_return_strategy_bare_raise_detected(tmp_path: Path):
    """Bare raise (re-raise) counts as a raise strategy."""
    source = """\
def handle(data):
    try:
        return process(data)
    except ValueError:
        raise
"""
    (tmp_path / "handler.py").write_text(source)
    result = parse_python_file(Path("handler.py"), tmp_path)

    ret_patterns = [p for p in result.patterns if p.category == PatternCategory.RETURN_PATTERN]
    assert len(ret_patterns) == 1
    strategies = ret_patterns[0].fingerprint["strategies"]
    assert "raise" in strategies
    assert "return_value" in strategies


def test_return_strategy_mutation_benchmark_scenario(tmp_path: Path):
    """The exact pfs_002 mutation scenario: 3 functions with diverging return strategies."""
    source = '''\
def get_user(user_id: int):
    """Returns user dict or None."""
    if user_id <= 0:
        return None
    return {"id": user_id, "name": "Alice"}

def get_user_or_raise(user_id: int) -> dict:
    """Returns user dict or raises."""
    if user_id <= 0:
        raise ValueError("Invalid user_id")
    return {"id": user_id, "name": "Alice"}

def get_user_result(user_id: int) -> tuple:
    """Returns (user, error) tuple."""
    if user_id <= 0:
        return None, "Invalid user_id"
    return {"id": user_id, "name": "Alice"}, None
'''
    (tmp_path / "user.py").write_text(source)
    result = parse_python_file(Path("user.py"), tmp_path)

    ret_patterns = [p for p in result.patterns if p.category == PatternCategory.RETURN_PATTERN]
    # get_user: [return_none, return_value] → pattern emitted
    # get_user_or_raise: [raise, return_value] → pattern emitted
    # get_user_result: [return_tuple] (only 1 strategy) → no pattern
    assert len(ret_patterns) >= 2
