# Windows GIF Workflow Reference

Use this reference when the main GIF Creation skill is loaded and the task needs concrete commands.

## Existing Repo Paths

- scripts/render_demo.ps1
- scripts/make_demo_gif.py
- demos/demo.tape
- demos/agent-fix-plan.tape
- demos/agent-diff.tape
- demos/agent-copilot-context.tape
- demos/.tools/vhs-0.10.0/vhs_0.10.0_Windows_x86_64/vhs.exe

## Preferred Command Order

### 1. Main Demo GIF

Use the existing PowerShell wrapper first:

```powershell
./scripts/render_demo.ps1
```

Why:

- fits the current Windows workspace
- prefers VHS automatically when available
- falls back to the Python/Pillow renderer when VHS is unavailable

### 2. Render an Existing Tape with Global VHS

Use this when vhs and ffmpeg are available on PATH:

```powershell
vhs demos/demo.tape
vhs demos/agent-fix-plan.tape
vhs demos/agent-diff.tape
vhs demos/agent-copilot-context.tape
```

### 3. Render an Existing Tape with the Repo-Local Windows VHS Binary

Use this when the repo-local binary exists and the task truly needs a tape render:

```powershell
& .\demos\.tools\vhs-0.10.0\vhs_0.10.0_Windows_x86_64\vhs.exe demos/demo.tape
```

Repeat with another .tape path as needed.

Note:

- VHS still depends on ffmpeg being available
- prefer the PowerShell wrapper for the main demo when possible

### 4. Python/Pillow Fallback

Use the workspace venv first:

```powershell
& .\.venv\Scripts\python.exe scripts/make_demo_gif.py
```

If the venv path does not exist, fall back to the active Python only after confirming the environment:

```powershell
python scripts/make_demo_gif.py
```

This path is the safest Windows fallback for the main demo GIF because it does not require VHS, Chrome, or browser-based rendering.

## Compatibility Checklist

Before choosing a renderer, check:

```powershell
Get-Command vhs, ffmpeg -ErrorAction SilentlyContinue
```

Check whether the workspace venv Python exists:

```powershell
Test-Path .\.venv\Scripts\python.exe
```

Check whether the repo-local VHS binary exists:

```powershell
Test-Path .\demos\.tools\vhs-0.10.0\vhs_0.10.0_Windows_x86_64\vhs.exe
```

## Decision Table

- Need demos/demo.gif and want the safest path: use scripts/render_demo.ps1
- Need a .tape rendered and vhs plus ffmpeg are available: use VHS
- Need a .tape rendered and only the repo-local VHS binary exists: use the repo-local binary
- Need a Windows-safe fallback with no VHS dependency: use scripts/make_demo_gif.py

## Troubleshooting

- If VHS fails because ffmpeg is missing, switch to the Pillow fallback when the task allows it.
- If Python fallback fails, use the workspace .venv first instead of system Python.
- If a new GIF workflow would require a new global dependency, prefer extending the existing Pillow path unless the user explicitly asks for a different renderer.
- If the task only updates a demo asset that already has a script, do not create a second parallel render path.
