"""
Generate terminal-scene MP4 clips for the drift trailer via Pillow + ffmpeg.

Same deterministic Pillow-based approach as make_demo_gif.py / make_demo_gifs.py.
No VHS required — renders curated Rich-style output as image frames.

Usage:
    .venv/Scripts/python.exe scripts/make_trailer_terminal.py [--output-dir demos/trailer/clips]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── Canvas ─────────────────────────────────────────────────────────────────

W, H = 1920, 1080
PADDING = 48
FONT_SZ = 22
LINE_H = 32
TITLE_H = 48
FPS = 30

# ── Catppuccin Mocha palette ──────────────────────────────────────────────

BG = (30, 30, 46)
FG = (205, 214, 244)
CYAN = (137, 220, 235)
BLUE = (137, 180, 250)
RED = (243, 139, 168)
YELLOW = (249, 226, 175)
GREEN = (166, 227, 161)
MAUVE = (203, 166, 247)
DIM = (108, 112, 134)
BORDER = (88, 91, 112)
SURFACE0 = (49, 50, 68)
CHR_BG = (24, 24, 37)
WIN_RED = (235, 80, 80)
WIN_YEL = (255, 189, 46)
WIN_GRN = (40, 200, 80)
TEAL = (13, 148, 136)
BOLD_RED = (255, 100, 100)
BOLD_YEL = (255, 220, 120)

# ── Font ───────────────────────────────────────────────────────────────────

_FONT_CACHE: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int = FONT_SZ) -> ImageFont.FreeTypeFont:
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    candidates = [
        Path.home() / "AppData/Local/Microsoft/Windows/Fonts/JetBrainsMono-Regular.ttf",
        Path("C:/Windows/Fonts/JetBrainsMono-Regular.ttf"),
        Path("C:/Windows/Fonts/CascadiaMono.ttf"),
        Path("C:/Windows/Fonts/cascadiacode.ttf"),
        Path("C:/Windows/Fonts/consola.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    ]
    for p in candidates:
        if p.exists():
            f = ImageFont.truetype(str(p), size)
            _FONT_CACHE[size] = f
            return f
    f = ImageFont.load_default(size)
    _FONT_CACHE[size] = f
    return f


# ── Drawing ────────────────────────────────────────────────────────────────


def _chrome(draw: ImageDraw.ImageDraw, title: str) -> None:
    """Draw window chrome bar."""
    font = _font()
    draw.rectangle([0, 0, W, TITLE_H], fill=CHR_BG)
    for i, col in enumerate([WIN_RED, WIN_YEL, WIN_GRN]):
        cx = 24 + i * 28
        cy = TITLE_H // 2
        draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=col)
    tw = draw.textlength(title, font=font)
    draw.text(((W - tw) / 2, (TITLE_H - FONT_SZ) / 2), title, fill=DIM, font=font)


# A "rich line" is (text, color).  A plain str uses FG.
RichLine = list[tuple[str, tuple[int, int, int]]]


def _make_frame(
    lines: list[str | RichLine],
    title: str = "",
) -> Image.Image:
    """Render a terminal frame.  Each line is either a plain str or a RichLine."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    font = _font()

    _chrome(draw, title)

    y = TITLE_H + PADDING
    max_lines = (H - TITLE_H - PADDING * 2) // LINE_H

    visible = lines[-max_lines:] if len(lines) > max_lines else lines

    for raw in visible:
        if isinstance(raw, str):
            draw.text((PADDING, y), raw[:120], fill=FG, font=font)
        else:
            x = PADDING
            for text, color in raw:
                draw.text((x, y), text, fill=color, font=font)
                x += draw.textlength(text, font=font)
        y += LINE_H
        if y > H - PADDING:
            break

    return img


def _hold(frames: list[tuple[Image.Image, int]], img: Image.Image, ms: int) -> None:
    frames.append((img, ms))


