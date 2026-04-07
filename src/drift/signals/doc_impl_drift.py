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
from drift.signals._utils import is_library_finding_path, is_likely_library_repo
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
    # Common short REST/API path segments and prose words that appear
    # in README examples but are not real directories
    "auth",
    "db",
    "en",
    "de",
    "fr",
    "es",
    "ja",
    "zh",
    "pt",
    "login",
    "logout",
    "signup",
    "token",
    "oauth",
    "callback",
    "webhook",
    "graphql",
    "json",
    "xml",
    "csv",
    "html",
    "css",
    "js",
    "ts",
    "py",
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


_VERSION_SEGMENT_RE = re.compile(r"^(?:v\d+(?:[._-]\d+)*)$")

# ---------------------------------------------------------------------------
# URL stripping (P3: remove URLs before dir-ref extraction to avoid
# extracting path segments from GitHub/registry links in plain text)
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://\S+")


def _strip_urls(text: str) -> str:
    """Remove URLs from text to prevent extracting URL path segments."""
    return _URL_RE.sub("", text)
_DIRECTORY_CONTEXT_KEYWORDS: tuple[str, ...] = (
    "directory",
    "directories",
    "folder",
    "folders",
    "path",
    "paths",
    "tree",
    "layout",
    "structure",
    "module",
    "modules",
    "package",
    "packages",
    "architecture",
    "component",
    "components",
)


def _is_likely_proper_noun(name: str) -> bool:
    """Heuristic for prose nouns that are unlikely to be repo directories."""
    if not name:
        return False
    if not name[0].isupper():
        return False
    if name.isupper():
        return False
    if "_" in name:
        return False
    return not any(ch.isdigit() for ch in name)


def _is_version_or_numeric_segment(name: str) -> bool:
    """Return True for numeric/version-like fragments (v1/, 2024/, 20240315/)."""
    if not name:
        return False
    if name.isdigit():
        # years, dates, generic numeric URL/path segments
        return len(name) >= 4
    return _VERSION_SEGMENT_RE.match(name.lower()) is not None


def _is_noise_dir_reference(name: str) -> bool:
    """Return True if *name* is likely noise and should be ignored."""
    if len(name) <= 2:
        return True
    if _is_url_segment(name):
        return True
    if _is_version_or_numeric_segment(name):
        return True
    return bool(_is_likely_proper_noun(name))


def _has_directory_context(raw_text: str, match_start: int, match_end: int) -> bool:
    """Return True when nearby prose indicates a structural directory claim."""
    text = raw_text.lower()
    window_start = max(0, match_start - 48)
    window_end = min(len(text), match_end + 48)
    window = text[window_start:window_end]
    return any(keyword in window for keyword in _DIRECTORY_CONTEXT_KEYWORDS)


def _extract_contextual_dir_refs(
    raw_text: str,
    *,
    allow_without_context: bool = False,
) -> set[str]:
    """Extract directory refs while filtering prose slash-tokens without context."""
    refs: set[str] = set()
    # P3: strip URLs first so GitHub/registry path segments aren't extracted
    cleaned_text = _strip_urls(raw_text)
    for match in _PROSE_DIR_RE.finditer(cleaned_text):
        ref = match.group("ref")
        wrapped = bool(match.group("tick"))
        if _is_noise_dir_reference(ref):
            continue
        if (
            allow_without_context
            or wrapped
            or _has_directory_context(cleaned_text, match.start(), match.end())
        ):
            refs.add(ref)
    return refs


def _extract_dir_refs_from_ast(
    markdown_text: str,
    *,
    trust_codespans: bool = False,
) -> set[str]:
    """Parse Markdown via mistune AST and extract directory-like references.

    Only prose nodes are inspected; link URLs, code spans, and fenced
    code blocks are skipped entirely (they are the main sources of false
    positives from badge/CI links and code examples).

    When *trust_codespans* is True, inline code spans are always extracted
    regardless of surrounding keyword context (useful for ADR files where
    codespans are architectural references by definition).

    Falls back to a simple regex when mistune is not installed.
    """
    mistune = _get_mistune()
    if mistune is None:
        # Regex fallback — less precise, but functional without mistune
        # Strip fenced code blocks (example code, not structure claims)
        cleaned = re.sub(r"```[^`]*```", "", markdown_text, flags=re.DOTALL)
        # Strip inline links [text](url) to avoid extracting URL segments
        cleaned = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", cleaned)
        return _extract_contextual_dir_refs(cleaned)

    md = mistune.create_markdown(renderer="ast")
    try:
        tokens: list[dict[str, Any]] = md(markdown_text)  # type: ignore[assignment]
    except Exception:
        logger.debug("Failed to parse Markdown AST, falling back to empty refs")
        return set()

    refs: set[str] = set()
    _walk_tokens(tokens, refs, trust_codespans=trust_codespans)
    return refs


