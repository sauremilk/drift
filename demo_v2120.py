"""Live-Demo der neuen Features in drift v2.12.0 / v2.13.0."""
from __future__ import annotations

import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import drift.api as api
from drift.arch_graph import ArchGraphStore, ArchHotspot, seed_graph
from drift.repair_template_registry import RepairTemplateRegistry

REPO = "."
SCOPE = "src/drift"
CACHE_DIR = Path(REPO).resolve() / ".drift-cache"
SEP = "=" * 60

# Git-SHA fuer Graph-Versionierung
try:
    _sha = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], text=True
    ).strip()
except Exception:
    _sha = "dev"

# ---------------------------------------------------------------------------
# 1) ArchGraph: scan -> module_scores + hotspots -> seed + persist
# ---------------------------------------------------------------------------
print("\n" + SEP)
print("FEATURE 1 -- Arch-graph API (seed_graph + ArchGraphStore)")
print(SEP)

# 1a) drift_map mit target_path=SCOPE: Module-Keys ('src/drift/api' etc.)
#     stimmen mit Findings-file_path ueberein -> module_scores + hotspots koennen
#     korrekt zugeordnet werden. Deps innerhalb src/drift sind 0 (absoluter Import-
#     stil), das ist erwartetes Verhalten fuer ein Python-Package.
dm = api.drift_map(REPO, target_path=SCOPE, max_modules=50)
modules = dm.get("modules", [])
deps = dm.get("dependencies", [])
print(f"  drift_map({SCOPE!r}) -> {len(modules)} Module, {len(deps)} Dependencies")

# 1b) scan liefert Findings mit file_path und signal -> Grundlage fuer module_scores + hotspots
print("  Starte Scan (max_findings=100) ...")
scan_result = api.scan(REPO, max_findings=100, response_detail="detailed", target_path=SCOPE)
findings = scan_result.get("findings", [])
print(f"  scan({SCOPE!r}) -> {len(findings)} Findings")

# 1c) module_scores aus findings ableiten
# file-Wert kann Datei ('src/drift/api/diff.py') oder Dir ('src/drift/signals') sein.
# drift_map-Module sind immer Verzeichnis-Pfade -> parent bei Dateien, direkt bei Dirs.
_mod_signals: dict[str, list[str]] = defaultdict(list)
for f in findings:
    fp = f.get("file", "")
    if not fp:
        continue
    p = Path(fp)
    mod = p.parent.as_posix() if p.suffix else fp
    # Normiere auf max 3 Ebenen (src/drift/<subpackage>) - tiefere Files gehoeren zum
    # naechsthoeherem Modul das drift_map kennt
    parts = Path(mod).parts
    if len(parts) > 3:
        mod = "/".join(parts[:3])
    _mod_signals[mod].append(f.get("signal", "UNKNOWN"))

module_scores: dict[str, dict] = {}
for mod, sigs in _mod_signals.items():
    counts = Counter(sigs)
    total = len(sigs)
    module_scores[mod] = {
        "drift_score": min(1.0, round(total / 20.0, 3)),
        "signal_scores": {s: round(c / total, 3) for s, c in counts.items()},
    }

# 1d) hotspots: Module mit >= 2 Findings und wiederkehrenden Signalen
hotspots: list[ArchHotspot] = [
    ArchHotspot(
        path=mod,
        recurring_signals=dict(Counter(sigs)),
        trend="degrading" if len(sigs) >= 5 else "stable",
        total_occurrences=len(sigs),
    )
    for mod, sigs in _mod_signals.items()
    if len(sigs) >= 2
]

# 1e) Graph seeden: mit echten Module-Scores aus dem Scan
graph = seed_graph(
    drift_map_result=dm,
    version=_sha,
    module_scores=module_scores,
)
graph.hotspots = hotspots  # nach seed_graph hinzufuegen

# Top-5 nach Drift-Score anzeigen
top_mods = sorted(
    graph.modules, key=lambda m: m.drift_score, reverse=True
)[:5]
print("  Top-5 Module nach Drift-Score:")
for m in top_mods:
    print(
        f"    {m.path}  score={m.drift_score:.3f}"
        f"  files={m.file_count}  signals={m.signal_scores}"
    )

