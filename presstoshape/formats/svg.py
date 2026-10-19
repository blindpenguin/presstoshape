"""SVG read/write for the document model.

Writing emits plain SVG with Inkscape-style layer groups. Reading accepts general SVG: rect/circle/ellipse/
line/polyline/polygon/path/text, nested groups, transforms and inherited presentation styles. Shapes under a
rotate/scale/skew transform keep their element type (rect, ellipse, text) with the transform in canonical form;
paths get it applied to their segments. Unsupported features (gradients, clip paths, <use>, images,
CSS stylesheets) are skipped or approximated. svgelements is only used for parsing path data, colors, lengths
and transforms — its own document parser drops `display:none` layers and `<text>`.
"""

import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence

import svgelements as se

from presstoshape.geometry import booleans
from presstoshape.formats.svg_page import PRESSTOSHAPE_NS, page_attributes, read_page
from presstoshape.formats.svg_page import number_text as _num
from presstoshape.geometry.affine import (
    IDENTITY,
    Affine,
    apply,
    as_rotation,
    compose,
    is_identity,
    scaling,
    translation,
)
from presstoshape.geometry.boxes import Rect
from presstoshape.geometry.segments import quad_to_cubic, transform_segments
from presstoshape.geometry.transforms import outline, transform_shape
from presstoshape.i18n import _
from presstoshape.models.app_state import Document, Layer, layer_name
from presstoshape.models.shapes import (
    Close,
    CompositeShape,
    CubicTo,
    EllipseShape,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Segment,
    Shape,
    Style,
    TextShape,
)

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("", SVG_NS)
# Composite definitions live in PRESSTOSHAPE_NS, inside the result path's <metadata>: viewers don't render it
# and Inkscape keeps it.
ET.register_namespace("inkscape", INKSCAPE_NS)
ET.register_namespace("presstoshape", PRESSTOSHAPE_NS)
_COMPOSITE = f"{{{PRESSTOSHAPE_NS}}}composite"
_MODE = f"{{{PRESSTOSHAPE_NS}}}mode"
_PART_MODES = ("add", "subtract", "intersect", "exclude")
# How far a stored result may drift from the parts' result (float rounding, other tools rewriting `d`) and
# still count as unedited: a share of the result's area, with a floor for tiny shapes.
_MISMATCH_SHARE = 1e-3
_MISMATCH_FLOOR = 0.05

_GROUPMODE = f"{{{INKSCAPE_NS}}}groupmode"
_LABEL = f"{{{INKSCAPE_NS}}}label"
_STYLE_KEYS = ("fill", "stroke", "stroke-width", "display", "font-size")
_DEFAULT_STYLE = {"fill": "black", "stroke": "none", "stroke-width": "1", "font-size": "16"}
_UNSUPPORTED_PAINT = "#808080"
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

