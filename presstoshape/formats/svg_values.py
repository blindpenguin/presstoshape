"""Parsing SVG attribute and property values: numbers, lengths, opacities, dash lists, transforms, path data.

svgelements parses lengths, transforms and path data here (and colours in svg_reader); its document reader isn't
used.
"""

import math
import re

import svgelements as se

from presstoshape.geometry.affine import IDENTITY, Affine
from presstoshape.geometry.segments import quad_to_cubic
from presstoshape.i18n import _
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo, Segment

NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_BREAKS = re.compile(r"\s*[\n\r\t]\s*")
_LENGTH_TEXT = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?[a-zA-Z]*")


def collapse_whitespace(text: str) -> str:
    """Line breaks and tabs become single spaces, as SVG renders them; ends are trimmed."""
    return _BREAKS.sub(" ", text).strip()


def corner_radii(rx_text: str | None, ry_text: str | None) -> tuple[float, float]:
    """SVG rule: a missing (or negative) radius takes the other one's value."""
    rx = parse_length(rx_text, -1.0) if rx_text is not None else -1.0
    ry = parse_length(ry_text, -1.0) if ry_text is not None else -1.0
    if rx < 0:
        rx = max(ry, 0.0)
    if ry < 0:
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


def parse_dashes(value: str | None) -> tuple[float, ...]:
    """Dash lengths; an invalid list means a solid line, as in SVG. Odd lists are repeated by `sanitized`."""
    if value is None or value.strip() in ("", "none"):
        return ()
    lengths = []
    for item in re.split(r"[\s,]+", value.strip()):
        # svgelements reads garbage as 0, which would turn a broken list into a valid one.
        length = parse_length(item, -1.0) if _LENGTH_TEXT.fullmatch(item) else -1.0
        if length < 0:
            return ()
        lengths.append(length)
    return tuple(lengths)


def font_relative_length(value: str | None, font_size: float) -> float:
    """A length that may be in em or ex (lines are often spaced as dy="1.2em"); the first of a list."""
    if not value:
        return 0.0
    first = value.replace(",", " ").split()[0] if value.strip() else ""
    for suffix, factor in (("em", 1.0), ("ex", 0.5)):
        if first.endswith(suffix):
            return parse_number(first[: -len(suffix)], 0.0) * factor * font_size
    return parse_length(first)


def parse_length(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(se.Length(value).value())
    except (ValueError, TypeError):
        return default


def first_number(value: str | None) -> float:
    match = NUMBER.search(value or "")
    return float(match.group()) if match else 0.0


def parse_transform(value: str | None) -> Affine:
    if not value:
        return IDENTITY
    try:
        m = se.Matrix(value)
    except (ValueError, TypeError):
        return IDENTITY
    return (m.a, m.b, m.c, m.d, m.e, m.f)


def parse_path_data(d: str) -> tuple[Segment, ...]:
    try:
        parsed = list(se.Path(d).segments())
    except (ValueError, TypeError, IndexError) as e:
        raise ValueError(_("bad path data: {data}").format(data=repr(d[:40]))) from e
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
    return tuple(out)
