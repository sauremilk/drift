"""
Generate text-overlay MP4 clips for trailer scenes 4, 11, 12, 13.

Creates PNG frame sequences per scene, then encodes each sequence
to an MP4 clip via ffmpeg.  All clips are 1920x1080 @ 30 fps with
white text on black background.

Usage:
    .venv/Scripts/python.exe scripts/make_trailer_cards.py [--output-dir demos/trailer/clips]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── Constants ──────────────────────────────────────────────────────────────

W, H = 1920, 1080
BG = (0, 0, 0)
FG = (255, 255, 255)
DIM = (100, 100, 100)
FPS = 30


# ── Font discovery ─────────────────────────────────────────────────────────


def _font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        Path.home() / "AppData/Local/Microsoft/Windows/Fonts/JetBrainsMono-Regular.ttf",
        Path("C:/Windows/Fonts/JetBrainsMono-Regular.ttf"),
        Path("C:/Windows/Fonts/CascadiaMono.ttf"),
        Path("C:/Windows/Fonts/consola.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    # Pillow >=10 default font supports sizing
    return ImageFont.load_default(size)


# ── Drawing helpers ────────────────────────────────────────────────────────


def _black() -> Image.Image:
    return Image.new("RGB", (W, H), BG)


def _draw_lines(
    img: Image.Image,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int] = FG,
    spacing: int = 30,
) -> Image.Image:
    """Draw *lines* centered horizontally and vertically on *img*."""
    draw = ImageDraw.Draw(img)
    bboxes = [draw.textbbox((0, 0), ln, font=font) for ln in lines]
    heights = [bb[3] - bb[1] for bb in bboxes]
    total_h = sum(heights) + spacing * (len(lines) - 1)
    y = (H - total_h) // 2

    for i, ln in enumerate(lines):
        tw = bboxes[i][2] - bboxes[i][0]
        x = (W - tw) // 2
        draw.text((x, y), ln, font=font, fill=color)
        y += heights[i] + spacing
    return img


def _save_frame(img: Image.Image, frame_dir: Path, idx: int) -> None:
    frame_dir.mkdir(parents=True, exist_ok=True)
    img.save(str(frame_dir / f"frame_{idx:04d}.png"))


def _encode(frame_dir: Path, output: Path, num_frames: int) -> None:
    """Encode PNG frame sequence to MP4."""
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(frame_dir / "frame_%04d.png"),
        "-frames:v", str(num_frames),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "18",
        str(output),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"  -> {output}  ({num_frames} frames, {num_frames / FPS:.1f}s)")


# ═══════════════════════════════════════════════════════════════════════════
# Scene 4 — "Your architecture is drifting."  (4 s = 120 frames)
#
#   Beat 1 (0–1 s):    Black
#   Beat 2 (1–1.5 s):  "Your"
#   Beat 3 (1.5–2 s):  "Your architecture"
#   Beat 4 (2–2.5 s):  "Your architecture is"
#   Beat 5 (2.5–4 s):  "Your architecture is drifting."
# ═══════════════════════════════════════════════════════════════════════════


def scene4(out: Path) -> None:
    print("Rendering Scene 4 — The Statement ...")
    fdir = out / "_frames" / "scene04"
    font = _font(64)
    total = 4 * FPS  # 120 frames

    stages: list[tuple[int, str]] = [
        (30, ""),
        (45, "Your"),
        (60, "Your architecture"),
        (75, "Your architecture is"),
        (120, "Your architecture is drifting."),
    ]

    idx = 0
    for end_frame, text in stages:
        img = _black()
        if text:
            _draw_lines(img, [text], font)
        while idx < end_frame:
            _save_frame(img, fdir, idx)
            idx += 1

    _encode(fdir, out / "scene04_statement.mp4", total)


# ═══════════════════════════════════════════════════════════════════════════
# Scene 11 — Facts flash  (6 s = 180 frames)
#
#   Beat 1 (0–1 s):    Black
#   Beat 2 (1–3 s):    "Deterministic. No LLM."
#   Beat 3 (3–4 s):    + "19 signals. ~30 seconds."
#   Beat 4 (4–6 s):    + "Zero install: uvx drift-analyzer analyze --repo ."
# ═══════════════════════════════════════════════════════════════════════════


def scene11(out: Path) -> None:
    print("Rendering Scene 11 — The Facts ...")
    fdir = out / "_frames" / "scene11"
    font = _font(48)
    total = 6 * FPS  # 180 frames

    all_lines = [
        "Deterministic. No LLM.",
        "19 signals. ~30 seconds.",
        "Zero install: uvx drift-analyzer analyze --repo .",
    ]

    stages: list[tuple[int, int]] = [
        (30, 0),    # black
        (90, 1),    # 1 line
        (120, 2),   # 2 lines
        (180, 3),   # 3 lines
    ]

    idx = 0
    for end_frame, n_lines in stages:
        img = _black()
        if n_lines > 0:
            _draw_lines(img, all_lines[:n_lines], font, spacing=40)
        while idx < end_frame:
            _save_frame(img, fdir, idx)
            idx += 1

    _encode(fdir, out / "scene11_facts.mp4", total)


# ═══════════════════════════════════════════════════════════════════════════
# Scene 12 — Tagline in three beats  (6 s = 180 frames)
#
#   Beat 1 (0–1 s):    Black
#   Beat 2 (1–2.5 s):  "Your architecture is drifting."
#   Beat 3 (2.5–3.5 s):+ "Your linter won't tell you."
#   Beat 4 (3.5–6 s):  + "Drift will."
# ═══════════════════════════════════════════════════════════════════════════


def scene12(out: Path) -> None:
    print("Rendering Scene 12 — The Tagline ...")
    fdir = out / "_frames" / "scene12"
    font = _font(56)
    total = 6 * FPS  # 180 frames

    all_lines = [
        "Your architecture is drifting.",
        "Your linter won't tell you.",
        "Drift will.",
    ]

    stages: list[tuple[int, int]] = [
        (30, 0),
        (75, 1),
        (105, 2),
        (180, 3),
    ]

    idx = 0
    for end_frame, n_lines in stages:
        img = _black()
        if n_lines > 0:
            _draw_lines(img, all_lines[:n_lines], font, spacing=36)
        while idx < end_frame:
            _save_frame(img, fdir, idx)
            idx += 1

    _encode(fdir, out / "scene12_tagline.mp4", total)


# ═══════════════════════════════════════════════════════════════════════════
# Scene 13 — URL with blinking cursor  (4 s = 120 frames)
#
#   URL always visible.  Cursor blinks every 0.5 s (15 frames).
# ═══════════════════════════════════════════════════════════════════════════


def scene13(out: Path) -> None:
    print("Rendering Scene 13 — The Door ...")
    fdir = out / "_frames" / "scene13"
    font = _font(52)
    total = 4 * FPS  # 120 frames

    url = "github.com/mick-gsk/drift"

    for idx in range(total):
        img = _black()
        draw = ImageDraw.Draw(img)
        bb = draw.textbbox((0, 0), url, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        x = (W - tw) // 2
        y = (H - th) // 2
        draw.text((x, y), url, font=font, fill=FG)

        # Blinking cursor: visible for 15 frames, hidden for 15
        cursor_on = (idx // 15) % 2 == 0
        if cursor_on:
            cx = x + tw + 8
            draw.rectangle([cx, y, cx + 3, y + th], fill=FG)

        _save_frame(img, fdir, idx)

    _encode(fdir, out / "scene13_url.mp4", total)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate trailer text-card clips.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("demos/trailer/clips"),
        help="Directory for rendered MP4 clips",
    )
    args = parser.parse_args()

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    scene4(out)
    scene11(out)
    scene12(out)
    scene13(out)

    print(f"\nAll text cards rendered to {out}")


if __name__ == "__main__":
    main()