print(
    f"\n  ArchGraph: {len(graph.modules)} Module,"
    f" {len(graph.dependencies)} Kanten,"
    f" {len(graph.abstractions)} Abstraktionen,"
    f" {len(graph.hotspots)} Hotspots"
)

store = ArchGraphStore(cache_dir=CACHE_DIR)
store.save(graph)
print(f"  Graph (version={_sha!r}) in {CACHE_DIR} persistiert.")

# ---------------------------------------------------------------------------
# 2) steer() -- location-centric architecture context
# ---------------------------------------------------------------------------
print("\n" + SEP)
print("FEATURE 2 -- steer() (pre-edit, location-centric context)")
print(SEP)

steer_target = top_mods[0].path if top_mods else SCOPE
result = api.steer(REPO, target=steer_target)
print(f"  Ziel: {steer_target!r}")
print(f"  Module im Kontext: {len(result.get('modules', []))}")
print(f"  Nachbarn: {result.get('neighbors', [])}")
print(f"  Hotspots: {len(result.get('hotspots', []))}")
print(f"  Layer-Policies: {len(result.get('layer_policies', []))}")
print(f"  Abstraktionen (reuse): {len(result.get('abstractions', []))}")
instr = result.get("agent_instruction", "")
if instr:
    print(f"\n  agent_instruction:\n    {instr[:280]}")

# ---------------------------------------------------------------------------
# 3) suggest_rules() -- Feedback-Loop: Pattern -> Rule
# ---------------------------------------------------------------------------
print("\n" + SEP)
print("FEATURE 3 -- suggest_rules() (Feedback-Loop: Pattern -> Rule)")
print(SEP)

rules_result = api.suggest_rules(REPO, min_occurrences=2)
proposals = rules_result.get("proposals", [])
print(f"  {len(proposals)} Regelvorschlaege generiert (min_occurrences=2).")
for p in proposals[:3]:
    pd = p.get("proposed_decision", {})
    pid = pd.get("id")
    pscope = pd.get("scope")
    prule = pd.get("rule")
    penf = pd.get("enforcement")
    pocc = p.get("occurrences")
    psig = p.get("signal_id")
    pmod = p.get("module_path")
    pconf = p.get("confidence", 0)
    print(f"\n    [{pid}]  Modul: {pmod}  Signal: {psig}")
    print(f"    Regel: {prule}")
    print(f"    Enforcement: {penf}  Occurrences: {pocc}  Konfidenz: {pconf:.2f}")
instr2 = rules_result.get("agent_instruction", "")
if instr2:
    print(f"\n  agent_instruction: {instr2[:200]}")

# ---------------------------------------------------------------------------
# 4) fix_plan + consolidation_opportunities (ADR-073)
# ---------------------------------------------------------------------------
print("\n" + SEP)
print("FEATURE 4 -- fix_plan: consolidation_opportunities (ADR-073)")
print(SEP)

fp = api.fix_plan(REPO, max_tasks=10, target_path=SCOPE)
tasks = fp.get("tasks", [])
cons = fp.get("consolidation_opportunities", [])
print(f"  fix_plan: {len(tasks)} Tasks, {len(cons)} Konsolidierungsgruppen")

for g in cons[:3]:
    gid = g.get("group_id")
    gtids = g.get("task_ids")
    gsav = g.get("estimated_savings")
    gpat = str(g.get("pattern_description", ""))[:100]
    print(f"\n    Gruppe: {gid}  Tasks: {gtids}")
    print(f"    Einsparung: {gsav}  Muster: {gpat}")

print("\n  Similar-Outcomes pro Task (ADR-072):")
for t in tasks[:4]:
    so = t.get("similar_outcomes") or []
    cg = t.get("consolidation_group_id")
    tid = t.get("id")
    sig = t.get("signal", "?")
    batch = t.get("batch_eligible", False)
    print(f"    [{tid}]  signal={sig}  batch={batch}  similar={len(so)}  group={cg}")

