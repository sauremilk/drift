"""Signal 3: Mutant Duplicate Score (MDS).

Detects near-duplicate functions — code that looks structurally very
similar but differs in subtle ways, suggesting copy-paste-then-modify
patterns typical of AI generation across multiple sessions.

v0.2 enhancements:
- Hybrid similarity: ``0.6 × ast_jaccard + 0.4 × cosine_embedding``
  when sentence-transformers is available.
- FAISS index for module-wide search (optional, with numpy fallback).
- New "Semantic duplicate" finding category for high embedding-sim pairs
  that structural checks miss.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING, Any

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    FunctionInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.base import BaseSignal, register_signal

if TYPE_CHECKING:
    from drift.embeddings import EmbeddingService

logger = logging.getLogger("drift.mds")

# Threshold above which two functions are considered near-duplicates
SIMILARITY_THRESHOLD = 0.80

# Hybrid similarity threshold (lower because embedding adds info)
_HYBRID_THRESHOLD = 0.75

# Maximum number of detailed comparisons to perform per bucket
_MAX_COMPARISONS_PER_BUCKET = 500

# Maximum near-duplicate findings to report
_MAX_FINDINGS = 200


def _get_precomputed_ngrams(func: FunctionInfo) -> list[tuple[str, ...]] | None:
    """Retrieve pre-computed AST n-grams from FunctionInfo.ast_fingerprint."""
    raw = func.ast_fingerprint.get("ngrams")
    if raw is None:
        return None
    if not raw:
        return []
    return [tuple(ng) for ng in raw]


def _structural_similarity(
    ngrams_a: list[tuple[str, ...]] | None,
    ngrams_b: list[tuple[str, ...]] | None,
) -> float:
    """Compute structural similarity from pre-computed AST n-gram lists."""
    if not ngrams_a or not ngrams_b:
        return 0.0

    len_a, len_b = len(ngrams_a), len(ngrams_b)
    if len_a > 0 and len_b > 0:
        size_ratio = min(len_a, len_b) / max(len_a, len_b)
        if size_ratio < 0.33:
            return size_ratio

    return _jaccard(ngrams_a, ngrams_b)


def _jaccard(a: list[tuple[str, ...]], b: list[tuple[str, ...]]) -> float:
    """Jaccard similarity over two multiset n-gram lists."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    set_a: dict[tuple[str, ...], int] = defaultdict(int)
    set_b: dict[tuple[str, ...], int] = defaultdict(int)
    for ng in a:
        set_a[ng] += 1
    for ng in b:
        set_b[ng] += 1

    all_keys = set(set_a) | set(set_b)
    intersection = sum(min(set_a[k], set_b[k]) for k in all_keys)
    union = sum(max(set_a[k], set_b[k]) for k in all_keys)
    return intersection / union if union else 0.0


def _function_signature_text(fn: FunctionInfo) -> str:
    """Build a compact text representation for embedding a function."""
    parts = [fn.name]
    # Include file context
    if fn.file_path:
        parts.append(fn.file_path.stem)
    # Include structural hints
    parts.append(f"lines={fn.loc}")
    parts.append(f"complexity={fn.complexity}")
    # Include a few n-gram type names
    ngrams = fn.ast_fingerprint.get("ngrams")
    if ngrams:
        flat = {node for ng in ngrams[:20] for node in ng}
        parts.extend(sorted(flat)[:10])
    return " ".join(parts)


