"""Tests for the embedding service (graceful degradation, caching, similarity)."""

from __future__ import annotations

import numpy as np
import pytest

from drift.embeddings import (  # noqa: E501
    _EMBEDDINGS_AVAILABLE,
    EmbeddingService,
    get_embedding_service,
    reset_embedding_service,
)


@pytest.fixture(autouse=True)
def _reset_service_singleton() -> None:
    reset_embedding_service()


# ---------------------------------------------------------------------------
# Graceful degradation without sentence-transformers
# ---------------------------------------------------------------------------


class TestEmbeddingServiceDegraded:
    """Tests that run with or without sentence-transformers installed."""

    def test_get_embedding_service_without_deps(self):
        if not _EMBEDDINGS_AVAILABLE:
            svc = get_embedding_service()
            assert svc is None
        else:
            svc = get_embedding_service()
            assert isinstance(svc, EmbeddingService)

    def test_cosine_similarity_identical(self):
        svc = EmbeddingService()
        v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        assert svc.cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-5)

    def test_cosine_similarity_orthogonal(self):
        svc = EmbeddingService()
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        assert svc.cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-5)

    def test_cosine_similarity_zero_vector(self):
        svc = EmbeddingService()
        a = np.array([1.0, 2.0], dtype=np.float32)
        z = np.array([0.0, 0.0], dtype=np.float32)
        assert svc.cosine_similarity(a, z) == 0.0

    def test_cosine_similarity_clamps_floating_point_overflow(self, monkeypatch):
        svc = EmbeddingService()
        a = np.array([1.0, 0.0], dtype=np.float64)
        b = np.array([1.0, 0.0], dtype=np.float64)

        monkeypatch.setattr(np, "dot", lambda _a, _b: np.float64(1.0000000000000002))
        assert svc.cosine_similarity(a, b) == 1.0

        monkeypatch.setattr(np, "dot", lambda _a, _b: np.float64(-1.0000000000000002))
        assert svc.cosine_similarity(a, b) == -1.0

    def test_build_index_returns_none_without_vectors(self):
        svc = EmbeddingService()
        assert svc.build_index([]) is None

    def test_build_index_and_search(self):
        svc = EmbeddingService()
        vecs = [
            np.array([1.0, 0.0, 0.0], dtype=np.float32),
            np.array([0.0, 1.0, 0.0], dtype=np.float32),
            np.array([0.99, 0.1, 0.0], dtype=np.float32),
        ]
        index = svc.build_index(vecs)
        assert index is not None

        results = svc.search_index(index, vecs[0], top_k=2)
        indices = [r[0] for r in results]
        assert 0 in indices
        assert 2 in indices

    def test_embed_text_returns_none_without_model(self):
        if not _EMBEDDINGS_AVAILABLE:
            svc = EmbeddingService()
            result = svc.embed_text("hello world")
            assert result is None

    def test_singleton_reuses_instance_with_same_parameters(self):
        if not _EMBEDDINGS_AVAILABLE:
            assert get_embedding_service() is None
            return

        s1 = get_embedding_service(model_name="all-MiniLM-L6-v2", batch_size=32)
        s2 = get_embedding_service(model_name="all-MiniLM-L6-v2", batch_size=32)
        assert s1 is s2

    def test_singleton_reinitializes_on_parameter_change(self):
        if not _EMBEDDINGS_AVAILABLE:
            assert get_embedding_service() is None
            return

        s1 = get_embedding_service(model_name="all-MiniLM-L6-v2", batch_size=32)
        s2 = get_embedding_service(model_name="all-MiniLM-L6-v2", batch_size=16)
        assert s1 is not s2


# ---------------------------------------------------------------------------
# Integration tests (only run if sentence-transformers is installed)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _EMBEDDINGS_AVAILABLE,
    reason="sentence-transformers not installed",
)
class TestEmbeddingServiceWithModel:
    def test_embed_text_shape(self):
        svc = EmbeddingService(model_name="all-MiniLM-L6-v2")
        vec = svc.embed_text("test function that processes payments")
        assert vec is not None
        assert vec.shape == (384,)

    def test_embed_texts_batch(self):
        svc = EmbeddingService(model_name="all-MiniLM-L6-v2")
        texts = ["payment processing", "database query", "HTTP routing"]
        vecs = svc.embed_texts(texts)
        assert len(vecs) == 3
        for v in vecs:
            assert v is not None
            assert v.shape == (384,)

    def test_similar_texts_high_similarity(self):
        svc = EmbeddingService(model_name="all-MiniLM-L6-v2")
        a = svc.embed_text("process payment transaction")
        b = svc.embed_text("handle payment processing")
        c = svc.embed_text("create database migration")
        sim_ab = svc.cosine_similarity(a, b)
        sim_ac = svc.cosine_similarity(a, c)
        # Payment-related texts should be more similar to each other
        assert sim_ab > sim_ac


