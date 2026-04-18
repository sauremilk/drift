"""
Drift — 30-Second Premium Launch Film Renderer
================================================

30s × 30fps = 900 frames, 1920×1080 16:9 native (no letterbox).
Visual identity: deep black, graphite, electric blue, clean white type.

Scene plan:
  0- 4s  black_open        — fragmented code streams / tension
  4- 8s  drift_apart       — nodes separating, risk pulse
  8-13s  product_reveal    — architecture graph materialises
 13-19s  interface         — 3 fast UI shots (2s each)
 19-24s  transform         — chaos → order
 24-30s  hero_end          — end card, "Build fast. Stay in control."

On-screen text (German, one phrase per scene):
  1. AI schreibt. Du mergst.
  2. Schwer zu überblicken.
  3. Plötzlich siehst du es.
  4. (no text)
  5. Aus Gefühl wird Signal.
  6. Build fast. Stay in control.

Usage:
    python scripts/make_launch_film.py [--output path/to/file.mp4]
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import warnings
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ═══════════════════════════════════════════════════════════════════════════
# 1. CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

W: int = 1920
H: int = 1080
FPS: int = 30
TOTAL_S: int = 30
GRAIN_STRENGTH: float = 0.011
GRAIN_COUNT: int = 6

# ═══════════════════════════════════════════════════════════════════════════
# 2. COLOR PALETTE  — electric-blue identity
# ═══════════════════════════════════════════════════════════════════════════

BLACK        = np.array([0.000, 0.000, 0.000], dtype=np.float32)
WHITE        = np.array([1.000, 1.000, 1.000], dtype=np.float32)
GRAPHITE_BG  = np.array([  4,   5,   8], dtype=np.float32) / 255.0
GRAPHITE     = np.array([ 10,  12,  18], dtype=np.float32) / 255.0
COOL_GREY    = np.array([ 52,  60,  78], dtype=np.float32) / 255.0

ELECTRIC     = np.array([ 42, 138, 255], dtype=np.float32) / 255.0
BLUE_BRIGHT  = np.array([104, 198, 255], dtype=np.float32) / 255.0
BLUE_DIM     = np.array([ 20,  72, 148], dtype=np.float32) / 255.0

RISK_RED     = np.array([220,  72,  58], dtype=np.float32) / 255.0
RISK_AMBER   = np.array([240, 180,  60], dtype=np.float32) / 255.0

# PIL tuples for text rendering
TEXT_WHITE:     tuple[int, int, int] = (242, 240, 235)
TEXT_DIM:       tuple[int, int, int] = (118, 116, 112)
TEXT_BLUE:      tuple[int, int, int] = (100, 192, 255)
RISK_AMBER_PIL: tuple[int, int, int] = (240, 180,  60)  # PIL equivalent of RISK_AMBER

# ═══════════════════════════════════════════════════════════════════════════
# 3. FONT HELPERS
# ═══════════════════════════════════════════════════════════════════════════

_FC: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    k = (name, size)
    if k not in _FC:
        for p in [name,
                  f"C:/Windows/Fonts/{name}.ttf",
                  f"C:/Windows/Fonts/{name}.otf"]:
            try:
                _FC[k] = ImageFont.truetype(p, size)
                return _FC[k]
            except OSError:
                continue
        warnings.warn(
            f"Font {name!r} (size={size}) nicht gefunden. "
            "PIL-Fallback aktiv — Text wird unlesbar gerendert. "
            "Systemfonts prüfen: C:/Windows/Fonts/",
            stacklevel=2,
        )
        _FC[k] = ImageFont.load_default()  # type: ignore[assignment]
    return _FC[k]


# ═══════════════════════════════════════════════════════════════════════════
# 4. EASING MATH
# ═══════════════════════════════════════════════════════════════════════════

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
    return 4 * t * t * t if t < 0.5 else 1.0 - (-2 * t + 2) ** 3 / 2.0


def ease_out_expo(t: float) -> float:
    t = clamp01(t)
    return 1.0 if t >= 1.0 else 1.0 - 2.0 ** (-10 * t)


def lerp_c(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    return a + (b - a) * clamp01(t)


# ═══════════════════════════════════════════════════════════════════════════
# 5. CACHES
# ═══════════════════════════════════════════════════════════════════════════

_VIGNETTE:      np.ndarray | None = None
_TEXT_CACHE:    dict = {}
_GLOW_CACHE:    dict = {}
_GRAIN_TEXTURES: list[np.ndarray] = []
_BOKEH_STAMPS:  dict[int, np.ndarray] = {}
_CONN_NODES:    np.ndarray | None = None
_NODE_SIZES:    np.ndarray | None = None
_CONN_EDGES:    list[tuple[int, int, float]] = []
_PARTICLES:     np.ndarray | None = None


def _reset_caches() -> None:
    global _VIGNETTE, _CONN_NODES, _NODE_SIZES, _PARTICLES
    _VIGNETTE = _CONN_NODES = _NODE_SIZES = _PARTICLES = None
    _CONN_EDGES.clear()
    _TEXT_CACHE.clear()
    _GLOW_CACHE.clear()
    _GRAIN_TEXTURES.clear()
    _BOKEH_STAMPS.clear()


def _vignette() -> np.ndarray:
    global _VIGNETTE
    if _VIGNETTE is None:
        cy, cx = H / 2.0, W / 2.0
        y = np.arange(H, dtype=np.float32) - cy
        x = np.arange(W, dtype=np.float32) - cx
        YY, XX = np.meshgrid(y, x, indexing="ij")
        d = np.sqrt(XX ** 2 + YY ** 2) / math.sqrt(cx ** 2 + cy ** 2)
        _VIGNETTE = (1.0 - np.clip(d, 0.0, 1.0) ** 1.55)[:, :, np.newaxis]
    return _VIGNETTE


def _bokeh_stamp(radius: int) -> np.ndarray:
    if radius not in _BOKEH_STAMPS:
        s = 2 * radius + 1
        y = np.arange(s, dtype=np.float32) - radius
        x = np.arange(s, dtype=np.float32) - radius
        YY, XX = np.meshgrid(y, x, indexing="ij")
        d = np.sqrt(XX ** 2 + YY ** 2) / max(radius, 1)
        _BOKEH_STAMPS[radius] = np.exp(-d * d * 2.5) * np.clip(1.0 - d, 0.0, 1.0)
    return _BOKEH_STAMPS[radius]


def _init_grain() -> None:
    rng = np.random.RandomState(777)
    _GRAIN_TEXTURES.clear()
    for _ in range(GRAIN_COUNT):
        _GRAIN_TEXTURES.append(
            rng.standard_normal((H, W, 1)).astype(np.float32) * GRAIN_STRENGTH
        )


def _init_conn_graph() -> None:
    global _CONN_NODES, _NODE_SIZES
    arch = Path(__file__).resolve().parent.parent / "arch_graph.json"
    modules: list[dict] = []
    try:
        data = json.loads(arch.read_text(encoding="utf-8"))
        modules = [m for m in data.get("modules", [])
                   if m.get("file_count", 0) >= 2][:24]
    except Exception:
        pass

    cx, cy = W / 2.0, H / 2.0
    if len(modules) >= 5:
        modules.sort(key=lambda m: m.get("file_count", 0), reverse=True)
        n = len(modules)
        inner_n = min(5, n)
        mid_n   = min(8, max(0, n - inner_n))
        outer_n = max(0, n - inner_n - mid_n)
        positions: list[tuple[float, float]] = []
        for k in range(inner_n):
            a = 2 * math.pi * k / max(inner_n, 1) - math.pi / 2
            positions.append((cx + 155 * math.cos(a), cy + 145 * math.sin(a)))
        for k in range(mid_n):
            a = 2 * math.pi * k / max(mid_n, 1) + math.pi / max(mid_n, 1)
            positions.append((cx + 295 * math.cos(a), cy + 275 * math.sin(a)))
        for k in range(outer_n):
            a = 2 * math.pi * k / max(outer_n, 1) + 0.32
            positions.append((cx + 430 * math.cos(a), cy + 400 * math.sin(a)))
        _CONN_NODES = np.array(positions, dtype=np.float32)
        _NODE_SIZES = np.array(
            [max(6, min(20, 5 + m.get("file_count", 1) // 4)) for m in modules],
            dtype=np.float32)
    else:
        rng2 = np.random.RandomState(55)
        n = 20
        pos = []
        for k in range(n):
            ang = 2 * math.pi * k / n
            r   = 168 + (k % 3) * 128
            pos.append((cx + r * math.cos(ang) + rng2.normal(0, 14),
                        cy + r * math.sin(ang) + rng2.normal(0, 14)))
        _CONN_NODES = np.array(pos, dtype=np.float32)
        _NODE_SIZES = np.full(n, 9, dtype=np.float32)

    _CONN_EDGES.clear()
    n = len(_CONN_NODES)
    for i in range(n):
        for j in range(i + 1, n):
            d = float(np.sqrt(
                (_CONN_NODES[i, 0] - _CONN_NODES[j, 0]) ** 2
                + (_CONN_NODES[i, 1] - _CONN_NODES[j, 1]) ** 2))
            if d < 390:
                _CONN_EDGES.append((i, j, d))


def _init_particles(count: int = 40) -> None:
    global _PARTICLES
    rng = np.random.RandomState(42)
    _PARTICLES = np.column_stack([
        rng.uniform(0, W, count),
        rng.uniform(0, H, count),
        rng.uniform(0.12, 0.50, count),
        rng.uniform(0, 2 * np.pi, count),
        rng.choice([3, 5, 7, 10, 12], count),
        rng.uniform(0.30, 0.90, count),
    ]).astype(np.float32)


# ═══════════════════════════════════════════════════════════════════════════
# 6. BUFFER OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════

def _fill(buf: np.ndarray, c: np.ndarray) -> None:
    buf[:, :] = c


def _apply_vig(buf: np.ndarray, strength: float = 0.50) -> None:
    buf *= (1.0 - strength * (1.0 - _vignette()))


def _blit_bokeh(buf: np.ndarray, cx: int, cy: int,
                radius: int, color: np.ndarray, alpha: float) -> None:
    if alpha < 0.01 or radius < 1:
        return
    stamp = _bokeh_stamp(radius)
    y1 = max(0, cy - radius); y2 = min(H, cy + radius + 1)
    x1 = max(0, cx - radius); x2 = min(W, cx + radius + 1)
    if y2 <= y1 or x2 <= x1:
        return
    sy1 = y1 - (cy - radius)
    sx1 = x1 - (cx - radius)
    m = stamp[sy1:sy1 + (y2 - y1), sx1:sx1 + (x2 - x1), np.newaxis] * alpha
    buf[y1:y2, x1:x2] = buf[y1:y2, x1:x2] * (1 - m) + color * m


def _radial_glow(buf: np.ndarray, cx: float, cy: float,
                 radius: float, color: np.ndarray, alpha: float) -> None:
    if alpha < 0.01:
        return
    y1 = max(0, int(cy - radius)); y2 = min(H, int(cy + radius))
    x1 = max(0, int(cx - radius)); x2 = min(W, int(cx + radius))
    if y2 <= y1 or x2 <= x1:
        return
    yy = np.arange(y1, y2, dtype=np.float32) - cy
    xx = np.arange(x1, x2, dtype=np.float32) - cx
    YY, XX = np.meshgrid(yy, xx, indexing="ij")
    d = np.sqrt(XX ** 2 + YY ** 2) / max(radius, 1.0)
    m = (np.exp(-d * d * 2.5) * alpha)[:, :, np.newaxis]
    buf[y1:y2, x1:x2] = buf[y1:y2, x1:x2] * (1 - m) + color * m


def _draw_line(buf: np.ndarray, x0: int, y0: int, x1: int, y1: int,
               color: np.ndarray, alpha: float) -> None:
    """Simple anti-aliased segment via linspace sampling."""
    if alpha < 0.01:
        return
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    xs = np.linspace(x0, x1, steps + 1, dtype=np.float32)
    ys = np.linspace(y0, y1, steps + 1, dtype=np.float32)
    xi = np.clip(xs.astype(np.int32), 0, W - 1)
    yi = np.clip(ys.astype(np.int32), 0, H - 1)
    c  = color * alpha
    buf[yi, xi] = np.clip(buf[yi, xi] + c, 0.0, 1.0)


# Pre-computed Gaussian weights for anamorphic streak (7 pixels, σ≈1.4)
_STREAK_WEIGHTS = np.array(
    [0.05, 0.20, 0.60, 1.00, 0.60, 0.20, 0.05], dtype=np.float32
)


def _anamorphic_streak(buf: np.ndarray, cy: float,
                       alpha: float, color: np.ndarray) -> None:
    """Anamorphic lens flare streak — 7-pixel Gaussian profile over y."""
    if alpha < 0.01:
        return
    center = int(cy)
    for dy, w in enumerate(_STREAK_WEIGHTS):
        row = center - 3 + dy
        if 0 <= row < H:
            buf[row, :] = np.clip(buf[row, :] + color * (alpha * w), 0.0, 1.0)


# ═══════════════════════════════════════════════════════════════════════════
# 7. TEXT RENDERING
# ═══════════════════════════════════════════════════════════════════════════

def _text_tracked_arr(text: str, font_name: str, size: int,
                      tracking: int = 0,
                      fill: tuple[int, ...] = TEXT_WHITE) -> np.ndarray:
    k = ("t", text, font_name, size, tracking, fill)
    if k not in _TEXT_CACHE:
        f  = _font(font_name, size)
        tw = sum(f.getlength(ch) for ch in text) + tracking * max(0, len(text) - 1)
        img  = Image.new("RGBA", (W, size + 40), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        x    = (W - tw) / 2.0
        rgba = fill + (255,) if len(fill) == 3 else fill
        for ch in text:
            draw.text((x, 8), ch, font=f, fill=rgba)
            x += f.getlength(ch) + tracking
        _TEXT_CACHE[k] = np.array(img, dtype=np.uint8)
    return _TEXT_CACHE[k]


def _text_glow(text: str, font_name: str, size: int,
               fill: tuple[int, ...] = TEXT_WHITE,
               tracking: int = 0, glow_radius: int = 12) -> np.ndarray:
    k = ("g", text, font_name, size, fill, tracking, glow_radius)
    if k not in _GLOW_CACHE:
        sharp = _text_tracked_arr(text, font_name, size, tracking, fill)
        _GLOW_CACHE[k] = np.array(
            Image.fromarray(sharp).filter(
                ImageFilter.GaussianBlur(radius=glow_radius)),
            dtype=np.uint8)
    return _GLOW_CACHE[k]


def _blit_text(buf: np.ndarray, rgba: np.ndarray, y: int, alpha: float) -> None:
    th = rgba.shape[0]
    y1 = max(0, y); y2 = min(H, y + th)
    if y2 <= y1:
        return
    s1 = y1 - y; s2 = s1 + (y2 - y1)
    a   = rgba[s1:s2, :, 3:4].astype(np.float32) * (alpha / 255.0)
    src = rgba[s1:s2, :, :3].astype(np.float32) / 255.0
    buf[y1:y2] = buf[y1:y2] * (1.0 - a) + src * a


def _text_hero(buf: np.ndarray, text: str, font_name: str, size: int,
               y: int, alpha: float,
               fill: tuple[int, ...] = TEXT_WHITE, tracking: int = 0,
               glow_radius: int = 14, glow_alpha: float = 0.28) -> None:
    if alpha < 0.02:
        return
    sharp = _text_tracked_arr(text, font_name, size, tracking, fill)
    glow  = _text_glow(text, font_name, size, fill, tracking, glow_radius)
    _blit_text(buf, glow,  y - 4, alpha * glow_alpha)
    _blit_text(buf, sharp, y,     alpha)


# ═══════════════════════════════════════════════════════════════════════════
# 8. COLOR GRADE
# ═══════════════════════════════════════════════════════════════════════════

def _color_grade(buf: np.ndarray) -> None:
    lum = (buf[:, :, 0:1] * 0.2126
           + buf[:, :, 1:2] * 0.7152
           + buf[:, :, 2:3] * 0.0722)
    # Cool shadow cast
    shadow = np.power(1.0 - np.clip(lum * 3.5, 0.0, 1.0), 3.5)
    buf[:, :, 0:1] += shadow * 0.002
    buf[:, :, 1:2] += shadow * 0.003
    buf[:, :, 2:3] += shadow * 0.009
    # Blue shimmer in highlights
    hi = np.clip(lum - 0.60, 0.0, 0.40) / 0.40
    buf[:, :, 2:3] += hi * 0.006
    np.clip(buf, 0.0, 1.0, out=buf)
    # S-curve (smoothstep)
    buf[:] = buf * buf * (3.0 - 2.0 * buf)
    # Gamma 0.72 — slightly open blacks
    np.power(buf, 0.72, out=buf)
    np.clip(buf, 0.0, 1.0, out=buf)


def _add_grain(buf: np.ndarray, frame: int) -> None:
    if _GRAIN_TEXTURES:
        buf += _GRAIN_TEXTURES[frame % len(_GRAIN_TEXTURES)]
        np.clip(buf, 0.0, 1.0, out=buf)


# ═══════════════════════════════════════════════════════════════════════════
# 9. SHARED DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _draw_graph_clean(buf: np.ndarray, alpha: float, t: float,
                      edge_color: np.ndarray = ELECTRIC,
                      node_color: np.ndarray = ELECTRIC,
                      zoom: float = 1.0) -> None:
    """Draw the architecture graph — clean, no drift displacement."""
    nodes = _CONN_NODES
    if nodes is None or alpha < 0.02:
        return
    cx, cy = W / 2.0, H / 2.0
    nz = (nodes - np.array([cx, cy])) * zoom + np.array([cx, cy])

    for i, j, dist in _CONN_EDGES:
        ea = alpha * max(0.0, 1.0 - dist / 380.0) * 0.56
        if ea < 0.02:
            continue
        _draw_line(buf, int(nz[i, 0]), int(nz[i, 1]),
                   int(nz[j, 0]), int(nz[j, 1]), edge_color, ea)

    for ni in range(len(nz)):
        nx, ny = float(nz[ni, 0]), float(nz[ni, 1])
        nsz   = int(_NODE_SIZES[ni]) if _NODE_SIZES is not None else 9
        pulse = 1.0 + 0.06 * math.sin(t * 2.4 + ni * 0.55)
        _blit_bokeh(buf, int(nx), int(ny), nsz, node_color, alpha * 1.45 * pulse)
        _radial_glow(buf, nx, ny, nsz * 2.6 + 4, node_color * 0.65,
                     alpha * pulse * 0.24)


def _draw_graph_drifted(buf: np.ndarray, alpha: float, t: float,
                        drift_px: float,
                        edge_color: np.ndarray = BLUE_DIM,
                        node_color: np.ndarray = BLUE_DIM) -> None:
    """Draw graph with random displacement — visual drift effect."""
    nodes = _CONN_NODES
    if nodes is None or alpha < 0.02:
        return
    n   = len(nodes)
    rng = np.random.RandomState(99)
    dxy = rng.normal(0, 1, (n, 2)).astype(np.float32)

    for i, j, dist in _CONN_EDGES:
        nx1 = float(nodes[i, 0]) + dxy[i, 0] * drift_px
        ny1 = float(nodes[i, 1]) + dxy[i, 1] * drift_px * 0.6
        nx2 = float(nodes[j, 0]) + dxy[j, 0] * drift_px
        ny2 = float(nodes[j, 1]) + dxy[j, 1] * drift_px * 0.6
        # Break some edges when drift is high
        if drift_px > 25 and rng.random() < (drift_px - 25) / 85.0 * 0.55:
            continue
        ea = alpha * max(0.0, 1.0 - dist / 380.0) * 0.42
        if ea < 0.02:
            continue
        _draw_line(buf, int(nx1), int(ny1), int(nx2), int(ny2), edge_color, ea)

    for ni in range(n):
        nx = float(nodes[ni, 0]) + dxy[ni, 0] * drift_px
        ny = float(nodes[ni, 1]) + dxy[ni, 1] * drift_px * 0.6
        nsz = int(_NODE_SIZES[ni]) if _NODE_SIZES is not None else 9
        _blit_bokeh(buf, int(nx), int(ny), nsz, node_color, alpha * 1.3)
        _radial_glow(buf, nx, ny, nsz * 2.2 + 4, node_color * 0.6, alpha * 0.22)


def _bokeh_particles(buf: np.ndarray, t: float, color: np.ndarray,
                     alpha_mult: float = 0.07, count: int = 16) -> None:
    pts = _PARTICLES
    if pts is None:
        return
    n = min(count, pts.shape[0])
    for i in range(n):
        bx, by, spd, phase, rad, a_base = pts[i]
        x = int((bx + math.sin(t * spd * 0.7 + phase) * 80) % W)
        y = int((by - t * spd * 18 + math.cos(t * spd * 0.5 + phase) * 30) % H)
        a = alpha_mult * a_base * (0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 1.5 + phase)))
        if a < 0.01:
            continue
        _blit_bokeh(buf, x, y, int(rad), color, a)


# ═══════════════════════════════════════════════════════════════════════════
# 10. SCENE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _s_black_open(buf: np.ndarray, p: float, t: float) -> None:
    """0–4 s — Abstract darkness. Fragmented code streams, unstable structures.
    On-screen: 'AI schreibt. Du mergst.'
    """
    _fill(buf, BLACK)

    # Horizontal streaming code lines — very dim, cold blue
    rng = np.random.RandomState(11)
    for _i in range(20):
        sy   = rng.uniform(60, H - 60)
        sw   = rng.uniform(50, 320)
        sx   = rng.uniform(80, W - 80)
        ph   = rng.uniform(0, math.pi * 2)
        spd  = rng.uniform(0.28, 0.72)
        la   = (0.035 + p * 0.055) * (0.5 + 0.5 * math.sin(t * spd + ph))
        x0   = int((sx + math.sin(t * 0.38 + ph) * 28) % W)
        x1   = min(W, x0 + int(sw))
        y    = max(0, min(H - 1, int(sy + math.sin(t * 0.28 + ph * 1.3) * 7)))
        if x1 > x0:
            buf[y, x0:x1] = np.clip(buf[y, x0:x1] + BLUE_DIM * la, 0.0, 1.0)

    # Broken dependency fragments — short disconnected line segments
    rng2 = np.random.RandomState(22)
    for _i in range(16):
        x0  = int(rng2.uniform(W * 0.10, W * 0.90))
        y0  = int(rng2.uniform(H * 0.14, H * 0.86))
        ang = rng2.uniform(0, math.pi * 2)
        lng = rng2.uniform(36, 130)
        ph  = rng2.uniform(0, math.pi * 2)
        a   = (0.10 + p * 0.12) * (0.5 + 0.5 * math.sin(t * 0.55 + ph))
        _draw_line(buf, x0, y0,
                   int(x0 + lng * math.cos(ang)),
                   int(y0 + lng * math.sin(ang)),
                   COOL_GREY * 0.45, a)

    # Tension pulse at centre — extremely subtle
    pulse_a = p * 0.10 * (0.5 + 0.5 * math.sin(t * 0.75))
    _radial_glow(buf, W * 0.5, H * 0.5, 380, BLUE_DIM * 0.55, pulse_a)

    # Text: "AI schreibt. Du mergst."
    if p > 0.36:
        ta = ease_out_expo(clamp01((p - 0.36) / 0.24))
        if p > 0.80:
            ta *= ease_out(clamp01((1.0 - p) / 0.18))
        _text_hero(buf, "AI schreibt. Du mergst.", "segoeuil", 54,
                   H // 2 - 27, ta * 0.88,
                   fill=TEXT_WHITE, tracking=2,
                   glow_radius=14, glow_alpha=0.22)

    _apply_vig(buf, 0.68)


def _s_drift_apart(buf: np.ndarray, p: float, t: float) -> None:
    """4–8 s — Complexity increases, nodes drift apart, risk pulse emerges.
    On-screen: 'Schwer zu überblicken.'
    """
    bg = lerp_c(BLACK, GRAPHITE_BG, p * 0.85)
    _fill(buf, bg)

    # Architecture graph drifting — displacement grows with p
    if _CONN_NODES is not None:
        g_alpha   = ease_out(clamp01(p / 0.55)) * 0.72
        drift_px  = ease_in(p) * 105.0
        _draw_graph_drifted(buf, g_alpha, t, drift_px, BLUE_DIM, BLUE_DIM)

    # Risk amber pulse appears in second half
    risk_a = ease_out(clamp01((p - 0.48) / 0.40)) * 0.32
    if risk_a > 0.01:
        pulse_r = 0.5 + 0.5 * math.sin(t * 2.1)
        _radial_glow(buf, W * 0.5, H * 0.38, 270, RISK_AMBER,
                     risk_a * pulse_r * 0.9)
        _radial_glow(buf, W * 0.5, H * 0.38, 110, RISK_AMBER * 1.2,
                     risk_a * pulse_r * 0.35)

    _bokeh_particles(buf, t, BLUE_DIM, 0.03 + p * 0.025, 10)

    # Text: "Schwer zu überblicken."
    if p > 0.28:
        ta = ease_out_expo(clamp01((p - 0.28) / 0.26))
        if p > 0.82:
            ta *= ease_out(clamp01((1.0 - p) / 0.16))
        _text_hero(buf, "Schwer zu \u00fcberblicken.", "segoeuil", 54,
                   H // 2 - 27, ta * 0.86,
                   fill=TEXT_WHITE, tracking=2,
                   glow_radius=14, glow_alpha=0.22)

    _apply_vig(buf, 0.56)


def _s_product_reveal(buf: np.ndarray, p: float, t: float) -> None:
    """8–13 s — Drift interface emerges from darkness. Architecture map stabilises.
    On-screen: 'Plötzlich siehst du es.'
    """
    bg = lerp_c(BLACK, GRAPHITE_BG, p * 0.78)
    _fill(buf, bg)

    # Volumetric light source building at centre
    light_a = ease_out_expo(clamp01(p / 0.58))
    _radial_glow(buf, W * 0.5, H * 0.47, 520, ELECTRIC * 0.25, light_a * 0.18)
    _radial_glow(buf, W * 0.5, H * 0.47, 210, BLUE_BRIGHT * 0.55, light_a * 0.13)
    _radial_glow(buf, W * 0.5, H * 0.47, 70,  WHITE * 0.9,        light_a * 0.05)

    # Nodes blink in staggered — materialising from darkness
    if _CONN_NODES is not None:
        n = len(_CONN_NODES)
        for ni in range(n):
            reveal_p = clamp01((p - ni * 0.017) / 0.24)
            na = ease_out_expo(reveal_p)
            if na < 0.02:
                continue
            nx = float(_CONN_NODES[ni, 0])
            ny = float(_CONN_NODES[ni, 1])
            nsz   = int(_NODE_SIZES[ni]) if _NODE_SIZES is not None else 9
            pulse = 1.0 + 0.06 * math.sin(t * 2.5 + ni * 0.6)
            _blit_bokeh(buf, int(nx), int(ny), nsz, ELECTRIC, na * 1.55 * pulse)
            _radial_glow(buf, nx, ny, nsz * 3.0 + 5, ELECTRIC * 0.58,
                         na * pulse * 0.27)

        # Edges: reveal after nodes, slow fade in
        if p > 0.32:
            ep = ease_out(clamp01((p - 0.32) / 0.48))
            for i, j, dist in _CONN_EDGES:
                ea = ep * max(0.0, 1.0 - dist / 375.0) * 0.56
                if ea < 0.02:
                    continue
                _draw_line(buf,
                           int(_CONN_NODES[i, 0]), int(_CONN_NODES[i, 1]),
                           int(_CONN_NODES[j, 0]), int(_CONN_NODES[j, 1]),
                           ELECTRIC, ea)

    # Anamorphic streak at brightness peak
    if p > 0.58:
        sa = ease_out_expo(clamp01((p - 0.58) / 0.24)) * 0.26
        _anamorphic_streak(buf, H * 0.47, sa, BLUE_BRIGHT * 0.65)

    # Text: "Plötzlich siehst du es."
    if p > 0.46:
        ta = ease_out_expo(clamp01((p - 0.46) / 0.28))
        if p > 0.86:
            ta *= ease_out(clamp01((1.0 - p) / 0.13))
        _text_hero(buf, "Plötzlich siehst du es.", "segoeuil", 54,
                   int(H * 0.78), ta * 0.90,
                   fill=TEXT_WHITE, tracking=2,
                   glow_radius=12, glow_alpha=0.24)

    _apply_vig(buf, 0.42)


# ── Interface Scene: three 2-second sub-shots ──────────────────────────────

def _shot_a_dep_graph(buf: np.ndarray, p: float, t: float) -> None:
    """Shot A (0-2 s relative) — Clean dependency graph, slow dolly-in."""
    _fill(buf, GRAPHITE_BG)
    zoom = 1.0 + ease_io(p) * 0.07
    _draw_graph_clean(buf, 0.92, t, ELECTRIC, ELECTRIC, zoom)
    _radial_glow(buf, W * 0.5, H * 0.5, 340, ELECTRIC * 0.22, 0.34)
    _radial_glow(buf, W * 0.5, H * 0.5, 120, BLUE_BRIGHT * 0.40, 0.18)
    # Scene identity text
    _text_hero(buf, "Architektur.", "segoeuil", 38,
               int(H * 0.80), ease_out(p) * 0.72,
               fill=TEXT_WHITE, tracking=2,
               glow_radius=10, glow_alpha=0.18)
    # Entry fade-in
    fade = ease_out(clamp01(p / 0.18))
    if fade < 0.98:
        buf[:] = buf * fade


def _shot_b_hotspot(buf: np.ndarray, p: float, t: float) -> None:
    """Shot B (0-2 s relative) — Drift hotspot: 3 nodes lit in risk amber."""
    _fill(buf, GRAPHITE_BG)
    nodes = _CONN_NODES
    if nodes is None:
        return
    n           = len(nodes)
    hot_set     = set(range(min(3, n)))

    # All edges dim
    for i, j, dist in _CONN_EDGES:
        ea = max(0.0, 1.0 - dist / 380.0) * 0.18
        _draw_line(buf, int(nodes[i, 0]), int(nodes[i, 1]),
                   int(nodes[j, 0]), int(nodes[j, 1]), BLUE_DIM, ea)

    # Hot edges between hotspot nodes
    ha_edge = ease_out(p) * 0.80
    for i, j, dist in _CONN_EDGES:
        if i in hot_set and j in hot_set:
            _draw_line(buf, int(nodes[i, 0]), int(nodes[i, 1]),
                       int(nodes[j, 0]), int(nodes[j, 1]),
                       RISK_AMBER, ha_edge)

    # All nodes
    for ni in range(n):
        nx  = float(nodes[ni, 0])
        ny  = float(nodes[ni, 1])
        nsz = int(_NODE_SIZES[ni]) if _NODE_SIZES is not None else 9
        if ni in hot_set:
            pulse = 1.0 + 0.16 * math.sin(t * 3.0 + ni * 1.2)
            na    = ease_out(p) * 1.55 * pulse
            _blit_bokeh(buf, int(nx), int(ny), nsz + 2, RISK_AMBER, na)
            _radial_glow(buf, nx, ny, (nsz + 2) * 3.2 + 8, RISK_AMBER,
                         na * 0.38 * pulse)
        else:
            _blit_bokeh(buf, int(nx), int(ny), nsz, BLUE_DIM * 0.75, 0.56)

    # Score label floating above hotspot centroid
    if p > 0.38 and hot_set:
        hx = float(np.mean([nodes[i, 0] for i in hot_set]))
        hy = float(np.mean([nodes[i, 1] for i in hot_set]))
        la = ease_out_expo(clamp01((p - 0.38) / 0.28))
        # Heat glow
        pr = 0.5 + 0.5 * math.sin(t * 2.0)
        _radial_glow(buf, hx, hy, 170, RISK_AMBER * 0.8, la * 0.30 * pr)
        # Score badge
        _text_hero(buf, "8.4 HIGH", "segoeuib", 36,
                   int(H * 0.80), la * 0.92,
                   fill=RISK_AMBER_PIL, glow_radius=12, glow_alpha=0.42)
        # Anchor label — explains the score as a Drift signal
        _text_hero(buf, "Strukturelle Erosion erkannt.", "segoeuil", 24,
                   int(H * 0.87), la * 0.55,
                   fill=TEXT_DIM, glow_radius=6, glow_alpha=0.12)

    fade = ease_out(clamp01(p / 0.15))
    if fade < 0.98:
        buf[:] = buf * fade


def _shot_c_risk_indicator(buf: np.ndarray, p: float, t: float) -> None:
    """Shot C (0-2 s relative) — Minimal risk score panel, centred."""
    _fill(buf, BLACK)
    _radial_glow(buf, W * 0.5, H * 0.5, 390, GRAPHITE * 0.9, 0.52)
    # Atmospheric amber glow anchors panel to scene
    _radial_glow(buf, W * 0.5, H * 0.5 + 30, 380, RISK_AMBER * 0.35,
                 ease_out(p) * 0.22)

    cx, cy  = W // 2, H // 2
    pw, ph  = 680, 290
    px, py  = cx - pw // 2, cy - ph // 2
    pa      = int(195 * ease_out(p))

    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Panel background
    try:
        draw.rounded_rectangle([px, py, px + pw, py + ph],
                               radius=14, fill=(7, 9, 14, pa))
    except TypeError:
        draw.rectangle([px, py, px + pw, py + ph], fill=(7, 9, 14, pa))

    # "drift score" label — dynamically centred, font 22
    la    = int(210 * ease_out_expo(clamp01((p - 0.08) / 0.28)))
    lbl_f = _font("segoeuil", 22)
    lbl_w = int(draw.textlength("drift score", font=lbl_f))
    draw.text((cx - lbl_w // 2, py + 28), "drift score",
              font=lbl_f, fill=(72, 84, 108, la))

    # Score number — large, RISK_AMBER
    sa      = int(255 * ease_out_expo(clamp01((p - 0.12) / 0.32)))
    score_f = _font("segoeuib", 110)
    bb      = draw.textbbox((0, 0), "8.4", font=score_f)
    sw      = bb[2] - bb[0]
    draw.text((cx - sw // 2, py + 52), "8.4", font=score_f,
              fill=(*RISK_AMBER_PIL, sa))

    # HIGH label
    sev_a = int(195 * ease_out_expo(clamp01((p - 0.28) / 0.28)))
    sev_f = _font("segoeuib", 24)
    sev_w = int(draw.textlength("HIGH", font=sev_f))
    draw.text((cx - sev_w // 2, py + 182), "HIGH",
              font=sev_f, fill=(*RISK_AMBER_PIL, sev_a))

    # Progress bar
    bar_y  = py + 226
    bar_w  = pw - 56
    bar_x  = px + 28
    bar_h  = 8
    bar_f  = ease_out(clamp01((p - 0.18) / 0.48)) * 0.84  # 8.4/10
    bar_a  = int(150 * ease_out(p))
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
                   fill=(18, 22, 30, bar_a))
    fw = int(bar_w * bar_f)
    if fw > 0:
        draw.rectangle([bar_x, bar_y, bar_x + fw, bar_y + bar_h],
                       fill=(*RISK_AMBER_PIL, int(215 * ease_out(p))))

    # Signal name
    sig_a = int(195 * ease_out_expo(clamp01((p - 0.38) / 0.28)))
    draw.text((bar_x, py + 250), "AVS  \u00b7  arch_vector_similarity",
              font=_font("consola", 18), fill=(102, 118, 148, sig_a))

    arr   = np.array(img, dtype=np.float32) / 255.0
    a_ch  = arr[:, :, 3:4]
    buf[:] = buf * (1.0 - a_ch) + arr[:, :, :3] * a_ch

    fade = ease_out(clamp01(p / 0.14))
    if fade < 0.98:
        buf[:] = buf * fade


def _s_interface(buf: np.ndarray, p: float, t: float) -> None:
    """13–19 s — Three fast premium UI shots. No on-screen text."""
    if p < 1 / 3:
        sp = p * 3.0
        _shot_a_dep_graph(buf, sp, t)
    elif p < 2 / 3:
        sp = (p - 1 / 3) * 3.0
        _shot_b_hotspot(buf, sp, t)
    else:
        sp = (p - 2 / 3) * 3.0
        _shot_c_risk_indicator(buf, sp, t)

    _apply_vig(buf, 0.38)


def _s_transform(buf: np.ndarray, p: float, t: float) -> None:
    """19–24 s — Chaos resolves into order. Confidence replaces ambiguity.
    On-screen: 'Aus Gefühl wird Signal.'
    """
    # Entry fade: Szene startet von BLACK (Interface-Ausgang), kein Hard-Jump
    entry = ease_out(clamp01(p / 0.14))
    bg = lerp_c(BLACK, lerp_c(GRAPHITE_BG, BLACK, p * 0.55), entry)
    _fill(buf, bg)

    order   = ease_out_expo(clamp01((p - 0.26) / 0.52))
    chaos   = ease_out(clamp01(1.0 - p * 2.4))

    if _CONN_NODES is not None:
        n     = len(_CONN_NODES)
        rng_d = np.random.RandomState(33)
        dxy   = rng_d.normal(0, 1, (n, 2)).astype(np.float32)
        dpx   = chaos * 78.0

        for i, j, dist in _CONN_EDGES:
            nx1 = float(_CONN_NODES[i, 0]) + dxy[i, 0] * dpx
            ny1 = float(_CONN_NODES[i, 1]) + dxy[i, 1] * dpx * 0.6
            nx2 = float(_CONN_NODES[j, 0]) + dxy[j, 0] * dpx
            ny2 = float(_CONN_NODES[j, 1]) + dxy[j, 1] * dpx * 0.6
            col = lerp_c(COOL_GREY * 0.38, ELECTRIC, order)
            ea  = (chaos * 0.34 + order * 0.55) * max(0.0, 1.0 - dist / 380.0)
            if ea < 0.02:
                continue
            _draw_line(buf, int(nx1), int(ny1), int(nx2), int(ny2), col, ea)

        for ni in range(n):
            nx_c = float(_CONN_NODES[ni, 0]) + dxy[ni, 0] * dpx
            ny_c = float(_CONN_NODES[ni, 1]) + dxy[ni, 1] * dpx * 0.6
            nx_o = float(_CONN_NODES[ni, 0])
            ny_o = float(_CONN_NODES[ni, 1])
            nx   = nx_c + (nx_o - nx_c) * order
            ny   = ny_c + (ny_o - ny_c) * order
            nsz  = int(_NODE_SIZES[ni]) if _NODE_SIZES is not None else 9
            col  = lerp_c(COOL_GREY * 0.55, ELECTRIC, order)
            a    = 0.52 + order * 0.68
            pulse = 1.0 + 0.06 * math.sin(t * 2.2 + ni * 0.5) * order
            _blit_bokeh(buf, int(nx), int(ny), nsz, col, a * 1.25 * pulse)
            _radial_glow(buf, nx, ny, nsz * 2.5 + 4, col * 0.65, a * 0.24 * pulse)

    # Centre glow emerges as order restores
    if order > 0.08:
        _radial_glow(buf, W * 0.5, H * 0.47, 360, ELECTRIC * 0.38, order * 0.20)

    if p > 0.38:
        sa = ease_out_expo(clamp01((p - 0.38) / 0.28)) * 0.22
        _anamorphic_streak(buf, H * 0.47, sa, BLUE_BRIGHT * 0.5)

    _bokeh_particles(buf, t, ELECTRIC, 0.04 + order * 0.04, 8)

    # Text: "Aus Gefühl wird Signal."
    if p > 0.22:
        ta = ease_out_expo(clamp01((p - 0.22) / 0.28))
        if p > 0.82:
            ta *= ease_out(clamp01((1.0 - p) / 0.16))
        _text_hero(buf, "Aus Gef\u00fchl wird Signal.", "segoeuil", 54,
                   H // 2 - 27, ta * 0.88,
                   fill=TEXT_WHITE, tracking=2,
                   glow_radius=14, glow_alpha=0.22)

    _apply_vig(buf, 0.46)


def _s_hero_end(buf: np.ndarray, p: float, t: float) -> None:
    """24–30 s — Hero end card. Minimal, sovereign, centred.
    On-screen: 'Build fast. Stay in control.' + Drift logo + URL.
    End card holds clean for last 3 s.
    """
    _fill(buf, BLACK)

    # Restrained centre glow — barely there
    breath = 0.5 + 0.5 * math.sin(t * 1.18)
    ga     = ease_out(clamp01(p / 0.48)) * (0.07 + breath * 0.035)
    _radial_glow(buf, W * 0.5, H * 0.5 - 10, 440, ELECTRIC * 0.28, ga)
    _radial_glow(buf, W * 0.5, H * 0.5 - 10, 150, WHITE * 0.5,     ga * 0.20)

    # "drift" logotype — white, massive
    logo_a      = ease_out_expo(clamp01(p / 0.17))
    logo_breath = 1.0 + math.sin(t * 1.4) * 0.004
    _text_hero(buf, "drift", "segoeuib", 196,
               H // 2 - 136, min(logo_a * logo_breath, 1.0),
               fill=TEXT_WHITE, tracking=32,
               glow_radius=40, glow_alpha=0.11)

    # Tagline: "Build fast. Stay in control."
    if p > 0.20:
        tag_a = ease_out_expo(clamp01((p - 0.20) / 0.22))
        _text_hero(buf, "Build fast. Stay in control.", "segoeuil", 34,
                   H // 2 + 68, tag_a * 0.70,
                   fill=(208, 206, 200), tracking=2,
                   glow_radius=9, glow_alpha=0.18)

    # URL placeholder
    if p > 0.46:
        url_a = ease_out_expo(clamp01((p - 0.46) / 0.22))
        _text_hero(buf, "github.com/mick-gsk/drift", "segoeui", 22,
                   H // 2 + 120, url_a * 0.40,
                   fill=TEXT_DIM, glow_radius=5, glow_alpha=0.10)

    _apply_vig(buf, 0.56)


# ═══════════════════════════════════════════════════════════════════════════
# 11. TIMELINE & DISPATCH
# ═══════════════════════════════════════════════════════════════════════════

_TIMELINE: list[tuple[float, float, str]] = [
    ( 0.0,  4.0, "_s_black_open"),
    ( 4.0,  8.0, "_s_drift_apart"),
    ( 8.0, 13.0, "_s_product_reveal"),
    (13.0, 19.0, "_s_interface"),
    (19.0, 24.0, "_s_transform"),
    (24.0, 30.0, "_s_hero_end"),
]

_SCENE_FN = {
    "_s_black_open":     _s_black_open,
    "_s_drift_apart":    _s_drift_apart,
    "_s_product_reveal": _s_product_reveal,
    "_s_interface":      _s_interface,
    "_s_transform":      _s_transform,
    "_s_hero_end":       _s_hero_end,
}


def _dispatch(frame: int) -> np.ndarray:
    t   = frame / FPS
    buf = np.zeros((H, W, 3), dtype=np.float32)

    for start_s, end_s, fn_name in _TIMELINE:
        if start_s <= t < end_s:
            p = (t - start_s) / (end_s - start_s)
            _SCENE_FN[fn_name](buf, p, t)
            break

    _add_grain(buf, frame)
    _color_grade(buf)
    return buf


# ═══════════════════════════════════════════════════════════════════════════
# 12. MAIN
# ═══════════════════════════════════════════════════════════════════════════

# One sample per scene: (scene_fn_name, output_label, progress_0_to_1)
_TESTFRAME_SAMPLES: list[tuple[str, str, float]] = [
    ("_s_black_open",     "black_open",     0.65),
    ("_s_drift_apart",    "drift_apart",    0.65),
    ("_s_product_reveal", "product_reveal", 0.65),
    ("_s_interface",      "interface_a",    0.10),  # Shot A mid
    ("_s_interface",      "interface_b",    0.43),  # Shot B mid
    ("_s_interface",      "interface_c",    0.77),  # Shot C mid
    ("_s_transform",      "transform",      0.65),
    ("_s_hero_end",       "hero_end",       0.65),
]


def _export_testframes(out_dir: Path) -> None:
    """Export 8 reference testframes as lf_*.png for visual review."""
    _reset_caches()
    _init_grain()
    _init_conn_graph()
    _init_particles()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Exporting {len(_TESTFRAME_SAMPLES)} testframes -> {out_dir}")
    for fn_name, label, p in _TESTFRAME_SAMPLES:
        start_s, end_s = next(
            (s, e) for s, e, n in _TIMELINE if n == fn_name)
        t = start_s + (end_s - start_s) * p
        frame_idx = int(t * FPS)
        buf = np.zeros((H, W, 3), dtype=np.float32)
        _SCENE_FN[fn_name](buf, p, t)
        _add_grain(buf, frame_idx)
        _color_grade(buf)
        out_path = out_dir / f"lf_{label}.png"
        Image.fromarray(
            np.clip(buf * 255, 0, 255).astype(np.uint8)
        ).save(str(out_path))
        print(f"  → {out_path}")
    print("Done.")


def _ffmpeg_cmd(out: Path) -> list[str]:
    return [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pixel_format", "rgb24",
        "-video_size", f"{W}x{H}",
        "-framerate", str(FPS),
        "-i", "pipe:0",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "17",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(out),
    ]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Render Drift 30s launch film")
    ap.add_argument("--output", default="work_artifacts/trailer/drift-launch-film.mp4")
    ap.add_argument("--fps",    type=int, default=FPS)
    ap.add_argument("--testframes", metavar="DIR", default=None,
                    help="Export 8 reference frames as lf_*.png and exit.")
    args = ap.parse_args()

    if args.testframes:
        _export_testframes(Path(args.testframes))
        return

    out   = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    total = TOTAL_S * FPS

    print(f"Rendering {total} frames @ {FPS} fps ({TOTAL_S}s) -> {out}")

    _reset_caches()
    _init_grain()
    _init_conn_graph()
    _init_particles()

    ff = subprocess.Popen(
        _ffmpeg_cmd(out),
        stdin=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    try:
        for f in range(total):
            frame_buf = _dispatch(f)
            ff.stdin.write(  # type: ignore[union-attr]
                np.clip(frame_buf * 255, 0, 255).astype(np.uint8).tobytes())
            if f % 90 == 0 or f == total - 1:
                pct  = 100 * (f + 1) / total
                t_s  = f / FPS
                name = next(
                    (nm for s, e, nm in _TIMELINE if s <= t_s < e),
                    _TIMELINE[-1][2])
                print(f"  [{pct:5.1f}%] Frame {f+1}/{total} -- {name}")
        ff.stdin.close()  # type: ignore[union-attr]
        ff.wait()
    except Exception:
        ff.kill()
        raise

    mb = out.stat().st_size / 1024 ** 2
    print(f"Done! {out} ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
