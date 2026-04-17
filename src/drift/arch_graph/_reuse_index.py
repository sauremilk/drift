"""Abstraction Index — active reuse suggestions for AI agents.

Phase C of the Architecture Runtime Blueprint.

Shifts from *"you duplicated X"* (MDS-style post-hoc detection) to
*"use X instead of writing a new one"* (proactive reuse guidance).

The index is built from ``ArchGraph.abstractions`` and supports:
- Token-based search (symbol names, description keywords)
- Scope filtering (only abstractions reachable from a module)
- Kind filtering (function / class)
- Usage-weighted ranking (more canonical = higher relevance)

When an ``EmbeddingService`` is available, semantic similarity
can optionally enhance the token-based ranking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from drift.arch_graph._models import ArchAbstraction, ArchGraph

# ---------------------------------------------------------------------------
# Token utilities
# ---------------------------------------------------------------------------

_SPLIT_RE = re.compile(r"[_\s/.\-]+")
_CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")


def _tokenize(text: str) -> set[str]:
    """Split *text* into lowercase keyword tokens.

    Handles snake_case, camelCase, paths, and whitespace.
    """
    # First split camelCase
    expanded = _CAMEL_RE.sub(" ", text)
    # Then split on separators
    parts = _SPLIT_RE.split(expanded)
    return {t.lower() for t in parts if len(t) >= 2}


# ---------------------------------------------------------------------------
# ReuseSuggestion — the value object returned to callers
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ReuseSuggestion:
    """A single reuse recommendation."""

    symbol: str
    kind: str
    module_path: str
    file_path: str
    usage_count: int
    relevance_score: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return {
            "symbol": self.symbol,
            "kind": self.kind,
            "module_path": self.module_path,
            "file_path": self.file_path,
            "usage_count": self.usage_count,
            "relevance_score": round(self.relevance_score, 4),
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# _IndexEntry — internal representation enriched with precomputed tokens
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _IndexEntry:
    """An abstraction plus precomputed search metadata."""

    symbol: str
    kind: str
    module_path: str
    file_path: str
    usage_count: int
    has_docstring: bool
    is_exported: bool
    tokens: frozenset[str]


# ---------------------------------------------------------------------------
# AbstractionIndex
# ---------------------------------------------------------------------------


class AbstractionIndex:
    """Searchable index of reusable abstractions.

    Build from ``ArchAbstraction`` objects, then query with
    ``search()`` for ranked suggestions.
    """

    __slots__ = ("_entries",)

    def __init__(self, entries: list[_IndexEntry]) -> None:
        self._entries = entries

    @property
    def entries(self) -> list[_IndexEntry]:
        """Indexed entries (for testing / introspection)."""
        return list(self._entries)

    @property
    def size(self) -> int:
        """Number of indexed abstractions."""
        return len(self._entries)

    # -- Construction -------------------------------------------------------

    @classmethod
    def build(
        cls,
        abstractions: list[ArchAbstraction],
        *,
        min_usage: int = 2,
    ) -> AbstractionIndex:
        """Build an index from a list of abstractions.

        Parameters
        ----------
        abstractions:
            Raw abstractions (e.g. from ``ArchGraph.abstractions``).
        min_usage:
            Minimum ``usage_count`` for non-exported symbols to be
            included.  Exported symbols are always included.
        """
        entries: list[_IndexEntry] = []
        for a in abstractions:
            if not a.is_exported and a.usage_count < min_usage:
                continue
            tokens = _tokenize(a.symbol) | _tokenize(a.module_path)
            entries.append(
                _IndexEntry(
                    symbol=a.symbol,
                    kind=a.kind,
                    module_path=a.module_path,
                    file_path=a.file_path,
                    usage_count=a.usage_count,
                    has_docstring=a.has_docstring,
                    is_exported=a.is_exported,
                    tokens=frozenset(tokens),
                )
            )
        return cls(entries)

    # -- Search -------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        kind: str | None = None,
        scope: str | None = None,
    ) -> list[ReuseSuggestion]:
        """Find abstractions matching *query*.

        Parameters
        ----------
        query:
            Free-text description (e.g. ``"validate email address"``).
        top_k:
            Maximum number of results.
        kind:
            Filter by kind (``"function"`` or ``"class"``).
        scope:
            Restrict to a specific module path prefix.

        Returns
        -------
        list[ReuseSuggestion]
            Ranked by relevance (descending).
        """
        if not self._entries:
            return []

        query_tokens = _tokenize(query)
        scored: list[tuple[float, _IndexEntry]] = []

        for entry in self._entries:
            # Apply filters
            if kind and entry.kind != kind:
                continue
            if scope:
                scope_norm = scope.replace("\\", "/").rstrip("/")
                if not entry.module_path.startswith(scope_norm):
                    continue

            score = self._score_entry(entry, query_tokens)
            scored.append((score, entry))

        # Sort descending by relevance
        scored.sort(key=lambda x: x[0], reverse=True)
        scored = scored[:top_k]

        return [
            ReuseSuggestion(
                symbol=e.symbol,
                kind=e.kind,
                module_path=e.module_path,
                file_path=e.file_path,
                usage_count=e.usage_count,
                relevance_score=s,
                reason=self._build_reason(e, query_tokens),
            )
            for s, e in scored
        ]

    # -- Scoring ------------------------------------------------------------

    @staticmethod
    def _score_entry(
        entry: _IndexEntry,
        query_tokens: set[str],
    ) -> float:
        """Compute a relevance score for *entry* against *query_tokens*.

        Components:
        - Token overlap (Jaccard-inspired, but asymmetric: query→entry)
        - Usage frequency bonus (canonical abstractions rank higher)
        - Docstring bonus (documented = more reusable)
        """
        # Token overlap: what fraction of query tokens appear in entry?
        if query_tokens:
            overlap = len(query_tokens & entry.tokens)
            token_score = overlap / len(query_tokens)
        else:
            # No query tokens → rank purely by usage
            token_score = 0.0

        # Usage bonus: log-scaled, capped
        usage_bonus = min(entry.usage_count / 10.0, 1.0)

        # Docstring bonus
        doc_bonus = 0.1 if entry.has_docstring else 0.0

        # Weighted combination
        return 0.55 * token_score + 0.35 * usage_bonus + 0.10 * doc_bonus

    @staticmethod
    def _build_reason(
        entry: _IndexEntry,
        query_tokens: set[str],
    ) -> str:
        """Build a human-readable reason for the suggestion."""
        overlap = query_tokens & entry.tokens
        parts: list[str] = []

        if overlap:
            parts.append(
                f"Token match: {', '.join(sorted(overlap))}"
            )
        if entry.usage_count > 0:
            parts.append(f"Used by {entry.usage_count} consumers")
        if entry.is_exported:
            parts.append("Part of public API")
        if entry.has_docstring:
            parts.append("Documented")

        return "; ".join(parts) if parts else "General candidate"


# ---------------------------------------------------------------------------
# suggest_reuse() — convenience entry point
# ---------------------------------------------------------------------------


def suggest_reuse(
    graph: ArchGraph,
    query: str,
    *,
    scope: str | None = None,
    max_suggestions: int = 10,
    min_usage: int = 2,
    kind: str | None = None,
) -> list[ReuseSuggestion]:
    """Suggest reusable abstractions from *graph* matching *query*.

    When *scope* is given, results are restricted to abstractions
    reachable from that module (the module itself + its graph neighbors).

    Parameters
    ----------
    graph:
        A populated ``ArchGraph``.
    query:
        Free-text description of what the agent wants to create.
    scope:
        Module path to limit suggestions to reachable modules.
    max_suggestions:
        Cap on the number of suggestions returned.
    min_usage:
        Minimum usage count for non-exported abstractions.
    kind:
        Filter by abstraction kind.

    Returns
    -------
    list[ReuseSuggestion]
        Ranked by relevance (descending).
    """
    # When scoped: restrict to abstractions in reachable modules
    if scope:
        scope_norm = scope.replace("\\", "/").rstrip("/")
        reachable = {scope_norm} | set(graph.neighbors(scope_norm))
        scoped_abstractions = [
            a for a in graph.abstractions
            if a.module_path in reachable
        ]
    else:
        scoped_abstractions = list(graph.abstractions)

    index = AbstractionIndex.build(scoped_abstractions, min_usage=min_usage)
    return index.search(query, top_k=max_suggestions, kind=kind)
