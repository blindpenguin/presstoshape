"""Reading SVG into the document model: general SVG from other programs as well as PressToShape's own files.

Accepts rect/circle/ellipse/line/polyline/polygon/path/text (one text object per positioned tspan line), nested
groups, `<use>`/`<symbol>` (expanded into copies), transforms, and styles cascaded from presentation attributes,
`<style>` sheets (formats/css.py) and inline `style`. Shapes under a rotate/scale/skew transform keep their
element type (rect, ellipse, text) with the transform in canonical form; paths get it applied to their segments.
What can't be represented yet (gradients, clip paths, masks, images, filters, markers) is skipped or
approximated and counted as a note (formats/svg_notes.py). svgelements' own document parser isn't used: it drops
`display:none` layers and `<text>`.
"""

import math
import xml.etree.ElementTree as ET

import svgelements as se

from presstoshape.formats import css
from presstoshape.formats.svg_names import (
    COMPOSITE,
    GROUPMODE,
    LABEL,
    MODE,
    PART_MODES,
    SVG_PREFIX,
    XLINK_HREF,
    q,
)
from presstoshape.formats.svg_notes import Note, NoteCollector
from presstoshape.formats.svg_page import read_page
from presstoshape.formats.svg_values import (
    NUMBER,
    collapse_whitespace,
    corner_radii,
    first_number,
    font_relative_length,
    one_of,
    parse_dashes,
    parse_fraction,
    parse_length,
    parse_number,
    parse_path_data,
    parse_transform,
)
from presstoshape.geometry import booleans
from presstoshape.geometry.affine import IDENTITY, Affine, apply, compose, scaling, translation
from presstoshape.geometry.segments import transform_segments
from presstoshape.geometry.transforms import outline, transform_shape
from presstoshape.i18n import _
from presstoshape.models.app_state import Document, Layer, layer_name
from presstoshape.models.shapes import (
    Close,
    CompositeShape,
    EllipseShape,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Segment,
    Shape,
    Style,
    TextShape,
    sanitized,
)

# How far a stored result may drift from the parts' result (float rounding, other tools rewriting `d`) and
# still count as unedited: a share of the result's area, with a floor for tiny shapes.
_MISMATCH_SHARE = 1e-3
_MISMATCH_FLOOR = 0.05
# Properties children inherit, and those that belong to one element only.
_INHERITED_KEYS = frozenset(
    {
        "fill",
        "stroke",
        "stroke-width",
        "font-size",
        "fill-opacity",
        "stroke-opacity",
        "fill-rule",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "stroke-dashoffset",
        "text-anchor",
        "visibility",
    }
)
_MARKER_KEYS = ("marker", "marker-start", "marker-mid", "marker-end")
_EFFECT_NOTES = (("clip-path", Note.CLIP), ("mask", Note.MASK), ("filter", Note.FILTER))
_STYLE_KEYS = _INHERITED_KEYS | {"display", "opacity", "clip-path", "mask", "filter", *_MARKER_KEYS}
# Compared between a text line and its tspans to notice mixed styles.
_TEXT_LOOK_KEYS = ("fill", "stroke", "font-size", "fill-opacity")
_DEFAULT_STYLE = {"fill": "black", "stroke": "none", "stroke-width": "1", "font-size": "16"}
_UNSUPPORTED_PAINT = "#808080"
_HIDDEN = ("hidden", "collapse")
_SHAPE_TAGS = frozenset({"rect", "circle", "ellipse", "line", "polyline", "polygon", "path"})
# Elements that only define things for others, or carry no drawing: never drawn where they stand.
_NOT_RENDERED = frozenset(
    {
        "defs",
        "symbol",
        "clipPath",
        "mask",
        "pattern",
        "marker",
        "linearGradient",
        "radialGradient",
        "filter",
        "style",
        "script",
        "title",
        "desc",
        "metadata",
    }
)
_MAX_USE_DEPTH = 32


def read_svg(text: str) -> Document:
    """Raises ET.ParseError on malformed XML, ValueError on XML that isn't a usable SVG document."""
    return read_svg_with_notes(text)[0]


def read_svg_with_notes(text: str) -> tuple[Document, list[str]]:
    """Like read_svg, plus notes about what couldn't be imported or was approximated (gradients, clip paths,
    Composites edited elsewhere, …), one per kind with a count."""
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
    if root.tag != q("svg"):
        raise ValueError(_("not an SVG document"))
    return root


