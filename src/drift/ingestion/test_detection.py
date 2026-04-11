"""Centralized detection of test and generated files for finding triage."""

from __future__ import annotations

import re
from pathlib import Path

_TEST_FILE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|/)__tests__/(?:|.*)$"),
    re.compile(r"(?:^|/)__mocks__/(?:|.*)$"),
    re.compile(r"(?:^|/)__fixtures__/(?:|.*)$"),
    re.compile(r"(?:^|/)test-(?:support|helpers)/(?:|.*)$"),
    re.compile(r"(^|/)conftest\.py$"),
    re.compile(r"(^|/)test_[^/]+\.py$"),
    re.compile(r"(^|/)[^/]+_test\.py$"),
    re.compile(r"\.(?:test|spec)\.[tj]sx?$"),
    re.compile(r"\.test-(?:harness|helpers)\.[tj]sx?$"),
    re.compile(r"\.stories\.[tj]sx?$"),
)

_GENERATED_FILE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|/)generated/(?:|.*)$"),
    re.compile(r"(?:^|/)gen/(?:|.*)$"),
)


def _to_posix_lower(path: Path | str) -> str:
    if isinstance(path, Path):
        return path.as_posix().lower()
    return path.replace("\\", "/").lower()


def is_test_file(path: Path | str) -> bool:
    """Return ``True`` when path matches common test/spec/fixture layouts."""
    value = _to_posix_lower(path)
    if (
        ("/tests/" in value or value.startswith("tests/"))
        and "/tests/fixtures/" not in value
        and not value.startswith("tests/fixtures/")
    ):
        return True
    if (
        ("/test/" in value or value.startswith("test/"))
        and "/test/fixtures/" not in value
        and not value.startswith("test/fixtures/")
    ):
        return True
    if "/testdata/" in value or value.startswith("testdata/"):
        return True
    return any(pattern.search(value) for pattern in _TEST_FILE_PATTERNS)


def is_generated_file(path: Path | str) -> bool:
    """Return ``True`` when path indicates generated source code."""
    value = _to_posix_lower(path)
    return any(pattern.search(value) for pattern in _GENERATED_FILE_PATTERNS)


def classify_file_context(path: Path | str) -> str:
    """Classify path as ``test``, ``generated`` or ``production``."""
    if is_test_file(path):
        return "test"
    if is_generated_file(path):
        return "generated"
    return "production"
