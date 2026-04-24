"""Deterministic corpus builder for drift retrieval (ADR-091).

Parses drift's verified fact sources into :class:`FactChunk` records with
stable, structured Fact-IDs. No external parsing dependencies beyond the
Python standard library — policy/ADR/audit parsing is heading-driven
regex, signal parsing uses :mod:`ast`, evidence parsing uses :mod:`json`.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from drift.retrieval.fact_ids import (
    generate_adr_id,
    generate_audit_id,
    generate_evidence_id,
    generate_policy_id,
    generate_roadmap_id,
    generate_signal_id,
)
from drift.retrieval.models import FactChunk

logger = logging.getLogger("drift.retrieval.corpus_builder")

# Ordered tuple so output stays deterministic across runs.
_DEFAULT_SOURCES: tuple[str, ...] = (
    "POLICY.md",
    "ROADMAP.md",
    "docs/decisions",
    "audit_results",
    "src/drift/signals",
    "benchmark_results",
)

_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$")
_ADR_SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$")
_POLICY_SECTION_RE = re.compile(r"^##\s+(?P<number>\d+)\.\s+(?P<title>.+?)\s*$")
_POLICY_PARAGRAPH_RE = re.compile(r"^(?P<num>\d+\.\d+)\s+(?P<body>.+)$")
_AUDIT_TABLE_ROW_RE = re.compile(r"^\|\s*(?P<first>[A-Z0-9][A-Z0-9._-]*)\s*\|")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_corpus(repo_root: Path, sources: Iterable[str] | None = None) -> list[FactChunk]:
    """Build the complete corpus for a drift repository.

    The returned list is sorted by ``fact_id`` so identical inputs yield
    identical output ordering — a precondition for reproducible
    ``corpus_sha256`` digests.
    """
    repo_root = repo_root.resolve()
    src_list = tuple(sources) if sources is not None else _DEFAULT_SOURCES
    chunks: list[FactChunk] = []
    for source in src_list:
        path = repo_root / source
        if not path.exists():
            logger.debug("retrieval: source missing, skipping: %s", source)
            continue
        chunks.extend(_dispatch(path, repo_root))
    chunks.sort(key=lambda c: c.fact_id)
    return chunks


def _dispatch(path: Path, repo_root: Path) -> list[FactChunk]:
    if path.is_file() and path.name == "POLICY.md":
        return list(parse_policy(path, repo_root))
    if path.is_file() and path.name == "ROADMAP.md":
        return list(parse_roadmap(path, repo_root))
    if path.is_dir() and path.name == "decisions":
        return list(parse_adr_dir(path, repo_root))
    if path.is_dir() and path.name == "audit_results":
        return list(parse_audit_dir(path, repo_root))
    if path.is_dir() and path.parts[-3:] == ("src", "drift", "signals"):
        return list(parse_signals_dir(path, repo_root))
    if path.is_dir() and path.name == "benchmark_results":
        return list(parse_evidence_dir(path, repo_root))
    return []


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _HeadingRange:
    level: int
    title: str
    start: int  # 1-based, line of heading itself
    body_start: int  # 1-based, first body line after heading (or start+1)
    end: int  # 1-based, inclusive; the last line before the next peer-or-higher heading


def _iter_heading_ranges(lines: list[str]) -> list[_HeadingRange]:
    """Walk a markdown file and yield ranges per heading.

    Each range ends at the line before the next heading of equal or
    higher (smaller #-count) level, or at end-of-file.
    """
    starts: list[tuple[int, int, str]] = []  # (line_no, level, title)
    for i, raw in enumerate(lines, start=1):
        m = _HEADING_RE.match(raw)
        if m:
            starts.append((i, len(m.group("hashes")), m.group("title").strip()))
    ranges: list[_HeadingRange] = []
    for idx, (line_no, level, title) in enumerate(starts):
        end = len(lines)
        for next_line, next_level, _ in starts[idx + 1 :]:
            if next_level <= level:
                end = next_line - 1
                break
        body_start = line_no + 1
        ranges.append(_HeadingRange(level, title, line_no, body_start, end))
    return ranges


def _rel_posix(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root).as_posix()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_policy(path: Path, repo_root: Path) -> Iterable[FactChunk]:
    """Split POLICY.md into per-paragraph chunks keyed by section number."""
    rel = _rel_posix(path, repo_root)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    current_section: int | None = None
    current_section_title: str = ""
    for i, raw in enumerate(lines, start=1):
        m_section = _POLICY_SECTION_RE.match(raw)
        if m_section:
            current_section = int(m_section.group("number"))
            current_section_title = m_section.group("title").strip()
            continue
        if current_section is None:
            continue
        m_para = _POLICY_PARAGRAPH_RE.match(raw.lstrip())
        if not m_para:
            continue
        num = m_para.group("num")
        try:
            section_part, para_part = num.split(".", 1)
            section_n = int(section_part)
            para_n = int(para_part)
        except ValueError:
            continue
        if section_n != current_section:
            # Paragraph number disagrees with current heading; keep heading as authority.
            continue
        body = m_para.group("body").strip()
        fact_id = generate_policy_id(section_n, para_n)
        yield FactChunk(
            fact_id=fact_id,
            kind="policy",
            source_path=rel,
            line_start=i,
            line_end=i,
            text=body,
            sha256=_sha(body),
            tags=(f"section:{section_n}", f"title:{current_section_title}"),
        )


def parse_roadmap(path: Path, repo_root: Path) -> Iterable[FactChunk]:
    """Split ROADMAP.md into heading-scoped chunks."""
    rel = _rel_posix(path, repo_root)
    lines = path.read_text(encoding="utf-8").splitlines()
    section_counter = 0
    for rng in _iter_heading_ranges(lines):
        if rng.level > 3:
            continue  # keep corpus coarse for the roadmap
        section_counter += 1
        body = "\n".join(lines[rng.body_start - 1 : rng.end]).strip()
        if not body:
            continue
        fact_id = generate_roadmap_id(section_counter, 1)
        yield FactChunk(
            fact_id=fact_id,
            kind="roadmap",
            source_path=rel,
            line_start=rng.start,
            line_end=rng.end,
            text=f"# {rng.title}\n\n{body}",
            sha256=_sha(body),
            tags=(f"title:{rng.title}", f"level:{rng.level}"),
        )


def parse_adr_dir(directory: Path, repo_root: Path) -> Iterable[FactChunk]:
    for adr_file in sorted(directory.glob("ADR-*.md")):
        yield from parse_adr(adr_file, repo_root)


_ADR_NUMBER_RE = re.compile(r"^ADR-(?P<n>\d+)")


def parse_adr(path: Path, repo_root: Path) -> Iterable[FactChunk]:
    """Parse one ADR file into section-level chunks (Kontext, Entscheidung, ...)."""
    rel = _rel_posix(path, repo_root)
    m = _ADR_NUMBER_RE.match(path.stem)
    if not m:
        return
    number = int(m.group("n"))
    lines = path.read_text(encoding="utf-8").splitlines()
    for rng in _iter_heading_ranges(lines):
        if rng.level != 2:
            continue
        body = "\n".join(lines[rng.body_start - 1 : rng.end]).strip()
        if not body:
            continue
        fact_id = generate_adr_id(number, rng.title)
        yield FactChunk(
            fact_id=fact_id,
            kind="adr",
            source_path=rel,
            line_start=rng.start,
            line_end=rng.end,
            text=body,
            sha256=_sha(body),
            tags=(f"adr:{number}", f"section:{rng.title}"),
        )


def parse_audit_dir(directory: Path, repo_root: Path) -> Iterable[FactChunk]:
    for md_file in sorted(directory.glob("*.md")):
        yield from parse_audit(md_file, repo_root)


def parse_audit(path: Path, repo_root: Path) -> Iterable[FactChunk]:
    """Emit one chunk per identifiable table row (first column = row-id)."""
    rel = _rel_posix(path, repo_root)
    file_stem = path.stem
    lines = path.read_text(encoding="utf-8").splitlines()
    header: list[str] = []
    in_table = False
    seen_separator = False
    for i, raw in enumerate(lines, start=1):
        if raw.strip().startswith("|"):
            cells = [c.strip() for c in raw.strip().strip("|").split("|")]
            if not in_table:
                header = cells
                in_table = True
                seen_separator = False
                continue
            if not seen_separator and all(set(c) <= set("-:") and c for c in cells):
                seen_separator = True
                continue
            if not seen_separator:
                # Rare: header without separator; still allow emission.
                seen_separator = True
            if not cells or not cells[0]:
                continue
            # First column must look like a row-id (short, alnum).
            m = _AUDIT_TABLE_ROW_RE.match(raw)
            if not m:
                continue
            row_id = m.group("first")
            row_text_parts = []
            for col_idx, cell in enumerate(cells):
                col_name = header[col_idx] if col_idx < len(header) else f"col{col_idx}"
                row_text_parts.append(f"{col_name}: {cell}")
            row_text = "\n".join(row_text_parts)
            fact_id = generate_audit_id(file_stem, row_id)
            yield FactChunk(
                fact_id=fact_id,
                kind="audit",
                source_path=rel,
                line_start=i,
                line_end=i,
                text=row_text,
                sha256=_sha(row_text),
                tags=(f"file:{file_stem}", f"row:{row_id}"),
            )
        else:
            in_table = False
            header = []
            seen_separator = False


def parse_signals_dir(directory: Path, repo_root: Path) -> Iterable[FactChunk]:
    for signal_file in sorted(directory.glob("*.py")):
        if signal_file.name.startswith("_"):
            continue
        yield from parse_signal(signal_file, repo_root)


def parse_signal(path: Path, repo_root: Path) -> Iterable[FactChunk]:
    """Extract class docstrings and ``reason``/``fix`` method docstrings per signal."""
    rel = _rel_posix(path, repo_root)
    try:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return
    for node in module.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not _looks_like_signal_class(node):
            continue
        signal_id = _signal_id_from_class(node) or node.name
        # Class-level rationale from the class docstring.
        class_doc = ast.get_docstring(node, clean=True)
        if class_doc:
            fact_id = generate_signal_id(signal_id, "rationale")
            yield FactChunk(
                fact_id=fact_id,
                kind="signal",
                source_path=rel,
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                text=class_doc,
                sha256=_sha(class_doc),
                tags=(f"signal:{signal_id}", "field:rationale"),
            )
        for child in node.body:
            if not isinstance(child, ast.FunctionDef):
                continue
            if child.name not in {"reason", "fix"}:
                continue
            doc = ast.get_docstring(child, clean=True)
            if not doc:
                continue
            fact_id = generate_signal_id(signal_id, child.name)
            yield FactChunk(
                fact_id=fact_id,
                kind="signal",
                source_path=rel,
                line_start=child.lineno,
                line_end=child.end_lineno or child.lineno,
                text=doc,
                sha256=_sha(doc),
                tags=(f"signal:{signal_id}", f"field:{child.name}"),
            )


def _looks_like_signal_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        name = base.id if isinstance(base, ast.Name) else (
            base.attr if isinstance(base, ast.Attribute) else None
        )
        if name and "Signal" in name:
            return True
    return False


def _signal_id_from_class(node: ast.ClassDef) -> str | None:
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if (
                    isinstance(tgt, ast.Name)
                    and tgt.id in {"signal_type", "signal_id", "id"}
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    return stmt.value.value
        if (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id in {"signal_type", "signal_id", "id"}
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            return stmt.value.value
    return None


_EVIDENCE_NAME_RE = re.compile(r"^v(?P<version>[\w.-]+?)(?:_(?P<slug>.+))?_feature_evidence$")


def parse_evidence_dir(directory: Path, repo_root: Path) -> Iterable[FactChunk]:
    for ev_file in sorted(directory.glob("v*_feature_evidence.json")):
        yield from parse_evidence(ev_file, repo_root)


def parse_evidence(path: Path, repo_root: Path) -> Iterable[FactChunk]:
    """Emit one chunk per top-level JSON key in a feature-evidence file."""
    rel = _rel_posix(path, repo_root)
    m = _EVIDENCE_NAME_RE.match(path.stem)
    if not m:
        return
    version = m.group("version")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return
    for key in sorted(payload.keys()):
        value = payload[key]
        if isinstance(value, (dict, list)):
            body = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
        else:
            body = json.dumps(value, ensure_ascii=False)
        fact_id = generate_evidence_id(version, key)
        yield FactChunk(
            fact_id=fact_id,
            kind="evidence",
            source_path=rel,
            line_start=1,
            line_end=1,
            text=f"{key}: {body}",
            sha256=_sha(body),
            tags=(f"version:{version}", f"key:{key}"),
        )


# ---------------------------------------------------------------------------
# Digest helpers
# ---------------------------------------------------------------------------


def compute_corpus_sha256(chunks: list[FactChunk]) -> str:
    """Compute a deterministic SHA-256 over a corpus's fact_ids and chunk digests."""
    hasher = hashlib.sha256()
    for chunk in sorted(chunks, key=lambda c: c.fact_id):
        hasher.update(chunk.fact_id.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(chunk.sha256.encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()
