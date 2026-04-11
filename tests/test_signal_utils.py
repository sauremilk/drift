"""Tests for drift.signals._utils."""

from __future__ import annotations

from pathlib import Path

from drift.signals._utils import is_test_file


class TestIsTestFile:
    # ── Python patterns ──────────────────────────────────────────

    def test_python_test_prefix(self):
        assert is_test_file(Path("tests/test_foo.py"))

    def test_python_test_suffix(self):
        assert is_test_file(Path("src/foo_test.py"))

    def test_python_production_file(self):
        assert not is_test_file(Path("src/module.py"))

    # ── TypeScript patterns ──────────────────────────────────────

    def test_ts_dot_test(self):
        assert is_test_file(Path("src/module.test.ts"))

    def test_ts_dot_spec(self):
        assert is_test_file(Path("src/module.spec.ts"))

    def test_tsx_dot_test(self):
        assert is_test_file(Path("src/component.test.tsx"))

    def test_tsx_dot_spec(self):
        assert is_test_file(Path("src/component.spec.tsx"))

    # ── JavaScript patterns ──────────────────────────────────────

    def test_js_dot_test(self):
        assert is_test_file(Path("src/module.test.js"))

    def test_js_dot_spec(self):
        assert is_test_file(Path("src/module.spec.js"))

    def test_jsx_dot_test(self):
        assert is_test_file(Path("src/component.test.jsx"))

    def test_jsx_dot_spec(self):
        assert is_test_file(Path("src/component.spec.jsx"))

    # ── __tests__ directory ──────────────────────────────────────

    def test_dunder_tests_dir(self):
        assert is_test_file(Path("src/__tests__/module.ts"))

    def test_nested_dunder_tests_dir(self):
        assert is_test_file(Path("packages/core/__tests__/utils.js"))

    def test_conftest_is_test_file(self):
        assert is_test_file(Path("tests/conftest.py"))

    # ── Negative cases ───────────────────────────────────────────

    def test_ts_production_file(self):
        assert not is_test_file(Path("src/service.ts"))

    def test_tsx_production_file(self):
        assert not is_test_file(Path("src/App.tsx"))

    def test_js_production_file(self):
        assert not is_test_file(Path("src/config.js"))

    def test_init_file(self):
        assert not is_test_file(Path("src/__init__.py"))

    def test_index_file(self):
        assert not is_test_file(Path("src/index.ts"))
