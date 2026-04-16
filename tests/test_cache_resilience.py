"""Resilience tests for disk-backed parse cache."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest

from drift.cache import _PARSE_CACHE_VERSION, ParseCache
from drift.embeddings import EmbeddingCache
from drift.models import ParseResult


def test_file_hash_uses_128_bit_prefix(tmp_path: Path) -> None:
    src = tmp_path / "a.py"
    src.write_text("print('ok')\n", encoding="utf-8")

    h = ParseCache.file_hash(src)
    assert len(h) == 32


def test_get_corrupted_cache_entry_returns_none_and_deletes_file(tmp_path: Path) -> None:
    cache = ParseCache(tmp_path)
    content_hash = "deadbeefdeadbeef"
    cache_file = tmp_path / "parse" / f"{content_hash}.json"
    cache_file.write_text("{not-valid-json", encoding="utf-8")

    result = cache.get(content_hash)

    assert result is None
    assert not cache_file.exists()


def test_put_swallows_oserror_on_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cache = ParseCache(tmp_path)
    parse_result = ParseResult(file_path=Path("a.py"), language="python")

    def _raise_oserror(*_args: object, **_kwargs: object) -> str:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", _raise_oserror)  # type: ignore[attr-defined]

    # Cache failures must never crash analysis.
    cache.put("cafebabecafebabe", parse_result)


def test_concurrent_put_get_does_not_crash(tmp_path: Path) -> None:
    cache = ParseCache(tmp_path)

    def _worker(i: int) -> None:
        h = f"{i:032x}"
        result = ParseResult(file_path=Path(f"f{i}.py"), language="python")
        cache.put(h, result)
        _ = cache.get(h)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(_worker, range(64)))


def test_parse_cache_version_mismatch_evicts_entry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """get() must evict and return None when _v doesn't match."""
    import json

    cache = ParseCache(tmp_path)
    content_hash = "aabbccddeeff0011" * 2
    result = ParseResult(file_path=Path("a.py"), language="python")
    cache.put(content_hash, result)

    # Tamper with the stored _v to simulate a future/past schema version.
    cache_file = tmp_path / "parse" / f"{content_hash}.json"
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    data["_v"] = _PARSE_CACHE_VERSION + 999
    cache_file.write_text(json.dumps(data), encoding="utf-8")

    assert cache.get(content_hash) is None
    assert not cache_file.exists()


def test_parse_cache_drift_version_mismatch_evicts_entry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """get() must evict and return None when _drift_v doesn't match."""
    import json

    cache = ParseCache(tmp_path)
    content_hash = "1122334455667788" * 2
    result = ParseResult(file_path=Path("b.py"), language="python")
    cache.put(content_hash, result)

    cache_file = tmp_path / "parse" / f"{content_hash}.json"
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    data["_drift_v"] = "0.0.0-stale"
    cache_file.write_text(json.dumps(data), encoding="utf-8")

    assert cache.get(content_hash) is None
    assert not cache_file.exists()


def test_parse_cache_roundtrip_with_version_tags(tmp_path: Path) -> None:
    """put() + get() round-trip succeeds when versions match."""
    cache = ParseCache(tmp_path)
    content_hash = "ffeeddccbbaa9988" * 2
    result = ParseResult(file_path=Path("c.py"), language="python")
    cache.put(content_hash, result)

    recovered = cache.get(content_hash)
    assert recovered is not None
    assert recovered.file_path == Path("c.py")


def test_embedding_cache_init_swallows_mkdir_oserror(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _raise_oserror(*_args: object, **_kwargs: object) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "mkdir", _raise_oserror)

    # Embedding cache init must fail open.
    cache = EmbeddingCache(tmp_path)
    assert cache._dir is None


def test_embedding_cache_put_swallows_oserror_on_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cache = EmbeddingCache(tmp_path)

    def _raise_oserror(*_args: object, **_kwargs: object) -> int:
        raise OSError("disk full")

    monkeypatch.setattr("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
    monkeypatch.setattr(Path, "write_bytes", _raise_oserror)

    # Write failures must never crash analysis.
    cache.put("hello", np.array([1.0, 2.0], dtype=np.float32))
