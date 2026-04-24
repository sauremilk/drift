---
name: drift-finding-message-authoring
description: "Write and review reason and next_action strings in Drift signal files. Use when authoring a new signal, sharpening existing finding messages, or reviewing unclear finding output for actionability and clarity."
argument-hint: "Describe the signal file, the current finding text, and whether you want authoring help, a review, or both."
---

# Drift Finding Message Authoring

Use this skill to write and review `reason` and `next_action` strings that are precise, actionable, and consistent with existing Drift finding output.

## When To Use

- a new signal needs initial finding text
- an existing signal has unclear, vague, or non-actionable messages
- the ROADMAP task to sharpen finding explanations is being worked through
- a community report says a finding is confusing or hard to act on

## Not For

- changing scoring, thresholds, or signal heuristics
- inventing new finding facts not supported by the signal logic
- rewriting output schemas or CLI formatting
- broad documentation work outside the signal file itself

## Quality Criteria

| Criterion | Pass condition |
|---|---|
| Cause specificity | Names the concrete code pattern, not a category |
| Jargon-free | Understandable without reading Drift docs |
| Actionability | `next_action` can be executed immediately |
| Length | Each field is at most 2 sentences |
| No hedging | Avoids phrases like "consider", "may", "possibly", or "might want to" |

## Core Rules

1. **Preserve factual meaning.** Improve clarity and actionability without changing what the signal actually detected.
2. **Name the code pattern directly.** Prefer the observed structure or smell over abstract category labels.
3. **Make the next step concrete.** `next_action` should tell the user exactly what to inspect, consolidate, remove, or move.
4. **Keep output concise.** Do not expand the message into explanation prose that belongs in docs or triage notes.
5. **Review both fields together.** A strong `reason` with a vague `next_action`, or the reverse, is incomplete.

## Standard Workflow

### 1. Load The Existing Strings

Read the current `reason` and `next_action` from the target signal file under `src/drift/signals/`.

If one field is missing, treat that as a failure and author the missing field from the signal's actual detection logic.

### 2. Evaluate Against The Quality Criteria

Assess each criterion with this format:

- `✅ pass` or `❌ fail`
- quote the exact failing phrase when a criterion fails
- explain the failure in one sentence tied to the criterion

Do not mark a criterion as passed without checking the literal wording.

### 3. Produce An Improved Version

Rewrite both fields so they keep the same factual content while improving clarity, specificity, and actionability.

Constraints:

- no hedging language
- no new claims not supported by the signal
- no schema or field-name changes
- no more than 2 sentences per field

### 4. Emit Diff-Ready Output

Return the result in this exact structure:

```text
BEFORE
  reason:      "[original text]"
  next_action: "[original text]"

AFTER
  reason:      "[improved text]"
  next_action: "[improved text]"

CHANGES
  - [one bullet per change explaining what was fixed and why]
```

### 5. Final Review

Before concluding, verify all of the following:

- the improved `reason` names a concrete pattern or behavior
- the improved `next_action` tells the user what to do next without soft verbs
- neither field exceeds 2 sentences
- the rewrite does not introduce facts absent from the signal logic

If any check fails, revise the strings before returning them.

## Review Checklist

- [ ] The skill is being used for finding-message authoring, not signal logic changes
- [ ] The existing strings were read from the actual signal file
- [ ] Each quality criterion was evaluated explicitly
- [ ] Failing phrases were quoted verbatim
- [ ] The improved text preserves factual meaning
- [ ] `next_action` is concrete and immediately executable
- [ ] The result is formatted as BEFORE / AFTER / CHANGES

## References

- `.github/instructions/drift-policy.instructions.md`
- `.github/instructions/drift-prompt-engineering.instructions.md`
- `.github/skills/drift-signal-development-full-lifecycle/SKILL.md`
- `src/drift/signals/`
- `ROADMAP.md`