# ---------------------------------------------------------------------------
# AP2: Model-/version-scoped cache tests
# ---------------------------------------------------------------------------


class TestEmbeddingCacheVersioning:
    def test_cache_dir_contains_model_and_version(self, tmp_path):
        from drift.embeddings import _CACHE_VERSION, EmbeddingCache

        cache = EmbeddingCache(tmp_path, model_name="test-model")
        assert cache._dir is not None
        assert "test-model" in str(cache._dir)
        assert f"v{_CACHE_VERSION}" in str(cache._dir)


# ---------------------------------------------------------------------------
# EmbeddingCache — get/put/get_batch
# ---------------------------------------------------------------------------


class TestEmbeddingCacheMethods:
    def test_get_returns_none_for_missing_key(self, tmp_path):
        from drift.embeddings import EmbeddingCache

        cache = EmbeddingCache(tmp_path, model_name="m")
        result = cache.get("nonexistent text")
        assert result is None

    def test_put_skipped_when_cache_disabled(self, tmp_path):
        from drift.embeddings import EmbeddingCache

        cache = EmbeddingCache(tmp_path, model_name="m")
        cache._dir = None  # simulate disabled cache
        # Should not raise
        vec = np.array([1.0, 2.0], dtype=np.float32)
        cache.put("test", vec)

    def test_get_returns_none_when_cache_disabled(self, tmp_path):
        from drift.embeddings import EmbeddingCache

        cache = EmbeddingCache(tmp_path, model_name="m")
        cache._dir = None
        assert cache.get("test") is None

    def test_get_batch_returns_all_misses_for_empty_cache(self, tmp_path):
        from drift.embeddings import EmbeddingCache

        cache = EmbeddingCache(tmp_path, model_name="m")
        hits_idx, hits_vec, misses = cache.get_batch(["a", "b", "c"])
        assert hits_idx == []
        assert hits_vec == []
        assert misses == [0, 1, 2]


# ---------------------------------------------------------------------------
# EmbeddingService — cosine_similarity_matrix
# ---------------------------------------------------------------------------


class TestCosineSimMatrix:
    def test_cosine_similarity_matrix_identity(self):
        svc = EmbeddingService()
        a = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        result = svc.cosine_similarity_matrix(a, a)
        assert result.shape == (2, 2)
        assert result[0, 0] == pytest.approx(1.0, abs=1e-5)
        assert result[0, 1] == pytest.approx(0.0, abs=1e-5)

    def test_cosine_similarity_matrix_normalizes_unnormalized_rows(self):
        svc = EmbeddingService()
        a = np.array([[2.0, 0.0], [0.0, 0.0]], dtype=np.float32)
        b = np.array([[3.0, 0.0], [0.0, 5.0]], dtype=np.float32)

        result = svc.cosine_similarity_matrix(a, b)

        assert result.shape == (2, 2)
        assert result[0, 0] == pytest.approx(1.0, abs=1e-5)
        assert result[0, 1] == pytest.approx(0.0, abs=1e-5)
        assert result[1, 0] == pytest.approx(0.0, abs=1e-5)
        assert result[1, 1] == pytest.approx(0.0, abs=1e-5)


# ---------------------------------------------------------------------------
# EmbeddingService — build_index numpy fallback
# ---------------------------------------------------------------------------


class TestBuildIndexFallback:
    def test_build_index_small_list_returns_ndarray(self):
        svc = EmbeddingService()
        vecs = [
            np.array([1.0, 0.0, 0.0], dtype=np.float32),
            np.array([0.0, 1.0, 0.0], dtype=np.float32),
        ]
        index = svc.build_index(vecs)
        assert index is not None
        assert isinstance(index, np.ndarray)

    def test_build_index_empty_ndarray_returns_none(self):
        svc = EmbeddingService()
        empty = np.array([], dtype=np.float32).reshape(0, 3)
        assert svc.build_index(empty) is None


# ---------------------------------------------------------------------------
# EmbeddingService — search_index numpy fallback
# ---------------------------------------------------------------------------


