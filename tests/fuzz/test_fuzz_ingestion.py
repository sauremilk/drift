"""Fuzz tests for the ingestion layer (ast_parser.parse_python_file).

Invariants verified:
- parse_python_file never raises an uncaught exception on arbitrary text input.
- The returned ParseResult always carries a file_path and language.
- parse_errors are strings when present (not None or other types).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from drift.ingestion.ast_parser import parse_python_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),  # no surrogates
    max_size=4_096,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.fuzz
@given(source=_safe_text)
def test_parse_python_file_never_crashes(source: str) -> None:
    """parse_python_file must never raise on arbitrary text written to a .py file."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        src_file = repo / "fuzz_target.py"
        src_file.write_text(source, encoding="utf-8")

        result = parse_python_file(src_file, repo)

    # Basic shape invariants
    assert result.file_path is not None
    assert result.language == "python"
    # parse_errors must be a list of strings (not mixed types)
    assert isinstance(result.parse_errors, list)
    for err in result.parse_errors:
        assert isinstance(err, str)


@pytest.mark.fuzz
@given(source=_safe_text)
def test_parse_python_file_line_count_non_negative(source: str) -> None:
    """Parsed line_count must always be >= 0."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        src_file = repo / "fuzz_lc.py"
        src_file.write_text(source, encoding="utf-8")

        result = parse_python_file(src_file, repo)

    assert result.line_count >= 0


@pytest.mark.fuzz
@given(
    source=st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            # Include common Python keywords/symbols to trigger AST paths
            whitelist_characters="abcdefghijklmnopqrstuvwxyz _:=()[]{}.,\n#\"'0123456789",
        ),
        min_size=0,
        max_size=2_048,
    )
)
def test_parse_python_file_valid_syntax_no_errors(source: str) -> None:
    """Valid Python syntax must produce no parse_errors."""
    import ast

    try:
        ast.parse(source)
    except SyntaxError:
        return  # not valid Python — skip this example

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        src_file = repo / "fuzz_valid.py"
        src_file.write_text(source, encoding="utf-8")

        result = parse_python_file(src_file, repo)

    # Valid Python should parse without errors
    assert result.parse_errors == []


# ---------------------------------------------------------------------------
# TypeScript parser fuzz tests
# ---------------------------------------------------------------------------


_ts_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),  # no surrogates
    max_size=4_096,
)


@pytest.mark.fuzz
@given(source=_ts_text)
def test_parse_typescript_file_never_crashes(source: str) -> None:
    """parse_typescript_file must never raise on arbitrary text written to a .ts file."""
    from drift.ingestion.ts_parser import parse_typescript_file

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        src_file = repo / "fuzz_target.ts"
        src_file.write_text(source, encoding="utf-8")

        result = parse_typescript_file(Path("fuzz_target.ts"), repo)

    assert result.file_path is not None
    assert result.language in ("typescript", "tsx", "javascript")
    assert isinstance(result.parse_errors, list)
    for err in result.parse_errors:
        assert isinstance(err, str)


@pytest.mark.fuzz
@given(source=_ts_text)
def test_parse_typescript_file_line_count_non_negative(source: str) -> None:
    """Parsed TypeScript line_count must always be >= 0."""
    from drift.ingestion.ts_parser import parse_typescript_file

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        src_file = repo / "fuzz_lc.ts"
        src_file.write_text(source, encoding="utf-8")

        result = parse_typescript_file(Path("fuzz_lc.ts"), repo)

    assert result.line_count >= 0
