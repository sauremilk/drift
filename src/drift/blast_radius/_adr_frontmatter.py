"""ADR-Frontmatter-Parser für die Blast-Radius-Engine.

Der zentrale ``adr_scanner`` parst nur skalare ``key: value``-Paare. Für
ADR-087-Semantik (``scope: list[str]``, ``criticality: critical|high|normal``)
brauchen wir eine leichtgewichtige Erweiterung, die YAML-Block-Listen
versteht, ohne PyYAML-Dependency.

Unterstützte Frontmatter-Formen:

.. code-block:: yaml

    ---
    id: ADR-087
    status: proposed
    scope:
      - "src/drift/blast_radius/**"
      - "scripts/check_blast_radius_gate.py"
    criticality: high
    ---

Inline-Listen (``scope: [a, b]``) werden ebenfalls unterstützt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_SCALAR_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*):\s*(?P<value>.*)$")
_LIST_ITEM_RE = re.compile(r"^\s+-\s+(?P<value>.*)$")
_INLINE_LIST_RE = re.compile(r"^\[(.*)\]$")

_VALID_CRITICALITIES: frozenset[str] = frozenset({"critical", "high", "normal"})
_VALID_STATUSES: frozenset[str] = frozenset(
    {"proposed", "accepted", "rejected", "superseded", "obsolete"}
)


@dataclass(frozen=True, slots=True)
class ADRFrontmatter:
    """Geparstes ADR-Frontmatter mit Blast-Radius-Feldern."""

    id: str
    status: str
    date: str | None = None
    supersedes: str | None = None
    scope: tuple[str, ...] = field(default_factory=tuple)
    criticality: str | None = None
    raw: dict[str, object] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Nur ``proposed`` und ``accepted`` ADRs sind für Blast-Radius relevant."""
        return self.status in {"proposed", "accepted"}

    @property
    def is_critical(self) -> bool:
        return self.criticality == "critical"


def _strip_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return stripped[1:-1]
    return stripped


def _parse_inline_list(raw: str) -> tuple[str, ...]:
    match = _INLINE_LIST_RE.match(raw.strip())
    if not match:
        return ()
    inner = match.group(1).strip()
    if not inner:
        return ()
    parts = [p.strip() for p in inner.split(",")]
    return tuple(_strip_quotes(p) for p in parts if p)


def parse_frontmatter_block(block: str) -> dict[str, object]:
    """Parse einen rohen Frontmatter-Block in ein Key-Value-Dict.

    Unterstützt Skalare, Block-Listen und Inline-Listen. Unbekannte
    Einrückung wird toleriert und als Skalar behandelt.
    """
    result: dict[str, object] = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        scalar = _SCALAR_RE.match(line)
        if not scalar:
            i += 1
            continue
        key = scalar.group("key").strip()
        value = scalar.group("value").strip()
        if value == "":
            # Block-Liste folgt ggf.
            items: list[str] = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if not next_line.strip():
                    j += 1
                    continue
                item_match = _LIST_ITEM_RE.match(next_line)
                if not item_match:
                    break
                items.append(_strip_quotes(item_match.group("value")))
                j += 1
            if items:
                result[key] = tuple(items)
                i = j
                continue
            # Leerer Wert ohne folgende Items → None
            result[key] = None
            i += 1
            continue
        inline = _parse_inline_list(value)
        if inline:
            result[key] = inline
        else:
            result[key] = _strip_quotes(value)
        i += 1
    return result


