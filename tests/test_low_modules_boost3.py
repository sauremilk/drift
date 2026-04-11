from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from drift.models import FunctionInfo, SignalType


def test_cross_package_import_ban_rule(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from drift.rules.tsjs.cross_package_import_ban import (
        _load_allowed_package_import_pairs,
        run_cross_package_import_ban,
    )

    cfg = tmp_path / "cross.json"
    cfg.write_text(
        json.dumps(
            {
                "allowed_package_import_pairs": [
                    ["pkg.a", "pkg.b"],
                    {
                        "source_package": "pkg.c",
                        "target_package": "pkg.d",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    allowed = _load_allowed_package_import_pairs(cfg)
    assert ("pkg.a", "pkg.b") in allowed
    assert ("pkg.c", "pkg.d") in allowed

    bad = tmp_path / "bad.json"
    bad.write_text("not-json", encoding="utf-8")
    assert _load_allowed_package_import_pairs(bad) == set()

    monkeypatch.setattr(
        "drift.rules.tsjs.cross_package_import_ban.assign_ts_sources_to_workspace_packages",
        lambda _repo: {
            "a.ts": "pkg.a",
            "b.ts": "pkg.b",
            "c.ts": "pkg.a",
            "d.ts": "pkg.a",
        },
    )
    monkeypatch.setattr(
        "drift.rules.tsjs.cross_package_import_ban.build_relative_import_graph",
        lambda _repo: {
            "a.ts": {"b.ts", "c.ts"},
            "c.ts": {"d.ts"},
            "x.ts": {"b.ts"},
        },
    )

    findings = run_cross_package_import_ban(tmp_path, cfg)
    assert len(findings) == 0  # a->b allowed, others same-package or unknown

    cfg.write_text("{}", encoding="utf-8")
    findings2 = run_cross_package_import_ban(tmp_path, cfg)
    assert len(findings2) == 1
    assert findings2[0]["rule_id"] == "cross-package-import-ban"


def test_mutant_duplicates_semantic_phase() -> None:
    from drift.signals.mutant_duplicates import MutantDuplicateSignal

    signal = MutantDuplicateSignal()

    fn_a = FunctionInfo(
        name="mod.fn_a",
        file_path=Path("src/a.py"),
        start_line=10,
        end_line=20,
        language="python",
    )
    fn_b = FunctionInfo(
        name="mod.fn_b",
        file_path=Path("src/b.py"),
        start_line=12,
        end_line=22,
        language="python",
    )

    fn_key_map = {"a": fn_a, "b": fn_b}
    embedding_cache = {"a": [0.1, 0.2], "b": [0.1, 0.21]}
    ngram_cache = {"a": [("x", "y")], "b": [("z", "w")]}

    class _Emb:
        def build_index(self, vectors):
            return object()

        def search_index(self, index, vector, top_k=5):
            if vector == embedding_cache["a"]:
                return [(0, 1.0), (1, 0.9)]
            return [(1, 1.0), (0, 0.9)]

    findings = signal._find_semantic_duplicates(
        [fn_a, fn_b],
        fn_key_map,
        embedding_cache,
        ngram_cache,
        checked=set(),
        emb=_Emb(),
        ast_threshold=0.8,
    )
    assert findings
    assert findings[0].signal_type == SignalType.MUTANT_DUPLICATE

    # branch: too few vectors
    none_findings = signal._find_semantic_duplicates(
        [fn_a],
        {"a": fn_a},
        {"a": [0.1]},
        {"a": [("x", "y")]},
        checked=set(),
        emb=_Emb(),
    )
    assert none_findings == []

    # branch: no index
    class _EmbNone(_Emb):
        def build_index(self, vectors):
            return None

    no_index = signal._find_semantic_duplicates(
        [fn_a, fn_b],
        fn_key_map,
        embedding_cache,
        ngram_cache,
        checked=set(),
        emb=_EmbNone(),
    )
    assert no_index == []


def test_a2a_router_handlers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import drift.serve.a2a_router as router

    monkeypatch.setattr(router, "_validate_repo_path", lambda p: str(tmp_path))

    monkeypatch.setattr("drift.api.scan", lambda **kwargs: {"tool": "scan", **kwargs})
    monkeypatch.setattr("drift.api.diff", lambda **kwargs: {"tool": "diff", **kwargs})
    monkeypatch.setattr("drift.api.explain", lambda **kwargs: {"tool": "explain", **kwargs})
    monkeypatch.setattr("drift.api.fix_plan", lambda **kwargs: {"tool": "fix_plan", **kwargs})
    monkeypatch.setattr("drift.api.validate", lambda **kwargs: {"tool": "validate", **kwargs})
    monkeypatch.setattr("drift.api.nudge", lambda **kwargs: {"tool": "nudge", **kwargs})
    monkeypatch.setattr("drift.api.brief", lambda **kwargs: {"tool": "brief", **kwargs})
    monkeypatch.setattr(
        "drift.api.negative_context", lambda **kwargs: {"tool": "negative_context", **kwargs}
    )

    assert router._handle_scan({"path": "."})["tool"] == "scan"
    assert router._handle_diff({"path": ".", "diff_ref": "HEAD~2"})["tool"] == "diff"
    assert router._handle_explain({"path": ".", "topic": "PFS"})["tool"] == "explain"
    assert router._handle_fix_plan({"path": ".", "max_tasks": 3})["tool"] == "fix_plan"
    assert router._handle_validate({"path": "."})["tool"] == "validate"
    assert router._handle_nudge({"path": "."})["tool"] == "nudge"
    assert router._handle_brief({"path": ".", "task": "x"})["tool"] == "brief"
    assert router._handle_negative_context({"path": "."})["tool"] == "negative_context"

    with pytest.raises(ValueError):
        router._handle_explain({"path": "."})


def test_signal_mapping_helpers() -> None:
    import drift.signal_mapping as sm

    mapping = sm.signal_abbrev_map()
    assert mapping["PFS"] == "pattern_fragmentation"
    assert sm.resolve_signal("PFS") is not None
    assert sm.resolve_signal("pattern_fragmentation") is not None
    assert sm.resolve_signal("UNKNOWN") is None
    assert sm.signal_abbrev("pattern_fragmentation") == "PFS"
    assert sm.signal_abbrev("custom_signal") == "CUS"

    assert sm.signal_scope_label(selected=[" pfs ", "mds"]) == "MDS+PFS"
    assert sm.signal_scope_label(ignored=[" avs ", "mds"]) == "all-minus:AVS+MDS"
    assert sm.signal_scope_label() == "all"


def test_package_init_exposes_version() -> None:
    import drift

    assert hasattr(drift, "__version__")


def test_alias_resolver_paths(tmp_path: Path) -> None:
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

    repo = tmp_path
    src = repo / "src"
    pkg = src / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "thing.ts").write_text("export const x = 1", encoding="utf-8")
    (src / "index.ts").write_text("export * from './pkg/thing'", encoding="utf-8")

    base_cfg = repo / "base.json"
    base_cfg.write_text(
        '{"compilerOptions": {"baseUrl": "src", "paths": {"@pkg/*": ["pkg/*"]}}}',
        encoding="utf-8",
    )
    ts_cfg = repo / "tsconfig.json"
    ts_cfg.write_text(
        json.dumps(
            {
                "extends": "./base.json",
                "compilerOptions": {
                    "baseUrl": "src",
                    "paths": {"@pkg/*": ["pkg/*"]},
                },
            }
        ),
        encoding="utf-8",
    )

    assert _load_tsconfig_data(ts_cfg) is not None
    assert _load_compiler_options(ts_cfg)
    assert _resolve_extends_path(ts_cfg, "./base.json") is not None
    assert _collect_tsconfig_chain(ts_cfg)
    assert _iter_effective_paths(ts_cfg)
    assert _match_alias_pattern("@pkg/*", "@pkg/thing") == "thing"
    assert _match_alias_pattern("@pkg", "@pkg") == ""
    assert _match_alias_pattern("@pkg/*", "@other/x") is None
    assert _expand_target_pattern("pkg/*", "thing") == "pkg/thing"
    assert _expand_target_pattern("pkg", "") == "pkg"
    assert _expand_target_pattern("pkg", "x") is None

    assert _resolve_candidate_file(src / "pkg" / "thing") is not None
    assert _resolve_candidate_file(src / "pkg" / "missing") is None

    resolved = resolve_tsconfig_alias_import(repo, Path("src/app.ts"), "@pkg/thing")
    assert resolved == Path("src/pkg/thing.ts")
    assert resolve_tsconfig_alias_import(repo, Path("src/app.ts"), "./local") is None


def test_barrel_resolver_paths(tmp_path: Path) -> None:
    from drift.analyzers.typescript.barrel_resolver import (
        _extract_barrel_exports,
        _parse_named_export_names,
        _resolve_relative_target,
        resolve_index_barrel_target,
    )

    repo = tmp_path
    feat = repo / "src" / "feat"
    feat.mkdir(parents=True)
    (feat / "impl.ts").write_text("export const foo = 1", encoding="utf-8")
    (feat / "other.ts").write_text("export const bar = 1", encoding="utf-8")
    index = feat / "index.ts"
    index.write_text(
        "export { foo as renamed } from './impl'\nexport * from './other'\n",
        encoding="utf-8",
    )

    names = _parse_named_export_names("type A, b as c, d")
    assert names == {"A", "c", "d"}
    exports = _extract_barrel_exports(index.read_text(encoding="utf-8"))
    assert len(exports) == 2

    resolved_rel = _resolve_relative_target(repo, Path("src/feat/index.ts"), "./impl")
    assert resolved_rel == Path("src/feat/impl.ts")
    assert _resolve_relative_target(repo, Path("src/feat/index.ts"), "pkg") is None

    # Ambiguous (star + named match) => None
    assert resolve_index_barrel_target(repo, Path("src/feat/index.ts"), {"renamed"}) is None

    index.write_text("export { foo } from './impl'\n", encoding="utf-8")
    single = resolve_index_barrel_target(repo, Path("src/feat/index.ts"), {"foo"})
    assert single == Path("src/feat/impl.ts")


def test_api_validate_core_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import importlib

    validate_mod = importlib.import_module("drift.api.validate")
    monkeypatch.setattr(validate_mod, "_emit_api_telemetry", lambda **kwargs: None)

    # traversal guard
    outside = Path.cwd().anchor + "\\outside.json"
    out = validate_mod.validate(path=tmp_path, config_file=outside)
    assert out["type"] == "error"

    # happy path with baseline compare
    class _W:
        def as_dict(self):
            return {"pattern_fragmentation": 1.0}

    cfg = SimpleNamespace(
        weights=_W(),
        thresholds=SimpleNamespace(similarity_threshold=0.8),
        include=["**/*.py"],
        exclude=[],
        embeddings_enabled=True,
    )
    monkeypatch.setattr(validate_mod, "_load_config_cached", lambda *_a, **_k: cfg)
    monkeypatch.setattr(
        "drift.config.DriftConfig._find_config_file", lambda _repo: tmp_path / "drift.yaml"
    )
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(
        "drift.ingestion.file_discovery.discover_files",
        lambda *_a, **_k: [
            SimpleNamespace(language="python"),
            SimpleNamespace(language="typescript"),
        ],
    )

    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"drift_score": 0.6}', encoding="utf-8")
    monkeypatch.setattr("drift.baseline.load_baseline", lambda _p: {"fp1"})
    monkeypatch.setattr("drift.api.scan", lambda *_a, **_k: {"drift_score": 0.4})
    monkeypatch.setattr(
        "drift.analyzer.analyze_repo", lambda *_a, **_k: SimpleNamespace(findings=[])
    )
    monkeypatch.setattr("drift.baseline.baseline_diff", lambda findings, fps: ([], []))

    ok = validate_mod.validate(path=tmp_path, baseline_file=str(baseline))
    assert ok["valid"] is True
    assert ok["progress"]["direction"] == "improved"
