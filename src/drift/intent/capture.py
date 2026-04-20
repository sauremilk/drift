"""Intent extraction — keyword-based, no LLM required."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from drift.intent._models import CapturedIntent

# ── Output-type detection ─────────────────────────────────────────────────────
_WEB_APP_KEYWORDS = [
    "website", "webapp", "web app", "web-app", "dashboard", "frontend",
    "landing page", "html", "css", "react", "vue", "svelte", "next.js",
    "django", "flask", "fastapi", "web",
]
_SCRIPT_KEYWORDS = [
    "script", "automate", "batch", "cli", "command line", "tool",
    "utility", "scheduled", "cron",
]
_GAME_KEYWORDS = [
    "game", "spiel", "spielen", "level", "score", "player", "pygame",
    "phaser", "unity",
]
_API_KEYWORDS = [
    "api", "rest", "endpoint", "microservice", "backend", "graphql",
    "webhook", "server",
]
_AUTOMATION_KEYWORDS = [
    "automation", "automatisierung", "bot", "scraper", "crawler",
    "rpa", "workflow",
]

_VAGUE_PATTERNS = [
    "something", "a thing", "whatever", "stuff", "etwas", "irgendwas",
]


def _detect_output_type(raw: str) -> str:
    lower = raw.lower()
    if any(kw in lower for kw in _WEB_APP_KEYWORDS):
        return "web_app"
    if any(kw in lower for kw in _SCRIPT_KEYWORDS):
        return "script"
    if any(kw in lower for kw in _GAME_KEYWORDS):
        return "game"
    if any(kw in lower for kw in _API_KEYWORDS):
        return "api"
    if any(kw in lower for kw in _AUTOMATION_KEYWORDS):
        return "automation"
    return "unknown"


def _extract_features(raw: str) -> list[str]:
    """Extract noun-phrase feature keywords from user input."""
    import re

    features: list[str] = []
    # Quoted phrases
    features += re.findall(r'"([^"]+)"', raw)
    features += re.findall(r"'([^']+)'", raw)
    # German compound capitalisation hints
    features += re.findall(
        r"\b[A-ZÄÖÜ][a-zäöüß]{3,}(?:[A-ZÄÖÜ][a-zäöüß]{2,})*\b", raw
    )
    # Hyphenated feature terms
    features += re.findall(r"\b\w{3,}-\w{3,}(?:-\w{2,})?\b", raw)
    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for f in features:
        if f not in seen and len(f) > 3:
            seen.add(f)
            result.append(f)
    if not result:
        words = [w.strip(".,!?") for w in raw.split() if len(w) > 4]
        result = words[:5]
    return result[:10]


def _generate_intent_id(raw: str) -> str:
    digest = hashlib.sha256(f"{raw}{time.time()}".encode()).hexdigest()[:8]
    return f"intent-{digest}"


def _is_vague(raw: str) -> bool:
    lower = raw.lower()
    if len(raw.split()) <= 3:
        return True
    return any(pat in lower for pat in _VAGUE_PATTERNS)


def _compute_confidence(
    features: list[str], output_type: str, vague: bool
) -> float:
    score = 0.5
    score += min(len(features), 5) * 0.05
    if output_type != "unknown":
        score += 0.15
    if vague:
        score -= 0.3
    return round(max(0.1, min(0.95, score)), 2)


def extract_intent(raw: str) -> CapturedIntent:
    """Extract a structured CapturedIntent from a raw natural-language string."""
    output_type = _detect_output_type(raw)
    features = _extract_features(raw)
    vague = _is_vague(raw)
    confidence = _compute_confidence(features, output_type, vague)
    intent_id = _generate_intent_id(raw)
    summary = raw.split(".")[0].strip()
    if len(summary) > 80:
        summary = summary[:77] + "..."

    clarification_needed = vague
    clarification_question: str | None = None
    if vague:
        clarification_question = (
            "Deine Eingabe ist sehr vage. Kannst du genauer beschreiben, "
            "was die App tun soll? Z.\u00a0B. welche Daten sie verwaltet, "
            "welche Aktionen möglich sein sollen, für wen sie gedacht ist."
        )

    return CapturedIntent(
        intent_id=intent_id,
        raw=raw,
        summary=summary,
        required_features=features,
        output_type=output_type,
        confidence=confidence,
        clarification_needed=clarification_needed,
        clarification_question=clarification_question,
    )


# ── Compatibility stubs for drift.api.intent ─────────────────────────────────

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "persistence": [
        "datenbank", "database", "persist", "speicher", "storage",
        "sql", "mongo", "redis", "cache",
    ],
    "security": [
        "login", "passwort", "password", "auth", "authentif", "registrier",
        "berechtigung", "permission", "zugriff", "secret",
    ],
    "error_handling": [
        "fehler", "error", "exception", "robust", "resilient", "fehlerbeh",
        "fallback", "retry",
    ],
    "communication": [
        "api", "rest", "http", "webhook", "graphql", "notification",
        "email", "sms", "message",
    ],
    "automation": [
        "automat", "script", "cron", "schedule", "batch", "pipeline",
        "deploy", "backup",
    ],
}


def detect_category(text: str) -> str:
    """Return the most likely intent category for a prompt string."""
    lower = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return "utility"


def _extract_contracts_from_prompt(prompt: str, category: str) -> list[dict]:
    """Derive supplementary contracts from salient nouns in the prompt."""
    import re

    extracted: list[dict] = []
    # Capitalised German nouns or multi-word noun phrases as features
    nouns = re.findall(
        r"\b[A-ZÄÖÜ][a-zäöüß]{3,}(?:[A-ZÄÖÜ][a-zäöüß]{2,})?\b", prompt
    )
    # Verbs of interest that imply contracts
    action_kws = {
        "verwalte": "management", "manage": "management",
        "speichere": "persistence", "erstelle": "creation",
        "lösche": "deletion", "bearbeit": "editing",
    }
    lower = prompt.lower()
    for kw, concept in action_kws.items():
        if kw in lower:
            nouns.append(concept.capitalize())

    for noun in set(nouns):
        ext_id = f"ext-{re.sub(r'[^a-z0-9]', '-', noun.lower())}"
        extracted.append(
            {
                "id": ext_id,
                "description_technical": f"Support for {noun} functionality",
                "description_human": f"{noun} wird unterstützt",
                "category": category,
                "severity": "medium",
                "auto_repair_eligible": False,
                "source": "extracted",
            }
        )
    return extracted


def capture(prompt: str, repo_path: object = None) -> dict:
    """Phase 1 capture — classify intent and load baseline contracts."""
    from pathlib import Path

    category = detect_category(prompt)
    repo = Path(str(repo_path)) if repo_path else Path(".")
    contracts: list[dict] = []
    try:
        from drift.intent.registry import load_baselines

        loaded = load_baselines(repo, category=category)
        contracts = [c.to_dict() for c in loaded]
        # Fallback: if category yields too few, load all baselines
        if len(contracts) < 5:
            all_loaded = load_baselines(repo)
            contracts = [c.to_dict() for c in all_loaded]
    except Exception:  # noqa: BLE001
        pass

    # Add extracted contracts for richer coverage
    extracted = _extract_contracts_from_prompt(prompt, category)
    contracts.extend(extracted)

    return {
        "schema_version": "1.0",
        "prompt": prompt,
        "category": category,
        "contracts": contracts,
    }


_INTENT_FILENAME = "drift.intent.json"


def load_intent_json(repo_path: object = None) -> dict:
    """Load a previously saved drift.intent.json from disk.

    Raises
    ------
    FileNotFoundError
        If drift.intent.json does not exist under repo_path.
    """
    import json
    from pathlib import Path

    path = (Path(str(repo_path)) if repo_path else Path(".")) / _INTENT_FILENAME
    if not path.exists():
        raise FileNotFoundError(f"Intent file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def save_intent_json(data: dict, repo_path: object = None) -> Path:
    """Persist the intent dict to drift.intent.json, returns the Path."""
    import json

    path = (Path(str(repo_path)) if repo_path else Path(".")) / _INTENT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