# ---------------------------------------------------------------------------
# 5) record_outcome -- angereichert mit task_id, new/resolved counts
# ---------------------------------------------------------------------------
print("\n" + SEP)
print("FEATURE 5 -- record_outcome (angereichert: task_id + counts)")
print(SEP)

registry = RepairTemplateRegistry()
if tasks:
    first = tasks[0]
    cg = first.get("consolidation_group_id") or "demo-group"
    fid_list = first.get("finding_ids") or ["demo-finding"]
    sig = first.get("signal", "cognitive_complexity")
    registry.record_outcome(
        signal=sig,
        edit_kind="refactor",
        context_class="production",
        direction="improving",
        score_delta=-0.5,
        task_id=cg,
        new_findings_count=0,
        resolved_count=1,
    )
    print(f"  Outcome fuer Signal {sig!r}  task_id={cg!r}")
    print("  direction=improving  resolved_count=1  new_findings_count=0")
    summary = registry.similar_outcomes(signal=sig, edit_kind="refactor")
    if summary:
        conf = summary.get("confidence")
        total = summary.get("total_outcomes", 0)
        conf_str = f"{conf:.2f}" if conf is not None else "n/a"
        print(f"  Template-Konfidenz: {conf_str}  (aus {total} Outcomes)")
    else:
        print("  (Kein Summary verfuegbar – noch zu wenige Eintraege)")
else:
    print("  Keine Tasks verfuegbar.")

print("\n" + SEP)
print("Demo abgeschlossen!")
print(SEP + "\n")

# ---------------------------------------------------------------------------
# 6) generate_skills (v2.13.0) — SkillBriefing -> .github/skills/<name>/SKILL.md
# ---------------------------------------------------------------------------
print("\n" + SEP)
print("FEATURE 6 -- generate_skills() (v2.13.0: Skill-Generator)")
print(SEP)

# Signal-Code -> menschenlesbare Beschreibung (aus echten Findings abgeleitet)
_SIGNAL_DESC = {
    "AVS": "Abstraction Violation / God-Module (zu viele Verantwortlichkeiten in einer Datei)",
    "EDS": "Unexplained Complexity / Entanglement (schwer erklärbare Komplexitaet)",
    "MDS": "Merge-/Duplikat-Signal (exakte oder nahezu identische Code-Duplikate)",
    "PFS": "Pattern Fragmentation (inkonsistente Muster fuer denselben Concern)",
    "CXS": "Cognitive Complexity (kognitiv schwer lesbare Funktionen/Methoden)",
    "TVS": "High Volatility (haeufig geaenderte Datei — Instabilitaet)",
    "DCA": "Dead Code / Unused Exports (potenziell ungenutzter Code)",
    "CCC": "Co-Change Coupling (versteckte Kopplung durch gemeinsame Aenderungshistorie)",
    "BEM": "Broad Exception Monoculture (undifferenziertes Exception-Handling)",
    "GCD": "Deep Nesting (tief verschachtelter Kontrollfluss)",
    "COD": "Cohesion Deficit (mangelnde interne Koh\u00e4sion eines Moduls)",
    "BAT": "Bypass Anti-Pattern (hohe Dichte an Umgehungsmarkierungen)",
}

skills_result = api.generate_skills(REPO, min_occurrences=2, min_confidence=0.6)
briefings = skills_result.get("skill_briefings", [])
print(
    f"  generate_skills() -> {len(briefings)} SkillBriefings"
    f" (min_occurrences=2, min_confidence=0.6)"
)
print()

SKILLS_ROOT = Path(REPO) / ".github" / "skills"
created = []
skipped = []

