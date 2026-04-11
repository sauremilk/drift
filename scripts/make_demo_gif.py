"""
Generate a beautiful terminal-recording-style demo GIF for Drift.

Curated hardcoded output — deterministic, no live drift execution required.

Requirements: Pillow
Run from repo root: python scripts/make_demo_gif.py
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Terminal colour palette — Banner-aligned (dark blue-black + orange/gold)
# ---------------------------------------------------------------------------
BG = (8, 12, 20)  # #080c14  Banner base
FG = (190, 180, 165)  # #beb4a5  Warm light text
ACCENT_CYAN = (255, 140, 66)  # #ff8c42  Primary orange (banner accent)
ACCENT_BLUE = (255, 217, 102)  # #ffd966  Gold (banner text)
ACCENT_RED = (255, 100, 70)  # #ff6446  Warm red for HIGH
ACCENT_YEL = (255, 189, 46)  # #ffbd2e  Amber for MED
ACCENT_GRN = (100, 210, 100)  # #64d264  Muted green for actions
ACCENT_MAV = (255, 140, 66)  # #ff8c42  Footer accent = primary orange
DIM = (100, 90, 75)  # #645a4b  Warm dim text
BORDER = (80, 45, 15)  # #502d0f  Warm dark border
SURFACE0 = (20, 14, 8)  # #140e08  Subtle highlight bg
CHR_BG = (18, 10, 4)  # #120a04  Banner chrome bg
WIN_RED = (107, 30, 0)  # #6b1e00  Banner traffic light
WIN_YEL = (160, 80, 0)  # #a05000  Banner traffic light
WIN_GRN = (212, 120, 0)  # #d47800  Banner traffic light

# ---------------------------------------------------------------------------
# Curated demo output — two-act story matching README "How it works"
#   Act 1: drift brief (before session — generate guardrails)
#   Act 2: drift check (after session — enforce structure)
# ---------------------------------------------------------------------------
PROMPT = "$ "

# ── Act 1: drift brief ────────────────────────────────────────────────────
BRIEF_CMD = 'drift brief --task "refactor the auth service"'

BRIEF_SCAN = [
    "Resolving scope",
    "Resolving scope.",
    "Resolving scope..",
    "Resolving scope...",
]

BRIEF_HEADER = [
    "╭──────────────────────────── Drift Brief ──────────────────────────────────────────────────────────────────────",  # noqa: E501
    "│  Task:   refactor the auth service",
    "│  Scope:  src/auth/, src/services/middleware/  (confidence: 85%)",
    "│  Risk:   MEDIUM -- high auth volatility, 3 middleware variants",
    "╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────",
]

BRIEF_LANDSCAPE_HEADER = [
    "",
    "  Signal    Score    Findings",
    "  ──────────────────────────────",
]

# (signal_name, score, findings_count) — rendered with graphical bars
BRIEF_LANDSCAPE_DATA = [
    ("BEM", 0.68, 12),
    ("MDS", 0.42, 5),
    ("PFS", 0.39, 3),
    ("AVS", 0.28, 1),
]

BRIEF_GUARDRAILS = [
    "",
    "╭──────── Guardrails (copy to agent prompt) ──────────────────────────────────────────────────────────────────────",  # noqa: E501
    "│  1. [BEM] No bare except: in auth middleware",
    "│     Do NOT: except: pass -- swallows auth failures",
    "│",
    "│  2. [MDS] Single source for middleware chain",
    "│     Do NOT: reimplement @requires_auth in multiple files",
    "│",
    "│  3. [PFS] One error handler pattern across API routes",
    "│     Do NOT: mix 4 different try/except styles",
    "╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────",
    "",
    "  Suggested: drift check --fail-on high  after implementation",
]

# ── Act 2: drift check ────────────────────────────────────────────────────
CHECK_CMD = "drift check --fail-on high"

CHECK_SCAN = [
    "Checking diff",
    "Checking diff.",
    "Checking diff..",
    "Checking diff...",
]

CHECK_HEADER = [
    "╭── drift check (HEAD~1 vs HEAD) ────────────────────────────────────────────────────────────────────────────────",  # noqa: E501
    "│  DRIFT SCORE  0.34    12 files changed    3 new findings    1.2s",
    "│  Severity: MEDIUM     Baseline: 3 matched",
    "╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────",
]

CHECK_FINDING_1 = [
    "",
    "  * HIGH  AVS  0.67   Import creates layer violation",
    "          -> src/api/routes.py:18  (db import in API layer)",
    "          -> Next: move DB access behind service interface",
]

CHECK_FINDING_2 = [
    "  *  MED  MDS  0.51   2 near-identical validators",
    "          -> src/utils/validators.py:42",
    "          -> Next: consolidate to shared validator",
]

CHECK_PASS = [
    "",
    "  ✓ Drift check passed (threshold: high).",
]

# ---------------------------------------------------------------------------
# Canvas parameters
# ---------------------------------------------------------------------------
W = 960
H = 580
PADDING = 24
FONT_SZ = 16
LINE_H = 23
TITLE_H = 36

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[mGKHF]", "", text)


def _load_font(size: int):
    from PIL import ImageFont  # type: ignore[import-untyped]

    candidates = [
        "C:/Windows/Fonts/cascadiacode.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/courbd.ttf",
        "C:/Windows/Fonts/cour.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _line_colour(line: str) -> tuple | list:
    """Assign a display colour or list of (text, colour) segments."""
    s = line.strip()
    # Box borders — segment title text in accent colour
    if s.startswith("╭") or s.startswith("╰"):
        for title in (
            "Drift Brief",
            "Guardrails (copy to agent prompt)",
            "drift check (HEAD~1 vs HEAD)",
        ):
            idx = line.find(title)
            if idx != -1:
                return [
                    (line[:idx], BORDER),
                    (title, ACCENT_CYAN),
                    (line[idx + len(title) :], BORDER),
                ]
        return BORDER
    # Box content — score/task lines
    if s.startswith("│"):
        if "DRIFT SCORE" in line:
            return ACCENT_CYAN
        if "Task:" in line or "Scope:" in line:
            return FG
        if "Risk:" in line:
            return ACCENT_YEL
        if "Guardrails" in line:
            return ACCENT_CYAN
        if "Do NOT:" in line or "Do NOT " in line:
            return ACCENT_RED
        if "[BEM]" in line or "[MDS]" in line or "[PFS]" in line or "[AVS]" in line:
            return ACCENT_BLUE
        return FG
    # Table separator
    if s.startswith("─"):
        return BORDER
    # Column header
    if s.startswith("Signal") and "Score" in line:
        return DIM
    # NOTE: landscape data rows are tuples — handled in _make_frame, not here
    # Scanning / resolving progress
    if s.startswith("Resolving") or s.startswith("Checking"):
        return DIM
    # Severity tags
    if "* HIGH" in line:
        return ACCENT_RED
    if "*  MED" in line or "* MED" in line:
        return ACCENT_YEL
    # Pass/fail
    if "passed" in line:
        return ACCENT_GRN
    if "failed" in line:
        return ACCENT_RED
    # Next-action lines — primary orange CTA
    if "-> Next:" in line:
        return ACCENT_CYAN
    # Suggested follow-up
    if "Suggested:" in line:
        return DIM
    # File location lines
    if "-> src/" in line:
        return DIM
    # Prompt / command — gold to match banner logotype
    if s.startswith(PROMPT.strip()) or s.startswith("drift "):
        return ACCENT_BLUE
    return FG


# ---------------------------------------------------------------------------
# Single-frame rendering
# ---------------------------------------------------------------------------


def _make_frame(lines: list[str], title: str = "drift analyze") -> object:
    from PIL import Image, ImageDraw  # type: ignore[import-untyped]

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    font = _load_font(FONT_SZ)

    # ── Window chrome ──────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, TITLE_H], fill=CHR_BG)
    for i, col in enumerate([WIN_RED, WIN_YEL, WIN_GRN]):
        cx = 18 + i * 22
        cy = TITLE_H // 2
        draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=col)
    tw = draw.textlength(title, font=font)
    draw.text(((W - tw) / 2, (TITLE_H - FONT_SZ) / 2), title, fill=DIM, font=font)
    # Chrome separator
    draw.line([(0, TITLE_H), (W, TITLE_H)], fill=BORDER, width=1)

    # ── Terminal body ──────────────────────────────────────────────────────
    y = TITLE_H + PADDING
    max_lines = (H - TITLE_H - PADDING * 2) // LINE_H
    visible = lines[-max_lines:] if len(lines) > max_lines else lines

    for raw_line in visible:
        # ── Landscape data rows — graphical column rendering ──────────
        if isinstance(raw_line, tuple) and raw_line[0] == "LANDSCAPE":
            _, sig, score, count = raw_line
            if score >= 0.6:
                col = ACCENT_CYAN
            elif score >= 0.35:
                col = ACCENT_YEL
            else:
                col = FG
            # Signal name at fixed x
            draw.text((PADDING + 10, y), sig, fill=col, font=font)
            # Bar track (background)
            bar_x = PADDING + 80
            bar_max = 80
            draw.rectangle([bar_x, y + 5, bar_x + bar_max, y + LINE_H - 6], fill=SURFACE0)
            # Bar fill (proportional to score)
            bar_w = int(score * bar_max)
            if bar_w > 0:
                draw.rectangle([bar_x, y + 5, bar_x + bar_w, y + LINE_H - 6], fill=col)
            # Score value at fixed x
            draw.text((PADDING + 178, y), f"{score:.2f}", fill=col, font=font)
            # Findings count at fixed x
            draw.text((PADDING + 255, y), f"{count:>4}", fill=DIM, font=font)
            y += LINE_H
            if y > H - PADDING:
                break
            continue

        line = _strip_ansi(raw_line)
        colour_info = _line_colour(line)

        # Subtle highlight background behind all box lines
        stripped = line.strip()
        if stripped.startswith("╭") or stripped.startswith("╰") or stripped.startswith("│"):
            draw.rectangle(
                [PADDING - 6, y - 2, W - PADDING + 6, y + LINE_H - 3],
                fill=SURFACE0,
            )

        # Render — single colour or multi-segment
        if isinstance(colour_info, list):
            x = PADDING
            for seg_text, seg_colour in colour_info:
                draw.text((x, y), seg_text, fill=seg_colour, font=font)
                x += draw.textlength(seg_text, font=font)
        else:
            draw.text((PADDING, y), line[:108], fill=colour_info, font=font)

        # ── Right border for box lines at fixed pixel position ──────
        if stripped.startswith("╭") or stripped.startswith("╰") or stripped.startswith("│"):
            cap = {"╭": "╮", "╰": "╯"}.get(stripped[0], "│")
            cap_w = draw.textlength(cap, font=font)
            cap_x = W - PADDING - cap_w
            # Clear area behind cap (overwrite extended ─ text)
            draw.rectangle(
                [cap_x - 1, y - 2, W - PADDING + 6, y + LINE_H - 3],
                fill=SURFACE0,
            )
            draw.text((cap_x, y), cap, fill=BORDER, font=font)

        y += LINE_H
        if y > H - PADDING:
            break

    return img


# ---------------------------------------------------------------------------
# Build animation frames
# ---------------------------------------------------------------------------


def _type_frames(
    cmd: str,
    prior_lines: list[str],
    title: str,
    frames: list,
) -> list[str]:
    """Animate typing a command, return the lines state after typing."""
    prompt_line = PROMPT + cmd
    # Type chars in groups of 2
    for i in range(len(PROMPT), len(prompt_line) + 1, 2):
        frames.append((_make_frame(prior_lines + [prompt_line[:i] + "_"], title), 45))
    # Cursor blink on complete command
    for blink in range(3):
        cursor = "_" if blink % 2 == 0 else ""
        frames.append((_make_frame(prior_lines + [prompt_line + cursor], title), 180))
    return prior_lines + [prompt_line]


def build_frames() -> list:
    """Assemble all animation frames as (PIL.Image, delay_ms) tuples.

    Two-act story matching README "How it works":
      Act 1 — drift brief  (before session: generate guardrails)
      Act 2 — drift check  (after session: enforce structure)
    """
    frames: list = []

    # ══════════════════════════════════════════════════════════════════════
    # ACT 1: drift brief — "Before a session"
    # ══════════════════════════════════════════════════════════════════════
    title_brief = "drift brief"

    # Initial prompt with cursor blink
    for blink in range(3):
        cursor = "_" if blink % 2 == 0 else " "
        frames.append((_make_frame([PROMPT + cursor], "drift"), 350))

    # Type the brief command
    current = _type_frames(BRIEF_CMD, [], title_brief, frames)

    # Resolving scope animation
    current = current + [""]
    for scan_text in BRIEF_SCAN:
        for _ in range(2):
            frames.append((_make_frame(current + [scan_text], title_brief), 100))
    frames.append((_make_frame(current + [BRIEF_SCAN[-1]], title_brief), 200))

    # Brief header panel — line-by-line reveal
    current.append("")
    for line in BRIEF_HEADER:
        current.append(line)
        frames.append((_make_frame(current, title_brief), 70))
    for _ in range(8):
        frames.append((_make_frame(current, title_brief), 110))

    # Landscape table header — line by line
    for line in BRIEF_LANDSCAPE_HEADER:
        current.append(line)
        frames.append((_make_frame(current, title_brief), 60))

    # Landscape data rows — graphical bars
    for sig, score, count in BRIEF_LANDSCAPE_DATA:
        current.append(("LANDSCAPE", sig, score, count))
        frames.append((_make_frame(current, title_brief), 80))
    for _ in range(6):
        frames.append((_make_frame(current, title_brief), 100))

    # Guardrails panel — line-by-line reveal (the key value prop)
    for line in BRIEF_GUARDRAILS:
        current.append(line)
        frames.append((_make_frame(current, title_brief), 70))
    for _ in range(30):
        frames.append((_make_frame(current, title_brief), 130))

    # ══════════════════════════════════════════════════════════════════════
    # ACT 2: drift check — "After a session"
    # ══════════════════════════════════════════════════════════════════════
    title_check = "drift check"

    # New prompt — clear screen for Act 2
    current_2: list[str] = []
    frames.append((_make_frame([PROMPT + "_"], title_check), 500))

    # Type the check command
    current_2 = _type_frames(CHECK_CMD, [], title_check, frames)

    # Checking diff animation
    current_2 = current_2 + [""]
    for scan_text in CHECK_SCAN:
        for _ in range(2):
            frames.append((_make_frame(current_2 + [scan_text], title_check), 100))
    frames.append((_make_frame(current_2 + [CHECK_SCAN[-1]], title_check), 200))

    # Check header — line-by-line reveal
    current_2.append("")
    for line in CHECK_HEADER:
        current_2.append(line)
        frames.append((_make_frame(current_2, title_check), 70))
    for _ in range(6):
        frames.append((_make_frame(current_2, title_check), 110))

    # Finding 1 — line by line
    for line in CHECK_FINDING_1:
        current_2.append(line)
        frames.append((_make_frame(current_2, title_check), 80))
    for _ in range(6):
        frames.append((_make_frame(current_2, title_check), 110))

    # Finding 2 — line by line
    for line in CHECK_FINDING_2:
        current_2.append(line)
        frames.append((_make_frame(current_2, title_check), 80))
    for _ in range(6):
        frames.append((_make_frame(current_2, title_check), 110))

    # Pass verdict — hold long so it sinks in
    current_2 = current_2 + CHECK_PASS
    for _ in range(35):
        frames.append((_make_frame(current_2, title_check), 140))

    return frames


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    from PIL import Image  # type: ignore[import-untyped]

    repo_root = Path(__file__).parent.parent
    output = repo_root / "demos" / "demo.gif"

    print("Building frames …")
    frames = build_frames()
    print(f"  {len(frames)} frames")

    imgs = [f for f, _ in frames]
    delays = [d for _, d in frames]

    print("Quantising (256 colours) …")

    def _quantise(img):
        return img.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=0)

    q0 = _quantise(imgs[0])
    q_rest = [_quantise(im) for im in imgs[1:]]

    print("Saving GIF …")
    q0.save(
        output,
        save_all=True,
        append_images=q_rest,
        optimize=True,
        loop=0,
        duration=delays,
    )
    print(f"Saved → {output}  ({output.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
