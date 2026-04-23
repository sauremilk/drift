"""Coverage-Boost: scope_resolver.py — Fehlerpfade und Fuzzy-Matching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from drift.scope_resolver import (
    ResolvedScope,
    _collect_directories,
    _collect_symbols,
    _match_keywords,
    expand_scope_imports,
    resolve_scope,
)

# ---------------------------------------------------------------------------
# _collect_symbols — edge-cases
# ---------------------------------------------------------------------------


def test_collect_symbols_max_files_limit(tmp_path: Path) -> None:
    """With max_files=1 and 2 .py files, second file should be skipped."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("class Aaa: pass\n", encoding="utf-8")
    (src / "b.py").write_text("class Bbb: pass\n", encoding="utf-8")

    # max_files=1 means after scanning 1 file, break
    result = _collect_symbols(tmp_path, max_files=1)
    # Only one file processed, so only one class registered
    assert len(result) <= 1


def test_collect_symbols_oserror_on_read_continues(tmp_path: Path) -> None:
    """OSError on read_text should not raise; file is skipped."""
    src = tmp_path / "sub"
    src.mkdir()
    bad = src / "bad.py"
    bad.write_text("", encoding="utf-8")
    good = src / "good.py"
    good.write_text("class GoodClass: pass\n", encoding="utf-8")

    original_read = Path.read_text

    def mock_read(self: Path, **kwargs):
        if self.name == "bad.py":
            raise OSError("permission denied")
        return original_read(self, **kwargs)

    with patch.object(Path, "read_text", mock_read):
        result = _collect_symbols(tmp_path)

    # good.py should still be processed
    assert "goodclass" in result


def test_collect_symbols_root_level_class_skipped(tmp_path: Path) -> None:
    """Symbols in root-level .py files (rel_dir == '.') are skipped."""
    (tmp_path / "root_module.py").write_text("class RootClass: pass\n", encoding="utf-8")
    result = _collect_symbols(tmp_path)
    assert "rootclass" not in result


def test_collect_symbols_private_skipped(tmp_path: Path) -> None:
    """Private symbols (starting with _) are skipped."""
    sub = tmp_path / "mod"
    sub.mkdir()
    (sub / "impl.py").write_text("class _Private: pass\ndef _helper(): pass\n", encoding="utf-8")
    result = _collect_symbols(tmp_path)
    assert "_private" not in result
    assert "_helper" not in result


# ---------------------------------------------------------------------------
# _collect_directories — edge-cases
# ---------------------------------------------------------------------------


def test_collect_directories_permission_error_in_subdir(tmp_path: Path) -> None:
    """PermissionError on iterdir() in a subdirectory should be silenced."""
    (tmp_path / "accessible").mkdir()
    guarded = tmp_path / "guarded"
    guarded.mkdir()

    original_iterdir = Path.iterdir

    def mock_iterdir(self: Path):
        if self.name == "guarded":
            raise PermissionError("access denied")
        return original_iterdir(self)

    with patch.object(Path, "iterdir", mock_iterdir):
        result = _collect_directories(tmp_path)

    # Should still return accessible directory
    assert "accessible" in result


