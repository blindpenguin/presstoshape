"""SVG read/write for the document model.

Writing emits plain SVG with Inkscape-style layer groups and presentation attributes; reading lives in
formats/svg_reader.py and is re-exported here, so callers import both directions from this module.
"""

import xml.etree.ElementTree as ET
from collections.abc import Sequence

from presstoshape.formats.svg_namedview import namedview_element
from presstoshape.formats.svg_names import COMPOSITE, GROUPMODE, INSENSITIVE, LABEL, MODE, XML_SPACE, q
from presstoshape.formats.svg_page import number_text as _num
from presstoshape.formats.svg_page import page_attributes
from presstoshape.formats.svg_paint import PaintDefs
from presstoshape.formats.svg_reader import read_shapes_svg, read_svg, read_svg_with_notes
from presstoshape.geometry.affine import Affine, as_rotation, is_identity
from presstoshape.geometry.boxes import Rect
from presstoshape.geometry.transforms import outline
from presstoshape.models.app_state import Document
from presstoshape.models.shapes import (
    Close,
    CompositeShape,
    CubicTo,
    EllipseShape,
    GroupShape,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Segment,
    Shape,
    Style,
    TextShape,
)

__all__ = [
    "path_d",
    "read_shapes_svg",
    "read_svg",
    "read_svg_with_notes",
    "transform_attr",
    "write_shapes_svg",
    "write_svg",
]


def transform_attr(m: Affine) -> str | None:
    """SVG `transform` value: None for identity, `rotate(a cx cy)` for a pure rotation, else `matrix(...)`."""
    if is_identity(m):
        return None
    rotation = as_rotation(m)
    if rotation is not None:
        return f"rotate({' '.join(_num(v) for v in rotation)})"
    # Matrix entries need more digits than coordinates: 0.001 off in `a` is visible on large shapes.
    return f"matrix({' '.join(_num(v, 6) for v in m)})"


def path_d(segments: tuple[Segment, ...]) -> str:
    parts = []
    for s in segments:
        match s:
            case MoveTo(x, y):
                parts.append(f"M {_num(x)} {_num(y)}")
            case LineTo(x, y):
                parts.append(f"L {_num(x)} {_num(y)}")
            case CubicTo(c1x, c1y, c2x, c2y, x, y):
                parts.append(f"C {' '.join(_num(v) for v in (c1x, c1y, c2x, c2y, x, y))}")
            case Close():
                parts.append("Z")
    return " ".join(parts)


def write_svg(doc: Document) -> str:
    root = ET.Element(q("svg"), page_attributes(doc))
    if doc.guides or doc.grid is not None:
        root.append(namedview_element(doc))
    defs = PaintDefs()
    defs_slot = len(root)
    for i, layer in enumerate(doc.layers, 1):
        attrs = {"id": f"layer{i}", GROUPMODE: "layer", LABEL: layer.name}
        if not layer.visible:
            attrs["style"] = "display:none"
        if layer.locked:
            attrs[INSENSITIVE] = "true"
        group = ET.SubElement(root, q("g"), attrs)
        for shape in layer.shapes:
            group.append(_shape_element(shape, defs))
    _insert_defs(root, defs, defs_slot)
    return _serialize(root)


def _insert_defs(root: ET.Element, defs: PaintDefs, index: int) -> None:
    element = defs.element()
    if element is not None:
        root.insert(index, element)


def write_shapes_svg(shapes: Sequence[Shape], bounds: Rect) -> str:
    """Standalone SVG of `shapes` (clipboard): no layers, the viewBox is `bounds` in doc coordinates, so other
    apps see a tight drawing and reading it back with read_shapes_svg keeps the shapes where they were."""
    x, y, w, h = (_num(value) for value in bounds)
    root = ET.Element(q("svg"), {"width": w, "height": h, "viewBox": f"{x} {y} {w} {h}"})
    defs = PaintDefs()
    for shape in shapes:
        root.append(_shape_element(shape, defs))
    _insert_defs(root, defs, 0)
    return _serialize(root)


def _serialize(root: ET.Element) -> str:
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def _shape_element(shape: Shape, defs: PaintDefs) -> ET.Element:
    element = _untransformed_element(shape, defs)
    transform = transform_attr(shape.transform)
    if transform is not None:
        element.set("transform", transform)
    if shape.hidden:
        element.set("style", "display:none")
    if shape.locked:
        element.set(INSENSITIVE, "true")
    return element


_WRITER_DEFAULTS = Style()


def _style_attributes(style: Style, defs: PaintDefs) -> dict[str, str]:
    """Presentation attributes; everything past fill, stroke and width only when it isn't SVG's default."""
    attrs = {
        "fill": defs.attribute(style.fill),
        "stroke": defs.attribute(style.stroke),
        "stroke-width": _num(style.stroke_width),
    }
    for key, attribute in (
        ("opacity", "opacity"),
        ("fill_opacity", "fill-opacity"),
        ("stroke_opacity", "stroke-opacity"),
        ("miter_limit", "stroke-miterlimit"),
        ("dash_offset", "stroke-dashoffset"),
    ):
        if getattr(style, key) != getattr(_WRITER_DEFAULTS, key):
            attrs[attribute] = _num(getattr(style, key))
    for key, attribute in (("fill_rule", "fill-rule"), ("cap", "stroke-linecap"), ("join", "stroke-linejoin")):
        if getattr(style, key) != getattr(_WRITER_DEFAULTS, key):
            attrs[attribute] = getattr(style, key)
    if style.dashes:
        attrs["stroke-dasharray"] = ",".join(_num(value) for value in style.dashes)
    return attrs


def _untransformed_element(shape: Shape, defs: PaintDefs) -> ET.Element:
    if isinstance(shape, GroupShape):
        element = ET.Element(q("g"), {"opacity": _num(shape.opacity)} if shape.opacity != 1 else {})
        for child in shape.children:
            element.append(_shape_element(child, defs))
        return element
    style = _style_attributes(shape.style, defs)
    match shape:
        case RectShape(x=x, y=y, width=w, height=h, rx=rx, ry=ry):
            attrs = {"x": _num(x), "y": _num(y), "width": _num(w), "height": _num(h)}
            if rx or ry:
                attrs |= {"rx": _num(rx), "ry": _num(ry)}
            return ET.Element(q("rect"), attrs | style)
        case EllipseShape(cx=cx, cy=cy, rx=rx, ry=ry):
            attrs = {"cx": _num(cx), "cy": _num(cy), "rx": _num(rx), "ry": _num(ry)}
            return ET.Element(q("ellipse"), attrs | style)
        case PathShape(segments=segments):
            return ET.Element(q("path"), {"d": path_d(segments)} | style)
        case CompositeShape(parts=parts, modes=modes):
            element = ET.Element(q("path"), {"d": path_d(outline(shape) or ())} | style)
            definition = ET.SubElement(ET.SubElement(element, q("metadata")), COMPOSITE)
            for part, mode in zip(parts, modes):
                child = _shape_element(part, defs)
                child.set(MODE, mode)
                definition.append(child)
            return element
        case TextShape(x=x, y=y, text=text, font_size=size):
            attrs = {"x": _num(x), "y": _num(y), "font-size": _num(size), "font-family": "sans-serif"}
            if shape.anchor != "start":
                attrs["text-anchor"] = shape.anchor
            if text != text.strip(" ") or "  " in text:
                attrs[XML_SPACE] = "preserve"
            element = ET.Element(q("text"), attrs | style)
            element.text = text
            return element