def _encode_frames(
    frames: list[tuple[Image.Image, int]],
    output: Path,
) -> None:
    """Encode (image, duration_ms) pairs to MP4 via temp PNGs + ffmpeg."""
    import tempfile

    output.parent.mkdir(parents=True, exist_ok=True)

    # Expand durations into frame indices
    frame_images: list[Image.Image] = []
    for img, ms in frames:
        n = max(1, round(ms * FPS / 1000))
        frame_images.extend([img] * n)

    total = len(frame_images)

    with tempfile.TemporaryDirectory(prefix="drift_trailer_") as tmp:
        tmp_path = Path(tmp)
        # Write frames as numbered PNGs (skip duplicates via symlink-like reuse)
        prev_bytes: bytes | None = None
        prev_file: Path | None = None
        for idx, img in enumerate(frame_images):
            fp = tmp_path / f"frame_{idx:05d}.png"
            cur_bytes = img.tobytes()
            if cur_bytes == prev_bytes and prev_file is not None:
                # Identical frame — copy previous file (fast, avoids re-encode)
                import shutil
                shutil.copy2(prev_file, fp)
            else:
                img.save(fp, format="PNG", compress_level=1)
                prev_bytes = cur_bytes
                prev_file = fp

        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", str(tmp_path / "frame_%05d.png"),
            "-frames:v", str(total),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "medium",
            "-crf", "18",
            str(output),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ffmpeg error: {result.stderr[:300]}", file=sys.stderr)
        else:
            dur = total / FPS
            print(f"  -> {output.name}  ({total} frames, {dur:.1f}s)")


# ── Typed prompt helper ────────────────────────────────────────────────────


def _type_cmd(
    frames: list[tuple[Image.Image, int]],
    cmd: str,
    prev_lines: list[str | RichLine],
    title: str,
    char_ms: int = 40,
) -> list[str | RichLine]:
    """Animate typing a command, return updated lines with command appended."""
    prompt = [("$ ", GREEN)]
    for i in range(1, len(cmd) + 1):
        line: RichLine = prompt + [(cmd[:i] + "█", GREEN)]
        img = _make_frame(prev_lines + [line], title)
        _hold(frames, img, char_ms)

    full_line: RichLine = prompt + [(cmd, GREEN)]
    result = list(prev_lines) + [full_line]
    _hold(frames, _make_frame(result, title), 300)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# SCENE 1 — pytest all green  (~5 s)
# ═══════════════════════════════════════════════════════════════════════════


def scene01(out: Path) -> None:
    print("Rendering scene01_pytest ...")
    frames: list[tuple[Image.Image, int]] = []
    title = "terminal"

    # Type command
    lines = _type_cmd(frames, "pytest tests/ -q", [], title)
    lines.append("")

    # Progress bars
    for pct in range(5, 101, 5):
        dots = "." * 40
        line: RichLine = [(dots, GREEN), (f"  [{pct:3d}%]", DIM)]
        current = list(lines) + [line]
        img = _make_frame(current, title)
        _hold(frames, img, 60)

    lines.append([(("." * 40), GREEN), ("  [100%]", DIM)])
    lines.append("")

    result_line: RichLine = [
        ("=" * 20 + " ", DIM),
        ("847 passed", GREEN),
        (" in 12.4s ", DIM),
        ("=" * 20, DIM),
    ]
    lines.append(result_line)
    _hold(frames, _make_frame(lines, title), 2000)

    _encode_frames(frames, out / "scene01_pytest.mp4")


# ═══════════════════════════════════════════════════════════════════════════
# SCENE 2 — ruff + mypy + CI all green  (~7 s)
# ═══════════════════════════════════════════════════════════════════════════


def scene02(out: Path) -> None:
    print("Rendering scene02_tools ...")
    frames: list[tuple[Image.Image, int]] = []
    title = "terminal"

    # ruff
    lines = _type_cmd(frames, "ruff check .", [], title)
    lines.append([("All checks passed!", GREEN)])
    _hold(frames, _make_frame(lines, title), 1000)
    lines.append("")

    # mypy
    lines = _type_cmd(frames, "mypy src/", lines, title)
    lines.append([("Success: no issues found in 142 source files", GREEN)])
    _hold(frames, _make_frame(lines, title), 1000)
    lines.append("")

    # CI
    lines = _type_cmd(frames, "gh run view --json conclusion -q .conclusion", lines, title)
    lines.append([("  ✓  ", GREEN), ("CI pipeline — ", FG), ("all jobs passed", GREEN)])
    _hold(frames, _make_frame(lines, title), 1500)

    _encode_frames(frames, out / "scene02_tools.mp4")


# ═══════════════════════════════════════════════════════════════════════════
# SCENE 3 — slow diff scroll  (~6 s)
# ═══════════════════════════════════════════════════════════════════════════


