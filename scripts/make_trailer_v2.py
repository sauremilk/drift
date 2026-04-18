"""
drift-analyzer Premium Trailer — Motion Graphics Renderer (v2 optimized)
=========================================================================

Generates an 85-second cinematic motion-graphics trailer as MP4.
Optimized: numpy compositing + direct pipe to ffmpeg (no temp PNGs).

Usage:
    python scripts/make_trailer.py [--fps 30] [--width 1920] [--height 1080]

Output: work_artifacts/trailer/drift-trailer.mp4
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Globals (set once in render_trailer, used by all helpers)
# ---------------------------------------------------------------------------

W = 1920
H = 1080
FPS = 30
TOTAL_S = 85

# Colours as float32 RGB [0,1]
BLACK_F = np.array([0.0, 0.0, 0.0], dtype=np.float32)
WHITE_F = np.array([1.0, 1.0, 1.0], dtype=np.float32)
BLUE_COLD_F = np.array([18, 28, 48], dtype=np.float32) / 255.0
BLUE_GREY_F = np.array([30, 40, 58], dtype=np.float32) / 255.0
AMBER_F = np.array([255, 180, 60], dtype=np.float32) / 255.0
AMBER_WARM_F = np.array([255, 200, 100], dtype=np.float32) / 255.0
WARM_WHITE_F = np.array([255, 248, 240], dtype=np.float32) / 255.0
DARK_BG_F = np.array([8, 8, 12], dtype=np.float32) / 255.0

WHITE = (255, 255, 255)

# ---------------------------------------------------------------------------
# Font cache
# ---------------------------------------------------------------------------

_FC: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    k = (name, size)
    if k not in _FC:
        for p in [name, f"C:/Windows/Fonts/{name}.ttf", f"C:/Windows/Fonts/{name}.otf"]:
            try:
                _FC[k] = ImageFont.truetype(p, size)
                return _FC[k]
            except (OSError, IOError):
                continue
        _FC[k] = ImageFont.load_default()  # type: ignore[assignment]
    return _FC[k]


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def ease_out(t: float) -> float:
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def ease_in(t: float) -> float:
    t = clamp01(t)
    return t * t * t


def ease_io(t: float) -> float:
    t = clamp01(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def lerp_c(c1: np.ndarray, c2: np.ndarray, t: float) -> np.ndarray:
    return c1 + (c2 - c1) * clamp01(t)


# ---------------------------------------------------------------------------
# Pre-computed assets (lazy, resolution-aware)
# ---------------------------------------------------------------------------

_VIGNETTE: np.ndarray | None = None
_GRID_MASK: np.ndarray | None = None
_CRACK_COORDS: list[tuple[int, int]] | None = None
_PARTICLES: np.ndarray | None = None
_CONN_NODES: np.ndarray | None = None
_CONN_EDGES: list[tuple[int, int, float]] | None = None
_TEXT_CACHE: dict[tuple[str, str, int], np.ndarray] = {}


def _reset_caches() -> None:
    global _VIGNETTE, _GRID_MASK, _CRACK_COORDS, _PARTICLES
    global _CONN_NODES, _CONN_EDGES
    _VIGNETTE = _GRID_MASK = _CRACK_COORDS = _PARTICLES = None
    _CONN_NODES = _CONN_EDGES = None
    _TEXT_CACHE.clear()


def _vignette() -> np.ndarray:
    global _VIGNETTE
    if _VIGNETTE is None:
        cy, cx = H / 2, W / 2
        y = np.arange(H, dtype=np.float32) - cy
        x = np.arange(W, dtype=np.float32) - cx
        YY, XX = np.meshgrid(y, x, indexing="ij")
        d = np.sqrt(XX * XX + YY * YY) / math.sqrt(cx * cx + cy * cy)
        _VIGNETTE = (1.0 - np.clip(d, 0, 1) ** 1.5)[:, :, np.newaxis]
    return _VIGNETTE


def _grid() -> np.ndarray:
    global _GRID_MASK
    if _GRID_MASK is None:
        m = np.zeros((H, W), dtype=np.float32)
        cols, rows, mx, my = 16, 10, 160, 120
        cw, ch = (W - 2 * mx) / cols, (H - 2 * my) / rows
        for i in range(cols + 1):
            x = int(mx + i * cw)
            if 0 <= x < W:
                m[my:H - my, max(0, x - 1):x + 2] = 1.0
        for j in range(rows + 1):
            y = int(my + j * ch)
            if 0 <= y < H:
                m[max(0, y - 1):y + 2, mx:W - mx] = 1.0
        _GRID_MASK = m
    return _GRID_MASK


def _crack_coords() -> list[tuple[int, int]]:
    global _CRACK_COORDS
    if _CRACK_COORDS is None:
        my = 120
        ch = (H - 2 * my) / 10
        cx = int(W * 0.55)
        y_top, y_bot = int(my + 2 * ch), int(my + 7 * ch)
        _CRACK_COORDS = [
            (cx, int(y_top + (s / 40) * (y_bot - y_top)))
            for s in range(41)
        ]
    return _CRACK_COORDS


def _particles(count: int = 40) -> np.ndarray:
    global _PARTICLES
    if _PARTICLES is None or _PARTICLES.shape[0] != count:
        rng = np.random.RandomState(42)
        _PARTICLES = np.column_stack([
            rng.uniform(0, W, count), rng.uniform(0, H, count),
            rng.uniform(0.3, 1.2, count), rng.uniform(0, 2 * np.pi, count),
        ]).astype(np.float32)
    return _PARTICLES


def _conn_graph() -> tuple[np.ndarray, list[tuple[int, int, float]]]:
    global _CONN_NODES, _CONN_EDGES
    if _CONN_NODES is None:
        rng = np.random.RandomState(77)
        n = 12
        nodes = np.column_stack([
            rng.uniform(200, W - 200, n), rng.uniform(200, H - 200, n),
        ]).astype(np.float32)
        edges = []
        for i in range(n):
            for j in range(i + 1, n):
                d = float(np.sqrt((nodes[i, 0] - nodes[j, 0]) ** 2 +
                                  (nodes[i, 1] - nodes[j, 1]) ** 2))
                if d < 500:
                    edges.append((i, j, d))
        _CONN_NODES, _CONN_EDGES = nodes, edges
    return _CONN_NODES, _CONN_EDGES  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Buffer operations
# ---------------------------------------------------------------------------

def _fill(buf: np.ndarray, c: np.ndarray) -> None:
    buf[:, :] = c


def _apply_vig(buf: np.ndarray, strength: float) -> None:
    v = _vignette()
    buf *= (1.0 - strength * (1.0 - v))


def _text_arr(text: str, font_name: str, size: int,
              fill: tuple[int, ...] = WHITE) -> np.ndarray:
    k = (text, font_name, size)
    if k not in _TEXT_CACHE:
        f = _font(font_name, size)
        img = Image.new("RGBA", (W, size + 20), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        bb = draw.textbbox((0, 0), text, font=f)
        tw = bb[2] - bb[0]
        draw.text(((W - tw) // 2, 0), text, font=f,
                  fill=fill + (255,) if len(fill) == 3 else fill)
        _TEXT_CACHE[k] = np.array(img, dtype=np.uint8)
    return _TEXT_CACHE[k]


def _blit_text(buf: np.ndarray, rgba: np.ndarray, y: int, alpha: float) -> None:
    th = rgba.shape[0]
    y1, y2 = max(0, y), min(H, y + th)
    if y2 <= y1:
        return
    s1 = y1 - y
    s2 = s1 + (y2 - y1)
    a = rgba[s1:s2, :, 3:4].astype(np.float32) * (alpha / 255.0)
    src = rgba[s1:s2, :, :3].astype(np.float32) / 255.0
    buf[y1:y2] = buf[y1:y2] * (1 - a) + src * a


def _narration(buf: np.ndarray, text: str, p: float,
               delay: float = 0.1, y: int | None = None) -> None:
    if y is None:
        y = H - 140
    a = ease_out(clamp01((p - delay) / 0.3))
    if p > 0.8:
        a *= ease_out(clamp01((1.0 - p) / 0.2))
    if a < 0.02:
        return
    _blit_text(buf, _text_arr(text, "segoeuil", 38), y, a)


def _draw_particles(buf: np.ndarray, t: float, color: np.ndarray,
                    alpha: float = 0.15, count: int = 30) -> None:
    pts = _particles(count)
    for i in range(min(count, pts.shape[0])):
        bx, by, spd, phase = pts[i]
        x = int((bx + math.sin(t * spd + phase) * 60) % W)
        y = int((by - t * spd * 30) % H)
        a = alpha * (0.5 + 0.5 * math.sin(t * 2 + phase))
        if a < 0.02:
            continue
        r = 2
        y1, y2 = max(0, y - r), min(H, y + r + 1)
        x1, x2 = max(0, x - r), min(W, x + r + 1)
        buf[y1:y2, x1:x2] = buf[y1:y2, x1:x2] * (1 - a) + color * a


def _draw_grid_lines(buf: np.ndarray, color: np.ndarray, alpha: float) -> None:
    m = _grid()[:, :, np.newaxis] * alpha
    buf[:] = buf * (1 - m) + color * m


def _draw_crack(buf: np.ndarray, progress: float) -> None:
    cc = _crack_coords()
    c = np.array([0.7, 0.23, 0.23], dtype=np.float32)
    a = min(progress, 1.0) * 0.5
    offset = int(progress * 8)
    for idx, (cx, cy) in enumerate(cc):
        t = idx / max(1, len(cc) - 1)
        dx = int(math.sin(t * math.pi * 3) * offset)
        x = cx + dx
        if 0 <= x < W and 0 <= cy < H:
            x1, x2 = max(0, x - 1), min(W, x + 2)
            buf[cy, x1:x2] = buf[cy, x1:x2] * (1 - a) + c * a


def _draw_glow(buf: np.ndarray, color: np.ndarray, alpha: float) -> None:
    m = _grid()[:, :, np.newaxis] * alpha * 0.35
    buf[:] = buf * (1 - m) + color * m
    v = _vignette() * alpha * 0.12
    buf[:] = buf * (1 - v) + color * v


def _radial_glow(buf: np.ndarray, cx: float, cy: float,
                 radius: float, color: np.ndarray, alpha: float) -> None:
    y1 = max(0, int(cy - radius))
    y2 = min(H, int(cy + radius))
    x1 = max(0, int(cx - radius))
    x2 = min(W, int(cx + radius))
    if y2 <= y1 or x2 <= x1:
        return
    yy = np.arange(y1, y2, dtype=np.float32) - cy
    xx = np.arange(x1, x2, dtype=np.float32) - cx
    YY, XX = np.meshgrid(yy, xx, indexing="ij")
    d = np.sqrt(XX * XX + YY * YY) / radius
    m = (np.clip(1.0 - d, 0, 1) ** 2 * alpha)[:, :, np.newaxis]
    buf[y1:y2, x1:x2] = buf[y1:y2, x1:x2] * (1 - m) + color * m


# ---------------------------------------------------------------------------
# Scene renderers
# ---------------------------------------------------------------------------

def _s_green_light(buf: np.ndarray, p: float) -> None:
    _fill(buf, lerp_c(BLUE_COLD_F, BLUE_GREY_F, 0.3))
    _radial_glow(buf, W * 0.6, H * 0.45, 250,
                 np.array([0.2, 0.78, 0.31], dtype=np.float32),
                 ease_out(min(p * 3, 1)) * 0.08)
    green = np.array([0.2, 0.78, 0.31], dtype=np.float32)
    for i, (ox, oy) in enumerate([(680, 400), (880, 420), (1080, 380)]):
        a = ease_out(clamp01((p - i * 0.12) * 5)) * 0.7
        if a > 0.02:
            _radial_glow(buf, ox, oy, 30, green, a)
    _draw_particles(buf, p * 6, np.array([0.16, 0.31, 0.24], dtype=np.float32), 0.1, 20)
    _narration(buf, "You push. Tests are green. You move on.", p, 0.1)
    _apply_vig(buf, 0.5)


def _s_routine(buf: np.ndarray, p: float) -> None:
    _fill(buf, lerp_c(BLUE_COLD_F, BLUE_GREY_F, 0.4))
    panels = [(80, 120, 580, 900), (660, 80, 1260, 940), (1340, 140, 1840, 880)]
    panel_c = np.array([0.06, 0.08, 0.14], dtype=np.float32)
    line_c = np.array([0.39, 0.55, 0.71], dtype=np.float32)
    for i, (x1, y1, x2, y2) in enumerate(panels):
        ap = ease_out(clamp01((p - i * 0.1) * 4)) * 0.7
        if ap < 0.02:
            continue
        buf[y1:y2, x1:x2] = buf[y1:y2, x1:x2] * (1 - ap) + panel_c * ap
        lh = 16
        for row in range(int((y2 - y1 - 40) / lh)):
            ly = y1 + 20 + row * lh
            if ly + 8 >= y2 or ly >= H:
                break
            phase = (p * 3 + i * 0.7 + row * 0.3) % 1.0
            lw = int(40 + phase * (x2 - x1 - 80) * 0.6)
            la = 0.25 * (0.3 + 0.7 * math.sin(p * 5 + row * 0.5 + i) ** 2) * ap
            xe = min(x1 + 20 + lw, x2, W)
            buf[ly:ly + 8, x1 + 20:xe] = (
                buf[ly:ly + 8, x1 + 20:xe] * (1 - la) + line_c * la)
    _draw_particles(buf, p * 7, np.array([0.24, 0.31, 0.47], dtype=np.float32), 0.08, 25)
    _narration(buf, "Your agent writes. You review. It looks right.", p, 0.1)
    _apply_vig(buf, 0.45)


def _s_the_pause(buf: np.ndarray, p: float) -> None:
    _fill(buf, lerp_c(BLUE_GREY_F, DARK_BG_F, p * 0.3))
    a = ease_out(clamp01(p * 3))
    if p > 0.6:
        a *= 0.7 + 0.3 * (1 - (p - 0.6) / 0.4)
    _blit_text(buf, _text_arr("It's looked right for weeks.", "segoeuil", 64), H // 2 - 32, a)
    if p > 0.4:
        u = clamp01((p - 0.4) / 0.6) * 0.06
        red = np.array([0.47, 0.12, 0.12], dtype=np.float32)
        buf[:, :120] = buf[:, :120] * (1 - u) + red * u
        buf[:, -120:] = buf[:, -120:] * (1 - u) + red * u
    _draw_particles(buf, p * 5, np.array([0.24, 0.20, 0.27], dtype=np.float32), 0.06, 12)
    _apply_vig(buf, 0.6)


def _s_the_crack(buf: np.ndarray, p: float) -> None:
    _fill(buf, BLUE_COLD_F)
    _draw_grid_lines(buf, np.array([0.24, 0.31, 0.47], dtype=np.float32),
                     ease_out(clamp01(p * 2)) * 0.4)
    crack = ease_in(clamp01((p - 0.3) / 0.7))
    if crack > 0:
        _draw_crack(buf, crack)
    _draw_particles(buf, p * 7, np.array([0.16, 0.20, 0.31], dtype=np.float32), 0.08, 20)
    if p < 0.5:
        _narration(buf, "Something changed three files ago.", p * 2, 0.05)
    else:
        _narration(buf, "You can't see it. Nobody can.", (p - 0.5) * 2, 0.05)
    _apply_vig(buf, 0.55)


def _s_new_vision(buf: np.ndarray, p: float) -> None:
    _fill(buf, lerp_c(BLUE_COLD_F, np.array([0.08, 0.10, 0.16], dtype=np.float32), p))
    _draw_grid_lines(buf, np.array([0.24, 0.31, 0.47], dtype=np.float32), 0.4)
    glow_p = ease_io(clamp01(p * 1.5))
    if glow_p > 0.01:
        _draw_glow(buf, AMBER_F, glow_p)
        _draw_crack(buf, 0.8)
    pc = lerp_c(np.array([0.16, 0.20, 0.31], dtype=np.float32),
                np.array([0.78, 0.63, 0.31], dtype=np.float32), p)
    _draw_particles(buf, p * 10, pc, 0.12 + p * 0.08, 30)
    if p < 0.45:
        _narration(buf, "Your linter reads one file at a time.", p / 0.45, 0.1)
    elif p > 0.55:
        _narration(buf, "Your agent sees no boundaries.", (p - 0.55) / 0.45, 0.1)
    _apply_vig(buf, 0.4)


def _s_the_question(buf: np.ndarray, p: float) -> None:
    _fill(buf, lerp_c(np.array([0.08, 0.10, 0.16], dtype=np.float32),
                       np.array([0.10, 0.11, 0.15], dtype=np.float32), p))
    nodes, edges = _conn_graph()
    reveal = ease_out(clamp01(p * 2))
    for i, j, d in edges:
        a = reveal * (1 - d / 500) * 0.2
        if a < 0.02:
            continue
        c = lerp_c(np.array([0.31, 0.39, 0.55], dtype=np.float32), AMBER_F, p)
        x1i, y1i = int(nodes[i, 0]), int(nodes[i, 1])
        x2i, y2i = int(nodes[j, 0]), int(nodes[j, 1])
        steps = max(abs(x2i - x1i), abs(y2i - y1i))
        if steps < 1:
            continue
        for s in range(0, steps, 4):
            t = s / steps
            px = int(x1i + (x2i - x1i) * t)
            py = int(y1i + (y2i - y1i) * t)
            if 0 <= px < W and 0 <= py < H:
                xl = max(0, px - 1)
                xr = min(W, px + 2)
                buf[py, xl:xr] = buf[py, xl:xr] * (1 - a) + c * a
    node_c = lerp_c(np.array([0.47, 0.59, 0.78], dtype=np.float32), AMBER_WARM_F, p)
    for x, y in nodes:
        _radial_glow(buf, float(x), float(y), 8, node_c, reveal * 0.6)
    if p < 0.6:
        _narration(buf, "What if you could see all of it?", p / 0.6, 0.15)
    _draw_particles(buf, p * 8, np.array([0.63, 0.55, 0.31], dtype=np.float32), 0.08, 15)
    _apply_vig(buf, 0.4)


def _s_the_verdict(buf: np.ndarray, p: float) -> None:
    _fill(buf, BLACK_F)
    if p < 0.7:
        full = "safe_to_commit: false"
        if p < 0.45:
            n = min(len(full), int((p / 0.45) * len(full)) + 1)
            visible = full[:n]
            ta = 1.0
        else:
            visible = full
            ta = 1.0 if p < 0.6 else ease_out(clamp01((0.7 - p) / 0.1))
        _blit_text(buf, _text_arr(visible, "consola", 72), H // 2 - 36, ta)
    else:
        warmth = ease_io(clamp01((p - 0.7) / 0.3))
        _radial_glow(buf, W / 2, H / 2, 350, AMBER_WARM_F, warmth * 0.12)
    if 0.4 < p < 0.85:
        lines = [
            "Every silent change.",
            "Every quiet divergence.",
            "Caught before it compounds.",
            "Not after the damage. Before.",
        ]
        lp = (p - 0.4) / 0.45
        idx = min(len(lines) - 1, int(lp * len(lines)))
        line_p = (lp * len(lines)) - idx
        _narration(buf, lines[idx], min(line_p * 2, 1.0), 0.0, H - 180)


def _s_control(buf: np.ndarray, p: float) -> None:
    _fill(buf, lerp_c(np.array([0.08, 0.086, 0.125], dtype=np.float32),
                       WARM_WHITE_F, ease_io(p) * 0.15))
    warmth = ease_io(clamp01(p * 1.5))
    # Warm gradient from right
    x_grad = (np.arange(W, dtype=np.float32) / W) ** 2 * warmth * 0.14
    m = x_grad[np.newaxis, :, np.newaxis]
    buf[:] = buf * (1 - m) + AMBER_WARM_F * m
    # Blueprint grid
    bp_a = ease_out(clamp01(p * 2)) * 0.12
    bp_c = np.array([0.78, 0.78, 0.82], dtype=np.float32)
    for y in range(200, H - 200, 60):
        buf[y:y + 1, 300:W - 300] = buf[y:y + 1, 300:W - 300] * (1 - bp_a) + bp_c * bp_a
    for x in range(300, W - 300, 80):
        buf[200:H - 200, x:x + 1] = buf[200:H - 200, x:x + 1] * (1 - bp_a) + bp_c * bp_a
    _draw_particles(buf, p * 13, np.array([0.78, 0.75, 0.63], dtype=np.float32), 0.06, 12)
    if p < 0.35:
        _narration(buf, "You don't react anymore.", p / 0.35, 0.1)
    elif p < 0.5:
        _narration(buf, "You already know.", (p - 0.35) / 0.15, 0.1)
    _apply_vig(buf, 0.25)


def _s_witness(buf: np.ndarray, p: float) -> None:
    bg = lerp_c(WARM_WHITE_F, np.array([0.94, 0.94, 0.96], dtype=np.float32), p)
    bg = lerp_c(bg, np.array([0.12, 0.125, 0.165], dtype=np.float32),
                ease_in(clamp01((p - 0.6) / 0.4)) * 0.8)
    _fill(buf, bg)
    fade = 1.0 - ease_in(p)
    _radial_glow(buf, W / 2, H / 2, 400, AMBER_WARM_F, fade * 0.08)
    if p < 0.55:
        _narration(buf, "Your architecture has a witness now.", p / 0.55, 0.1)
    _apply_vig(buf, 0.3 + p * 0.3)


def _s_cta(buf: np.ndarray, p: float) -> None:
    _fill(buf, BLACK_F)
    if 0.2 <= p < 0.55:
        a = ease_out(clamp01((p - 0.2) / 0.1))
        if p > 0.45:
            a *= ease_out(clamp01((0.55 - p) / 0.1))
        _blit_text(buf, _text_arr("Your architecture is drifting.", "segoeuil", 52),
                   H // 2 - 26, a)
    if 0.55 <= p < 0.8:
        a = ease_out(clamp01((p - 0.55) / 0.1))
        if p > 0.72:
            a *= ease_out(clamp01((0.8 - p) / 0.08))
        _blit_text(buf, _text_arr("Your linter won't tell you.", "segoeuil", 52),
                   H // 2 - 26, a)
    if p >= 0.8:
        ba = ease_out(clamp01((p - 0.8) / 0.1))
        _blit_text(buf, _text_arr("drift", "segoeuib", 84), H // 2 - 60, ba)
        ua = ease_out(clamp01((p - 0.88) / 0.08))
        url_arr = _text_arr("github.com/mick-gsk/drift", "segoeui", 28)
        _blit_text(buf, url_arr, H // 2 + 50, ua)


# Scene dispatch table
_SCENES_FN = {
    "green_light": _s_green_light,
    "routine": _s_routine,
    "the_pause": _s_the_pause,
    "the_crack": _s_the_crack,
    "new_vision": _s_new_vision,
    "the_question": _s_the_question,
    "the_verdict": _s_the_verdict,
    "control": _s_control,
    "witness": _s_witness,
    "cta": _s_cta,
}

TIMELINE = [
    ("green_light", 0, 6),
    ("routine", 6, 13),
    ("the_pause", 13, 18),
    ("the_crack", 18, 25),
    ("new_vision", 25, 35),
    ("the_question", 35, 43),
    ("the_verdict", 43, 55),
    ("control", 55, 68),
    ("witness", 68, 75),
    ("cta", 75, 85),
]


def _scene_at(t: float) -> tuple[str, float]:
    for name, s, e in TIMELINE:
        if s <= t < e:
            return name, (t - s) / (e - s)
    return "black", 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def render_trailer(output_path: Path, fps: int = FPS,
                   w: int = 1920, h: int = 1080,
                   total_s: int = TOTAL_S) -> Path:
    global W, H
    W, H = w, h
    _reset_caches()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_frames = total_s * fps
    buf = np.zeros((h, w, 3), dtype=np.float32)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{w}x{h}", "-pix_fmt", "rgb24",
        "-r", str(fps), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(output_path),
    ]

    print(f"Rendering {total_frames} frames @ {fps} fps ({total_s} s) → {output_path}")
    print(f"Resolution: {w}×{h}")
    sys.stdout.flush()

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None

    try:
        for i in range(total_frames):
            t = i / fps
            scene, p = _scene_at(t)
            buf[:] = 0
            fn = _SCENES_FN.get(scene)
            if fn:
                fn(buf, p)
            proc.stdin.write(np.clip(buf * 255, 0, 255).astype(np.uint8).tobytes())
            if (i + 1) % (fps * 5) == 0 or i == total_frames - 1:
                pct = (i + 1) / total_frames * 100
                print(f"  [{pct:5.1f}%] Frame {i + 1}/{total_frames} — {scene}")
                sys.stdout.flush()
    finally:
        proc.stdin.close()
        _, stderr = proc.communicate()

    if proc.returncode != 0:
        print(f"ffmpeg error:\n{stderr.decode()}", file=sys.stderr)
        sys.exit(1)

    sz = output_path.stat().st_size / (1024 * 1024)
    print(f"\nDone! {output_path} ({sz:.1f} MB)")
    return output_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Render drift-analyzer trailer")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--seconds", type=int, default=85)
    ap.add_argument("--output", type=str,
                    default=str(Path(__file__).resolve().parent.parent /
                                "work_artifacts" / "trailer" / "drift-trailer.mp4"))
    a = ap.parse_args()
    render_trailer(Path(a.output), a.fps, a.width, a.height, a.seconds)


if __name__ == "__main__":
    main()
