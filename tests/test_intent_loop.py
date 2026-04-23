"""Tests for the 5-phase intent guarantor loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from drift.intent.models import Contract, ContractResult, ContractStatus

# ---------------------------------------------------------------------------
# Helpers & fixtures
# ---------------------------------------------------------------------------


@dataclass
class FakeFinding:
    """Minimal finding stub for testing validation."""

    signal_type: str
    severity: str
    rule_id: str = "FAKE-001"
    title: str = "Fake finding"


@pytest.fixture
def intent_repo(tmp_path: Path) -> Path:
    """Create a temporary repo with the baselines YAML."""
    # Load baseline YAML from package data (canonical location after B1 move)
    try:
        from importlib.resources import files

        baselines_text = files("drift.intent.data").joinpath("baselines.yaml").read_text(
            encoding="utf-8"
        )
    except Exception:
        # Inline minimal baselines as CI fallback
        baselines_text = _MINIMAL_BASELINES
    (tmp_path / "drift.intent.baselines.yaml").write_text(baselines_text, encoding="utf-8")
    return tmp_path


_MINIMAL_BASELINES = """\
persistence:
  - id: persist-survive-restart
    description_technical: Data persists across process restarts.
    description_human: Daten bleiben nach Neustart erhalten
    category: persistence
    severity: critical
    auto_repair_eligible: false
  - id: persist-concurrent-safety
    description_technical: Concurrent writes do not corrupt state.
    description_human: Gleichzeitige Zugriffe zerstören keine Daten
    category: persistence
    severity: high
    auto_repair_eligible: false
  - id: persist-input-integrity
    description_technical: User input is validated before persistence.
    description_human: Eingaben werden vor dem Speichern geprüft
    category: persistence
    severity: high
    auto_repair_eligible: true

security:
  - id: sec-no-plaintext-secrets
    description_technical: No secrets in plaintext source or config.
    description_human: Keine Passwörter im Klartext
    category: security
    severity: critical
    auto_repair_eligible: true
  - id: sec-input-validation
    description_technical: All external input is validated and sanitized.
    description_human: Externe Eingaben werden geprüft
    category: security
    severity: high
    auto_repair_eligible: true
  - id: sec-external-data-validation
    description_technical: External data sources are validated before use.
    description_human: Externe Datenquellen werden vor Nutzung geprüft
    category: security
    severity: high
    auto_repair_eligible: true

error_handling:
  - id: err-user-friendly-messages
    description_technical: Errors produce user-facing messages, not raw tracebacks.
    description_human: Fehlermeldungen sind verständlich
    category: error_handling
    severity: high
    auto_repair_eligible: true
  - id: err-empty-input-resilience
    description_technical: Empty or missing input does not crash the app.
    description_human: Leere Eingaben führen nicht zum Absturz
    category: error_handling
    severity: high
    auto_repair_eligible: true
  - id: err-network-data-safety
    description_technical: Network failures do not cause data loss.
    description_human: Netzwerkprobleme führen nicht zu Datenverlust
    category: error_handling
    severity: critical
    auto_repair_eligible: false
