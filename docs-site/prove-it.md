---
title: "Prove It Yourself"
description: "Analyze a public GitHub repo directly in your browser. No install, no config, no sign-up."
---

# Your Repo. Your Results.

A benchmark on someone else's code proves nothing to you.
Pick a repo you know — and judge the findings yourself.

---

## 1. Enter a public GitHub repo

Paste the URL of any public Python repo on GitHub. The analysis runs entirely in your browser — code is fetched via GitHub's public API and never sent to any server.

<form class="drift-prove-form" data-max-findings="5" data-results-target="drift-prove-full-results">
  <div class="drift-prove-url-row">
    <input type="text" class="drift-prove-url" placeholder="https://github.com/owner/repo" required>
    <button type="submit" class="drift-prove-btn">Analyze</button>
  </div>
</form>
<div class="drift-prove-progress" hidden>
  <span class="drift-prove-spinner"></span>
  <span class="drift-prove-status">Preparing…</span>
</div>
<div id="drift-prove-full-results" class="drift-prove-results" hidden></div>
<p class="drift-prove-privacy">🔒 Code is fetched via GitHub's public API and analyzed in your browser. No server, no analytics, no cookies.</p>

!!! info "Rate limits"
    GitHub allows 60 API requests per hour without authentication. A typical analysis uses 10–35 requests. If you hit the limit, wait a few minutes and try again.

---

## 2. Check the findings yourself

Don't take drift's word for it. Here are three things to verify against your own knowledge:

### The finding you already knew about

Every codebase has that one module that grew too fast, that one file everyone avoids, that one pattern that got copy-pasted three times. Look at the top findings — **do you recognize the files?**

If drift flagged something you've been meaning to fix anyway, that's not a coincidence. That's signal.

### The duplicate you didn't notice

Look for **MDS** (Mutant Duplicates) findings. These are functions with the same name defined across different files — the classic artifact of AI-assisted development where each prompt produces a self-contained solution.

Ask yourself: are those functions really different? Do they need to exist separately?

### The import that shouldn't be there

Look for **CIR** (Circular Import) findings. These flag modules that import each other — creating hidden coupling that makes refactoring dangerous.

Check: is the circular dependency intentional, or did it creep in during a fast iteration?

---

## 3. Want the full analysis?

The browser preview analyzes a subset of Python files using lightweight pattern detection. For the **full 23-signal analysis** including git history, AST parsing, and co-change patterns:

=== "Zero-install (uvx)"

    ```bash
    uvx drift-analyzer analyze --repo . --format json --compact
    ```

=== "pip"

    ```bash
    pip install drift-analyzer
    drift analyze --repo . --format json --compact
    ```

=== "pipx"

    ```bash
    pipx run drift-analyzer analyze --repo . --format json --compact
    ```

=== "Docker"

    ```bash
    docker run --rm -v "$(pwd):/repo" ghcr.io/mick-gsk/drift:latest analyze --repo /repo --format json --compact
    ```

**Or drop a local result file here:**

<div class="drift-prove-drop" data-max-findings="10" data-results-target="drift-prove-local-results" style="margin-top: 1rem;">
  <span class="drift-prove-drop-icon">&#128462;</span>
  Drop <strong>drift-results.json</strong> here<br>
  <button data-prove-paste>paste from clipboard</button> · <label>browse<input type="file" accept=".json" data-prove-file></label>
</div>
<div id="drift-prove-local-results" class="drift-prove-results" hidden></div>

---

## 4. What if drift found nothing?

That's fine. It happens when:

- The repo has fewer than ~10 Python files
- The codebase is genuinely well-structured
- The analyzed subset (browser preview) didn't cover the most affected files

None of these invalidate the tool. Small repos simply have less surface for structural drift to develop. Try it on a larger project — or run the full local analysis.

## 5. What if drift found something real?

That's the proof. Not our proof — yours.

**Next steps:**

- [Finding Triage](getting-started/finding-triage.md) — how to read and prioritize findings
- [Prompts to Try](getting-started/prompts.md) — ask your AI agent to explain and fix findings
- [CI Integration](integrations.md) — add drift to your pipeline so findings don't regress

## 6. What if a finding is wrong?

False positives exist. Drift is at 97.3% precision — which means roughly 1 in 37 findings may be inaccurate.

If you spot one:

- [Troubleshooting](getting-started/troubleshooting.md) — common causes and workarounds
- [Open an issue](https://github.com/mick-gsk/drift/issues/new) — we treat every false positive report as a bug

---

<p style="text-align: center; font-size: 0.92rem; color: var(--md-default-fg-color--light); margin-top: 2rem;">
  <em>A proof you construct can be disputed. A proof you initiate cannot be denied.</em>
</p>
