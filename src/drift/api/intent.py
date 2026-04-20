"""Public API for intent capture, management, and the 5-phase intent loop.

Usage::

    from drift.api.intent import capture_intent, list_intents, intent

    # Legacy API
    contract = capture_intent("Eine Todo-App mit Login", language="de")
    contracts = list_intents(Path("."))

    # 5-phase intent loop
    result = intent("Ich will eine App die meinen Kühlschrank verwaltet")
    result = intent(phase=2, path=".")  # single phase
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from drift.api._config import _emit_api_telemetry
from drift.api_helpers import _base_response, _error_response
from drift.intent._classify import classify_intent
from drift.intent._questions import generate_questions
from drift.intent._store import load_contracts, save_contract
from drift.intent.capture import capture, load_intent_json, save_intent_json  # drift:ignore[PHR]
from drift.intent.formalize import formalize
from drift.intent.handoff import handoff, save_agent_prompt
from drift.intent.models import ContractStatus
from drift.intent.repair import repair_loop
from drift.intent.validate import (
    results_to_report_json,
    save_report,
    validate_contracts,
)


def capture_intent(
    description: str,
    *,
    language: str = "de",
    llm_config: dict[str, Any] | None = None,
    project_root: Path | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """Capture a user intent and return a formalized contract.

    Parameters
    ----------
    description:
        Free-text description of what the user wants.
    language:
        ISO 639-1 language code.
    llm_config:
        Optional LLM configuration. If ``None``, uses keyword fallback.
    project_root:
        Project root for saving the contract. Defaults to cwd.
    save:
        Whether to save the contract to ``.drift-intent.yaml``.

    Returns
    -------
    dict
        Contract data with ``contract``, ``questions``, and ``saved_to`` keys.
    """
    if not description or not description.strip():
        raise ValueError("description must not be empty")
    contract = classify_intent(description, language=language, llm_config=llm_config)
    questions = generate_questions(contract)

    result: dict[str, Any] = {
        "contract": contract.to_dict(),
        "questions": [
            {
                "question_text": q.question_text,
                "options": q.options,
                "affects_requirement": q.affects_requirement,
            }
            for q in questions
        ],
        "saved_to": None,
    }

    if save and project_root is not None:
        intent_file = save_contract(contract, project_root)
        result["saved_to"] = str(intent_file)

    return result


def list_intents(project_root: Path) -> list[dict[str, Any]]:
    """List all intent contracts from a project.

    Parameters
    ----------
    project_root:
        Path to the project root.

    Returns
    -------
    list[dict]
        Serialized contract dicts.
    """
    if not project_root:
        return []
    contracts = load_contracts(project_root)
    return [c.to_dict() for c in contracts]


# ---------------------------------------------------------------------------
# 5-phase intent loop
# ---------------------------------------------------------------------------


def intent(
    prompt: str | None = None,
    path: str | Path = ".",
    *,
    phase: int | None = None,
    max_repair_iterations: int = 3,
    findings: list[Any] | None = None,
) -> dict[str, Any]:
    """Run the intent guarantor loop.

    Parameters
    ----------
    prompt:
        Natural-language user prompt (required for phase 1 or full run).
    path:
        Repository root.
    phase:
        Run a single phase (1-5). If ``None``, runs all phases sequentially.
    max_repair_iterations:
        Maximum repair loop iterations (phase 5).
    findings:
        Pre-computed findings for validation (testing).

    Returns
    -------
    dict
        Structured API response following Drift envelope convention.
    """
    from drift.telemetry import timed_call

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params: dict[str, Any] = {
        "prompt": prompt,
        "path": str(path),
        "phase": phase,
        "max_repair_iterations": max_repair_iterations,
    }

    try:
        if phase is not None:
            result = _run_single_phase(
                prompt=prompt,
                repo_path=repo_path,
                phase=phase,
                max_repair_iterations=max_repair_iterations,
                findings=findings,
            )
        else:
            result = _run_all_phases(
                prompt=prompt,
                repo_path=repo_path,
                max_repair_iterations=max_repair_iterations,
                findings=findings,
            )

        _emit_api_telemetry(
            tool_name="api.intent",
            params=params,
            status="ok",
            result=result,
            error=None,
            elapsed_ms=elapsed_ms(),
            repo_root=repo_path,
        )
        return result

    except FileNotFoundError as exc:
        return _error_response(
            "DRIFT-1003",
            str(exc),
            recoverable=True,
        )
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            "DRIFT-2001",
            f"Intent loop failed: {exc}",
            recoverable=False,
        )


def _run_single_phase(
    *,
    prompt: str | None,
    repo_path: Path,
    phase: int,
    max_repair_iterations: int,
    findings: list[Any] | None,
) -> dict[str, Any]:
    """Execute a single intent phase."""
    if phase == 1:
        if not prompt:
            return _error_response(
                "DRIFT-1002",
                "Phase 1 requires a prompt string.",
                invalid_fields=[{"field": "prompt", "reason": "required for capture"}],
            )
        intent_data = capture(prompt, repo_path)
        formalized = formalize(intent_data)
        save_intent_json(formalized, repo_path)

        return _base_response(
            type="intent_capture",
            phase=1,
            category=formalized["category"],
            contracts_count=len(formalized.get("contracts", [])),
            intent_file="drift.intent.json",
            data=formalized,
        )

    if phase == 2:
        intent_data = load_intent_json(repo_path)
        formalized = formalize(intent_data)
        save_intent_json(formalized, repo_path)

        return _base_response(
            type="intent_formalize",
            phase=2,
            validation=formalized.get("validation", {}),
            intent_file="drift.intent.json",
            data=formalized,
        )

    if phase == 3:
        intent_data = load_intent_json(repo_path)
        original_prompt = intent_data.get("prompt", "")
        agent_prompt = handoff(original_prompt, intent_data)
        save_agent_prompt(agent_prompt, repo_path)

        return _base_response(
            type="intent_handoff",
            phase=3,
            agent_prompt_file="drift.agent.prompt.md",
        )

    if phase == 4:
        intent_data = load_intent_json(repo_path)
        results = validate_contracts(intent_data, repo_path, findings=findings)
        original_prompt = intent_data.get("prompt", "")
        json_path, md_path = save_report(
            results, repo_path, prompt=original_prompt
        )

        report = results_to_report_json(results, prompt=original_prompt)
        return _base_response(
            type="intent_validate",
            phase=4,
            report=report,
            report_json_file=str(json_path.name),
            report_md_file=str(md_path.name),
            all_fulfilled=report["summary"]["all_fulfilled"],
        )

    if phase == 5:
        intent_data = load_intent_json(repo_path)
        report = repair_loop(
            intent_data,
            repo_path,
            max_iterations=max_repair_iterations,
            findings=findings,
        )

        return _base_response(
            type="intent_repair",
            phase=5,
            report=report,
            repair_status=report.get("repair", {}).get("status", "unknown"),
        )

    return _error_response(
        "DRIFT-1002",
        f"Invalid phase: {phase}. Must be 1-5.",
        invalid_fields=[{"field": "phase", "value": str(phase)}],
    )


def _run_all_phases(
    *,
    prompt: str | None,
    repo_path: Path,
    max_repair_iterations: int,
    findings: list[Any] | None,
) -> dict[str, Any]:
    """Execute all 5 phases sequentially."""
    if not prompt:
        return _error_response(
            "DRIFT-1002",
            "Full intent loop requires a prompt string.",
            invalid_fields=[{"field": "prompt", "reason": "required"}],
        )

    # Phase 1 + 2: Capture & Formalize
    intent_data = capture(prompt, repo_path)
    formalized = formalize(intent_data)
    save_intent_json(formalized, repo_path)

    # Phase 3: Handoff
    agent_prompt = handoff(prompt, formalized)
    save_agent_prompt(agent_prompt, repo_path)

    # Phase 4: Validate
    results = validate_contracts(formalized, repo_path, findings=findings)
    json_path, md_path = save_report(results, repo_path, prompt=prompt)

    violated = [r for r in results if r.status == ContractStatus.VIOLATED]

    # Phase 5: Repair (only if there are violations)
    repair_report: dict[str, Any] | None = None
    if violated:
        repair_report = repair_loop(
            formalized,
            repo_path,
            max_iterations=max_repair_iterations,
            findings=findings,
        )

    report = results_to_report_json(results, prompt=prompt)
    response = _base_response(
        type="intent_full",
        prompt=prompt,
        category=formalized["category"],
        contracts_count=len(formalized.get("contracts", [])),
        phases_completed=[1, 2, 3, 4] + ([5] if violated else []),
        report=report,
        all_fulfilled=report["summary"]["all_fulfilled"],
        files_written=[
            "drift.intent.json",
            "drift.agent.prompt.md",
            str(json_path.name),
            str(md_path.name),
        ],
    )

    if repair_report is not None:
        response["repair"] = repair_report.get("repair", {})
        response["files_written"].append("drift.repair.prompt.md")

    return response
