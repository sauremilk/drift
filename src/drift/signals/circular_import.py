"""Signal: Circular Import Detection (CID).

Detects circular import chains within Python packages by building a
directed import graph from ParseResult data and running cycle detection.

Circular imports cause runtime ImportErrors, fragile import ordering,
and indicate tangled module responsibilities.

TypeScript/JS circular imports are already covered by ts_architecture.py.
This signal handles Python-only codebases.

Deterministic, AST-only, LLM-free.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path, PurePosixPath

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals._utils import is_test_file
from drift.signals.base import BaseSignal, register_signal


def _build_import_graph(
    parse_results: list[ParseResult],
) -> tuple[dict[str, set[str]], dict[str, Path]]:
    """Build a directed graph of module → imported-modules from parse results.

    Returns ``(graph, module_to_path)`` where graph maps normalised
    module names to sets of imported module names, and module_to_path
    maps module names back to their file paths.
    """
    graph: dict[str, set[str]] = defaultdict(set)
    module_to_path: dict[str, Path] = {}

    for pr in parse_results:
        if pr.language != "python":
            continue
        if is_test_file(pr.file_path):
            continue

        module_name = _path_to_module(pr.file_path)
        if not module_name:
            continue

        module_to_path[module_name] = pr.file_path
        # Ensure every module appears in graph even without imports
        graph.setdefault(module_name, set())

        for imp in pr.imports:
            target = imp.imported_module
            if not target:
                continue
            graph[module_name].add(target)

    return dict(graph), module_to_path


def _path_to_module(file_path: Path) -> str:
    """Convert a file path to a dotted module name.

    ``src/drift/signals/base.py`` → ``src.drift.signals.base``
    ``drift/config.py`` → ``drift.config``
    ``__init__.py`` files → package name (e.g. ``drift.signals``)
    """
    posix = PurePosixPath(file_path)
    parts = list(posix.parts)
    if not parts:
        return ""
    # Remove .py extension
    if parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    # __init__ → use parent package
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Find all elementary cycles via DFS.

    Returns a list of cycles, each cycle being a list of module names.
    Only returns cycles where *all* participants exist as keys in the
    graph (i.e. are local modules, not external dependencies).
    """
    visited: set[str] = set()
    on_stack: set[str] = set()
    stack: list[str] = []
    cycles: list[list[str]] = []
    seen_cycles: set[frozenset[str]] = set()

    def _dfs(node: str) -> None:
        visited.add(node)
        on_stack.add(node)
        stack.append(node)

        for neighbour in graph.get(node, ()):
            # Only follow edges to local modules (present in graph)
            if neighbour not in graph:
                continue
            if neighbour not in visited:
                _dfs(neighbour)
            elif neighbour in on_stack:
                # Found a cycle
                idx = stack.index(neighbour)
                cycle = stack[idx:]
                cycle_key = frozenset(cycle)
                if cycle_key not in seen_cycles:
                    seen_cycles.add(cycle_key)
                    cycles.append(list(cycle))

        stack.pop()
        on_stack.discard(node)

    for node in graph:
        if node not in visited:
            _dfs(node)

    return cycles


@register_signal
class CircularImportSignal(BaseSignal):
    """Detect circular import chains in Python packages."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.CIRCULAR_IMPORT

    @property
    def name(self) -> str:
        return "Circular Import"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        graph, module_to_path = _build_import_graph(parse_results)
        cycles = _find_cycles(graph)
        findings: list[Finding] = []

        for cycle in cycles:
            cycle_len = len(cycle)
            score = round(min(1.0, 0.3 + 0.1 * cycle_len), 3)
            severity = Severity.HIGH if score >= 0.7 else Severity.MEDIUM

            # Use the first module's path as the finding location
            first_module = cycle[0]
            file_path = module_to_path.get(first_module)

            related = [
                module_to_path[m]
                for m in cycle[1:]
                if m in module_to_path
            ]

            cycle_display = " → ".join(cycle) + " → " + cycle[0]

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity,
                    score=score,
                    title=f"Circular import ({cycle_len} modules)",
                    description=(
                        f"Circular import chain detected: {cycle_display}. "
                        f"This can cause runtime ImportErrors and indicates "
                        f"tangled module responsibilities."
                    ),
                    file_path=file_path,
                    related_files=related,
                    fix=(
                        f"Break the import cycle ({cycle_display}) by: "
                        f"extracting shared types into a separate module, "
                        f"using TYPE_CHECKING-guarded imports, or "
                        f"restructuring module boundaries."
                    ),
                    metadata={
                        "cycle_modules": cycle,
                        "cycle_length": cycle_len,
                    },
                    rule_id="circular_import",
                )
            )

        return findings