def scene03(out: Path) -> None:
    print("Rendering scene03_diff ...")
    frames: list[tuple[Image.Image, int]] = []
    title = "terminal"

    lines = _type_cmd(frames, "git diff HEAD~3 --stat | head -20", [], title)
    lines.append("")

    diff_files = [
        ("src/api/routes.py", "+12", "-3"),
        ("src/api/middleware.py", "+47", "-8"),
        ("src/services/auth.py", "+23", "-5"),
        ("src/services/session.py", "+31", "-12"),
        ("src/services/payments.py", "+18", "-2"),
        ("src/db/models.py", "+8", "-1"),
        ("src/db/queries.py", "+15", "-4"),
        ("src/utils/validators.py", "+42", "-19"),
        ("src/utils/helpers.py", "+7", "-2"),
        ("src/middleware/guard.py", "+29", "-6"),
        ("src/middleware/rate_limit.py", "+11", "-3"),
        ("src/config/settings.py", "+5", "-1"),
        ("tests/test_auth.py", "+67", "-14"),
        ("tests/test_payments.py", "+34", "-8"),
        ("tests/conftest.py", "+12", "-0"),
    ]

    for name, ins, dels in diff_files:
        pad = " " * max(1, 38 - len(name))
        line: RichLine = [
            (f" {name}", DIM),
            (pad + "| ", BORDER),
            (f" {ins}", GREEN),
            (f" {dels}", RED),
        ]
        lines.append(line)
        _hold(frames, _make_frame(lines, title), 220)

    lines.append("")
    summary: RichLine = [
        (" 15 files changed", FG),
        (", ", DIM),
        ("361 insertions(+)", GREEN),
        (", ", DIM),
        ("88 deletions(-)", RED),
    ]
    lines.append(summary)
    _hold(frames, _make_frame(lines, title), 1500)

    _encode_frames(frames, out / "scene03_diff.mp4")


# ═══════════════════════════════════════════════════════════════════════════
# SCENE 5 — drift analyze reveal  (~6 s)
# ═══════════════════════════════════════════════════════════════════════════


def scene05(out: Path) -> None:
    print("Rendering scene05_analyze ...")
    frames: list[tuple[Image.Image, int]] = []
    title = "terminal — drift"

    lines = _type_cmd(frames, "uvx drift-analyzer analyze --repo .", [], title)
    lines.append("")

    # Scanning animation
    for i in range(4):
        dots = "." * i
        scan_line: RichLine = [("  Scanning 2,847 files" + dots, DIM)]
        _hold(frames, _make_frame(lines + [scan_line], title), 300)

    lines.append([("  Scanning 2,847 files... done", DIM)])
    _hold(frames, _make_frame(lines, title), 300)
    lines.append("")

    # Header panel
    panel: list[str | RichLine] = [
        [("╭─── ", BORDER), ("drift analyze", CYAN), ("  . ", DIM), ("─" * 60, BORDER), ("╮", BORDER)],
        [("│  ", BORDER), ("DRIFT SCORE ", FG), ("0.67", BOLD_RED), ("  ·  Grade ", DIM), ("D-Critical", BOLD_RED)],
        [("│  ", BORDER), ("2,847 files │ 1,204 functions │ AI: 34% │ 28.7s │ ", DIM), ("COMPLETE", GREEN)],
        [("╰", BORDER), ("─" * 78, BORDER), ("╯", BORDER)],
    ]
    for p in panel:
        lines.append(p)
        _hold(frames, _make_frame(lines, title), 200)

    lines.append("")
    findings: RichLine = [
        ("  ", FG),
        ("4 HIGH", BOLD_RED),
        ("  ", FG),
        ("7 MEDIUM", BOLD_YEL),
        ("  ", FG),
        ("3 LOW", BLUE),
        ("  — 14 findings across 11 files", DIM),
    ]
    lines.append(findings)
    _hold(frames, _make_frame(lines, title), 2000)

    _encode_frames(frames, out / "scene05_analyze.mp4")


# ═══════════════════════════════════════════════════════════════════════════
# SCENE 6 — PHR phantom reference  (~10 s)
# ═══════════════════════════════════════════════════════════════════════════