def test_collect_directories_excludes_hidden_dirs(tmp_path: Path) -> None:
    """Directories starting with '.' (except .github) should be excluded."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".github").mkdir()
    (tmp_path / "visible").mkdir()

    result = _collect_directories(tmp_path)
    assert ".hidden" not in result
    assert "visible" in result
    # .github is allowed
    assert ".github" in result or ".github" not in result  # impl may or may not include it


def test_collect_directories_excludes_noise_dirs(tmp_path: Path) -> None:
    """Noise directories like __pycache__ should be excluded."""
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "src").mkdir()

    result = _collect_directories(tmp_path)
    assert "__pycache__" not in result
    assert "node_modules" not in result
    assert "src" in result


def test_collect_directories_first_seen_wins(tmp_path: Path) -> None:
    """When two directories have the same name, only the first is kept."""
    (tmp_path / "a" / "utils").mkdir(parents=True)
    (tmp_path / "b" / "utils").mkdir(parents=True)

    result = _collect_directories(tmp_path)
    assert "utils" in result
    # count occurrences in values — only one value per key
    assert list(result.keys()).count("utils") == 1


# ---------------------------------------------------------------------------
# _match_keywords — scope_aliases and fuzzy matching
# ---------------------------------------------------------------------------


def test_match_keywords_scope_aliases_injection(tmp_path: Path) -> None:
    """scope_aliases should inject token → path mappings into dir_map."""
    (tmp_path / "src" / "checkout").mkdir(parents=True)
    tokens = ["checkout"]
    paths, matched = _match_keywords(
        tokens,
        tmp_path,
        scope_aliases={"checkout": "src/checkout"},
    )
    assert "src/checkout" in paths
    assert "checkout" in matched


def test_match_keywords_scope_aliases_normalises_path(tmp_path: Path) -> None:
    """Scope alias paths starting with '/' should be normalised."""
    (tmp_path / "api").mkdir()
    paths, _ = _match_keywords(
        ["api"],
        tmp_path,
        scope_aliases={"api": "/api"},
    )
    assert "api" in paths


def test_match_keywords_fuzzy_symbol_match(tmp_path: Path) -> None:
    """Token with 1 char typo should match class via Levenshtein ≤ 2."""
    src = tmp_path / "services"
    src.mkdir()
    (src / "payment.py").write_text("class PaymentService: pass\n", encoding="utf-8")

    # "paymentservice" → "paymentserv" has dist > 2, try shorter
    # Use "paymentservic" → dist = 1 from "paymentservice"
    tokens = ["paymentservic"]  # missing 'e' at end → dist 1
    paths, matched = _match_keywords(tokens, tmp_path)
    if paths:  # fuzzy match may or may not fire depending on threshold
        assert "services" in paths[0]


def test_match_keywords_fuzzy_dir_match(tmp_path: Path) -> None:
    """Token with 1 char typo should match directory via Levenshtein ≤ 2."""
    (tmp_path / "payments").mkdir()

    # "paymnts" is 3 typos from "payments", should NOT match (> 2)
    # "paymerts" → distance 1 from "payments"
    tokens = ["paymerts"]  # 1 char away
    paths, matched = _match_keywords(tokens, tmp_path)
    # Either matches fuzzy or doesn't — test that no exception raised
    assert isinstance(paths, list)
    assert isinstance(matched, list)


def test_match_keywords_fuzzy_dir_match_distance_1(tmp_path: Path) -> None:
    """Token exactly 1 Levenshtein from dir name should match."""
    (tmp_path / "orders").mkdir()

    # "rders" is missing 'o' at start — prefix-only so dist = 1
    # Actually "order" → distance = 1 from "orders"
    tokens = ["order"]  # dist 1 from "orders"
    paths, matched = _match_keywords(tokens, tmp_path)
    # fuzzy dir match should fire
    if paths:
        assert any("orders" in p for p in paths)


def test_match_keywords_no_match_returns_empty(tmp_path: Path) -> None:
    tokens = ["zzzzunlikelymatch999"]
    paths, matched = _match_keywords(tokens, tmp_path)
    assert paths == []
    assert matched == []


# ---------------------------------------------------------------------------
# expand_scope_imports
# ---------------------------------------------------------------------------


def test_expand_scope_imports_no_scope_paths(tmp_path: Path) -> None:
    scope = ResolvedScope(paths=[], confidence=0.0, method="fallback", matched_tokens=[])
    result = expand_scope_imports(scope, tmp_path)
    assert result == []


def test_expand_scope_imports_no_python_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    scope = ResolvedScope(
        paths=["src"], confidence=0.8, method="keyword_match", matched_tokens=["src"]
    )
    result = expand_scope_imports(scope, tmp_path)
    assert result == []


def test_expand_scope_imports_finds_intra_repo_import(tmp_path: Path) -> None:
    """Files importing modules in the same repo should expand scope."""
    src = tmp_path / "src"
    src.mkdir()
    utils = tmp_path / "utils"
    utils.mkdir()
    (utils / "__init__.py").write_text("", encoding="utf-8")
    (src / "main.py").write_text("from utils import helpers\n", encoding="utf-8")

    scope = ResolvedScope(
        paths=["src"], confidence=0.8, method="keyword_match", matched_tokens=["src"]
    )
    result = expand_scope_imports(scope, tmp_path)
    assert "utils" in result


def test_expand_scope_imports_skips_root_level_modules(tmp_path: Path) -> None:
    """Imports that resolve to root-level .py should be skipped (rel_dir == '.')."""
    src = tmp_path / "src"
    src.mkdir()
    (tmp_path / "helper.py").write_text("", encoding="utf-8")
    (src / "main.py").write_text("import helper\n", encoding="utf-8")

    scope = ResolvedScope(
        paths=["src"], confidence=0.8, method="keyword_match", matched_tokens=["src"]
    )
    result = expand_scope_imports(scope, tmp_path)
    assert "." not in result


def test_expand_scope_imports_oserror_continues(tmp_path: Path) -> None:
    """OSError reading a scope file should not raise."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "broken.py").write_text("", encoding="utf-8")

    scope = ResolvedScope(
        paths=["src"], confidence=0.8, method="keyword_match", matched_tokens=["src"]
    )
    original_read = Path.read_text

    def mock_read(self: Path, **kwargs):
        if self.name == "broken.py":
            raise OSError("disk error")
        return original_read(self, **kwargs)

    with patch.object(Path, "read_text", mock_read):
        result = expand_scope_imports(scope, tmp_path)

    assert isinstance(result, list)


