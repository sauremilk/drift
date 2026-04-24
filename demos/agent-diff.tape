Output demos/agent-diff.gif

Set Shell "powershell"
Set FontSize 14
Set Width 1400
Set Height 860
Set Theme "Catppuccin Mocha"
Set Padding 20
Set Framerate 24
Set PlaybackSpeed 1.0

Type "Write-Host 'Prepare temporary staged-change demo repo'" Enter
Sleep 800ms

Type "$demo = 'demos/.tmp_agent_diff_demo'" Enter
Type "if (Test-Path $demo) { Remove-Item -Recurse -Force $demo }" Enter
Type "New-Item -ItemType Directory -Path $demo | Out-Null" Enter
Type "Copy-Item -Recurse -Path 'examples/demo-project/*' -Destination $demo" Enter
Type "Push-Location $demo" Enter
Type "git init | Out-Null" Enter
Type "git config user.email 'demo@example.com'" Enter
Type "git config user.name 'Drift Demo'" Enter
Type "git add ." Enter
Type "git commit -m 'baseline' | Out-Null" Enter
Type "Add-Content -Path 'services/user_service.py' -Value \"`n# staged drift demo change\"" Enter
Type "git add services/user_service.py" Enter
Type "Pop-Location" Enter
Sleep 1s

Type "Write-Host 'Agent guardrail: inspect staged drift before commit'" Enter
Sleep 1200ms

Type ".\\.venv\\Scripts\\drift.exe diff --repo demos/.tmp_agent_diff_demo --staged-only --max-findings 3" Sleep 350ms Enter
Sleep 5s
