"""GIMP palettes (`.gpl`), the plain palette format GIMP, Inkscape and Krita share: a `GIMP Palette` header,
optional `Name:` / `Columns:` lines, `#` comments, then one `R G B name` line per colour. They have no opacity."""

from presstoshape.geometry.colours import hex_to_rgb, rgb_to_hex

HEADER = "GIMP Palette"


def read_gpl(text: str) -> list[tuple[str, str]]:
    """(name, `#rrggbb`) per colour line; lines that aren't colours are skipped. Raises ValueError for text that
    isn't a GIMP palette."""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != HEADER:
        raise ValueError("not a GIMP palette")
    colors = []
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" in stripped.split(None, 1)[0]:
            continue
        parts = stripped.split(None, 3)
        try:
            rgb = tuple(int(part) for part in parts[:3])
        except ValueError:
            continue
        if len(rgb) != 3 or not all(0 <= channel <= 255 for channel in rgb):
            continue
        name = parts[3].strip() if len(parts) > 3 else ""
        colors.append((name, rgb_to_hex(rgb)))
    return colors


def write_gpl(name: str, colors: list[tuple[str, str]]) -> str:
    """A palette named `name` holding (name, `#rrggbb`) colours."""
    lines = [HEADER, f"Name: {' '.join(name.split())}", "Columns: 0", "#"]
    for color_name, color in colors:
        r, g, b = hex_to_rgb(color)
        lines.append(f"{r:3d} {g:3d} {b:3d}\t{' '.join(color_name.split())}".rstrip())
    return "\n".join(lines) + "\n"
