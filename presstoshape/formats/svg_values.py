"""Parsing SVG attribute and property values: numbers, opacities, dash lists, transforms, path data.

svgelements parses transforms and path data here (and colours in svg_reader), lengths are in svg_lengths; its
document reader isn't used.
"""

import math
import re

import svgelements as se

from presstoshape.formats import svg_lengths
from presstoshape.formats.svg_lengths import Viewport
from presstoshape.geometry.affine import IDENTITY, Affine
from presstoshape.geometry.segments import quad_to_cubic
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo, Segment

NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_BREAKS = re.compile(r"[\n\r\t]")
_SPACES = re.compile(r" {2,}")


class Whitespace:
    """Builds one text object's string from chunks, each with its element's `xml:space` mode.

    Default mode: line breaks are removed, tabs become spaces, runs of spaces collapse into one, and a space at the
    start (or right after a collapsible one) is dropped. Preserve mode: line breaks and tabs become spaces, all
    spaces stay. Trailing spaces that came from default chunks are trimmed in `result`."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._empty = True
        self._tail_collapsible = False

    def add(self, text: str, preserve: bool) -> None:
        if preserve:
            chunk = _BREAKS.sub(" ", text)
        else:
            chunk = _SPACES.sub(" ", text.replace("\n", "").replace("\r", "").replace("\t", " "))
            if chunk.startswith(" ") and (self._empty or self._tail_collapsible):
                chunk = chunk[1:]
        if not chunk:
            return
        self._parts.append(chunk)
        self._empty = False
        self._tail_collapsible = not preserve and chunk.endswith(" ")

    def result(self) -> str:
        text = "".join(self._parts)
        return text[:-1] if self._tail_collapsible and text.endswith(" ") else text


def corner_radii(rx: float | None, ry: float | None) -> tuple[float, float]:
    """SVG rule: a missing (or negative) radius takes the other one's value."""
    if rx is None or rx < 0:
        rx = max(ry, 0.0) if ry is not None else 0.0
    if ry is None or ry < 0:
        ry = rx
    return rx, ry


def one_of(value: str | None, choices: tuple[str, ...], default: str) -> str:
    return value if value in choices else default


def parse_fraction(value: str | None, default: float = 1.0) -> float:
    """Opacity values: a number or a percentage, clamped to 0..1."""
    if value is None:
        return default
    value = value.strip()
    try:
        number = float(value[:-1]) / 100 if value.endswith("%") else float(value)
    except ValueError:
        return default
    return min(1.0, max(0.0, number)) if math.isfinite(number) else default


def parse_number(value: str | None, default: float) -> float:
    try:
        number = float(value) if value is not None else default
    except ValueError:
        return default
    return number if math.isfinite(number) else default


def parse_dashes(value: str | None, viewport: Viewport, font_size: float) -> tuple[float, ...]:
    """Dash lengths; an invalid list means a solid line, as in SVG. Odd lists are repeated by `sanitized`."""
    if value is None or value.strip() in ("", "none"):
        return ()
    lengths = []
    for item in re.split(r"[\s,]+", value.strip()):
        number = svg_lengths.length(item, "other", viewport, font_size, css=True)
        if number is None or number < 0:
            return ()
        lengths.append(number)
    return tuple(lengths)


def first_token(value: str | None) -> str | None:
    """The first item of a list attribute (text x/y/dy), None when missing or empty."""
    items = value.replace(",", " ").split() if value else []
    return items[0] if items else None


def parse_transform(value: str | None) -> Affine:
    if not value:
        return IDENTITY
    try:
        m = se.Matrix(value)
    except (ValueError, TypeError):
        return IDENTITY
    return (m.a, m.b, m.c, m.d, m.e, m.f)


_ARGUMENT_COUNT = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
_ARC_FLAGS = (3, 4)
_SEPARATORS = " \t\n\r\f,"


def _skip_blanks(text: str, pos: int) -> int:
    while pos < len(text) and text[pos] in " \t\n\r\f":
        pos += 1
    return pos


def valid_path_prefix(d: str) -> tuple[str, bool]:
    """The longest leading part of path data that follows the SVG grammar and ends on a complete segment, and
    whether anything was cut off. SVG renders such a path up to its first error."""
    end = 0
    pos = 0
    command = ""
    after_set = False
    while True:
        pos = _skip_blanks(d, pos)
        if pos >= len(d):
            break
        char = d[pos]
        if after_set and char == ",":
            pos = _skip_blanks(d, pos + 1)
            if pos >= len(d) or NUMBER.match(d, pos) is None:
                break
            char = d[pos]
        if char.upper() in _ARGUMENT_COUNT:
            if not command and char not in "Mm":
                break
            command = char
            pos += 1
            after_set = False
            if char in "Zz":
                end = pos
                continue
        elif command in ("", "Z", "z") or NUMBER.match(d, pos) is None:
            break
        count = _ARGUMENT_COUNT[command.upper()]
        for index in range(count):
            pos = _skip_blanks(d, pos)
            if index:
                if pos < len(d) and d[pos] == ",":
                    pos = _skip_blanks(d, pos + 1)
            if index in _ARC_FLAGS and command in "Aa":
                if pos >= len(d) or d[pos] not in "01":
                    return d[:end], True
                pos += 1
                continue
            match = NUMBER.match(d, pos)
            if match is None:
                return d[:end], True
            pos = match.end()
        end = pos
        after_set = True
        if command in "Mm":
            command = "L" if command == "M" else "l"
    return d[:end], bool(d[end:].strip())


def parse_points(text: str) -> tuple[tuple[tuple[float, float], ...], bool]:
    """Coordinate pairs of a points list up to the first invalid token, and whether anything was cut off."""
    values: list[float] = []
    pos = 0
    cut = False
    while True:
        while pos < len(text) and text[pos] in _SEPARATORS:
            pos += 1
        if pos >= len(text):
            break
        match = NUMBER.match(text, pos)
        if match is None:
            cut = True
            break
        values.append(float(match.group()))
        pos = match.end()
    if len(values) % 2:
        values.pop()
        cut = True
    return tuple(zip(values[::2], values[1::2])), cut


def parse_path_data(d: str) -> tuple[tuple[Segment, ...], bool]:
    """Segments of the valid part of the path data, and whether the data had errors."""
    prefix, cut = valid_path_prefix(d)
    if not prefix:
        return (), cut
    try:
        parsed = list(se.Path(prefix).segments())
    except (ValueError, TypeError, IndexError):
        return (), True
    out: list[Segment] = []
    for s in parsed:
        if isinstance(s, se.Move):
            out.append(MoveTo(s.end.x, s.end.y))
        elif isinstance(s, se.Close):
            out.append(Close())
        elif isinstance(s, se.Line):
            out.append(LineTo(s.end.x, s.end.y))
        elif isinstance(s, se.CubicBezier):
            out.append(CubicTo(s.control1.x, s.control1.y, s.control2.x, s.control2.y, s.end.x, s.end.y))
        elif isinstance(s, se.QuadraticBezier):
            out.append(quad_to_cubic((s.start.x, s.start.y), (s.control.x, s.control.y), (s.end.x, s.end.y)))
        elif isinstance(s, se.Arc):
            for c in s.as_cubic_curves():
                out.append(CubicTo(c.control1.x, c.control1.y, c.control2.x, c.control2.y, c.end.x, c.end.y))
    return tuple(out), cut
