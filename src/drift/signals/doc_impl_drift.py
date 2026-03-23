"""Signal 5: Doc-Implementation Drift (DIA).

Detects divergence between architectural documentation (ADRs, README)
and actual code implementation.

v0.2 enhancements:
- Markdown AST parsing via mistune instead of raw-text regex.
- URL-segment blacklist eliminates false positives from badge/CI links.
- Separate extraction per node type (links, code-blocks, prose).
- Optional embedding-based claim validation.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from drift.config import DriftConfig
from drift.models import FileHistory, Finding, ParseResult, Severity, SignalType
from drift.signals.base import BaseSignal, register_signal

logger = logging.getLogger("drift.dia")


# ---------------------------------------------------------------------------
# URL / path segment blacklist – segments that look like directories but
# belong to URLs (GitHub, CI badges, package registries, etc.)
# ---------------------------------------------------------------------------

_URL_PATH_SEGMENTS: set[str] = {
    # GitHub / GitLab UI paths
    "actions",
    "badge",
    "blob",
    "tree",
    "commit",
    "commits",
    "compare",
    "pull",
    "pulls",
    "issues",
    "releases",
    "tags",
    "raw",
    "archive",
    "wiki",
    "settings",
    "security",
    "discussions",
    "packages",
    "milestones",
    "labels",
    "projects",
    "graphs",
    "network",
    # CI/CD
    "workflows",
    "runs",
    "jobs",
    "steps",
    "artifacts",
    "pipelines",
    # Package registries
    "pypi",
    "npmjs",
    "registry",
    "npm",
    "dist",
    "download",
    # Web / URL generic
    "http",
    "https",
    "www",
    "com",
    "org",
    "io",
    "dev",
    "net",
    "api",
    "v1",
    "v2",
    "v3",
    # Common markdown / text fragments
    "e",
    "g",
    "i",
    "eg",
    "etc",
    "img",
    "svg",
    "png",
    "jpg",
    "gif",
    "ico",
    "shields",
    "codecov",
    "coveralls",
    "readthedocs",
}


# ---------------------------------------------------------------------------
# Markdown AST helpers
# ---------------------------------------------------------------------------


def _get_mistune():
    """Lazy-import mistune; returns the module or None if unavailable."""
    try:
        import mistune  # noqa: PLC0415

        return mistune
    except ImportError:
        return None


_FALLBACK_DIR_RE = re.compile(r"(?<!\w)(\w[\w\-]*)/" r"(?!\S*://)")


def _extract_dir_refs_from_ast(markdown_text: str) -> set[str]:
    """Parse Markdown via mistune AST and extract directory-like references.

    Only prose nodes are inspected; link URLs, code spans, and fenced
    code blocks are skipped entirely (they are the main sources of false
    positives from badge/CI links and code examples).

    Falls back to a simple regex when mistune is not installed.
    """
    mistune = _get_mistune()
    if mistune is None:
        # Regex fallback — less precise, but functional without mistune
        # Strip fenced code blocks (example code, not structure claims)
        cleaned = re.sub(r"```[^`]*```", "", markdown_text, flags=re.DOTALL)
        # Strip inline links [text](url) to avoid extracting URL segments
        cleaned = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", cleaned)
        refs = set(_FALLBACK_DIR_RE.findall(cleaned))
        return {r for r in refs if not _is_url_segment(r)}

    md = mistune.create_markdown(renderer="ast")
    try:
        tokens: list[dict[str, Any]] = md(markdown_text)  # type: ignore[assignment]
    except Exception:
        logger.debug("Failed to parse Markdown AST, falling back to empty refs")
        return set()

    refs: set[str] = set()
    _walk_tokens(tokens, refs)
    return refs


_PROSE_DIR_RE = re.compile(r"`?(\w[\w\-]*)/" r"`?")


def _walk_tokens(tokens: list[dict[str, Any]], refs: set[str]) -> None:
    """Recursively walk mistune AST tokens collecting directory references."""
    for tok in tokens:
        tok_type = tok.get("type", "")

        # Skip link URLs entirely — they are the #1 source of FPs
        if tok_type == "link":
            # Still walk the link *text children* (they may mention real dirs)
            children = tok.get("children")
            if children:
                _walk_tokens(children, refs)
            continue

        # Skip images
        if tok_type == "image":
            continue

        # Skip code spans and code blocks — directory references inside
        # code examples are not claims about project structure and are the
        # #2 source of false positives after link URLs.
        # Inline code spans (``codespan``) are kept — they typically reference
        # real project paths in prose context (e.g. "the `src/` directory").
        if tok_type == "block_code":
            continue

        # For inline code spans — extract directory-like patterns
        if tok_type == "codespan":
            raw = tok.get("raw", tok.get("text", ""))
            if raw:
                refs.update(_PROSE_DIR_RE.findall(raw))
            continue

        # For paragraphs, headings, list items — check raw text of
        # leaf children (text, softbreak, etc.)
        raw = tok.get("raw", tok.get("text", ""))
        if raw and tok_type in ("text", "paragraph", "heading"):
            refs.update(_PROSE_DIR_RE.findall(raw))

        # Recurse into children
        children = tok.get("children")
        if children and isinstance(children, list):
            _walk_tokens(children, refs)


def _is_url_segment(name: str) -> bool:
    """Return True if *name* looks like a URL path component, not a directory."""
    return name.lower() in _URL_PATH_SEGMENTS


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


@register_signal
class DocImplDriftSignal(BaseSignal):
    """Detect drift between documentation claims and code reality.

    Checks:
    1. README or docs/ presence.
    2. Modules referenced in README that don't exist in the codebase.
    3. Top-level source directories with no README mention.
    4. (Optional, with embeddings) Semantic claim validation.
    """

    def __init__(self, repo_path: Path, **kwargs: object) -> None:
        super().__init__(repo_path=repo_path, **kwargs)

    @property
    def signal_type(self) -> SignalType:
        return SignalType.DOC_IMPL_DRIFT

    @property
    def name(self) -> str:
        return "Doc-Implementation Drift"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        findings: list[Finding] = []

        # Locate README
        readme_path = self._find_readme()
        if readme_path is None:
            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=Severity.MEDIUM,
                    score=0.4,
                    title="No README found",
                    description=(
                        "The repository has no README file. "
                        "A README is essential for architectural context."
                    ),
                    fix=(
                        "Erstelle eine README.md im Repository-Wurzelverzeichnis"
                        " mit Architekturüberblick."
                    ),
                )
            )
            return findings

        readme_text = readme_path.read_text(encoding="utf-8", errors="replace")

        # Collect actual top-level source directories that contain .py files
        source_dirs = self._source_directories(parse_results)

        # Extract directory names using Markdown AST parsing
        referenced_dirs = _extract_dir_refs_from_ast(readme_text)

        # Check for phantom references: mentioned in README but absent
        for ref in sorted(referenced_dirs):
            if _is_url_segment(ref):
                continue

            candidate = self._repo_path / ref
            if not candidate.exists() and ref.lower() not in {d.lower() for d in source_dirs}:
                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=Severity.LOW,
                        score=0.3,
                        title=f"README references missing directory: {ref}/",
                        description=(
                            f"README mentions '{ref}/' but no such directory exists. "
                            f"Documentation may be outdated."
                        ),
                        file_path=readme_path.relative_to(self._repo_path),
                        fix=f"Entferne '{ref}/' aus README oder lege das Verzeichnis an.",
                        metadata={"referenced_dir": ref},
                    )
                )

        # Check for undocumented source directories
        if source_dirs:
            readme_lower = readme_text.lower()
            for src_dir in sorted(source_dirs):
                if src_dir.lower() not in readme_lower:
                    findings.append(
                        Finding(
                            signal_type=self.signal_type,
                            severity=Severity.INFO,
                            score=0.15,
                            title=f"Source directory not mentioned in README: {src_dir}/",
                            description=(
                                f"Directory '{src_dir}/' contains source files "
                                f"but is not mentioned in README."
                            ),
                            file_path=Path(src_dir),
                            fix=(
                                f"Ergänze '{src_dir}/' in README"
                                " mit kurzer Beschreibung des Moduls."
                            ),
                            metadata={"undocumented_dir": src_dir},
                        )
                    )

        return findings

    def _find_readme(self) -> Path | None:
        for name in ("README.md", "README.rst", "README.txt", "README"):
            p = self._repo_path / name
            if p.exists():
                return p
        return None

    def _source_directories(self, parse_results: list[ParseResult]) -> set[str]:
        """Return top-level directory names that contain parsed source files."""
        dirs: set[str] = set()
        for pr in parse_results:
            parts = pr.file_path.parts
            if len(parts) > 1:
                dirs.add(parts[0])
        return dirs
