"""SVG read/write for the document model.

Writing emits plain SVG with Inkscape-style layer groups. Reading accepts general SVG: rect/circle/ellipse/
line/polyline/polygon/path/text, nested groups, transforms and inherited presentation styles. Shapes under a
non-translation transform are flattened to paths. Unsupported features (gradients, clip paths, <use>, images,
CSS stylesheets) are skipped or approximated. svgelements is only used for parsing path data, colors, lengths
and transforms — its own document parser drops `display:none` layers and `<text>`.
"""

import math
import re
import xml.etree.ElementTree as ET

import svgelements as se

from veccy.controllers.geometry import (
    ellipse_segments,
    quad_to_cubic,
    rect_segments,
    transform_segments,
)
from veccy.models.app_state import Document, Layer
from veccy.models.shapes import (
    Close,
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
ET.register_namespace("inkscape", INKSCAPE_NS)

_GROUPMODE = f"{{{INKSCAPE_NS}}}groupmode"
_LABEL = f"{{{INKSCAPE_NS}}}label"
_STYLE_KEYS = ("fill", "stroke", "stroke-width", "display", "font-size")
_DEFAULT_STYLE = {"fill": "black", "stroke": "none", "stroke-width": "1", "font-size": "16"}
_UNSUPPORTED_PAINT = "#808080"
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

Matrix = tuple[float, float, float, float, float, float]
_IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _q(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"


def _num(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


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
    w, h = _num(doc.width), _num(doc.height)
    root = ET.Element(_q("svg"), {"width": w, "height": h, "viewBox": f"0 0 {w} {h}"})
    for i, layer in enumerate(doc.layers, 1):
        attrs = {"id": f"layer{i}", _GROUPMODE: "layer", _LABEL: layer.name}
        if not layer.visible:
            attrs["style"] = "display:none"
        group = ET.SubElement(root, _q("g"), attrs)
        for shape in layer.shapes:
            group.append(_shape_element(shape))
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def _shape_element(shape: Shape) -> ET.Element:
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
        case TextShape(x=x, y=y, text=text, font_size=size):
            attrs = {"x": _num(x), "y": _num(y), "font-size": _num(size), "font-family": "sans-serif"}
            element = ET.Element(_q("text"), attrs | style)
            element.text = text
            return element


def read_svg(text: str) -> Document:
    """Raises ET.ParseError on malformed XML, ValueError on XML that isn't a usable SVG document."""
    root = ET.fromstring(text)
    if root.tag != _q("svg"):
        raise ValueError("not an SVG document")
    width, height, origin = _document_frame(root)
    reader = _Reader()
    base_style = _merge_style(_DEFAULT_STYLE, root)
    base_matrix: Matrix = (1.0, 0.0, 0.0, 1.0, -origin[0], -origin[1])

    layers: list[Layer] = []
    loose: Layer | None = None
    for child in root:
        if child.tag == _q("g") and child.get(_GROUPMODE) == "layer":
            style = _merge_style(base_style, child)
            # Hidden layers still hold content, so read their children despite display:none.
            visible = style.pop("display", None) != "none"
            name = child.get(_LABEL) or child.get("id") or f"Layer {len(layers) + 1}"
            layer = Layer(name, visible)
            matrix = _compose(base_matrix, _parse_transform(child.get("transform")))
            for grandchild in child:
                reader.visit(grandchild, style, matrix, layer.shapes)
            layers.append(layer)
        else:
            if loose is None or layers[-1] is not loose:
                loose = Layer(f"Layer {len(layers) + 1}")
                layers.append(loose)
            reader.visit(child, base_style, base_matrix, loose.shapes)

    return Document(width, height, layers or [Layer("Layer 1")], next_id=reader.next_id)


def _document_frame(root: ET.Element) -> tuple[float, float, tuple[float, float]]:
    """(width, height, viewBox origin) in user units — the model works in viewBox coordinates."""
    view_box = [float(v) for v in _NUMBER.findall(root.get("viewBox", ""))]
    if len(view_box) == 4 and view_box[2] > 0 and view_box[3] > 0:
        return view_box[2], view_box[3], (view_box[0], view_box[1])
    return _length(root.get("width"), 600.0), _length(root.get("height"), 400.0), (0.0, 0.0)


class _Reader:
    def __init__(self) -> None:
        self.next_id = 1

    def _new_id(self) -> int:
        self.next_id += 1
        return self.next_id - 1

    def visit(self, element: ET.Element, inherited: dict[str, str], matrix: Matrix, out: list[Shape]) -> None:
        style = _merge_style(inherited, element)
        if style.get("display") == "none":
            return
        matrix = _compose(matrix, _parse_transform(element.get("transform")))
        tag = element.tag.removeprefix(f"{{{SVG_NS}}}")
        if tag in ("g", "a", "switch"):
            for child in element:
                self.visit(child, style, matrix, out)
            return
        shape = self._shape(tag, element, style, matrix)
        if shape is not None:
            out.append(shape)

    def _shape(self, tag: str, el: ET.Element, style: dict[str, str], m: Matrix) -> Shape | None:
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
            return self._path(rect_segments(x, y, w, h), m, paint)

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
            return self._path(ellipse_segments(cx, cy, rx, ry), m, paint)

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
            # Only the anchor point is transformed; rotated/skewed text comes in upright.
            x, y = _apply(m, _first_number(el.get("x")), _first_number(el.get("y")))
            size = _length(style.get("font-size"), 16.0) * scale
            return TextShape(self._new_id(), x, y, content, size, paint)

        return None

    def _path(self, segments: tuple[Segment, ...], m: Matrix, paint: Style) -> PathShape:
        if m != _IDENTITY:
            segments = transform_segments(segments, lambda x, y: _apply(m, x, y))
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


def _parse_transform(value: str | None) -> Matrix:
    if not value:
        return _IDENTITY
    try:
        m = se.Matrix(value)
    except (ValueError, TypeError):
        return _IDENTITY
    return (m.a, m.b, m.c, m.d, m.e, m.f)


def _compose(outer: Matrix, inner: Matrix) -> Matrix:
    """Matrix applying `inner` first, then `outer`."""
    a1, b1, c1, d1, e1, f1 = outer
    a2, b2, c2, d2, e2, f2 = inner
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def _parse_path_data(d: str) -> tuple[Segment, ...]:
    try:
        parsed = list(se.Path(d).segments())
    except (ValueError, TypeError, IndexError) as e:
        raise ValueError(f"bad path data: {d[:40]!r}") from e
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
