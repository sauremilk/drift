"""Session-handover gate for ``drift_session_end`` (ADR-079).

Provides deterministic classification of a session's change class from its
touched files, derives the required handover artifacts, and runs a layered
validation over them:

* L1 existence + minimum file size
* L2 shape (frontmatter fields, required Markdown sections, evidence/ADR
  minimum schema, session-state cross-check)
* L3 placeholder denylist (``TODO``, ``FIXME``, ``<N>``, ``lorem`` ...)
* L4 optional LLM review (opt-in via ``DRIFT_SESSION_END_LLM_REVIEW=1``)

The server only validates; the agent writes the artifacts.

See:
    decisions/ADR-079-session-handover-artifact-gate.md
    .github/prompts/_partials/session-handover-contract.md
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from drift.session import DriftSession


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_HANDOVER_RETRIES = 5
"""Maximum allowed blocked retries before agent must use ``force=true``."""

MIN_MARKDOWN_BYTES = 200
"""Minimum non-empty size for Markdown artifacts."""

MIN_JSON_BYTES = 64
"""Minimum non-empty size for JSON evidence artifacts."""

MIN_ADR_CONTEXT_CHARS = 120
"""Minimum substantive characters in an ADR ``## Kontext`` section."""

MIN_BYPASS_REASON_CHARS = 40
"""Minimum characters for a ``force=true`` bypass reason."""

_DENYLIST_TOKENS: tuple[str, ...] = (
    "TODO",
    "FIXME",
    "XXX",
    "TBD",
    "???",
    "<N>",
    "<NNN>",
    "LOREM",
    "IPSUM",
)
_NAME_PLACEHOLDER_TOKENS: tuple[str, ...] = ("FOO", "BAR", "BAZ")

_REQUIRED_SECTIONS: tuple[str, ...] = (
    "Scope",
    "Ergebnisse",
    "Offene Enden",
    "Next-Agent-Einstieg",
    "Evidenz",
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class ChangeClass(StrEnum):
    """Detected change class for a session.

    Ordering (highest-priority first) matches the table in ADR-079.
    """

    SIGNAL = "signal"
    ARCHITECTURE = "architecture"
    FIX = "fix"
    DOCS = "docs"
    CHORE = "chore"


_CLASS_PRIORITY: dict[ChangeClass, int] = {
    ChangeClass.SIGNAL: 4,
    ChangeClass.ARCHITECTURE: 3,
    ChangeClass.FIX: 2,
    ChangeClass.DOCS: 1,
    ChangeClass.CHORE: 0,
}


@dataclass(frozen=True)
class RequiredArtifact:
    """One required handover artifact for a given change class."""

    kind: str  # "evidence" | "adr" | "session_md"
    path: str  # repo-relative path
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "path": self.path, "reason": self.reason}


@dataclass(frozen=True)
class ShapeError:
    """A single L2 shape violation."""

    path: str
    field: str
    expected: str
    actual: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True)
class PlaceholderFlag:
    """A single L3 placeholder match."""

    path: str
    line: int
    pattern: str
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line": self.line,
            "pattern": self.pattern,
            "snippet": self.snippet,
        }


