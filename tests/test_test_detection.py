from __future__ import annotations

from pathlib import Path

from drift.ingestion.test_detection import classify_file_context, is_generated_file, is_test_file


def test_is_test_file_patterns() -> None:
    assert is_test_file(Path("tests/test_api.py"))
    assert is_test_file(Path("src/foo_test.py"))
    assert is_test_file(Path("src/app.spec.ts"))
    assert is_test_file(Path("extensions/discord/src/send.test-harness.ts"))
    assert is_test_file(Path("extensions/shared/src/time.test-helpers.ts"))
    assert is_test_file(Path("src/__tests__/api.ts"))
    assert is_test_file(Path("src/test-support/mocks.ts"))
    assert is_test_file(Path("src/test-helpers/factories.ts"))
    assert is_test_file(Path("tests/conftest.py"))
    assert not is_test_file(Path("src/app.py"))


def test_is_generated_file_patterns() -> None:
    assert is_generated_file(Path("src/generated/client.py"))
    assert is_generated_file(Path("src/gen/types.ts"))
    assert not is_generated_file(Path("src/core/service.py"))


def test_classify_file_context() -> None:
    assert classify_file_context(Path("tests/test_api.py")) == "test"
    assert classify_file_context(Path("src/generated/client.py")) == "generated"
    assert classify_file_context(Path("src/core/service.py")) == "production"