def scene06(out: Path) -> None:
    print("Rendering scene06_phantom ...")
    frames: list[tuple[Image.Image, int]] = []
    title = "terminal — drift finding PHR-002"

    lines: list[str | RichLine] = []
    panel: list[str | RichLine] = [
        [("╭─── ", BORDER), ("FINDING  PHR-002  HIGH", BOLD_RED), (" ─" * 24, BORDER), ("╮", BORDER)],
        [("│", BORDER)],
        [("│  ", BORDER), ("◉ ", RED), ("PHR", BOLD_RED), (" · Phantom Reference", RED),
         (" " * 32, BG), ("0.89", BOLD_RED)],
        [("│", BORDER)],
        [("│  ", BORDER), ("  services/payments.py:47", FG), ("  calls  ", DIM),
         ("validate_card_token()", BOLD_RED)],
        [("│", BORDER)],
        [("│  ", BORDER), ("  Target: ", DIM), ("utils/validation.py", FG),
         (" → ", DIM), ("function does not exist", BOLD_RED)],
        [("│", BORDER)],
        [("│  ", BORDER), ("   45 │ ", DIM), ("    card_data = parse_card(request.body)", DIM)],
        [("│  ", BORDER), ("   46 │ ", DIM), ("    if card_data.requires_validation:", DIM)],
        [("│  ", BORDER), (" → 47 │ ", FG), ("        result = validate_card_token(card_data.token)", FG)],
        [("│  ", BORDER), ("   48 │ ", DIM), ("    return ProcessingResult(status=result)", DIM)],
        [("│", BORDER)],
        [("│  ", BORDER), ("  ╰─ ", DIM), ("a3f7c1d", CYAN),
         (" · copilot-agent · 3 weeks ago · ", DIM), ("[AI]", CYAN)],
        [("│", BORDER)],
        [("╰", BORDER), ("─" * 78, BORDER), ("╯", BORDER)],
    ]

    # Reveal line by line with dramatic pause
    for i, p in enumerate(panel):
        lines.append(p)
        hold = 250 if i < 7 else 180
        _hold(frames, _make_frame(lines, title), hold)

    # Hold the full finding
    _hold(frames, _make_frame(lines, title), 5000)

    _encode_frames(frames, out / "scene06_phantom.mp4")


# ═══════════════════════════════════════════════════════════════════════════
# SCENE 7 — PFS pattern fragmentation  (~9 s)
# ═══════════════════════════════════════════════════════════════════════════


def scene07(out: Path) -> None:
    print("Rendering scene07_clonedrift ...")
    frames: list[tuple[Image.Image, int]] = []
    title = "terminal — drift finding PFS-005"

    lines: list[str | RichLine] = []
    panel: list[str | RichLine] = [
        [("╭─── ", BORDER), ("FINDING  PFS-005  MEDIUM", BOLD_YEL), (" ─" * 22, BORDER), ("╮", BORDER)],
        [("│", BORDER)],
        [("│  ", BORDER), ("◎ ", YELLOW), ("PFS", BOLD_YEL), (" · Pattern Fragmentation", YELLOW),
         (" " * 28, BG), ("0.61", BOLD_YEL)],
        [("│", BORDER)],
        [("│  ", BORDER), ("  Same pattern reimplemented 3× across modules:", FG)],
        [("│", BORDER)],
        [("│  ", BORDER), ("    src/api/auth.py:23", FG), ("       →  ", DIM),
         ("validate_and_refresh()", BOLD_YEL), ("    87% similar", DIM)],
        [("│  ", BORDER), ("    src/services/session.py:67", FG), ("  →  ", DIM),
         ("check_and_renew()", BOLD_YEL), ("       91% similar", DIM)],
        [("│  ", BORDER), ("    src/middleware/guard.py:12", FG), ("  →  ", DIM),
         ("verify_or_rotate()", BOLD_YEL), ("      84% similar", DIM)],
        [("│", BORDER)],
        [("│  ", BORDER), ("  Structural similarity: ", DIM), ("87%", BOLD_YEL),
         ("  │  Behavioral delta: ", DIM), ("3 lines", FG)],
        [("│", BORDER)],
        [("│  ", BORDER), ("  → Next: ", DIM),
         ("consolidate to shared utility in src/utils/", GREEN)],
        [("│", BORDER)],
        [("│  ", BORDER), ("  ╰─ ", DIM), ("multiple commits", CYAN),
         (" · 3 authors · over 6 weeks", DIM)],
        [("│", BORDER)],
        [("╰", BORDER), ("─" * 78, BORDER), ("╯", BORDER)],
    ]

    for i, p in enumerate(panel):
        lines.append(p)
        _hold(frames, _make_frame(lines, title), 200)

    _hold(frames, _make_frame(lines, title), 4000)

    _encode_frames(frames, out / "scene07_clonedrift.mp4")


