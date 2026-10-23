"""Paints for the SVG writer: colours as they are, gradients once in `<defs>` and referenced by `url(#id)`."""

import xml.etree.ElementTree as ET

from presstoshape.formats.svg_names import q
from presstoshape.formats.svg_page import number_text
from presstoshape.geometry.boxes import Rect
from presstoshape.models.shapes import Gradient, LinearGradient, Paint, RadialGradient


def _num(value: float) -> str:
    return number_text(value, 6)


class PaintDefs:
    """Collects the gradients of one written document; equal gradients share one element."""

    def __init__(self, page: Rect = (0.0, 0.0, 0.0, 0.0)) -> None:
        self._ids: dict[Gradient, str] = {}
        self._definitions: list[ET.Element] = []
        self._counts: dict[str, int] = {}
        self._page = page

    def new_id(self, prefix: str) -> str:
        """The next unused id for a definition: `prefix1`, `prefix2`, … in order of first use."""
        self._counts[prefix] = self._counts.get(prefix, 0) + 1
        return f"{prefix}{self._counts[prefix]}"

    def add_definition(self, element: ET.Element) -> None:
        self._definitions.append(element)

    def fallback_region(self, scale: float) -> Rect:
        """The page grown to `scale` times its size around its centre (a mask region when nothing better is known)."""
        x, y, width, height = self._page
        return x - width * (scale - 1) / 2, y - height * (scale - 1) / 2, width * scale, height * scale

    def attribute(self, paint: Paint) -> str:
        if paint is None:
            return "none"
        if isinstance(paint, str):
            return paint
        if paint not in self._ids:
            self._ids[paint] = f"grad{len(self._ids) + 1}"
        return f"url(#{self._ids[paint]})"

    def element(self) -> ET.Element | None:
        if not self._ids and not self._definitions:
            return None
        defs = ET.Element(q("defs"))
        for gradient, gradient_id in self._ids.items():
            defs.append(_gradient_element(gradient, gradient_id))
        defs.extend(self._definitions)
        return defs


def _gradient_element(gradient: Gradient, gradient_id: str) -> ET.Element:
    match gradient:
        case LinearGradient(x1=x1, y1=y1, x2=x2, y2=y2):
            tag, attrs = "linearGradient", {"x1": _num(x1), "y1": _num(y1), "x2": _num(x2), "y2": _num(y2)}
        case RadialGradient(cx=cx, cy=cy, r=r, fx=fx, fy=fy):
            tag = "radialGradient"
            attrs = {"cx": _num(cx), "cy": _num(cy), "r": _num(r), "fx": _num(fx), "fy": _num(fy)}
    attrs = {"id": gradient_id} | attrs
    if gradient.units != "objectBoundingBox":
        attrs["gradientUnits"] = gradient.units
    if gradient.spread != "pad":
        attrs["spreadMethod"] = gradient.spread
    if gradient.transform != (1.0, 0.0, 0.0, 1.0, 0.0, 0.0):
        attrs["gradientTransform"] = f"matrix({' '.join(_num(value) for value in gradient.transform)})"
    element = ET.Element(q(tag), attrs)
    for stop in gradient.stops:
        stop_attrs = {"offset": _num(stop.offset), "stop-color": stop.color}
        if stop.opacity != 1.0:
            stop_attrs["stop-opacity"] = _num(stop.opacity)
        ET.SubElement(element, q("stop"), stop_attrs)
    return element
