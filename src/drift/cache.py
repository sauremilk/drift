"""File-level parse result caching for Drift.

Caches parse results keyed by file content SHA-256 to skip re-parsing
unchanged files across runs. Stored as JSON in the configured cache_dir.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

from drift.models import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    ParseResult,
    PatternCategory,
    PatternInstance,
)

if TYPE_CHECKING:
    from drift.models import Finding

logger = logging.getLogger("drift")


class ParseCache:
    """Disk-backed parse result cache."""

    # Evict entries not accessed in the last 7 days.
    _EVICTION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
    # 128-bit prefix keeps filenames compact while materially reducing
    # collision probability versus 64-bit truncation on large repositories.
    _HASH_HEX_LEN = 32

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir / "parse"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._evict_stale()

    def _evict_stale(self) -> None:
        """Remove cache entries older than ``_EVICTION_MAX_AGE_SECONDS``."""
        cutoff = time.time() - self._EVICTION_MAX_AGE_SECONDS
        for entry in self._cache_dir.glob("*.json"):
            try:
                if entry.stat().st_mtime < cutoff:
                    entry.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def file_hash(file_path: Path) -> str:
        """SHA-256 of file content (first 32 hex chars, 128-bit)."""
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()[:ParseCache._HASH_HEX_LEN]

    def _cache_path(self, content_hash: str) -> Path:
        return self._cache_dir / f"{content_hash}.json"

    def get(self, content_hash: str) -> ParseResult | None:
        """Look up a cached parse result. Returns None on miss."""
        path = self._cache_path(content_hash)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return _deserialize(data)
        except Exception:
            # Corrupted cache entry — remove and miss
            path.unlink(missing_ok=True)
            return None

    def put(self, content_hash: str, result: ParseResult) -> None:
        """Store a parse result in the cache."""
        data = _serialize(result)
        try:
            self._cache_path(content_hash).write_text(
                json.dumps(data, default=str), encoding="utf-8"
            )
        except OSError:
            # Cache is an optimization only; analysis must proceed without it.
            return


def _serialize(pr: ParseResult) -> dict[str, Any]:
    return {
        "file_path": pr.file_path.as_posix(),
        "language": pr.language,
        "line_count": pr.line_count,
        "parse_errors": pr.parse_errors,
        "functions": [_ser_func(f) for f in pr.functions],
        "classes": [_ser_class(c) for c in pr.classes],
        "imports": [_ser_import(i) for i in pr.imports],
        "patterns": [_ser_pattern(p) for p in pr.patterns],
    }


def _ser_func(f: FunctionInfo) -> dict[str, Any]:
    return {
        "name": f.name,
        "file_path": f.file_path.as_posix(),
        "start_line": f.start_line,
        "end_line": f.end_line,
        "language": f.language,
        "complexity": f.complexity,
        "loc": f.loc,
        "parameters": f.parameters,
        "return_type": f.return_type,
        "decorators": f.decorators,
        "has_docstring": f.has_docstring,
        "body_hash": f.body_hash,
        "ast_fingerprint": f.ast_fingerprint,
    }


def _ser_class(c: ClassInfo) -> dict[str, Any]:
    return {
        "name": c.name,
        "file_path": c.file_path.as_posix(),
        "start_line": c.start_line,
        "end_line": c.end_line,
        "language": c.language,
        "bases": c.bases,
        "methods": [_ser_func(m) for m in c.methods],
        "has_docstring": c.has_docstring,
    }


def _ser_import(i: ImportInfo) -> dict[str, Any]:
    return {
        "source_file": i.source_file.as_posix(),
        "imported_module": i.imported_module,
        "imported_names": i.imported_names,
        "line_number": i.line_number,
        "is_relative": i.is_relative,
        "is_module_level": i.is_module_level,
    }


def _ser_pattern(p: PatternInstance) -> dict[str, Any]:
    return {
        "category": p.category.value,
        "file_path": p.file_path.as_posix(),
        "function_name": p.function_name,
        "start_line": p.start_line,
        "end_line": p.end_line,
        "fingerprint": p.fingerprint,
        "variant_id": p.variant_id,
    }


def _deserialize(data: dict[str, Any]) -> ParseResult:
    return ParseResult(
        file_path=Path(data["file_path"]),
        language=data["language"],
        line_count=data.get("line_count", 0),
        parse_errors=data.get("parse_errors", []),
        functions=[_deser_func(f) for f in data.get("functions", [])],
        classes=[_deser_class(c) for c in data.get("classes", [])],
        imports=[_deser_import(i) for i in data.get("imports", [])],
        patterns=[_deser_pattern(p) for p in data.get("patterns", [])],
    )


def _deser_func(d: dict[str, Any]) -> FunctionInfo:
    return FunctionInfo(
        name=d["name"],
        file_path=Path(d["file_path"]),
        start_line=d["start_line"],
        end_line=d["end_line"],
        language=d["language"],
        complexity=d.get("complexity", 0),
        loc=d.get("loc", 0),
        parameters=d.get("parameters", []),
        return_type=d.get("return_type"),
        decorators=d.get("decorators", []),
        has_docstring=d.get("has_docstring", False),
        body_hash=d.get("body_hash", ""),
        ast_fingerprint=d.get("ast_fingerprint", {}),
    )


def _deser_class(d: dict[str, Any]) -> ClassInfo:
    return ClassInfo(
        name=d["name"],
        file_path=Path(d["file_path"]),
        start_line=d["start_line"],
        end_line=d["end_line"],
        language=d["language"],
        bases=d.get("bases", []),
        methods=[_deser_func(m) for m in d.get("methods", [])],
        has_docstring=d.get("has_docstring", False),
    )


def _deser_import(d: dict[str, Any]) -> ImportInfo:
    return ImportInfo(
        source_file=Path(d["source_file"]),
        imported_module=d["imported_module"],
        imported_names=d.get("imported_names", []),
        line_number=d["line_number"],
        is_relative=d.get("is_relative", False),
        is_module_level=d.get("is_module_level", True),
    )


def _deser_pattern(d: dict[str, Any]) -> PatternInstance:
    return PatternInstance(
        category=PatternCategory(d["category"]),
        file_path=Path(d["file_path"]),
        function_name=d["function_name"],
        start_line=d["start_line"],
        end_line=d["end_line"],
        fingerprint=d.get("fingerprint", {}),
        variant_id=d.get("variant_id", ""),
    )


# ---------------------------------------------------------------------------
# Signal-level finding cache
# ---------------------------------------------------------------------------

# Version tag embedded in each cache entry.  Bump when the Finding
# dataclass or signal contract changes in an incompatible way.
# v3: migrated from pickle to JSON to eliminate CWE-502 deserialization risk.
_SIGNAL_CACHE_VERSION = 3


class SignalCache:
    """Disk-backed cache for per-signal findings keyed by content hashes.

    The cache key is ``(signal_type, config_fingerprint, content_hash)``
    where *content_hash* is the combined hash of all ParseResult content
    hashes fed into the signal.  For per-file signals the content hash
    is that of a single file; for cross-file signals it is a hash over
    the sorted file hashes of all inputs.

    Entries are stored as JSON to avoid unsafe deserialization (CWE-502).
    Path objects and enums are serialized as strings.
    A version tag invalidates stale entries automatically.
    """

    _EVICTION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir / "signals"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._evict_stale()

    def _evict_stale(self) -> None:
        cutoff = time.time() - self._EVICTION_MAX_AGE_SECONDS
        for entry in self._cache_dir.glob("*.json"):
            try:
                if entry.stat().st_mtime < cutoff:
                    entry.unlink(missing_ok=True)
            except OSError:
                pass
        # Clean up legacy pickle files from v2 cache.
        for entry in self._cache_dir.glob("*.pkl"):
            with suppress(OSError):
                entry.unlink(missing_ok=True)

    @staticmethod
    def config_fingerprint(config: object) -> str:
        """Derive a short fingerprint from the DriftConfig thresholds.

        We hash the JSON-serialised thresholds + weights so that a
        config change invalidates signal caches automatically.
        """
        from drift.config import DriftConfig

        if not isinstance(config, DriftConfig):
            return "unknown"
        payload = json.dumps(
            {
                "weights": config.weights.model_dump(mode="python"),
                "thresholds": config.thresholds.model_dump(mode="python"),
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @staticmethod
    def content_hash_for_file(file_hash: str) -> str:
        """Return the cache-key content hash for a single file.

        For file-local signals the per-file content hash *is* the file
        hash itself (already a 32-char SHA-256 prefix produced by
        ``ParseCache.file_hash``).
        """
        return file_hash

    @staticmethod
    def content_hash_for_results(
        parse_results: list[ParseResult],
        file_hashes: dict[str, str],
    ) -> str:
        """Compute a combined content hash over multiple ParseResults.

        *file_hashes* maps ``file_path.as_posix()`` → content SHA-256
        (the same hashes produced by ``ParseCache.file_hash``).
        """
        parts: list[str] = []
        for pr in sorted(parse_results, key=lambda p: p.file_path.as_posix()):
            h = file_hashes.get(pr.file_path.as_posix(), "")
            parts.append(h)
        combined = "|".join(parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def _cache_path(self, signal_type: str, config_fp: str, content_hash: str) -> Path:
        key = f"{signal_type}_{config_fp}_{content_hash}"
        return self._cache_dir / f"{key}.json"

    def get(
        self, signal_type: str, config_fp: str, content_hash: str,
    ) -> list[Finding] | None:
        """Retrieve cached findings or ``None`` on miss."""
        path = self._cache_path(signal_type, config_fp, content_hash)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("_v") != _SIGNAL_CACHE_VERSION:
                path.unlink(missing_ok=True)
                return None
            raw_findings = data.get("findings")
            if not isinstance(raw_findings, list):
                path.unlink(missing_ok=True)
                return None
            return [_deser_finding(f) for f in raw_findings]
        except Exception:
            path.unlink(missing_ok=True)
            return None

    def put(
        self,
        signal_type: str,
        config_fp: str,
        content_hash: str,
        findings: list[Finding],
    ) -> None:
        """Store findings in the cache."""
        path = self._cache_path(signal_type, config_fp, content_hash)
        try:
            payload = json.dumps(
                {"_v": _SIGNAL_CACHE_VERSION, "findings": [_ser_finding(f) for f in findings]},
                default=str,
            )
            path.write_text(payload, encoding="utf-8")
        except OSError:
            return


# ---------------------------------------------------------------------------
# Finding JSON serialization (replaces pickle — CWE-502 fix)
# ---------------------------------------------------------------------------


def _ser_finding(f: Finding) -> dict[str, Any]:
    """Serialize a Finding to a JSON-safe dictionary."""
    return {
        "signal_type": f.signal_type if f.signal_type else None,
        "severity": f.severity.value if f.severity else None,
        "score": f.score,
        "title": f.title,
        "description": f.description,
        "file_path": f.file_path.as_posix() if f.file_path else None,
        "start_line": f.start_line,
        "end_line": f.end_line,
        "symbol": f.symbol,
        "related_files": [p.as_posix() for p in f.related_files],
        "commit_hash": f.commit_hash,
        "ai_attributed": f.ai_attributed,
        "fix": f.fix,
        "impact": f.impact,
        "score_contribution": f.score_contribution,
        "deferred": f.deferred,
        "metadata": f.metadata,
        "rule_id": f.rule_id,
    }


def _deser_finding(d: dict[str, Any]) -> Finding:
    """Deserialize a Finding from a JSON dictionary."""
    from drift.models import Finding, Severity, SignalType

    return Finding(
        signal_type=SignalType(d["signal_type"]),
        severity=Severity(d["severity"]),
        score=d.get("score", 0.0),
        title=d.get("title", ""),
        description=d.get("description", ""),
        file_path=Path(d["file_path"]) if d.get("file_path") else None,
        start_line=d.get("start_line"),
        end_line=d.get("end_line"),
        symbol=d.get("symbol"),
        related_files=[Path(p) for p in d.get("related_files", [])],
        commit_hash=d.get("commit_hash"),
        ai_attributed=d.get("ai_attributed", False),
        fix=d.get("fix"),
        impact=d.get("impact", 0.0),
        score_contribution=d.get("score_contribution", 0.0),
        deferred=d.get("deferred", False),
        metadata=d.get("metadata", {}),
        rule_id=d.get("rule_id"),
    )
