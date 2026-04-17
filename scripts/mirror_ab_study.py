#!/usr/bin/env python3
"""ADR-071: Automated A/B study — full vs. mirror output mode for fix_plan.

Does prescriptive guidance (constraints, verify_plan, agent_instruction)
help agents fix drift findings, or does diagnostic-only output suffice?

Pipeline:
    python scripts/mirror_ab_study.py generate-tasks [--max-per-repo 3]
    python scripts/mirror_ab_study.py run-llm [--model gpt-4o] [--temperature 0]
    python scripts/mirror_ab_study.py evaluate
    python scripts/mirror_ab_study.py stats
    python scripts/mirror_ab_study.py assemble

    # With local Ollama (no API key needed):
    python scripts/mirror_ab_study.py run-llm \\
        --base-url http://localhost:11434/v1 --model qwen2.5-coder:7b

Environment variables:
    OPENAI_API_KEY        Required for run-llm (unless --base-url is set)
    DRIFT_STUDY_BASE_URL  Optional OpenAI-compatible base URL
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths & Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
ORACLE_FILE = REPO_ROOT / "benchmarks" / "oracle_repos.json"
WORK_DIR = REPO_ROOT / "work_artifacts" / "mirror_study"
PROMPTS_DIR = WORK_DIR / "prompts"
RESPONSES_DIR = WORK_DIR / "responses"
OUTCOMES_FILE = WORK_DIR / "outcomes.json"
ARTIFACT_FILE = REPO_ROOT / "benchmark_results" / "mirror_ab_study.json"

MAX_CONTEXT_CHARS = 16_000  # ~4k tokens

# Repos to use (subset of oracle_repos.json for speed)
_DEFAULT_REPOS = [
    {"url": "https://github.com/psf/requests", "ref": "main", "name": "requests"},
    {"url": "https://github.com/pallets/click", "ref": "main", "name": "click"},
    {"url": "https://github.com/encode/httpx", "ref": "main", "name": "httpx"},
]

# Severity weights (same as brief_ab_study)
_SEVERITY_WEIGHTS: dict[str, int] = {
    "critical": 8,
    "high": 4,
    "medium": 2,
    "low": 1,
    "info": 0,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _shallow_clone(url: str, ref: str, dest: Path) -> None:
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", ref, "--single-branch", url, str(dest)],
        check=True,
        capture_output=True,
        timeout=300,
    )


def _read_file_context(repo_path: Path, files: list[str]) -> str:
    """Read target files as code context, truncated to MAX_CONTEXT_CHARS."""
    parts: list[str] = []
    for rel in files:
        p = repo_path / rel
        if not p.exists():
            parts.append(f"# FILE: {rel}\n# (not found)\n")
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
    fenced = re.search(r"```(?:diff|patch)\n(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    bare = re.search(r"^(diff --git .+|---\s+\S.+)", text, re.MULTILINE)
    if bare:
        return text[bare.start() :].strip()
    return None


def _normalize_diff(diff_text: str, repo_path: Path) -> str:
    """Normalize LLM-generated diffs for git apply compatibility."""
    text = diff_text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"

    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not out and not line.startswith("diff "):
            i += 1
            continue
        if re.match(r"^index [0-9a-f]+\.\.[0-9a-f]+", line):
            i += 1
            continue
        if line.startswith("new file mode") and out and out[-1].startswith("diff --git"):
            parts = out[-1].split()
            if len(parts) >= 4:
                fpath = parts[3].lstrip("b/")
                if (repo_path / fpath).exists():
                    i += 1
                    continue
        if line == "--- /dev/null" and out:
            for prev in reversed(out):
                if prev.startswith("diff --git"):
                    parts = prev.split()
                    if len(parts) >= 3:
                        fpath = parts[2].lstrip("a/")
                        if (repo_path / fpath).exists():
                            line = f"--- a/{fpath}"
                    break
        out.append(line)
        i += 1

    result = "\n".join(out)
    if result and not result.endswith("\n"):
        result += "\n"
    return result


def _patch_line_count(diff_text: str) -> int:
    count = 0
    for line in diff_text.splitlines():
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            count += 1
    return count


def _error_cost(findings: list[dict[str, Any]]) -> float:
    return sum(_SEVERITY_WEIGHTS.get(str(f.get("severity", "info")).lower(), 0) for f in findings)


def _drift_version() -> str:
    try:
        from drift import __version__

        return __version__
    except Exception:
        return "unknown"


def _load_repos() -> list[dict[str, Any]]:
    """Load repos from oracle file or fall back to defaults."""
    if ORACLE_FILE.exists():
        data = json.loads(ORACLE_FILE.read_text(encoding="utf-8"))
        repos = data.get("repos", [])
        # Use first 3 Python repos
        py_repos = [r for r in repos if r.get("name") not in ("express",)]
        return py_repos[:3]
    return _DEFAULT_REPOS


# ---------------------------------------------------------------------------
# generate-tasks: Scan repos, find real findings, build prompt pairs
# ---------------------------------------------------------------------------


def cmd_generate_tasks(args: argparse.Namespace) -> None:
    from drift.api.fix_plan import fix_plan as api_fix_plan
    from drift.api.scan import scan as api_scan
    from drift.response_shaping import apply_output_mode

    repos = _load_repos()
    max_per_repo: int = args.max_per_repo
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

    task_index: list[dict[str, Any]] = []
    task_counter = 0

    for repo_info in repos:
        name = repo_info["name"]
        print(f"\n=== {name} ({repo_info['url']}) ===")

        if args.dry_run:
            print(f"  DRY-RUN: would clone and scan {name}")
            continue

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            print(f"  Cloning {repo_info['url']} ...")
            try:
                _shallow_clone(repo_info["url"], repo_info["ref"], repo_path)
            except subprocess.CalledProcessError as exc:
                print(f"  Clone failed: {exc.stderr.decode(errors='replace')[:200]}")
                continue

            # --- Scan for findings ---
            print("  Scanning ...")
            try:
                scan_result = api_scan(
                    str(repo_path),
                    max_findings=max_per_repo * 3,  # oversample for diversity
                    response_detail="detailed",
                    strategy="diverse",
                )
            except Exception as exc:
                print(f"  Scan failed: {exc}")
                continue

            findings = scan_result.get("findings", [])
            if not findings:
                print("  No findings, skipping")
                continue

            # Select diverse findings: one per signal, prefer MEDIUM+
            seen_signals: set[str] = set()
            selected: list[dict[str, Any]] = []
            # First pass: medium/high, one per signal
            for f in findings:
                sig = f.get("signal", "")
                sev = str(f.get("severity", "")).lower()
                if sig in seen_signals:
                    continue
                if sev in ("medium", "high", "critical"):
                    seen_signals.add(sig)
                    selected.append(f)
                    if len(selected) >= max_per_repo:
                        break
            # Second pass: fill remaining with low severity
            if len(selected) < max_per_repo:
                for f in findings:
                    sig = f.get("signal", "")
                    if sig in seen_signals:
                        continue
                    seen_signals.add(sig)
                    selected.append(f)
                    if len(selected) >= max_per_repo:
                        break

            print(f"  Selected {len(selected)} findings from {len(findings)} total")

            for finding in selected:
                task_counter += 1
                tid = f"MIR-{task_counter:02d}"
                sig = finding.get("signal", "unknown")
                sev = finding.get("severity", "unknown")
                fpath = finding.get("file", "")
                title = finding.get("title", "")

                # Target files: the finding's file + related files
                target_files = [fpath] if fpath else []
                for rf in finding.get("related_files", []):
                    rf_path = rf if isinstance(rf, str) else rf.get("path", "")
                    if rf_path and rf_path not in target_files:
                        target_files.append(rf_path)
                target_files = target_files[:5]  # cap

                code_context = _read_file_context(repo_path, target_files)

                # --- Generate fix_plan for this signal (both modes) ---
                try:
                    fp_full = api_fix_plan(
                        str(repo_path),
                        signal=sig,
                        max_tasks=3,
                        target_path=fpath or None,
                    )
                except Exception as exc:
                    print(f"    [{tid}] fix_plan failed: {exc}")
                    fp_full = {"error": str(exc)}

                # Deep copy and strip for mirror
                fp_mirror = apply_output_mode(
                    json.loads(json.dumps(fp_full, default=str)),
                    "mirror",
                )
                fp_full_copy = apply_output_mode(
                    json.loads(json.dumps(fp_full, default=str)),
                    "full",
                )

                # --- Build prompt pair ---
                system_msg = (
                    "You are a precise code quality agent. "
                    "You receive a drift analysis finding and "
                    "must produce a minimal unified diff (git diff format) "
                    "that fixes the identified issue. "
                    "Output ONLY the diff block, fenced in ```diff ... ```. "
                    "Do not explain or add prose outside the fenced block."
                )

                finding_block = (
                    f"Signal: {sig}\n"
                    f"Severity: {sev}\n"
                    f"File: {fpath}\n"
                    f"Title: {title}\n"
                    f"Description: {finding.get('description', 'N/A')}\n"
                )

                # Control (full): includes prescriptive guidance
                full_user_msg = (
                    f"Drift has identified the following architectural issue:\n\n"
                    f"{finding_block}\n"
                    f"<drift_fix_plan>\n"
                    f"{json.dumps(fp_full_copy, indent=2, default=str)}\n"
                    f"</drift_fix_plan>\n\n"
                    f"<code_context>\n{code_context}\n</code_context>\n\n"
                    f"Produce a minimal unified diff that addresses this finding."
                )

                # Treatment (mirror): diagnostic only
                mirror_user_msg = (
                    f"Drift has identified the following architectural issue:\n\n"
                    f"{finding_block}\n"
                    f"<drift_analysis>\n"
                    f"{json.dumps(fp_mirror, indent=2, default=str)}\n"
                    f"</drift_analysis>\n\n"
                    f"<code_context>\n{code_context}\n</code_context>\n\n"
                    f"Produce a minimal unified diff that addresses this finding."
                )

                for arm, user_msg in [("full", full_user_msg), ("mirror", mirror_user_msg)]:
                    payload = {
                        "task_id": tid,
                        "treatment": arm,
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": user_msg},
                        ],
                        "meta": {
                            "repo_url": repo_info["url"],
                            "ref": repo_info["ref"],
                            "repo_name": name,
                            "signal": sig,
                            "severity": sev,
                            "file": fpath,
                            "title": title,
                            "target_files": target_files,
                        },
                    }
                    out_path = PROMPTS_DIR / f"{tid}_{arm}.json"
                    out_path.write_text(
                        json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )

                task_index.append(
                    {
                        "id": tid,
                        "repo_name": name,
                        "repo_url": repo_info["url"],
                        "ref": repo_info["ref"],
                        "signal": sig,
                        "severity": sev,
                        "file": fpath,
                        "title": title,
                        "target_files": target_files,
                        "full_context_chars": len(full_user_msg),
                        "mirror_context_chars": len(mirror_user_msg),
                        "context_reduction_pct": round(
                            100 * (1 - len(mirror_user_msg) / max(len(full_user_msg), 1)), 1
                        ),
                    }
                )

                print(
                    f"    [{tid}] {sig}/{sev} → {fpath}"
                    f" (full={len(full_user_msg):,}ch, mirror={len(mirror_user_msg):,}ch,"
                    f" Δ={task_index[-1]['context_reduction_pct']}%)"
                )

    # Save task index
    index_path = WORK_DIR / "task_index.json"
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(task_index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n{len(task_index)} tasks generated → {PROMPTS_DIR}")
    if task_index:
        avg_reduction = sum(t["context_reduction_pct"] for t in task_index) / len(task_index)
        print(f"Average context reduction: {avg_reduction:.1f}%")


# ---------------------------------------------------------------------------
# run-llm: Send prompts to LLM, collect diffs
# ---------------------------------------------------------------------------


def cmd_run_llm(args: argparse.Namespace) -> None:
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("openai package required. Run: uv add --dev openai")

    base_url = getattr(args, "base_url", None) or os.environ.get("DRIFT_STUDY_BASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key and not base_url:
        sys.exit(
            "OPENAI_API_KEY not set. "
            "Use --base-url for local backend (e.g. http://localhost:11434/v1)"
        )
    if not api_key:
        api_key = "local"  # pragma: allowlist secret

    model = args.model
    client = OpenAI(api_key=api_key, base_url=base_url)

    if not PROMPTS_DIR.exists():
        sys.exit(f"No prompts found: {PROMPTS_DIR}. Run generate-tasks first.")

    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    prompt_files = sorted(PROMPTS_DIR.glob("*.json"))
    if not prompt_files:
        sys.exit("No prompt files. Run generate-tasks first.")

    repeats: int = args.repeats
    total = len(prompt_files) * repeats
    print(f"Running {model} on {len(prompt_files)} prompts × {repeats} repeats ...")

    for pf in prompt_files:
        payload = json.loads(pf.read_text(encoding="utf-8"))

        for r in range(repeats):
            stem = f"{pf.stem}_r{r}" if repeats > 1 else pf.stem
            diff_out = RESPONSES_DIR / f"{stem}.diff"
            meta_out = RESPONSES_DIR / f"{stem}_meta.json"

            if diff_out.exists() and not args.force:
                print(f"  [{stem}] exists, skipping")
                continue

            print(f"  [{stem}] calling {model} ...")
            try:
                extra: dict[str, Any] = {}
                if args.temperature > 0 and repeats > 1:
                    extra["seed"] = 42 + r

                resp = client.chat.completions.create(
                    model=model,
                    temperature=args.temperature,
                    messages=payload["messages"],
                    max_tokens=2048,
                    **extra,
                )
                text = resp.choices[0].message.content or ""
                diff_block = _extract_diff_block(text)
                status = "ok" if diff_block else "parse_error"
                diff_out.write_text(
                    diff_block or text,
                    encoding="utf-8",
                )
            except Exception as exc:
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
                        "repeat": r,
                        "meta": payload.get("meta", {}),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"  [{stem}] status={status}")

    print(f"\nResponses → {RESPONSES_DIR} ({total} total)")


# ---------------------------------------------------------------------------
# evaluate: Apply diffs, measure with drift diff
# ---------------------------------------------------------------------------


def cmd_evaluate(args: argparse.Namespace) -> None:
    import shutil

    from drift.api.diff import diff as api_diff

    if not RESPONSES_DIR.exists():
        sys.exit(f"No responses: {RESPONSES_DIR}. Run run-llm first.")

    diff_files = sorted(RESPONSES_DIR.glob("*.diff"))
    if not diff_files:
        sys.exit("No diff files. Run run-llm first.")

    outcomes: list[dict[str, Any]] = []
    print(f"Evaluating {len(diff_files)} diffs ...")

    # Cache cloned repos to avoid re-cloning for each finding in same repo
    _clone_cache: dict[str, Path] = {}
    _tmpdir_obj = tempfile.TemporaryDirectory()
    tmpdir = Path(_tmpdir_obj.name)

    try:
        for df in diff_files:
            stem = df.stem
            meta_file = RESPONSES_DIR / f"{stem}_meta.json"
            if not meta_file.exists():
                print(f"  [{stem}] no meta, skipping")
                continue

            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            task_id = meta["task_id"]
            treatment = meta["treatment"]
            task_meta = meta.get("meta", {})

            if meta["status"] != "ok":
                outcomes.append(
                    {
                        "task_id": task_id,
                        "treatment": treatment,
                        "repeat": meta.get("repeat", 0),
                        "status": meta["status"],
                        "signal": task_meta.get("signal"),
                        "severity": task_meta.get("severity"),
                        **_null_metrics(),
                    }
                )
                print(f"  [{stem}] upstream status={meta['status']}")
                continue

            diff_content = df.read_text(encoding="utf-8").strip()
            if not diff_content:
                outcomes.append(
                    {
                        "task_id": task_id,
                        "treatment": treatment,
                        "repeat": meta.get("repeat", 0),
                        "status": "empty_diff",
                        "signal": task_meta.get("signal"),
                        "severity": task_meta.get("severity"),
                        **_null_metrics(),
                    }
                )
                print(f"  [{stem}] empty diff")
                continue

            patch_loc = _patch_line_count(diff_content)
            repo_url = task_meta.get("repo_url", "")
            repo_ref = task_meta.get("ref", "main")
            cache_key = f"{repo_url}@{repo_ref}"

            if args.dry_run:
                outcomes.append(
                    {
                        "task_id": task_id,
                        "treatment": treatment,
                        "repeat": meta.get("repeat", 0),
                        "status": "dry_run",
                        "signal": task_meta.get("signal"),
                        "severity": task_meta.get("severity"),
                        "patch_size_loc": patch_loc,
                        **{
                            k: None
                            for k in [
                                "new_findings_count",
                                "accept_change",
                                "error_cost",
                                "resolved_count",
                                "net_cost",
                            ]
                        },
                    }
                )
                print(f"  [{stem}] DRY-RUN")
                continue

            # Clone (with cache)
            if cache_key not in _clone_cache:
                repo_path = tmpdir / task_meta.get("repo_name", "repo")
                if repo_path.exists():
                    shutil.rmtree(repo_path)
                print(f"  [{stem}] cloning {repo_url} ...")
                try:
                    _shallow_clone(repo_url, repo_ref, repo_path)
                    _clone_cache[cache_key] = repo_path
                except subprocess.CalledProcessError as exc:
                    err = exc.stderr.decode(errors="replace")[:200]
                    print(f"  [{stem}] clone failed: {err[:80]}")
                    outcomes.append(
                        {
                            "task_id": task_id,
                            "treatment": treatment,
                            "repeat": meta.get("repeat", 0),
                            "status": f"clone_error: {err[:80]}",
                            "signal": task_meta.get("signal"),
                            **_null_metrics(),
                        }
                    )
                    continue

            # For each evaluation we need a clean worktree — copy from cache
            eval_dir = tmpdir / f"eval_{stem}"
            if eval_dir.exists():
                shutil.rmtree(eval_dir)
            shutil.copytree(_clone_cache[cache_key], eval_dir)
            repo_path = eval_dir

            # Apply diff
            normalized = _normalize_diff(diff_content, repo_path)
            diff_file = tmpdir / f"{stem}_patch.diff"
            diff_file.write_text(normalized, encoding="utf-8", newline="\n")

            applied = False
            apply_result = None
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

            if not applied:
                # Try patch binary as fallback
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
                    applied = apply_result.returncode == 0

            if not applied:
                err = (
                    apply_result.stderr.decode(errors="replace")[:200]
                    if apply_result
                    else "no apply_result"
                )
                print(f"  [{stem}] apply failed: {err[:80]}")
                outcomes.append(
                    {
                        "task_id": task_id,
                        "treatment": treatment,
                        "repeat": meta.get("repeat", 0),
                        "status": "apply_error",
                        "signal": task_meta.get("signal"),
                        "severity": task_meta.get("severity"),
                        "patch_size_loc": patch_loc,
                        "apply_stderr": err[:200],
                        **{
                            k: None
                            for k in [
                                "new_findings_count",
                                "accept_change",
                                "error_cost",
                                "resolved_count",
                                "net_cost",
                            ]
                        },
                    }
                )
                continue

            # Run drift diff
            print(f"  [{stem}] running drift diff ...")
            try:
                result = api_diff(str(repo_path), uncommitted=True, response_detail="detailed")
                new_findings = result.get("new_findings", result.get("new", []))
                resolved_findings = result.get("resolved_findings", result.get("resolved", []))
                new_count = len(new_findings)
                resolved_count = len(resolved_findings)
                accept = bool(result.get("accept_change", False))
                cost_new = _error_cost(new_findings)
                cost_resolved = _error_cost(resolved_findings)

                outcomes.append(
                    {
                        "task_id": task_id,
                        "treatment": treatment,
                        "repeat": meta.get("repeat", 0),
                        "status": "ok",
                        "signal": task_meta.get("signal"),
                        "severity": task_meta.get("severity"),
                        "new_findings_count": new_count,
                        "resolved_count": resolved_count,
                        "accept_change": accept,
                        "error_cost": cost_new,
                        "net_cost": round(cost_new - cost_resolved, 4),
                        "patch_size_loc": patch_loc,
                        "score_delta": result.get("delta"),
                        "drift_status": result.get("status"),
                    }
                )
                print(
                    f"  [{stem}] new={new_count} resolved={resolved_count} "
                    f"accept={accept} patch={patch_loc}"
                )
            except Exception as exc:
                print(f"  [{stem}] drift diff error: {exc}")
                outcomes.append(
                    {
                        "task_id": task_id,
                        "treatment": treatment,
                        "repeat": meta.get("repeat", 0),
                        "status": f"drift_error: {exc}",
                        "signal": task_meta.get("signal"),
                        "severity": task_meta.get("severity"),
                        "patch_size_loc": patch_loc,
                        **{
                            k: None
                            for k in [
                                "new_findings_count",
                                "accept_change",
                                "error_cost",
                                "resolved_count",
                                "net_cost",
                            ]
                        },
                    }
                )

            # Clean up eval dir to save disk
            shutil.rmtree(eval_dir, ignore_errors=True)
    finally:
        _tmpdir_obj.cleanup()

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTCOMES_FILE.write_text(
        json.dumps(outcomes, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    ok_count = sum(1 for o in outcomes if o["status"] == "ok")
    print(f"\nOutcomes → {OUTCOMES_FILE} ({ok_count}/{len(outcomes)} ok)")


def _null_metrics() -> dict[str, None]:
    return {
        "new_findings_count": None,
        "accept_change": None,
        "error_cost": None,
        "resolved_count": None,
        "net_cost": None,
        "patch_size_loc": None,
    }


# ---------------------------------------------------------------------------
# stats: Statistical analysis (paired within-subjects design)
# ---------------------------------------------------------------------------


def _cohens_d(a: list[float], b: list[float]) -> float:
    n_a, n_b = len(a), len(b)
    if n_a < 2 or n_b < 2:
        return float("nan")
    mean_a, mean_b = sum(a) / n_a, sum(b) / n_b
    var_a = sum((x - mean_a) ** 2 for x in a) / (n_a - 1)
    var_b = sum((x - mean_b) ** 2 for x in b) / (n_b - 1)
    pooled = math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
    return (mean_a - mean_b) / pooled if pooled else 0.0


def cmd_stats(args: argparse.Namespace) -> None:
    try:
        from scipy.stats import fisher_exact, mannwhitneyu, wilcoxon
    except ImportError:
        sys.exit("scipy required. Run: uv add --dev scipy")

    if not OUTCOMES_FILE.exists():
        sys.exit(f"No outcomes: {OUTCOMES_FILE}. Run evaluate first.")

    outcomes = json.loads(OUTCOMES_FILE.read_text(encoding="utf-8"))
    ok = [o for o in outcomes if o["status"] == "ok"]
    full = [o for o in ok if o["treatment"] == "full"]
    mirror = [o for o in ok if o["treatment"] == "mirror"]

    n_full, n_mirror = len(full), len(mirror)
    error_rate = 1 - len(ok) / max(len(outcomes), 1)

    print(f"Status: {len(ok)}/{len(outcomes)} ok  |  full={n_full}  mirror={n_mirror}")
    if error_rate > 0.20:
        print(f"\nWARNING: error rate {error_rate:.0%} > 20%", file=sys.stderr)
    if n_full == 0 or n_mirror == 0:
        sys.exit("Cannot compute stats with empty group.")

    # --- Unpaired tests ---
    full_new = [o["new_findings_count"] for o in full]
    mirror_new = [o["new_findings_count"] for o in mirror]
    full_accept = sum(1 for o in full if o["accept_change"])
    mirror_accept = sum(1 for o in mirror if o["accept_change"])

    mw_stat, mw_p = mannwhitneyu(full_new, mirror_new, alternative="two-sided")
    contingency = [
        [full_accept, n_full - full_accept],
        [mirror_accept, n_mirror - mirror_accept],
    ]
    fisher_or, fisher_p = fisher_exact(contingency, alternative="two-sided")
    d = _cohens_d(full_new, mirror_new)

    print("\n--- new_findings_count (unpaired) ---")
    print(f"  full mean:   {sum(full_new) / n_full:.3f}")
    print(f"  mirror mean: {sum(mirror_new) / n_mirror:.3f}")
    print(f"  Mann-Whitney U: {mw_stat:.1f}  p={mw_p:.4f}")
    print(f"  Cohen's d: {d:.3f}")

    print("\n--- accept_change ---")
    print(f"  full rate:   {full_accept}/{n_full} = {full_accept / n_full:.2%}")
    print(f"  mirror rate: {mirror_accept}/{n_mirror} = {mirror_accept / n_mirror:.2%}")
    print(f"  Fisher p: {fisher_p:.4f}  OR: {fisher_or:.3f}")

    # --- Paired analysis (same finding, full vs mirror) ---
    from collections import defaultdict

    buckets: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for o in ok:
        buckets[o["task_id"]][o["treatment"]].append(o)

    paired_tasks = [tid for tid, arms in buckets.items() if "full" in arms and "mirror" in arms]
    paired_stats: dict[str, Any] = {}

    if len(paired_tasks) >= 5:

        def _mean(vals: list) -> float:
            return sum(vals) / len(vals) if vals else 0.0

        paired_full_cost = [
            _mean([r["error_cost"] for r in buckets[t]["full"]]) for t in paired_tasks
        ]
        paired_mirror_cost = [
            _mean([r["error_cost"] for r in buckets[t]["mirror"]]) for t in paired_tasks
        ]
        paired_full_patch = [
            _mean([r["patch_size_loc"] for r in buckets[t]["full"]]) for t in paired_tasks
        ]
        paired_mirror_patch = [
            _mean([r["patch_size_loc"] for r in buckets[t]["mirror"]]) for t in paired_tasks
        ]
        paired_full_resolved = [
            _mean([r["resolved_count"] for r in buckets[t]["full"]]) for t in paired_tasks
        ]
        paired_mirror_resolved = [
            _mean([r["resolved_count"] for r in buckets[t]["mirror"]]) for t in paired_tasks
        ]

        diffs_cost = [f - m for f, m in zip(paired_full_cost, paired_mirror_cost, strict=True)]
        diffs_patch = [f - m for f, m in zip(paired_full_patch, paired_mirror_patch, strict=True)]
        diffs_resolved = [
            m - f for f, m in zip(paired_full_resolved, paired_mirror_resolved, strict=True)
        ]

        def _safe_wilcoxon(diffs: list[float]) -> tuple[float, float]:
            nonzero = [x for x in diffs if x != 0]
            if len(nonzero) < 5:
                return (float("nan"), float("nan"))
            stat, p = wilcoxon(nonzero, alternative="two-sided")
            return (float(stat), float(p))

        w_cost, wp_cost = _safe_wilcoxon(diffs_cost)
        w_patch, wp_patch = _safe_wilcoxon(diffs_patch)
        w_resolved, wp_resolved = _safe_wilcoxon(diffs_resolved)
        d_cost = _cohens_d(paired_full_cost, paired_mirror_cost)

        print(f"\n--- paired analysis ({len(paired_tasks)} tasks) ---")
        print(
            "  error_cost: "
            f"full={_mean(paired_full_cost):.2f}  "
            f"mirror={_mean(paired_mirror_cost):.2f}"
        )
        print(f"    Wilcoxon p={wp_cost:.4f}  Cohen's d={d_cost:.3f}")
        print(
            "  resolved: "
            f"full={_mean(paired_full_resolved):.2f}  "
            f"mirror={_mean(paired_mirror_resolved):.2f}"
        )
        print(f"    Wilcoxon p={wp_resolved:.4f}")
        print(
            "  patch_size: "
            f"full={_mean(paired_full_patch):.1f}  "
            f"mirror={_mean(paired_mirror_patch):.1f}"
        )
        print(f"    Wilcoxon p={wp_patch:.4f}")

        paired_stats = {
            "n_paired_tasks": len(paired_tasks),
            "error_cost": {
                "full_mean": round(_mean(paired_full_cost), 4),
                "mirror_mean": round(_mean(paired_mirror_cost), 4),
                "wilcoxon_p": wp_cost,
                "cohens_d": round(d_cost, 4),
                "significant": bool(wp_cost < 0.05) if not math.isnan(wp_cost) else False,
            },
            "resolved_count": {
                "full_mean": round(_mean(paired_full_resolved), 4),
                "mirror_mean": round(_mean(paired_mirror_resolved), 4),
                "wilcoxon_p": wp_resolved,
                "significant": bool(wp_resolved < 0.05) if not math.isnan(wp_resolved) else False,
            },
            "patch_size": {
                "full_mean": round(_mean(paired_full_patch), 2),
                "mirror_mean": round(_mean(paired_mirror_patch), 2),
                "wilcoxon_p": wp_patch,
            },
        }
    else:
        print(f"\n--- paired: skipped ({len(paired_tasks)} tasks, need ≥5) ---")

    # --- Interpretation ---
    paired_sig = paired_stats.get("error_cost", {}).get("significant", False)
    paired_effect = abs(paired_stats.get("error_cost", {}).get("cohens_d", 0)) >= 0.3
    mw_sig = bool(mw_p < 0.05)
    fish_sig = bool(fisher_p < 0.05)
    medium_effect = abs(d) >= 0.3

    if paired_sig and paired_effect:
        # Check direction
        full_m = paired_stats.get("error_cost", {}).get("full_mean", 0)
        mirror_m = paired_stats.get("error_cost", {}).get("mirror_mean", 0)
        interpretation = "mirror_better" if full_m > mirror_m else "full_better"
    elif not mw_sig and not fish_sig and not paired_sig:
        interpretation = "null_result"
    elif (mw_sig or fish_sig) and medium_effect:
        interpretation = "effect_detected_unpaired"
    else:
        interpretation = "inconclusive"

    print(f"\nInterpretation: {interpretation}")

    stats_payload: dict[str, Any] = {
        "n_full": n_full,
        "n_mirror": n_mirror,
        "error_rate": round(error_rate, 4),
        "new_findings": {
            "full_mean": round(sum(full_new) / n_full, 4),
            "mirror_mean": round(sum(mirror_new) / n_mirror, 4),
            "mann_whitney_u": float(mw_stat),
            "p_value": float(mw_p),
            "cohens_d": round(d, 4),
            "significant": mw_sig,
        },
        "accept_change": {
            "full_rate": round(full_accept / n_full, 4),
            "mirror_rate": round(mirror_accept / n_mirror, 4),
            "fisher_p": float(fisher_p),
            "significant": fish_sig,
        },
        "interpretation": interpretation,
    }
    if paired_stats:
        stats_payload["paired"] = paired_stats

    stats_file = WORK_DIR / "stats.json"
    stats_file.write_text(json.dumps(stats_payload, indent=2), encoding="utf-8")
    print(f"Stats → {stats_file}")


# ---------------------------------------------------------------------------
# assemble: Build final evidence artifact
# ---------------------------------------------------------------------------


def cmd_assemble(args: argparse.Namespace) -> None:
    stats_file = WORK_DIR / "stats.json"
    if not stats_file.exists():
        sys.exit(f"No stats: {stats_file}. Run stats first.")
    if not OUTCOMES_FILE.exists():
        sys.exit(f"No outcomes: {OUTCOMES_FILE}. Run evaluate first.")

    stats = json.loads(stats_file.read_text(encoding="utf-8"))
    outcomes = json.loads(OUTCOMES_FILE.read_text(encoding="utf-8"))

    task_index_file = WORK_DIR / "task_index.json"
    task_index = (
        json.loads(task_index_file.read_text(encoding="utf-8")) if task_index_file.exists() else []
    )

    # Infer model
    model_used = "unknown"
    temperature_used = 0.0
    with contextlib.suppress(StopIteration, json.JSONDecodeError, OSError):
        first_meta = next(RESPONSES_DIR.glob("*_meta.json"))
        m = json.loads(first_meta.read_text(encoding="utf-8"))
        model_used = m.get("model", "unknown")
        temperature_used = m.get("temperature", 0.0)

    artifact = {
        "schema_version": "1.0",
        "date": date.today().isoformat(),
        "drift_version": _drift_version(),
        "adr": "ADR-071",
        "experiment": "mirror_output_mode_ab",
        "description": (
            "Does prescriptive guidance (constraints, verify_plan, agent_instruction) "
            "in fix_plan output help or hinder agents fixing drift findings? "
            "Compares full (prescriptive) vs mirror (diagnostic-only) output mode."
        ),
        "model": model_used,
        "temperature": temperature_used,
        "task_index": task_index,
        "results": stats,
        "raw_outcomes": outcomes,
    }

    ARTIFACT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_FILE.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Artifact → {ARTIFACT_FILE}")
    print(f"Interpretation: {stats.get('interpretation', 'unknown')}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mirror_ab_study",
        description="ADR-071: A/B study — full vs. mirror output mode for fix_plan.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate-tasks", help="Scan repos, build prompt pairs.")
    p_gen.add_argument(
        "--max-per-repo", type=int, default=5, help="Max findings per repo (default: 5)."
    )
    p_gen.add_argument("--dry-run", action="store_true")
    p_gen.add_argument("--force", action="store_true")

    p_llm = sub.add_parser("run-llm", help="Send prompts to LLM.")
    p_llm.add_argument("--model", default="gpt-4o")
    p_llm.add_argument("--base-url", default=None)
    p_llm.add_argument("--temperature", type=float, default=0.0)
    p_llm.add_argument("--repeats", type=int, default=1)
    p_llm.add_argument("--force", action="store_true")

    p_eval = sub.add_parser("evaluate", help="Apply diffs, measure with drift diff.")
    p_eval.add_argument("--dry-run", action="store_true")

    sub.add_parser("stats", help="Statistical analysis.")
    sub.add_parser("assemble", help="Build evidence artifact JSON.")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    dispatch = {
        "generate-tasks": cmd_generate_tasks,
        "run-llm": cmd_run_llm,
        "evaluate": cmd_evaluate,
        "stats": cmd_stats,
        "assemble": cmd_assemble,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
