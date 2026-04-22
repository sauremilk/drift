"""Phase 3 — Agent Handoff.

Generates an agent prompt that embeds the contracts as invisible constraints
and encodes the autonomous agent regelkreis with a conservative severity gate
(see ADR-089).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Section headers kept as module constants so the contract test can assert
# their presence without duplicating string literals.
SECTION_TRIGGER = "## Trigger"
SECTION_REGELKREIS = "## Regelkreis"
SECTION_SEVERITY_GATE = "## Severity-Gate"
SECTION_APPROVAL_GATE = "## Approval-Gate"
SECTION_FEEDBACK_LOOP = "## Feedback-Loop"
SECTION_ROLLBACK = "## Rollback-Trigger"

REQUIRED_SECTIONS: tuple[str, ...] = (
    SECTION_TRIGGER,
    SECTION_REGELKREIS,
    SECTION_SEVERITY_GATE,
    SECTION_APPROVAL_GATE,
    SECTION_FEEDBACK_LOOP,
    SECTION_ROLLBACK,
)


def _gate_decision_for(contract: dict[str, Any]) -> str:
    """Map a contract to its gate routing (AUTO | REVIEW | BLOCK).

    Conservative mapping per ADR-089:
    - ``high``/``critical`` → BLOCK
    - ``medium`` → REVIEW
    - ``low``/``info`` → AUTO only when ``auto_repair_eligible`` is true,
      otherwise REVIEW.
    """
    severity = str(contract.get("severity", "medium")).lower()
    if severity in ("high", "critical"):
        return "BLOCK"
    if severity == "medium":
        return "REVIEW"
    # low / info / unknown low-risk
    if contract.get("auto_repair_eligible") is True:
        return "AUTO"
    return "REVIEW"


def _render_constraint_block(contracts: list[dict[str, Any]]) -> str:
    """Render contracts as a constraint block for agent prompts."""
    lines: list[str] = []
    for c in contracts:
        severity_icon = {"critical": "🔴", "high": "🟡", "medium": "🟢"}.get(
            c.get("severity", "medium"), "⚪"
        )
        gate = _gate_decision_for(c)
        lines.append(
            f"- [{severity_icon} {c['severity'].upper()}] **{c['id']}** "
            f"→ Gate: `{gate}`: {c['description_technical']}"
        )
        if c.get("verification_signal") and c["verification_signal"] != "manual":
            lines.append(f"  Signal: `{c['verification_signal']}`")
    return "\n".join(lines)


def _render_trigger_section() -> list[str]:
    return [
        SECTION_TRIGGER,
        "",
        "Der Agent-Regelkreis wird durch einen der folgenden Trigger aktiviert:",
        "",
        "- **Datei-Edit**: Nach jeder Änderung an einer Quelldatei MUSS"
        " `drift_nudge(changed_files=[...])` aufgerufen werden (Post-Edit-Nudge-Vertrag,"
        " siehe `.github/copilot-instructions.md`).",
        "- **Cron / Schedule**: Geplante Wiederholung über"
        " `.github/workflows/drift-baseline-persist.yml`.",
        "- **PR-Event**: `action.yml` mit `comment: true` postet strukturierten Report am PR.",
        "",
    ]


def _render_regelkreis_section() -> list[str]:
    return [
        SECTION_REGELKREIS,
        "",
        "Der autonome Regelkreis durchläuft fünf Phasen. Jede Phase benennt das"
        " verbindliche Werkzeug.",
        "",
        "1. **Analyze** — `drift analyze --format json` (oder MCP `drift_scan`)"
        " erzeugt strukturierte Findings gemäß `drift.output.schema.json`.",
        "2. **Classify** — Jedes Finding wird über das Severity-Gate unten einem"
        " der drei Buckets `AUTO` / `REVIEW` / `BLOCK` zugeordnet.",
        "3. **Decide** — Agent prüft zusätzlich `auto_repair_eligible` und"
        " `drift_nudge(...).safe_to_commit`. Bei `safe_to_commit=false` darf kein"
        " `AUTO` ausgeführt werden.",
        "4. **Act** — `AUTO` → Patch anwenden. `REVIEW` → PR-Kommentar via"
        " `action.yml`. `BLOCK` → Workflow-Exit ≠ 0 und Issue-Filing.",
        "5. **Feedback** — TP/FP über `drift feedback` markieren. Der Workflow"
        " `.github/workflows/drift-label-feedback.yml` speist Kalibrierung zurück.",
        "",
    ]


def _render_severity_gate_section(contracts: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = [
        SECTION_SEVERITY_GATE,
        "",
        "Verbindliches Routing (ADR-089, konservativ). Der Agent DARF dieses"
        " Mapping nicht umgehen.",
        "",
        "| Severity | auto_repair_eligible | Gate | Aktion |",
        "|---|---|---|---|",
        "| low / info | true | `AUTO` | Patch direkt anwenden, wenn `safe_to_commit=true`. |",
        "| low / info | false | `REVIEW` | Als PR-Kommentar eskalieren. |",
        "| medium | egal | `REVIEW` | Als PR-Kommentar eskalieren. |",
        "| high / critical | egal | `BLOCK` | CI-Exit ≠ 0 und Issue-Filing. |",
        "",
    ]
    if contracts:
        lines.extend(
            [
                "Pro-Contract-Routing (aus `drift.intent.json`):",
                "",
            ]
        )
        for c in contracts:
            lines.append(
                f"- **{c['id']}** (`{c.get('severity', 'medium')}`,"
                f" auto_repair_eligible=`{bool(c.get('auto_repair_eligible'))}`)"
                f" → Gate: `{_gate_decision_for(c)}`"
            )
        lines.append("")
    return lines


def _render_approval_gate_section() -> list[str]:
    return [
        SECTION_APPROVAL_GATE,
        "",
        "`BLOCK`- und `REVIEW`-Findings werden nur durch einen Menschen freigegeben.",
        "",
        "- Der Agent MUSS einen Vorschlag in"
        " `work_artifacts/agent_run_<timestamp>.md` ablegen, bevor er wartet.",
        "- CI akzeptiert das Gate nur, wenn entweder das Label `drift/approved` durch"
        " einen Maintainer gesetzt ist oder `drift_nudge(...).safe_to_commit=true`.",
        "- Der Agent DARF dieses Gate nicht selbst setzen, überspringen oder"
        " umschreiben. Bypass-Versuche werden von"
        " `scripts/verify_gate_not_bypassed.py` erkannt.",
        "",
    ]


def _render_feedback_loop_section() -> list[str]:
    return [
        SECTION_FEEDBACK_LOOP,
        "",
        "- True-Positive / False-Positive: `drift feedback mark --finding <id> --outcome tp|fp`.",
        "- Label-basierter Feedback-Pfad: PR-Labels werden durch"
        " `.github/workflows/drift-label-feedback.yml` in Kalibrierungsinput"
        " übersetzt.",
        "- Der Agent aktualisiert `agent_telemetry.agent_actions_taken` (sobald"
        " Schema 2.2 aktiv ist, siehe Paket 1B) mit dem `feedback_mark`-Eintrag.",
        "",
    ]


def _render_rollback_section() -> list[str]:
    return [
        SECTION_ROLLBACK,
        "",
        "- Wenn `drift_nudge(...).revert_recommended == true`: Edit SOFORT"
        " revertieren und einen anderen Ansatz wählen.",
        "- Wenn ein `AUTO`-Patch bei erneutem `drift_nudge` `direction: degrading`"
        " liefert: Patch revertieren und auf `REVIEW` eskalieren.",
        "- Rollback wird in `agent_telemetry.agent_actions_taken` mit"
        " `action_type: auto_fix` und `reason: reverted_on_degrading` dokumentiert.",
        "",
    ]


def handoff(
    prompt: str,
    intent_data: dict[str, Any],
) -> str:
    """Execute Phase 3 — generate the agent prompt.

    Parameters
    ----------
    prompt:
        Original user prompt.
    intent_data:
        Validated ``drift.intent.json`` payload.

    Returns
    -------
    str
        Markdown agent prompt content. Includes the autonomous regelkreis
        sections (trigger, regelkreis, severity-gate, approval-gate,
        feedback-loop, rollback-trigger) defined in ADR-089.
    """
    contracts = intent_data.get("contracts", [])
    category = intent_data.get("category", "utility")

    lines: list[str] = [
        "# Agent-Auftrag",
        "",
        "## Ziel",
        "",
        f"> {prompt}",
        "",
        f"Kategorie: **{category}**",
        "",
        "## Constraints (automatisch generiert)",
        "",
        "Die folgenden Anforderungen MÜSSEN bei der Implementierung eingehalten werden.",
        "Nach jedem Modul / jeder Funktion stoppen und auf Validierung warten.",
        "",
        _render_constraint_block(contracts),
        "",
        "## Validierung",
        "",
        "Nach jeder Änderung wird `drift intent run --phase 4` ausgeführt.",
        "Der Commit ist erst erlaubt, wenn alle Contracts den Status `fulfilled` haben.",
        "",
        "## Ablauf",
        "",
        "1. Implementiere die nächste Funktion / das nächste Modul",
        "2. Stoppe und warte auf `drift intent run --phase 4`",
        "3. Behebe alle `violated`-Contracts",
        "4. Wiederhole bis alle Contracts `fulfilled` sind",
        "",
    ]

    lines.extend(_render_trigger_section())
    lines.extend(_render_regelkreis_section())
    lines.extend(_render_severity_gate_section(contracts))
    lines.extend(_render_approval_gate_section())
    lines.extend(_render_feedback_loop_section())
    lines.extend(_render_rollback_section())

    return "\n".join(lines)


def save_agent_prompt(content: str, repo_path: Path) -> Path:
    """Write drift.agent.prompt.md to the repo root."""
    out = repo_path / "drift.agent.prompt.md"
    out.write_text(content, encoding="utf-8")
    return out