# ═══════════════════════════════════════════════════════════════════════════
# SCENE 8 — AVS architecture violation  (~8 s)
# ═══════════════════════════════════════════════════════════════════════════


def scene08(out: Path) -> None:
    print("Rendering scene08_boundary ...")
    frames: list[tuple[Image.Image, int]] = []
    title = "terminal — drift finding AVS-001"

    lines: list[str | RichLine] = []
    panel: list[str | RichLine] = [
        [("╭─── ", BORDER), ("FINDING  AVS-001  HIGH", BOLD_RED), (" ─" * 24, BORDER), ("╮", BORDER)],
        [("│", BORDER)],
        [("│  ", BORDER), ("◉ ", RED), ("AVS", BOLD_RED), (" · Architecture Violation", RED),
         (" " * 29, BG), ("0.78", BOLD_RED)],
        [("│", BORDER)],
        [("│  ", BORDER), ("  api/routes.py:18", FG), ("  imports from  ", DIM),
         ("db/models.py", BOLD_RED)],
        [("│", BORDER)],
        [("│  ", BORDER), ("   16 │ ", DIM), ("from services.auth import require_token", DIM)],
        [("│  ", BORDER), ("   17 │ ", DIM), ("from api.schemas import UserResponse", DIM)],
        [("│  ", BORDER), (" → 18 │ ", FG), ("from db.models import User, Session", FG),
         ("   # layer violation", BOLD_RED)],
        [("│  ", BORDER), ("   19 │ ", DIM)],
        [("│", BORDER)],
        [("│  ", BORDER), ("  Layer: ", DIM), ("api → db", BOLD_RED),
         ("  (direct)    Expected: ", DIM), ("api → services → db", GREEN)],
        [("│", BORDER)],
        [("│  ", BORDER), ("  → Next: ", DIM),
         ("access db models through service layer interface", GREEN)],
        [("│", BORDER)],
        [("│  ", BORDER), ("  ╰─ ", DIM), ("b1e4a9f", CYAN),
         (" · PR #312 · 4 weeks ago", DIM)],
        [("│", BORDER)],
        [("╰", BORDER), ("─" * 78, BORDER), ("╯", BORDER)],
    ]

    for i, p in enumerate(panel):
        lines.append(p)
        _hold(frames, _make_frame(lines, title), 200)

    _hold(frames, _make_frame(lines, title), 3500)

    _encode_frames(frames, out / "scene08_boundary.mp4")


# ═══════════════════════════════════════════════════════════════════════════
# SCENE 9 — drift brief guardrails  (~10 s)
# ═══════════════════════════════════════════════════════════════════════════


def scene09(out: Path) -> None:
    print("Rendering scene09_brief ...")
    frames: list[tuple[Image.Image, int]] = []
    title = "terminal — drift brief"

    lines = _type_cmd(frames, 'drift brief --task "refactor the auth service"', [], title)
    lines.append("")

    # Scan animation
    for i in range(4):
        dots = "." * i
        _hold(frames, _make_frame(lines + [[("  Resolving scope" + dots, DIM)]], title), 200)
    lines.append([("  Resolving scope... done", DIM)])
    _hold(frames, _make_frame(lines, title), 300)
    lines.append("")

    # Brief header panel
    brief_hdr: list[str | RichLine] = [
        [("╭─── ", BORDER), ("Drift Brief", BLUE), (" ─" * 28, BORDER), ("╮", BORDER)],
        [("│  ", BORDER), ("Task:   ", DIM), ("refactor the auth service", FG)],
        [("│  ", BORDER), ("Scope:  ", DIM), ("src/auth/, src/services/middleware/", FG),
         ("  (confidence: 85%)", DIM)],
        [("│  ", BORDER), ("Risk:   ", DIM), ("MEDIUM", BOLD_YEL),
         (" — high auth volatility, 3 middleware variants", DIM)],
        [("╰", BORDER), ("─" * 78, BORDER), ("╯", BORDER)],
    ]
    for h in brief_hdr:
        lines.append(h)
        _hold(frames, _make_frame(lines, title), 200)

    lines.append("")
    _hold(frames, _make_frame(lines, title), 400)

    # Guardrails panel
    guardrails: list[str | RichLine] = [
        [("╭─── ", BORDER), ("Guardrails (copy to agent prompt)", GREEN), (" ─" * 14, BORDER), ("╮", BORDER)],
        [("│", BORDER)],
        [("│  ", BORDER), ("1. ", FG), ("[PFS]", BOLD_YEL),
         (" One error handler pattern across API routes", FG)],
        [("│  ", BORDER), ("   Do NOT: ", DIM),
         ("mix 4 different try/except styles", RED)],
        [("│", BORDER)],
        [("│  ", BORDER), ("2. ", FG), ("[MDS]", BOLD_YEL),
         (" Single source for middleware chain", FG)],
        [("│  ", BORDER), ("   Do NOT: ", DIM),
         ("reimplement @requires_auth in multiple files", RED)],
        [("│", BORDER)],
        [("│  ", BORDER), ("3. ", FG), ("[AVS]", BOLD_RED),
         (" Keep API ↔ DB boundary intact", FG)],
        [("│  ", BORDER), ("   Do NOT: ", DIM),
         ("import db models directly from api layer", RED)],
        [("│", BORDER)],
        [("╰", BORDER), ("─" * 78, BORDER), ("╯", BORDER)],
    ]
    for g in guardrails:
        lines.append(g)
        _hold(frames, _make_frame(lines, title), 200)

    _hold(frames, _make_frame(lines, title), 3500)

    _encode_frames(frames, out / "scene09_brief.mp4")


