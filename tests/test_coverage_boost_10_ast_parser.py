"""Coverage-Boost: ingestion/ast_parser.py — pure helper functions."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from drift.ingestion.ast_parser import (
    PythonFileParser,
    _classify_return_strategy,
    _decorator_name,
    _fingerprint_endpoint,
    _fingerprint_return_strategy,
    _fingerprint_try_block,
    _is_route_decorator,
    parse_file,
    parse_python_file,
)

# ---------------------------------------------------------------------------
# _fingerprint_try_block — branch coverage
# ---------------------------------------------------------------------------


def _parse_try(source: str) -> ast.Try:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            return node
    pytest.fail("No try block found in source")


def test_fingerprint_try_block_attribute_exception() -> None:
    """except errno.ENOENT: → ast.Attribute exception type."""
    src = """
try:
    x = 1
except errno.ENOENT:
    raise
"""
    node = _parse_try(src)
    fp = _fingerprint_try_block(node)
    assert fp["handlers"][0]["exception_type"].startswith("Attribute")


def test_fingerprint_try_block_tuple_exception() -> None:
    """except (ValueError, TypeError): → ast.Tuple exception type."""
    src = """
try:
    x = 1
except (ValueError, TypeError):
    pass
"""
    node = _parse_try(src)
    fp = _fingerprint_try_block(node)
    assert "|" in fp["handlers"][0]["exception_type"]


def test_fingerprint_try_block_body_print_func_attr() -> None:
    """Body with attr.print(msg) → 'print' action."""
    src = """
try:
    x = 1
except Exception:
    sys.print("error")
"""
    node = _parse_try(src)
    fp = _fingerprint_try_block(node)
    # func.attr == "print" → body_actions.append("print")
    assert "print" in fp["handlers"][0]["actions"]


def test_fingerprint_try_block_body_call_func_attr_other() -> None:
    """Body with attr.other_func() → 'call' action."""
    src = """
try:
    x = 1
except Exception:
    some.do_stuff()
"""
    node = _parse_try(src)
    fp = _fingerprint_try_block(node)
    assert "call" in fp["handlers"][0]["actions"]


def test_fingerprint_try_block_body_print_func_name() -> None:
    """Body with bare print(msg) → 'print' action."""
    src = """
try:
    x = 1
except Exception:
    print("error")
"""
    node = _parse_try(src)
    fp = _fingerprint_try_block(node)
    assert "print" in fp["handlers"][0]["actions"]


def test_fingerprint_try_block_body_log_func_name() -> None:
    """Body with logging(msg) → 'log' action."""
    src = """
try:
    x = 1
except Exception:
    logging("err")
"""
    node = _parse_try(src)
    fp = _fingerprint_try_block(node)
    assert "log" in fp["handlers"][0]["actions"]


def test_fingerprint_try_block_body_call_func_name() -> None:
    """Body with bare function call → 'call' action."""
    src = """
try:
    x = 1
except Exception:
    process(x)
"""
    node = _parse_try(src)
    fp = _fingerprint_try_block(node)
    assert "call" in fp["handlers"][0]["actions"]


def test_fingerprint_try_block_body_call_func_other() -> None:
    """Body with complex call (not Name or Attribute) → 'call'."""
    src = """
try:
    x = 1
except Exception:
    (lambda: None)()
"""
    node = _parse_try(src)
    fp = _fingerprint_try_block(node)
    assert "call" in fp["handlers"][0]["actions"]


def test_fingerprint_try_block_bare_handler() -> None:
    """Bare except: → exc_type='bare'."""
    src = """
try:
    x = 1
except:
    pass
"""
    node = _parse_try(src)
    fp = _fingerprint_try_block(node)
    assert fp["handlers"][0]["exception_type"] == "bare"


# ---------------------------------------------------------------------------
# _is_route_decorator — path coverage
# ---------------------------------------------------------------------------


def test_is_route_decorator_false_for_constant() -> None:
    """Decorator that is neither Call/Attribute/Name → returns False."""
    # Build a Constant node as decorator (unusual, but tests the fallback)
    const = ast.Constant(value=42)
    assert _is_route_decorator(const) is False


# ---------------------------------------------------------------------------
# _decorator_name — path coverage
# ---------------------------------------------------------------------------


def test_decorator_name_returns_empty_for_constant() -> None:
    """Non-Attribute, non-Name, non-Call decorator → returns ''."""
    const = ast.Constant(value="foo")
    assert _decorator_name(const) == ""


# ---------------------------------------------------------------------------
# _fingerprint_endpoint — auth body_name + body_attr branches
# ---------------------------------------------------------------------------


def _parse_func(source: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            return node
    pytest.fail("No FunctionDef found")


def test_fingerprint_endpoint_auth_body_name() -> None:
    """Function with @get and Depends usage → auth via body_name."""
    src = """
@get("/items")
def list_items():
    user = Depends(get_current_user)
    return []
"""
    node = _parse_func(src)
    fp = _fingerprint_endpoint(node)
    assert fp is not None
    assert fp["has_auth"] is True
    assert fp["auth_mechanism"] == "body_name"


def test_fingerprint_endpoint_auth_body_attr() -> None:
    """Function with @post and request.user access → auth via body_attr."""
    src = """
