"""Render a self-contained SVG badge for the drift score.

The badge is modeled after shields.io flat-style badges so it blends
with existing README badge rows.  No external HTTP request needed.
"""

from __future__ import annotations

_TEMPLATE = """\
<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20" role="img" \
aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_w}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_w}" height="20" fill="#555"/>
    <rect x="{label_w}" width="{value_w}" height="20" fill="{color}"/>
    <rect width="{total_w}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" \
font-family="Verdana,Geneva,DejaVu Sans,sans-serif" \
text-rendering="geometricPrecision" font-size="11">
    <text aria-hidden="true" x="{label_cx}" y="150" fill="#010101" \
fill-opacity=".3" transform="scale(.1)" textLength="{label_tw}">{label}</text>
    <text x="{label_cx}" y="140" transform="scale(.1)" \
textLength="{label_tw}">{label}</text>
    <text aria-hidden="true" x="{value_cx}" y="150" fill="#010101" \
fill-opacity=".3" transform="scale(.1)" textLength="{value_tw}">{value}</text>
    <text x="{value_cx}" y="140" transform="scale(.1)" \
textLength="{value_tw}">{value}</text>
  </g>
</svg>
"""


def _estimate_text_width(text: str) -> int:
    """Return estimated pixel width for Verdana 11px.

    Uses a simple per-character table that approximates real glyph widths.
    """
    widths: dict[str, float] = {
        " ": 3.3,
        ".": 3.3,
        "0": 6.8,
        "1": 6.8,
        "2": 6.8,
        "3": 6.8,
        "4": 6.8,
        "5": 6.8,
        "6": 6.8,
        "7": 6.8,
        "8": 6.8,
        "9": 6.8,
    }
    default_width = 6.5
    return int(sum(widths.get(ch, default_width) for ch in text) + 0.5)


# shields.io named-color → hex mapping (flat style)
_COLOR_MAP: dict[str, str] = {
    "brightgreen": "#4c1",
    "green": "#97ca00",
    "yellowgreen": "#a4a61d",
    "yellow": "#dfb317",
    "orange": "#fe7d37",
    "red": "#e05d44",
    "critical": "#e05d44",
    "blue": "#007ec6",
    "lightgrey": "#9f9f9f",
}


def render_badge_svg(label: str, value: str, color: str) -> str:
    """Return a self-contained SVG badge string.

    Parameters
    ----------
    label:
        Left-hand text (e.g. ``"drift score"``).
    value:
        Right-hand text (e.g. ``"0.50"``).
    color:
        Named color (``"brightgreen"``, ``"yellow"``, ``"orange"``,
        ``"critical"``) **or** a hex string like ``"#4c1"``.
    """
    hex_color = _COLOR_MAP.get(color, color)
    padding = 10  # 5px each side

    label_tw = _estimate_text_width(label) * 10  # textLength in 0.1px
    value_tw = _estimate_text_width(value) * 10

    label_w = _estimate_text_width(label) + padding
    value_w = _estimate_text_width(value) + padding
    total_w = label_w + value_w

    label_cx = (label_w / 2) * 10  # center x in 0.1px
    value_cx = (label_w + value_w / 2) * 10

    return _TEMPLATE.format(
        total_w=total_w,
        label_w=label_w,
        value_w=value_w,
        label_tw=int(label_tw),
        value_tw=int(value_tw),
        label_cx=int(label_cx),
        value_cx=int(value_cx),
        label=label,
        value=value,
        color=hex_color,
    )