def _read_layers(root: ET.Element, base_matrix: Affine) -> tuple[Document, list[str]]:
    reader = _Reader(root)
    base_style = reader.style(_DEFAULT_STYLE, root)
    base_opacity = parse_fraction(base_style.get("opacity"))

    layers: list[Layer] = []
    loose: Layer | None = None
    for child in root:
        if child.tag == q("g") and child.get(GROUPMODE) == "layer":
            style = reader.style(base_style, child)
            # Hidden layers still hold content, so read their children despite display:none.
            visible = style.pop("display", None) != "none"
            name = child.get(LABEL) or child.get("id") or layer_name(len(layers) + 1)
            layer = Layer(name, visible)
            matrix = compose(base_matrix, parse_transform(child.get("transform")))
            reader.visit_group(child, style, matrix, layer.shapes, base_opacity)
            layers.append(layer)
        else:
            shapes: list[Shape] = []
            reader.visit(child, base_style, base_matrix, shapes, base_opacity)
            # Elements outside layers that draw nothing (defs, Inkscape's namedview) don't make a layer.
            if not shapes:
                continue
            if loose is None or layers[-1] is not loose:
                loose = Layer(layer_name(len(layers) + 1))
                layers.append(loose)
            loose.shapes.extend(shapes)

    document = Document(layers=layers or [Layer(layer_name(1))], next_id=reader.next_id)
    return document, reader.notes.messages()


def _local_name(element: ET.Element) -> str | None:
    """Tag without the SVG namespace; None for elements of other namespaces (Inkscape, Illustrator, …)."""
    tag = element.tag
    if not isinstance(tag, str) or not tag.startswith(SVG_PREFIX):
        return None
    return tag[len(SVG_PREFIX) :]