@post("/items")
def create_item(request):
    user = request.user
    return {}
"""
    node = _parse_func(src)
    fp = _fingerprint_endpoint(node)
    assert fp is not None
    assert fp["has_auth"] is True
    assert fp["auth_mechanism"] == "body_attr"


def test_fingerprint_endpoint_no_route_returns_none() -> None:
    """Function without route decorator → returns None."""
    src = """
def plain_function():
    return 1
"""
    node = _parse_func(src)
    fp = _fingerprint_endpoint(node)
    assert fp is None


# ---------------------------------------------------------------------------
# _fingerprint_return_strategy — returns None when < 2 strategies
# ---------------------------------------------------------------------------


def test_fingerprint_return_strategy_returns_none_for_single() -> None:
    """Function with only one return strategy → returns None."""
    src = """
def single_strategy():
    if x:
        return 1
    return 2
"""
    node = _parse_func(src)
    # Both return 1 and return 2 are "return_value" => single strategy => None
    result = _fingerprint_return_strategy(node)
    assert result is None


def test_fingerprint_return_strategy_returns_dict_for_mixed() -> None:
    """Function with return_none and return_value → returns dict."""
    src = """
def mixed():
    if condition:
        return None
    return {"key": "value"}
"""
    node = _parse_func(src)
    result = _fingerprint_return_strategy(node)
    assert result is not None
    assert "strategies" in result
    assert len(result["strategies"]) >= 2


# ---------------------------------------------------------------------------
# _classify_return_strategy — all branches
# ---------------------------------------------------------------------------


def test_classify_return_strategy_none_value() -> None:
    node = ast.Return(value=ast.Constant(value=None))
    assert _classify_return_strategy(node) == "return_none"


def test_classify_return_strategy_no_value() -> None:
    node = ast.Return(value=None)
    assert _classify_return_strategy(node) == "return_none"


def test_classify_return_strategy_tuple() -> None:
    node = ast.Return(value=ast.Tuple(elts=[], ctx=ast.Load()))
    assert _classify_return_strategy(node) == "return_tuple"


def test_classify_return_strategy_dict() -> None:
    node = ast.Return(value=ast.Dict(keys=[], values=[]))
    assert _classify_return_strategy(node) == "return_dict"


def test_classify_return_strategy_value() -> None:
    node = ast.Return(value=ast.Constant(value=42))
    assert _classify_return_strategy(node) == "return_value"


# ---------------------------------------------------------------------------
# PythonFileParser — edge cases
# ---------------------------------------------------------------------------


def _make_tmp_file(tmp_path: Path, content: str, name: str = "test.py") -> Path:
    f = tmp_path / name
    f.write_text(content, encoding="utf-8")
    return f


def test_parser_function_with_attribute_decorator(tmp_path: Path) -> None:
    """@module.decorator — Attribute decorator in _process_function."""
    content = """
import module

@module.decorator
def my_func(x):
    return x + 1
"""
    _make_tmp_file(tmp_path, content)
    from drift.ingestion.ast_parser import PythonFileParser

    parser = PythonFileParser(content, Path("test.py"))
    result = parser.parse()
    assert len(result.functions) == 1
    # decorator stored as attr string
    assert result.functions[0].decorators


def test_parser_function_with_call_attr_decorator(tmp_path: Path) -> None:
    """@module.method(args) — Call with Attribute func."""
    content = """
@module.method("arg")
def endpoint():
    return 1
"""
    parser = PythonFileParser(content, Path("test.py"))
    result = parser.parse()
    assert len(result.functions) == 1
    assert any("method" in d for d in result.functions[0].decorators)


def test_parser_class_with_attribute_base(tmp_path: Path) -> None:
    """Class with module.Base → ast.unparse path."""
    content = """
class MyClass(module.Base):
    pass
"""
    parser = PythonFileParser(content, Path("test.py"))
    result = parser.parse()
    assert len(result.classes) == 1
    assert any("Base" in b for b in result.classes[0].bases)


def test_parse_python_file_oserror(tmp_path: Path) -> None:
    """parse_python_file with non-existent file → parse_errors."""
    result = parse_python_file(Path("does_not_exist.py"), tmp_path)
    assert result.parse_errors


def test_parse_file_unsupported_language(tmp_path: Path) -> None:
    """parse_file with unknown language → parse_errors."""
    f = tmp_path / "foo.rust"
    f.write_text("fn main() {}", encoding="utf-8")
    result = parse_file(Path("foo.rust"), tmp_path, "rust")
    assert result.parse_errors
    assert "Unsupported" in result.parse_errors[0]


def test_parse_file_typescript_calls_ts_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """parse_file with 'typescript' language routes to ts_parser."""
    called = []

    def fake_ts_parse(file_path, repo_path, language):
        called.append(language)
        from drift.models import ParseResult
        return ParseResult(file_path=file_path, language=language)

    monkeypatch.setattr("drift.ingestion.ts_parser.parse_typescript_file", fake_ts_parse)
    f = tmp_path / "app.ts"
    f.write_text("const x = 1;", encoding="utf-8")
    parse_file(Path("app.ts"), tmp_path, "typescript")
    assert called == ["typescript"]
