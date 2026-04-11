Output demos/demo.gif

Set Shell "cmd"
Set FontSize 14
Set Width 1200
Set Height 750
Set Theme "Catppuccin Mocha"
Set Padding 20
Set Framerate 24
Set PlaybackSpeed 1.5

# Kurzanalyse - max 5 Findings, gruppiert
Type "drift analyze --repo . --max-findings 5 --group-by severity" Sleep 400ms Enter

# Warte auf vollständige Analyse (~35s Repo-Scan + Rendering)
Sleep 45s

# Zeige CI-Gate Befehl
Sleep 1s
Type "drift check --fail-on high" Sleep 400ms Enter
Sleep 8s