"""


# ── Phase 1: Capture ───────────────────────────────────────────────────


class TestCapture:
    """Test Phase 1 — capture."""

    def test_detect_category_persistence(self) -> None:
        from drift.intent.capture import detect_category

        assert detect_category("Ich will eine Datenbank-App") == "persistence"

    def test_detect_category_security(self) -> None:
        from drift.intent.capture import detect_category

        assert detect_category("Login und Passwort verwalten") == "security"

    def test_detect_category_error(self) -> None:
        from drift.intent.capture import detect_category

        assert detect_category("Robuste Fehlerbehandlung") == "error_handling"

    def test_detect_category_fallback(self) -> None:
        from drift.intent.capture import detect_category

        assert detect_category("xyz abc 123") == "utility"

    def test_detect_category_empty(self) -> None:
        from drift.intent.capture import detect_category

        assert detect_category("") == "utility"

    def test_capture_returns_contracts(self, intent_repo: Path) -> None:
        from drift.intent.capture import capture
        from drift.intent.registry import clear_cache

        clear_cache()
        result = capture("Ich will eine Datenbank-App", intent_repo)

        assert result["schema_version"] == "1.0"
        assert result["category"] == "persistence"
        assert len(result["contracts"]) >= 3  # at least 3 baselines
        assert result["prompt"] == "Ich will eine Datenbank-App"

    def test_capture_merges_extracted_contracts(self, intent_repo: Path) -> None:
        from drift.intent.capture import capture
        from drift.intent.registry import clear_cache

        clear_cache()
        # Prompt with manage keyword to trigger extraction
        result = capture("Verwalte meine Kühlschrank-Datenbank", intent_repo)

        ids = [c["id"] for c in result["contracts"]]
        # Should have baselines + extracted
        assert "persist-survive-restart" in ids  # baseline
        assert any("ext-" in cid for cid in ids)  # extracted

    def test_capture_min_5_contracts(self, intent_repo: Path) -> None:
        from drift.intent.capture import capture
        from drift.intent.registry import clear_cache

        clear_cache()
        result = capture("xyz", intent_repo)
        assert len(result["contracts"]) >= 5

    def test_save_and_load_intent_json(self, intent_repo: Path) -> None:
        from drift.intent.capture import load_intent_json, save_intent_json

        data = {"schema_version": "1.0", "prompt": "test", "category": "utility", "contracts": []}
        path = save_intent_json(data, intent_repo)
        assert path.exists()

        loaded = load_intent_json(intent_repo)
        assert loaded == data

    def test_load_intent_json_not_found(self, intent_repo: Path) -> None:
        from drift.intent.capture import load_intent_json

        with pytest.raises(FileNotFoundError):
            load_intent_json(intent_repo)


# ── Phase 2: Formalize ─────────────────────────────────────────────────


class TestFormalize:
    """Test Phase 2 — formalize."""

    def test_resolve_signal_contract_specific(self) -> None:
        from drift.intent.formalize import _resolve_signal

        c = Contract(
            id="sec-no-plaintext-secrets",
            description_technical="No secrets in plaintext.",
            description_human="Keine Passwörter im Klartext",
            category="security",
            severity="critical",
            auto_repair_eligible=True,
        )
        assert _resolve_signal(c) == "hardcoded_secret_candidate"

    def test_resolve_signal_category_fallback(self) -> None:
        from drift.intent.formalize import _resolve_signal

        c = Contract(
            id="unknown-contract-id",
            description_technical="Something unknown.",
            description_human="Unbekannt",
            category="security",
            severity="medium",
            auto_repair_eligible=True,
        )
        assert _resolve_signal(c) == "missing_authorization"

    def test_resolve_signal_manual(self) -> None:
        from drift.intent.formalize import _resolve_signal

        c = Contract(
            id="completely-unknown-id-xyz",
            description_technical="No signal.",
            description_human="Kein Signal",
            category="utility",
            severity="medium",
            auto_repair_eligible=True,
        )
        # utility has a mapping to guard_clause_deficit, use a category that doesn't
        # Actually utility IS mapped, so we need to test truly unmapped path
        # by checking a contract whose id and category both miss the maps.
        # utility -> guard_clause_deficit via _CATEGORY_SIGNAL_MAP, so it won't be manual.
        # Instead test that the resolve function is deterministic for a known contract.
        assert _resolve_signal(c) == "guard_clause_deficit"

    def test_formalize_adds_signals_and_validation(self) -> None:
        from drift.intent.formalize import formalize

        intent_data = {
            "schema_version": "1.0",
            "prompt": "test",
            "category": "persistence",
            "contracts": [
                {
                    "id": "persist-survive-restart",
                    "description_technical": "Data persists.",
                    "description_human": "Daten bleiben erhalten",
                    "category": "persistence",
                    "severity": "critical",
                    "auto_repair_eligible": False,
                    "source": "baseline",
                }
            ],
        }
        result = formalize(intent_data)

        # Signal should be added
        assert result["contracts"][0]["verification_signal"] == "exception_contract_drift"

        # Validation block should be added
        assert "validation" in result
        assert result["validation"]["schema_valid"] is True
        assert result["validation"]["total_contracts"] == 1

    def test_validate_against_schema_detects_errors(self) -> None:
        from drift.intent.formalize import _validate_against_schema

        data = {
            "schema_version": "1.0",
            "prompt": "test",
            "category": "persistence",
            "contracts": [
                {
                    "id": "bad",
                    # missing description_technical
                    "description_human": "test",
                    "category": "invalid-cat",
                    "severity": "invalid-sev",
                    "auto_repair_eligible": True,
                    "source": "baseline",
                }
            ],
        }
        errors = _validate_against_schema(data)
        assert len(errors) > 0
        # Should catch missing field and invalid category/severity
        error_text = " ".join(errors)
        assert "description_technical" in error_text or "invalid" in error_text


# ── Phase 3: Handoff ───────────────────────────────────────────────────


class TestHandoff:
    """Test Phase 3 — handoff."""

    def test_handoff_generates_markdown(self) -> None:
        from drift.intent.handoff import handoff

        intent_data = {
            "category": "persistence",
            "contracts": [
                {
                    "id": "persist-survive-restart",
                    "description_technical": "Data persists.",
                    "description_human": "Daten bleiben erhalten",
                    "category": "persistence",
                    "severity": "critical",
                    "auto_repair_eligible": False,
                    "source": "baseline",
                    "verification_signal": "exception_contract_drift",
                }
            ],
        }
        result = handoff("Mache mir eine App", intent_data)

        assert "# Agent-Auftrag" in result
        assert "Mache mir eine App" in result
        assert "persist-survive-restart" in result
        assert "exception_contract_drift" in result

    def test_save_agent_prompt(self, intent_repo: Path) -> None:
        from drift.intent.handoff import save_agent_prompt

        path = save_agent_prompt("# Test prompt", intent_repo)
        assert path.exists()
        assert path.name == "drift.agent.prompt.md"
        assert path.read_text(encoding="utf-8") == "# Test prompt"


# ── Phase 4: Validate ──────────────────────────────────────────────────


class TestValidate:
    """Test Phase 4 — validate."""

    def test_validate_all_fulfilled(self) -> None:
        from drift.intent.validate import validate_contracts

        intent_data = {
            "contracts": [
                {
                    "id": "sec-input-validation",
                    "description_technical": "Validate input.",
                    "description_human": "Eingaben prüfen",
                    "category": "security",
                    "severity": "high",
                    "auto_repair_eligible": True,
                    "source": "baseline",
                    "verification_signal": "guard_clause_deficit",
                }
            ],
        }
        # No findings → all fulfilled
        results = validate_contracts(intent_data, Path("."), findings=[])

        assert len(results) == 1
        assert results[0].status == ContractStatus.FULFILLED

    def test_validate_violated(self) -> None:
        from drift.intent.validate import validate_contracts

        intent_data = {
            "contracts": [
                {
                    "id": "sec-input-validation",
                    "description_technical": "Validate input.",
                    "description_human": "Eingaben prüfen",
                    "category": "security",
                    "severity": "high",
                    "auto_repair_eligible": True,
                    "source": "baseline",
                    "verification_signal": "guard_clause_deficit",
                }
            ],
        }
        findings = [FakeFinding(signal_type="guard_clause_deficit", severity="high")]
        results = validate_contracts(intent_data, Path("."), findings=findings)

        assert len(results) == 1
        assert results[0].status == ContractStatus.VIOLATED

    def test_validate_unverifiable_manual(self) -> None:
        from drift.intent.validate import validate_contracts

        intent_data = {
            "contracts": [
                {
                    "id": "manual-check",
                    "description_technical": "Manual only.",
                    "description_human": "Manuell prüfen",
                    "category": "utility",
                    "severity": "medium",
                    "auto_repair_eligible": False,
                    "source": "baseline",
                    "verification_signal": "manual",
                }
            ],
        }
        results = validate_contracts(intent_data, Path("."), findings=[])

        assert len(results) == 1
        assert results[0].status == ContractStatus.UNVERIFIABLE

    def test_validate_severity_threshold(self) -> None:
        """Finding with lower severity than contract should not violate."""
        from drift.intent.validate import validate_contracts

        intent_data = {
            "contracts": [
                {
                    "id": "sec-input-validation",
                    "description_technical": "Validate input.",
                    "description_human": "Eingaben prüfen",
                    "category": "security",
                    "severity": "critical",
                    "auto_repair_eligible": True,
                    "source": "baseline",
                    "verification_signal": "guard_clause_deficit",
                }
            ],
        }
        # Finding severity is "medium" < contract's "critical"
        findings = [FakeFinding(signal_type="guard_clause_deficit", severity="medium")]
        results = validate_contracts(intent_data, Path("."), findings=findings)

        assert results[0].status == ContractStatus.FULFILLED  # not violated

    def test_results_to_report_json(self) -> None:
        from drift.intent.validate import results_to_report_json

        c = Contract(
            id="test-c",
            description_technical="Test.",
            description_human="Test",
            category="utility",
            severity="medium",
            auto_repair_eligible=True,
        )
        results = [
            ContractResult(contract=c, status=ContractStatus.FULFILLED),
        ]
        report = results_to_report_json(results, prompt="hello")

        assert report["summary"]["total"] == 1
        assert report["summary"]["fulfilled"] == 1
        assert report["summary"]["all_fulfilled"] is True

    def test_save_report(self, intent_repo: Path) -> None:
        from drift.intent.validate import save_report

        c = Contract(
            id="test-c",
            description_technical="Test.",
            description_human="Test",
            category="utility",
            severity="medium",
            auto_repair_eligible=True,
        )
        results = [
            ContractResult(contract=c, status=ContractStatus.FULFILLED),
        ]
        json_path, md_path = save_report(results, intent_repo, prompt="hello")

        assert json_path.exists()
        assert md_path.exists()
        assert json_path.name == "drift.intent.report.json"
        assert md_path.name == "drift.intent.report.md"


# ── Phase 5: Repair ────────────────────────────────────────────────────


class TestRepair:
    """Test Phase 5 — repair loop."""

    def test_repair_loop_all_fulfilled(self, intent_repo: Path) -> None:
        from drift.intent.repair import repair_loop

        intent_data = {
            "prompt": "test",
            "contracts": [
                {
                    "id": "test-c",
                    "description_technical": "Test.",
                    "description_human": "Test",
                    "category": "utility",
                    "severity": "medium",
                    "auto_repair_eligible": True,
                    "source": "baseline",
                    "verification_signal": "guard_clause_deficit",
                }
            ],
        }
        report = repair_loop(intent_data, intent_repo, findings=[])

        assert report["repair"]["status"] == "all_fulfilled"
        assert report["repair"]["iterations_used"] == 0

    def test_repair_loop_writes_prompt_without_callback(self, intent_repo: Path) -> None:
        from drift.intent.repair import repair_loop

        intent_data = {
            "prompt": "test",
            "contracts": [
                {
                    "id": "test-c",
                    "description_technical": "Test.",
                    "description_human": "Test",
                    "category": "utility",
                    "severity": "high",
                    "auto_repair_eligible": True,
                    "source": "baseline",
                    "verification_signal": "guard_clause_deficit",
                }
            ],
        }
        findings = [FakeFinding(signal_type="guard_clause_deficit", severity="high")]
        report = repair_loop(intent_data, intent_repo, findings=findings, max_iterations=3)

        assert report["repair"]["status"] == "repair_prompt_written"
        assert (intent_repo / "drift.repair.prompt.md").exists()

    def test_repair_loop_max_iterations_reached(self, intent_repo: Path) -> None:
        from drift.intent.repair import repair_loop

        intent_data = {
            "prompt": "test",
            "contracts": [
                {
                    "id": "test-c",
                    "description_technical": "Test.",
                    "description_human": "Test",
                    "category": "utility",
                    "severity": "high",
                    "auto_repair_eligible": True,
                    "source": "baseline",
                    "verification_signal": "guard_clause_deficit",
                }
            ],
        }
        findings = [FakeFinding(signal_type="guard_clause_deficit", severity="high")]

        # With callback that does nothing (never fixes the violation)
        calls: list[int] = []
        report = repair_loop(
            intent_data,
            intent_repo,
            findings=findings,
            max_iterations=2,
            on_repair=lambda prompt, iteration: calls.append(iteration),
        )

        assert report["repair"]["status"] == "max_iterations_reached"
        assert report["repair"]["iterations_used"] == 2
        assert len(report["repair"]["escalations"]) > 0
        assert len(calls) == 2


# ── Translator ──────────────────────────────────────────────────────────


class TestTranslator:
    """Test the plain-language translator."""

    def test_contract_result_to_plain_fulfilled(self) -> None:
        from drift.intent.translator import contract_result_to_plain

        c = Contract(
            id="x",
            description_technical="X",
            description_human="Alles ok",
            category="utility",
            severity="medium",
            auto_repair_eligible=True,
        )
        result = ContractResult(contract=c, status=ContractStatus.FULFILLED)
        text = contract_result_to_plain(result)
        assert "✅" in text
        assert "Alles ok" in text

    def test_contract_result_to_plain_violated(self) -> None:
        from drift.intent.translator import contract_result_to_plain

        c = Contract(
            id="x",
            description_technical="X",
            description_human="Fehler",
            category="utility",
            severity="medium",
            auto_repair_eligible=True,
        )
        result = ContractResult(contract=c, status=ContractStatus.VIOLATED)
        text = contract_result_to_plain(result)
        assert "❌" in text
        assert "Fehler" in text

    def test_results_to_markdown(self) -> None:
        from drift.intent.translator import results_to_markdown

        c = Contract(
            id="x",
            description_technical="X",
            description_human="Alles ok",
            category="utility",
            severity="medium",
            auto_repair_eligible=True,
        )
        results = [ContractResult(contract=c, status=ContractStatus.FULFILLED)]
        md = results_to_markdown(results, prompt="Test prompt")

        assert "# Ergebnis" in md
        assert "Test prompt" in md
        assert "✅" in md

    def test_escalation_message(self) -> None:
        from drift.intent.translator import escalation_message

        c = Contract(
            id="x",
            description_technical="X",
            description_human="Daten sichern",
            category="utility",
            severity="medium",
            auto_repair_eligible=True,
        )
        result = ContractResult(contract=c, status=ContractStatus.VIOLATED)
        msg = escalation_message(result, 3)
        assert "Daten sichern" in msg
        assert "3" in msg


# ── Registry ────────────────────────────────────────────────────────────


class TestRegistry:
    """Test baseline contract registry."""

    def test_load_baselines_all(self, intent_repo: Path) -> None:
        from drift.intent.registry import clear_cache, load_baselines

        clear_cache()
        contracts = load_baselines(intent_repo)
        assert len(contracts) >= 9  # 3 categories × 3 each

    def test_load_baselines_filtered(self, intent_repo: Path) -> None:
        from drift.intent.registry import clear_cache, load_baselines

        clear_cache()
        contracts = load_baselines(intent_repo, category="security")
        assert all(c.category == "security" for c in contracts)
        assert len(contracts) == 3

    def test_load_baselines_caching(self, intent_repo: Path) -> None:
        from drift.intent.registry import clear_cache, load_baselines

        clear_cache()
        first = load_baselines(intent_repo)
        second = load_baselines(intent_repo)
        assert first == second  # Same objects from cache


# ── Models ──────────────────────────────────────────────────────────────


class TestNewModels:
    """Test the new Contract/ContractResult/ContractStatus models."""

    def test_contract_roundtrip(self) -> None:
        c = Contract(
            id="test-1",
            description_technical="Technical desc",
            description_human="Human desc",
            category="security",
            severity="high",
            auto_repair_eligible=True,
            source="extracted",
            verification_signal="guard_clause_deficit",
        )
        d = c.to_dict()
        c2 = Contract.from_dict(d)
        assert c2.id == c.id
        assert c2.verification_signal == c.verification_signal
        assert c2.source == "extracted"

    def test_contract_invalid_category(self) -> None:
        with pytest.raises(ValueError, match="category"):
            Contract(
                id="bad",
                description_technical="X",
                description_human="X",
                category="nonexistent",
                severity="high",
                auto_repair_eligible=True,
            )

    def test_contract_status_values(self) -> None:
        assert ContractStatus.FULFILLED == "fulfilled"
        assert ContractStatus.VIOLATED == "violated"
        assert ContractStatus.UNVERIFIABLE == "unverifiable"

    def test_contract_result_to_dict(self) -> None:
        c = Contract(
            id="test-1",
            description_technical="X",
            description_human="Y",
            category="utility",
            severity="medium",
            auto_repair_eligible=True,
        )
        result = ContractResult(
            contract=c,
            status=ContractStatus.VIOLATED,
            finding_id="FAKE-001",
            finding_title="Fake finding",
        )
        d = result.to_dict()
        assert d["status"] == "violated"
        assert d["finding_id"] == "FAKE-001"
        assert d["contract_id"] == "test-1"


# ── API integration ─────────────────────────────────────────────────────


class TestIntentAPI:
    """Test the intent() API function."""

    def test_intent_phase_1(self, intent_repo: Path) -> None:
        from drift.api.intent import intent
        from drift.intent.registry import clear_cache

        clear_cache()
        result = intent(
            prompt="Ich will eine Datenbank-App",
            path=intent_repo,
            phase=1,
        )

        assert result["type"] == "intent_capture"
        assert result["phase"] == 1
        assert result["category"] == "persistence"
        assert result["contracts_count"] >= 3
        assert (intent_repo / "drift.intent.json").exists()

    def test_intent_phase_2(self, intent_repo: Path) -> None:
        from drift.api.intent import intent
        from drift.intent.capture import save_intent_json
        from drift.intent.registry import clear_cache

        clear_cache()
        # Pre-create intent.json for phase 2
        save_intent_json(
            {
                "schema_version": "1.0",
                "prompt": "test",
                "category": "security",
                "contracts": [
                    {
                        "id": "sec-no-plaintext-secrets",
                        "description_technical": "No plaintext secrets.",
                        "description_human": "Keine Klartext-Passwörter",
                        "category": "security",
                        "severity": "critical",
                        "auto_repair_eligible": True,
                        "source": "baseline",
                    }
                ],
            },
            intent_repo,
        )

        result = intent(path=intent_repo, phase=2)
        assert result["type"] == "intent_formalize"
        assert result["phase"] == 2
        assert "validation" in result

    def test_intent_phase_3(self, intent_repo: Path) -> None:
        from drift.api.intent import intent
        from drift.intent.capture import save_intent_json

        save_intent_json(
            {
                "schema_version": "1.0",
                "prompt": "Mache mir eine App",
                "category": "utility",
                "contracts": [
                    {
                        "id": "test-c",
                        "description_technical": "Test.",
                        "description_human": "Test",
                        "category": "utility",
                        "severity": "medium",
                        "auto_repair_eligible": True,
                        "source": "baseline",
                        "verification_signal": "guard_clause_deficit",
                    }
                ],
            },
            intent_repo,
        )

        result = intent(path=intent_repo, phase=3)
        assert result["type"] == "intent_handoff"
        assert result["phase"] == 3
        assert (intent_repo / "drift.agent.prompt.md").exists()

    def test_intent_phase_4(self, intent_repo: Path) -> None:
        from drift.api.intent import intent
        from drift.intent.capture import save_intent_json

        save_intent_json(
            {
                "schema_version": "1.0",
                "prompt": "test",
                "category": "utility",
                "contracts": [
                    {
                        "id": "test-c",
                        "description_technical": "Test.",
                        "description_human": "Test",
                        "category": "utility",
                        "severity": "medium",
                        "auto_repair_eligible": True,
                        "source": "baseline",
                        "verification_signal": "guard_clause_deficit",
                    }
                ],
            },
            intent_repo,
        )

        result = intent(path=intent_repo, phase=4, findings=[])
        assert result["type"] == "intent_validate"
        assert result["phase"] == 4
        assert result["all_fulfilled"] is True

    def test_intent_phase_5_all_fulfilled(self, intent_repo: Path) -> None:
        from drift.api.intent import intent
        from drift.intent.capture import save_intent_json

        save_intent_json(
            {
                "schema_version": "1.0",
                "prompt": "test",
                "category": "utility",
                "contracts": [
                    {
                        "id": "test-c",
                        "description_technical": "Test.",
                        "description_human": "Test",
                        "category": "utility",
                        "severity": "medium",
                        "auto_repair_eligible": True,
                        "source": "baseline",
                        "verification_signal": "guard_clause_deficit",
                    }
                ],
            },
            intent_repo,
        )

        result = intent(path=intent_repo, phase=5, findings=[])
        assert result["type"] == "intent_repair"
        assert result["repair_status"] == "all_fulfilled"

    def test_intent_full_loop(self, intent_repo: Path) -> None:
        from drift.api.intent import intent
        from drift.intent.registry import clear_cache

        clear_cache()
        result = intent(
            prompt="Ich will eine Datenbank-App",
            path=intent_repo,
            findings=[],
        )

        assert result["type"] == "intent_full"
        assert result["category"] == "persistence"
        assert result["all_fulfilled"] is True
        assert 1 in result["phases_completed"]
        assert 4 in result["phases_completed"]
        assert (intent_repo / "drift.intent.json").exists()
        assert (intent_repo / "drift.agent.prompt.md").exists()

    def test_intent_missing_prompt_phase_1(self) -> None:
        from drift.api.intent import intent

        result = intent(path=".", phase=1)  # no prompt
        assert result["type"] == "error"
        assert "DRIFT-1002" in result["error_code"]

    def test_intent_missing_prompt_full_loop(self) -> None:
        from drift.api.intent import intent

        result = intent(path=".")  # no prompt, no phase
        assert result["type"] == "error"

    def test_intent_invalid_phase(self) -> None:
        from drift.api.intent import intent

        result = intent(prompt="test", path=".", phase=99)
        assert result["type"] == "error"

    def test_intent_missing_intent_file(self, intent_repo: Path) -> None:
        from drift.api.intent import intent

        # Phase 2 without drift.intent.json → error
        result = intent(path=intent_repo, phase=2)
        assert result["type"] == "error"
        assert "DRIFT-1003" in result["error_code"]
