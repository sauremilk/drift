# Trailer — "All Green. All Wrong."

90-second screen-recording trailer for drift-analyzer.

## Quick start

```powershell
# Full pipeline: VHS scenes + text cards + concat
.\scripts\render_trailer.ps1

# Single scene for testing
.\scripts\render_trailer.ps1 -SceneOnly scene6

# Only text cards (no VHS required)
.\scripts\render_trailer.ps1 -SkipTerminal

# Only terminal scenes (no Pillow cards)
.\scripts\render_trailer.ps1 -SkipCards
```

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| VHS | ≥0.10 | `vhs --version` |
| ffmpeg | ≥6.0 | `ffmpeg -version` |
| JetBrains Mono | any | Font used by VHS; falls back gracefully |
| Pillow | ≥10.0 | Installed in `.venv` |
| Rich | any | Installed in `.venv` (drift dependency) |

## Architecture

```
scripts/
  _trailer_scenes.py      # Curated Rich terminal output per scene
  make_trailer_cards.py    # Pillow → PNG frames → ffmpeg → MP4
  render_trailer.ps1       # Master orchestrator

demos/trailer/
  clips/                   # Per-scene MP4 clips (generated)
  tapes/                   # VHS tape files (generated)
  _normalized/             # Re-encoded clips for concat (generated)
  concat_norm.txt          # ffmpeg concat manifest (generated)
  trailer_all_green_all_wrong.mp4   # Final output
```

## Scene map

| Scene | Act | Duration | Source | Content |
|-------|-----|----------|--------|---------|
| 01 | 1 | 5 s | VHS | pytest all-pass |
| 02 | 1 | 7 s | VHS | ruff + mypy + CI green |
| 03 | 1 | 6 s | VHS | Slow diff scroll |
| 04 | 1 | 4 s | Pillow | "Your architecture is drifting." |
| 05 | 2 | 6 s | VHS | `drift analyze` reveal |
| 06 | 2 | 10 s | VHS | PHR phantom reference |
| 07 | 2 | 9 s | VHS | PFS pattern fragmentation |
| 08 | 2 | 8 s | VHS | AVS architecture violation |
| 09 | 3 | 10 s | VHS | `drift brief` guardrails |
| 10 | 3 | 9 s | VHS | `drift nudge` safe_to_commit |
| 11 | 4 | 6 s | Pillow | Three fact lines |
| 12 | 4 | 6 s | Pillow | Tagline in three beats |
| 13 | 4 | 4 s | Pillow | URL + blinking cursor |

## Adding voice-over

The final `trailer_all_green_all_wrong.mp4` is silent (no audio track).
To add narration:

```powershell
ffmpeg -i demos/trailer/trailer_all_green_all_wrong.mp4 ^
       -i narration.wav ^
       -c:v copy -c:a aac -shortest ^
       demos/trailer/trailer_final.mp4
```

## Narration script

See [docs/distribution/trailer-script-all-green-all-wrong.md](../../docs/distribution/trailer-script-all-green-all-wrong.md)
for the full scene-by-scene breakdown with voice-over text and director's notes.
