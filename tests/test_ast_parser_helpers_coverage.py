"""Coverage tests for ast_parser helpers:
_fingerprint_try_block, _fingerprint_endpoint, _is_route_decorator,
_decorator_name, _has_auth_decorator, _classify_return_strategy."""

from __future__ import annotations

import ast
import textwrap

from drift.ingestion.ast_parser import (
    _classify_return_strategy,
    _decorator_name,
    _fingerprint_endpoint,
    _fingerprint_try_block,
    _has_auth_decorator,
    _is_route_decorator,
)


def _parse_func(src: str) -> ast.FunctionDef:
    tree = ast.parse(textwrap.dedent(src))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    raise ValueError("no function found")


def _parse_try(src: str) -> ast.Try:
    tree = ast.parse(textwrap.dedent(src))
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            return node
    raise ValueError("no try found")


# ── _fingerprint_try_block ───────────────────────────────────────


class TestFingerprintTryBlock:
    def test_single_handler_raise(self):
        node = _parse_try("""\
        try:
            x = 1
        except ValueError:
            raise
        """)
        fp = _fingerprint_try_block(node)
        assert fp["handler_count"] == 1
        assert fp["handlers"][0]["exception_type"] == "ValueError"
        assert "raise" in fp["handlers"][0]["actions"]

    def test_bare_except_pass(self):
        node = _parse_try("""\
        try:
            x = 1
        except:
            pass
        """)
        fp = _fingerprint_try_block(node)
        assert fp["handlers"][0]["exception_type"] == "bare"
        assert "pass" in fp["handlers"][0]["actions"]

    def test_handler_with_return(self):
        node = _parse_try("""\
        try:
            x = 1
        except Exception:
            return None
        """)
        fp = _fingerprint_try_block(node)
        assert "return" in fp["handlers"][0]["actions"]

    def test_handler_with_log(self):
        node = _parse_try("""\
        try:
            x = 1
        except Exception:
            logger.error("fail")
        """)
        fp = _fingerprint_try_block(node)
        assert "log" in fp["handlers"][0]["actions"]

    def test_handler_with_print(self):
        node = _parse_try("""\
        try:
            x = 1
        except Exception:
            print("fail")
        """)
        fp = _fingerprint_try_block(node)
        assert "print" in fp["handlers"][0]["actions"]

    def test_handler_fallback_assign(self):
        node = _parse_try("""\
        try:
            x = 1
        except Exception:
            x = 0
        """)
        fp = _fingerprint_try_block(node)
        assert "fallback_assign" in fp["handlers"][0]["actions"]

    def test_tuple_exception(self):
        node = _parse_try("""\
        try:
            x = 1
        except (ValueError, TypeError):
            pass
        """)
        fp = _fingerprint_try_block(node)
        assert "ValueError" in fp["handlers"][0]["exception_type"]

    def test_finally(self):
        node = _parse_try("""\
        try:
            x = 1
        except Exception:
            pass
        finally:
            cleanup()
        """)
        fp = _fingerprint_try_block(node)
        assert fp["has_finally"] is True

    def test_else(self):
        node = _parse_try("""\
        try:
            x = 1
        except Exception:
            pass
        else:
            y = 2
        """)
        fp = _fingerprint_try_block(node)
        assert fp["has_else"] is True


# ── _is_route_decorator ──────────────────────────────────────────


class TestIsRouteDecorator:
    def test_attribute(self):
        dec = ast.parse("@app.get\ndef f(): pass").body[0].decorator_list[0]
        assert _is_route_decorator(dec) is True

    def test_name(self):
        dec = ast.parse("@route\ndef f(): pass").body[0].decorator_list[0]
        assert _is_route_decorator(dec) is True

    def test_call(self):
        dec = ast.parse("@app.post('/api')\ndef f(): pass").body[0].decorator_list[0]
        assert _is_route_decorator(dec) is True

    def test_not_route(self):
        dec = ast.parse("@staticmethod\ndef f(): pass").body[0].decorator_list[0]
        assert _is_route_decorator(dec) is False


# ── _decorator_name ──────────────────────────────────────────────


class TestDecoratorName:
    def test_simple_name(self):
        dec = ast.parse("@foo\ndef f(): pass").body[0].decorator_list[0]
        assert _decorator_name(dec) == "foo"

    def test_attribute(self):
        dec = ast.parse("@mod.bar\ndef f(): pass").body[0].decorator_list[0]
        assert _decorator_name(dec) == "bar"

    def test_call(self):
        dec = ast.parse("@mod.baz()\ndef f(): pass").body[0].decorator_list[0]
        assert _decorator_name(dec) == "baz"


# ── _has_auth_decorator ──────────────────────────────────────────


class TestHasAuthDecorator:
    def test_login_required(self):
        func = _parse_func("""\
        @login_required
        def view(request):
            pass
        """)
        assert _has_auth_decorator(func) is True

    def test_no_auth(self):
        func = _parse_func("""\
        @staticmethod
        def view():
            pass
        """)
        assert _has_auth_decorator(func) is False


# ── _fingerprint_endpoint ────────────────────────────────────────


class TestFingerprintEndpoint:
    def test_no_route(self):
        func = _parse_func("""\
        def helper():
            pass
        """)
        assert _fingerprint_endpoint(func) is None

    def test_basic_endpoint(self):
        func = _parse_func("""\
        @app.get
        def list_items():
            return items()
        """)
        fp = _fingerprint_endpoint(func)
        assert fp is not None
        assert fp["is_async"] is False

    def test_endpoint_with_try(self):
        func = _parse_func("""\
        @app.post
        def create():
            try:
                save()
            except Exception:
                pass
        """)
        fp = _fingerprint_endpoint(func)
        assert fp["has_error_handling"] is True

    def test_endpoint_auth_decorator(self):
        func = _parse_func("""\
        @app.get
        @login_required
        def protected():
            pass
        """)
        fp = _fingerprint_endpoint(func)
        assert fp["has_auth"] is True
        assert fp["auth_mechanism"] == "decorator"


# ── _classify_return_strategy ────────────────────────────────────


class TestClassifyReturnStrategy:
    def test_return_none(self):
        node = ast.parse("return").body[0]
        assert _classify_return_strategy(node) == "return_none"

    def test_return_none_literal(self):
        node = ast.parse("return None").body[0]
        assert _classify_return_strategy(node) == "return_none"
