"""Coverage tests for cache and helper branches.

Includes mutant_duplicates, exception_contract_drift,
cli._machine_error_enabled, and negative_context paths.
"""

from __future__ import annotations

import ast
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

from drift.cache import ParseCache, SignalCache
from drift.cli import _machine_error_enabled
from drift.config import DriftConfig
from drift.models import (
    Finding,
    FunctionInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals.exception_contract_drift import _extract_exception_profile
from drift.signals.mutant_duplicates import (
    MutantDuplicateSignal,
    _is_protocol_method_pair,
    _is_thin_wrapper,
    _name_token_similarity,
    _structural_similarity,
    _tokenize_name,
)

# ── cache: ParseCache._evict_stale ────────────────────────────────────────────


def test_parse_cache_evicts_old_json_entry(tmp_path: Path) -> None:
    """Lines 53-54: stale JSON cache file gets deleted during init."""
    cache_dir = tmp_path / "parse"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create a "stale" JSON file
    stale = cache_dir / "old_entry.json"
    stale.write_text("{}", encoding="utf-8")

    # Set mtime to 8 days ago (> eviction threshold of 7 days)
    eight_days_ago = time.time() - 8 * 24 * 3600
    os.utime(stale, (eight_days_ago, eight_days_ago))

    # Re-creating ParseCache should evict the stale file
    ParseCache(tmp_path)
    assert not stale.exists()


def test_parse_cache_keeps_fresh_entry(tmp_path: Path) -> None:
    """Fresh cache entries are not evicted."""
    ParseCache(tmp_path)
    cache_dir = tmp_path / "parse"
    fresh = cache_dir / "fresh_entry.json"
    fresh.write_text("{}", encoding="utf-8")

    # New instance - fresh file should remain
    ParseCache(tmp_path)
    assert fresh.exists()


# ── cache: SignalCache get/put paths ──────────────────────────────────────────


def test_signal_cache_put_then_get_roundtrip(tmp_path: Path) -> None:
    """Lines 330-339: put() writes cache; get() reads it back."""
    sc = SignalCache(tmp_path)
    findings: list[Finding] = []
    sc.put("PFS", "fp1", "hash1", findings)
    result = sc.get("PFS", "fp1", "hash1")
    assert result == []


def test_signal_cache_get_miss_returns_none(tmp_path: Path) -> None:
    """get() returns None on cache miss."""
    sc = SignalCache(tmp_path)
    assert sc.get("PFS", "fp1", "missing_hash") is None


def test_signal_cache_get_wrong_version_returns_none(tmp_path: Path) -> None:
    """Lines 261-262: cache entry with wrong _v is rejected."""
    sc = SignalCache(tmp_path)
    # Write cache entry with old version
    cache_dir = tmp_path / "signals"
    cache_file = cache_dir / "PFS_fp1_hash2.json"
    cache_file.write_text(json.dumps({"_v": 999, "findings": []}), encoding="utf-8")

    result = sc.get("PFS", "fp1", "hash2")
    assert result is None
    assert not cache_file.exists()  # stale file removed


def test_signal_cache_get_bad_findings_format_returns_none(tmp_path: Path) -> None:
    """Lines 265-266: cache entry where findings is not a list is rejected."""
    sc = SignalCache(tmp_path)
    from drift.cache import _SIGNAL_CACHE_VERSION

    cache_dir = tmp_path / "signals"
    cache_file = cache_dir / "PFS_fp1_hash3.json"
    cache_file.write_text(
        json.dumps({"_v": _SIGNAL_CACHE_VERSION, "findings": "not_a_list"}),
        encoding="utf-8",
    )

    result = sc.get("PFS", "fp1", "hash3")
    assert result is None


def test_signal_cache_get_corrupt_json_returns_none(tmp_path: Path) -> None:
    """Line 278: corrupt JSON in cache file returns None."""
    sc = SignalCache(tmp_path)
    cache_dir = tmp_path / "signals"
    cache_file = cache_dir / "PFS_fp1_hash4.json"
    cache_file.write_text("NOT VALID JSON !", encoding="utf-8")

    result = sc.get("PFS", "fp1", "hash4")
    assert result is None


def test_signal_cache_put_oserror_does_not_raise(tmp_path: Path) -> None:
    """Lines 356-357: put() silently ignores OSError."""
    sc = SignalCache(tmp_path)
    with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
        sc.put("PFS", "fp1", "hash5", [])  # Should not raise


def test_signal_cache_config_fingerprint_non_config_object(tmp_path: Path) -> None:
    """config_fingerprint returns 'unknown' for non-DriftConfig input."""
    result = SignalCache.config_fingerprint("not a config")
    assert result == "unknown"


def test_signal_cache_evicts_old_signals(tmp_path: Path) -> None:
    """SignalCache._evict_stale removes old signal cache entries."""
    SignalCache(tmp_path)
    cache_dir = tmp_path / "signals"

    stale = cache_dir / "stale.json"
    stale.write_text("{}", encoding="utf-8")
    eight_days_ago = time.time() - 8 * 24 * 3600
    os.utime(stale, (eight_days_ago, eight_days_ago))

    SignalCache(tmp_path)
    assert not stale.exists()


# ── mutant_duplicates: early return with < 2 qualifying functions ─────────────


def _make_mut_fn(
    name: str = "process",
    file_path: str = "src/service.py",
    loc: int = 10,
    complexity: int = 3,
    body_hash: str = "",
    ngrams: list | None = None,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=Path(file_path),
        start_line=1,
        end_line=loc,
        language="python",
        complexity=complexity,
        loc=loc,
        parameters=["x"],
        body_hash=body_hash,
        ast_fingerprint={"ngrams": ngrams or []},
    )


def test_mds_analyze_returns_empty_for_single_function(tmp_path: Path) -> None:
    """Line 203: < 2 qualifying functions → early return []."""
    signal = MutantDuplicateSignal()
    fn = _make_mut_fn(loc=6, complexity=2)
    pr = ParseResult(file_path=Path("src/service.py"), language="python", functions=[fn])
    findings = signal.analyze([pr], {}, DriftConfig())
    assert findings == []


def test_mds_analyze_returns_empty_for_dunder_method(tmp_path: Path) -> None:
    """Dunder methods are excluded → empty if <2 qualifying functions."""
    signal = MutantDuplicateSignal()
    fn1 = _make_mut_fn("__repr__", loc=6, complexity=2)
    fn2 = _make_mut_fn("__str__", loc=7, complexity=2)
    pr = ParseResult(file_path=Path("src/service.py"), language="python", functions=[fn1, fn2])
    findings = signal.analyze([pr], {}, DriftConfig())
    assert findings == []


def test_mds_exact_duplicate_finding_same_dir(tmp_path: Path) -> None:
    """Lines 343-423: exact duplicate (same body_hash) generates finding."""
    signal = MutantDuplicateSignal()
    body_hash = "abcdef1234567890"
    fn1 = _make_mut_fn("process_data", "src/a.py", loc=10, complexity=3, body_hash=body_hash)
    fn2 = _make_mut_fn("process_data_copy", "src/b.py", loc=10, complexity=3, body_hash=body_hash)
    pr1 = ParseResult(file_path=Path("src/a.py"), language="python", functions=[fn1])
    pr2 = ParseResult(file_path=Path("src/b.py"), language="python", functions=[fn2])
    findings = signal.analyze([pr1, pr2], {}, DriftConfig())
    assert any(f.signal_type == SignalType.MUTANT_DUPLICATE for f in findings)


def test_mds_exact_duplicate_cross_dir_finding(tmp_path: Path) -> None:
    """Lines 357-362: exact dups in different parent dirs → common_parent fallback."""
    signal = MutantDuplicateSignal()
    body_hash = "deadbeef12345678"
    fn1 = _make_mut_fn("helper", "src/module_a/utils.py", loc=10, complexity=3, body_hash=body_hash)
    fn2 = _make_mut_fn(
        "helper_copy", "src/module_b/tools.py", loc=10, complexity=3, body_hash=body_hash
    )
    pr1 = ParseResult(file_path=Path("src/module_a/utils.py"), language="python", functions=[fn1])
    pr2 = ParseResult(file_path=Path("src/module_b/tools.py"), language="python", functions=[fn2])
    findings = signal.analyze([pr1, pr2], {}, DriftConfig())
    assert any(f.signal_type == SignalType.MUTANT_DUPLICATE for f in findings)


def test_mds_exact_duplicate_many_functions_name_ellipsis() -> None:
    """Line 412: 6+ functions with same body_hash triggers '+N' in names_str."""
    signal = MutantDuplicateSignal()
    body_hash = "aabbccdd11223344"
    functions = []
    prs = []
    for i in range(7):
        fn = _make_mut_fn(
            f"fn_{i}", f"src/module_{i}/utils.py", loc=10, complexity=3, body_hash=body_hash
        )
        pr = ParseResult(
            file_path=Path(f"src/module_{i}/utils.py"), language="python", functions=[fn]
        )
        functions.append(fn)
        prs.append(pr)
    findings = signal.analyze(prs, {}, DriftConfig())
    titles = [f.title for f in findings if f.signal_type == SignalType.MUTANT_DUPLICATE]
    assert any("+2" in t or "+" in t for t in titles)


# ── mutant_duplicates: helper function unit tests ─────────────────────────────


def test_structural_similarity_empty_returns_zero() -> None:
    """_structural_similarity with None inputs → 0.0."""
    assert _structural_similarity(None, None) == 0.0
    assert _structural_similarity([("Call",)], None) == 0.0


def test_structural_similarity_very_different_sizes() -> None:
    """Size ratio < 0.33 → early return with size_ratio."""
    # 1 ngram vs 10 ngrams
    small = [("Call",)]
    large = [("Name",)] * 10
    result = _structural_similarity(small, large)
    assert result < 0.5


def test_tokenize_name_camel_case() -> None:
    """_tokenize_name splits CamelCase properly."""
    tokens = _tokenize_name("ProcessDataItem")
    assert "process" in tokens
    assert "data" in tokens
    assert "item" in tokens


def test_name_token_similarity_same_name() -> None:
    """Identical names → high similarity."""
    assert _name_token_similarity("process_data", "process_data") == 1.0


def test_name_token_similarity_empty_names() -> None:
    """Both empty → 1.0."""
    assert _name_token_similarity("", "") == 1.0


def test_is_protocol_method_pair_same_class() -> None:
    """Same class → not a protocol pair."""
    a = _make_mut_fn("ClassA.serialize", "src/a.py")
    b = _make_mut_fn("ClassA.serialize", "src/b.py")
    assert not _is_protocol_method_pair(a, b)


def test_is_protocol_method_pair_different_classes() -> None:
    """Different classes with same protocol method → is a pair."""
    a = _make_mut_fn("ClassA.serialize", "src/a.py")
    b = _make_mut_fn("ClassB.serialize", "src/b.py")
    assert _is_protocol_method_pair(a, b)


def test_is_thin_wrapper_loc_too_large() -> None:
    """Function with loc > 5 is not a thin wrapper."""
    fn = _make_mut_fn(loc=10, ngrams=[("Call",)])
    assert not _is_thin_wrapper(fn)


def test_is_thin_wrapper_single_call() -> None:
    """Function with loc <= 5 and single Call ngram is a thin wrapper."""
    fn = _make_mut_fn(loc=3, ngrams=[("Call", "Name")])
    assert _is_thin_wrapper(fn)


# ── exception_contract_drift: _extract_exception_profile helper ───────────────


def test_extract_profile_bare_raise() -> None:
    """has_bare_raise = True when function has bare `raise`."""
    source = "def foo():\n    try:\n        pass\n    except:\n        raise\n"
    tree = ast.parse(source)
    func_node = tree.body[0]
    profile = _extract_exception_profile(func_node)
    assert profile["has_bare_raise"] is True


def test_extract_profile_raise_name_node() -> None:
    """Lines 68-69: `raise ValueError` (Name node, not Call) → adds to raise_types."""
    source = "def foo():\n    raise ValueError\n"
    tree = ast.parse(source)
    func_node = tree.body[0]
    profile = _extract_exception_profile(func_node)
    assert "ValueError" in profile["raise_types"]


def test_extract_profile_raise_call_node() -> None:
    """raise ValueError('msg') (Call node) → adds to raise_types."""
    source = "def foo():\n    raise ValueError('bad input')\n"
    tree = ast.parse(source)
    func_node = tree.body[0]
    profile = _extract_exception_profile(func_node)
    assert "ValueError" in profile["raise_types"]


def test_extract_profile_bare_except() -> None:
    """has_bare_except = True when handler catches bare except."""
    source = "def foo():\n    try:\n        pass\n    except:\n        pass\n"
    tree = ast.parse(source)
    func_node = tree.body[0]
    profile = _extract_exception_profile(func_node)
    assert profile["has_bare_except"] is True


def test_extract_profile_typed_except() -> None:
    """Typed except handler adds to handler_types."""
    source = "def foo():\n    try:\n        pass\n    except ValueError:\n        pass\n"
    tree = ast.parse(source)
    func_node = tree.body[0]
    profile = _extract_exception_profile(func_node)
    assert "ValueError" in profile["handler_types"]


def test_extract_profile_tuple_except() -> None:
    """Tuple except handler (except (A, B)) adds both to handler_types."""
    source = (
        "def foo():\n    try:\n        pass\n    except (ValueError, TypeError):\n        pass\n"
    )
    tree = ast.parse(source)
    func_node = tree.body[0]
    profile = _extract_exception_profile(func_node)
    assert "ValueError" in profile["handler_types"]
    assert "TypeError" in profile["handler_types"]


# ── cli: _machine_error_enabled paths ─────────────────────────────────────────


def test_machine_error_enabled_env_var() -> None:
    """Returns True when DRIFT_ERROR_FORMAT=json env var is set."""
    with patch.dict(os.environ, {"DRIFT_ERROR_FORMAT": "json"}):
        assert _machine_error_enabled() is True


def test_machine_error_enabled_json_flag() -> None:
    """Returns True when --json flag is present."""
    assert _machine_error_enabled(["--json"]) is True


def test_machine_error_enabled_format_json_separate() -> None:
    """Returns True for --format json as separate tokens."""
    assert _machine_error_enabled(["--format", "json"]) is True


def test_machine_error_enabled_format_not_json() -> None:
    """Lines 61-62: --format rich (not json) → idx+=2 continue → returns False."""
    assert _machine_error_enabled(["--format", "rich"]) is False


def test_machine_error_enabled_format_equals_json() -> None:
    """Lines 65-67: --format=json as single token → returns True."""
    assert _machine_error_enabled(["--format=json"]) is True


def test_machine_error_enabled_output_format_equals_json() -> None:
    """Lines 65-67: --output-format=json → returns True."""
    assert _machine_error_enabled(["--output-format=json"]) is True


def test_machine_error_enabled_short_flag_equals_json() -> None:
    """Lines 70-72: -f=json → returns True."""
    assert _machine_error_enabled(["-f=json"]) is True


def test_machine_error_enabled_no_json_flag() -> None:
    """Returns False when no json-related flags present."""
    assert _machine_error_enabled(["--repo", ".", "--format", "rich"]) is False


def test_machine_error_enabled_empty_argv() -> None:
    """Returns False for empty argv."""
    assert _machine_error_enabled([]) is False


# ── negative_context: _scope_from_finding branches ───────────────────────────


def _make_finding(
    *,
    related_files: list[Path] | None = None,
    file_path: Path | None = None,
) -> Finding:
    return Finding(
        signal_type=SignalType.PATTERN_FRAGMENTATION,
        severity=Severity.MEDIUM,
        score=0.5,
        title="Test finding",
        description="desc",
        file_path=file_path,
        related_files=related_files or [],
    )


def test_scope_from_finding_file_scope() -> None:
    """Line 136: file_path set → FILE scope."""
    from drift.negative_context.core import NegativeContextScope, _scope_from_finding

    finding = _make_finding(file_path=Path("src/service.py"))
    scope = _scope_from_finding(finding)
    assert scope == NegativeContextScope.FILE


def test_scope_from_finding_module_scope() -> None:
    """Line 139: no file_path → MODULE scope."""
    from drift.negative_context.core import NegativeContextScope, _scope_from_finding

    finding = _make_finding(file_path=None)
    scope = _scope_from_finding(finding)
    assert scope == NegativeContextScope.MODULE
