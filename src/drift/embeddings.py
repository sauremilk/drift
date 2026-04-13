"""Embedding service for semantic analysis in Drift.

Provides vector embeddings via sentence-transformers and optional FAISS
indexing.  All functionality degrades gracefully when optional dependencies
(sentence-transformers, faiss-cpu, numpy) are not installed — callers
receive ``None`` from :func:`get_embedding_service` and must handle that.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger("drift.embeddings")

# ---------------------------------------------------------------------------
# Optional dependency probing
# ---------------------------------------------------------------------------

_EMBEDDINGS_AVAILABLE = False
_FAISS_AVAILABLE = False

try:
    import numpy as np  # noqa: F811
    from sentence_transformers import SentenceTransformer

    _EMBEDDINGS_AVAILABLE = True
except ImportError:
    pass

try:
    import faiss  # noqa: F811

    _FAISS_AVAILABLE = True
except ImportError:
    pass


def embeddings_available() -> bool:
    """Return True when sentence-transformers + numpy are installed."""
    return _EMBEDDINGS_AVAILABLE


# ---------------------------------------------------------------------------
# Embedding cache (disk-backed)
# ---------------------------------------------------------------------------

_CACHE_VERSION = 2


def _safe_model_name(model_name: str) -> str:
    """Normalise a model name for use as a directory component."""
    return model_name.replace("/", "_").replace("\\", "_")


class EmbeddingCache:
    """Disk-backed embedding vector cache.

    Keys are SHA-256 hashes of input text.  Values are stored as raw
    float32 bytes for fast mmap-free loading.

    The cache is partitioned by *model_name* and *_CACHE_VERSION* so that
    a model switch or cache-format change never silently returns stale
    vectors.
    """

    def __init__(self, cache_dir: Path, *, model_name: str = "unknown") -> None:
        safe = _safe_model_name(model_name)
        self._dir: Path | None = cache_dir / "embeddings" / safe / f"v{_CACHE_VERSION}"
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            with suppress(OSError):
                # Best-effort: Windows does not support POSIX permissions
                os.chmod(self._dir, 0o700)
        except OSError as exc:
            # Cache is optional; disable it when the filesystem is unavailable.
            logger.warning("Embedding cache disabled: could not create cache directory (%s)", exc)
            self._dir = None

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def get(self, text: str) -> np.ndarray | None:
        if not _EMBEDDINGS_AVAILABLE:
            return None
        if self._dir is None:
            return None
        path = self._dir / f"{self._key(text)}.bin"
        if not path.exists():
            return None
        try:
            return np.frombuffer(path.read_bytes(), dtype=np.float32).copy()
        except Exception:
            path.unlink(missing_ok=True)
            return None

    def put(self, text: str, vector: np.ndarray) -> None:
        if not _EMBEDDINGS_AVAILABLE:
            return
        if self._dir is None:
            return
        path = self._dir / f"{self._key(text)}.bin"
        try:
            path.write_bytes(vector.astype(np.float32).tobytes())
        except OSError as exc:
            logger.warning(
                "Embedding cache write failed; continuing without persisted cache (%s)",
                exc,
            )

    def get_batch(self, texts: list[str]) -> tuple[list[int], list[np.ndarray], list[int]]:
        """Look up multiple texts.  Returns (hit_indices, hit_vectors, miss_indices)."""
        hits_idx: list[int] = []
        hits_vec: list[np.ndarray] = []
        misses: list[int] = []
        for i, t in enumerate(texts):
            vec = self.get(t)
            if vec is not None:
                hits_idx.append(i)
                hits_vec.append(vec)
            else:
                misses.append(i)
        return hits_idx, hits_vec, misses


# ---------------------------------------------------------------------------
# Embedding service
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "all-MiniLM-L6-v2"


class EmbeddingService:
    """High-level embedding API with caching and optional FAISS indexing.

    The underlying model is loaded lazily on first call to avoid startup
    overhead when embeddings are not needed.
    """

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        cache_dir: Path | None = None,
        batch_size: int = 64,
    ) -> None:
        self._model_name = model_name
        self._batch_size = batch_size
        self._model: SentenceTransformer | None = None
        self._cache = (
            EmbeddingCache(cache_dir, model_name=model_name)
            if cache_dir
            else None
        )

    # -- lazy model loading --------------------------------------------------

    def _ensure_model(self) -> SentenceTransformer | None:
        if self._model is None:
            if not _EMBEDDINGS_AVAILABLE:
                return None
            logger.info("Loading embedding model '%s'…", self._model_name)
            self._model = SentenceTransformer(self._model_name)
        return self._model

    # -- public API ----------------------------------------------------------

    def embed_text(self, text: str) -> np.ndarray | None:
        """Embed a single text string.  Returns a 1-D float32 vector, or None."""
        if self._cache:
            hit = self._cache.get(text)
            if hit is not None:
                return hit
        model = self._ensure_model()
        if model is None:
            return None
        vec: np.ndarray = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        if self._cache:
            self._cache.put(text, vec)
        return vec

    def embed_texts(self, texts: list[str]) -> list[np.ndarray | None]:
        """Embed multiple texts.  Returns list of 1-D float32 vectors."""
        if not texts:
            return []

        # Check cache for each text
        if self._cache:
            hit_idx, hit_vec, miss_idx = self._cache.get_batch(texts)
        else:
            hit_idx, hit_vec, miss_idx = [], [], list(range(len(texts)))

        model = self._ensure_model()
        if model is None:
            return [None] * len(texts)

        # Encode uncached texts
        miss_vecs: np.ndarray | None = None
        if miss_idx:
            miss_texts = [texts[i] for i in miss_idx]
            miss_vecs = model.encode(
                miss_texts,
                batch_size=self._batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            # Store in cache
            if self._cache:
                for j, idx in enumerate(miss_idx):
                    self._cache.put(texts[idx], miss_vecs[j])

        # Reassemble full result in original order
        result: list[np.ndarray | None] = [None] * len(texts)
        for j, idx in enumerate(hit_idx):
            result[idx] = hit_vec[j]
        if miss_vecs is not None:
            for j, idx in enumerate(miss_idx):
                result[idx] = miss_vecs[j]
        return result

    # -- similarity helpers --------------------------------------------------

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two vectors."""
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    @staticmethod
    def cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Pairwise cosine similarity matrix between two sets of vectors."""
        return a @ b.T  # type: ignore[no-any-return]

    # -- FAISS index ---------------------------------------------------------

    @staticmethod
    def build_index(vectors: list[np.ndarray] | np.ndarray) -> object | None:
        """Build a FAISS inner-product index.  Falls back to brute-force numpy.

        Returns None when *vectors* is empty.
        """
        matrix: np.ndarray
        if isinstance(vectors, list):
            if not vectors:
                return None
            matrix = cast(np.ndarray, np.stack(vectors))
        else:
            matrix = vectors

        if matrix.size == 0:
            return None
        if _FAISS_AVAILABLE and matrix.shape[0] >= 32:
            index = faiss.IndexFlatIP(matrix.shape[1])
            index.add(matrix)
            return index  # type: ignore[no-any-return]
        # Fallback: store raw matrix for numpy-based search
        return matrix  # type: ignore[no-any-return]

    @staticmethod
    def search_index(index: object, query: np.ndarray, top_k: int = 10) -> list[tuple[int, float]]:
        """Search an index for nearest neighbours.

        Returns list of (index, similarity) tuples, sorted descending.
        """
        if query.ndim == 1:
            query = query.reshape(1, -1)

        if _FAISS_AVAILABLE and hasattr(index, "search"):
            k = min(top_k, getattr(index, "ntotal", top_k))
            if k < 1:
                return []
            scores, indices = index.search(query, k)
            return [
                (int(idx), float(score))
                for idx, score in zip(indices[0], scores[0], strict=True)
                if idx >= 0
            ]

        # Numpy fallback
        vectors = index  # type: ignore[assignment]
        if not isinstance(vectors, np.ndarray) or vectors.size == 0:
            return []
        sims = (query @ vectors.T).flatten()
        k = min(top_k, len(sims))
        top_indices = np.argpartition(sims, -k)[-k:]
        top_indices = top_indices[np.argsort(sims[top_indices])[::-1]]
        return [(int(i), float(sims[i])) for i in top_indices]


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_SERVICE: EmbeddingService | None = None
_SERVICE_CFG: tuple[str, str | None, int] | None = None
_SERVICE_LOCK = threading.Lock()


def _cache_dir_key(cache_dir: Path | None) -> str | None:
    if cache_dir is None:
        return None
    try:
        return str(cache_dir.resolve())
    except OSError:
        return str(cache_dir)


def get_embedding_service(
    cache_dir: Path | None = None,
    model_name: str = _DEFAULT_MODEL,
    batch_size: int = 64,
) -> EmbeddingService | None:
    """Return the global EmbeddingService, or None if deps are missing."""
    global _SERVICE, _SERVICE_CFG
    if not _EMBEDDINGS_AVAILABLE:
        return None

    requested_cfg = (model_name, _cache_dir_key(cache_dir), batch_size)
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = EmbeddingService(
                model_name=model_name,
                cache_dir=cache_dir,
                batch_size=batch_size,
            )
            _SERVICE_CFG = requested_cfg
            return _SERVICE

        if requested_cfg != _SERVICE_CFG:
            logger.warning(
                "Reinitializing embedding service due to changed configuration: "
                "old=%s new=%s",
                _SERVICE_CFG,
                requested_cfg,
            )
            _SERVICE = EmbeddingService(
                model_name=model_name,
                cache_dir=cache_dir,
                batch_size=batch_size,
            )
            _SERVICE_CFG = requested_cfg

        return _SERVICE


def reset_embedding_service() -> None:
    """Reset the global singleton (useful in tests)."""
    global _SERVICE, _SERVICE_CFG
    with _SERVICE_LOCK:
        _SERVICE = None
        _SERVICE_CFG = None
