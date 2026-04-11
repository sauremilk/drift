# Onboarding Troubleshooting

Common problems when you're just getting started with drift, and how to fix them.

> For technical errors (config validation, signal failures, etc.), see
> [Troubleshooting](../getting-started/troubleshooting.md).

---

## "I see a high score but don't know where to start"

**Symptom:** `drift status` returns RED or YELLOW, but the finding descriptions feel abstract.

**What to do:**

1. Run `drift explain <SIGNAL>` for the top finding to read a concrete description and example.
2. Add `--repo-context` for examples from your own codebase:
   ```bash
   drift explain PFS --repo-context
   ```
3. Copy the prompt from `drift status` and paste it directly into your AI assistant.
   Drift generates a ready-to-use prompt for each finding.

---

## "My score is very high on the first run"

**What this means:** A first-run score of 0.30–0.65 is normal for most projects, especially
AI-assisted ones. Drift measures accumulated structural debt, not style.

**What to do:**

- Run `drift setup` if you haven't configured a profile yet.
  The **vibe-coding** profile uses calibrated thresholds for AI-assisted projects.
- Focus on the top 2–3 findings from `drift status`, not the absolute score.
- Re-run `drift status` after each fix to see the score drop.

---

## "drift status shows nothing — no findings"

**Possible causes:**

- The `include` pattern in `drift.yaml` doesn't match your source files. Verify:
  ```bash
  drift analyze --repo . --format json | python -m json.tool | grep '"total_files"'
  ```
  If `total_files` is very small, extend your `include` patterns in `drift.yaml`.

- Your project is genuinely healthy. Run `drift analyze --repo .` for the full signal breakdown.

---

## "The AI prompts don't work well with my AI assistant"

**What to do:**

- Paste the full prompt including the `##` header — it provides context the AI needs.
- Append the relevant file content: *"Here is the file: [paste code]"*
- If the AI still seems confused, run `drift explain <SIGNAL>` and paste the
  *"What it detects"* section as additional context.

---

## "TypeScript/JavaScript files are skipped"

**Symptom:** `⚠ Skipped N file(s): typescript (N)`

**Fix:**

```bash
pip install drift-analyzer[typescript]
```

---

## "drift setup created a config but nothing changed"

After `drift setup`, re-run the analysis:

```bash
drift status
```

If you used `--non-interactive`, the profile defaults to `vibe-coding`.
Run `drift setup` interactively to choose a stricter profile if needed.

---

## "I want to ignore a specific finding"

Add a suppression comment in your source code:

```python
some_function()  # drift:ignore
```

Or exclude whole paths via `drift.yaml`:

```yaml
exclude:
  - "**/migrations/**"
  - "**/generated/**"
```

---

## Still stuck?

Run a full analysis and attach the JSON output when opening an issue:

```bash
drift analyze --repo . --format json > drift_output.json
```

[Open a GitHub Issue](https://github.com/mick-gsk/drift/issues)