for b in briefings:
    name = b["name"]
    module_path = b["module_path"]
    signals = b["trigger_signals"]
    confidence = b["confidence"]
    hotspot_files = b["hotspot_files"]
    constraints = b["constraints"]
    layer = b["layer"] or "unbekannt"
    neighbors = b["neighbors"]
    abstractions = b["abstractions"]

    skill_dir = SKILLS_ROOT / name
    skill_file = skill_dir / "SKILL.md"

    if skill_file.exists():
        skipped.append(name)
        continue

    skill_dir.mkdir(parents=True, exist_ok=True)

    # Signal-Abschnitte fuer Core Rules
    signal_rules = []
    for sig in signals:
        desc = _SIGNAL_DESC.get(sig, sig)
        signal_rules.append(f"- **{sig}**: {desc} — vor Aenderungen in `{module_path}` pruefen.")

    # Constraints aus ADR/Decisions
    constraint_lines = []
    for c in constraints:
        enf = c.get("enforcement", "warn").upper()
        rule_text = c.get("rule", "")
        constraint_lines.append(f"- [{enf}] {rule_text}")

    signal_keywords = ", ".join(signals)
    neighbor_text = (
        ", ".join(f"`{n}`" for n in neighbors)
        if neighbors
        else "keine bekannten Nachbarmodule"
    )
    abstr_text = (", ".join(f"`{a}`" for a in abstractions)) if abstractions else "keine"
    hotspot_text = "\n".join(f"  - `{hf}`" for hf in hotspot_files)
    constraint_block = (
        "\n".join(constraint_lines)
        if constraint_lines
        else "- (Keine ADR-Constraints aktiv)"
    )
    rule_block = "\n".join(signal_rules)

    content = f"""---
name: {name}
description: >
  Drift-generierter Guard fuer `{module_path}`. Aktiv bei Signalen: {signal_keywords}.
  Konfidenz: {confidence:.2f}. Verwende diesen Skill wenn du Aenderungen an `{module_path}` planst
  oder wiederholte Drift-Findings ({signal_keywords}) fuer dieses Modul bearbeitest.
argument-hint: "Beschreibe die geplante Aenderung in `{module_path}`."
---

# Guard: `{module_path}`

Automatisch generiert von `drift.api.generate_skills` (v2.13.0).
Konfidenz: **{confidence:.2f}** | Signale: **{signal_keywords}**

## When To Use

Verwende diesen Skill wenn:
- Du Aenderungen in `{module_path}` oder dessen Untermodulen planst.
- Drift-Findings fuer Signale **{signal_keywords}** in diesem Modul auftauchen.
- Ein Code-Review fuer Dateien in `{module_path}` durchgefuehrt wird.

Bekannte Hotspot-Dateien:
{hotspot_text}

## Core Rules

{rule_block}

## Architecture Constraints (aus ADR/Decisions)

{constraint_block}

## Architecture Context

- **Layer**: `{layer}`
- **Nachbarmodule**: {neighbor_text}
- **Wiederverwendete Abstraktionen**: {abstr_text}

## Review Checklist

Vor jedem Commit in `{module_path}` pruefen:

{"".join(
    f"- [ ] Keine neuen **{sig}**-Findings eingefuehrt"
    f" (`drift analyze --target {module_path}`)" + chr(10)
    for sig in signals
)}- [ ] `drift nudge` zeigt `safe_to_commit: true`
- [ ] Keine unnoetigen Abstraktionsgrenzen verletzt

## References

- [DEVELOPER.md](../../DEVELOPER.md) — Build, Test, Contribution-Workflow
- [POLICY.md](../../POLICY.md) — Produktions- und Priorisierungsregeln
- [CHANGELOG.md](../../CHANGELOG.md) — Letzte Aenderungen
"""
    skill_file.write_text(content, encoding="utf-8")
    created.append(name)
    print(f"  [ERSTELLT] .github/skills/{name}/SKILL.md  signals={signals}  conf={confidence:.2f}")

print()
if skipped:
    print(f"  Uebersprungen (bereits vorhanden): {skipped}")
print(f"  Ergebnis: {len(created)} neu erstellt, {len(skipped)} uebersprungen.")
print()
instr6 = skills_result.get("agent_instruction", "")
if instr6:
    print(f"  agent_instruction: {instr6[:250]}...")

print("\n" + SEP)
print("Demo v2.13.0 abgeschlossen!")
print(SEP + "\n")
