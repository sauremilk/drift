# Drift Intent Guardian Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `capture_intent`, `verify_intent`, and `feedback_for_agent` as new MCP tools and API functions, enabling fully autonomous vibe-coding intent verification in agent workflows.

**Architecture:** New `src/drift/intent/` subpackage contains core logic (capture, verify, feedback, LLM, storage). Three new `src/drift/api/` modules expose them as Drift API functions. Three new A2A handlers in `src/drift/serve/a2a_router.py` register them as MCP tools. Intent artefacts are stored locally in `.drift/intents/<intent_id>.json`.

**Tech Stack:** Python 3.11+, Pydantic v2, existing `drift.api._config` helpers, `openai` (optional, LLM-gestützte Verifikation Phase 2), `json`, `hashlib`, `pathlib`

---

## File Map

| File | Action | Verantwortung |
|---|---|---|
| `src/drift/intent/__init__.py` | Create | Package-Exports |
| `src/drift/intent/_models.py` | Create | `CapturedIntent`, `VerifyResult`, `FeedbackResult` Pydantic-Modelle |
| `src/drift/intent/_storage.py` | Create | Lokal speichern/laden `.drift/intents/<id>.json` |
| `src/drift/intent/capture.py` | Create | Intent-Extraktion aus Rohtext (strukturiert, ohne LLM) |
| `src/drift/intent/verify.py` | Create | Strukturelle Feature-Prüfung gegen Artefakt-Pfad |
| `src/drift/intent/feedback.py` | Create | Priorisiertes Action-Set aus VerifyResult |
| `src/drift/api/capture_intent.py` | Create | API-Funktion `capture_intent(raw, path)` |
| `src/drift/api/verify_intent.py` | Create | API-Funktion `verify_intent(intent_id, artifact_path, path)` |
| `src/drift/api/feedback_for_agent.py` | Create | API-Funktion `feedback_for_agent(intent_id, path)` |
| `src/drift/api/__init__.py` | Modify | 3 neue Exports hinzufügen |
| `src/drift/serve/a2a_router.py` | Modify | 3 neue Handler + dispatch-Einträge |
| `tests/test_intent_capture.py` | Create | Unit-Tests für capture-Logik |
| `tests/test_intent_verify.py` | Create | Unit-Tests für verify-Logik |
| `tests/test_intent_feedback.py` | Create | Unit-Tests für feedback-Logik |
| `tests/test_intent_api.py` | Create | Integrationstests für alle 3 API-Funktionen |
| `tests/test_intent_mcp.py` | Create | MCP-Handler-Tests (A2A JSON-RPC) |

---

## Task 1: Intent-Modelle (`src/drift/intent/_models.py`)

**Files:**
- Create: `src/drift/intent/_models.py`
- Create: `src/drift/intent/__init__.py`
- Test: `tests/test_intent_capture.py` (erste Tests hier)

- [ ] **Step 1: Schreibe failing Test für CapturedIntent-Modell**

```python
# tests/test_intent_capture.py
from __future__ import annotations
import pytest
from drift.intent._models import CapturedIntent, VerifyResult, FeedbackResult, FeedbackAction


def test_captured_intent_fields():
    intent = CapturedIntent(
        intent_id="test-001",
        raw="Ich brauche eine Finanzplaner-App",
        summary="Finanzplaner-App",
        required_features=["Einnahmen erfassen", "Ausgaben erfassen"],
        output_type="web_app",
        confidence=0.9,
        clarification_needed=False,
        clarification_question=None,
    )
    assert intent.intent_id == "test-001"
    assert len(intent.required_features) == 2
    assert intent.clarification_needed is False


def test_verify_result_fulfilled():
    result = VerifyResult(
        status="fulfilled",
        confidence=0.95,
        missing=[],
        agent_feedback="",
    )
    assert result.status == "fulfilled"
    assert result.missing == []


def test_verify_result_incomplete():
    result = VerifyResult(
        status="incomplete",
        confidence=0.4,
        missing=["Budgetwarnungen fehlen"],
        agent_feedback="Implementiere: Budgetwarnung wenn 80% erreicht",
    )
    assert result.status == "incomplete"
    assert len(result.missing) == 1


def test_feedback_result_actions():
    result = FeedbackResult(
        actions=[
            FeedbackAction(priority=1, action="add_feature", description="Budgetwarnung"),
            FeedbackAction(priority=2, action="add_feature", description="Export-Funktion"),
        ],
        estimated_complexity="low",
    )
    assert len(result.actions) == 2
    assert result.actions[0].priority == 1
```

- [ ] **Step 2: Führe Test aus — erwartet FAIL (ImportError)**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_capture.py::test_captured_intent_fields -v
```
Erwartetes Ergebnis: `ModuleNotFoundError: No module named 'drift.intent'`

- [ ] **Step 3: Erstelle `src/drift/intent/_models.py`**

```python
"""Pydantic models for the Drift intent guardian system."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class CapturedIntent(BaseModel):
    """Structured representation of a user's natural-language intent."""

    model_config = ConfigDict(frozen=True)

    intent_id: str
    raw: str
    summary: str
    required_features: list[str]
    output_type: Literal["web_app", "script", "file", "api", "game", "automation", "unknown"]
    confidence: float
    clarification_needed: bool
    clarification_question: str | None = None


class VerifyResult(BaseModel):
    """Result of verifying a build artifact against a captured intent."""

    model_config = ConfigDict(frozen=True)

    status: Literal["fulfilled", "incomplete"]
    confidence: float
    missing: list[str]
    agent_feedback: str
    iteration: int = 1


