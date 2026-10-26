"""Colour conversions for the colour panel: hex, RGB (0..255) and HSV (hue 0..360, saturation and value 0..1)."""

import colorsys
import re
from collections.abc import Callable

RGB = tuple[int, int, int]
HSV = tuple[float, float, float]

_HEX = re.compile(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def hex_to_rgb(color: str) -> RGB:
    digits = color.lstrip("#")
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)


def rgb_to_hex(rgb: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(min(255, max(0, round(channel))) for channel in rgb))


def rgb_to_hsv(rgb: RGB) -> HSV:
    h, s, v = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
    return h * 360, s, v


def hsv_to_rgb(hsv: HSV) -> RGB:
    h, s, v = hsv
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360, min(1.0, max(0.0, s)), min(1.0, max(0.0, v)))
    return round(r * 255), round(g * 255), round(b * 255)


def hsv_to_hex(hsv: HSV) -> str:
    return rgb_to_hex(hsv_to_rgb(hsv))


def hsv_for(color: str, previous: HSV) -> HSV:
    """The HSV of `color`, keeping what it can't express from `previous`: the hue of a grey, and hue and saturation
    of black, so dragging to the edge of the picker and back doesn't lose them."""
    h, s, v = rgb_to_hsv(hex_to_rgb(color))
    if v == 0:
        return previous[0], previous[1], 0.0
    if s == 0:
        return previous[0], 0.0, v
    return h, s, v


def parse_hex_input(text: str, keyword: Callable[[str], str | None] = lambda text: None) -> str | None:
    """`#rrggbb` (lower case) for typed `#rgb` / `#rrggbb`, with or without `#`, else what `keyword` makes of it
    (colour names); None for anything else."""
    text = text.strip()
    if _HEX.fullmatch(text):
        return rgb_to_hex(hex_to_rgb(text))
    if not text:
        return None
    color = keyword(text)
    return color.lower() if color is not None else None
