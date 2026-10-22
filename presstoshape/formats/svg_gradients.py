"""Reading `<linearGradient>` / `<radialGradient>`: attribute defaults, `href` inheritance and the SVG error rules.

Pure: the reader passes in what needs its cascade (`stop_style`) and the viewport that user-space percentages
refer to.
"""

import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass

from presstoshape.formats import svg_lengths
from presstoshape.formats.svg_lengths import Axis, Viewport
from presstoshape.formats.svg_names import XLINK_HREF, q
from presstoshape.formats.svg_values import parse_color, parse_transform
from presstoshape.models.shapes import (
    MAX_STOPS,
    Gradient,
    GradientStop,
    LinearGradient,
    Paint,
    RadialGradient,
    Style,
    sanitized,
)

MAX_CHAIN = 16
_LINEAR_ATTRIBUTES = frozenset({"x1", "y1", "x2", "y2"})
_RADIAL_ATTRIBUTES = frozenset({"cx", "cy", "r", "fx", "fy"})
_BASE_FONT_SIZE = 16.0
_UNIT_BOX = Viewport(1.0, 1.0)

StopStyle = Callable[[ET.Element], dict[str, str]]


@dataclass(frozen=True)
class Resolved:
    """`paint` is a gradient, a flat colour (one stop, degenerate vector), or None (no stops: no paint).
    `opacity` is the flat colour's own stop opacity for the caller to fold into the paint opacity. `invalid`
    counts values that were replaced by defaults or dropped; `linear_rgb` says the gradient asked for
    `color-interpolation: linearRGB`, which is not honoured."""

    paint: Paint
    opacity: float = 1.0
    invalid: int = 0
    linear_rgb: bool = False


def gradient_chain(element: ET.Element, ids: dict[str, ET.Element]) -> list[ET.Element]:
    """The gradient and the gradients it inherits from through `href`, nearest first. Anything that is not a
    gradient, a repeated element or a chain longer than `MAX_CHAIN` ends the chain."""
    chain: list[ET.Element] = []
    seen: set[int] = set()
    current: ET.Element | None = element
    while current is not None and len(chain) < MAX_CHAIN and id(current) not in seen:
        if current.tag not in (q("linearGradient"), q("radialGradient")):
            break
        chain.append(current)
        seen.add(id(current))
        href = current.get("href") or current.get(XLINK_HREF) or ""
        current = ids.get(href[1:]) if href.startswith("#") else None
    return chain


def _attribute(chain: list[ET.Element], name: str, own_tag: str | None = None) -> str | None:
    """First value along the chain; geometry only from gradients of the same type."""
    for element in chain:
        if own_tag is not None and element.tag != own_tag:
            continue
        value = element.get(name)
        if value is not None:
            return value
    return None


def resolve_gradient(
    element: ET.Element, ids: dict[str, ET.Element], stop_style: StopStyle, viewport: Viewport
) -> Resolved | None:
    """The paint for a reference to `element`, or None when it is no usable gradient (wrong element, negative
    radius): the caller then uses the reference's fallback colour."""
    chain = gradient_chain(element, ids)
    if not chain:
        return None
    invalid = 0

    units = _attribute(chain, "gradientUnits")
    if units not in (None, "objectBoundingBox", "userSpaceOnUse"):
        invalid += 1
    units = units if units in ("objectBoundingBox", "userSpaceOnUse") else "objectBoundingBox"
    spread = _attribute(chain, "spreadMethod")
    if spread not in (None, "pad", "reflect", "repeat"):
        invalid += 1
    spread = spread if spread in ("pad", "reflect", "repeat") else "pad"
    transform = parse_transform(_attribute(chain, "gradientTransform"))
    base = _UNIT_BOX if units == "objectBoundingBox" else viewport

    def read(name: str, axis: Axis, default: str, tag: str) -> float:
        nonlocal invalid
        text = _attribute(chain, name, tag)
        value = svg_lengths.length(text if text is not None else default, axis, base, _BASE_FONT_SIZE)
        if value is None:
            invalid += 1
            value = svg_lengths.length(default, axis, base, _BASE_FONT_SIZE)
        return value if value is not None else 0.0

    stops, stop_invalid = _stops(chain, stop_style)
    invalid += stop_invalid
    linear_rgb = _attribute(chain, "color-interpolation") == "linearRGB"
    if not stops:
        return Resolved(None, 1.0, invalid, linear_rgb)

    linear = element.tag == q("linearGradient")
    gradient: Gradient
    if linear:
        tag = q("linearGradient")
        x1, y1 = read("x1", "x", "0%", tag), read("y1", "y", "0%", tag)
        x2, y2 = read("x2", "x", "100%", tag), read("y2", "y", "0%", tag)
        degenerate = x1 == x2 and y1 == y2
        gradient = LinearGradient(x1, y1, x2, y2, stops, units, spread, transform)
    else:
        tag = q("radialGradient")
        cx, cy, r = read("cx", "x", "50%", tag), read("cy", "y", "50%", tag), read("r", "other", "50%", tag)
        if r < 0:
            return None
        fx = read("fx", "x", "50%", tag) if _attribute(chain, "fx", tag) is not None else cx
        fy = read("fy", "y", "50%", tag) if _attribute(chain, "fy", tag) is not None else cy
        degenerate = r == 0
        gradient = RadialGradient(cx, cy, r, fx, fy, stops, units, spread, transform)

    # One stop, or no area to spread the stops over: the (last) stop's colour fills the shape.
    if len(stops) == 1 or degenerate:
        last = stops[-1]
        return Resolved(last.color, last.opacity, invalid, linear_rgb)
    paint = sanitized(Style(fill=gradient)).fill
    return Resolved(paint, 1.0, invalid, linear_rgb)


def _stops(chain: list[ET.Element], stop_style: StopStyle) -> tuple[tuple[GradientStop, ...], int]:
    """Stops of the first gradient in the chain that has any (offsets clamped and not decreasing)."""
    source = next((element for element in chain if element.find(q("stop")) is not None), None)
    if source is None:
        return (), 0
    stops: list[GradientStop] = []
    invalid = 0
    previous = 0.0
    for child in source:
        if child.tag != q("stop"):
            continue
        if len(stops) >= MAX_STOPS:
            invalid += 1
            break
        offset = _offset(child.get("offset"))
        if offset is None:
            invalid += 1
            offset = 0.0
        offset = min(1.0, max(previous, offset))
        previous = offset
        style = stop_style(child)
        color, alpha = _stop_color(style)
        stops.append(GradientStop(offset, color, _opacity(style.get("stop-opacity")) * alpha))
    return tuple(stops), invalid


def _offset(text: str | None) -> float | None:
    if text is None:
        return 0.0
    parsed = svg_lengths.parse(text)
    if parsed is None or parsed[1] not in ("", "%"):
        return None
    return parsed[0] / 100 if parsed[1] == "%" else parsed[0]


def _stop_color(style: dict[str, str]) -> tuple[str, float]:
    value = style.get("stop-color", "black").strip()
    if value == "currentColor":
        value = style.get("color", "black").strip()
    color, alpha = parse_color(value)
    # `transparent` and `none` leave no colour: a see-through black stop.
    return (color, alpha) if color is not None else ("#000000", 0.0)


def _opacity(text: str | None) -> float:
    if text is None:
        return 1.0
    text = text.strip()
    try:
        value = float(text[:-1]) / 100 if text.endswith("%") else float(text)
    except ValueError:
        return 1.0
    return min(1.0, max(0.0, value)) if value == value else 1.0