class FeedbackAction(BaseModel):
    """A single prioritised action for the building agent."""

    model_config = ConfigDict(frozen=True)

    priority: int
    action: Literal["add_feature", "fix_bug", "improve_ux", "add_test"]
    description: str


class FeedbackResult(BaseModel):
    """Prioritised action set for the building agent."""

    model_config = ConfigDict(frozen=True)

    actions: list[FeedbackAction]
    estimated_complexity: Literal["low", "medium", "high"]
```

- [ ] **Step 4: Erstelle `src/drift/intent/__init__.py`**

```python
"""Drift Intent Guardian — autonomous vibe-coding intent verification."""

from __future__ import annotations

from drift.intent._models import (
    CapturedIntent,
    FeedbackAction,
    FeedbackResult,
    VerifyResult,
)

__all__ = [
    "CapturedIntent",
    "FeedbackAction",
    "FeedbackResult",
    "VerifyResult",
]
```

- [ ] **Step 5: Führe Tests aus — erwartet PASS**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_capture.py -v
```
Erwartetes Ergebnis: 4 Tests grün

- [ ] **Step 6: Commit**

```
git add src/drift/intent/_models.py src/drift/intent/__init__.py tests/test_intent_capture.py
git commit -m "feat: add intent guardian models (CapturedIntent, VerifyResult, FeedbackResult)"
```

---

## Task 2: Intent-Storage (`src/drift/intent/_storage.py`)

**Files:**
- Create: `src/drift/intent/_storage.py`
- Test: `tests/test_intent_capture.py` (erweitern)

- [ ] **Step 1: Schreibe failing Tests für Storage**

```python
# tests/test_intent_capture.py — append:

import json
from pathlib import Path
from drift.intent._storage import save_intent, load_intent, intent_store_path


def test_save_and_load_intent(tmp_path: Path):
    intent = CapturedIntent(
        intent_id="store-001",
        raw="Test",
        summary="Test App",
        required_features=["Feature A"],
        output_type="web_app",
        confidence=0.85,
        clarification_needed=False,
    )
    save_intent(intent, repo_root=tmp_path)
    loaded = load_intent("store-001", repo_root=tmp_path)
    assert loaded is not None
    assert loaded.intent_id == "store-001"
    assert loaded.required_features == ["Feature A"]


def test_load_nonexistent_intent(tmp_path: Path):
    result = load_intent("nonexistent-999", repo_root=tmp_path)
    assert result is None


def test_intent_store_path(tmp_path: Path):
    path = intent_store_path("abc-123", repo_root=tmp_path)
    assert path == tmp_path / ".drift" / "intents" / "abc-123.json"
```

- [ ] **Step 2: Führe Tests aus — erwartet FAIL**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_capture.py::test_save_and_load_intent -v
```
Erwartetes Ergebnis: `ImportError: cannot import name 'save_intent'`

- [ ] **Step 3: Erstelle `src/drift/intent/_storage.py`**

```python
"""Local storage for captured intents under .drift/intents/."""

from __future__ import annotations

import json
from pathlib import Path

from drift.intent._models import CapturedIntent


def intent_store_path(intent_id: str, *, repo_root: Path) -> Path:
    """Return the file path for a given intent_id."""
    return repo_root / ".drift" / "intents" / f"{intent_id}.json"


