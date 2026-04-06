Output demos/agent-workflow.gif

Set Shell "cmd"
Set FontSize 14
Set Width 1280
Set Height 820
Set Theme "Catppuccin Mocha"
Set Padding 20
Set Framerate 24
Set PlaybackSpeed 1.0

# Step 1: Session baseline scan for agents
Type "echo Drift for agents: step 1 — session baseline" Sleep 250ms Enter
Sleep 800ms

Type ".venv\\Scripts\\drift.exe scan --repo examples/demo-project --max-findings 5 --select PFS,BEM,EDS" Sleep 350ms Enter
Sleep 7s

# Step 2: Agent diff guardrail (pre-commit)
Type "echo Step 2 — pre-commit guardrail (staged diff)" Sleep 250ms Enter
Sleep 800ms

Type "cd demos\\.tmp_agent_workflow_demo 2>nul & rmdir /s /q demos\\.tmp_agent_workflow_demo 2>nul" Sleep 200ms Enter
Sleep 500ms
Type "xcopy /e /q /i examples\\demo-project demos\\.tmp_agent_workflow_demo >nul" Sleep 200ms Enter
Sleep 500ms
Type "cd demos\\.tmp_agent_workflow_demo && git init -q && git config user.email demo@example.com && git config user.name Demo" Sleep 200ms Enter
Sleep 500ms
Type "git add . && git commit -q -m baseline" Sleep 200ms Enter
Sleep 1s
Type "echo # staged drift demo >> services\\user_service.py && git add services\\user_service.py" Sleep 200ms Enter
Sleep 500ms
Type "cd ..\\..\ && .venv\\Scripts\\drift.exe diff --repo demos\\.tmp_agent_workflow_demo --staged-only --max-findings 3" Sleep 350ms Enter
Sleep 5s

# Step 3: Prioritized repair tasks
Type "echo Step 3 — prioritized repair tasks for agent" Sleep 250ms Enter
Sleep 1000ms

Type ".venv\\Scripts\\drift.exe fix-plan --repo examples/demo-project --max-tasks 3" Sleep 350ms Enter
Sleep 7s