@register_signal
class MutantDuplicateSignal(BaseSignal):
    """Detect near-duplicate functions that diverge in subtle ways."""

    _embedding_service: EmbeddingService | None = None  # set by create_signals

    def __init__(self, repo_path: Path) -> None:
        self._repo_path = repo_path

    @property
    def signal_type(self) -> SignalType:
        return SignalType.MUTANT_DUPLICATE

    @property
    def name(self) -> str:
        return "Mutant Duplicates"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        functions: list[FunctionInfo] = []
        for pr in parse_results:
            for fn in pr.functions:
                if fn.loc >= 5:
                    functions.append(fn)

        if len(functions) < 2:
            return []

        findings: list[Finding] = []
        checked: set[tuple[str, str]] = set()

        # ---- Phase 1: Exact duplicates via body_hash (O(n)) ----
        hash_groups: dict[str, list[FunctionInfo]] = defaultdict(list)
        for fn in functions:
            if fn.body_hash:
                hash_groups[fn.body_hash].append(fn)

        for _h, group in hash_groups.items():
            if len(group) > 1:
                for a, b in combinations(group, 2):
                    key = tuple(sorted([f"{a.file_path}:{a.name}", f"{b.file_path}:{b.name}"]))
                    if key in checked:
                        continue
                    checked.add(key)

                    findings.append(
                        Finding(
                            signal_type=self.signal_type,
                            severity=Severity.HIGH,
                            score=0.9,
                            title=f"Exact duplicate: {a.name} ↔ {b.name}",
                            description=(
                                f"{a.file_path}:{a.start_line} and "
                                f"{b.file_path}:{b.start_line} are identical "
                                f"({a.loc} lines). Consider consolidating."
                            ),
                            file_path=a.file_path,
                            start_line=a.start_line,
                            related_files=[b.file_path],
                            metadata={
                                "similarity": 1.0,
                                "body_hash": _h,
                                "function_a": a.name,
                                "function_b": b.name,
                                "file_a": a.file_path.as_posix(),
                                "file_b": b.file_path.as_posix(),
                            },
                        )
                    )

        # ---- Pre-compute data for Phase 2 + 3 ----
        ngram_cache: dict[str, list[tuple[str, ...]] | None] = {}
        fn_key_map: dict[str, FunctionInfo] = {}
        for fn in functions:
            fn_key = f"{fn.file_path}:{fn.name}:{fn.start_line}"
            ngram_cache[fn_key] = _get_precomputed_ngrams(fn)
            fn_key_map[fn_key] = fn

        # Pre-compute function embeddings if service is available
        emb = getattr(self, "_embedding_service", None)
        embedding_cache: dict[str, Any] = {}
        if emb is not None:
            texts = []
            keys = []
            for fn in functions:
                fn_key = f"{fn.file_path}:{fn.name}:{fn.start_line}"
                text = _function_signature_text(fn)
                texts.append(text)
                keys.append(fn_key)
            if texts:
                vectors = emb.embed_texts(texts)
                for k, v in zip(keys, vectors, strict=True):
                    if v is not None:
                        embedding_cache[k] = v

        # ---- Phase 2: Near-duplicates via LOC-bucket + hybrid similarity ----
        bucket_size = 10
        loc_buckets: dict[int, list[FunctionInfo]] = defaultdict(list)
        for fn in functions:
            bucket = fn.loc // bucket_size
            loc_buckets[bucket].append(fn)

        sorted_buckets = sorted(loc_buckets.keys())
        use_hybrid = bool(embedding_cache)
        threshold = _HYBRID_THRESHOLD if use_hybrid else SIMILARITY_THRESHOLD

        for i, bucket_key in enumerate(sorted_buckets):
            candidates = list(loc_buckets[bucket_key])
            if i + 1 < len(sorted_buckets) and sorted_buckets[i + 1] == bucket_key + 1:
                candidates.extend(loc_buckets[sorted_buckets[i + 1]])

            if len(candidates) < 2:
                continue

            comparisons = 0
            for a, b in combinations(candidates, 2):
                if comparisons >= _MAX_COMPARISONS_PER_BUCKET:
                    break
                if len(findings) >= _MAX_FINDINGS:
                    break

                key = tuple(sorted([f"{a.file_path}:{a.name}", f"{b.file_path}:{b.name}"]))
                if key in checked:
                    continue

                if a.loc > 0 and b.loc > 0:
                    ratio = min(a.loc, b.loc) / max(a.loc, b.loc)
                    if ratio < 0.5:
                        continue

                if a.body_hash and a.body_hash == b.body_hash:
                    continue

                comparisons += 1
                key_a = f"{a.file_path}:{a.name}:{a.start_line}"
                key_b = f"{b.file_path}:{b.name}:{b.start_line}"
                ng_a = ngram_cache.get(key_a)
                ng_b = ngram_cache.get(key_b)

                ast_sim = _structural_similarity(ng_a, ng_b)

                # Compute hybrid similarity if embeddings available
                if use_hybrid and key_a in embedding_cache and key_b in embedding_cache:
                    emb_sim = emb.cosine_similarity(embedding_cache[key_a], embedding_cache[key_b])
                    sim = 0.6 * ast_sim + 0.4 * emb_sim
                else:
                    sim = ast_sim

                if sim >= threshold:
                    checked.add(key)

                    severity = Severity.MEDIUM if sim < 0.9 else Severity.HIGH
                    score = sim * 0.85

                    metadata: dict[str, Any] = {
                        "similarity": round(sim, 3),
                        "function_a": a.name,
                        "function_b": b.name,
                        "file_a": a.file_path.as_posix(),
                        "file_b": b.file_path.as_posix(),
                    }
                    if use_hybrid:
                        metadata["ast_similarity"] = round(ast_sim, 3)

                    findings.append(
                        Finding(
                            signal_type=self.signal_type,
                            severity=severity,
                            score=score,
                            title=f"Near-duplicate ({sim:.0%}): {a.name} ↔ {b.name}",
                            description=(
                                f"{a.file_path}:{a.start_line} and "
                                f"{b.file_path}:{b.start_line} are {sim:.0%} similar. "
                                f"Small differences may indicate copy-paste divergence."
                            ),
                            file_path=a.file_path,
                            start_line=a.start_line,
                            related_files=[b.file_path],
                            metadata=metadata,
                        )
                    )

            if len(findings) >= _MAX_FINDINGS:
                break

        # ---- Phase 3: Semantic duplicates (embedding-only, cross-bucket) ----
        if emb is not None and embedding_cache and len(findings) < _MAX_FINDINGS:
            findings.extend(
                self._find_semantic_duplicates(
                    functions,
                    fn_key_map,
                    embedding_cache,
                    ngram_cache,
                    checked,
                    emb,
                )
            )

        return findings

    def _find_semantic_duplicates(
        self,
        functions: list[FunctionInfo],
        fn_key_map: dict[str, FunctionInfo],
        embedding_cache: dict[str, Any],
        ngram_cache: dict[str, list[tuple[str, ...]] | None],
        checked: set[tuple[str, str]],
        emb: EmbeddingService,
    ) -> list[Finding]:
        """Find high-embedding-similarity pairs that structural checks miss."""
        findings: list[Finding] = []

        # Build FAISS / numpy index for fast search
        keys = list(embedding_cache.keys())
        vectors = [embedding_cache[k] for k in keys]
        if len(vectors) < 2:
            return findings

        index = emb.build_index(vectors)
        if index is None:
            return findings

        seen: set[tuple[str, str]] = set(checked)

        for i, key_a in enumerate(keys):
            if len(findings) >= 50:  # Cap semantic-only findings
                break
            results = emb.search_index(index, embedding_cache[key_a], top_k=5)
            for j, score in results:
                if j == i or score < 0.85:
                    continue
                key_b = keys[j]
                pair = tuple(sorted([key_a, key_b]))
                if pair in seen:
                    continue
                seen.add(pair)

                fn_a = fn_key_map.get(key_a)
                fn_b = fn_key_map.get(key_b)
                if fn_a is None or fn_b is None:
                    continue

                # Verify that structural similarity is LOW (otherwise Phase 2
                # already caught it)
                ng_a = ngram_cache.get(key_a)
                ng_b = ngram_cache.get(key_b)
                ast_sim = _structural_similarity(ng_a, ng_b)
                if ast_sim >= SIMILARITY_THRESHOLD:
                    continue

                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=Severity.LOW,
                        score=score * 0.6,
                        title=(f"Semantic duplicate ({score:.0%}): {fn_a.name} ↔ {fn_b.name}"),
                        description=(
                            f"{fn_a.file_path}:{fn_a.start_line} and "
                            f"{fn_b.file_path}:{fn_b.start_line} are semantically "
                            f"similar ({score:.0%}) despite different structure. "
                            f"They may serve the same purpose."
                        ),
                        file_path=fn_a.file_path,
                        start_line=fn_a.start_line,
                        related_files=[fn_b.file_path],
                        metadata={
                            "embedding_similarity": round(score, 3),
                            "ast_similarity": round(ast_sim, 3),
                            "function_a": fn_a.name,
                            "function_b": fn_b.name,
                            "file_a": fn_a.file_path.as_posix(),
                            "file_b": fn_b.file_path.as_posix(),
                            "detection_method": "semantic",
                        },
                    )
                )

        return findings
