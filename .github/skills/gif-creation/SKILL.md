---
name: gif-creation
description: "Create or update animated GIFs for demos, docs, terminal recordings, or README assets. Use when users ask for GIF creation, demo GIFs, terminal GIFs, VHS tapes, Pillow renderers, Windows-compatible animation workflows, or PowerShell-based recording."
argument-hint: "Describe the source and target, for example: render demos/demo.tape to demos/demo.gif or create a Windows-compatible CLI demo GIF from the existing drift scripts."
---

# GIF Creation Skill

## Purpose

Create reproducible animated GIFs without introducing avoidable compatibility problems.

In this workspace, prefer the existing Windows-friendly workflow before adding new tooling:

- PowerShell commands instead of Bash-first snippets
- repo-local scripts before ad hoc one-off commands
- workspace Python in .venv before system Python
- Pillow fallback before inventing a new renderer when VHS is unavailable

## When to Use

- A user asks to create or update a GIF
- A docs or README change needs an animated demo asset
- A terminal workflow should be recorded as an animation
- A task mentions VHS, .tape files, Pillow, or demo rendering
- A Windows-compatible GIF workflow is required

## Environment Defaults

Assume this workspace runs in PowerShell on Windows unless current evidence says otherwise.

Prefer these existing paths in this repository:

1. scripts/render_demo.ps1 for the main demo GIF flow
2. scripts/make_demo_gif.py for the Python/Pillow fallback
3. demos/*.tape for existing terminal recordings
4. demos/.tools/vhs-0.10.0/vhs_0.10.0_Windows_x86_64/vhs.exe as the repo-local Windows VHS binary when needed

Use global tool installs only when the repo-local or workspace-local path cannot satisfy the task.

## Workflow

### Step 1: Identify the GIF Source

Choose the smallest fitting path:

- Existing drift demo artifact: reuse the repo scripts
- Existing .tape recording: use VHS if the environment supports it
- Image sequence or screenshots: prefer a small Python/Pillow renderer over a new platform-specific stack
- New terminal walkthrough: create a .tape only if a tape-based workflow is genuinely the right fit

### Step 2: Run a Compatibility Preflight

Check the environment before rendering:

- Is the shell PowerShell on Windows?
- Is vhs available on PATH?
- Is ffmpeg available on PATH when VHS is needed?
- Does the repo-local VHS binary exist?
- Does the workspace .venv exist and include Pillow for the Python fallback?

Do not assume Linux paths, Bash syntax, or a globally configured media stack.

### Step 3: Choose the Renderer

Use this order of preference in this repository:

1. Main repo demo GIF:
   - run scripts/render_demo.ps1 from PowerShell
   - this already chooses VHS first and falls back to Python/Pillow when VHS is unavailable

2. Existing .tape asset on Windows:
   - use vhs if both vhs and ffmpeg are available
   - if vhs is not on PATH but the repo-local Windows binary exists, use that binary explicitly
   - if VHS cannot run, do not force a broken path; either use the Python fallback if it fits the task or explain the blocker

3. Python fallback:
   - use .venv\Scripts\python.exe when present
   - prefer the existing Pillow-based renderer before adding another dependency

4. New custom GIF generation:
   - keep it small and deterministic
   - prefer Python + Pillow over platform-specific graphics tooling unless the task explicitly requires another stack

### Step 4: Keep the Output Deterministic

Use stable inputs and avoid environment-specific noise:

- avoid machine-specific absolute paths inside recordings
- keep window size, theme, and typing behavior fixed where possible
- prefer fast commands with predictable output
- reuse existing demo scripts instead of manually replaying long sessions

### Step 5: Verify the Artifact

After rendering, verify:

- the output file exists at the expected path
- the file size is sane for docs or README usage
- the frames are not blank, clipped, or missing fonts
- the chosen workflow did not depend on an unavailable tool

## Repo-Specific Commands

Use the concrete patterns in [references/windows-gif-workflow.md](./references/windows-gif-workflow.md).

## Guardrails

- Do not introduce a new GIF toolchain if the repo's VHS or Pillow path already solves the task.
- Do not assume Bash, WSL, or Unix-only paths in this workspace.
- Do not require global installs when the repo-local binary or .venv path is sufficient.
- Do not overwrite unrelated demo assets unless the user asked for that specific output.
- Do not make the workflow less reproducible by depending on interactive manual capture when a scripted render already exists.

## Response Pattern

When using this skill, work in this order:

1. Identify the source asset type.
2. Check compatibility constraints in the current environment.
3. Pick the smallest existing rendering path that works here.
4. Render or update the GIF.
5. Verify the artifact and report the exact path used.

## References

- [Windows GIF workflow](./references/windows-gif-workflow.md)