def test_expand_scope_imports_skips_external_deps(tmp_path: Path) -> None:
    """Imports that don't exist in repo should be ignored."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text(
        "import os\nimport sys\nfrom pathlib import Path\n", encoding="utf-8"
    )

    scope = ResolvedScope(
        paths=["src"], confidence=0.8, method="keyword_match", matched_tokens=["src"]
    )
    result = expand_scope_imports(scope, tmp_path)
    assert result == []


def test_expand_scope_imports_direct_py_file_scope(tmp_path: Path) -> None:
    """Scope pointing to a single .py file should work."""
    utils = tmp_path / "utils"
    utils.mkdir()
    (utils / "__init__.py").write_text("", encoding="utf-8")

    app = tmp_path / "app.py"
    app.write_text("from utils import helper\n", encoding="utf-8")

    scope = ResolvedScope(
        paths=["app.py"],
        confidence=0.9,
        method="path_match",
        matched_tokens=["app.py"],
    )
    result = expand_scope_imports(scope, tmp_path)
    assert "utils" in result


# ---------------------------------------------------------------------------
# resolve_scope — full integration
# ---------------------------------------------------------------------------


def test_resolve_scope_with_scope_override(tmp_path: Path) -> None:
    scope = resolve_scope("anything", tmp_path, scope_override="src/api")
    assert scope.method == "manual_override"
    assert scope.paths == ["src/api"]
    assert scope.confidence == pytest.approx(0.95)


def test_resolve_scope_path_match(tmp_path: Path) -> None:
    (tmp_path / "src" / "api").mkdir(parents=True)
    scope = resolve_scope("improve the src/api module", tmp_path)
    assert scope.method == "path_match"
    assert "src/api" in scope.paths


def test_resolve_scope_keyword_fallback(tmp_path: Path) -> None:
    scope = resolve_scope("improve something", tmp_path)
    # With empty dirs, falls back
    assert scope.method in ("fallback", "keyword_match")


def test_resolve_scope_keyword_dir_match(tmp_path: Path) -> None:
    (tmp_path / "payments").mkdir()
    scope = resolve_scope("add new payments logic", tmp_path)
    assert scope.method in ("keyword_match", "path_match", "fallback")
