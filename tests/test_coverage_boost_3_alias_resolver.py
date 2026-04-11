"""Coverage-Boost: analyzers/typescript/alias_resolver.py — Fehlerpfade und Edge-Cases."""

from __future__ import annotations

import json
from pathlib import Path

from drift.analyzers.typescript.alias_resolver import (
    _collect_tsconfig_chain,
    _expand_target_pattern,
    _iter_effective_paths,
    _load_compiler_options,
    _load_tsconfig_data,
    _match_alias_pattern,
    _resolve_candidate_file,
    _resolve_extends_path,
    resolve_tsconfig_alias_import,
)

# ---------------------------------------------------------------------------
# _load_compiler_options — error paths
# ---------------------------------------------------------------------------


def test_load_compiler_options_missing_file(tmp_path: Path) -> None:
    result = _load_compiler_options(tmp_path / "nonexistent.json")
    assert result == {}


def test_load_compiler_options_invalid_json(tmp_path: Path) -> None:
    f = tmp_path / "tsconfig.json"
    f.write_text("NOT JSON {{", encoding="utf-8")
    result = _load_compiler_options(f)
    assert result == {}


def test_load_compiler_options_non_dict_compiler_options(tmp_path: Path) -> None:
    f = tmp_path / "tsconfig.json"
    f.write_text(json.dumps({"compilerOptions": "should-be-dict"}), encoding="utf-8")
    result = _load_compiler_options(f)
    assert result == {}


def test_load_compiler_options_valid(tmp_path: Path) -> None:
    f = tmp_path / "tsconfig.json"
    f.write_text(json.dumps({"compilerOptions": {"baseUrl": "src"}}), encoding="utf-8")
    result = _load_compiler_options(f)
    assert result == {"baseUrl": "src"}


# ---------------------------------------------------------------------------
# _load_tsconfig_data — error paths
# ---------------------------------------------------------------------------


def test_load_tsconfig_data_missing_file(tmp_path: Path) -> None:
    assert _load_tsconfig_data(tmp_path / "missing.json") is None


def test_load_tsconfig_data_invalid_json(tmp_path: Path) -> None:
    f = tmp_path / "tsconfig.json"
    f.write_text("{invalid", encoding="utf-8")
    assert _load_tsconfig_data(f) is None


def test_load_tsconfig_data_non_dict(tmp_path: Path) -> None:
    f = tmp_path / "tsconfig.json"
    f.write_text("[1, 2, 3]", encoding="utf-8")
    assert _load_tsconfig_data(f) is None


# ---------------------------------------------------------------------------
# _resolve_extends_path
# ---------------------------------------------------------------------------


def test_resolve_extends_path_package_style_returns_none(tmp_path: Path) -> None:
    """Package-style extends (no ./) should return None (out of scope)."""
    tsconfig = tmp_path / "tsconfig.json"
    tsconfig.write_text("{}", encoding="utf-8")
    result = _resolve_extends_path(tsconfig, "tsconfig/strictest")
    assert result is None


def test_resolve_extends_path_absolute_nonexistent(tmp_path: Path) -> None:
    tsconfig = tmp_path / "tsconfig.json"
    tsconfig.write_text("{}", encoding="utf-8")
    result = _resolve_extends_path(tsconfig, "/nonexistent/path.json")
    assert result is None


def test_resolve_extends_path_relative_json_file_exists(tmp_path: Path) -> None:
    base = tmp_path / "tsconfig.base.json"
    base.write_text("{}", encoding="utf-8")
    tsconfig = tmp_path / "tsconfig.json"
    tsconfig.write_text("{}", encoding="utf-8")
    result = _resolve_extends_path(tsconfig, "./tsconfig.base.json")
    assert result is not None
    assert result.name == "tsconfig.base.json"


def test_resolve_extends_path_adds_json_extension(tmp_path: Path) -> None:
    base = tmp_path / "tsconfig.base.json"
    base.write_text("{}", encoding="utf-8")
    tsconfig = tmp_path / "tsconfig.json"
    tsconfig.write_text("{}", encoding="utf-8")
    # Without .json suffix
    result = _resolve_extends_path(tsconfig, "./tsconfig.base")
    assert result is not None