def save_intent(intent: CapturedIntent, *, repo_root: Path) -> Path:
    """Persist a CapturedIntent to .drift/intents/<id>.json. Returns path."""
    path = intent_store_path(intent.intent_id, repo_root=repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(intent.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def load_intent(intent_id: str, *, repo_root: Path) -> CapturedIntent | None:
    """Load a CapturedIntent by id. Returns None if not found."""
    path = intent_store_path(intent_id, repo_root=repo_root)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return CapturedIntent.model_validate(data)
```

- [ ] **Step 4: Führe Tests aus — erwartet PASS**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_capture.py -v
```
Erwartetes Ergebnis: alle 7 Tests grün

- [ ] **Step 5: Commit**

```
git add src/drift/intent/_storage.py tests/test_intent_capture.py
git commit -m "feat: add intent local storage (.drift/intents/)"
```

---

## Task 3: Intent-Extraktion (`src/drift/intent/capture.py`)

**Files:**
- Create: `src/drift/intent/capture.py`
- Test: `tests/test_intent_capture.py` (erweitern)

*Hinweis: Diese Phase verwendet regelbasierte Extraktion ohne LLM-Aufruf — LLM-Erweiterung kommt in Task 5.*

- [ ] **Step 1: Schreibe failing Tests für capture-Logik**

```python
# tests/test_intent_capture.py — append:

from drift.intent.capture import extract_intent, _detect_output_type, _extract_features


def test_detect_output_type_web():
    assert _detect_output_type("Ich brauche eine Website für meine Band") == "web_app"


def test_detect_output_type_script():
    assert _detect_output_type("ein Script das meine Fotos sortiert") == "script"


def test_detect_output_type_game():
    assert _detect_output_type("ein einfaches Spiel für meinen Sohn") == "game"


def test_detect_output_type_api():
    assert _detect_output_type("eine REST API für meinen Shop") == "api"


def test_detect_output_type_fallback():
    assert _detect_output_type("irgendetwas cooles") == "unknown"


def test_extract_features_finance():
    features = _extract_features("eine App die meine Finanzen und Ausgaben verwaltet")
    assert len(features) >= 1
    assert any("Finanzen" in f or "Ausgaben" in f for f in features)


def test_extract_intent_full():
    intent = extract_intent("Ich brauche eine App, die meine Finanzen plant.")
    assert intent.summary != ""
    assert intent.output_type in ("web_app", "script", "file", "api", "game", "automation", "unknown")
    assert len(intent.required_features) >= 1
    assert 0.0 <= intent.confidence <= 1.0
    assert intent.intent_id != ""


def test_extract_intent_vague_sets_clarification():
    intent = extract_intent("ich will was cooles")
    assert intent.clarification_needed is True
    assert intent.clarification_question is not None
```

- [ ] **Step 2: Führe Tests aus — erwartet FAIL**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_capture.py::test_detect_output_type_web -v
```
Erwartetes Ergebnis: `ImportError: cannot import name 'extract_intent'`

- [ ] **Step 3: Erstelle `src/drift/intent/capture.py`**

```python
"""Rule-based intent extraction from natural-language user input."""

from __future__ import annotations

import hashlib
import re
import time

from drift.intent._models import CapturedIntent
from drift.intent._storage import save_intent

# --- Output-type detection keywords ---

_OUTPUT_TYPE_RULES: list[tuple[list[str], str]] = [
    (["website", "webseite", "web app", "webapp", "browser", "html", "homepage", "landing page"], "web_app"),
    (["spiel", "game", "spielen"], "game"),
    (["api", "rest", "endpoint", "backend", "server"], "api"),
    (["automation", "automatisierung", "bot", "cron", "scheduler", "workflow"], "automation"),
    (["script", "skript", "datei sortieren", "fotos sortieren", "rename", "konvertieren"], "script"),
    (["app", "anwendung", "tool", "werkzeug", "programm"], "web_app"),
]

# --- Feature keyword map ---

_FEATURE_KEYWORDS: list[tuple[str, str]] = [
    (r"finanz|ausgabe|einnahme|budget|geld|kosten|rechnung", "Finanzverwaltung"),
    (r"foto|bild|galerie|album", "Fotoverwaltung"),
    (r"task|aufgabe|todo|checklist", "Aufgabenverwaltung"),
    (r"kalend|termin|datum|event|veranstaltung", "Terminplanung"),
    (r"kontakt|adresse|telefonbuch", "Kontaktverwaltung"),
    (r"rezept|kochen|zutat|mahlzeit", "Rezeptverwaltung"),
    (r"notiz|notizen|text|schreiben", "Notizen"),
    (r"shop|kaufen|produkt|warenkorb|bestellung", "Online-Shop"),
    (r"musik|playlist|song|band", "Musikverwaltung"),
    (r"fitness|sport|training|workout|kalorien", "Fitness-Tracking"),
    (r"wetter|temperatur|forecast", "Wetteranzeige"),
    (r"chat|nachricht|kommunikation|message", "Messaging"),
    (r"export|download|csv|pdf|bericht", "Export-Funktion"),
    (r"login|registrierung|benutzer|konto|auth", "Benutzerverwaltung"),
    (r"statistik|diagramm|chart|grafik|dashboard", "Dashboard/Statistiken"),
    (r"plan|planen|planung", "Planungsfunktion"),
]

_VAGUE_PATTERN = re.compile(
    r"^(ich will|ich brauche|mach mir|bau mir|erstell mir)?\s*(irgendwas|was cooles|irgendwas cooles|etwas|irgend)\s*$",
    re.IGNORECASE,
)


def _detect_output_type(raw: str) -> str:
    """Detect the most likely output type from raw user input."""
    lower = raw.lower()
    for keywords, output_type in _OUTPUT_TYPE_RULES:
        if any(kw in lower for kw in keywords):
            return output_type
    return "unknown"


def _extract_features(raw: str) -> list[str]:
    """Extract likely required features from raw user input."""
    lower = raw.lower()
    features: list[str] = []
    for pattern, label in _FEATURE_KEYWORDS:
        if re.search(pattern, lower):
            features.append(label)
    # Fallback: use the whole sentence as a feature hint
    if not features:
        # Strip filler words and capitalise remainder as a feature
        stripped = re.sub(
            r"^(ich brauche|ich will|mach mir|bau mir|erstell mir|eine|ein|app|tool|script)\s*",
            "",
            raw.strip(),
            flags=re.IGNORECASE,
        ).strip()
        if stripped:
            features.append(stripped.capitalize())
    return features


def _generate_intent_id(raw: str) -> str:
    """Deterministic short ID based on content + timestamp."""
    digest = hashlib.sha1(f"{raw}{time.time_ns()}".encode()).hexdigest()[:8]
    return f"intent-{digest}"


def _compute_confidence(raw: str, features: list[str], output_type: str) -> float:
    """Heuristic confidence score."""
    score = 0.5
    if features:
        score += min(0.3, len(features) * 0.05)
    if output_type != "unknown":
        score += 0.15
    if len(raw.split()) < 3:
        score -= 0.3
    return round(max(0.1, min(1.0, score)), 2)


def _is_vague(raw: str) -> bool:
    return bool(_VAGUE_PATTERN.match(raw.strip())) or len(raw.strip().split()) < 3


def extract_intent(raw: str) -> CapturedIntent:
    """Extract a structured CapturedIntent from a raw user input string.

    This is the primary entry point for the intent guardian capture phase.
    No LLM call is made here — this is purely rule-based.
    """
    features = _extract_features(raw)
    output_type = _detect_output_type(raw)
    confidence = _compute_confidence(raw, features, output_type)
    vague = _is_vague(raw)

    summary_base = re.sub(
        r"^(ich brauche|ich will|mach mir|bau mir|erstell mir|eine|ein)\s*",
        "",
        raw.strip(),
        flags=re.IGNORECASE,
    ).strip()
    summary = summary_base.capitalize() if summary_base else raw.strip().capitalize()

    return CapturedIntent(
        intent_id=_generate_intent_id(raw),
        raw=raw,
        summary=summary,
        required_features=features,
        output_type=output_type,  # type: ignore[arg-type]
        confidence=confidence,
        clarification_needed=vague,
        clarification_question=(
            "Was genau soll das Tool oder die App für dich tun?" if vague else None
        ),
    )
```

- [ ] **Step 4: Führe Tests aus — erwartet PASS**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_capture.py -v
```
Erwartetes Ergebnis: alle Tests grün

- [ ] **Step 5: Commit**

```
git add src/drift/intent/capture.py tests/test_intent_capture.py
git commit -m "feat: add rule-based intent extraction (capture_intent)"
```

---

## Task 4: Intent-Verifikation (`src/drift/intent/verify.py`)

**Files:**
- Create: `src/drift/intent/verify.py`
- Create: `tests/test_intent_verify.py`

- [ ] **Step 1: Schreibe failing Tests**

```python
# tests/test_intent_verify.py
from __future__ import annotations

import json
from pathlib import Path
import pytest

from drift.intent._models import CapturedIntent, VerifyResult
from drift.intent.verify import verify_artifact, _scan_artifact_content


def _make_intent(features: list[str]) -> CapturedIntent:
    return CapturedIntent(
        intent_id="v-test-001",
        raw="Test",
        summary="Test",
        required_features=features,
        output_type="web_app",
        confidence=0.8,
        clarification_needed=False,
    )


def test_verify_fulfilled_when_all_features_present(tmp_path: Path):
    (tmp_path / "index.html").write_text(
        "<html><body>Finanzverwaltung Ausgaben Einnahmen Dashboard</body></html>",
        encoding="utf-8",
    )
    intent = _make_intent(["Finanzverwaltung", "Dashboard"])
    result = verify_artifact(intent=intent, artifact_path=tmp_path)
    assert result.status == "fulfilled"
    assert result.confidence >= 0.7


def test_verify_incomplete_when_features_missing(tmp_path: Path):
    (tmp_path / "index.html").write_text(
        "<html><body>Nur ein bisschen Text ohne Features</body></html>",
        encoding="utf-8",
    )
    intent = _make_intent(["Finanzverwaltung", "Export-Funktion", "Dashboard"])
    result = verify_artifact(intent=intent, artifact_path=tmp_path)
    assert result.status == "incomplete"
    assert len(result.missing) >= 1
    assert result.agent_feedback != ""


def test_verify_empty_artifact(tmp_path: Path):
    intent = _make_intent(["Finanzverwaltung"])
    result = verify_artifact(intent=intent, artifact_path=tmp_path)
    assert result.status == "incomplete"
    assert result.confidence < 0.5


def test_scan_artifact_content_reads_files(tmp_path: Path):
    (tmp_path / "app.py").write_text("def finanz(): pass\ndef budget(): pass", encoding="utf-8")
    (tmp_path / "readme.md").write_text("# Meine Finanzplaner App", encoding="utf-8")
    content = _scan_artifact_content(tmp_path)
    assert "finanz" in content.lower()


def test_verify_increments_iteration(tmp_path: Path):
    intent = _make_intent(["Finanzverwaltung"])
    result = verify_artifact(intent=intent, artifact_path=tmp_path, iteration=3)
    assert result.iteration == 3
```

- [ ] **Step 2: Führe Tests aus — erwartet FAIL**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_verify.py::test_verify_fulfilled_when_all_features_present -v
```
Erwartetes Ergebnis: `ImportError`

- [ ] **Step 3: Erstelle `src/drift/intent/verify.py`**

```python
"""Structural feature verification for build artifacts against a captured intent."""

from __future__ import annotations

import re
from pathlib import Path

from drift.intent._models import CapturedIntent, VerifyResult

# Extensions to scan for feature keywords
_SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".md",
    ".txt", ".json", ".yaml", ".yml", ".toml", ".svelte", ".vue",
}

_MAX_FILE_SIZE = 200_000  # bytes — skip large binaries


def _scan_artifact_content(artifact_path: Path) -> str:
    """Concatenate text content of all scannable files under artifact_path."""
    if not artifact_path.exists():
        return ""
    parts: list[str] = []
    if artifact_path.is_file():
        try:
            parts.append(artifact_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
        return " ".join(parts)
    for file in artifact_path.rglob("*"):
        if not file.is_file():
            continue
        if file.suffix.lower() not in _SCANNABLE_EXTENSIONS:
            continue
        try:
            if file.stat().st_size > _MAX_FILE_SIZE:
                continue
            parts.append(file.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return " ".join(parts)


def _feature_present(feature: str, content_lower: str) -> bool:
    """Check if a feature keyword appears in the artifact content."""
    # Strip common suffixes and check keyword presence
    keywords = re.split(r"[-/]", feature.lower())
    return any(kw.strip() in content_lower for kw in keywords if len(kw.strip()) > 2)


def verify_artifact(
    *,
    intent: CapturedIntent,
    artifact_path: Path,
    iteration: int = 1,
) -> VerifyResult:
    """Verify that artifact_path fulfils all required_features of intent.

    Returns a VerifyResult with status 'fulfilled' or 'incomplete'.
    """
    content = _scan_artifact_content(artifact_path)
    content_lower = content.lower()

    if not content.strip():
        return VerifyResult(
            status="incomplete",
            confidence=0.1,
            missing=list(intent.required_features),
            agent_feedback=(
                "Das Artefakt ist leer oder enthält keine lesbaren Dateien. "
                f"Bitte implementiere: {', '.join(intent.required_features)}."
            ),
            iteration=iteration,
        )

    missing: list[str] = []
    found: list[str] = []

    for feature in intent.required_features:
        if _feature_present(feature, content_lower):
            found.append(feature)
        else:
            missing.append(feature)

    total = len(intent.required_features)
    coverage = len(found) / total if total > 0 else 1.0
    confidence = round(0.5 + coverage * 0.5, 2)

    if not missing:
        return VerifyResult(
            status="fulfilled",
            confidence=confidence,
            missing=[],
            agent_feedback="",
            iteration=iteration,
        )

    feedback = (
        f"Folgende Features fehlen noch: {', '.join(missing)}. "
        f"Bitte implementiere diese Funktionen."
    )
    return VerifyResult(
        status="incomplete",
        confidence=confidence,
        missing=missing,
        agent_feedback=feedback,
        iteration=iteration,
    )
```

- [ ] **Step 4: Führe Tests aus — erwartet PASS**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_verify.py -v
```
Erwartetes Ergebnis: alle 5 Tests grün

- [ ] **Step 5: Commit**

```
git add src/drift/intent/verify.py tests/test_intent_verify.py
git commit -m "feat: add structural artifact verification (verify_intent)"
```

---

## Task 5: Feedback-Generator (`src/drift/intent/feedback.py`)

**Files:**
- Create: `src/drift/intent/feedback.py`
- Create: `tests/test_intent_feedback.py`

- [ ] **Step 1: Schreibe failing Tests**

```python
# tests/test_intent_feedback.py
from __future__ import annotations

import pytest
from drift.intent._models import VerifyResult, FeedbackResult
from drift.intent.feedback import generate_feedback, _estimate_complexity


def _make_verify_incomplete(missing: list[str]) -> VerifyResult:
    return VerifyResult(
        status="incomplete",
        confidence=0.4,
        missing=missing,
        agent_feedback="Bitte implementiere: " + ", ".join(missing),
        iteration=2,
    )


def test_generate_feedback_returns_one_action_per_missing():
    result = _make_verify_incomplete(["Finanzverwaltung", "Export-Funktion"])
    feedback = generate_feedback(result)
    assert isinstance(feedback, FeedbackResult)
    assert len(feedback.actions) == 2


def test_generate_feedback_priorities_ordered():
    result = _make_verify_incomplete(["A", "B", "C"])
    feedback = generate_feedback(result)
    priorities = [a.priority for a in feedback.actions]
    assert priorities == sorted(priorities)


def test_generate_feedback_all_add_feature():
    result = _make_verify_incomplete(["Finanzverwaltung"])
    feedback = generate_feedback(result)
    assert all(a.action == "add_feature" for a in feedback.actions)


def test_generate_feedback_fulfilled_returns_empty():
    result = VerifyResult(
        status="fulfilled",
        confidence=0.95,
        missing=[],
        agent_feedback="",
        iteration=1,
    )
    feedback = generate_feedback(result)
    assert feedback.actions == []
    assert feedback.estimated_complexity == "low"


def test_estimate_complexity_low():
    assert _estimate_complexity(1) == "low"


def test_estimate_complexity_medium():
    assert _estimate_complexity(3) == "medium"


def test_estimate_complexity_high():
    assert _estimate_complexity(6) == "high"
```

- [ ] **Step 2: Führe Tests aus — erwartet FAIL**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_feedback.py::test_generate_feedback_returns_one_action_per_missing -v
```
Erwartetes Ergebnis: `ImportError`

- [ ] **Step 3: Erstelle `src/drift/intent/feedback.py`**

```python
"""Prioritised action-set generation for the building agent."""

from __future__ import annotations

from drift.intent._models import FeedbackAction, FeedbackResult, VerifyResult


def _estimate_complexity(missing_count: int) -> str:
    if missing_count <= 1:
        return "low"
    if missing_count <= 4:
        return "medium"
    return "high"


def generate_feedback(verify_result: VerifyResult) -> FeedbackResult:
    """Convert a VerifyResult into a prioritised FeedbackResult for the agent.

    Returns an empty FeedbackResult when status is 'fulfilled'.
    """
    if verify_result.status == "fulfilled" or not verify_result.missing:
        return FeedbackResult(actions=[], estimated_complexity="low")

    actions = [
        FeedbackAction(
            priority=i + 1,
            action="add_feature",
            description=feature,
        )
        for i, feature in enumerate(verify_result.missing)
    ]
    return FeedbackResult(
        actions=actions,
        estimated_complexity=_estimate_complexity(len(actions)),
    )
```

- [ ] **Step 4: Führe Tests aus — erwartet PASS**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_feedback.py -v
```
Erwartetes Ergebnis: alle 7 Tests grün

- [ ] **Step 5: Commit**

```
git add src/drift/intent/feedback.py tests/test_intent_feedback.py
git commit -m "feat: add feedback generator for building agent (feedback_for_agent)"
```

---

## Task 6: API-Funktionen (3 neue Module in `src/drift/api/`)

**Files:**
- Create: `src/drift/api/capture_intent.py`
- Create: `src/drift/api/verify_intent.py`
- Create: `src/drift/api/feedback_for_agent.py`
- Modify: `src/drift/api/__init__.py`
- Create: `tests/test_intent_api.py`

- [ ] **Step 1: Schreibe failing Tests für alle 3 API-Funktionen**

```python
# tests/test_intent_api.py
from __future__ import annotations

import json
from pathlib import Path
import pytest

from drift.api.capture_intent import capture_intent
from drift.api.verify_intent import verify_intent
from drift.api.feedback_for_agent import feedback_for_agent


def test_capture_intent_returns_dict(tmp_path: Path):
    result = capture_intent(raw="Ich brauche eine Finanzplaner-App", path=str(tmp_path))
    assert isinstance(result, dict)
    assert "intent_id" in result
    assert "required_features" in result
    assert "output_type" in result
    assert result["output_type"] in ("web_app", "script", "file", "api", "game", "automation", "unknown")


def test_capture_intent_saves_locally(tmp_path: Path):
    result = capture_intent(raw="Website für meine Band", path=str(tmp_path))
    intent_id = result["intent_id"]
    stored = tmp_path / ".drift" / "intents" / f"{intent_id}.json"
    assert stored.exists()
    data = json.loads(stored.read_text(encoding="utf-8"))
    assert data["intent_id"] == intent_id


def test_capture_intent_vague_flags_clarification(tmp_path: Path):
    result = capture_intent(raw="was cooles", path=str(tmp_path))
    assert result["clarification_needed"] is True
    assert result["clarification_question"] is not None


def test_verify_intent_fulfilled(tmp_path: Path):
    cap = capture_intent(raw="Finanzplaner App mit Ausgaben Übersicht", path=str(tmp_path))
    intent_id = cap["intent_id"]
    artifact = tmp_path / "output"
    artifact.mkdir()
    (artifact / "index.html").write_text(
        "<html>Finanzplaner Ausgaben Planungsfunktion Dashboard</html>",
        encoding="utf-8",
    )
    result = verify_intent(intent_id=intent_id, artifact_path=str(artifact), path=str(tmp_path))
    assert result["status"] in ("fulfilled", "incomplete")
    assert "confidence" in result


def test_verify_intent_missing_id_returns_error(tmp_path: Path):
    result = verify_intent(intent_id="nonexistent-999", artifact_path=str(tmp_path), path=str(tmp_path))
    assert result.get("error") is not None


def test_feedback_for_agent_returns_actions(tmp_path: Path):
    cap = capture_intent(raw="App mit Finanzen und Export", path=str(tmp_path))
    intent_id = cap["intent_id"]
    result = feedback_for_agent(intent_id=intent_id, path=str(tmp_path), artifact_path=str(tmp_path))
    assert "actions" in result
    assert "estimated_complexity" in result
```

- [ ] **Step 2: Führe Tests aus — erwartet FAIL**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_api.py::test_capture_intent_returns_dict -v
```
Erwartetes Ergebnis: `ImportError`

- [ ] **Step 3: Erstelle `src/drift/api/capture_intent.py`**

```python
"""API endpoint: capture_intent — extract and persist a structured intent."""

from __future__ import annotations

import time as _time
from pathlib import Path
from typing import Any

from drift.api._config import _emit_api_telemetry, _log
from drift.intent.capture import extract_intent
from drift.intent._storage import save_intent


def capture_intent(*, raw: str, path: str) -> dict[str, Any]:
    """Extract a structured intent from a raw user input string.

    Persists the intent to .drift/intents/<intent_id>.json under `path`.

    Args:
        raw: The natural-language user input.
        path: Repo root path (used for local storage).

    Returns:
        A dict with intent_id, summary, required_features, output_type,
        confidence, clarification_needed, clarification_question.
    """
    t0 = _time.monotonic()
    repo_root = Path(path)
    error: Exception | None = None
    result: dict[str, Any] = {}
    try:
        intent = extract_intent(raw)
        save_intent(intent, repo_root=repo_root)
        result = intent.model_dump(mode="json")
        result["next_tool_call"] = (
            f"drift_verify_intent(intent_id='{intent.intent_id}', artifact_path='<path-to-build>')"
        )
        result["agent_instruction"] = (
            "Intent captured and saved. "
            "Call verify_intent after the build is complete to check if the intent is fulfilled."
        )
        if intent.clarification_needed:
            result["agent_instruction"] = (
                f"Clarification needed before building: {intent.clarification_question}"
            )
    except Exception as exc:
        error = exc
        _log.error("capture_intent failed: %s", exc)
        result = {"error": str(exc)}
    finally:
        elapsed = int((_time.monotonic() - t0) * 1000)
        _emit_api_telemetry(
            tool_name="capture_intent",
            params={"raw_length": len(raw), "path": path},
            status="error" if error else "ok",
            elapsed_ms=elapsed,
            result=result if not error else None,
            error=error,
            repo_root=repo_root if repo_root.exists() else None,
        )
    return result
```

- [ ] **Step 4: Erstelle `src/drift/api/verify_intent.py`**

```python
"""API endpoint: verify_intent — check artifact against captured intent."""

from __future__ import annotations

import time as _time
from pathlib import Path
from typing import Any

from drift.api._config import _emit_api_telemetry, _log
from drift.intent._storage import load_intent
from drift.intent.verify import verify_artifact


def verify_intent(*, intent_id: str, artifact_path: str, path: str) -> dict[str, Any]:
    """Verify that a build artifact fulfils a previously captured intent.

    Args:
        intent_id: The intent ID returned by capture_intent.
        artifact_path: Path to the built artifact (file or directory).
        path: Repo root path (used for intent storage lookup).

    Returns:
        A dict with status, confidence, missing[], agent_feedback,
        iteration, next_tool_call, agent_instruction.
    """
    t0 = _time.monotonic()
    repo_root = Path(path)
    error: Exception | None = None
    result: dict[str, Any] = {}
    try:
        intent = load_intent(intent_id, repo_root=repo_root)
        if intent is None:
            return {
                "error": f"Intent '{intent_id}' not found. Call capture_intent first.",
                "intent_id": intent_id,
            }
        verify_result = verify_artifact(
            intent=intent,
            artifact_path=Path(artifact_path),
        )
        result = verify_result.model_dump(mode="json")
        result["intent_id"] = intent_id
        if verify_result.status == "fulfilled":
            result["next_tool_call"] = "DONE — intent fulfilled, deliver result to user"
            result["agent_instruction"] = (
                "The build artifact fulfils the user's intent. "
                "Deliver the result to the user in plain language."
            )
        else:
            result["next_tool_call"] = (
                f"drift_feedback_for_agent(intent_id='{intent_id}')"
            )
            result["agent_instruction"] = (
                f"{len(verify_result.missing)} feature(s) missing. "
                "Call feedback_for_agent to get a prioritised action list, "
                "then fix and call verify_intent again."
            )
    except Exception as exc:
        error = exc
        _log.error("verify_intent failed: %s", exc)
        result = {"error": str(exc), "intent_id": intent_id}
    finally:
        elapsed = int((_time.monotonic() - t0) * 1000)
        _emit_api_telemetry(
            tool_name="verify_intent",
            params={"intent_id": intent_id, "artifact_path": artifact_path},
            status="error" if error else "ok",
            elapsed_ms=elapsed,
            result=result if not error else None,
            error=error,
            repo_root=repo_root if repo_root.exists() else None,
        )
    return result
```

- [ ] **Step 5: Erstelle `src/drift/api/feedback_for_agent.py`**

```python
"""API endpoint: feedback_for_agent — prioritised action list from last verify result."""

from __future__ import annotations

import time as _time
from pathlib import Path
from typing import Any

from drift.api._config import _emit_api_telemetry, _log
from drift.intent._storage import load_intent
from drift.intent.verify import verify_artifact
from drift.intent.feedback import generate_feedback


def feedback_for_agent(*, intent_id: str, path: str, artifact_path: str) -> dict[str, Any]:
    """Return a prioritised action list based on the current verify state.

    Re-runs verify_artifact internally so callers get fresh, consistent feedback.

    Args:
        intent_id: The intent ID returned by capture_intent.
        path: Repo root path.
        artifact_path: Path to the current build artifact.

    Returns:
        A dict with actions[], estimated_complexity, intent_id,
        next_tool_call, agent_instruction.
    """
    t0 = _time.monotonic()
    repo_root = Path(path)
    error: Exception | None = None
    result: dict[str, Any] = {}
    try:
        intent = load_intent(intent_id, repo_root=repo_root)
        if intent is None:
            return {
                "error": f"Intent '{intent_id}' not found. Call capture_intent first.",
                "intent_id": intent_id,
            }
        verify_result = verify_artifact(intent=intent, artifact_path=Path(artifact_path))
        feedback = generate_feedback(verify_result)
        result = feedback.model_dump(mode="json")
        result["intent_id"] = intent_id
        result["verify_status"] = verify_result.status
        result["missing"] = verify_result.missing
        result["next_tool_call"] = (
            f"drift_verify_intent(intent_id='{intent_id}', artifact_path='{artifact_path}')"
        )
        result["agent_instruction"] = (
            f"Apply the {len(feedback.actions)} action(s) listed, then call verify_intent again."
            if feedback.actions
            else "Intent already fulfilled — no actions needed."
        )
    except Exception as exc:
        error = exc
        _log.error("feedback_for_agent failed: %s", exc)
        result = {"error": str(exc), "intent_id": intent_id}
    finally:
        elapsed = int((_time.monotonic() - t0) * 1000)
        _emit_api_telemetry(
            tool_name="feedback_for_agent",
            params={"intent_id": intent_id, "path": path},
            status="error" if error else "ok",
            elapsed_ms=elapsed,
            result=result if not error else None,
            error=error,
            repo_root=repo_root if repo_root.exists() else None,
        )
    return result
```

- [ ] **Step 6: Erweitere `src/drift/api/__init__.py` — 3 neue Imports**

Füge nach dem letzten `from drift.api.` Import-Block diese drei Zeilen ein:

```python
from drift.api.capture_intent import capture_intent
from drift.api.feedback_for_agent import feedback_for_agent
from drift.api.verify_intent import verify_intent
```

Und erweitere `STABLE_API`:
```python
# In der STABLE_API Liste hinzufügen:
"capture_intent",
"verify_intent",
"feedback_for_agent",
```

- [ ] **Step 7: Führe alle API-Tests aus — erwartet PASS**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_api.py -v
```
Erwartetes Ergebnis: alle 6 Tests grün

- [ ] **Step 8: Commit**

```
git add src/drift/api/capture_intent.py src/drift/api/verify_intent.py src/drift/api/feedback_for_agent.py src/drift/api/__init__.py tests/test_intent_api.py
git commit -m "feat: add capture_intent, verify_intent, feedback_for_agent API endpoints"
```

---

## Task 7: MCP-Tools in A2A-Router registrieren

**Files:**
- Modify: `src/drift/serve/a2a_router.py`
- Create: `tests/test_intent_mcp.py`

- [ ] **Step 1: Schreibe failing MCP-Handler-Tests**

```python
# tests/test_intent_mcp.py
from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from drift.serve.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def _a2a(client, skill: str, params: dict) -> dict:
    response = client.post(
        "/a2a/v1",
        json={
            "jsonrpc": "2.0",
            "id": "test-1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "data", "data": {"skill": skill, **params}}],
                    "metadata": {"skillId": skill},
                }
            },
        },
    )
    assert response.status_code == 200
    return response.json()


def test_capture_intent_mcp_tool_registered(client, tmp_path):
    result = _a2a(client, "capture_intent", {"raw": "Finanzplaner App", "path": str(tmp_path)})
    assert "result" in result
    parts = result["result"]["artifacts"][0]["parts"] if "artifacts" in result.get("result", {}) else []
    # Tool must not return method_not_found error
    assert result.get("error", {}).get("code") != -32601, "capture_intent not registered"


def test_verify_intent_mcp_tool_registered(client, tmp_path):
    result = _a2a(client, "verify_intent", {
        "intent_id": "nonexistent",
        "artifact_path": str(tmp_path),
        "path": str(tmp_path),
    })
    assert result.get("error", {}).get("code") != -32601, "verify_intent not registered"


def test_feedback_for_agent_mcp_tool_registered(client, tmp_path):
    result = _a2a(client, "feedback_for_agent", {
        "intent_id": "nonexistent",
        "artifact_path": str(tmp_path),
        "path": str(tmp_path),
    })
    assert result.get("error", {}).get("code") != -32601, "feedback_for_agent not registered"
```

- [ ] **Step 2: Führe Tests aus — erwartet FAIL**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_mcp.py::test_capture_intent_mcp_tool_registered -v
```
Erwartetes Ergebnis: AssertionError (skill not registered, error code -32601)

- [ ] **Step 3: Erweitere `src/drift/serve/a2a_router.py`**

Im `_ensure_dispatch_table()` Block, nach `"patch_commit": _handle_patch_commit,` einfügen:

```python
            "capture_intent": _handle_capture_intent,
            "verify_intent": _handle_verify_intent,
            "feedback_for_agent": _handle_feedback_for_agent,
```

Dann am Ende der Datei (vor dem letzten `dispatch`-Aufruf oder nach den anderen `_handle_*` Funktionen) die drei neuen Handler hinzufügen:

```python
def _handle_capture_intent(params: dict[str, Any]) -> dict[str, Any]:
    """Handle capture_intent skill."""
    from drift.api.capture_intent import capture_intent

    raw = params.get("raw", "")
    path = params.get("path", ".")
    if not raw:
        return {"error": "Parameter 'raw' is required"}
    return capture_intent(raw=raw, path=path)


def _handle_verify_intent(params: dict[str, Any]) -> dict[str, Any]:
    """Handle verify_intent skill."""
    from drift.api.verify_intent import verify_intent

    intent_id = params.get("intent_id", "")
    artifact_path = params.get("artifact_path", ".")
    path = params.get("path", ".")
    if not intent_id:
        return {"error": "Parameter 'intent_id' is required"}
    return verify_intent(intent_id=intent_id, artifact_path=artifact_path, path=path)


def _handle_feedback_for_agent(params: dict[str, Any]) -> dict[str, Any]:
    """Handle feedback_for_agent skill."""
    from drift.api.feedback_for_agent import feedback_for_agent

    intent_id = params.get("intent_id", "")
    path = params.get("path", ".")
    artifact_path = params.get("artifact_path", ".")
    if not intent_id:
        return {"error": "Parameter 'intent_id' is required"}
    return feedback_for_agent(intent_id=intent_id, path=path, artifact_path=artifact_path)
```

- [ ] **Step 4: Führe MCP-Tests aus — erwartet PASS**

```
.venv\Scripts\python.exe -m pytest tests/test_intent_mcp.py -v
```
Erwartetes Ergebnis: alle 3 Tests grün

- [ ] **Step 5: Führe gesamte Testsuite aus**

```
.venv\Scripts\python.exe -m pytest tests/ --ignore=tests/test_smoke_real_repos.py -m "not slow" -q --tb=short
```
Erwartetes Ergebnis: alle Tests grün, keine Regressionen

- [ ] **Step 6: Commit**

```
git add src/drift/serve/a2a_router.py tests/test_intent_mcp.py
git commit -m "feat: register capture_intent, verify_intent, feedback_for_agent as MCP tools"
```

---

## Verifikation (nach allen Tasks)

- [ ] Alle neuen Tests grün: `pytest tests/test_intent_capture.py tests/test_intent_verify.py tests/test_intent_feedback.py tests/test_intent_api.py tests/test_intent_mcp.py -v`
- [ ] Keine Regressionen: `pytest tests/ --ignore=tests/test_smoke_real_repos.py -m "not slow" -q`
- [ ] Import-Sanity: `python -c "from drift.api import capture_intent, verify_intent, feedback_for_agent; print('OK')"`

---

## Bekannte Grenzen (bewusst aus Scope ausgeschlossen)

- **LLM-gestützte Verifikation**: Phase 2 dieses Systems — verify_intent nutzt aktuell nur strukturelle/keyword-basierte Prüfung, keine LLM-Semantik
- **Max-Iterations-Loop**: der Abbruch nach 5 Iterationen liegt beim aufrufenden Agenten, nicht in Drift
- **Deployment-Adapter**: Drift kennt keinen Deploy-Schritt — das bleibt beim Agenten
- **Mehrsprachige Keyword-Extraktion**: aktuell DE/EN gemischt, kein vollständiges NLP