def parse_adr_file(path: Path) -> ADRFrontmatter | None:
    """Lade und parse ein ADR-Markdown-File.

    Returns ``None``, wenn die Datei kein Frontmatter hat oder nicht lesbar ist.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return None
    raw = parse_frontmatter_block(match.group(1))
    adr_id = str(raw.get("id") or path.stem)
    status = str(raw.get("status") or "").lower()
    scope_raw = raw.get("scope")
    scope: tuple[str, ...]
    if isinstance(scope_raw, tuple):
        scope = tuple(str(item) for item in scope_raw)
    elif isinstance(scope_raw, str) and scope_raw:
        scope = (scope_raw,)
    else:
        scope = ()
    criticality_raw = raw.get("criticality")
    criticality = str(criticality_raw).lower() if isinstance(criticality_raw, str) else None
    date_raw = raw.get("date")
    supersedes_raw = raw.get("supersedes")
    return ADRFrontmatter(
        id=adr_id,
        status=status,
        date=str(date_raw) if isinstance(date_raw, str) else None,
        supersedes=str(supersedes_raw) if isinstance(supersedes_raw, str) else None,
        scope=scope,
        criticality=criticality,
        raw=raw,
    )


@dataclass(frozen=True, slots=True)
class ADRValidationIssue:
    """Eine Frontmatter-Verletzung mit Severity."""

    path: Path
    adr_id: str
    severity: str  # "error" | "warning"
    message: str


def validate_adr_frontmatter(
    decisions_dir: Path,
) -> list[ADRValidationIssue]:
    """Validiere alle ADRs in ``decisions_dir`` gegen das ADR-087-Schema.

    Regeln:

    - ``status`` muss aus dem geschlossenen Set stammen (Error).
    - ``criticality: critical`` ohne ``scope`` ist Error.
    - ``criticality`` mit ungültigem Wert ist Error.
    - ``scope``-Einträge müssen non-empty Strings sein (Error).
    - Fehlendes ``scope`` bei aktiven ADRs ist Warning (Text-Fallback greift).
    """
    if not isinstance(decisions_dir, Path):
        raise TypeError(f"decisions_dir must be a Path, got {type(decisions_dir)!r}")
    issues: list[ADRValidationIssue] = []
    if not decisions_dir.is_dir():
        return issues
    for adr_path in sorted(decisions_dir.glob("ADR-*.md")):
        parsed = parse_adr_file(adr_path)
        if parsed is None:
            # Migration-Toleranz: bestehende ADRs ohne Frontmatter dürfen existieren.
            # Sie fallen für Blast-Radius automatisch auf den Text-Scanner zurück.
            issues.append(
                ADRValidationIssue(
                    path=adr_path,
                    adr_id=adr_path.stem,
                    severity="warning",
                    message="Kein YAML-Frontmatter — Blast-Radius nutzt Text-Fallback.",
                )
            )
            continue
        if parsed.status and parsed.status not in _VALID_STATUSES:
            issues.append(
                ADRValidationIssue(
                    path=adr_path,
                    adr_id=parsed.id,
                    severity="error",
                    message=f"Unbekannter status: {parsed.status!r}. Erlaubt: "
                    + ", ".join(sorted(_VALID_STATUSES)),
                )
            )
        if parsed.criticality is not None and parsed.criticality not in _VALID_CRITICALITIES:
            issues.append(
                ADRValidationIssue(
                    path=adr_path,
                    adr_id=parsed.id,
                    severity="error",
                    message=(
                        f"Unbekannte criticality: {parsed.criticality!r}. "
                        "Erlaubt: critical, high, normal."
                    ),
                )
            )
        if parsed.is_critical and not parsed.scope:
            issues.append(
                ADRValidationIssue(
                    path=adr_path,
                    adr_id=parsed.id,
                    severity="error",
                    message="criticality: critical ohne scope ist nicht zulässig.",
                )
            )
        if parsed.scope:
            for item in parsed.scope:
                if not item or not item.strip():
                    issues.append(
                        ADRValidationIssue(
                            path=adr_path,
                            adr_id=parsed.id,
                            severity="error",
                            message="Leerer scope-Eintrag ist nicht zulässig.",
                        )
                    )
                    break
        elif parsed.is_active:
            issues.append(
                ADRValidationIssue(
                    path=adr_path,
                    adr_id=parsed.id,
                    severity="warning",
                    message=(
                        "scope nicht gesetzt — Blast-Radius fällt auf textbasiertes "
                        "ADR-Matching zurück (niedrigere Precision)."
                    ),
                )
            )
    return issues


def load_all_adrs(decisions_dir: Path) -> list[ADRFrontmatter]:
    """Lade alle aktiven ADRs (``proposed`` + ``accepted``) aus ``decisions_dir``."""
    adrs: list[ADRFrontmatter] = []
    if not decisions_dir.is_dir():
        return adrs
    for adr_path in sorted(decisions_dir.glob("ADR-*.md")):
        parsed = parse_adr_file(adr_path)
        if parsed is None or not parsed.is_active:
            continue
        adrs.append(parsed)
    return adrs
