"""File-level parse result caching for Drift.

Caches parse results keyed by file content SHA-256 to skip re-parsing
unchanged files across runs. Stored as JSON in the configured cache_dir.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from drift.models import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    ParseResult,
    PatternCategory,
    PatternInstance,
)


class ParseCache:
    """Disk-backed parse result cache."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir / "parse"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def file_hash(file_path: Path) -> str:
        """SHA-256 of file content (first 16 hex chars)."""
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()[:16]

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
        self._cache_path(content_hash).write_text(
            json.dumps(data, default=str), encoding="utf-8"
        )


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