def test_resolve_extends_path_empty_suffix_tries_tsconfig_json(tmp_path: Path) -> None:
    """Path with no suffix should try <path>/tsconfig.json."""
    subdir = tmp_path / "shared"
    subdir.mkdir()
    (subdir / "tsconfig.json").write_text("{}", encoding="utf-8")
    tsconfig = tmp_path / "tsconfig.json"
    tsconfig.write_text("{}", encoding="utf-8")
    result = _resolve_extends_path(tsconfig, "./shared")
    assert result is not None


# ---------------------------------------------------------------------------
# _collect_tsconfig_chain
# ---------------------------------------------------------------------------


def test_collect_tsconfig_chain_single(tmp_path: Path) -> None:
    f = tmp_path / "tsconfig.json"
    f.write_text(json.dumps({"compilerOptions": {"baseUrl": "."}}), encoding="utf-8")
    chain = _collect_tsconfig_chain(f)
    assert len(chain) == 1
    assert chain[0] == f.resolve()


def test_collect_tsconfig_chain_cycle_prevention(tmp_path: Path) -> None:
    """Self-extending tsconfig should not cause infinite loop."""
    f = tmp_path / "tsconfig.json"
    f.write_text(json.dumps({"extends": "./tsconfig.json"}), encoding="utf-8")
    chain = _collect_tsconfig_chain(f)
    # Should stop after detecting cycle
    assert len(chain) == 1


def test_collect_tsconfig_chain_extends_non_string(tmp_path: Path) -> None:
    f = tmp_path / "tsconfig.json"
    f.write_text(json.dumps({"extends": 42}), encoding="utf-8")
    chain = _collect_tsconfig_chain(f)
    assert len(chain) == 1


def test_collect_tsconfig_chain_parent_not_found(tmp_path: Path) -> None:
    f = tmp_path / "tsconfig.json"
    f.write_text(json.dumps({"extends": "./nonexistent.json"}), encoding="utf-8")
    chain = _collect_tsconfig_chain(f)
    assert len(chain) == 1  # stops when parent not found


# ---------------------------------------------------------------------------
# _iter_effective_paths
# ---------------------------------------------------------------------------


def test_iter_effective_paths_invalid_base_url_type(tmp_path: Path) -> None:
    """baseUrl of non-string type should be skipped."""
    f = tmp_path / "tsconfig.json"
    f.write_text(
        json.dumps({"compilerOptions": {"baseUrl": 42, "paths": {"@a/*": ["a/*"]}}}),
        encoding="utf-8",
    )
    result = _iter_effective_paths(f)
    assert result == []


def test_iter_effective_paths_shadowed_empty_targets(tmp_path: Path) -> None:
    """Alias with empty typed_targets should be shadowed (skipped)."""
    f = tmp_path / "tsconfig.json"
    f.write_text(
        json.dumps(
            {
                "compilerOptions": {
                    "baseUrl": ".",
                    "paths": {"@a/*": [123, 456]},  # non-string targets
                }
            }
        ),
        encoding="utf-8",
    )
    result = _iter_effective_paths(f)
    assert result == []


def test_iter_effective_paths_valid(tmp_path: Path) -> None:
    f = tmp_path / "tsconfig.json"
    f.write_text(
        json.dumps(
            {
                "compilerOptions": {
                    "baseUrl": ".",
                    "paths": {"@components/*": ["src/components/*"]},
                }
            }
        ),
        encoding="utf-8",
    )
    result = _iter_effective_paths(f)
    assert len(result) == 1
    _, alias, targets = result[0]
    assert alias == "@components/*"


# ---------------------------------------------------------------------------
# _match_alias_pattern
# ---------------------------------------------------------------------------


def test_match_alias_pattern_exact_no_wildcard() -> None:
    assert _match_alias_pattern("@app", "@app") == ""
    assert _match_alias_pattern("@app", "@other") is None


def test_match_alias_pattern_wildcard() -> None:
    assert _match_alias_pattern("@a/*", "@a/utils") == "utils"


def test_match_alias_pattern_no_match_prefix() -> None:
    assert _match_alias_pattern("@a/*", "@b/utils") is None


