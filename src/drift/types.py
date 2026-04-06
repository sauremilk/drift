"""Shared type aliases and protocols used across Drift internals."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeAlias, TypeVar

JsonDict: TypeAlias = dict[str, object]
JsonList: TypeAlias = list[object]


class SupportsAppend(Protocol):
    """Minimal append protocol for line-oriented builders."""

    def append(self, item: str, style: str | None = None) -> object: ...


class TreeSitterNode(Protocol):
    """Subset of tree-sitter node API used by Drift."""

    type: str
    children: list[TreeSitterNode]
    start_byte: int
    end_byte: int
    start_point: tuple[int, int]
    end_point: tuple[int, int]
    prev_sibling: TreeSitterNode | None
    parent: TreeSitterNode | None

    def child_by_field_name(self, name: str) -> TreeSitterNode | None: ...


class TreeSitterTree(Protocol):
    """Subset of tree-sitter tree API used by Drift."""

    root_node: TreeSitterNode


class TreeSitterParser(Protocol):
    """Subset of tree-sitter parser API used by Drift."""

    def parse(self, source: bytes) -> TreeSitterTree: ...


SyncCallable = TypeVar("SyncCallable", bound=Callable[..., object])