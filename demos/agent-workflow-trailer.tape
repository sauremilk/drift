Output demos/agent-workflow-trailer.gif

Set Shell "cmd"
Set FontFamily "JetBrains Mono"
Set FontSize 16
Set Width 1200
Set Height 620
Set Theme "Catppuccin Mocha"
Set Padding 20
Set Framerate 24
Set PlaybackSpeed 2.5
Set TypingSpeed 30ms

# ──────────────────────────────────────────────────────────────
# Szene 1 — Hook
# Leeres Terminal erscheint, Cursor blinkt, Befehl wird getippt
# (1.13 s GIF: 0.28 s Pause + 0.8 s Tippen + 0.12 s Settle)
# ──────────────────────────────────────────────────────────────
Hide
Sleep 400ms
Show
Sleep 700ms

Type ".venv\\Scripts\\drift.exe scan --repo examples/demo-project --max-findings 4 --select PFS,BEM,EDS,COD" Enter
Sleep 300ms

# ──────────────────────────────────────────────────────────────
# Szene 2 — Konflikt
# Analyse läuft (~7 s real → ~2.8 s im GIF bei PlaybackSpeed 2.5×)
# Hoher Drift-Score, Violations, roter Status — 4-6 Zeilen Output
# 1 s Pause lässt den "schlechten Zustand" wirken (0.72 s GIF)
# ──────────────────────────────────────────────────────────────
Sleep 7s
Sleep 1800ms

# ──────────────────────────────────────────────────────────────
# Szene 3 — Eingriff
# Konkrete Repair-Tasks als nächster Schritt
# (~0.86 s Tippen + 2.8 s Analyse + 0.4 s Settle = ~4.1 s GIF)
# ──────────────────────────────────────────────────────────────
Type ".venv\\Scripts\\drift.exe fix-plan --repo examples/demo-project --max-tasks 3" Enter
Sleep 300ms

Sleep 7s
Sleep 1000ms

# ──────────────────────────────────────────────────────────────
# Szene 4 — Resolution
# Letzter Frame (fix-plan Output = Action-Plan sichtbar) hält 2 s
# im GIF → 5 s real bei PlaybackSpeed 2.5×
# Kein neuer Prompt — harter Schluss, gutes Loop-Verhalten
# ──────────────────────────────────────────────────────────────
Sleep 5s