_PROSE_DIR_RE = re.compile(r"(?P<tick>`)?(?P<ref>\w[\w\-]*)/(?!\w)(?P=tick)?")


def _collect_sibling_text(children: list[dict[str, Any]]) -> str:
    """Concatenate raw text from text-type children for context checks."""
    parts: list[str] = []
    for child in children:
        if child.get("type") in ("text", "softbreak"):
            raw = child.get("raw", child.get("text", ""))
            if raw:
                parts.append(raw)
    return " ".join(parts)


def _walk_tokens(
    tokens: list[dict[str, Any]],
    refs: set[str],
    *,
    sibling_context: str = "",
    trust_codespans: bool = False,
) -> None:
    """Recursively walk mistune AST tokens collecting directory references."""
    # Track context across sequential sibling tokens so that e.g.
    # a paragraph "Project structure:" propagates to its following list.
    running_ctx = sibling_context
    for tok in tokens:
        tok_type = tok.get("type", "")

        # Skip link URLs entirely — they are the #1 source of FPs
        if tok_type == "link":
            # Still walk the link *text children* (they may mention real dirs)
            children = tok.get("children")
            if children:
                _walk_tokens(
                    children, refs, sibling_context=running_ctx, trust_codespans=trust_codespans
                )
            continue

        # Skip images
        if tok_type == "image":
            continue

        # Skip fenced code blocks — code examples are not structure claims.
        if tok_type == "block_code":
            continue

        # For inline code spans — extract directory-like patterns only when
        # the surrounding paragraph/heading text contains a directory keyword.
        if tok_type == "codespan":
            raw = tok.get("raw", tok.get("text", ""))
            if raw:
                if trust_codespans:
                    has_ctx = True
                else:
                    ctx_lower = running_ctx.lower()
                    has_ctx = any(
                        kw in ctx_lower for kw in _DIRECTORY_CONTEXT_KEYWORDS
                    )
                refs.update(
                    _extract_contextual_dir_refs(
                        raw,
                        allow_without_context=has_ctx,
                    )
                )
            continue

        # For paragraphs, headings, list items — check raw text of
        # leaf children (text, softbreak, etc.)
        raw = tok.get("raw", tok.get("text", ""))
        if raw and tok_type in ("text", "paragraph", "heading"):
            refs.update(_extract_contextual_dir_refs(raw))

        # Recurse into children — for paragraphs/headings, build sibling
        # context from text children so codespans can use it.
        # Context is accumulated across siblings: a paragraph "Project
        # structure:" propagates through a subsequent list to its items.
        children = tok.get("children")
        if children and isinstance(children, list):
            if tok_type in ("paragraph", "heading"):
                local = _collect_sibling_text(children)
                ctx = (running_ctx + " " + local).strip() if local else running_ctx
                running_ctx = ctx  # Propagate to following siblings
            elif tok_type == "list_item":
                # list_item children are paragraphs (not text nodes),
                # pass through inherited context without overwriting.
                ctx = running_ctx
            else:
                ctx = running_ctx
            _walk_tokens(children, refs, sibling_context=ctx, trust_codespans=trust_codespans)


def _is_url_segment(name: str) -> bool:
    """Return True if *name* looks like a URL path component, not a directory."""
    return name.lower() in _URL_PATH_SEGMENTS


# ---------------------------------------------------------------------------
# Container-prefix existence check (Phase B: CS-2 fix)
# ---------------------------------------------------------------------------

_CONTAINER_PREFIXES: frozenset[str] = frozenset(
    {"src", "lib", "app", "pkg", "packages", "libs", "internal"}
)


