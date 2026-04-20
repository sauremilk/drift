"""Translation Layer for Drift findings.

Translates technical signal findings into plain language for non-programmers.

Public API::

    from drift.lang import translate_finding, enrich_human_messages

    # Single finding
    msg = translate_finding(finding, lang="de", audience="plain")

    # Batch enrichment (pipeline integration)
    enriched = enrich_human_messages(findings, lang="de", audience="plain")
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Literal

from drift.lang._catalog import FALLBACK_TEMPLATES, PLAIN_CATALOG

if TYPE_CHECKING:
    from drift.models._findings import Finding

Audience = Literal["developer", "plain"]


def _template_vars(finding: Finding) -> dict[str, str]:
    """Build substitution variables from a Finding."""
    return {
        "file": finding.file_path.as_posix() if finding.file_path else "unbekannt",
        "symbol": finding.symbol or "unbekannt",
        "line": str(finding.start_line) if finding.start_line else "?",
        "impact": f"{finding.impact * 100:.0f} %" if finding.impact else "?",
        "signal_type": finding.signal_type,
    }


def translate_finding(
    finding: Finding,
    *,
    lang: str = "en",
    audience: Audience = "plain",
) -> str:
    """Translate a Finding into a human-readable message.

    Parameters
    ----------
    finding:
        The Finding to translate.
    lang:
        ISO 639-1 language code (``"de"``, ``"en"``).  Falls back to
        ``"en"`` for unsupported languages.
    audience:
        ``"developer"`` returns the original description unchanged.
        ``"plain"`` returns a non-programmer-friendly message.

    Returns
    -------
    str
        The translated message.
    """
    if audience == "developer":
        return finding.description

    signal_templates = PLAIN_CATALOG.get(finding.signal_type)
    if signal_templates is None:
        # Unknown / plugin signal → fallback
        tpl = FALLBACK_TEMPLATES.get(lang, FALLBACK_TEMPLATES["en"])
    else:
        tpl = signal_templates.get(lang, signal_templates.get("en", {}))  # type: ignore[typeddict-item]
        if not tpl:
            tpl = FALLBACK_TEMPLATES.get(lang, FALLBACK_TEMPLATES["en"])

    variables = _template_vars(finding)

    parts: list[str] = []
    if tpl.get("title"):
        parts.append(tpl["title"].format_map(variables))
    if tpl.get("description"):
        parts.append(tpl["description"].format_map(variables))
    if tpl.get("impact"):
        parts.append(tpl["impact"].format_map(variables))
    if tpl.get("action"):
        parts.append(tpl["action"].format_map(variables))

    return " ".join(parts)


def enrich_human_messages(
    findings: list[Finding],
    *,
    lang: str = "en",
    audience: Audience = "plain",
) -> list[Finding]:
    """Return a new list of findings with ``human_message`` populated.

    Does **not** mutate the original findings.  In ``developer`` mode,
    ``human_message`` stays ``None``.

    Parameters
    ----------
    findings:
        Original findings list.
    lang:
        ISO 639-1 language code.
    audience:
        ``"developer"`` or ``"plain"``.

    Returns
    -------
    list[Finding]
        Shallow copies with ``human_message`` set (plain) or ``None`` (developer).
    """
    result: list[Finding] = []
    for f in findings:
        enriched = copy.copy(f)
        if audience == "plain":
            enriched.human_message = translate_finding(f, lang=lang, audience="plain")
        else:
            enriched.human_message = None
        result.append(enriched)
    return result
