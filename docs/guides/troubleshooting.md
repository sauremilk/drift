# Troubleshooting Guide

Common problems when starting with drift, and how to fix them.

---

## "I see a high score but don't know where to start"

**Symptom:** `drift status` returns RED or YELLOW, but the finding descriptions feel abstract.

**What to do:**

1. Run `drift explain <SIGNAL>` for the top finding to read a concrete description and example.
2. Add `--repo-context` for examples from your own codebase:
   ```bash
   drift explain PFS --repo-context
   ```
3. Copy the prompt from `drift status` and paste it directly into your AI assistant. Drift generates it for you.

---

## "My score is very high on the first run"

**What this means:** A first-run score in the range 0.30–0.65 is normal for most projects, especially
AI-assisted ones. Drift measures structural debt accumulated over time, not style issues.

**What to do:**

- Run `drift setup` if you haven't configured a profile yet. The **vibe-coding** profile uses calibrated
  thresholds for AI-assisted projects.
- Focus on the top 2–3 findings from `drift status`, not the score itself.
- Run `drift status` again after you fix a finding to see the score drop.

---

## "drift status shows nothing — no findings"

**Symptom:** Score is very low, no findings listed. Seems too good to be true.

**Possible causes:**

- The `include` pattern in your `drift.yaml` doesn't match your source files. Check:
  ```bash
  drift analyze --repo . --format json | python -m json.tool | grep '"total_files"'
  ```
  If `total_files` is 0 or very small, extend your `include` patterns.

- Your project is genuinely healthy. Run `drift analyze --repo .` for the full signal breakdown.

---

## "The AI prompts don't seem to work with my AI assistant"

**What to do:**

- Paste the full prompt including the `##` header. It provides necessary context.
- Add the relevant file content after the prompt: "Here is the file: [paste code]"
- If the AI assistant doesn't understand, run `drift explain <SIGNAL>` and paste the
  "What it detects" section as additional context.

---

## "TypeScript/JavaScript files are skipped"

**Symptom:** Warning: `⚠ Skipped N file(s): typescript (N)`

**Fix:** Install the TypeScript extension:

```bash
pip install drift-analyzer[typescript]
```

---

## "drift setup created a config but I don't see a difference"

After `drift setup`, re-run analysis:

```bash
drift status
```

If you used `--non-interactive`, the profile is `vibe-coding` — run `drift setup` interactively to
pick a stricter profile if needed.

---

## "I want to ignore a specific finding"

Add a comment directly in your source code:

```python
some_function()  # drift:ignore
```

Or suppress an entire file via `exclude` in `drift.yaml`:

```yaml
exclude:
  - "**/migrations/**"
  - "**/generated/**"
```

---

## Still stuck?

- Run `drift analyze --repo . --format json` and check the raw signal scores.
- Open a [GitHub Issue](https://github.com/mick-gsk/drift/issues) — attach the JSON output.
