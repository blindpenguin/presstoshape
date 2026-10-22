"""SVG lengths: a number with an optional unit, resolved to user units against the viewport and font size.

Stricter than svgelements, which reads garbage as 0 and accepts units in any case: attribute values are
case-sensitive (`10PX` is invalid), CSS values are not.
"""

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

Axis = Literal["x", "y", "other"]

_PATTERN = r"([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)(px|pt|pc|mm|cm|in|em|ex|%)?"
_LENGTH = re.compile(_PATTERN)
_CSS_LENGTH = re.compile(_PATTERN, re.IGNORECASE)
_ABSOLUTE = {"": 1.0, "px": 1.0, "pt": 4 / 3, "pc": 16.0, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96.0}
_VIEW_BOX_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_DEFAULT_SIZE = 100.0


@dataclass(frozen=True)
class Viewport:
    width: float
    height: float

    def percent_base(self, axis: Axis) -> float:
        if axis == "x":
            return self.width
        if axis == "y":
            return self.height
        return math.hypot(self.width, self.height) / math.sqrt(2)


@lru_cache(maxsize=4096)
def parse(text: str, css: bool = False) -> tuple[float, str] | None:
    """(number, unit) of a valid length, else None. The unit is lower case; "" means user units."""
    match = (_CSS_LENGTH if css else _LENGTH).fullmatch(text.strip())
    if match is None:
        return None
    value = float(match.group(1))
    if not math.isfinite(value):
        return None
    return value, (match.group(2) or "").lower()


def resolve(length: tuple[float, str], axis: Axis, viewport: Viewport, font_size: float) -> float:
    value, unit = length
    if unit == "%":
        return value / 100 * viewport.percent_base(axis)
    if unit == "em":
        return value * font_size
    if unit == "ex":
        return value * font_size / 2
    return value * _ABSOLUTE[unit]


def length(
    text: str | None, axis: Axis, viewport: Viewport, font_size: float, default: float = 0.0, css: bool = False
) -> float | None:
    """The length in user units; `default` for a missing attribute, None when present but invalid."""
    if text is None:
        return default
    parsed = parse(text, css)
    return None if parsed is None else resolve(parsed, axis, viewport, font_size)


def root_viewport(root: ET.Element) -> Viewport:
    """What percentages refer to: the viewBox size, else the root's width and height, else 100 × 100."""
    values = [float(v) for v in _VIEW_BOX_NUMBER.findall(root.get("viewBox", ""))]
    if len(values) == 4 and values[2] > 0 and values[3] > 0:
        return Viewport(values[2], values[3])
    fallback = Viewport(_DEFAULT_SIZE, _DEFAULT_SIZE)
    sizes = []
    for name in ("width", "height"):
        text = root.get(name)
        parsed = parse(text) if text is not None else None
        size = resolve(parsed, "other", fallback, 16.0) if parsed is not None and parsed[1] != "%" else 0.0
        sizes.append(size if size > 0 else _DEFAULT_SIZE)
    return Viewport(*sizes)
