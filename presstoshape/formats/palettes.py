"""Palette files, as Lospec and pixel-art tools offer them: GIMP `.gpl`, plain `.hex` (one colour per line), JASC
`.pal`, Paint.NET `.txt` (with alpha) and palette images (each distinct pixel colour). Text in, text out: callers
read and write the files, and decode images to RGBA pixels themselves."""

import re
from collections.abc import Callable

from presstoshape.formats.gpl import HEADER as GPL_HEADER
from presstoshape.formats.gpl import read_gpl, write_gpl
from presstoshape.geometry.colours import hex_to_rgb, rgb_to_hex

# (name, "#rrggbb", opacity)
PaletteColor = tuple[str, str, float]

READ_SUFFIXES = (".gpl", ".hex", ".pal", ".txt")
WRITE_SUFFIXES = (".gpl", ".hex", ".pal", ".txt")
# More distinct colours than this in an image means it's a picture, not a palette.
MAX_IMAGE_COLORS = 1024

_HEX_LINE = re.compile(r"#?([0-9a-fA-F]{6})")
_PAINT_NET_LINE = re.compile(r"([0-9a-fA-F]{2})([0-9a-fA-F]{6})")
_JASC_HEADER = "JASC-PAL"
_PAINT_NET_HEADER = ";paint.net palette file"


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.lstrip("﻿").splitlines()]


def _unnamed_if_hex(name: str, color: str) -> str:
    """Lospec's GIMP palettes put the hex code where the name goes; that's no name."""
    return "" if name.lstrip("#").lower() == color[1:] else name


def read_gpl_palette(text: str) -> list[PaletteColor]:
    return [(_unnamed_if_hex(name, color), color, 1.0) for name, color in read_gpl(text)]


def read_hex(text: str) -> list[PaletteColor]:
    colors = []
    for line in _lines(text):
        match = _HEX_LINE.fullmatch(line)
        if match is not None:
            colors.append(("", "#" + match.group(1).lower(), 1.0))
        elif line and not line.startswith((";", "//")):
            raise ValueError(f"not a hex palette line: {line[:40]!r}")
    if not colors:
        raise ValueError("no colours")
    return colors


def read_jasc(text: str) -> list[PaletteColor]:
    lines = _lines(text)
    if len(lines) < 3 or lines[0] != _JASC_HEADER:
        raise ValueError("not a JASC palette")
    colors = []
    for line in lines[3:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            rgb = tuple(int(part) for part in parts[:3])
        except ValueError:
            continue
        if all(0 <= channel <= 255 for channel in rgb):
            colors.append(("", rgb_to_hex(rgb), 1.0))
    return colors


def read_paint_net(text: str) -> list[PaletteColor]:
    """`AARRGGBB` per line, `;` comments; the alpha becomes the swatch opacity."""
    colors = []
    for line in _lines(text):
        if not line or line.startswith(";"):
            continue
        match = _PAINT_NET_LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"not a Paint.NET palette line: {line[:40]!r}")
        alpha = int(match.group(1), 16) / 255
        colors.append(("", "#" + match.group(2).lower(), round(alpha, 3)))
    if not colors:
        raise ValueError("no colours")
    return colors


_READERS: dict[str, Callable[[str], list[PaletteColor]]] = {
    ".gpl": read_gpl_palette,
    ".hex": read_hex,
    ".pal": read_jasc,
    ".txt": read_paint_net,
}


def read_palette(suffix: str, text: str) -> list[PaletteColor]:
    """The colours of a palette file. The header decides where it is clear (a GIMP palette saved as .txt still
    reads), else the suffix. Raises ValueError for anything that isn't a palette."""
    first = next((line for line in _lines(text) if line), "")
    if first == GPL_HEADER:
        return read_gpl_palette(text)
    if first == _JASC_HEADER:
        return read_jasc(text)
    if first.lower() == _PAINT_NET_HEADER:
        return read_paint_net(text)
    reader = _READERS.get(suffix.lower())
    if reader is None:
        raise ValueError(f"unknown palette type {suffix!r}")
    return reader(text)


def colors_from_pixels(width: int, height: int, rgba: bytes) -> list[PaletteColor]:
    """Distinct colours of an RGBA image in reading order (a Lospec palette PNG at any scale); fully transparent
    pixels are skipped. Raises ValueError when there are more than MAX_IMAGE_COLORS."""
    if len(rgba) < width * height * 4:
        raise ValueError("not enough pixel data")
    found: dict[tuple[int, int, int, int], None] = {}
    for offset in range(0, width * height * 4, 4):
        r, g, b, a = rgba[offset : offset + 4]
        if a == 0:
            continue
        found.setdefault((r, g, b, a))
        if len(found) > MAX_IMAGE_COLORS:
            raise ValueError("too many colours for a palette")
    return [("", rgb_to_hex((r, g, b)), round(a / 255, 3)) for r, g, b, a in found]


def write_palette(suffix: str, name: str, colors: list[PaletteColor]) -> str:
    """A palette file of type `suffix` (one of WRITE_SUFFIXES). Only Paint.NET keeps opacity; only GIMP names."""
    suffix = suffix.lower()
    if suffix == ".gpl":
        return write_gpl(name, [(color_name, color) for color_name, color, _opacity in colors])
    if suffix == ".hex":
        return "".join(f"{color[1:]}\n" for _name, color, _opacity in colors)
    if suffix == ".pal":
        rows = [" ".join(str(channel) for channel in hex_to_rgb(color)) for _name, color, _opacity in colors]
        return "\r\n".join([_JASC_HEADER, "0100", str(len(rows)), *rows]) + "\r\n"
    if suffix == ".txt":
        header = [";paint.net Palette File", f";Palette Name: {' '.join(name.split())}", f";Colors: {len(colors)}"]
        rows = [f"{round(opacity * 255):02X}{color[1:].upper()}" for _name, color, opacity in colors]
        return "\n".join([*header, *rows]) + "\n"
    raise ValueError(f"unknown palette type {suffix!r}")