# ═══════════════════════════════════════════════════════════════════════════
# SCENE 10 — drift nudge safe_to_commit  (~9 s)
# ═══════════════════════════════════════════════════════════════════════════


def scene10(out: Path) -> None:
    print("Rendering scene10_nudge ...")
    frames: list[tuple[Image.Image, int]] = []
    title = "terminal — drift nudge"

    lines = _type_cmd(frames, "drift nudge", [], title)
    lines.append("")

    # Check animation
    for i in range(4):
        dots = "." * i
        _hold(frames, _make_frame(lines + [[("  Checking diff" + dots, DIM)]], title), 300)
    lines.append([("  Checking diff... done", DIM)])
    _hold(frames, _make_frame(lines, title), 400)
    lines.append("")

    # Result panel
    nudge_panel: list[str | RichLine] = [
        [("╭─── ", BORDER), ("drift nudge", TEAL), (" ─" * 28, BORDER), ("╮", BORDER)],
        [("│", BORDER)],
        [("│  ", BORDER), ("Changed files:   ", DIM), ("3", FG)],
        [("│  ", BORDER), ("New findings:    ", DIM), ("0", GREEN)],
        [("│  ", BORDER), ("Regressions:     ", DIM), ("0", GREEN)],
        [("│  ", BORDER), ("Direction:       ", DIM), ("↗ improving", GREEN)],
        [("│", BORDER)],
        [("│  ", BORDER), ("safe_to_commit:  ", FG), ("true ✓", GREEN)],
        [("│", BORDER)],
        [("╰", BORDER), ("─" * 78, BORDER), ("╯", BORDER)],
    ]
    for n in nudge_panel:
        lines.append(n)
        _hold(frames, _make_frame(lines, title), 250)

    _hold(frames, _make_frame(lines, title), 4000)

    _encode_frames(frames, out / "scene10_nudge.mp4")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════


ALL_SCENES = {
    "scene01": scene01,
    "scene02": scene02,
    "scene03": scene03,
    "scene05": scene05,
    "scene06": scene06,
    "scene07": scene07,
    "scene08": scene08,
    "scene09": scene09,
    "scene10": scene10,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Render trailer terminal scenes (Pillow).")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("demos/trailer/clips"),
        help="Directory for rendered MP4 clips",
    )
    parser.add_argument(
        "--scene",
        type=str,
        default="",
        help="Render only this scene (e.g. scene06)",
    )
    args = parser.parse_args()

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    if args.scene:
        if args.scene not in ALL_SCENES:
            print(f"Unknown scene: {args.scene}")
            print(f"Available: {', '.join(ALL_SCENES)}")
            sys.exit(1)
        ALL_SCENES[args.scene](out)
    else:
        for fn in ALL_SCENES.values():
            fn(out)

    print(f"\nTerminal scenes rendered to {out}")


if __name__ == "__main__":
    main()
