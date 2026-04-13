#!/usr/bin/env python3
"""ADR-067: Controlled A/B study — does drift brief reduce agent-introduced drift?

Usage:
    # Full pipeline (sequential):
    python scripts/brief_ab_study.py generate-prompts
    python scripts/brief_ab_study.py run-llm [--model gpt-4o] [--temperature 0]
    python scripts/brief_ab_study.py evaluate
    python scripts/brief_ab_study.py stats
    python scripts/brief_ab_study.py assemble

    # Dry-run without LLM calls or git clones:
    python scripts/brief_ab_study.py generate-prompts --dry-run
    python scripts/brief_ab_study.py evaluate --dry-run

Environment variables:
    OPENAI_API_KEY        Required for run-llm subcommand
    DRIFT_STUDY_MODEL     Override model (default: gpt-4o)
    DRIFT_STUDY_BASE_URL  Optional OpenAI-compatible base URL (e.g. for Azure)
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


def _read_files_as_context(repo_path: Path, target_files: list[str]) -> str:
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
    if len(combined) > MAX_CONTEXT_CHARS:
        combined = combined[:MAX_CONTEXT_CHARS] + "\n\n# ... (truncated)"
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
        return text[bare.start():].strip()
    return None


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

            system_msg = (
                "You are a precise Python code editing agent. "
                "When given a task and code context, produce a minimal unified diff "
                "(git diff format) that implements the requested change. "
                "Output ONLY the diff block, fenced in ```diff ... ```. "
                "Do not explain or add prose outside the fenced block."
            )
            user_msg = (
                f"Task: {task['task_description']}\n\n"
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
                brief_block = json.dumps(brief_result, indent=2, ensure_ascii=False)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{tid}] drift brief failed: {exc}")
                brief_block = '{"error": "drift brief unavailable"}'

            treatment_user_msg = (
                f"Task: {task['task_description']}\n\n"
                f"<drift_brief>\n{brief_block}\n</drift_brief>\n\n"
                f"Code context:\n{code_context}"
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
    """Generate a deterministic mock diff simulating agent edits.

    Treatment group: attempts to follow brief constraints (fewer violations).
    Control group: naive edits (more pattern violations).
    """
    target = task["target_files"][0] if task["target_files"] else "file.py"

    if treatment == "treatment" and brief_result:
        # Treatment: cleaner edits inspired by brief constraints
        new_lines = [
            "# Refactored per drift brief constraints",
            f"def {task['id'].lower().replace('-', '_')}_fix():",
            f"    \"\"\"Fix for: {task['task_description'][:60]}\"\"\"",
            "    pass  # Minimal, constraint-aware implementation",
            "",
        ]
    else:
        # Control: naive edits that introduce structural issues
        dup_func = f"def handle_{rng.randint(1000, 9999)}():"
        new_lines = [
            "# Quick fix attempt",
            dup_func,
            "    \"\"\"Auto-generated handler.\"\"\"",
            "    try:",
            "        result = do_something()",
            "    except Exception:",
            "        pass  # TODO: handle properly",
            "    return result",
            "",
            f"def handle_{rng.randint(1000, 9999)}():",
            "    \"\"\"Another handler — similar pattern.\"\"\"",
            "    try:",
            "        result = do_something()",
            "    except Exception:",
            "        pass  # TODO: handle properly",
            "    return result",
            "",
        ]

    added = "\n".join(f"+{line}" for line in new_lines)
    return (
        f"diff --git a/{target} b/{target}\n"
        f"--- a/{target}\n"
        f"+++ b/{target}\n"
        f"@@ -1,0 +1,{len(new_lines)} @@\n"
        f"{added}\n"
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

    rng = random_mod.Random(args.seed)
    print(f"Generating mock agent responses for {len(prompt_files)} prompts (seed={args.seed}) ...")

    for pf in prompt_files:
        stem = pf.stem
        diff_out = RESPONSES_DIR / f"{stem}.diff"
        meta_out = RESPONSES_DIR / f"{stem}_meta.json"

        if diff_out.exists() and not args.force:
            print(f"  [{stem}] already exists, skipping")
            continue

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

        # Build a minimal task dict for the generator
        corpus = _load_corpus()
        task_map = {t["id"]: t for t in corpus["tasks"]}
        task = task_map.get(task_id, {"id": task_id, "target_files": ["file.py"],
                                       "task_description": "unknown task"})

        diff_content = _generate_mock_diff(task, treatment, rng, brief_result)
        diff_out.write_text(diff_content, encoding="utf-8")

        meta_out.write_text(
            json.dumps({
                "task_id": task_id,
                "treatment": treatment,
                "model": "mock-agent",
                "temperature": 0.0,
                "status": "ok",
                "seed": args.seed,
            }, indent=2),
            encoding="utf-8",
        )
        print(f"  [{stem}] mock diff written")

    print(f"\nMock responses written to: {RESPONSES_DIR}")


# ---------------------------------------------------------------------------
# Subcommand: run-llm
# ---------------------------------------------------------------------------


def cmd_run_llm(args: argparse.Namespace) -> None:
    try:
        from openai import OpenAI  # noqa: PLC0415
    except ImportError:
        sys.exit("openai package not installed. Run: uv add --dev openai")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("OPENAI_API_KEY environment variable not set.")

    model = os.environ.get("DRIFT_STUDY_MODEL", args.model)
    base_url = os.environ.get("DRIFT_STUDY_BASE_URL") or None
    client = OpenAI(api_key=api_key, base_url=base_url)

    if not PROMPTS_DIR.exists():
        sys.exit(f"Prompts directory not found: {PROMPTS_DIR}. Run generate-prompts first.")

    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    prompt_files = sorted(PROMPTS_DIR.glob("*.json"))
    if not prompt_files:
        sys.exit("No prompt files found. Run generate-prompts first.")

    print(
        f"Running LLM ({model}, temperature={args.temperature}) on "
        f"{len(prompt_files)} prompts ..."
    )

    for pf in prompt_files:
        stem = pf.stem  # e.g. REQ-01_control
        diff_out = RESPONSES_DIR / f"{stem}.diff"
        meta_out = RESPONSES_DIR / f"{stem}_meta.json"

        if diff_out.exists() and not args.force:
            print(f"  [{stem}] already exists, skipping")
            continue

        payload = json.loads(pf.read_text(encoding="utf-8"))
        print(f"  [{stem}] calling {model} ...")
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=args.temperature,
                messages=payload["messages"],  # type: ignore[arg-type]
                max_tokens=2048,
            )
            text = response.choices[0].message.content or ""
            diff_block = _extract_diff_block(text)
            if diff_block is None:
                status = "parse_error"
                diff_out.write_text(text, encoding="utf-8")
            else:
                status = "ok"
                diff_out.write_text(diff_block, encoding="utf-8")
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
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  [{stem}] status={status}")

    print(f"\nResponses written to: {RESPONSES_DIR}")


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
            outcomes.append({
                "task_id": task_id,
                "treatment": treatment,
                "status": meta["status"],
                "new_findings_count": None,
                "accept_change": None,
            })
            print(f"  [{stem}] upstream status={meta['status']}, skipping evaluate")
            continue

        diff_content = df.read_text(encoding="utf-8").strip()
        if not diff_content:
            outcomes.append({
                "task_id": task_id,
                "treatment": treatment,
                "status": "empty_diff",
                "new_findings_count": None,
                "accept_change": None,
            })
            print(f"  [{stem}] empty diff, skipping")
            continue

        if args.dry_run:
            print(f"  [{stem}] DRY-RUN: would apply diff and run drift diff")
            outcomes.append({
                "task_id": task_id,
                "treatment": treatment,
                "status": "dry_run",
                "new_findings_count": None,
                "accept_change": None,
            })
            continue

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            print(f"  [{stem}] cloning {task['repo_url']} ...")
            try:
                _shallow_clone(task["repo_url"], task["ref"], repo_path)
            except subprocess.CalledProcessError as exc:
                err = exc.stderr.decode(errors="replace")[:200]
                print(f"  [{stem}] clone failed: {err}")
                outcomes.append({
                    "task_id": task_id,
                    "treatment": treatment,
                    "status": f"clone_error: {err[:80]}",
                    "new_findings_count": None,
                    "accept_change": None,
                })
                continue

            diff_file = Path(tmpdir) / "patch.diff"
            diff_file.write_text(diff_content, encoding="utf-8")

            apply_result = subprocess.run(
                ["git", "apply", "--reject", str(diff_file)],
                cwd=str(repo_path),
                capture_output=True,
            )
            if apply_result.returncode != 0:
                err = apply_result.stderr.decode(errors="replace")[:200]
                print(f"  [{stem}] git apply failed: {err[:80]}")
                outcomes.append({
                    "task_id": task_id,
                    "treatment": treatment,
                    "status": "apply_error",
                    "new_findings_count": None,
                    "accept_change": None,
                    "apply_stderr": err,
                })
                continue

            print(f"  [{stem}] running drift diff ...")
            try:
                result = api_diff(repo_path, uncommitted=True)
                new_count = len(result.get("new", []))
                accept = bool(result.get("accept_change", False))
                outcomes.append({
                    "task_id": task_id,
                    "treatment": treatment,
                    "status": "ok",
                    "new_findings_count": new_count,
                    "accept_change": accept,
                    "drift_status": result.get("status"),
                    "score_delta": result.get("delta"),
                })
                print(f"  [{stem}] new_findings={new_count} accept={accept}")
            except Exception as exc:  # noqa: BLE001
                print(f"  [{stem}] drift diff error: {exc}")
                outcomes.append({
                    "task_id": task_id,
                    "treatment": treatment,
                    "status": f"drift_error: {exc}",
                    "new_findings_count": None,
                    "accept_change": None,
                })

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


def cmd_stats(args: argparse.Namespace) -> None:  # noqa: ARG001
    try:
        from scipy.stats import fisher_exact, mannwhitneyu  # noqa: PLC0415
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

    if n_ctrl < 20 or n_treat < 20:
        print(
            f"\nWARNING: insufficient sample size (need n>=20 per group, "
            f"have control={n_ctrl}, treatment={n_treat}). "
            "Results will be unreliable.",
            file=sys.stderr,
        )
        if n_ctrl == 0 or n_treat == 0:
            sys.exit("Cannot compute statistics with empty group.")

    ctrl_counts = [o["new_findings_count"] for o in control]
    treat_counts = [o["new_findings_count"] for o in treatment]

    ctrl_accept = sum(1 for o in control if o["accept_change"])
    treat_accept = sum(1 for o in treatment if o["accept_change"])
    ctrl_reject = n_ctrl - ctrl_accept
    treat_reject = n_treat - treat_accept

    # Mann-Whitney U on new_findings_count
    mw_stat, mw_p = mannwhitneyu(ctrl_counts, treat_counts, alternative="greater")
    mw_stat, mw_p = float(mw_stat), float(mw_p)

    # Fisher exact on accept_change
    contingency = [[ctrl_accept, ctrl_reject], [treat_accept, treat_reject]]
    fisher_or, fisher_p = fisher_exact(contingency, alternative="less")
    fisher_or, fisher_p = float(fisher_or), float(fisher_p)

    # Cohen's d (control - treatment; positive d = control has more findings)
    d = _cohens_d(ctrl_counts, treat_counts)

    ctrl_mean = sum(ctrl_counts) / n_ctrl
    treat_mean = sum(treat_counts) / n_treat

    print("\n--- new_findings_count ---")
    print(f"  control mean:   {ctrl_mean:.3f}")
    print(f"  treatment mean: {treat_mean:.3f}")
    print(f"  Mann-Whitney U: {mw_stat:.1f}  p={mw_p:.4f}")
    print(f"  Cohen's d:      {d:.3f}")

    print("\n--- accept_change ---")
    print(f"  control accept rate:   {ctrl_accept}/{n_ctrl} = {ctrl_accept/n_ctrl:.2%}")
    print(f"  treatment accept rate: {treat_accept}/{n_treat} = {treat_accept/n_treat:.2%}")
    print(f"  Fisher exact p: {fisher_p:.4f}  OR: {fisher_or:.3f}")

    alpha = 0.05
    mw_sig = bool(mw_p < alpha)
    fish_sig = bool(fisher_p < alpha)
    medium_effect = abs(d) >= 0.3

    if (mw_sig or fish_sig) and medium_effect:
        interpretation = "positive_effect"
    elif not mw_sig and not fish_sig:
        interpretation = "null_result"
    else:
        interpretation = "inconclusive"

    print(f"\nInterpretation: {interpretation}")

    # Persist stats for assemble
    stats_file = WORK_DIR / "stats.json"
    stats_file.write_text(
        json.dumps(
            {
                "n_control": n_ctrl,
                "n_treatment": n_treat,
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
            },
            indent=2,
        ),
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

    artifact = {
        "schema_version": "1.0",
        "date": date.today().isoformat(),
        "drift_version": _drift_version(),
        "adr": "ADR-067",
        "corpus": {
            "n_tasks": len(corpus["tasks"]),
            "repos": list({t["repo_url"] for t in corpus["tasks"]}),
        },
        "model": model_used,
        "temperature": temperature_used,
        "results": {
            "n_control": stats["n_control"],
            "n_treatment": stats["n_treatment"],
            "new_findings": stats["new_findings"],
            "accept_change": stats["accept_change"],
            "interpretation": stats["interpretation"],
        },
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
    p_llm.add_argument("--model", default="gpt-4o", help="OpenAI model (default: gpt-4o).")
    p_llm.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature (default: 0).",
    )
    p_llm.add_argument("--force", action="store_true", help="Re-run even if response files exist.")

    # run-mock (H4 instrument — no API key required)
    p_mock = sub.add_parser(
        "run-mock",
        help="Generate deterministic mock agent diffs without LLM API (H4).",
    )
    p_mock.add_argument("--seed", type=int, default=42, help="Random seed (default: 42).")
    p_mock.add_argument("--force", action="store_true", help="Overwrite existing responses.")

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