def _ref_exists_in_repo(
    repo_path: Path, ref: str, source_dirs: set[str]
) -> bool:
    """Check whether *ref* exists as a directory anywhere plausible in the repo."""
    if (repo_path / ref).exists():
        return True
    if ref.lower() in {d.lower() for d in source_dirs}:
        return True
    # Check under known container prefixes (e.g. src/services/ for ref=services)
    for prefix in _CONTAINER_PREFIXES:
        container = repo_path / prefix
        if container.is_dir() and (container / ref).is_dir():
            return True
    # P6: check with dotfile prefix (e.g. drift-cache → .drift-cache)
    return (repo_path / f".{ref}").is_dir()


# ---------------------------------------------------------------------------
# ADR status parsing (Phase C: CS-3 fix)
# ---------------------------------------------------------------------------

_SKIP_ADR_STATUSES: frozenset[str] = frozenset(
    {"superseded", "deprecated", "rejected"}
)

_ADR_FRONTMATTER_STATUS_RE = re.compile(
    r"^---\s*\n.*?^status:\s*(\S+)", re.MULTILINE | re.DOTALL
)
_ADR_MADR_STATUS_RE = re.compile(
    r"^##\s+Status\s*\n+\s*(\w+)", re.MULTILINE
)


def _extract_adr_status(text: str) -> str | None:
    """Extract ADR status from YAML frontmatter or MADR heading format."""
    m = _ADR_FRONTMATTER_STATUS_RE.search(text)
    if m:
        return m.group(1).lower().strip()
    m = _ADR_MADR_STATUS_RE.search(text)
    if m:
        return m.group(1).lower().strip()
    return None


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

    # -----------------------------------------------------------------------
    # P1: Auxiliary directories — conventional project dirs that don't need
    # explicit README documentation (tests, scripts, benchmarks, etc.)
    # -----------------------------------------------------------------------
    _AUXILIARY_DIRS: frozenset[str] = frozenset({
        "tests", "test",
        "scripts", "script",
        "benchmarks", "benchmark",
        "tools", "tool",
        "examples", "example",
        "samples", "sample",
        "demos", "demo",
        "fixtures",
        "docs", "doc",
        # Build / CI artifacts and working directories
        "artifacts", "work_artifacts",
    })

    incremental_scope = "file_local"

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
        library_repo = is_likely_library_repo(parse_results)
        repo_path = self.repo_path
        if repo_path is None:
            return findings

        # Locate README
        readme_path = self._find_readme()
        is_bootstrap_repo = len(parse_results) <= 1 or (
            bool(parse_results)
            and all(result.file_path.name == "__init__.py" for result in parse_results)
        )
        if readme_path is None:
            if is_bootstrap_repo:
                return findings
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
                            "Create a README.md at the repository root with"
                            " an architecture overview."
                    ),
                )
            )
            return findings

        readme_text = readme_path.read_text(encoding="utf-8", errors="replace")

        # Collect actual top-level source directories that contain .py files
        source_dirs = self._source_directories(parse_results)

        # Collect actual import graph modules for ADR validation
        actual_imports = self._actual_import_modules(parse_results)

        # Extract directory names using Markdown AST parsing
        referenced_dirs = _extract_dir_refs_from_ast(readme_text)

        # Check for phantom references: mentioned in README but absent
        for ref in sorted(referenced_dirs):
            if _is_noise_dir_reference(ref):
                continue

            if not _ref_exists_in_repo(repo_path, ref, source_dirs):
                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=Severity.LOW,
                        score=0.3,
                        title=f"README references missing directory: {ref}/",
                        description=(
                            f"README mentions '{ref}/' but no such directory"
                            f" exists. Documentation may be outdated."
                        ),
                        file_path=readme_path.relative_to(repo_path),
                            fix=(
                                f"Remove '{ref}/' from README.md or create the"
                                f" directory."
                            ),
                        metadata={
                            "referenced_dir": ref,
                            "library_context_candidate": library_repo
                            and is_library_finding_path(readme_path.relative_to(repo_path)),
                        },
                    )
                )

        # Check for undocumented source directories
        if source_dirs:
            readme_lower = readme_text.lower()
            for src_dir in sorted(source_dirs):
                # P1: skip conventional auxiliary directories
                if src_dir.lower() in self._AUXILIARY_DIRS:
                    continue
                if src_dir.lower() not in readme_lower:
                    findings.append(
                        Finding(
                            signal_type=self.signal_type,
                            severity=Severity.INFO,
                            score=0.15,
                            title=(
                                f"Source directory not mentioned in README:"
                                f" {src_dir}/"
                            ),
                            description=(
                                f"Directory '{src_dir}/' contains source files "
                                f"but is not mentioned in README."
                            ),
                            file_path=Path(src_dir),
                            fix=(
                                    f"Add a section for '{src_dir}/' to README.md"
                                    f" with a short description of the module."
                            ),
                            metadata={
                                "undocumented_dir": src_dir,
                                "library_context_candidate": library_repo
                                and is_library_finding_path(Path(src_dir)),
                            },
                        )
                    )

        # ── ADR / architecture doc scanning ──
        findings.extend(
            self._scan_adr_files(
                parse_results,
                source_dirs,
                actual_imports,
                library_repo=library_repo,
            )
        )

        return findings

    def _scan_adr_files(
        self,
        parse_results: list[ParseResult],
        source_dirs: set[str],
        actual_imports: set[str],
        *,
        library_repo: bool,
    ) -> list[Finding]:
        """Scan ADR and architecture docs for stale directory claims."""
        findings: list[Finding] = []
        adr_dirs = self._discover_adr_dirs()
        repo_path = self.repo_path
        if repo_path is None:
            return findings

        for adr_dir in adr_dirs:
            if not adr_dir.is_dir():
                continue
            for md_file in sorted(adr_dir.glob("*.md")):
                try:
                    text = md_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                status = _extract_adr_status(text)
                if status in _SKIP_ADR_STATUSES:
                    continue
                refs = _extract_dir_refs_from_ast(text, trust_codespans=True)
                for ref in sorted(refs):
                    if _is_noise_dir_reference(ref):
                        continue
                    if not _ref_exists_in_repo(repo_path, ref, source_dirs):
                        try:
                            rel_path = md_file.relative_to(repo_path)
                        except ValueError:
                            rel_path = md_file
                        findings.append(
                            Finding(
                                signal_type=self.signal_type,
                                severity=Severity.MEDIUM,
                                score=0.4,
                                title=(
                                    f"ADR references missing directory:"
                                    f" {ref}/"
                                ),
                                description=(
                                    f"{rel_path} mentions '{ref}/' but no"
                                    f" such directory exists."
                                ),
                                file_path=rel_path,
                                fix=(
                                        f"Update {rel_path.name}: remove or correct"
                                        f" the stale '{ref}/' reference."
                                ),
                                metadata={
                                    "referenced_dir": ref,
                                    "adr_file": rel_path.as_posix(),
                                    "library_context_candidate": library_repo
                                    and is_library_finding_path(rel_path),
                                },
                            )
                        )

        return findings

    def _discover_adr_dirs(self) -> list[Path]:
        """Discover likely ADR/architecture-doc directories in the repository."""
        repo_path = self.repo_path
        if repo_path is None:
            return []
        seed_dirs = [
            repo_path / "docs" / "adr",
            repo_path / "docs" / "adrs",
            repo_path / "adr",
            repo_path / "docs" / "architecture",
            repo_path / "doc" / "adr",
            repo_path / "doc" / "adrs",
            repo_path / "doc" / "decisions",
            repo_path / "architecture" / "decisions",
        ]
        roots_to_scan = [
            repo_path,
            repo_path / "docs",
            repo_path / "doc",
            repo_path / "architecture",
        ]
        discovered: set[Path] = set()
        for path in seed_dirs:
            if path.is_dir():
                discovered.add(path)

        for root in roots_to_scan:
            if not root.is_dir():
                continue
            try:
                children = list(root.iterdir())
            except OSError:
                continue
            for child in children:
                if not child.is_dir():
                    continue
                name = child.name.lower()
                if name in {"adr", "adrs", "decisions", "architecture"} or (
                    "adr" in name and len(name) <= 20
                ):
                    discovered.add(child)

        return sorted(discovered)

    def _find_readme(self) -> Path | None:
        repo_path = self.repo_path
        if repo_path is None:
            return None
        for name in ("README.md", "README.rst", "README.txt", "README"):
            p = repo_path / name
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

    def _actual_import_modules(
        self, parse_results: list[ParseResult]
    ) -> set[str]:
        """Return the set of top-level module names actually imported."""
        modules: set[str] = set()
        for pr in parse_results:
            for imp in pr.imports:
                top = imp.imported_module.split(".")[0]
                if top:
                    modules.add(top)
        return modules
