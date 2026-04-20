"""Scope resolution from natural-language task descriptions.

Deterministic, three-stage algorithm that maps a task string to concrete
repository paths:

1. **Explicit path extraction** — regex for file/directory paths in the text
2. **Keyword-to-module mapping** — match tokens against directory names,
   configured layer boundaries, symbol names (class/function), and
   user-defined scope aliases
3. **Fallback** — entire repository when no match is found

No LLM, no embeddings — pure string heuristics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import (
    Path,
    PurePosixPath,
)

# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ResolvedScope:
    """Result of scope resolution."""

    paths: list[str]
    """Resolved repository-relative paths (posix-normalised, no leading /)."""

    confidence: float
    """0.0 (fallback/whole-repo) … 1.0 (exact path match)."""

    method: str
    """How the scope was resolved: ``path_match``, ``keyword_match``, ``fallback``."""

    matched_tokens: list[str] = field(default_factory=list)
    """Task tokens that were matched (for transparency)."""

    file_count: int = 0
    """Number of files in resolved scope (populated externally)."""

    function_count: int = 0
    """Number of functions in resolved scope (populated externally)."""


# ---------------------------------------------------------------------------
# Stop-words — removed before keyword matching
# ---------------------------------------------------------------------------

_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "to", "in", "on", "at", "of", "for", "and", "or",
    "is", "it", "with", "from", "by", "as", "be", "this", "that", "into",
    "add", "create", "implement", "write", "fix", "update", "change",
    "modify", "refactor", "remove", "delete", "move", "new", "make",
    "use", "using", "should", "would", "could", "need", "want",
    "please", "can", "do", "does", "did", "will", "shall",
    "all", "every", "each", "some", "any", "no", "not",
    "my", "our", "your", "their", "its", "i", "we", "you", "they",
    "code", "file", "function", "class", "method", "module",
})


# ---------------------------------------------------------------------------
# Levenshtein distance (stdlib-only, no external dependency)
# ---------------------------------------------------------------------------


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


# ---------------------------------------------------------------------------
# Symbol extraction (class/function names from Python source files)
# ---------------------------------------------------------------------------

# Matches top-level ``class Foo`` and ``def bar`` declarations
_SYMBOL_DECL_RE = re.compile(
    r"^(?:class|def)\s+([A-Za-z_]\w*)",
    re.MULTILINE,
)

# Directories to skip during symbol scan (same set as _collect_directories)
_SYMBOL_SCAN_NOISE: frozenset[str] = frozenset({
    ".git", ".github", ".venv", "venv", "__pycache__", "node_modules",
    ".tox", ".nox", "dist", "build", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "site-packages", ".pixi", ".eggs", "site",
    "htmlcov", ".coverage",
})


def _collect_symbols(
    repo_path: Path,
    *,
    max_files: int = 500,
) -> dict[str, str]:
    """Build a map of lowercase symbol name → repo-relative directory path.

    Scans ``.py`` files for ``class X`` and ``def X`` declarations using
    regex (no AST parse).  Returns at most *max_files* worth of symbols
    to keep the scan fast.
    """
    result: dict[str, str] = {}
    count = 0
    for py_file in sorted(repo_path.rglob("*.py")):
        # Skip symlinks to avoid traversal outside repository boundary
        if py_file.is_symlink():
            continue
        # Skip noise directories
        parts = py_file.relative_to(repo_path).parts
        if any(p.lower() in _SYMBOL_SCAN_NOISE for p in parts):
            continue
        if count >= max_files:
            break
        count += 1
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in _SYMBOL_DECL_RE.finditer(source):
            name = m.group(1)
            low = name.lower()
            if low.startswith("_"):
                continue  # skip private symbols
            if low in result:
                continue  # first-seen wins
            rel_dir = py_file.relative_to(repo_path).parent.as_posix()
            if rel_dir == ".":
                continue
            result[low] = rel_dir
    return result


# ---------------------------------------------------------------------------
# Stage 1 — Explicit path extraction
# ---------------------------------------------------------------------------

# Matches things like src/checkout/, tests/test_pay.py, ./api/routes.py
_PATH_RE = re.compile(
    r"""
    (?:^|[\s"'(,])                  # preceded by whitespace / quote / paren / start
    (
        (?:\.{1,2}/)?               # optional ./ or ../
        [a-zA-Z_][\w\-]*            # first path component (no slashes yet)
        /                            # at least one slash required (distinguishes paths)
        [\w\-./]*                   # rest of path
        (?:\.(?:py|ts|tsx|js|jsx))? # optional file extension
        /?                           # optional trailing slash
    )
    """,
    re.VERBOSE,
)


def _extract_paths(task: str) -> list[str]:
    """Extract file/directory paths from the task string."""
    return [m.group(1).strip() for m in _PATH_RE.finditer(task)]


def _validate_paths(candidates: list[str], repo_path: Path) -> list[str]:
    """Keep only candidates that resolve to an existing file or directory."""
    valid: list[str] = []
    repo_resolved = repo_path.resolve()
    for cand in candidates:
        normalised = PurePosixPath(cand).as_posix().strip("/")
        if not normalised:
            continue
        # Reject any path containing traversal components
        if ".." in normalised:
            continue
        full = repo_path / normalised
        if full.exists():
            try:
                if not full.resolve().is_relative_to(repo_resolved):
                    continue
            except OSError:
                continue
            valid.append(normalised)
    return valid


# ---------------------------------------------------------------------------
# Stage 2 — Keyword-to-module mapping
# ---------------------------------------------------------------------------


def _tokenize_task(task: str) -> list[str]:
    """Split task into lowercase tokens, stripping stop-words."""
    raw = re.split(r"[\s/\-_.,;:!?\"'()]+", task.lower())
    return [t for t in raw if t and t not in _STOP_WORDS]


def _collect_directories(repo_path: Path, max_depth: int = 4) -> dict[str, str]:
    """Build a map of lowercase directory name → repo-relative posix path.

    Only source-relevant directories are included (skip hidden dirs, common
    noise like node_modules, __pycache__, .git, etc.).
    """
    noise = {
        ".git", ".github", ".venv", "venv", "__pycache__", "node_modules",
        ".tox", ".nox", "dist", "build", ".mypy_cache", ".pytest_cache",
        ".ruff_cache", "site-packages", ".pixi", ".eggs", "site",
        "htmlcov", ".coverage",
    }
    result: dict[str, str] = {}

    def _walk(current: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir())
        except PermissionError:
            return
        for entry in entries:
            # Skip symlinks to prevent escaping the repository boundary
            if entry.is_symlink() or not entry.is_dir():
                continue
            name_lower = entry.name.lower()
            if name_lower.startswith(".") and name_lower not in {".github"}:
                continue
            if name_lower in noise:
                continue
            rel = entry.relative_to(repo_path).as_posix()
            # Map the terminal directory name → its full relative path
            if name_lower not in result:
                result[name_lower] = rel
            _walk(entry, depth + 1)

    _walk(repo_path, 0)
    return result


def _match_keywords(
    tokens: list[str],
    repo_path: Path,
    layer_names: list[str] | None = None,
    scope_aliases: dict[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    """Match task tokens against repository directories, symbols, and aliases.

    Returns (matched_paths, matched_tokens).
    """
    dir_map = _collect_directories(repo_path)

    matched_paths: list[str] = []
    matched_tokens: list[str] = []

    # Also add configured layer names as aliases
    if layer_names:
        for ln in layer_names:
            low = ln.lower()
            if low in dir_map:
                continue  # already covered
            # Try to find a directory containing the layer name
            for dname, dpath in dir_map.items():
                if low in dname:
                    dir_map[low] = dpath
                    break

    # Inject user-defined scope aliases (from drift.yaml brief.scope_aliases)
    if scope_aliases:
        repo_resolved = repo_path.resolve()
        for alias, target in scope_aliases.items():
            normalised = PurePosixPath(target).as_posix().strip("/")
            if not normalised:
                continue
            if ".." in normalised.split("/"):
                continue
            full = repo_path / normalised
            try:
                if not full.resolve().is_relative_to(repo_resolved):
                    continue
            except OSError:
                continue
            dir_map[alias.lower()] = normalised

    # Build symbol map lazily (only if needed after dir matching)
    symbol_map: dict[str, str] | None = None

    for token in tokens:
        # --- Exact directory match ---
        if token in dir_map:
            if dir_map[token] not in matched_paths:
                matched_paths.append(dir_map[token])
                matched_tokens.append(token)
            continue

        # --- Substring match: token is a substring of a directory name ---
        found = False
        for dname, dpath in dir_map.items():
            if len(token) >= 3 and token in dname and dpath not in matched_paths:
                matched_paths.append(dpath)
                matched_tokens.append(token)
                found = True
                break
        if found:
            continue

        # --- Symbol-based matching (class/function names) ---
        if symbol_map is None:
            symbol_map = _collect_symbols(repo_path)

        # Exact symbol match
        if token in symbol_map:
            spath = symbol_map[token]
            if spath not in matched_paths:
                matched_paths.append(spath)
                matched_tokens.append(token)
            continue

        # Fuzzy symbol match (Levenshtein ≤ 2, only for tokens ≥ 4 chars)
        if len(token) >= 4:
            best_dist = 3  # threshold + 1
            best_path: str | None = None
            for sym, spath in symbol_map.items():
                if abs(len(sym) - len(token)) > 2:
                    continue  # quick length pre-filter
                dist = _levenshtein(token, sym)
                if dist < best_dist:
                    best_dist = dist
                    best_path = spath
            if best_path is not None and best_path not in matched_paths:
                matched_paths.append(best_path)
                matched_tokens.append(token)
                continue

        # --- Fuzzy directory match (Levenshtein ≤ 2, tokens ≥ 4 chars) ---
        if len(token) >= 4:
            best_dist = 3
            best_dpath: str | None = None
            for dname, dpath in dir_map.items():
                if abs(len(dname) - len(token)) > 2:
                    continue
                dist = _levenshtein(token, dname)
                if dist < best_dist:
                    best_dist = dist
                    best_dpath = dpath
            if best_dpath is not None and best_dpath not in matched_paths:
                matched_paths.append(best_dpath)
                matched_tokens.append(token)

    return matched_paths, matched_tokens


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def resolve_scope(
    task: str,
    repo_path: Path,
    *,
    scope_override: str | None = None,
    layer_names: list[str] | None = None,
    scope_aliases: dict[str, str] | None = None,
) -> ResolvedScope:
    """Resolve a natural-language task description to repository paths.

    Parameters
    ----------
    task:
        Free-text task description (e.g. "add payment integration to checkout").
    repo_path:
        Absolute path to the repository root.
    scope_override:
        If provided, skip heuristics and use this path directly.
    layer_names:
        Optional layer boundary names from drift.yaml config.
    scope_aliases:
        Optional keyword → path mapping from drift.yaml ``brief.scope_aliases``.
    """
    repo_path = repo_path.resolve()

    # Manual override — highest confidence
    if scope_override:
        normalised = PurePosixPath(scope_override).as_posix().strip("/")
        if not normalised:
            raise ValueError(
                f"scope_override {scope_override!r} normalises to an empty path."
            )
        if ".." in normalised.split("/"):
            raise ValueError(
                f"scope_override {scope_override!r} contains path traversal components."
            )
        full = repo_path / normalised
        try:
            if not full.resolve().is_relative_to(repo_path):
                raise ValueError(
                    f"scope_override {scope_override!r} resolves outside the repository root."
                )
        except OSError as exc:
            raise ValueError(
                f"scope_override {scope_override!r} could not be resolved: {exc}"
            ) from exc
        return ResolvedScope(
            paths=[normalised],
            confidence=0.95,
            method="manual_override",
            matched_tokens=[],
        )

    # Stage 1: Explicit path extraction
    candidates = _extract_paths(task)
    valid_paths = _validate_paths(candidates, repo_path)
    if valid_paths:
        return ResolvedScope(
            paths=valid_paths,
            confidence=0.95,
            method="path_match",
            matched_tokens=valid_paths,
        )

    # Stage 2: Keyword-to-module mapping
    tokens = _tokenize_task(task)
    if tokens:
        paths, matched = _match_keywords(
            tokens, repo_path, layer_names, scope_aliases,
        )
        if paths:
            confidence = min(0.85, 0.60 + 0.10 * len(paths))
            return ResolvedScope(
                paths=paths,
                confidence=confidence,
                method="keyword_match",
                matched_tokens=matched,
            )

    # Stage 3: Fallback — whole repo
    return ResolvedScope(
        paths=[],
        confidence=0.0,
        method="fallback",
        matched_tokens=[],
    )


# ---------------------------------------------------------------------------
# Import-graph scope expansion (1-hop)
# ---------------------------------------------------------------------------

# Matches Python import statements: ``import x.y`` and ``from x.y import z``
_IMPORT_RE = re.compile(
    r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))",
    re.MULTILINE,
)


def _module_to_path_candidates(module: str) -> list[str]:
    """Convert a dotted module name to possible repo-relative file paths."""
    parts = module.replace(".", "/")
    return [
        f"{parts}.py",
        f"{parts}/__init__.py",
    ]


def _collect_scope_files(scope_paths: list[str], repo_path: Path) -> list[Path]:
    """Collect all .py files within the resolved scope paths."""
    files: list[Path] = []
    for sp in scope_paths:
        target = repo_path / sp
        if target.is_file() and target.suffix == ".py":
            files.append(target)
        elif target.is_dir():
            files.extend(target.rglob("*.py"))
    return files


def _expand_imports_from_file(
    py_file: Path,
    repo_path: Path,
    existing: set[str],
    imported_dirs: set[str],
) -> None:
    """Scan py_file for intra-repo imports and add new dirs to imported_dirs."""
    try:
        source = py_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    for match in _IMPORT_RE.finditer(source):
        module = match.group(1) or match.group(2)
        if not module:
            continue

        for candidate in _module_to_path_candidates(module):
            full = repo_path / candidate
            if full.exists():
                rel_dir = Path(candidate).parent.as_posix()
                if rel_dir == ".":
                    continue
                if rel_dir not in existing and rel_dir not in imported_dirs:
                    imported_dirs.add(rel_dir)
                break


def expand_scope_imports(
    scope: ResolvedScope,
    repo_path: Path,
) -> list[str]:
    """Expand resolved scope by 1-hop import dependencies.

    Scans Python files within the scope for ``import`` / ``from ... import``
    statements and returns additional repo-relative directory paths that are
    imported but not already in the scope.

    This is a lightweight heuristic — no full AST parse, no external
    dependency resolution.  Only intra-repo imports are resolved.

    Returns
    -------
    list[str]
        Additional repo-relative paths (directories) that the scope depends on.
        Does not include paths already present in ``scope.paths``.
    """
    if not scope.paths:
        return []

    repo_path = repo_path.resolve()
    py_files = _collect_scope_files(scope.paths, repo_path)
    if not py_files:
        return []

    imported_dirs: set[str] = set()
    existing = set(scope.paths)

    for py_file in py_files:
        _expand_imports_from_file(py_file, repo_path, existing, imported_dirs)

    return sorted(imported_dirs)
