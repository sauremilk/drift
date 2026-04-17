#!/usr/bin/env python3
"""ADR-067: Controlled A/B study — does drift brief reduce agent-introduced drift?

Usage:
    # Full pipeline (sequential):
    python scripts/brief_ab_study.py generate-prompts
    python scripts/brief_ab_study.py run-mock [--repeats 3]
    python scripts/brief_ab_study.py run-llm [--model gpt-4o] [--temperature 0] [--repeats 3]
    python scripts/brief_ab_study.py evaluate
    python scripts/brief_ab_study.py stats
    python scripts/brief_ab_study.py assemble

    # With local Ollama (no API key needed):
    ollama serve                          # start Ollama in separate terminal
    ollama pull qwen2.5-coder:7b          # pull a coding model
    python scripts/brief_ab_study.py run-llm --base-url http://localhost:11434/v1 \
        --model qwen2.5-coder:7b --temperature 0.2 --repeats 3

    # Dry-run without LLM calls or git clones:
    python scripts/brief_ab_study.py generate-prompts --dry-run
    python scripts/brief_ab_study.py evaluate --dry-run

Environment variables:
    OPENAI_API_KEY        Required for run-llm (unless --base-url is set)
    DRIFT_STUDY_MODEL     Override model (default: gpt-4o)
    DRIFT_STUDY_BASE_URL  Optional OpenAI-compatible base URL (e.g. for Ollama, Azure)
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_FILE = REPO_ROOT / "benchmarks" / "brief_study_corpus.json"
WORK_DIR = REPO_ROOT / "work_artifacts" / "brief_study"
PROMPTS_DIR = WORK_DIR / "prompts"
RESPONSES_DIR = WORK_DIR / "responses"
OUTCOMES_FILE = WORK_DIR / "outcomes.json"
ARTIFACT_FILE = REPO_ROOT / "benchmark_results" / "drift_brief_ab_study.json"

MAX_CONTEXT_CHARS = 16_000  # ~4000 tokens at 4 chars/token
MAX_CONTEXT_CHARS_TREATMENT = 10_000  # Smaller context for treatment to leave room for brief JSON

# ---------------------------------------------------------------------------
# Error-cost model (ADR-067 extension: severity-weighted cost function)
# ---------------------------------------------------------------------------

# Severity multiplier — maps string severity labels to numeric weights.
# INFO is excluded (weight 0) to avoid inflating cost with noise findings.
_SEVERITY_WEIGHTS: dict[str, int] = {
    "critical": 8,
    "high": 4,
    "medium": 2,
    "low": 1,
    "info": 0,
}

# Hours-per-signal estimate — imported from roi_estimate at call time to
# avoid circular/missing-module issues when drift is not installed.  This
# fallback table is used when the import fails.
_HOURS_PER_SIGNAL_FALLBACK: dict[str, float] = {
    "pattern_fragmentation": 2.0,
    "architecture_violation": 3.0,
    "mutant_duplicate": 1.5,
    "explainability_deficit": 0.5,
    "doc_impl_drift": 0.5,
    "temporal_volatility": 1.0,
    "system_misalignment": 2.0,
    "broad_exception_monoculture": 0.5,
    "test_polarity_deficit": 1.5,
    "guard_clause_deficit": 0.5,
    "cohesion_deficit": 2.5,
    "naming_contract_violation": 0.3,
    "bypass_accumulation": 1.0,
    "exception_contract_drift": 1.0,
    "co_change_coupling": 2.0,
    "fan_out_explosion": 2.0,
    "circular_import": 1.5,
    "dead_code_accumulation": 0.5,
    "missing_authorization": 2.0,
    "insecure_default": 1.0,
    "hardcoded_secret": 0.5,
    "phantom_reference": 1.0,
    "ts_architecture": 1.5,
    "cognitive_complexity": 1.0,
}
_DEFAULT_HOURS = 1.0


def _get_hours_per_signal() -> dict[str, float]:
    """Return hours-per-signal table, preferring the canonical roi_estimate source."""
    try:
        from drift.commands.roi_estimate import _HOURS_PER_SIGNAL  # noqa: PLC0415

        return _HOURS_PER_SIGNAL
    except ImportError:
        return _HOURS_PER_SIGNAL_FALLBACK


def _error_cost_default(findings: list[dict[str, Any]]) -> float:
    """Simple severity-weighted cost: sum of severity weights across findings.

    C_default = Σ w_sev(f)
    """
    total = 0.0
    for f in findings:
        sev = str(f.get("severity", "info")).lower()
        total += _SEVERITY_WEIGHTS.get(sev, 0)
    return total


def _error_cost_robust(findings: list[dict[str, Any]]) -> float:
    """Signal- and breadth-weighted cost: h(signal) × w_sev × min(B_cap, 1+ln(1+|related|)).

    C_robust = Σ h(signal_type) × w_sev(f) × min(4.0, 1 + ln(1 + |related_files|))
    """
    hours_table = _get_hours_per_signal()
    total = 0.0
    for f in findings:
        sev = str(f.get("severity", "info")).lower()
        w_sev = _SEVERITY_WEIGHTS.get(sev, 0)
        if w_sev == 0:
            continue
        signal = f.get("signal") or f.get("signal_type") or ""
        h = hours_table.get(signal, _DEFAULT_HOURS)
        related_count = len(f.get("related_files", []))
        breadth = min(4.0, 1 + math.log(1 + related_count))
        total += h * w_sev * breadth
    return round(total, 4)


def _patch_line_count(diff_text: str) -> int:
    """Count added + removed lines in a unified diff (lines starting with +/- excluding headers)."""
    count = 0
    for line in diff_text.splitlines():
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            count += 1
    return count


# Patterns matching hallucinated placeholder context lines in LLM-generated diffs.
_PLACEHOLDER_PATTERNS = re.compile(
    r"^[ ]("
    r"\.\.\.$"
    r"|# ?\.\.\."
    r"|# existing .*"
    r"|# rest of .*"
    r"|# \.\.\. ?\(.*\)"
    r"|pass\s*# placeholder"
    r"|# omitted"
    r"|# \(truncated\)"
    r"|# \(unchanged\)"
    r")"
)


def _is_placeholder_context(line: str) -> bool:
    """Return True if *line* is a hallucinated placeholder that never appears in real source."""
    return bool(_PLACEHOLDER_PATTERNS.match(line))


def _recount_hunks(diff_text: str) -> str:
    """Recompute @@ line-count headers from actual hunk content.

    LLMs frequently emit wrong counts because they don't track additions/removals.
    ``git apply`` is strict about this, so we recount.
    """
    out_lines: list[str] = []
    hunk_start_idx: int | None = None
    old_start = new_start = 0

    def _flush_hunk() -> None:
        nonlocal hunk_start_idx
        if hunk_start_idx is None:
            return
        # Count actual context/add/del lines between hunk_start_idx+1 and current pos
        old_count = new_count = 0
        for hl in out_lines[hunk_start_idx + 1 :]:
            if hl.startswith("+"):
                new_count += 1
            elif hl.startswith("-"):
                old_count += 1
            elif hl.startswith(" ") or hl == "":
                old_count += 1
                new_count += 1
            # Skip \ No newline at end of file
        # Rewrite the @@ header
        out_lines[hunk_start_idx] = f"@@ -{old_start},{old_count} +{new_start},{new_count} @@"
        hunk_start_idx = None

    for line in diff_text.splitlines():
        m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if m:
            _flush_hunk()
            old_start = int(m.group(1))
            new_start = int(m.group(2))
            hunk_start_idx = len(out_lines)
            out_lines.append(line)  # placeholder — will be rewritten by _flush_hunk
            continue
        out_lines.append(line)
    _flush_hunk()
    return "\n".join(out_lines) + "\n"


def _normalize_diff(diff_text: str, repo_path: Path) -> str:
    """Normalize LLM-generated diffs for ``git apply`` compatibility.

    Fixes common issues:
    - CRLF → LF
    - Missing trailing newline
    - Hallucinated ``index xxxx..yyyy`` lines (removed)
    - ``new file mode`` for files that already exist in the repo
    - Strips preamble / postamble text outside diff blocks
    - Removes placeholder context lines (``...``, ``# existing ...``)
    - Recounts @@ hunk line numbers
    - Converts ``# FILE: path`` markers to proper ``diff --git`` headers
    """
    # 1. Normalize line endings
    text = diff_text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Ensure trailing newline
    if not text.endswith("\n"):
        text += "\n"

    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip lines before the first diff header
        if not out and not line.startswith("diff "):
            i += 1
            continue

        # Remove hallucinated index lines
        if re.match(r"^index [0-9a-f]+\.\.[0-9a-f]+ ", line):
            i += 1
            continue
        if re.match(r"^index [0-9a-f]+\.\.[0-9a-f]+$", line):
            i += 1
            continue

        # Fix "new file mode" for existing files
        if line.startswith("new file mode"):
            if out and out[-1].startswith("diff --git"):
                parts = out[-1].split()
                if len(parts) >= 4:
                    fpath = parts[3].lstrip("b/")
                    if (repo_path / fpath).exists():
                        i += 1
                        continue
            out.append(line)
            i += 1
            continue

        # Fix --- /dev/null for files that exist (after new file mode removal)
        if line == "--- /dev/null" and out:
            for prev in reversed(out):
                if prev.startswith("diff --git"):
                    parts = prev.split()
                    if len(parts) >= 3:
                        fpath = parts[2].lstrip("a/")
                        if (repo_path / fpath).exists():
                            line = f"--- a/{fpath}"
                    break

        # Convert ``# FILE: path/to/new.py`` + following ``+`` lines into a new-file diff
        if re.match(r"^[# ]*FILE:\s+(.+)", line):
            m = re.match(r"^[# ]*FILE:\s+(.+)", line)
            if m:
                new_file_path = m.group(1).strip()
                out.append(f"diff --git a/{new_file_path} b/{new_file_path}")
                out.append("new file mode 100644")
                out.append("--- /dev/null")
                out.append(f"+++ b/{new_file_path}")
                # Collect following + lines
                plus_lines: list[str] = []
                j = i + 1
                while j < len(lines):
                    nl = lines[j]
                    if nl.startswith("+"):
                        plus_lines.append(nl)
                        j += 1
                    elif nl.startswith(" ") and not nl.startswith("diff "):
                        # Might be LLM emitting context for new file — treat as added
                        plus_lines.append("+" + nl[1:])
                        j += 1
                    else:
                        break
                if plus_lines:
                    out.append(f"@@ -0,0 +1,{len(plus_lines)} @@")
                    out.extend(plus_lines)
                i = j
                continue

        # Remove placeholder context lines that would cause context mismatch
        if _is_placeholder_context(line):
            i += 1
            continue

        out.append(line)
        i += 1

    # Strip postamble (non-diff lines after last hunk)
    result = "\n".join(out)
    # Ensure final newline
    if result and not result.endswith("\n"):
        result += "\n"

    # Recount hunk line numbers (LLMs often get them wrong)
    result = _recount_hunks(result)

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_corpus() -> dict[str, Any]:
    if not CORPUS_FILE.exists():
        sys.exit(f"Corpus not found: {CORPUS_FILE}")
    return json.loads(CORPUS_FILE.read_text(encoding="utf-8"))


def _shallow_clone(url: str, ref: str, dest: Path) -> None:
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", ref, "--single-branch", url, str(dest)],
        check=True,
        capture_output=True,
        timeout=300,
    )


def _read_files_as_context(
    repo_path: Path, target_files: list[str], *, max_chars: int = MAX_CONTEXT_CHARS
) -> str:
    parts: list[str] = []
    for rel in target_files:
        p = repo_path / rel
        if not p.exists():
            parts.append(f"# FILE: {rel}\n# (file not found in this ref)\n")
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            parts.append(f"# FILE: {rel}\n# (read error: {exc})\n")
            continue
        parts.append(f"# FILE: {rel}\n{content}")
    combined = "\n\n".join(parts)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n\n# ... (truncated)"
    return combined


def _extract_diff_block(text: str) -> str | None:
    """Extract the first unified diff block from LLM response text."""
    # Fenced ```diff ... ``` or ```patch ... ```
    fenced = re.search(r"```(?:diff|patch)\n(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    # Bare diff starting with --- or diff --git
    bare = re.search(r"^(diff --git .+|---\s+\S.+)", text, re.MULTILINE)
    if bare:
        return text[bare.start() :].strip()
    return None


def _extract_file_block(text: str, target_files: list[str]) -> tuple[str, str] | None:
    """Extract file path and complete content from an LLM whole-file response.

    Looks for fenced code blocks with a file path as language tag, e.g.::

        ```path/to/file.py
        <content>
        ```

    Falls back to ``python`` language tag using the primary target file path.
    Returns ``(rel_path, content)`` or ``None``.
    """
    # 1. Try fenced block with explicit .py path
    m = re.search(r"```(\S+\.py)\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return (m.group(1), m.group(2))
    # 2. Try ```python — use primary target file as path
    m = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL)
    if m and target_files:
        return (target_files[0], m.group(1))
    # 3. Try any fenced block
    m = re.search(r"```\w*\s*\n(.*?)```", text, re.DOTALL)
    if m and target_files:
        return (target_files[0], m.group(1))
    return None


def _compress_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Strip verbose prose from brief output to save tokens.

    Keeps only fields that provide actionable coding guardrails.
    """
    keep_keys = {
        "guardrails",
        "constraints",
        "scope_files",
        "warnings",
        "scope_confidence",
        "affected_signals",
    }
    compressed: dict[str, Any] = {}
    for k, v in brief.items():
        if k in keep_keys and v:
            compressed[k] = v
    return compressed or brief  # Fallback to full if nothing matched


def _drift_version() -> str:
    try:
        from drift import __version__  # type: ignore[import-untyped]

        return __version__
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Subcommand: generate-prompts
# ---------------------------------------------------------------------------


def cmd_generate_prompts(args: argparse.Namespace) -> None:
    corpus = _load_corpus()
    tasks = corpus["tasks"]
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Generating prompts for {len(tasks)} tasks ...")
    skipped = 0

    for task in tasks:
        tid = task["id"]
        control_path = PROMPTS_DIR / f"{tid}_control.json"
        treatment_path = PROMPTS_DIR / f"{tid}_treatment.json"

        if control_path.exists() and treatment_path.exists() and not args.force:
            print(f"  [{tid}] already exists, skipping (use --force to regenerate)")
            skipped += 1
            continue

        if args.dry_run:
            print(f"  [{tid}] DRY-RUN: would clone {task['repo_url']} and generate 2 prompts")
            continue

        print(f"  [{tid}] cloning {task['repo_url']} ...")
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            try:
                _shallow_clone(task["repo_url"], task["ref"], repo_path)
            except subprocess.CalledProcessError as exc:
                print(f"  [{tid}] clone failed: {exc.stderr.decode(errors='replace')[:200]}")
                continue

            code_context = _read_files_as_context(repo_path, task["target_files"])

            primary_file = task["target_files"][0]
            system_msg = (
                "You are a precise Python code editing agent. "
                "When given a task and code context, output the COMPLETE modified file. "
                "Use the target file path as the language tag in a fenced code block:\n\n"
                f"```{primary_file}\n"
                "<entire file content with your changes applied>\n"
                "```\n\n"
                "If the task creates a new file, output its complete content in the same format. "
                "Focus on the primary target file only. "
                "Do not add prose or explanations outside the code block."
            )
            user_msg = (
                f"Task: {task['task_description']}\n\n"
                f"Primary target file: {primary_file}\n\n"
                f"Code context:\n{code_context}"
            )

            control_payload = {
                "task_id": tid,
                "treatment": "control",
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                "meta": {
                    "repo_url": task["repo_url"],
                    "ref": task["ref"],
                    "target_files": task["target_files"],
                    "expected_signals": task["expected_signals"],
                },
            }
            control_path.write_text(
                json.dumps(control_payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Treatment: generate drift brief for this repo + task
            try:
                from drift.api.brief import brief as api_brief  # noqa: PLC0415

                brief_result = api_brief(repo_path, task=task["task_description"])
                brief_compact = _compress_brief(brief_result)
                brief_block = json.dumps(brief_compact, indent=2, ensure_ascii=False)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{tid}] drift brief failed: {exc}")
                brief_block = '{"error": "drift brief unavailable"}'

            # Use reduced context for treatment to leave room for brief
            treatment_context = _read_files_as_context(
                repo_path,
                task["target_files"],
                max_chars=MAX_CONTEXT_CHARS_TREATMENT,
            )
            treatment_user_msg = (
                f"Task: {task['task_description']}\n\n"
                f"Primary target file: {primary_file}\n\n"
                f"<drift_brief>\n{brief_block}\n</drift_brief>\n\n"
                f"Code context:\n{treatment_context}"
            )
            treatment_payload = {
                "task_id": tid,
                "treatment": "treatment",
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": treatment_user_msg},
                ],
                "meta": {
                    "repo_url": task["repo_url"],
                    "ref": task["ref"],
                    "target_files": task["target_files"],
                    "expected_signals": task["expected_signals"],
                },
            }
            treatment_path.write_text(
                json.dumps(treatment_payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"  [{tid}] prompts written")

    if skipped:
        print(f"\n{skipped} task(s) skipped (already exist).")
    if not args.dry_run:
        print(f"\nPrompts written to: {PROMPTS_DIR}")


# ---------------------------------------------------------------------------
# Subcommand: run-mock (H4 instrument — no API key required)
# ---------------------------------------------------------------------------


def _generate_mock_diff(
    task: dict[str, Any],
    treatment: str,
    rng: random.Random,
    brief_result: dict[str, Any] | None = None,
) -> str:
    """Generate a deterministic mock whole-file content simulating agent edits.

    Treatment group: attempts to follow brief constraints (fewer violations).
    Control group: naive edits that introduce structural issues.
    Returns complete Python source content for the primary target file.
    """
    target = task["target_files"][0] if task["target_files"] else "file.py"  # noqa: F841

    if treatment == "treatment" and brief_result:
        # Treatment: cleaner edits inspired by brief constraints
        return (
            '"""Module refactored per drift brief constraints."""\n'
            "from __future__ import annotations\n\n"
            f"def {task['id'].lower().replace('-', '_')}_fix() -> None:\n"
            f'    """Fix for: {task["task_description"][:60]}"""\n'
            "    pass  # Minimal, constraint-aware implementation\n"
        )
    else:
        # Control: naive edits that introduce structural issues (duplicate funcs, broad except)
        id1 = rng.randint(1000, 9999)
        id2 = rng.randint(1000, 9999)
        return (
            '"""Quick fix attempt."""\n'
            "from __future__ import annotations\n\n"
            f"def handle_{id1}():\n"
            '    """Auto-generated handler."""\n'
            "    try:\n"
            "        result = do_something()\n"
            "    except Exception:\n"
            "        pass  # TODO: handle properly\n"
            "    return result\n\n\n"
            f"def handle_{id2}():\n"
            '    """Another handler - similar pattern."""\n'
            "    try:\n"
            "        result = do_something()\n"
            "    except Exception:\n"
            "        pass  # TODO: handle properly\n"
            "    return result\n"
        )


def cmd_run_mock(args: argparse.Namespace) -> None:
    """Generate deterministic mock agent responses without LLM API calls."""
    import random as random_mod  # noqa: PLC0415

    if not PROMPTS_DIR.exists():
        sys.exit(f"Prompts directory not found: {PROMPTS_DIR}. Run generate-prompts first.")

    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    prompt_files = sorted(PROMPTS_DIR.glob("*.json"))
    if not prompt_files:
        sys.exit("No prompt files found. Run generate-prompts first.")

    repeats: int = getattr(args, "repeats", 1)
    corpus = _load_corpus()
    task_map = {t["id"]: t for t in corpus["tasks"]}

    total = len(prompt_files) * repeats
    print(
        f"Generating mock agent responses for {len(prompt_files)} prompts "
        f"× {repeats} repeats (seed={args.seed}) ..."
    )

    for pf in prompt_files:
        base_stem = pf.stem
        payload = json.loads(pf.read_text(encoding="utf-8"))
        task_id = payload["task_id"]
        treatment = payload["treatment"]

        # Load brief result from treatment prompt if available
        brief_result = None
        if treatment == "treatment":
            for msg in payload.get("messages", []):
                content = msg.get("content", "")
                if "<drift_brief>" in content:
                    start = content.find("<drift_brief>") + len("<drift_brief>")
                    end = content.find("</drift_brief>")
                    if end > start:
                        with contextlib.suppress(json.JSONDecodeError):
                            brief_result = json.loads(content[start:end].strip())

        task = task_map.get(
            task_id,
            {"id": task_id, "target_files": ["file.py"], "task_description": "unknown task"},
        )

        for r in range(repeats):
            stem = f"{base_stem}_r{r}" if repeats > 1 else base_stem
            diff_out = RESPONSES_DIR / f"{stem}.diff"
            meta_out = RESPONSES_DIR / f"{stem}_meta.json"

            if diff_out.exists() and not args.force:
                print(f"  [{stem}] already exists, skipping")
                continue

            # Each repeat gets a unique but deterministic seed
            rng = random_mod.Random(args.seed + r)
            diff_content = _generate_mock_diff(task, treatment, rng, brief_result)
            diff_out.write_text(diff_content, encoding="utf-8")

            meta_out.write_text(
                json.dumps(
                    {
                        "task_id": task_id,
                        "treatment": treatment,
                        "model": "mock-agent",
                        "temperature": 0.0,
                        "status": "ok",
                        "response_format": "whole_file",
                        "seed": args.seed,
                        "repeat": r,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"  [{stem}] mock file written")

    print(f"\nMock responses written to: {RESPONSES_DIR} ({total} total)")


# ---------------------------------------------------------------------------
# Subcommand: run-llm
# ---------------------------------------------------------------------------


def cmd_run_llm(args: argparse.Namespace) -> None:
    try:
        from openai import OpenAI  # noqa: PLC0415
    except ImportError:
        sys.exit("openai package not installed. Run: uv add --dev openai")

    base_url = getattr(args, "base_url", None) or os.environ.get("DRIFT_STUDY_BASE_URL") or None
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key and not base_url:
        sys.exit(
            "OPENAI_API_KEY environment variable not set.\n"
            "Alternatively, use --base-url for a local backend (e.g. Ollama):\n"
            "  python scripts/brief_ab_study.py run-llm "
            "--base-url http://localhost:11434/v1 --model qwen2.5-coder:7b"
        )
    # Local backends (Ollama etc.) don't need a real key; use placeholder.
    if not api_key:
        api_key = "local"  # pragma: allowlist secret

    model = os.environ.get("DRIFT_STUDY_MODEL", args.model)
    client = OpenAI(api_key=api_key, base_url=base_url)

    if not PROMPTS_DIR.exists():
        sys.exit(f"Prompts directory not found: {PROMPTS_DIR}. Run generate-prompts first.")

    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    prompt_files = sorted(PROMPTS_DIR.glob("*.json"))
    if not prompt_files:
        sys.exit("No prompt files found. Run generate-prompts first.")

    repeats: int = getattr(args, "repeats", 1)
    total = len(prompt_files) * repeats
    print(
        f"Running LLM ({model}, temperature={args.temperature}) on "
        f"{len(prompt_files)} prompts × {repeats} repeats ..."
    )

    for pf in prompt_files:
        base_stem = pf.stem  # e.g. REQ-01_control
        payload = json.loads(pf.read_text(encoding="utf-8"))

        for r in range(repeats):
            stem = f"{base_stem}_r{r}" if repeats > 1 else base_stem
            diff_out = RESPONSES_DIR / f"{stem}.diff"
            meta_out = RESPONSES_DIR / f"{stem}_meta.json"

            if diff_out.exists() and not args.force:
                print(f"  [{stem}] already exists, skipping")
                continue

            print(f"  [{stem}] calling {model} ...")
            try:
                # Vary seed per repeat when temperature > 0
                extra_kwargs: dict[str, Any] = {}
                if args.temperature > 0 and repeats > 1:
                    extra_kwargs["seed"] = 42 + r

                response = client.chat.completions.create(
                    model=model,
                    temperature=args.temperature,
                    messages=payload["messages"],  # type: ignore[arg-type]
                    max_tokens=4096,
                    **extra_kwargs,
                )
                text = response.choices[0].message.content or ""
                target_files = payload.get("meta", {}).get("target_files", [])
                file_result = _extract_file_block(text, target_files)
                if file_result is None:
                    status = "parse_error"
                    diff_out.write_text(text, encoding="utf-8")
                else:
                    _fpath, file_content = file_result
                    status = "ok"
                    diff_out.write_text(file_content, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                status = f"api_error: {exc}"
                diff_out.write_text("", encoding="utf-8")

            meta_out.write_text(
                json.dumps(
                    {
                        "task_id": payload["task_id"],
                        "treatment": payload["treatment"],
                        "model": model,
                        "temperature": args.temperature,
                        "status": status,
                        "response_format": "whole_file",
                        "repeat": r,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"  [{stem}] status={status}")

    print(f"\nResponses written to: {RESPONSES_DIR} ({total} total)")


# ---------------------------------------------------------------------------
# Subcommand: evaluate
# ---------------------------------------------------------------------------


def cmd_evaluate(args: argparse.Namespace) -> None:
    from drift.api.diff import diff as api_diff  # noqa: PLC0415

    if not RESPONSES_DIR.exists():
        sys.exit(f"Responses directory not found: {RESPONSES_DIR}. Run run-llm first.")

    corpus = _load_corpus()
    task_map = {t["id"]: t for t in corpus["tasks"]}

    diff_files = sorted(RESPONSES_DIR.glob("*.diff"))
    if not diff_files:
        sys.exit("No diff files found. Run run-llm first.")

    outcomes: list[dict[str, Any]] = []
    print(f"Evaluating {len(diff_files)} diffs ...")

    for df in diff_files:
        stem = df.stem  # e.g. REQ-01_control
        meta_file = RESPONSES_DIR / f"{stem}_meta.json"
        if not meta_file.exists():
            print(f"  [{stem}] no meta file, skipping")
            continue

        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        task_id = meta["task_id"]
        treatment = meta["treatment"]
        task = task_map.get(task_id)
        if task is None:
            print(f"  [{stem}] task_id {task_id!r} not in corpus, skipping")
            continue

        if meta["status"] != "ok":
            outcomes.append(
                {
                    "task_id": task_id,
                    "treatment": treatment,
                    "repeat": meta.get("repeat", 0),
                    "status": meta["status"],
                    "new_findings_count": None,
                    "accept_change": None,
                    "error_cost_default": None,
                    "error_cost_robust": None,
                    "patch_size_loc": None,
                }
            )
            print(f"  [{stem}] upstream status={meta['status']}, skipping evaluate")
            continue

        diff_content = df.read_text(encoding="utf-8").strip()
        if not diff_content:
            outcomes.append(
                {
                    "task_id": task_id,
                    "treatment": treatment,
                    "repeat": meta.get("repeat", 0),
                    "status": "empty_diff",
                    "new_findings_count": None,
                    "accept_change": None,
                    "error_cost_default": None,
                    "error_cost_robust": None,
                    "patch_size_loc": None,
                }
            )
            print(f"  [{stem}] empty response, skipping")
            continue

        response_format = meta.get("response_format", "diff")

        if args.dry_run:
            print(f"  [{stem}] DRY-RUN: would apply changes and run drift diff")
            outcomes.append(
                {
                    "task_id": task_id,
                    "treatment": treatment,
                    "repeat": meta.get("repeat", 0),
                    "status": "dry_run",
                    "new_findings_count": None,
                    "accept_change": None,
                    "error_cost_default": None,
                    "error_cost_robust": None,
                    "patch_size_loc": 0,
                }
            )
            continue

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            print(f"  [{stem}] cloning {task['repo_url']} ...")
            try:
                _shallow_clone(task["repo_url"], task["ref"], repo_path)
            except subprocess.CalledProcessError as exc:
                err = exc.stderr.decode(errors="replace")[:200]
                print(f"  [{stem}] clone failed: {err}")
                outcomes.append(
                    {
                        "task_id": task_id,
                        "treatment": treatment,
                        "repeat": meta.get("repeat", 0),
                        "status": f"clone_error: {err[:80]}",
                        "new_findings_count": None,
                        "accept_change": None,
                        "error_cost_default": None,
                        "error_cost_robust": None,
                        "patch_size_loc": 0,
                    }
                )
                continue

            applied = False
            if response_format == "whole_file":
                # --- Whole-file approach: write LLM output directly ---
                primary_file = task["target_files"][0]
                target_path = repo_path / primary_file
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(diff_content, encoding="utf-8")
                # Stage all changes so drift can see new files
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=str(repo_path),
                    capture_output=True,
                )
                applied = True
            else:
                # --- Legacy diff approach: normalize and git apply ---
                normalized = _normalize_diff(diff_content, repo_path)
                diff_file = Path(tmpdir) / "patch.diff"
                diff_file.write_text(normalized, encoding="utf-8", newline="\n")

                for apply_args in [
                    ["git", "apply", "--ignore-whitespace", str(diff_file)],
                    ["git", "apply", "--ignore-whitespace", "--3way", str(diff_file)],
                    ["git", "apply", "--ignore-whitespace", "--reject", str(diff_file)],
                ]:
                    apply_result = subprocess.run(
                        apply_args,
                        cwd=str(repo_path),
                        capture_output=True,
                    )
                    if apply_result.returncode == 0:
                        applied = True
                        break

                # Last resort: try `patch` with fuzz factor (more tolerant)
                if not applied:
                    import shutil  # noqa: PLC0415

                    patch_bin = shutil.which("patch")
                    if not patch_bin:
                        git_bin = shutil.which("git")
                        if git_bin:
                            candidate = (
                                Path(git_bin).resolve().parent.parent / "usr" / "bin" / "patch.exe"
                            )
                            if candidate.exists():
                                patch_bin = str(candidate)
                    if patch_bin:
                        apply_result = subprocess.run(
                            [patch_bin, "-p1", "--fuzz=3", "--force", "-i", str(diff_file)],
                            cwd=str(repo_path),
                            capture_output=True,
                        )
                        if apply_result.returncode == 0:
                            applied = True

            if not applied:
                err = apply_result.stderr.decode(errors="replace")[:200]
                print(f"  [{stem}] apply failed: {err[:80]}")
                outcomes.append(
                    {
                        "task_id": task_id,
                        "treatment": treatment,
                        "repeat": meta.get("repeat", 0),
                        "status": "apply_error",
                        "new_findings_count": None,
                        "accept_change": None,
                        "error_cost_default": None,
                        "error_cost_robust": None,
                        "patch_size_loc": 0,
                        "apply_stderr": err,
                    }
                )
                continue

            # Calculate patch size from actual git diff
            git_diff_result = subprocess.run(
                ["git", "diff", "--staged"] if response_format == "whole_file" else ["git", "diff"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
            )
            patch_loc = (
                _patch_line_count(git_diff_result.stdout) if git_diff_result.returncode == 0 else 0
            )

            print(f"  [{stem}] running drift diff ...")
            try:
                result = api_diff(repo_path, uncommitted=True, response_detail="detailed")
                new_findings = result.get("new_findings", result.get("new", []))
                resolved_findings = result.get("resolved_findings", result.get("resolved", []))
                new_count = len(new_findings)
                accept = bool(result.get("accept_change", False))

                cost_d = _error_cost_default(new_findings)
                cost_r = _error_cost_robust(new_findings)
                resolved_cost_d = _error_cost_default(resolved_findings)
                resolved_cost_r = _error_cost_robust(resolved_findings)

                outcomes.append(
                    {
                        "task_id": task_id,
                        "treatment": treatment,
                        "repeat": meta.get("repeat", 0),
                        "status": "ok",
                        "new_findings_count": new_count,
                        "accept_change": accept,
                        "error_cost_default": cost_d,
                        "error_cost_robust": cost_r,
                        "net_cost_default": round(cost_d - resolved_cost_d, 4),
                        "net_cost_robust": round(cost_r - resolved_cost_r, 4),
                        "resolved_count": len(resolved_findings),
                        "patch_size_loc": patch_loc,
                        "drift_status": result.get("status"),
                        "score_delta": result.get("delta"),
                    }
                )
                print(
                    f"  [{stem}] new={new_count} cost_d={cost_d:.1f} "
                    f"cost_r={cost_r:.1f} patch={patch_loc} accept={accept}"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  [{stem}] drift diff error: {exc}")
                outcomes.append(
                    {
                        "task_id": task_id,
                        "treatment": treatment,
                        "repeat": meta.get("repeat", 0),
                        "status": f"drift_error: {exc}",
                        "new_findings_count": None,
                        "accept_change": None,
                        "error_cost_default": None,
                        "error_cost_robust": None,
                        "patch_size_loc": patch_loc,
                    }
                )

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTCOMES_FILE.write_text(json.dumps(outcomes, indent=2, ensure_ascii=False), encoding="utf-8")
    ok_count = sum(1 for o in outcomes if o["status"] == "ok")
    print(f"\nOutcomes written to: {OUTCOMES_FILE} ({ok_count}/{len(outcomes)} ok)")


# ---------------------------------------------------------------------------
# Subcommand: stats
# ---------------------------------------------------------------------------


def _cohens_d(a: list[float], b: list[float]) -> float:
    n_a, n_b = len(a), len(b)
    if n_a < 2 or n_b < 2:
        return float("nan")
    mean_a = sum(a) / n_a
    mean_b = sum(b) / n_b
    var_a = sum((x - mean_a) ** 2 for x in a) / (n_a - 1)
    var_b = sum((x - mean_b) ** 2 for x in b) / (n_b - 1)
    pooled_sd = math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
    if pooled_sd == 0:
        return 0.0
    return (mean_a - mean_b) / pooled_sd


def _aggregate_by_task(
    outcomes: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Group ok outcomes by (task_id, treatment) and compute per-task means.

    Returns ``{task_id: {treatment: {metric: mean_value}}}``
    """
    from collections import defaultdict  # noqa: PLC0415

    buckets: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for o in outcomes:
        if o["status"] != "ok":
            continue
        buckets[o["task_id"]][o["treatment"]].append(o)

    result: dict[str, dict[str, dict[str, float]]] = {}
    metrics = (
        "new_findings_count",
        "error_cost_default",
        "error_cost_robust",
        "net_cost_default",
        "net_cost_robust",
        "patch_size_loc",
    )
    for task_id, arms in buckets.items():
        result[task_id] = {}
        for arm_name, runs in arms.items():
            agg: dict[str, float] = {}
            for m in metrics:
                vals = [r[m] for r in runs if r.get(m) is not None]
                agg[m] = sum(vals) / len(vals) if vals else 0.0
            agg["n_runs"] = float(len(runs))
            agg["accept_rate"] = (
                sum(1 for r in runs if r.get("accept_change")) / len(runs) if runs else 0.0
            )
            result[task_id][arm_name] = agg
    return result


def cmd_stats(args: argparse.Namespace) -> None:  # noqa: ARG001
    try:
        from scipy.stats import (  # noqa: PLC0415
            fisher_exact,
            mannwhitneyu,
            wilcoxon,
        )
    except ImportError:
        sys.exit("scipy not installed. Run: uv add --dev scipy")

    if not OUTCOMES_FILE.exists():
        sys.exit(f"Outcomes file not found: {OUTCOMES_FILE}. Run evaluate first.")

    outcomes = json.loads(OUTCOMES_FILE.read_text(encoding="utf-8"))
    ok = [o for o in outcomes if o["status"] == "ok"]

    control = [o for o in ok if o["treatment"] == "control"]
    treatment = [o for o in ok if o["treatment"] == "treatment"]

    n_ctrl = len(control)
    n_treat = len(treatment)
    print(f"Status: {len(ok)}/{len(outcomes)} ok  |  control={n_ctrl}  treatment={n_treat}")

    # --------------- validity checks ---------------
    error_rate = 1 - len(ok) / max(len(outcomes), 1)
    if error_rate > 0.20:
        print(
            f"\nWARNING: error rate {error_rate:.0%} exceeds 20% threshold. "
            "Study validity is compromised.",
            file=sys.stderr,
        )

    if n_ctrl < 20 or n_treat < 20:
        print(
            f"\nWARNING: insufficient sample size (need n>=20 per group, "
            f"have control={n_ctrl}, treatment={n_treat}). "
            "Results will be unreliable.",
            file=sys.stderr,
        )
        if n_ctrl == 0 or n_treat == 0:
            sys.exit("Cannot compute statistics with empty group.")

    # --------------- unpaired tests (legacy, all runs) ---------------
    ctrl_counts = [o["new_findings_count"] for o in control]
    treat_counts = [o["new_findings_count"] for o in treatment]

    ctrl_accept = sum(1 for o in control if o["accept_change"])
    treat_accept = sum(1 for o in treatment if o["accept_change"])
    ctrl_reject = n_ctrl - ctrl_accept
    treat_reject = n_treat - treat_accept

    mw_stat, mw_p = mannwhitneyu(ctrl_counts, treat_counts, alternative="greater")
    mw_stat, mw_p = float(mw_stat), float(mw_p)

    contingency = [[ctrl_accept, ctrl_reject], [treat_accept, treat_reject]]
    fisher_or, fisher_p = fisher_exact(contingency, alternative="less")
    fisher_or, fisher_p = float(fisher_or), float(fisher_p)

    d = _cohens_d(ctrl_counts, treat_counts)
    ctrl_mean = sum(ctrl_counts) / n_ctrl
    treat_mean = sum(treat_counts) / n_treat

    print("\n--- new_findings_count (unpaired) ---")
    print(f"  control mean:   {ctrl_mean:.3f}")
    print(f"  treatment mean: {treat_mean:.3f}")
    print(f"  Mann-Whitney U: {mw_stat:.1f}  p={mw_p:.4f}")
    print(f"  Cohen's d:      {d:.3f}")

    print("\n--- accept_change ---")
    print(f"  control accept rate:   {ctrl_accept}/{n_ctrl} = {ctrl_accept / n_ctrl:.2%}")
    print(f"  treatment accept rate: {treat_accept}/{n_treat} = {treat_accept / n_treat:.2%}")
    print(f"  Fisher exact p: {fisher_p:.4f}  OR: {fisher_or:.3f}")

    # --------------- paired analysis (per-task means) ---------------
    task_agg = _aggregate_by_task(outcomes)
    paired_tasks = [
        tid for tid, arms in task_agg.items() if "control" in arms and "treatment" in arms
    ]

    paired_stats: dict[str, Any] = {}
    if len(paired_tasks) >= 5:
        # Build paired vectors (control mean - treatment mean per task)
        ctrl_cost_r = [task_agg[t]["control"]["error_cost_robust"] for t in paired_tasks]
        treat_cost_r = [task_agg[t]["treatment"]["error_cost_robust"] for t in paired_tasks]
        ctrl_cost_d = [task_agg[t]["control"]["error_cost_default"] for t in paired_tasks]
        treat_cost_d = [task_agg[t]["treatment"]["error_cost_default"] for t in paired_tasks]
        ctrl_patch = [task_agg[t]["control"]["patch_size_loc"] for t in paired_tasks]
        treat_patch = [task_agg[t]["treatment"]["patch_size_loc"] for t in paired_tasks]

        diffs_cost_r = [c - t for c, t in zip(ctrl_cost_r, treat_cost_r, strict=True)]
        diffs_cost_d = [c - t for c, t in zip(ctrl_cost_d, treat_cost_d, strict=True)]
        diffs_patch = [c - t for c, t in zip(ctrl_patch, treat_patch, strict=True)]

        def _safe_wilcoxon(diffs: list[float]) -> tuple[float, float]:
            nonzero = [x for x in diffs if x != 0]
            if len(nonzero) < 5:
                return (float("nan"), float("nan"))
            stat, p = wilcoxon(nonzero, alternative="greater")
            return (float(stat), float(p))

        def _rank_biserial(diffs: list[float]) -> float:
            """Matched-pairs rank-biserial correlation r = (W+ - W-) / W_total."""
            nonzero = [x for x in diffs if x != 0]
            n = len(nonzero)
            if n == 0:
                return 0.0
            w_total = n * (n + 1) / 2
            w_plus = sum(rank for rank, val in enumerate(sorted(nonzero, key=abs), 1) if val > 0)
            return (2 * w_plus - w_total) / w_total

        w_stat_r, w_p_r = _safe_wilcoxon(diffs_cost_r)
        w_stat_d, w_p_d = _safe_wilcoxon(diffs_cost_d)
        w_stat_patch, w_p_patch = _safe_wilcoxon(diffs_patch)

        r_biserial_r = _rank_biserial(diffs_cost_r)
        d_cost_r = _cohens_d(ctrl_cost_r, treat_cost_r)

        print(f"\n--- paired analysis ({len(paired_tasks)} tasks) ---")
        print(f"  error_cost_robust (ctrl mean): {sum(ctrl_cost_r) / len(ctrl_cost_r):.2f}")
        print(f"  error_cost_robust (treat mean): {sum(treat_cost_r) / len(treat_cost_r):.2f}")
        print(f"  Wilcoxon W (cost_robust): {w_stat_r:.1f}  p={w_p_r:.4f}")
        print(f"  Rank-biserial r:          {r_biserial_r:.3f}")
        print(f"  Cohen's d (cost_robust):  {d_cost_r:.3f}")
        print(f"  error_cost_default Wilcoxon p={w_p_d:.4f}")
        print(f"\n  patch_size_loc Wilcoxon p={w_p_patch:.4f} (guardrail check)")

        paired_stats = {
            "n_paired_tasks": len(paired_tasks),
            "error_cost_robust": {
                "control_mean": round(sum(ctrl_cost_r) / len(ctrl_cost_r), 4),
                "treatment_mean": round(sum(treat_cost_r) / len(treat_cost_r), 4),
                "wilcoxon_w": w_stat_r,
                "p_value": w_p_r,
                "cohens_d": d_cost_r,
                "rank_biserial_r": round(r_biserial_r, 4),
                "significant": bool(w_p_r < 0.05) if not math.isnan(w_p_r) else False,
            },
            "error_cost_default": {
                "control_mean": round(sum(ctrl_cost_d) / len(ctrl_cost_d), 4),
                "treatment_mean": round(sum(treat_cost_d) / len(treat_cost_d), 4),
                "wilcoxon_w": w_stat_d,
                "p_value": w_p_d,
                "significant": bool(w_p_d < 0.05) if not math.isnan(w_p_d) else False,
            },
            "patch_size_guardrail": {
                "control_mean": round(sum(ctrl_patch) / len(ctrl_patch), 2),
                "treatment_mean": round(sum(treat_patch) / len(treat_patch), 2),
                "wilcoxon_p": w_p_patch,
                "treatment_shorter": bool(w_p_patch < 0.05 if not math.isnan(w_p_patch) else False),
                "guardrail_violated": bool(
                    w_p_patch < 0.05 if not math.isnan(w_p_patch) else False
                ),
            },
        }

        if paired_stats.get("patch_size_guardrail", {}).get("guardrail_violated"):
            print(
                "\n  ⚠ GUARDRAIL: Treatment produces significantly shorter patches. "
                "Cost reduction may be trivial (less code = fewer findings)."
            )
    else:
        print(
            f"\n--- paired analysis: skipped (only {len(paired_tasks)} paired tasks, need ≥5) ---"
        )

    # --------------- interpretation ---------------
    alpha = 0.05
    mw_sig = bool(mw_p < alpha)
    fish_sig = bool(fisher_p < alpha)
    medium_effect = abs(d) >= 0.3

    paired_sig = paired_stats.get("error_cost_robust", {}).get("significant", False)
    paired_effect = abs(paired_stats.get("error_cost_robust", {}).get("cohens_d", 0)) >= 0.3
    guardrail_ok = not paired_stats.get("patch_size_guardrail", {}).get("guardrail_violated", False)

    if paired_sig and paired_effect and guardrail_ok:
        interpretation = "positive_effect"
    elif (mw_sig or fish_sig) and medium_effect:
        interpretation = "positive_effect_unpaired"
    elif not mw_sig and not fish_sig and not paired_sig:
        interpretation = "null_result"
    elif not guardrail_ok:
        interpretation = "confounded_by_patch_size"
    else:
        interpretation = "inconclusive"

    print(f"\nInterpretation: {interpretation}")

    # Persist stats for assemble
    stats_file = WORK_DIR / "stats.json"
    stats_payload: dict[str, Any] = {
        "n_control": n_ctrl,
        "n_treatment": n_treat,
        "error_rate": round(error_rate, 4),
        "new_findings": {
            "control_mean": ctrl_mean,
            "treatment_mean": treat_mean,
            "mann_whitney_u": mw_stat,
            "p_value": mw_p,
            "cohens_d": d,
            "significant": mw_sig,
        },
        "accept_change": {
            "control_rate": ctrl_accept / n_ctrl,
            "treatment_rate": treat_accept / n_treat,
            "fisher_p": fisher_p,
            "odds_ratio": fisher_or,
            "significant": fish_sig,
        },
        "interpretation": interpretation,
    }
    if paired_stats:
        stats_payload["paired"] = paired_stats

    stats_file.write_text(
        json.dumps(stats_payload, indent=2),
        encoding="utf-8",
    )
    print(f"Stats written to: {stats_file}")


# ---------------------------------------------------------------------------
# Subcommand: assemble
# ---------------------------------------------------------------------------


def cmd_assemble(args: argparse.Namespace) -> None:  # noqa: ARG001
    corpus = _load_corpus()

    stats_file = WORK_DIR / "stats.json"
    if not stats_file.exists():
        sys.exit(f"Stats file not found: {stats_file}. Run stats first.")
    if not OUTCOMES_FILE.exists():
        sys.exit(f"Outcomes file not found: {OUTCOMES_FILE}. Run evaluate first.")

    stats = json.loads(stats_file.read_text(encoding="utf-8"))
    outcomes = json.loads(OUTCOMES_FILE.read_text(encoding="utf-8"))

    # Infer model from first meta file
    model_used = "unknown"
    temperature_used: float = 0.0
    with contextlib.suppress(StopIteration, json.JSONDecodeError, OSError):
        first_meta = next(RESPONSES_DIR.glob("*_meta.json"))
        m = json.loads(first_meta.read_text(encoding="utf-8"))
        model_used = m.get("model", "unknown")
        temperature_used = m.get("temperature", 0.0)

    results: dict[str, Any] = {
        "n_control": stats["n_control"],
        "n_treatment": stats["n_treatment"],
        "error_rate": stats.get("error_rate"),
        "new_findings": stats["new_findings"],
        "accept_change": stats["accept_change"],
        "interpretation": stats["interpretation"],
    }
    if "paired" in stats:
        results["paired"] = stats["paired"]

    artifact = {
        "schema_version": "2.0",
        "date": date.today().isoformat(),
        "drift_version": _drift_version(),
        "adr": "ADR-067",
        "corpus": {
            "n_tasks": len(corpus["tasks"]),
            "repos": list({t["repo_url"] for t in corpus["tasks"]}),
        },
        "model": model_used,
        "temperature": temperature_used,
        "results": results,
        "raw_outcomes": outcomes,
    }

    ARTIFACT_FILE.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Artifact written to: {ARTIFACT_FILE}")
    print(f"Interpretation: {stats['interpretation']}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="brief_ab_study",
        description="ADR-067: A/B study to measure drift brief effectiveness.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # generate-prompts
    p_gen = sub.add_parser(
        "generate-prompts",
        help="Clone repos and build prompt files.",
    )
    p_gen.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip cloning; only print what would happen.",
    )
    p_gen.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if prompt files exist.",
    )

    # run-llm
    p_llm = sub.add_parser(
        "run-llm",
        help="Call LLM for each prompt and save diffs.",
    )
    p_llm.add_argument("--model", default="gpt-4o", help="LLM model name (default: gpt-4o).")
    p_llm.add_argument(
        "--base-url",
        default=None,
        help=(
            "OpenAI-compatible base URL for local backends "
            "(e.g. http://localhost:11434/v1 for Ollama)."
        ),
    )
    p_llm.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature (default: 0).",
    )
    p_llm.add_argument("--force", action="store_true", help="Re-run even if response files exist.")
    p_llm.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Number of repeat runs per task for paired k-repetitions (default: 1).",
    )

    # run-mock (H4 instrument — no API key required)
    p_mock = sub.add_parser(
        "run-mock",
        help="Generate deterministic mock agent diffs without LLM API (H4).",
    )
    p_mock.add_argument("--seed", type=int, default=42, help="Random seed (default: 42).")
    p_mock.add_argument("--force", action="store_true", help="Overwrite existing responses.")
    p_mock.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Number of repeat runs per task for paired k-repetitions (default: 1).",
    )

    # evaluate
    p_eval = sub.add_parser(
        "evaluate",
        help="Apply diffs and measure outcomes with drift diff.",
    )
    p_eval.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip cloning/apply; print what would happen.",
    )

    # stats
    sub.add_parser("stats", help="Compute statistical tests from outcomes.")

    # assemble
    sub.add_parser("assemble", help="Build final benchmark_results artifact JSON.")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    dispatch = {
        "generate-prompts": cmd_generate_prompts,
        "run-llm": cmd_run_llm,
        "run-mock": cmd_run_mock,
        "evaluate": cmd_evaluate,
        "stats": cmd_stats,
        "assemble": cmd_assemble,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
