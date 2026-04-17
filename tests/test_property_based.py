"""Property-based tests for Drift's parsing and config boundaries.

These tests fuzz the system boundary functions that receive external input:
- YAML/config parsing (DriftConfig.load)
- File path pattern matching (_matches_any)
- File discovery on arbitrary directory structures

Each test asserts a safety property: the function must never crash with an
unexpected exception regardless of input shape.  DriftConfigError,
ValidationError, and ValueError are expected — everything else is a bug.

CI budget: @settings(max_examples=50) keeps the full suite under ~10 seconds.
"""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from drift.config import DriftConfig
from drift.errors import DriftConfigError
from drift.ingestion.file_discovery import _matches_any, discover_files

# ---------------------------------------------------------------------------
# Strategy helpers
# ---------------------------------------------------------------------------

# Printable ASCII strings that could appear in YAML values
_yaml_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    max_size=64,
)

# Relative path segments — no drive letters, no null bytes
_path_segment = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="-_.",
        blacklist_characters="/\\:\x00",
    ),
    min_size=1,
    max_size=20,
)

# File path strings with forward slashes (platform-normalised)
_file_path_str = st.builds(
    lambda parts: "/".join(parts),
    st.lists(_path_segment, min_size=1, max_size=5),
)

# Glob patterns similar to what appear in include/exclude config lists
_glob_pattern = st.one_of(
    st.just("**/*.py"),
    st.just("**/node_modules/**"),
    st.just("**/__pycache__/**"),
    st.builds(lambda seg: f"**/{seg}/**", _path_segment),
    st.builds(lambda seg: f"**/*.{seg}", _path_segment),
    _file_path_str,
)


# ---------------------------------------------------------------------------
# 1. Config YAML parser: never raises unexpected exceptions
# ---------------------------------------------------------------------------


@given(content=st.text(max_size=512))
@settings(
    max_examples=50,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
    ],
)
def test_config_load_from_yaml_never_raises_unexpected(content: str) -> None:
    """DriftConfig.load must only raise DriftConfigError on malformed YAML input.

    Any other exception (AttributeError, KeyError, IndexError, ...) is a bug.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        config_file = tmp / "drift.yaml"
        config_file.write_text(content, encoding="utf-8")
        with contextlib.suppress(DriftConfigError):
            DriftConfig.load(tmp, config_path=config_file)


@given(data=st.dictionaries(st.text(max_size=20), _yaml_safe_text, max_size=8))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_config_model_validate_never_raises_unexpected(data: dict) -> None:
    """DriftConfig.model_validate must only raise ValidationError on invalid data."""
    with contextlib.suppress(ValidationError, DriftConfigError):
        DriftConfig.model_validate(data)


# ---------------------------------------------------------------------------
# 2. Pattern matching: always returns a bool, never crashes
# ---------------------------------------------------------------------------


@given(path_str=_file_path_str, patterns=st.lists(_glob_pattern, max_size=6))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_matches_any_always_returns_bool(path_str: str, patterns: list[str]) -> None:
    """_matches_any must return a bool for any combination of path and patterns."""
    result = _matches_any(path_str, patterns)
    assert isinstance(result, bool)


@given(path_str=st.text(max_size=200), patterns=st.just([]))
@settings(max_examples=50)
def test_matches_any_empty_patterns_always_false(path_str: str, patterns: list[str]) -> None:
    """Empty pattern list must always return False."""
    assert _matches_any(path_str, patterns) is False


# ---------------------------------------------------------------------------
# 3. File discovery: terminates and returns a list for any valid repo path
# ---------------------------------------------------------------------------


@given(
    include=st.lists(_glob_pattern, min_size=1, max_size=3),
    exclude=st.lists(_glob_pattern, max_size=3),
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
    ],
)
def test_discover_files_terminates_on_empty_repo(include: list[str], exclude: list[str]) -> None:
    """discover_files on an empty directory must terminate and return a list."""
    with tempfile.TemporaryDirectory() as td:
        result = discover_files(Path(td), include=include, exclude=exclude, max_files=100)
        assert isinstance(result, list)


@given(
    file_names=st.lists(
        st.builds(lambda seg: f"{seg}.py", _path_segment),
        min_size=1,
        max_size=5,
        unique=True,
    )
)
@settings(
    max_examples=30,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
    ],
)
def test_discover_files_finds_all_python_files(file_names: list[str]) -> None:
    """discover_files must return at least the Python files placed in the repo root."""
    # Deduplicate case-insensitively for case-insensitive filesystems (Windows/macOS)
    seen: set[str] = set()
    unique_names: list[str] = []
    for name in file_names:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            unique_names.append(name)
    file_names = unique_names

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name in file_names:
            (tmp / name).write_text("x = 1\n", encoding="utf-8")

        result = discover_files(tmp, include=["**/*.py"], exclude=[], max_files=1000)
        found_names = {f.path.name for f in result}
        for name in file_names:
            assert name in found_names, f"{name} not found in {found_names}"
