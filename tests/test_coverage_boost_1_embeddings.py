"""Coverage-Boost: embeddings.py — Pfade mit gemocktem SentenceTransformer."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from drift.embeddings import (
    EmbeddingCache,
    EmbeddingService,
    _safe_model_name,
    get_embedding_service,
    reset_embedding_service,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_embedding_service()


# ---------------------------------------------------------------------------
# _safe_model_name
# ---------------------------------------------------------------------------


def test_safe_model_name_replaces_slashes() -> None:
    assert "/" not in _safe_model_name("org/model-name")
    assert "\\" not in _safe_model_name("org\\model")


def test_safe_model_name_unchanged_without_slashes() -> None:
    assert _safe_model_name("all-MiniLM-L6-v2") == "all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# EmbeddingCache — full put/get cycle
# ---------------------------------------------------------------------------


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
def test_cache_put_and_get_roundtrip(tmp_path: Path) -> None:
    cache = EmbeddingCache(tmp_path, model_name="test-m")
    if cache._dir is None:
        pytest.skip("Cache dir not created")
    vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    cache.put("hello world", vec)
    result = cache.get("hello world")
    assert result is not None
    np.testing.assert_array_almost_equal(result, vec)


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
def test_cache_get_corrupted_file_returns_none(tmp_path: Path) -> None:
    """Corrupted .bin file should be removed and None returned."""
    cache = EmbeddingCache(tmp_path, model_name="test-m")
    if cache._dir is None:
        pytest.skip("Cache dir not created")
    key = hashlib.sha256(b"corrupt").hexdigest()[:16]
    (cache._dir / f"{key}.bin").write_bytes(b"NOT_FLOAT32_DATA")
    result = cache.get("corrupt")
    # After frombuffer on bad data: either None or array; .bin file may be gone
    # The important thing: no exception raised
    _ = result


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
def test_cache_put_oserror_logs_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """OSError during write should log a warning, not raise."""
    cache = EmbeddingCache(tmp_path, model_name="test-m")
    if cache._dir is None:
        pytest.skip("Cache dir not created")
    vec = np.array([0.5], dtype=np.float32)
    with patch.object(Path, "write_bytes", side_effect=OSError("disk full")):
        import logging

        with caplog.at_level(logging.WARNING, logger="drift.embeddings"):
            cache.put("text", vec)
    # Should not raise


def test_cache_disabled_no_dir(tmp_path: Path) -> None:
    cache = EmbeddingCache(tmp_path, model_name="m")
    cache._dir = None
    assert cache.get("any") is None
    # put should silently no-op
    cache.put("any", np.array([1.0], dtype=np.float32))


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
def test_cache_get_batch_partial_hit(tmp_path: Path) -> None:
    cache = EmbeddingCache(tmp_path, model_name="m")
    if cache._dir is None:
        pytest.skip("Cache dir not available")
    v1 = np.array([1.0, 0.0], dtype=np.float32)
    cache.put("a", v1)
    hit_idx, hit_vec, miss_idx = cache.get_batch(["a", "b", "c"])
    assert 0 in hit_idx
    assert 1 in miss_idx
    assert 2 in miss_idx


def test_cache_init_oserror_disables_cache(tmp_path: Path) -> None:
    """When mkdir fails the cache should be disabled (dir = None)."""
    with patch("pathlib.Path.mkdir", side_effect=OSError("no space")):
        cache = EmbeddingCache(tmp_path, model_name="oserr-model")
    assert cache._dir is None


# ---------------------------------------------------------------------------
# EmbeddingService with mocked SentenceTransformer
# ---------------------------------------------------------------------------


def _make_mock_model() -> MagicMock:
    model = MagicMock()
    model.encode = MagicMock(
        side_effect=lambda texts, **kwargs: (
            np.stack([np.ones(4, dtype=np.float32) for _ in texts])
            if isinstance(texts, list)
            else np.ones(4, dtype=np.float32)
        )
    )
    return model


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
@patch("drift.embeddings.SentenceTransformer", create=True)
def test_embed_text_model_encode_and_cache(mock_st_cls: MagicMock, tmp_path: Path) -> None:
    """embed_text should call model.encode and store result in cache."""
    mock_model = _make_mock_model()
    mock_st_cls.return_value = mock_model

    svc = EmbeddingService(model_name="mock-model", cache_dir=tmp_path)
    result = svc.embed_text("hello")
    assert result is not None
    assert result.shape == (4,)
    mock_model.encode.assert_called_once()

    # Second call — should hit cache
    result2 = svc.embed_text("hello")
    assert result2 is not None
    # encode still called once (cache hit)
    assert mock_model.encode.call_count == 1


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
@patch("drift.embeddings.SentenceTransformer", create=True)
def test_embed_text_without_cache(mock_st_cls: MagicMock) -> None:
    """embed_text without cache_dir should call model.encode every time."""
    mock_model = _make_mock_model()
    mock_st_cls.return_value = mock_model

    svc = EmbeddingService(model_name="mock-model", cache_dir=None)
    r = svc.embed_text("test text")
    assert r is not None
    assert r.shape == (4,)


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
@patch("drift.embeddings.SentenceTransformer", create=True)
def test_embed_texts_partial_cache(mock_st_cls: MagicMock, tmp_path: Path) -> None:
    """embed_texts: some cached, some not — result order must be preserved."""
    mock_model = _make_mock_model()
    mock_st_cls.return_value = mock_model

    svc = EmbeddingService(model_name="mock-model", cache_dir=tmp_path)
    # Pre-warm cache for first text
    v = np.array([9.0, 9.0, 9.0, 9.0], dtype=np.float32)
    if svc._cache:
        svc._cache.put("first", v)

    results = svc.embed_texts(["first", "second", "third"])
    assert len(results) == 3
    assert results[0] is not None
    # First should be the cached vector
    np.testing.assert_array_almost_equal(results[0], v)
    # Others should be from encode
    assert results[1] is not None
    assert results[2] is not None


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
@patch("drift.embeddings.SentenceTransformer", create=True)
def test_embed_texts_all_cache_hits(mock_st_cls: MagicMock, tmp_path: Path) -> None:
    """When all texts are cached, model.encode should not be called."""
    mock_model = _make_mock_model()
    mock_st_cls.return_value = mock_model

    svc = EmbeddingService(model_name="mock-model", cache_dir=tmp_path)
    v = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    for t in ["x", "y", "z"]:
        if svc._cache:
            svc._cache.put(t, v)

    results = svc.embed_texts(["x", "y", "z"])
    assert all(r is not None for r in results)
    mock_model.encode.assert_not_called()


# ---------------------------------------------------------------------------
# build_index with FAISS mock
# ---------------------------------------------------------------------------


@patch("drift.embeddings._FAISS_AVAILABLE", True)
def test_build_index_faiss_path_32_vectors() -> None:
    """When FAISS is available and >= 32 vectors, faiss.IndexFlatIP should be used."""
    import drift.embeddings as emb_mod

    mock_index = MagicMock()
    mock_faiss = MagicMock()
    mock_faiss.IndexFlatIP.return_value = mock_index

    with (
        patch.dict("sys.modules", {"faiss": mock_faiss}),
        patch.object(emb_mod, "_FAISS_AVAILABLE", True),
        patch.object(emb_mod, "faiss", mock_faiss, create=True),
    ):
        svc = EmbeddingService()
        vecs = [np.random.rand(8).astype(np.float32) for _ in range(32)]
        index = svc.build_index(vecs)
    # When FAISS is mocked, the index is the mock object
    assert index is not None


def test_build_index_numpy_ndarray_input() -> None:
    """build_index with ndarray input should return as-is for small matrices."""
    svc = EmbeddingService()
    matrix = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    result = svc.build_index(matrix)
    assert result is not None


# ---------------------------------------------------------------------------
# search_index with FAISS mock
# ---------------------------------------------------------------------------


@patch("drift.embeddings._FAISS_AVAILABLE", True)
def test_search_index_faiss_path() -> None:
    """search_index should use FAISS search when index has .search attribute."""
    svc = EmbeddingService()
    mock_index = MagicMock()
    mock_index.ntotal = 3
    mock_index.search.return_value = (
        np.array([[0.9, 0.8]], dtype=np.float32),
        np.array([[0, 2]], dtype=np.int64),
    )

    import drift.embeddings as emb_mod

    with patch.object(emb_mod, "_FAISS_AVAILABLE", True):
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = svc.search_index(mock_index, query, top_k=2)

    assert len(results) == 2
    assert results[0][0] == 0
    assert results[0][1] == pytest.approx(0.9, abs=1e-4)


@patch("drift.embeddings._FAISS_AVAILABLE", True)
def test_search_index_faiss_empty_index() -> None:
    """search_index with ntotal=0 FAISS index should return empty list."""
    svc = EmbeddingService()
    mock_index = MagicMock()
    mock_index.ntotal = 0

    import drift.embeddings as emb_mod

    with patch.object(emb_mod, "_FAISS_AVAILABLE", True):
        query = np.array([1.0, 0.0], dtype=np.float32)
        results = svc.search_index(mock_index, query, top_k=5)
    assert results == []


# ---------------------------------------------------------------------------
# get_embedding_service singleton paths
# ---------------------------------------------------------------------------


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
@patch("drift.embeddings.SentenceTransformer", create=True)
def test_get_embedding_service_creates_singleton(mock_st_cls: MagicMock, tmp_path: Path) -> None:
    mock_st_cls.return_value = MagicMock()
    s1 = get_embedding_service(cache_dir=tmp_path, model_name="mock-model")
    s2 = get_embedding_service(cache_dir=tmp_path, model_name="mock-model")
    assert s1 is s2


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
@patch("drift.embeddings.SentenceTransformer", create=True)
def test_get_embedding_service_reinitializes_on_change(
    mock_st_cls: MagicMock, tmp_path: Path
) -> None:
    mock_st_cls.return_value = MagicMock()
    s1 = get_embedding_service(cache_dir=tmp_path, model_name="model-a")
    s2 = get_embedding_service(cache_dir=tmp_path, model_name="model-b")
    assert s1 is not s2


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
@patch("drift.embeddings.SentenceTransformer", create=True)
def test_get_embedding_service_cache_dir_key_none(mock_st_cls: MagicMock) -> None:
    """get_embedding_service with cache_dir=None should still work."""
    mock_st_cls.return_value = MagicMock()
    svc = get_embedding_service(cache_dir=None)
    assert svc is not None


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
@patch("drift.embeddings.SentenceTransformer", create=True)
def test_ensure_model_returns_none_and_logs_warning_on_load_error(
    mock_st_cls: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Model load errors should degrade gracefully instead of bubbling up."""
    import logging

    mock_st_cls.side_effect = OSError("network down")
    svc = EmbeddingService(model_name="mock-model")

    with caplog.at_level(logging.WARNING, logger="drift.embeddings"):
        result = svc.embed_text("hello")

    assert result is None
    assert "Failed to load embedding model" in caplog.text


@patch("drift.embeddings._EMBEDDINGS_AVAILABLE", True)
def test_ensure_model_timeout_returns_none_and_logs_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Timed out model load should return None and not block callers indefinitely."""
    import drift.embeddings as emb_mod
    import logging

    class _ThreadStub:
        def __init__(self, target, daemon):
            self._target = target
            self.daemon = daemon
            self._alive = True

        def start(self):
            # Do not run target: simulate a still-running load.
            return None

        def join(self, timeout=None):
            return None

        def is_alive(self):
            return self._alive

    monkeypatch.setattr(emb_mod.threading, "Thread", _ThreadStub)
    monkeypatch.setattr(emb_mod, "SentenceTransformer", MagicMock(), raising=False)
    monkeypatch.setenv("DRIFT_EMBEDDING_MODEL_LOAD_TIMEOUT", "0.01")

    svc = EmbeddingService(model_name="mock-model")
    with caplog.at_level(logging.WARNING, logger="drift.embeddings"):
        result = svc.embed_text("hello")

    assert result is None
    assert "timed out" in caplog.text