def test_match_alias_pattern_multiple_wildcards_returns_none() -> None:
    assert _match_alias_pattern("@a/*/x/*", "@a/foo/x/bar") is None


def test_match_alias_pattern_suffix_mismatch() -> None:
    assert _match_alias_pattern("@a/*.test", "@a/foo.spec") is None


# ---------------------------------------------------------------------------
# _expand_target_pattern
# ---------------------------------------------------------------------------


def test_expand_target_pattern_no_wildcard_empty_capture() -> None:
    assert _expand_target_pattern("src/utils", "") == "src/utils"


def test_expand_target_pattern_no_wildcard_nonempty_capture_returns_none() -> None:
    assert _expand_target_pattern("src/utils", "extra") is None


def test_expand_target_pattern_with_wildcard() -> None:
    assert _expand_target_pattern("src/components/*", "Button") == "src/components/Button"


def test_expand_target_pattern_multiple_wildcards_returns_none() -> None:
    assert _expand_target_pattern("src/*/sub/*", "x") is None


# ---------------------------------------------------------------------------
# _resolve_candidate_file
# ---------------------------------------------------------------------------


def test_resolve_candidate_file_ts_file_exists(tmp_path: Path) -> None:
    f = tmp_path / "Button.ts"
    f.write_text("export default {}", encoding="utf-8")
    result = _resolve_candidate_file(tmp_path / "Button.ts")
    assert result == f


def test_resolve_candidate_file_without_extension_tries_ts(tmp_path: Path) -> None:
    f = tmp_path / "utils.ts"
    f.write_text("", encoding="utf-8")
    result = _resolve_candidate_file(tmp_path / "utils")
    assert result is not None
    assert result.suffix == ".ts"


def test_resolve_candidate_file_index_ts(tmp_path: Path) -> None:
    subdir = tmp_path / "components"
    subdir.mkdir()
    idx = subdir / "index.ts"
    idx.write_text("", encoding="utf-8")
    result = _resolve_candidate_file(tmp_path / "components")
    assert result == idx


def test_resolve_candidate_file_no_match_returns_none(tmp_path: Path) -> None:
    result = _resolve_candidate_file(tmp_path / "nonexistent")
    assert result is None


def test_resolve_candidate_file_tsx(tmp_path: Path) -> None:
    f = tmp_path / "Button.tsx"
    f.write_text("", encoding="utf-8")
    result = _resolve_candidate_file(tmp_path / "Button")
    assert result == f


# ---------------------------------------------------------------------------
# resolve_tsconfig_alias_import — top-level
# ---------------------------------------------------------------------------


def test_resolve_alias_no_tsconfig(tmp_path: Path) -> None:
    """No tsconfig.json → return None."""
    result = resolve_tsconfig_alias_import(tmp_path, Path("src/foo.ts"), "@a/utils")
    assert result is None


def test_resolve_alias_relative_import_skipped(tmp_path: Path) -> None:
    result = resolve_tsconfig_alias_import(tmp_path, Path("src/a.ts"), "./utils")
    assert result is None


def test_resolve_alias_resolves_to_ts_file(tmp_path: Path) -> None:
    # Create tsconfig
    tsconfig = tmp_path / "tsconfig.json"
    tsconfig.write_text(
        json.dumps(
            {
                "compilerOptions": {
                    "baseUrl": ".",
                    "paths": {"@utils/*": ["src/utils/*"]},
                }
            }
        ),
        encoding="utf-8",
    )
    # Create target file
    utils_dir = tmp_path / "src" / "utils"
    utils_dir.mkdir(parents=True)
    (utils_dir / "helpers.ts").write_text("export function h() {}", encoding="utf-8")

    result = resolve_tsconfig_alias_import(tmp_path, Path("src/a.ts"), "@utils/helpers")
    assert result is not None
    assert result.suffix == ".ts"


def test_resolve_alias_no_match_returns_none(tmp_path: Path) -> None:
    tsconfig = tmp_path / "tsconfig.json"
    tsconfig.write_text(
        json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@a/*": ["src/a/*"]}}}),
        encoding="utf-8",
    )
    result = resolve_tsconfig_alias_import(tmp_path, Path("src/x.ts"), "@b/notmatch")
    assert result is None
