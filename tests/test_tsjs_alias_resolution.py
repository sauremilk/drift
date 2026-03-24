from __future__ import annotations

from pathlib import Path

from drift.analyzers.typescript.alias_resolver import resolve_tsconfig_alias_import


def test_resolve_tsconfig_alias_import_resolves_two_aliases_and_ignores_unknown() -> None:
    repo_path = Path(__file__).parent / "fixtures" / "tsjs_alias_resolution"
    source_path = Path("src/app.ts")

    resolved_core = resolve_tsconfig_alias_import(repo_path, source_path, "@core/logger")
    resolved_shared = resolve_tsconfig_alias_import(repo_path, source_path, "@shared/config")
    unresolved = resolve_tsconfig_alias_import(repo_path, source_path, "@unknown/missing")

    assert resolved_core == Path("src/core/logger.ts")
    assert resolved_shared == Path("src/shared/config.ts")
    assert unresolved is None
