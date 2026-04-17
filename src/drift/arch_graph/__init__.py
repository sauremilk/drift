"""Architecture Graph — living, persistent architecture model for drift.

Phase A of the Architecture Runtime Blueprint.
Provides a versioned, incrementally-updated graph of modules, dependencies,
abstractions, and hotspots derived from existing drift analysis data.
"""

from __future__ import annotations

from drift.arch_graph._models import (
    ArchAbstraction,
    ArchDecision,
    ArchDependency,
    ArchGraph,
    ArchHotspot,
    ArchModule,
    PatternProposal,
)
from drift.arch_graph._persistence import ArchGraphStore
from drift.arch_graph._reuse_index import AbstractionIndex, ReuseSuggestion, suggest_reuse
from drift.arch_graph._seeding import seed_graph

__all__ = [
    "AbstractionIndex",
    "ArchAbstraction",
    "ArchDecision",
    "ArchDependency",
    "ArchGraph",
    "ArchGraphStore",
    "ArchHotspot",
    "ArchModule",
    "PatternProposal",
    "ReuseSuggestion",
    "seed_graph",
    "suggest_reuse",
]