class _Reader:
    def __init__(self, root: ET.Element) -> None:
        self.next_id = 1
        self.notes = NoteCollector()
        # The first element with an id wins, as browsers do.
        self.ids: dict[str, ET.Element] = {}
        for element in root.iter():
            element_id = element.get("id")
            if element_id is not None:
                self.ids.setdefault(element_id, element)
        sheets = [element.text or "" for element in root.iter(q("style"))]
        self.sheet = css.parse("\n".join(sheets))
        self.notes.add(Note.CSS_SKIPPED, self.sheet.skipped)

    def _new_id(self) -> int:
        self.next_id += 1
        return self.next_id - 1

    def style(self, inherited: dict[str, str], element: ET.Element) -> dict[str, str]:
        """The element's properties, in CSS order: inherited values, presentation attributes, style sheet,
        inline `style`, then `!important` from the sheet and inline. `inherit` keeps the inherited value."""
        style = {key: value for key, value in inherited.items() if key in _INHERITED_KEYS}
        for key in _STYLE_KEYS:
            value = element.get(key)
            if value is not None:
                _assign(style, inherited, key, value.strip())
        inline = css.parse_declarations(element.get("style", ""))
        tag = _local_name(element)
        if self.sheet.rules and tag is not None:
            classes = frozenset(element.get("class", "").split())
            sheet_normal, sheet_important = self.sheet.declarations_for(tag, element.get("id"), classes)
        else:
            sheet_normal, sheet_important = {}, {}
        layers = (
            sheet_normal.items(),
            ((key, value) for key, value, important in inline if not important),
            sheet_important.items(),
            ((key, value) for key, value, important in inline if important),
        )
        for declarations in layers:
            for key, value in declarations:
                if key in _STYLE_KEYS:
                    _assign(style, inherited, key, value)
        return style

    def visit(
        self,
        element: ET.Element,
        inherited: dict[str, str],
        matrix: Affine,
        out: list[Shape],
        opacity: float = 1.0,
        uses: tuple[str, ...] = (),
    ) -> None:
        tag = _local_name(element)
        if tag is None or tag in _NOT_RENDERED:
            return
        style = self.style(inherited, element)
        if style.get("display") == "none":
            return
        if tag == "svg":
            self.notes.add(Note.NESTED_SVG)
            return
        if tag == "image":
            self.notes.add(Note.IMAGE)
            return
        matrix = compose(matrix, parse_transform(element.get("transform")))
        self._note_effects(style)
        if tag in ("g", "a", "switch"):
            self.visit_group(element, style, matrix, out, opacity, uses)
            return
        opacity *= parse_fraction(style.get("opacity"))
        if tag == "use":
            self._use(element, style, matrix, out, opacity, uses)
            return
        if tag == "text":
            out.extend(self._text(element, style, matrix, opacity))
            return
        if tag not in _SHAPE_TAGS:
            self.notes.add(Note.UNKNOWN_ELEMENT)
            return
        if style.get("visibility") in _HIDDEN:
            return
        shape = self._read(tag, element, style, matrix, opacity)
        if shape is not None:
            out.append(shape)

    def visit_group(
        self,
        group: ET.Element,
        style: dict[str, str],
        matrix: Affine,
        out: list[Shape],
        opacity: float = 1.0,
        uses: tuple[str, ...] = (),
    ) -> None:
        """Children of a group whose own style and transform are already applied. Group opacity can only be
        handed down to each shape; with several shapes that differs where they overlap, so it's noted."""
        group_opacity = parse_fraction(style.get("opacity"))
        before = len(out)
        for child in group:
            self.visit(child, style, matrix, out, opacity * group_opacity, uses)
        if group_opacity < 1 and len(out) - before > 1:
            self.notes.add(Note.GROUP_OPACITY)

    def _note_effects(self, style: dict[str, str]) -> None:
        for key, note in _EFFECT_NOTES:
            value = style.get(key)
            if value is not None and value != "none":
                self.notes.add(note)
        if any(style.get(key, "none") != "none" for key in _MARKER_KEYS):
            self.notes.add(Note.MARKER)

    def _use(
        self,
        element: ET.Element,
        style: dict[str, str],
        matrix: Affine,
        out: list[Shape],
        opacity: float,
        uses: tuple[str, ...],
    ) -> None:
        """A copy of the referenced element at the use's x/y, inheriting the use's style."""
        href = element.get("href") or element.get(XLINK_HREF) or ""
        target_id = href[1:] if href.startswith("#") else None
        target = self.ids.get(target_id) if target_id else None
        if target is None:
            self.notes.add(Note.MISSING_REFERENCE)
            return
        if target_id in uses or len(uses) >= _MAX_USE_DEPTH:
            self.notes.add(Note.CYCLIC_REFERENCE)
            return
        matrix = compose(matrix, translation(parse_length(element.get("x")), parse_length(element.get("y"))))
        uses = (*uses, target_id)
        if _local_name(target) == "symbol":
            symbol_style = self.style(style, target)
            if symbol_style.get("display") == "none":
                return
            matrix = compose(matrix, _symbol_matrix(target, element))
            self.visit_group(target, symbol_style, matrix, out, opacity, uses)
        else:
            self.visit(target, style, matrix, out, opacity, uses)

    def _read(self, tag: str, el: ET.Element, style: dict[str, str], m: Affine, opacity: float) -> Shape | None:
        """One element as a shape; a path carrying a Composite definition becomes that Composite."""
        if tag == "path" and el.find(f"{q('metadata')}/{COMPOSITE}") is not None:
            return self._composite(el, style, m, opacity)
        return self._shape(tag, el, style, m, opacity)

    def _composite(self, el: ET.Element, style: dict[str, str], m: Affine, opacity: float) -> Shape | None:
        """The stored parts if they still produce the path's visible result, else the plain path with a note."""
        plain = self._shape("path", el, style, m, opacity)
        try:
            parts: list[Shape] = []
            modes: list[str] = []
            for child in el.find(f"{q('metadata')}/{COMPOSITE}"):
                child_style = self.style(style, child)
                child_matrix = compose(m, parse_transform(child.get("transform")))
                child_tag = _local_name(child) or ""
                part = self._read(
                    child_tag, child, child_style, child_matrix, parse_fraction(child_style.get("opacity"))
                )
                if part is None:
                    raise ValueError("unreadable composite part")
                mode = child.get(MODE, "add")
                parts.append(part)
                modes.append(mode if mode in PART_MODES else "add")
            if not parts:
                raise ValueError("composite without parts")
            paint = plain.style if plain is not None else Style()
            composite = CompositeShape(self._new_id(), tuple(parts), tuple(modes), paint)
        except (ValueError, TypeError, IndexError):
            self.notes.add(Note.COMPOSITE_UNREADABLE)
            return plain
        result = outline(composite) or ()
        stored = plain.segments if plain is not None else ()
        allowed = max(_MISMATCH_SHARE * booleans.area(result), _MISMATCH_FLOOR)
        if booleans.mismatch_area(result, stored) > allowed:
            self.notes.add(Note.COMPOSITE_EDITED)
            return plain
        return composite

    def _paint(self, style: dict[str, str], m: Affine, opacity: float) -> Style:
        scale = math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
        fill, fill_alpha = self._color(style.get("fill", "black"))
        stroke, stroke_alpha = self._color(style.get("stroke", "none"))
        dashes = parse_dashes(style.get("stroke-dasharray"))
        return sanitized(
            Style(
                fill=fill,
                stroke=stroke,
                stroke_width=parse_length(style.get("stroke-width"), 1.0) * scale,
                opacity=opacity,
                fill_opacity=parse_fraction(style.get("fill-opacity")) * fill_alpha,
                stroke_opacity=parse_fraction(style.get("stroke-opacity")) * stroke_alpha,
                fill_rule="evenodd" if style.get("fill-rule") == "evenodd" else "nonzero",
                cap=one_of(style.get("stroke-linecap"), ("butt", "round", "square"), "butt"),
                join=one_of(style.get("stroke-linejoin"), ("miter", "round", "bevel"), "miter"),
                miter_limit=parse_number(style.get("stroke-miterlimit"), 4.0),
                dashes=tuple(value * scale for value in dashes),
                dash_offset=parse_length(style.get("stroke-dashoffset")) * scale,
            )
        )

    def _color(self, value: str) -> tuple[str | None, float]:
        """Hex colour (None for no paint) and the colour's own alpha. Gradients and patterns are grey, unless
        the reference names a fallback colour (`url(#g) red`)."""
        value = value.strip()
        if value.startswith("url("):
            self.notes.add(Note.GRADIENT)
            fallback = value.partition(")")[2].strip()
            if not fallback or fallback.startswith("url("):
                return _UNSUPPORTED_PAINT, 1.0
            value = fallback
        if value in ("none", "transparent"):
            return None, 1.0
        if value == "currentColor":
            return "#000000", 1.0
        try:
            color = se.Color(value)
        except (ValueError, TypeError):
            return "#000000", 1.0
        if color.value is None:
            return "#000000", 1.0
        return color.hexrgb, round(color.opacity, 3)

    def _shape(self, tag: str, el: ET.Element, style: dict[str, str], m: Affine, opacity: float) -> Shape | None:
        paint = self._paint(style, m, opacity)
        translate_only = m[:4] == (1.0, 0.0, 0.0, 1.0)
        tx, ty = m[4], m[5]

        if tag == "rect":
            x, y, w, h = (parse_length(el.get(k)) for k in ("x", "y", "width", "height"))
            if w <= 0 or h <= 0:
                return None
            rx, ry = corner_radii(el.get("rx"), el.get("ry"))
            if translate_only:
                return RectShape(self._new_id(), x + tx, y + ty, w, h, paint, rx=rx, ry=ry)
            return self._transformed(RectShape(self._new_id(), x, y, w, h, paint, rx=rx, ry=ry), m)

        if tag in ("circle", "ellipse"):
            cx, cy = parse_length(el.get("cx")), parse_length(el.get("cy"))
            if tag == "circle":
                rx = ry = parse_length(el.get("r"))
            else:
                rx, ry = corner_radii(el.get("rx"), el.get("ry"))
            if rx <= 0 or ry <= 0:
                return None
            if translate_only:
                return EllipseShape(self._new_id(), cx + tx, cy + ty, rx, ry, paint)
            return self._transformed(EllipseShape(self._new_id(), cx, cy, rx, ry, paint), m)

        if tag == "line":
            x1, y1, x2, y2 = (parse_length(el.get(k)) for k in ("x1", "y1", "x2", "y2"))
            return self._path((MoveTo(x1, y1), LineTo(x2, y2)), m, paint)

        if tag in ("polyline", "polygon"):
            values = [float(v) for v in NUMBER.findall(el.get("points", ""))]
            points = list(zip(values[::2], values[1::2]))
            if len(points) < 2:
                return None
            segments: list[Segment] = [MoveTo(*points[0]), *(LineTo(*p) for p in points[1:])]
            if tag == "polygon":
                segments.append(Close())
            return self._path(tuple(segments), m, paint)

        if tag == "path":
            segments = parse_path_data(el.get("d", ""))
            return self._path(segments, m, paint) if segments else None

        return None

    def _text(self, element: ET.Element, style: dict[str, str], m: Affine, opacity: float) -> list[Shape]:
        """One text object per positioned run: the text element's own position, then each tspan with its own
        x, y or dy (how Inkscape and Illustrator write lines). Unpositioned tspans continue the current run."""
        start_x = first_number(element.get("x"))
        runs = [_TextRun(start_x, first_number(element.get("y")), style)]
        self._collect_runs(element, style, runs, start_x)
        shapes = []
        for run in runs:
            content = collapse_whitespace("".join(run.parts))
            if not content or run.style.get("visibility") in _HIDDEN:
                continue
            size = parse_length(run.style.get("font-size"), 16.0)
            anchor = one_of(run.style.get("text-anchor"), ("start", "middle", "end"), "start")
            paint = self._paint(run.style, m, opacity)
            text = TextShape(self._new_id(), run.x, run.y, content, size, paint, anchor=anchor)
            # Rotation and uniform scale are kept; skew can't be represented on text and is dropped.
            shape = self._transformed(text, m)
            if shape is not None:
                shapes.append(shape)
        return shapes

    def _collect_runs(self, node: ET.Element, style: dict[str, str], runs: list["_TextRun"], start_x: float) -> None:
        if node.text:
            runs[-1].add(node.text, style, self.notes)
        for child in node:
            child_style = self.style(style, child)
            if _local_name(child) in ("tspan", "textPath", "a") and child_style.get("display") != "none":
                if any(child.get(key) is not None for key in ("x", "y", "dy")):
                    size = parse_length(child_style.get("font-size"), 16.0)
                    x = first_number(child.get("x")) if child.get("x") is not None else start_x
                    if child.get("y") is not None:
                        y = first_number(child.get("y"))
                    else:
                        y = runs[-1].y + font_relative_length(child.get("dy"), size)
                    runs.append(_TextRun(x, y, child_style))
                self._collect_runs(child, child_style, runs, start_x)
            if child.tail:
                runs[-1].add(child.tail, style, self.notes)

    def _transformed(self, shape: Shape, m: Affine) -> Shape | None:
        try:
            return transform_shape(shape, m, scale_radii=True)
        except ValueError:
            return None

    def _path(self, segments: tuple[Segment, ...], m: Affine, paint: Style) -> PathShape:
        if m != IDENTITY:
            segments = transform_segments(segments, lambda x, y: apply(m, x, y))
        return PathShape(self._new_id(), segments, paint)