@dataclass
class ValidationResult:
    """Aggregate outcome of all validation layers."""

    change_class: ChangeClass
    required: list[RequiredArtifact] = field(default_factory=list)
    missing: list[RequiredArtifact] = field(default_factory=list)
    shape_errors: list[ShapeError] = field(default_factory=list)
    placeholder_flags: list[PlaceholderFlag] = field(default_factory=list)
    semantic_ok: bool | None = None  # only set if L4 ran
    touched_files: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True iff all required layers passed."""
        if self.missing or self.shape_errors or self.placeholder_flags:
            return False
        return self.semantic_ok is not False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "change_class": str(self.change_class.value),
            "required_artifacts": [r.to_dict() for r in self.required],
            "missing_artifacts": [r.to_dict() for r in self.missing],
            "shape_errors": [e.to_dict() for e in self.shape_errors],
            "placeholder_flags": [p.to_dict() for p in self.placeholder_flags],
            "touched_files": list(self.touched_files),
        }
        if self.semantic_ok is not None:
            payload["semantic_ok"] = self.semantic_ok
        return payload


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _normalise_path(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def _classify_one(path: str) -> ChangeClass:
    norm = _normalise_path(path)
    if norm.startswith("src/drift/signals/") or norm.startswith("src/drift/scoring/"):
        return ChangeClass.SIGNAL
    if (
        norm.startswith("src/drift/ingestion/")
        or norm.startswith("src/drift/output/")
        or norm.startswith("src/drift/api/")
        or norm.startswith("src/drift/api.py")
        or re.match(r"^src/drift/mcp_.*\.py$", norm)
        or re.match(r"^src/drift/session.*\.py$", norm)
        or re.match(r"^src/drift/session_handover\.py$", norm)
    ):
        return ChangeClass.ARCHITECTURE
    if norm.startswith("src/drift/"):
        return ChangeClass.FIX
    if (
        norm.startswith("docs/")
        or norm.startswith("docs-site/")
        or norm.startswith(".github/prompts/")
        or norm.startswith(".github/skills/")
        or norm.startswith(".github/instructions/")
    ):
        return ChangeClass.DOCS
    return ChangeClass.CHORE


def classify_touched(paths: list[str]) -> ChangeClass:
    """Derive the change class from a list of touched file paths.

    Highest-priority class wins; empty input maps to ``CHORE``.
    """
    if not paths:
        return ChangeClass.CHORE
    classes = [_classify_one(p) for p in paths if p]
    if not classes:
        return ChangeClass.CHORE
    return max(classes, key=lambda c: _CLASS_PRIORITY[c])


def _git_touched_files(repo: Path, base_sha: str | None) -> list[str]:
    """Return files changed since ``base_sha`` plus uncommitted changes."""
    if not repo.exists():
        return []
    touched: set[str] = set()
    try:
        if base_sha:
            out = subprocess.run(
                ["git", "diff", "--name-only", f"{base_sha}..HEAD"],
                cwd=str(repo),
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if out.returncode == 0:
                touched.update(
                    line.strip() for line in out.stdout.splitlines() if line.strip()
                )
        for args in (["diff", "--name-only"], ["diff", "--name-only", "--cached"]):
            out = subprocess.run(
                ["git", *args],
                cwd=str(repo),
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if out.returncode == 0:
                touched.update(
                    line.strip() for line in out.stdout.splitlines() if line.strip()
                )
    except (OSError, subprocess.SubprocessError):
        return []
    return sorted(touched)


def _trace_touched_files(session: DriftSession) -> list[str]:
    """Fallback: collect ``touched_files`` metadata from session trace entries."""
    collected: set[str] = set()
    for entry in getattr(session, "trace", []):
        tf = entry.get("touched_files") if isinstance(entry, dict) else None
        if isinstance(tf, (list, tuple)):
            collected.update(str(p) for p in tf if p)
    return sorted(collected)


def detect_touched_files(session: DriftSession) -> list[str]:
    """Determine files touched during the session.

    Primary source: ``git diff`` against ``session.git_head_at_plan``.
    Fallback: ``touched_files`` metadata in trace entries.
    """
    repo = Path(session.repo_path) if session.repo_path else Path.cwd()
    base = getattr(session, "git_head_at_plan", None)
    git_files = _git_touched_files(repo, base)
    if git_files:
        return git_files
    return _trace_touched_files(session)


def classify_session(session: DriftSession) -> ChangeClass:
    """Classify the session via detected touched files."""
    return classify_touched(detect_touched_files(session))


# ---------------------------------------------------------------------------
# Required artifacts
# ---------------------------------------------------------------------------


def _session_md_path(session: DriftSession) -> str:
    return f"work_artifacts/session_{session.session_id[:8]}.md"


def required_artifacts(
    change_class: ChangeClass, session: DriftSession
) -> list[RequiredArtifact]:
    """Return the required artifacts for a change class."""
    session_md = RequiredArtifact(
        kind="session_md",
        path=_session_md_path(session),
        reason=(
            "Session-Handover-Markdown mit Scope, Ergebnissen, offenen Enden "
            "und Next-Agent-Einstieg."
        ),
    )
    if change_class in (ChangeClass.SIGNAL, ChangeClass.ARCHITECTURE):
        return [
            RequiredArtifact(
                kind="evidence",
                path="benchmark_results/v<Version>_<slug>_feature_evidence.json",
                reason=(
                    "Versioniertes Evidence-JSON laut "
                    "drift-evidence-artifact-authoring Skill."
                ),
            ),
            RequiredArtifact(
                kind="adr",
                path="decisions/ADR-<NNN>-<slug>.md",
                reason=(
                    "ADR-Draft (status: proposed) mit Kontext, Alternativen, "
                    "Entscheidung, Konsequenzen, Validierung."
                ),
            ),
            session_md,
        ]
    return [session_md]


# ---------------------------------------------------------------------------
# L1 existence
# ---------------------------------------------------------------------------


def _resolve_artifact_path(
    repo: Path, artifact: RequiredArtifact, overrides: dict[str, str] | None
) -> Path | None:
    """Resolve an artifact's concrete on-disk path.

    - For ``session_md``: deterministic path from session id.
    - For ``evidence`` / ``adr``: caller may supply ``overrides`` (by kind);
      otherwise we glob the conventional directory and pick a single match.
    """
    if overrides and artifact.kind in overrides:
        candidate = Path(overrides[artifact.kind])
        return candidate if candidate.exists() else None

    if artifact.kind == "session_md":
        return repo / artifact.path

    if artifact.kind == "evidence":
        evidence_dir = repo / "benchmark_results"
        if not evidence_dir.is_dir():
            return None
        matches = sorted(evidence_dir.glob("v*_feature_evidence.json"))
        return matches[-1] if matches else None

    if artifact.kind == "adr":
        adr_dir = repo / "decisions"
        if not adr_dir.is_dir():
            return None
        matches = sorted(adr_dir.glob("ADR-*.md"))
        return matches[-1] if matches else None

    return None


def _check_existence(
    repo: Path,
    required: list[RequiredArtifact],
    overrides: dict[str, str] | None,
) -> tuple[list[RequiredArtifact], dict[str, Path]]:
    missing: list[RequiredArtifact] = []
    resolved: dict[str, Path] = {}
    for artifact in required:
        path = _resolve_artifact_path(repo, artifact, overrides)
        if path is None or not path.exists():
            missing.append(artifact)
            continue
        min_bytes = MIN_JSON_BYTES if artifact.kind == "evidence" else MIN_MARKDOWN_BYTES
        if path.stat().st_size < min_bytes:
            missing.append(artifact)
            continue
        resolved[artifact.kind] = path
    return missing, resolved


# ---------------------------------------------------------------------------
# L2 shape
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(
    r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL
)
_SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)


def _parse_frontmatter(text: str) -> dict[str, str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def _split_sections(text: str) -> dict[str, str]:
    """Return map of section title -> body text (excluding heading)."""
    headings = list(_SECTION_RE.finditer(text))
    sections: dict[str, str] = {}
    for i, match in enumerate(headings):
        title = match.group("title").strip()
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        sections[title] = text[start:end].strip()
    return sections


def _check_session_md_shape(
    path: Path, session: DriftSession
) -> list[ShapeError]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return [ShapeError(str(path), "readable", "utf-8 text", "unreadable")]

    errors: list[ShapeError] = []
    frontmatter = _parse_frontmatter(text)
    if not frontmatter:
        errors.append(
            ShapeError(str(path), "frontmatter", "YAML block ---…---", "missing")
        )
        return errors

    expected_sid = session.session_id
    actual_sid = frontmatter.get("session_id", "")
    if actual_sid != expected_sid:
        errors.append(
            ShapeError(str(path), "session_id", expected_sid, actual_sid or "<missing>")
        )

    for required_field in (
        "change_class",
        "duration_seconds",
        "tool_calls",
        "tasks_completed",
        "findings_delta",
    ):
        if required_field not in frontmatter:
            errors.append(
                ShapeError(
                    str(path),
                    required_field,
                    "present in frontmatter",
                    "<missing>",
                )
            )

    sections = _split_sections(text)
    for required_section in _REQUIRED_SECTIONS:
        body = sections.get(required_section)
        if body is None:
            errors.append(
                ShapeError(
                    str(path),
                    "section",
                    f"## {required_section}",
                    "<missing>",
                )
            )
        elif not body.strip():
            errors.append(
                ShapeError(
                    str(path),
                    "section",
                    f"## {required_section} (non-empty)",
                    "<whitespace-only>",
                )
            )

    return errors


def _check_evidence_shape(
    path: Path, change_class: ChangeClass
) -> list[ShapeError]:
    import json

    errors: list[ShapeError] = []
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except OSError:
        return [ShapeError(str(path), "readable", "utf-8 text", "unreadable")]
    except json.JSONDecodeError as exc:
        return [ShapeError(str(path), "json", "valid JSON", f"decode error: {exc}")]

    if not isinstance(data, dict):
        return [ShapeError(str(path), "root", "JSON object", type(data).__name__)]

    for key in ("version", "feature", "description", "tests", "audit_artifacts_updated"):
        if key not in data:
            errors.append(
                ShapeError(str(path), key, "present", "<missing>")
            )

    audit = data.get("audit_artifacts_updated")
    if change_class in (ChangeClass.SIGNAL, ChangeClass.ARCHITECTURE) and (
        not isinstance(audit, list) or not audit
    ):
        errors.append(
            ShapeError(
                str(path),
                "audit_artifacts_updated",
                "non-empty list (signal/architecture class)",
                repr(audit),
            )
        )

    return errors


def _check_adr_shape(path: Path) -> list[ShapeError]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return [ShapeError(str(path), "readable", "utf-8 text", "unreadable")]

    errors: list[ShapeError] = []
    frontmatter = _parse_frontmatter(text)
    status = frontmatter.get("status", "")
    if status not in ("proposed", "accepted"):
        errors.append(
            ShapeError(
                str(path),
                "status",
                "proposed|accepted",
                status or "<missing>",
            )
        )

    sections = _split_sections(text)
    context = sections.get("Kontext", "")
    if len(context) < MIN_ADR_CONTEXT_CHARS:
        errors.append(
            ShapeError(
                str(path),
                "Kontext",
                f">= {MIN_ADR_CONTEXT_CHARS} chars",
                f"{len(context)} chars",
            )
        )

    # Require at least two mentions of the word "Alternative" or
    # two list items under a section heading that mentions alternatives.
    alt_count = len(re.findall(r"\bAlternative[n]?\b", text))
    if alt_count < 2:
        errors.append(
            ShapeError(
                str(path),
                "alternatives",
                ">= 2 explicit alternatives",
                f"{alt_count} mentions",
            )
        )

    for required_section in ("Entscheidung", "Konsequenzen"):
        if required_section not in sections or not sections[required_section].strip():
            errors.append(
                ShapeError(
                    str(path),
                    "section",
                    f"## {required_section}",
                    "<missing>",
                )
            )

    return errors


# ---------------------------------------------------------------------------
# L3 placeholder denylist
# ---------------------------------------------------------------------------


_DENY_RE = re.compile(
    r"(?i)(?<![A-Z0-9_])("
    + "|".join(re.escape(t) for t in _DENYLIST_TOKENS)
    + r")(?![A-Z0-9_])"
)
_NAME_PLACEHOLDER_RE = re.compile(
    r"(?i)(?<![A-Z0-9_])("
    + "|".join(re.escape(t) for t in _NAME_PLACEHOLDER_TOKENS)
    + r")(?![A-Z0-9_])"
)
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def _strip_large_code_fences(text: str) -> str:
    """Drop code fences of >= 3 lines, which are assumed to hold real samples."""

    def _replace(match: re.Match[str]) -> str:
        block = match.group(0)
        lines = block.splitlines()
        # Large block (>=3 content lines plus fence lines) is treated as a real
        # example and exempted from denylist.
        if len(lines) >= 5:
            return "\n" * len(lines)
        return block  # keep; will be scanned

    return _CODE_FENCE_RE.sub(_replace, text)


def _scan_placeholders(path: Path) -> list[PlaceholderFlag]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    stripped = _strip_large_code_fences(text)
    flags: list[PlaceholderFlag] = []
    for lineno, line in enumerate(stripped.splitlines(), start=1):
        for pattern_re in (_DENY_RE, _NAME_PLACEHOLDER_RE):
            for match in pattern_re.finditer(line):
                snippet = line.strip()[:120]
                flags.append(
                    PlaceholderFlag(
                        path=str(path),
                        line=lineno,
                        pattern=match.group(1),
                        snippet=snippet,
                    )
                )
    return flags


# ---------------------------------------------------------------------------
# Top-level validate
# ---------------------------------------------------------------------------


def _llm_review_enabled() -> bool:
    return os.environ.get("DRIFT_SESSION_END_LLM_REVIEW", "0") == "1"


def validate(
    session: DriftSession,
    *,
    change_class: ChangeClass | None = None,
    path_overrides: dict[str, str] | None = None,
    llm_review: bool | None = None,
    llm_reviewer: Any | None = None,
) -> ValidationResult:
    """Run L1–L3 (and optionally L4) validation for a session's handover.

    Parameters
    ----------
    session:
        The active ``DriftSession`` whose end is being validated.
    change_class:
        Override for the detected change class. If ``None``, classification
        runs from session trace + git diff.
    path_overrides:
        Mapping from artifact kind (``"session_md"``, ``"evidence"``, ``"adr"``)
        to concrete file paths. Used by tests and by agents that pass explicit
        artifact paths via the MCP tool.
    llm_review:
        Force-enable/disable the L4 LLM review. If ``None``, defaults to the
        ``DRIFT_SESSION_END_LLM_REVIEW`` environment flag.
    llm_reviewer:
        Callable ``(payload) -> bool`` injected for tests.
    """
    touched = detect_touched_files(session)
    if change_class is None:
        change_class = classify_touched(touched)

    required = required_artifacts(change_class, session)
    repo = Path(session.repo_path) if session.repo_path else Path.cwd()

    missing, resolved = _check_existence(repo, required, path_overrides)

    shape_errors: list[ShapeError] = []
    placeholder_flags: list[PlaceholderFlag] = []

    session_md_path = resolved.get("session_md")
    if session_md_path is not None:
        shape_errors.extend(_check_session_md_shape(session_md_path, session))
        placeholder_flags.extend(_scan_placeholders(session_md_path))

    evidence_path = resolved.get("evidence")
    if evidence_path is not None:
        shape_errors.extend(_check_evidence_shape(evidence_path, change_class))

    adr_path = resolved.get("adr")
    if adr_path is not None:
        shape_errors.extend(_check_adr_shape(adr_path))
        placeholder_flags.extend(_scan_placeholders(adr_path))

    semantic_ok: bool | None = None
    run_llm = llm_review if llm_review is not None else _llm_review_enabled()
    if run_llm and not missing and not shape_errors and not placeholder_flags:
        reviewer = llm_reviewer or _default_llm_reviewer
        try:
            semantic_ok = bool(
                reviewer(
                    {
                        "session_md": str(session_md_path) if session_md_path else None,
                        "adr": str(adr_path) if adr_path else None,
                        "evidence": str(evidence_path) if evidence_path else None,
                        "change_class": str(change_class.value),
                    }
                )
            )
        except Exception:  # noqa: BLE001 - review hook isolation
            semantic_ok = False

    return ValidationResult(
        change_class=change_class,
        required=required,
        missing=missing,
        shape_errors=shape_errors,
        placeholder_flags=placeholder_flags,
        semantic_ok=semantic_ok,
        touched_files=touched,
    )


def _default_llm_reviewer(payload: dict[str, Any]) -> bool:
    """Default L4 reviewer — returns True without invoking any external LLM.

    A real deployment replaces this by injecting ``llm_reviewer=...`` or by
    wiring a production reviewer through ``drift.agent`` configuration.
    """
    _ = payload
    return True


# ---------------------------------------------------------------------------
# Bypass-reason validation (for force=true)
# ---------------------------------------------------------------------------


def validate_bypass_reason(reason: str | None) -> str | None:
    """Return an error message if the bypass reason is unacceptable, else ``None``.

    A valid reason has at least ``MIN_BYPASS_REASON_CHARS`` characters after
    strip and contains no denylisted placeholder tokens.
    """
    if reason is None:
        return "bypass_reason required when force=true"
    stripped = reason.strip()
    if len(stripped) < MIN_BYPASS_REASON_CHARS:
        return (
            f"bypass_reason must have at least {MIN_BYPASS_REASON_CHARS} "
            f"characters (got {len(stripped)})"
        )
    if _DENY_RE.search(stripped) or _NAME_PLACEHOLDER_RE.search(stripped):
        return "bypass_reason contains placeholder tokens"
    return None


__all__ = [
    "ChangeClass",
    "MAX_HANDOVER_RETRIES",
    "MIN_ADR_CONTEXT_CHARS",
    "MIN_BYPASS_REASON_CHARS",
    "MIN_JSON_BYTES",
    "MIN_MARKDOWN_BYTES",
    "PlaceholderFlag",
    "RequiredArtifact",
    "ShapeError",
    "ValidationResult",
    "classify_session",
    "classify_touched",
    "detect_touched_files",
    "required_artifacts",
    "validate",
    "validate_bypass_reason",
]