class TestSearchIndexFallback:
    def test_numpy_fallback_search(self):
        svc = EmbeddingService()
        vecs = np.array(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.9, 0.1, 0.0]],
            dtype=np.float32,
        )
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = svc.search_index(vecs, query, top_k=2)
        assert len(results) == 2
        indices = [r[0] for r in results]
        assert 0 in indices

    def test_search_index_empty_returns_empty(self):
        svc = EmbeddingService()
        empty = np.array([], dtype=np.float32).reshape(0, 3)
        results = svc.search_index(empty, np.array([1.0, 0.0, 0.0], dtype=np.float32))
        assert results == []

    def test_search_non_ndarray_returns_empty(self):
        svc = EmbeddingService()
        results = svc.search_index("not_an_array", np.array([1.0], dtype=np.float32))
        assert results == []


# ---------------------------------------------------------------------------
# embed_texts returns None list when model unavailable
# ---------------------------------------------------------------------------


class TestEmbedTextsDegraded:
    def test_embed_texts_empty_returns_empty(self):
        svc = EmbeddingService()
        assert svc.embed_texts([]) == []

    def test_embed_texts_returns_nones_without_model(self):
        if _EMBEDDINGS_AVAILABLE:
            pytest.skip("sentence-transformers installed")
        svc = EmbeddingService()
        result = svc.embed_texts(["hello", "world"])
        assert result == [None, None]


class TestEmbeddingInputSanitization:
    def test_embed_text_returns_none_for_empty_sanitized_input(self, monkeypatch, caplog):
        svc = EmbeddingService()

        def _unexpected_model_call() -> object:
            raise AssertionError("_ensure_model must not be called for empty sanitized input")

        monkeypatch.setattr(svc, "_ensure_model", _unexpected_model_call)

        with caplog.at_level("DEBUG", logger="drift.embeddings"):
            result = svc.embed_text(" \t\n\x00 ")

        assert result is None
        assert "Skipping embedding for empty or invalid input" in caplog.text

    def test_embed_texts_skips_invalid_items_and_preserves_order(self, monkeypatch):
        svc = EmbeddingService()

        class _FakeModel:
            def encode(self, texts, **_kwargs):
                return np.array(
                    [[float(len(texts[0]))], [float(len(texts[1]))]],
                    dtype=np.float32,
                )

        monkeypatch.setattr(svc, "_ensure_model", lambda: _FakeModel())

        result = svc.embed_texts(["\x00   ", "  hello\x00  ", "\n\t", "world"])

        assert result[0] is None
        assert result[1] is not None
        assert result[2] is None
        assert result[3] is not None
        assert result[1].shape == (1,)
        assert result[3].shape == (1,)
        assert result[1][0] == pytest.approx(5.0)
        assert result[3][0] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# get_embedding_service / embeddings_available
# ---------------------------------------------------------------------------


class TestEmbeddingsAvailable:
    def test_embeddings_available_returns_bool(self):
        from drift.embeddings import embeddings_available

        assert isinstance(embeddings_available(), bool)

    def test_cache_dir_includes_model_and_version(self, tmp_path):
        from drift.embeddings import _CACHE_VERSION, EmbeddingCache

        cache = EmbeddingCache(tmp_path, model_name="all-MiniLM-L6-v2")
        assert cache._dir is not None
        parts = cache._dir.parts
        assert "all-MiniLM-L6-v2" in parts
        assert f"v{_CACHE_VERSION}" in parts

    def test_different_models_use_different_dirs(self, tmp_path):
        from drift.embeddings import EmbeddingCache

        c1 = EmbeddingCache(tmp_path, model_name="model-a")
        c2 = EmbeddingCache(tmp_path, model_name="model-b")
        assert c1._dir != c2._dir

    def test_slash_in_model_name_normalised(self, tmp_path):
        from drift.embeddings import EmbeddingCache

        cache = EmbeddingCache(tmp_path, model_name="org/model-v1")
        assert cache._dir is not None
        # no literal "/" in the leaf directory names
        for part in cache._dir.parts:
            assert "org/model" not in part

    def test_model_switch_no_cross_read(self, tmp_path):
        """Vectors stored under model-a are not returned for model-b."""
        from drift.embeddings import EmbeddingCache

        c1 = EmbeddingCache(tmp_path, model_name="model-a")
        fake_vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        # Write directly to bypass the _EMBEDDINGS_AVAILABLE guard
        assert c1._dir is not None
        key = c1._key("hello")
        (c1._dir / f"{key}.bin").write_bytes(fake_vec.tobytes())

        c2 = EmbeddingCache(tmp_path, model_name="model-b")
        assert c2._dir is not None
        assert not (c2._dir / f"{key}.bin").exists()  # different model → no file