def _q(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"


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
    root = ET.Element(_q("svg"), page_attributes(doc))
    for i, layer in enumerate(doc.layers, 1):
        attrs = {"id": f"layer{i}", _GROUPMODE: "layer", _LABEL: layer.name}
        if not layer.visible:
            attrs["style"] = "display:none"
        group = ET.SubElement(root, _q("g"), attrs)
        for shape in layer.shapes:
            group.append(_shape_element(shape))
    return _serialize(root)


def write_shapes_svg(shapes: Sequence[Shape], bounds: Rect) -> str:
    """Standalone SVG of `shapes` (clipboard): no layers, the viewBox is `bounds` in doc coordinates, so other
    apps see a tight drawing and reading it back with read_shapes_svg keeps the shapes where they were."""
    x, y, w, h = (_num(value) for value in bounds)
    root = ET.Element(_q("svg"), {"width": w, "height": h, "viewBox": f"{x} {y} {w} {h}"})
    for shape in shapes:
        root.append(_shape_element(shape))
    return _serialize(root)


def _serialize(root: ET.Element) -> str:
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def _shape_element(shape: Shape) -> ET.Element:
    element = _untransformed_element(shape)
    transform = transform_attr(shape.transform)
    if transform is not None:
        element.set("transform", transform)
    return element


def _untransformed_element(shape: Shape) -> ET.Element:
    style = {
        "fill": shape.style.fill or "none",
        "stroke": shape.style.stroke or "none",
        "stroke-width": _num(shape.style.stroke_width),
    }
    match shape:
        case RectShape(x=x, y=y, width=w, height=h):
            attrs = {"x": _num(x), "y": _num(y), "width": _num(w), "height": _num(h)}
            return ET.Element(_q("rect"), attrs | style)
        case EllipseShape(cx=cx, cy=cy, rx=rx, ry=ry):
            attrs = {"cx": _num(cx), "cy": _num(cy), "rx": _num(rx), "ry": _num(ry)}
            return ET.Element(_q("ellipse"), attrs | style)
        case PathShape(segments=segments):
            return ET.Element(_q("path"), {"d": path_d(segments)} | style)
        case CompositeShape(parts=parts, modes=modes):
            element = ET.Element(_q("path"), {"d": path_d(outline(shape) or ())} | style)
            definition = ET.SubElement(ET.SubElement(element, _q("metadata")), _COMPOSITE)
            for part, mode in zip(parts, modes):
                child = _shape_element(part)
                child.set(_MODE, mode)
                definition.append(child)
            return element
        case TextShape(x=x, y=y, text=text, font_size=size):
            attrs = {"x": _num(x), "y": _num(y), "font-size": _num(size), "font-family": "sans-serif"}
            element = ET.Element(_q("text"), attrs | style)
            element.text = text
            return element


def read_svg(text: str) -> Document:
    """Raises ET.ParseError on malformed XML, ValueError on XML that isn't a usable SVG document."""
    return read_svg_with_notes(text)[0]


def read_svg_with_notes(text: str) -> tuple[Document, list[str]]:
    """Like read_svg, plus notes about things that couldn't be restored (e.g. Composites edited elsewhere)."""
    root = _parse_root(text)
    page = read_page(root)
    base_matrix = compose(scaling(page.scale, page.scale), translation(-page.origin[0], -page.origin[1]))
    document, notes = _read_layers(root, base_matrix)
    document.width, document.height = page.width, page.height
    document.unit, document.dpi = page.unit, page.dpi
    return document, notes


def read_shapes_svg(text: str) -> tuple[list[Shape], list[str]]:
    """Shapes of every layer in document order (clipboard paste), in the SVG's own user space: unlike read_svg
    the viewBox origin is not moved to 0,0. Coarse physical user units (mm-based files) are scaled like on open.
    Raises like read_svg."""
    root = _parse_root(text)
    page = read_page(root)
    document, notes = _read_layers(root, scaling(page.scale, page.scale))
    return [shape for layer in document.layers for shape in layer.shapes], notes


def _parse_root(text: str) -> ET.Element:
    root = ET.fromstring(text)
    if root.tag != _q("svg"):
        raise ValueError(_("not an SVG document"))
    return root


def _read_layers(root: ET.Element, base_matrix: Affine) -> tuple[Document, list[str]]:
    reader = _Reader()
    base_style = _merge_style(_DEFAULT_STYLE, root)

    layers: list[Layer] = []
    loose: Layer | None = None
    for child in root:
        if child.tag == _q("g") and child.get(_GROUPMODE) == "layer":
            style = _merge_style(base_style, child)
            # Hidden layers still hold content, so read their children despite display:none.
            visible = style.pop("display", None) != "none"
            name = child.get(_LABEL) or child.get("id") or layer_name(len(layers) + 1)
            layer = Layer(name, visible)
            matrix = compose(base_matrix, _parse_transform(child.get("transform")))
            for grandchild in child:
                reader.visit(grandchild, style, matrix, layer.shapes)
            layers.append(layer)
        else:
            if loose is None or layers[-1] is not loose:
                loose = Layer(layer_name(len(layers) + 1))
                layers.append(loose)
            reader.visit(child, base_style, base_matrix, loose.shapes)

    return Document(layers=layers or [Layer(layer_name(1))], next_id=reader.next_id), reader.notes


class _Reader:
    def __init__(self) -> None:
        self.next_id = 1
        self.notes: list[str] = []

    def _new_id(self) -> int:
        self.next_id += 1
        return self.next_id - 1

    def visit(self, element: ET.Element, inherited: dict[str, str], matrix: Affine, out: list[Shape]) -> None:
        style = _merge_style(inherited, element)
        if style.get("display") == "none":
            return
        matrix = compose(matrix, _parse_transform(element.get("transform")))
        tag = element.tag.removeprefix(f"{{{SVG_NS}}}")
        if tag in ("g", "a", "switch"):
            for child in element:
                self.visit(child, style, matrix, out)
            return
        shape = self._read(tag, element, style, matrix)
        if shape is not None:
            out.append(shape)

    def _read(self, tag: str, el: ET.Element, style: dict[str, str], m: Affine) -> Shape | None:
        """One element as a shape; a path carrying a Composite definition becomes that Composite."""
        if tag == "path" and el.find(f"{_q('metadata')}/{_COMPOSITE}") is not None:
            return self._composite(el, style, m)
        return self._shape(tag, el, style, m)

    def _composite(self, el: ET.Element, style: dict[str, str], m: Affine) -> Shape | None:
        """The stored parts if they still produce the path's visible result, else the plain path with a note."""
        plain = self._shape("path", el, style, m)
        try:
            parts: list[Shape] = []
            modes: list[str] = []
            for child in el.find(f"{_q('metadata')}/{_COMPOSITE}"):
                child_style = _merge_style(style, child)
                child_matrix = compose(m, _parse_transform(child.get("transform")))
                part = self._read(child.tag.removeprefix(f"{{{SVG_NS}}}"), child, child_style, child_matrix)
                if part is None:
                    raise ValueError("unreadable composite part")
                mode = child.get(_MODE, "add")
                parts.append(part)
                modes.append(mode if mode in _PART_MODES else "add")
            if not parts:
                raise ValueError("composite without parts")
            paint = plain.style if plain is not None else Style()
            composite = CompositeShape(self._new_id(), tuple(parts), tuple(modes), paint)
        except (ValueError, TypeError, IndexError):
            self.notes.append(_("A composite couldn't be read and was opened as a path"))
            return plain
        result = outline(composite) or ()
        stored = plain.segments if plain is not None else ()
        allowed = max(_MISMATCH_SHARE * booleans.area(result), _MISMATCH_FLOOR)
        if booleans.mismatch_area(result, stored) > allowed:
            self.notes.append(_("A composite was edited in another program and was opened as a path"))
            return plain
        return composite

    def _shape(self, tag: str, el: ET.Element, style: dict[str, str], m: Affine) -> Shape | None:
        scale = math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
        paint = Style(
            fill=_color(style.get("fill", "black")),
            stroke=_color(style.get("stroke", "none")),
            stroke_width=_length(style.get("stroke-width"), 1.0) * scale,
        )
        translate_only = m[:4] == (1.0, 0.0, 0.0, 1.0)
        tx, ty = m[4], m[5]

        if tag == "rect":
            x, y, w, h = (_length(el.get(k)) for k in ("x", "y", "width", "height"))
            if w <= 0 or h <= 0:
                return None
            if translate_only:
                return RectShape(self._new_id(), x + tx, y + ty, w, h, paint)
            return self._transformed(RectShape(self._new_id(), x, y, w, h, paint), m)

        if tag in ("circle", "ellipse"):
            cx, cy = _length(el.get("cx")), _length(el.get("cy"))
            if tag == "circle":
                rx = ry = _length(el.get("r"))
            else:
                rx, ry = _length(el.get("rx")), _length(el.get("ry"))
            if rx <= 0 or ry <= 0:
                return None
            if translate_only:
                return EllipseShape(self._new_id(), cx + tx, cy + ty, rx, ry, paint)
            return self._transformed(EllipseShape(self._new_id(), cx, cy, rx, ry, paint), m)

        if tag == "line":
            x1, y1, x2, y2 = (_length(el.get(k)) for k in ("x1", "y1", "x2", "y2"))
            return self._path((MoveTo(x1, y1), LineTo(x2, y2)), m, paint)

        if tag in ("polyline", "polygon"):
            values = [float(v) for v in _NUMBER.findall(el.get("points", ""))]
            points = list(zip(values[::2], values[1::2]))
            if len(points) < 2:
                return None
            segments: list[Segment] = [MoveTo(*points[0]), *(LineTo(*p) for p in points[1:])]
            if tag == "polygon":
                segments.append(Close())
            return self._path(tuple(segments), m, paint)

        if tag == "path":
            segments = _parse_path_data(el.get("d", ""))
            return self._path(segments, m, paint) if segments else None

        if tag == "text":
            content = "".join(el.itertext()).strip()
            if not content:
                return None
            x, y = _first_number(el.get("x")), _first_number(el.get("y"))
            size = _length(style.get("font-size"), 16.0)
            # Rotation and uniform scale are kept; skew can't be represented on text and is dropped.
            return self._transformed(TextShape(self._new_id(), x, y, content, size, paint), m)

        return None

    def _transformed(self, shape: Shape, m: Affine) -> Shape | None:
        try:
            return transform_shape(shape, m)
        except ValueError:
            return None

    def _path(self, segments: tuple[Segment, ...], m: Affine, paint: Style) -> PathShape:
        if m != IDENTITY:
            segments = transform_segments(segments, lambda x, y: apply(m, x, y))
        return PathShape(self._new_id(), segments, paint)


def _merge_style(inherited: dict[str, str], el: ET.Element) -> dict[str, str]:
    """Inherited values, then presentation attributes, then inline `style` (highest precedence)."""
    style = dict(inherited)
    for key in _STYLE_KEYS:
        value = el.get(key)
        if value is not None and value.strip() != "inherit":
            style[key] = value.strip()
    for declaration in el.get("style", "").split(";"):
        key, _, value = declaration.partition(":")
        key, value = key.strip(), value.strip()
        if key in _STYLE_KEYS and value and value != "inherit":
            style[key] = value
    return style


def _color(value: str) -> str | None:
    value = value.strip()
    if value in ("none", "transparent"):
        return None
    if value == "currentColor":
        return "#000000"
    if value.startswith("url("):
        return _UNSUPPORTED_PAINT
    try:
        color = se.Color(value)
    except (ValueError, TypeError):
        return "#000000"
    return "#000000" if color.value is None else color.hexrgb


def _length(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(se.Length(value).value())
    except (ValueError, TypeError):
        return default


def _first_number(value: str | None) -> float:
    match = _NUMBER.search(value or "")
    return float(match.group()) if match else 0.0


def _parse_transform(value: str | None) -> Affine:
    if not value:
        return IDENTITY
    try:
        m = se.Matrix(value)
    except (ValueError, TypeError):
        return IDENTITY
    return (m.a, m.b, m.c, m.d, m.e, m.f)


def _parse_path_data(d: str) -> tuple[Segment, ...]:
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
