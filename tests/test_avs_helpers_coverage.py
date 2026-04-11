"""Coverage tests for architecture_violation pure helpers:
_module_for_path, _module_aliases_for_path, _matches_pattern,
_matches_module_pattern, _relative_import_candidates, _compute_hub_nodes."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from drift.models import ImportInfo
from drift.signals.architecture_violation import (
    _compute_hub_nodes,
    _matches_module_pattern,
    _matches_pattern,
    _module_aliases_for_path,
    _module_for_path,
    _relative_import_candidates,
)

# -- _module_for_path ----------------------------------------------------------


class TestModuleForPath:
    def test_simple(self):
        assert _module_for_path(Path("src/pkg/mod.py")) == "src.pkg.mod"

    def test_init(self):
        assert _module_for_path(Path("src/pkg/__init__.py")) == "src.pkg.__init__"

    def test_single_file(self):
        assert _module_for_path(Path("main.py")) == "main"


# -- _module_aliases_for_path --------------------------------------------------


class TestModuleAliasesForPath:
    def test_with_src_root(self):
        aliases = _module_aliases_for_path(Path("src/mypackage/utils.py"))
        assert "src.mypackage.utils" in aliases
        assert "mypackage.utils" in aliases

    def test_without_src_root(self):
        aliases = _module_aliases_for_path(Path("mypackage/utils.py"))
        assert aliases == ["mypackage.utils"]

    def test_lib_root(self):
        aliases = _module_aliases_for_path(Path("lib/pkg/mod.py"))
        assert "pkg.mod" in aliases

    def test_single_part(self):
        aliases = _module_aliases_for_path(Path("mod.py"))
        assert aliases == ["mod"]


# -- _matches_pattern ----------------------------------------------------------


class TestMatchesPattern:
    def test_glob_match(self):
        assert _matches_pattern("src/pkg/utils.py", "src/*/utils.py") is True

    def test_no_match(self):
        assert _matches_pattern("src/pkg/main.py", "*.test") is False


# -- _matches_module_pattern ---------------------------------------------------


class TestMatchesModulePattern:
    def test_exact(self):
        assert _matches_module_pattern("pkg.utils", "pkg.utils") is True

    def test_prefix(self):
        assert _matches_module_pattern("pkg.utils.helpers", "pkg.utils") is True

    def test_glob(self):
        assert _matches_module_pattern("pkg.utils", "pkg.*") is True

    def test_no_match(self):
        assert _matches_module_pattern("other.mod", "pkg.utils") is False

    def test_glob_no_match(self):
        assert _matches_module_pattern("other.mod", "pkg.*") is False

    def test_partial_name(self):
        # "pkg.util" should NOT match prefix of "pkg.utils"
        assert _matches_module_pattern("pkg.util", "pkg.utils") is False


# -- _relative_import_candidates -----------------------------------------------


class TestRelativeImportCandidates:
    def _imp(
        self,
        module: str = "",
        names: list[str] | None = None,
        relative: bool = True,
    ) -> ImportInfo:
        return ImportInfo(
            imported_module=module,
            imported_names=names or [],
            is_relative=relative,
            source_file=Path("pkg/sub/mod.py"),
            line_number=1,
        )

    def test_non_relative(self):
        imp = self._imp(module="os.path", relative=False)
        assert _relative_import_candidates(Path("pkg/sub/mod.py"), imp) == []

    def test_relative_with_module(self):
        imp = self._imp(module="utils")
        result = _relative_import_candidates(Path("pkg/sub/mod.py"), imp)
        assert "pkg.sub.utils" in result

    def test_relative_names_only(self):
        imp = self._imp(module="", names=["helper"])
        result = _relative_import_candidates(Path("pkg/sub/mod.py"), imp)
        assert "pkg.sub.helper" in result

    def test_short_path(self):
        imp = self._imp(module="utils")
        result = _relative_import_candidates(Path("mod.py"), imp)
        assert result == []

    def test_relative_with_module_and_names(self):
        imp = self._imp(module="utils", names=["func"])
        result = _relative_import_candidates(Path("pkg/sub/mod.py"), imp)
        assert "pkg.sub.utils" in result
        assert "pkg.sub.utils.func" in result


# -- _compute_hub_nodes --------------------------------------------------------


class TestComputeHubNodes:
    def test_small_graph(self):
        g = nx.DiGraph()
        g.add_edge("a", "b")
        assert _compute_hub_nodes(g) == set()

    def test_hub_detection(self):
        g = nx.DiGraph()
        for i in range(10):
            g.add_edge(f"src{i}", "hub")
        g.add_edge("other", "leaf")
        hubs = _compute_hub_nodes(g, percentile=0.5)
        assert "hub" in hubs

    def test_empty_graph(self):
        g = nx.DiGraph()
        assert _compute_hub_nodes(g) == set()
