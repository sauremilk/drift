Output demos/agent-fix-plan.gif

Set Shell "cmd"
Set FontSize 14
Set Width 1280
Set Height 820
Set Theme "Catppuccin Mocha"
Set Padding 20
Set Framerate 24
Set PlaybackSpeed 1.0

Type "echo Drift for agents: baseline scan" Sleep 250ms Enter
Sleep 1s

Type ".venv\\Scripts\\drift.exe scan --repo examples/demo-project --max-findings 3 --select PFS,AVS,MDS" Sleep 350ms Enter
Sleep 5s

Type "echo Drift for agents: prioritized repair tasks" Sleep 250ms Enter
Sleep 1200ms

Type ".venv\\Scripts\\drift.exe fix-plan --repo examples/demo-project --max-tasks 3" Sleep 350ms Enter
Sleep 5s
