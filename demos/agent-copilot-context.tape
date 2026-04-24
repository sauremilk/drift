Output demos/agent-copilot-context.gif

Set Shell "cmd"
Set FontSize 14
Set Width 1280
Set Height 820
Set Theme "Catppuccin Mocha"
Set Padding 20
Set Framerate 24
Set PlaybackSpeed 1.0

Type "echo MCP config for VS Code agents" Sleep 250ms Enter
Sleep 800ms

Type "type examples\\vibe-coding\\mcp.json" Sleep 250ms Enter
Sleep 3s

Type "echo Drift can also generate repo-specific Copilot instructions" Sleep 250ms Enter
Sleep 1200ms

Type ".venv\\Scripts\\drift.exe copilot-context --repo examples/demo-project" Sleep 350ms Enter
Sleep 5s