class _TextRun:
    """Text of one positioned line, in the style of the element that started it."""

    def __init__(self, x: float, y: float, style: dict[str, str]) -> None:
        self.x, self.y, self.style = x, y, style
        self.parts: list[str] = []
        self._mixed = False

    def add(self, text: str, style: dict[str, str], notes: NoteCollector) -> None:
        self.parts.append(text)
        if not self._mixed and text.strip() and _text_look(style) != _text_look(self.style):
            self._mixed = True
            notes.add(Note.MIXED_TEXT)


def _text_look(style: dict[str, str]) -> tuple[str | None, ...]:
    return tuple(style.get(key) for key in _TEXT_LOOK_KEYS)


def _assign(style: dict[str, str], inherited: dict[str, str], key: str, value: str) -> None:
    if value == "inherit":
        if key in inherited:
            style[key] = inherited[key]
        return
    style[key] = value


def _symbol_matrix(symbol: ET.Element, use: ET.Element) -> Affine:
    """Maps the symbol's viewBox into the use's width × height (default: the viewBox size), centred and
    uniformly scaled unless preserveAspectRatio is "none"."""
    values = [float(v) for v in NUMBER.findall(symbol.get("viewBox", ""))]
    if len(values) != 4 or values[2] <= 0 or values[3] <= 0:
        return IDENTITY
    min_x, min_y, box_width, box_height = values
    width = parse_length(use.get("width") or symbol.get("width"), box_width)
    height = parse_length(use.get("height") or symbol.get("height"), box_height)
    if width <= 0 or height <= 0:
        return IDENTITY
    scale_x, scale_y = width / box_width, height / box_height
    if (use.get("preserveAspectRatio") or symbol.get("preserveAspectRatio", "")).strip() != "none":
        scale_x = scale_y = min(scale_x, scale_y)
    offset_x = (width - box_width * scale_x) / 2 - min_x * scale_x
    offset_y = (height - box_height * scale_y) / 2 - min_y * scale_y
    return compose(translation(offset_x, offset_y), scaling(scale_x, scale_y))
