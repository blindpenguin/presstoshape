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
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import unquote

from presstoshape.formats import css
from presstoshape.formats.svg_conditions import is_drawable, passes, switch_choice
from presstoshape.formats.svg_gradients import Resolved, resolve_gradient
from presstoshape.formats.svg_images import ImageBudget, box_size, load_image
from presstoshape.formats.svg_lengths import Axis, Viewport, length, resolve, root_viewport
from presstoshape.formats.svg_lengths import parse as parse_length_text
from presstoshape.formats.svg_masks import (
    MAX_CLIP_CHILDREN,
    MAX_REFERENCE_DEPTH,
    Box,
    bbox_matrix,
    covers,
    parse_reference,
    region_in_group_space,
    shapes_box,
    unit_value,
)
from presstoshape.formats.svg_namedview import read_namedview
from presstoshape.formats.svg_names import (
    COMPOSITE,
    GROUPMODE,
    INSENSITIVE,
    LABEL,
    MODE,
    PART_MODES,
    SVG_PREFIX,
    XLINK_HREF,
    XML_BASE,
    XML_SPACE,
    q,
)
from presstoshape.formats.svg_nodes import Nodes
from presstoshape.formats.svg_notes import Note, NoteCollector
from presstoshape.formats.svg_page import Page, read_page
from presstoshape.formats.svg_properties import normalize
from presstoshape.formats.svg_values import (
    Whitespace,
    corner_radii,
    first_token,
    one_of,
    parse_color,
    parse_dashes,
    parse_fraction,
    parse_number,
    parse_path_data,
    parse_points,
    parse_transform,
)
from presstoshape.formats.svg_viewport import (
    DEFAULT,
    INVALID,
    Aspect,
    escapes,
    fit,
    is_finite,
    parse_aspect,
    parse_view_box,
)
from presstoshape.geometry import booleans
from presstoshape.geometry.affine import IDENTITY, Affine, apply, compose, invert, scaling, translation
from presstoshape.geometry.segments import segments_bounds, transform_segments
from presstoshape.geometry.transforms import outline, transform_shape
from presstoshape.i18n import _
from presstoshape.models.app_state import Document, Layer, layer_name
from presstoshape.models.shapes import (
    Close,
    CompositeShape,
    EllipseShape,
    Gradient,
    GroupShape,
    ImageShape,
    LineTo,
    Masking,
    MoveTo,
    Paint,
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
        "color",
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
        "color-interpolation",
        "clip-rule",
    }
)
_MARKER_KEYS = ("marker", "marker-start", "marker-mid", "marker-end")
_EFFECT_NOTES = (("filter", Note.FILTER),)
_STYLE_KEYS = _INHERITED_KEYS | {
    "display",
    "opacity",
    "overflow",
    "clip-path",
    "mask",
    "mask-type",
    "filter",
    "stop-color",
    "stop-opacity",
    *_MARKER_KEYS,
}
# Compared between a text line and its tspans to notice mixed styles.
_TEXT_LOOK_KEYS = ("fill", "stroke", "font-size", "fill-opacity")
_DEFAULT_STYLE = {"color": "black", "fill": "black", "stroke": "none", "stroke-width": "1", "font-size": "16"}
_FONT_SIZES = {
    "xx-small": 9.0,
    "x-small": 10.0,
    "small": 13.0,
    "medium": 16.0,
    "large": 18.0,
    "x-large": 24.0,
    "xx-large": 32.0,
}
_FONT_STEP = 1.2
_UNSUPPORTED_PAINT = "#808080"
_GRADIENT_TAGS = ("linearGradient", "radialGradient")
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
# Nested groups and <use> chains deeper than this are cut off (real drawings stay far below it).
_MAX_DEPTH = 32


def read_svg(text: str) -> Document:
    """Raises ET.ParseError on malformed XML, ValueError on XML that isn't a usable SVG document."""
    return read_svg_with_notes(text)[0]


def read_svg_with_notes(
    text: str, languages: tuple[str, ...] = ("en",), base_folder: Path | None = None
) -> tuple[Document, list[str]]:
    """Like read_svg, plus notes about what couldn't be imported or was approximated (gradients, clip paths,
    Composites edited elsewhere, …), one per kind with a count. `languages` are the user's, most preferred
    first, for `systemLanguage` and `<switch>`. `base_folder` is where relative image files are looked for;
    without it only data URIs and absolute paths can be read."""
    root = _parse_root(text)
    page = read_page(root)
    base_matrix = page.view or compose(scaling(page.scale, page.scale), translation(-page.origin[0], -page.origin[1]))
    document, notes = _read_layers(root, base_matrix, languages, base_folder, page)
    document.width, document.height = page.width, page.height
    document.unit, document.dpi = page.unit, page.dpi
    return document, notes


def read_shapes_svg(
    text: str, languages: tuple[str, ...] = ("en",), base_folder: Path | None = None
) -> tuple[list[Shape], list[str]]:
    """Shapes of every layer in document order (clipboard paste), in the SVG's own user space: unlike read_svg
    the viewBox origin is not moved to 0,0. Coarse physical user units (mm-based files) are scaled like on open.
    Raises like read_svg."""
    root = _parse_root(text)
    page = read_page(root)
    document, notes = _read_layers(root, scaling(page.scale, page.scale), languages, base_folder)
    return [shape for layer in document.layers for shape in layer.shapes], notes


def _parse_root(text: str) -> ET.Element:
    root = ET.fromstring(text)
    if root.tag != q("svg"):
        raise ValueError(_("not an SVG document"))
    return root


def _read_layers(
    root: ET.Element,
    base_matrix: Affine,
    languages: tuple[str, ...],
    base_folder: Path | None,
    page: Page | None = None,
) -> tuple[Document, list[str]]:
    """Layers and shapes; with `page` (opening a file, not pasting) also guides and the grid."""
    reader = _Reader(root, languages, base_folder)
    base_style = reader.style(_DEFAULT_STYLE, root)
    base_opacity = parse_fraction(base_style.get("opacity"))
    reader.notes.add(Note.INVALID_VALUE, parse_aspect(root.get("preserveAspectRatio")) is INVALID)

    layers: list[Layer] = []
    loose: Layer | None = None
    for child in root:
        if child.tag == q("g") and child.get(GROUPMODE) == "layer":
            if not passes(child, languages):
                reader.notes.add(Note.CONDITIONAL)
                continue
            style = reader.style(base_style, child)
            # Hidden layers still hold content, so read their children despite display:none.
            visible = style.pop("display", None) != "none"
            name = child.get(LABEL) or child.get("id") or layer_name(len(layers) + 1)
            layer = Layer(name, visible, locked=_locked(child))
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

    guides, grid = read_namedview(root, page, reader.new_id, reader.notes) if page is not None else ((), None)
    document = Document(layers=layers or [Layer(layer_name(1))], next_id=reader.next_id, guides=guides, grid=grid)
    return document, reader.notes.messages()


def _is_css_sheet(style: ET.Element) -> bool:
    """`<style>` elements with a CSS type that apply to screens; the others are not read."""
    return (style.get("type") or "text/css").strip().lower() in ("", "text/css") and css.media_applies(
        style.get("media", "")
    )


def _locked(element: ET.Element) -> bool:
    return (element.get(INSENSITIVE) or "").strip() == "true"


def _local_name(element: ET.Element) -> str | None:
    """Tag without the SVG namespace; None for elements of other namespaces (Inkscape, Illustrator, …)."""
    tag = element.tag
    if not isinstance(tag, str) or not tag.startswith(SVG_PREFIX):
        return None
    return tag[len(SVG_PREFIX) :]


@dataclass(frozen=True)
class _View:
    """Where a viewport puts its content: viewBox to parent space, the viewport rectangle (parent space) and what
    percentages inside refer to."""

    matrix: Affine
    rect: tuple[float, float, float, float]
    inner: Viewport


class _Reader:
    def __init__(self, root: ET.Element, languages: tuple[str, ...], base_folder: Path | None = None) -> None:
        self.languages = languages
        self.base_folder = base_folder
        self.images = ImageBudget()
        # `xml:base` of the elements being read, outer to inner: where relative image files are looked for.
        self._bases: list[str] = []
        self.viewport = root_viewport(root)
        self.next_id = 1
        self._depth = 0
        self._clipping = False
        self._mask_chain: tuple[str, ...] = ()
        self.notes = NoteCollector()
        # The first element with an id wins, as browsers do.
        self.ids: dict[str, ET.Element] = {}
        for element in root.iter():
            element_id = element.get("id")
            if element_id is not None:
                self.ids.setdefault(element_id, element)
        self.nodes = Nodes(root)
        self._gradients: dict[tuple[int, Viewport], Resolved | None] = {}
        sheets = []
        left_out = 0
        for element in root.iter(q("style")):
            if _is_css_sheet(element):
                sheets.append(element.text or "")
            else:
                left_out += 1
        self.sheet = css.parse("\n".join(sheets))
        self.notes.add(Note.CSS_SKIPPED, self.sheet.skipped + left_out)

    def new_id(self) -> int:
        self.next_id += 1
        return self.next_id - 1

    def style(self, inherited: dict[str, str], element: ET.Element) -> dict[str, str]:
        """The element's properties, in CSS order: inherited values, presentation attributes, style sheet,
        inline `style`, then `!important` from the sheet and inline. `inherit` keeps the inherited value."""
        style = {key: value for key, value in inherited.items() if key in _INHERITED_KEYS}
        for key in _STYLE_KEYS:
            value = element.get(key)
            if value is not None:
                self._assign(style, inherited, key, value, css=False)
        inline = css.parse_declarations(element.get("style", ""))
        if self.sheet.rules and _local_name(element) is not None:
            sheet_normal, sheet_important = self.sheet.declarations_for(self.nodes.node(element))
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
                    self._assign(style, inherited, key, value, css=True)
        if style.get("color") == "currentColor":
            style["color"] = inherited.get("color", "black")
        self._resolve_font_size(style, inherited)
        return style

    def _assign(self, style: dict[str, str], inherited: dict[str, str], key: str, value: str, css: bool) -> None:
        """One declaration into the cascade; invalid values are ignored and counted."""
        normalized = normalize(key, value, css)
        if normalized is None:
            self.notes.add(Note.INVALID_VALUE)
        elif normalized == "inherit":
            if key in inherited:
                style[key] = inherited[key]
        else:
            style[key] = normalized

    def _resolve_font_size(self, style: dict[str, str], inherited: dict[str, str]) -> None:
        """Stores font-size as a plain number of user units, so children inherit an absolute size."""
        declared = style.get("font-size")
        if declared is None or declared == inherited.get("font-size"):
            return
        parent = _font_size(inherited)
        size = self._font_size_value(declared.strip(), parent)
        if size is None or size < 0:
            self.notes.add(Note.INVALID_VALUE)
            size = parent
        style["font-size"] = repr(size)

    def _font_size_value(self, text: str, parent: float) -> float | None:
        if text in _FONT_SIZES:
            return _FONT_SIZES[text]
        if text == "larger":
            return parent * _FONT_STEP
        if text == "smaller":
            return parent / _FONT_STEP
        parsed = parse_length_text(text, css=True)
        if parsed is None:
            return None
        if parsed[1] == "%":
            return parsed[0] / 100 * parent
        return resolve(parsed, "other", self.viewport, parent)

    def _length(
        self, text: str | None, axis: Axis, style: dict[str, str], default: float = 0.0, css: bool = False
    ) -> float:
        """A length attribute in user units; invalid values are counted and take the default."""
        value = length(text, axis, self.viewport, _font_size(style), default, css)
        if value is None:
            self.notes.add(Note.INVALID_VALUE)
            return default
        return value

    def _optional_length(self, text: str | None, axis: Axis, style: dict[str, str]) -> float | None:
        """Like `_length`, but None for a missing or invalid value (rx/ry fall back to each other)."""
        if text is None:
            return None
        value = length(text, axis, self.viewport, _font_size(style))
        if value is None:
            self.notes.add(Note.INVALID_VALUE)
        return value

    def visit(
        self,
        element: ET.Element,
        inherited: dict[str, str],
        matrix: Affine,
        out: list[Shape],
        opacity: float = 1.0,
        uses: tuple[str, ...] = (),
        use: ET.Element | None = None,
    ) -> None:
        base = element.get(XML_BASE)
        if base is None:
            self._visit(element, inherited, matrix, out, opacity, uses, use)
            return
        self._bases.append(base)
        try:
            self._visit(element, inherited, matrix, out, opacity, uses, use)
        finally:
            self._bases.pop()

    def _visit(
        self,
        element: ET.Element,
        inherited: dict[str, str],
        matrix: Affine,
        out: list[Shape],
        opacity: float = 1.0,
        uses: tuple[str, ...] = (),
        use: ET.Element | None = None,
    ) -> None:
        tag = _local_name(element)
        if tag is None or tag in _NOT_RENDERED:
            return
        if not passes(element, self.languages):
            self.notes.add(Note.CONDITIONAL)
            return
        style = self.style(inherited, element)
        hidden = style.get("display") == "none"
        # What a <use> copies is drawn only where SVG renders it; elsewhere display:none is kept as hidden.
        if hidden and uses:
            return
        before = len(out)
        self._visit_shown(tag, element, style, matrix, out, opacity, uses, use)
        if len(out) > before and not hidden:
            self._apply_masks(element, style, matrix, out, before)
        locked = _locked(element)
        if hidden or locked:
            out[before:] = [replace(shape, hidden=hidden, locked=locked) for shape in out[before:]]

    def _visit_shown(
        self,
        tag: str,
        element: ET.Element,
        style: dict[str, str],
        matrix: Affine,
        out: list[Shape],
        opacity: float,
        uses: tuple[str, ...],
        use: ET.Element | None = None,
    ) -> None:
        if self._clipping and tag not in _SHAPE_TAGS and tag not in ("text", "use"):
            return
        if tag == "svg":
            self._note_effects(style)
            matrix = compose(matrix, parse_transform(element.get("transform")))
            self._viewport_content(element, style, matrix, out, opacity, uses, use)
            return
        matrix = compose(matrix, parse_transform(element.get("transform")))
        self._note_effects(style)
        if tag in ("g", "a"):
            # Inkscape sublayers too: PressToShape has no nested layers yet.
            self._group(element, style, matrix, out, opacity, uses)
            return
        if tag == "switch":
            self._switch(element, style, matrix, out, opacity, uses)
            return
        opacity *= parse_fraction(style.get("opacity"))
        if tag == "image":
            if style.get("visibility") not in _HIDDEN:
                image = self._image(element, style, matrix, opacity)
                if image is not None:
                    out.append(image)
            return
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

    def _image(self, el: ET.Element, style: dict[str, str], m: Affine, opacity: float) -> Shape | None:
        data = load_image(el.get("href") or el.get(XLINK_HREF), self._image_folder(), self.images, self.notes)
        if data is None:
            return None
        size = box_size(
            self._image_side(el.get("width"), "x", style), self._image_side(el.get("height"), "y", style), data
        )
        if size is None:
            return None
        aspect = parse_aspect(el.get("preserveAspectRatio"))
        self.notes.add(Note.INVALID_VALUE, aspect is INVALID)
        shape = ImageShape(
            self.new_id(),
            self._length(el.get("x"), "x", style),
            self._length(el.get("y"), "y", style),
            *size,
            data,
            aspect if isinstance(aspect, Aspect) else DEFAULT,
            min(1.0, opacity),
        )
        return self._transformed(shape, m)

    def _image_folder(self) -> Path | None:
        """Where relative image files are looked for: the opened file's folder moved by each `xml:base`."""
        folder = self.base_folder
        for base in self._bases:
            path = Path(unquote(base))
            if path.is_absolute():
                folder = path
            elif folder is not None:
                folder = folder / path
        return folder

    def _image_side(self, text: str | None, axis: Axis, style: dict[str, str]) -> float | None:
        """`width` or `height` of an image: None when missing or `auto`."""
        if text is None or text.strip() == "auto":
            return None
        return self._length(text, axis, style)

    def _switch(
        self,
        element: ET.Element,
        style: dict[str, str],
        matrix: Affine,
        out: list[Shape],
        opacity: float,
        uses: tuple[str, ...],
    ) -> None:
        """Only the first child whose conditions pass is drawn; the other drawable children are counted."""
        choice = switch_choice(element, self.languages)
        self.notes.add(Note.CONDITIONAL, sum(1 for child in element if is_drawable(child) and child is not choice))
        if choice is not None:
            self.visit(choice, style, matrix, out, opacity * parse_fraction(style.get("opacity")), uses)

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

    def _group(
        self,
        element: ET.Element,
        style: dict[str, str],
        matrix: Affine,
        out: list[Shape],
        opacity: float,
        uses: tuple[str, ...],
    ) -> None:
        """The element's content as one group, with the element's opacity (and what ancestors handed down) as the
        group's own. Empty groups are dropped; very deep nesting is cut off with a note."""
        if self._depth >= _MAX_DEPTH:
            self.notes.add(Note.UNKNOWN_ELEMENT)
            return
        # Taken before the children's, so ids follow document order like PressToShape's own files.
        group_id = self.new_id()
        children: list[Shape] = []
        self._depth += 1
        try:
            for child in element:
                self.visit(child, style, matrix, children, 1.0, uses)
        finally:
            self._depth -= 1
        if children:
            group_opacity = min(1.0, opacity * parse_fraction(style.get("opacity")))
            out.append(GroupShape(group_id, tuple(children), group_opacity))

    def _apply_masks(
        self, element: ET.Element, style: dict[str, str], matrix: Affine, out: list[Shape], before: int
    ) -> None:
        """Wraps what `element` produced (out[before:]) in a masked group for its `mask` and `clip-path`: the mask
        inside, the clip around it. Both are defined in the user space of the element, so its own transform is
        part of the matrix. An element that can't be measured for bounding-box units is not shown."""
        user = compose(matrix, parse_transform(element.get("transform")))
        for key, tag in (("mask", "mask"), ("clip-path", "clipPath")):
            if key == "mask" and self._clipping:
                continue
            reference = parse_reference(style.get(key))
            if reference.type == "none":
                continue
            note = Note.MASK if key == "mask" else Note.CLIP
            target = self.ids.get(reference.target) if reference.target else None
            if reference.type != "url" or target is None or _local_name(target) != tag:
                self.notes.add(note)
                continue
            if reference.target in self._mask_chain or len(self._mask_chain) >= MAX_REFERENCE_DEPTH:
                self.notes.add(Note.CYCLIC_REFERENCE)
                continue
            content = out[before:]
            self._mask_chain = (*self._mask_chain, reference.target)
            try:
                wrapped = (
                    self._clip_group(target, user, content)
                    if tag == "clipPath"
                    else self._mask_group(target, user, content)
                )
            finally:
                self._mask_chain = self._mask_chain[:-1]
            out[before:] = [wrapped] if wrapped is not None else []
            if wrapped is None:
                return

    def _clip_group(self, clip: ET.Element, user: Affine, content: list[Shape]) -> Shape | None:
        """`content` clipped by the clipPath's shapes."""
        mask_shapes = self._clip_shapes(clip, user, content)
        return None if mask_shapes is None else self._masked(content, mask_shapes, "clip")

    def _clip_shapes(self, clip: ET.Element, user: Affine, content: list[Shape]) -> list[Shape] | None:
        """The clipPath's children as shapes in the document space of `content`; None when the clip can't be
        applied (bounding-box units on an element without extent). A clip path that has a `clip-path` itself is
        cut by that one: its shapes become one mask object."""
        style = self._element_style(clip)
        matrix = compose(user, parse_transform(clip.get("transform")))
        if clip.get("clipPathUnits") == "objectBoundingBox":
            box = shapes_box(content, user)
            if box is None or box[2] <= 0 or box[3] <= 0:
                self.notes.add(Note.INVALID_VALUE)
                return None
            matrix = compose(matrix, bbox_matrix(box))
        shapes = self._read_mask_children(clip, style, matrix, clipping=True)
        reference = parse_reference(style.get("clip-path"))
        if reference.type == "none":
            return shapes
        target = self.ids.get(reference.target) if reference.target else None
        if reference.type != "url" or target is None or _local_name(target) != "clipPath":
            self.notes.add(Note.CLIP)
            return shapes
        if reference.target in self._mask_chain or len(self._mask_chain) >= MAX_REFERENCE_DEPTH:
            self.notes.add(Note.CYCLIC_REFERENCE)
            return shapes
        self._mask_chain = (*self._mask_chain, reference.target)
        try:
            cut = self._clip_shapes(target, user, content)
        finally:
            self._mask_chain = self._mask_chain[:-1]
        if cut is None:
            return None
        return [self._masked(shapes, cut, "clip")]

    def _mask_group(self, mask: ET.Element, user: Affine, content: list[Shape]) -> Shape | None:
        style = self._element_style(mask)
        box = shapes_box(content, user)
        units = mask.get("maskUnits") or "objectBoundingBox"
        content_units = mask.get("maskContentUnits") or "userSpaceOnUse"
        if (units == "objectBoundingBox" or content_units == "objectBoundingBox") and (
            box is None or box[2] <= 0 or box[3] <= 0
        ):
            self.notes.add(Note.INVALID_VALUE)
            return None
        matrix = compose(user, bbox_matrix(box)) if content_units == "objectBoundingBox" else user
        if style.get("color-interpolation") == "linearRGB":
            self.notes.add(Note.MASK_COLOR_SPACE)
        mask_shapes = self._read_mask_children(mask, style, matrix, clipping=False)
        region = self._mask_region(mask, style, units, box, user)
        if region is not None and covers(region, shapes_box([*content, *mask_shapes], IDENTITY)):
            region = None
        mask_type = "alpha" if style.get("mask-type") == "alpha" else "luminance"
        return self._masked(content, mask_shapes, mask_type, region)

    def _mask_region(
        self, mask: ET.Element, style: dict[str, str], units: str, box: Box | None, user: Affine
    ) -> Box | None:
        """The mask's x, y, width and height as a box around the element's document-space area."""
        if units == "objectBoundingBox":
            x = unit_value(mask.get("x"), -0.1)
            y = unit_value(mask.get("y"), -0.1)
            width = unit_value(mask.get("width"), 1.2)
            height = unit_value(mask.get("height"), 1.2)
            left, top, box_width, box_height = box
            rect = (left + x * box_width, top + y * box_height, width * box_width, height * box_height)
        else:
            base_x, base_y = self.viewport.width * -0.1, self.viewport.height * -0.1
            rect = (
                self._length(mask.get("x"), "x", style, base_x),
                self._length(mask.get("y"), "y", style, base_y),
                self._length(mask.get("width"), "x", style, self.viewport.width * 1.2),
                self._length(mask.get("height"), "y", style, self.viewport.height * 1.2),
            )
        if rect[2] <= 0 or rect[3] <= 0:
            return (0.0, 0.0, 0.0, 0.0)
        return region_in_group_space(rect, user)

    def _read_mask_children(
        self, element: ET.Element, style: dict[str, str], matrix: Affine, clipping: bool
    ) -> list[Shape]:
        """The children of a clipPath or mask, read with `matrix` as the user space of the element they apply to."""
        shapes: list[Shape] = []
        was_clipping, self._clipping = self._clipping, clipping
        try:
            for child in element:
                self.visit(child, style, matrix, shapes)
                if len(shapes) > MAX_CLIP_CHILDREN:
                    self.notes.add(Note.INVALID_VALUE)
                    del shapes[MAX_CLIP_CHILDREN:]
                    break
        finally:
            self._clipping = was_clipping
        if clipping:
            shapes = [shape for shape in shapes if not shape.hidden]
        return shapes

    def _masked(
        self, content: list[Shape], mask_shapes: list[Shape], mask_type: str, region: Box | None = None
    ) -> Shape:
        masking = Masking(mask_type, tuple(shape.id for shape in mask_shapes), False, region)
        return GroupShape(self.new_id(), (*content, *mask_shapes), masking=masking)

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
        if target_id in uses or len(uses) >= _MAX_DEPTH:
            self.notes.add(Note.CYCLIC_REFERENCE)
            return
        matrix = compose(
            matrix,
            translation(self._length(element.get("x"), "x", style), self._length(element.get("y"), "y", style)),
        )
        uses = (*uses, target_id)
        if _local_name(target) == "symbol":
            if not passes(target, self.languages):
                self.notes.add(Note.CONDITIONAL)
                return
            symbol_style = self.style(style, target)
            if symbol_style.get("display") == "none":
                return
            self._viewport_content(target, symbol_style, matrix, out, opacity, uses, element)
        else:
            self.visit(target, style, matrix, out, opacity, uses, element if _local_name(target) == "svg" else None)

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
                if child_style.get("display") == "none" or _locked(child):
                    part = replace(part, hidden=child_style.get("display") == "none", locked=_locked(child))
                mode = child.get(MODE, "add")
                parts.append(part)
                modes.append(mode if mode in PART_MODES else "add")
            if not parts:
                raise ValueError("composite without parts")
            paint = plain.style if plain is not None else Style()
            composite = CompositeShape(self.new_id(), tuple(parts), tuple(modes), paint)
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
        if self._clipping:
            # Inside a clipPath only the fill area counts, and its rule is clip-rule.
            rule = style.get("clip-rule", "nonzero")
            style = {**style, "fill": "black", "stroke": "none", "fill-opacity": "1", "fill-rule": rule}
            opacity = 1.0
        scale = math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
        fill, fill_alpha = self._color(style.get("fill", "black"), style)
        stroke, stroke_alpha = self._color(style.get("stroke", "none"), style)
        if stroke is not None and not _is_similarity(m):
            self.notes.add(Note.UNEVEN_STROKE)
        font_size = _font_size(style)
        dashes = parse_dashes(style.get("stroke-dasharray"), self.viewport, font_size)
        return sanitized(
            Style(
                fill=fill,
                stroke=stroke,
                stroke_width=self._length(style.get("stroke-width"), "other", style, 1.0, css=True) * scale,
                opacity=opacity,
                fill_opacity=parse_fraction(style.get("fill-opacity")) * fill_alpha,
                stroke_opacity=parse_fraction(style.get("stroke-opacity")) * stroke_alpha,
                fill_rule="evenodd" if style.get("fill-rule") == "evenodd" else "nonzero",
                cap=one_of(style.get("stroke-linecap"), ("butt", "round", "square"), "butt"),
                join=one_of(style.get("stroke-linejoin"), ("miter", "round", "bevel"), "miter"),
                miter_limit=parse_number(style.get("stroke-miterlimit"), 4.0),
                dashes=tuple(value * scale for value in dashes),
                dash_offset=self._length(style.get("stroke-dashoffset"), "other", style, css=True) * scale,
            )
        )

    def _color(self, value: str, style: dict[str, str]) -> tuple[Paint, float]:
        """The paint (a hex colour, a gradient, None for no paint) and its own alpha. A `url()` that names no
        usable gradient takes its fallback colour, else it paints nothing; patterns are grey."""
        value = value.strip()
        if value.startswith("url("):
            reference, fallback = self._reference(value)
            if reference is not None:
                return reference
            if fallback.startswith("url("):
                return None, 1.0
            value = fallback or "none"
        if value == "currentColor":
            return self._color(style.get("color", "black"), {})
        return parse_color(value)

    def _reference(self, value: str) -> tuple[tuple[Paint, float] | None, str]:
        """(paint, alpha) of a `url(#id)` paint, None when it can't be used, and the fallback text after it."""
        target_text, _close, fallback = value[4:].partition(")")
        target_text = target_text.strip().strip("'\"")
        target = self.ids.get(target_text[1:]) if target_text.startswith("#") else None
        fallback = fallback.strip()
        tag = _local_name(target) if target is not None else None
        if tag in _GRADIENT_TAGS:
            resolved = self._gradient(target)
            if resolved is not None:
                return (resolved.paint, resolved.opacity), fallback
        elif tag == "pattern":
            self.notes.add(Note.PATTERN)
            return (None if fallback else (_UNSUPPORTED_PAINT, 1.0)), fallback
        else:
            self.notes.add(Note.MISSING_REFERENCE)
        return None, fallback

    def _gradient(self, element: ET.Element) -> Resolved | None:
        key = (id(element), self.viewport)
        if key not in self._gradients:
            resolved = resolve_gradient(element, self.ids, self._stop_style, self.viewport)
            self._gradients[key] = resolved
            if resolved is not None:
                self.notes.add(Note.INVALID_VALUE, resolved.invalid)
                if self._element_style(element).get("color-interpolation") == "linearRGB":
                    self.notes.add(Note.COLOR_INTERPOLATION)
        return self._gradients[key]

    def _element_style(self, element: ET.Element) -> dict[str, str]:
        """The cascade down to `element` from the root, as for a drawn element."""
        chain = []
        current: ET.Element | None = element
        while current is not None:
            chain.append(current)
            position = self.nodes.position(current)
            current = position[0] if position else None
        style = dict(_DEFAULT_STYLE)
        for ancestor in reversed(chain):
            style = self.style(style, ancestor)
        return style

    def _stop_style(self, stop: ET.Element) -> dict[str, str]:
        return self._element_style(stop)

    def _place_gradients(self, shape: Shape, m: Affine, box: Box | None, props: dict[str, str] | None = None) -> Shape:
        """A gradient is defined in the user space of the element that uses it. Where the shape took part of
        the element's matrix into its geometry, `baked = shape.transform⁻¹ ∘ m`, the gradient follows. A
        bounding-box gradient on geometry without width or height is invalid: its fallback colour is used, else
        nothing is painted."""
        style = shape.style
        if props is not None and box is not None and (box[2] <= 0 or box[3] <= 0):
            style = self._without_box_gradients(style, props)
            shape = replace(shape, style=style)
        if not isinstance(style.fill, Gradient) and not isinstance(style.stroke, Gradient):
            return shape
        try:
            baked = compose(invert(shape.transform), m)
        except ValueError:
            return shape
        if baked == IDENTITY:
            return shape
        return replace(
            shape,
            style=replace(style, fill=_placed(style.fill, baked, box), stroke=_placed(style.stroke, baked, box)),
        )

    def _without_box_gradients(self, style: Style, props: dict[str, str]) -> Style:
        changes: dict[str, object] = {}
        for key, opacity_key in (("fill", "fill_opacity"), ("stroke", "stroke_opacity")):
            paint = getattr(style, key)
            if isinstance(paint, Gradient) and paint.units == "objectBoundingBox":
                text = props.get(key, "")
                fallback = text.partition(")")[2].strip() if text.startswith("url(") else ""
                replacement, alpha = self._color(fallback, props) if fallback else (None, 1.0)
                changes[key] = replacement
                changes[opacity_key] = getattr(style, opacity_key) * alpha
        return sanitized(replace(style, **changes)) if changes else style

    def _shape(self, tag: str, el: ET.Element, style: dict[str, str], m: Affine, opacity: float) -> Shape | None:
        paint = self._paint(style, m, opacity)
        shape, box = self._geometry(tag, el, style, m, paint)
        if shape is None or not (isinstance(paint.fill, Gradient) or isinstance(paint.stroke, Gradient)):
            return shape
        return self._place_gradients(shape, m, box, style)

    def _geometry(
        self, tag: str, el: ET.Element, style: dict[str, str], m: Affine, paint: Style
    ) -> tuple[Shape | None, Box | None]:
        """The shape and the element's own geometry box (before `m`), which bounding-box gradients refer to."""
        translate_only = m[:4] == (1.0, 0.0, 0.0, 1.0)
        tx, ty = m[4], m[5]

        if tag == "rect":
            x, y = self._length(el.get("x"), "x", style), self._length(el.get("y"), "y", style)
            w, h = self._length(el.get("width"), "x", style), self._length(el.get("height"), "y", style)
            if w <= 0 or h <= 0:
                return None, None
            box = (x, y, w, h)
            rx, ry = corner_radii(
                self._optional_length(el.get("rx"), "x", style), self._optional_length(el.get("ry"), "y", style)
            )
            if translate_only:
                return RectShape(self.new_id(), x + tx, y + ty, w, h, paint, rx=rx, ry=ry), box
            return self._transformed(RectShape(self.new_id(), x, y, w, h, paint, rx=rx, ry=ry), m), box

        if tag in ("circle", "ellipse"):
            cx, cy = self._length(el.get("cx"), "x", style), self._length(el.get("cy"), "y", style)
            if tag == "circle":
                rx = ry = self._length(el.get("r"), "other", style)
            else:
                rx, ry = corner_radii(
                    self._optional_length(el.get("rx"), "x", style), self._optional_length(el.get("ry"), "y", style)
                )
            if rx <= 0 or ry <= 0:
                return None, None
            box = (cx - rx, cy - ry, 2 * rx, 2 * ry)
            if translate_only:
                return EllipseShape(self.new_id(), cx + tx, cy + ty, rx, ry, paint), box
            return self._transformed(EllipseShape(self.new_id(), cx, cy, rx, ry, paint), m), box

        if tag == "line":
            x1, x2 = (self._length(el.get(k), "x", style) for k in ("x1", "x2"))
            y1, y2 = (self._length(el.get(k), "y", style) for k in ("y1", "y2"))
            return self._path_with_box((MoveTo(x1, y1), LineTo(x2, y2)), m, paint)

        if tag in ("polyline", "polygon"):
            points, cut = parse_points(el.get("points", ""))
            if cut:
                self.notes.add(Note.PATH_ERROR)
            if len(points) < 2:
                return None, None
            segments: list[Segment] = [MoveTo(*points[0]), *(LineTo(*p) for p in points[1:])]
            if tag == "polygon":
                segments.append(Close())
            return self._path_with_box(tuple(segments), m, paint)

        if tag == "path":
            segments, cut = parse_path_data(el.get("d", ""))
            if cut:
                self.notes.add(Note.PATH_ERROR)
            return self._path_with_box(segments, m, paint) if segments else (None, None)

        return None, None

    def _text(self, element: ET.Element, style: dict[str, str], m: Affine, opacity: float) -> list[Shape]:
        """One text object per positioned run: the text element's own position, then each tspan with its own
        x, y or dy (how Inkscape and Illustrator write lines). Unpositioned tspans continue the current run."""
        start_x = self._length(first_token(element.get("x")), "x", style)
        runs = [_TextRun(start_x, self._length(first_token(element.get("y")), "y", style), style)]
        self._collect_runs(element, style, runs, start_x, self._preserves_space(element))
        shapes = []
        for run in runs:
            content = run.whitespace.result()
            if not content.strip() or run.style.get("visibility") in _HIDDEN:
                continue
            size = _font_size(run.style)
            anchor = one_of(run.style.get("text-anchor"), ("start", "middle", "end"), "start")
            paint = self._paint(run.style, m, opacity)
            if not _is_similarity(m):
                self.notes.add(Note.TEXT_SKEW)
            text = TextShape(self.new_id(), run.x, run.y, content, size, paint, anchor=anchor)
            # Rotation and uniform scale are kept; skew can't be represented on text and is dropped.
            shape = self._transformed(text, m)
            if shape is not None:
                shapes.append(self._place_gradients(shape, m, None))
        return shapes

    def _preserves_space(self, element: ET.Element) -> bool:
        """The `xml:space` mode in effect for an element: its own or the nearest ancestor's."""
        node = self.nodes.node(element)
        while node is not None:
            mode = node.element.get(XML_SPACE)
            if mode is not None:
                return mode == "preserve"
            node = node.parent
        return False

    def _collect_runs(
        self, node: ET.Element, style: dict[str, str], runs: list["_TextRun"], start_x: float, preserve: bool
    ) -> None:
        if node.text:
            runs[-1].add(node.text, style, self.notes, preserve)
        for child in node:
            child_style = self.style(style, child)
            if _local_name(child) in ("tspan", "textPath", "a") and child_style.get("display") != "none":
                if any(child.get(key) is not None for key in ("x", "y", "dy")):
                    x = start_x
                    if child.get("x") is not None:
                        x = self._length(first_token(child.get("x")), "x", child_style)
                    if child.get("y") is not None:
                        y = self._length(first_token(child.get("y")), "y", child_style)
                    else:
                        y = runs[-1].y + self._length(first_token(child.get("dy")), "y", child_style)
                    runs.append(_TextRun(x, y, child_style))
                mode = child.get(XML_SPACE)
                self._collect_runs(child, child_style, runs, start_x, preserve if mode is None else mode == "preserve")
            if child.tail:
                runs[-1].add(child.tail, style, self.notes, preserve)

    @staticmethod
    def _attribute(name: str, element: ET.Element, use: ET.Element | None) -> str | None:
        """A viewport attribute; the `<use>` that instantiates the viewport overrides the element's own."""
        if use is not None and use.get(name) is not None:
            return use.get(name)
        return element.get(name)

    def _viewport(
        self, element: ET.Element, use: ET.Element | None, style: dict[str, str], positioned: bool
    ) -> _View | None:
        """Where an `<svg>` or `<symbol>` puts its content, None when it isn't rendered (no size, or a viewBox
        without extent). A symbol's position comes from its `<use>`, so only `<svg>` reads `x` and `y`."""
        x = self._length(element.get("x"), "x", style) if positioned else 0.0
        y = self._length(element.get("y"), "y", style) if positioned else 0.0
        width = self._length(self._attribute("width", element, use), "x", style, self.viewport.width)
        height = self._length(self._attribute("height", element, use), "y", style, self.viewport.height)
        view_box = parse_view_box(element.get("viewBox"))
        aspect = parse_aspect(self._attribute("preserveAspectRatio", element, use))
        self.notes.add(Note.INVALID_VALUE, (view_box is INVALID) + (aspect is INVALID))
        if width <= 0 or height <= 0:
            return None
        aspect = aspect if isinstance(aspect, Aspect) else DEFAULT
        if isinstance(view_box, tuple):
            if view_box[2] <= 0 or view_box[3] <= 0:
                return None
            matrix = compose(translation(x, y), fit(view_box, width, height, aspect))
            inner = Viewport(view_box[2], view_box[3])
        else:
            matrix = translation(x, y)
            inner = Viewport(width, height)
        if not is_finite(matrix):
            self.notes.add(Note.INVALID_VALUE)
            return None
        return _View(matrix, (x, y, width, height), inner)

    def _viewport_content(
        self,
        element: ET.Element,
        style: dict[str, str],
        matrix: Affine,
        out: list[Shape],
        opacity: float,
        uses: tuple[str, ...],
        use: ET.Element | None,
    ) -> None:
        """The content of an `<svg>` or `<symbol>` as one group, mapped into its viewport; percentages inside
        refer to that viewport."""
        view = self._viewport(element, use, style, _local_name(element) == "svg")
        if view is None:
            return
        outer = self.viewport
        self.viewport = view.inner
        before = len(out)
        try:
            self._group(element, style, compose(matrix, view.matrix), out, opacity, uses)
        finally:
            self.viewport = outer
        if len(out) > before and style.get("overflow") not in ("visible", "auto"):
            self._check_overflow(out[before:], view.rect, matrix)

    def _check_overflow(self, shapes: list[Shape], rect: tuple[float, float, float, float], matrix: Affine) -> None:
        """Content is read in document space, so the viewport rectangle is taken there too (the bounding box of
        its corners when the matrix turns it). Nothing is clipped before there are clip objects; this only counts."""
        x, y, width, height = rect
        corners = [
            apply(matrix, cx, cy) for cx, cy in ((x, y), (x + width, y), (x, y + height), (x + width, y + height))
        ]
        left, right = min(cx for cx, _ in corners), max(cx for cx, _ in corners)
        top, bottom = min(cy for _, cy in corners), max(cy for _, cy in corners)
        if escapes(shapes, left, top, right - left, bottom - top):
            self.notes.add(Note.VIEWPORT_OVERFLOW)

    def _transformed(self, shape: Shape, m: Affine) -> Shape | None:
        try:
            return transform_shape(shape, m, scale_radii=True)
        except ValueError:
            return None

    def _path(self, segments: tuple[Segment, ...], m: Affine, paint: Style) -> PathShape:
        if m != IDENTITY:
            segments = transform_segments(segments, lambda x, y: apply(m, x, y))
        return PathShape(self.new_id(), segments, paint)

    def _path_with_box(self, segments: tuple[Segment, ...], m: Affine, paint: Style) -> tuple[PathShape, Box | None]:
        """The baked path and its box before `m`, which is only worked out for gradients."""
        box = (
            segments_bounds(segments)
            if isinstance(paint.fill, Gradient) or isinstance(paint.stroke, Gradient)
            else None
        )
        return self._path(segments, m, paint), box


def _placed(paint: Paint, baked: Affine, box: Box | None) -> Paint:
    """`paint` for geometry that `baked` was applied to. User-space gradients take the matrix on. A bounding-box
    gradient is unchanged while the box only moved and grew (`baked` has positive scales and no turn); otherwise
    it becomes a user-space gradient on the original box, since the baked geometry's box isn't that box."""
    if not isinstance(paint, Gradient):
        return paint
    a, b, c, d = baked[:4]
    if paint.units == "objectBoundingBox":
        if abs(b) < 1e-9 and abs(c) < 1e-9 and a > 0 and d > 0:
            return paint
        if box is None or box[2] <= 0 or box[3] <= 0:
            return paint
        x, y, width, height = box
        inner = compose((width, 0.0, 0.0, height, x, y), paint.transform)
        return replace(paint, units="userSpaceOnUse", transform=compose(baked, inner))
    return replace(paint, transform=compose(baked, paint.transform))


class _TextRun:
    """Text of one positioned line, in the style of the element that started it."""

    def __init__(self, x: float, y: float, style: dict[str, str]) -> None:
        self.x, self.y, self.style = x, y, style
        self.whitespace = Whitespace()
        self._mixed = False

    def add(self, text: str, style: dict[str, str], notes: NoteCollector, preserve: bool) -> None:
        self.whitespace.add(text, preserve)
        if not self._mixed and text.strip() and _text_look(style) != _text_look(self.style):
            self._mixed = True
            notes.add(Note.MIXED_TEXT)


def _text_look(style: dict[str, str]) -> tuple[str | None, ...]:
    return tuple(style.get(key) for key in _TEXT_LOOK_KEYS)


def _is_similarity(m: Affine) -> bool:
    """Rotation, mirroring and uniform scale: lengths (stroke width, font size) stay uniform under it."""
    a, b, c, d = m[:4]
    scale = a * a + b * b + c * c + d * d
    return abs(a * c + b * d) <= 1e-6 * scale and abs(a * a + b * b - c * c - d * d) <= 1e-6 * scale


def _font_size(style: dict[str, str]) -> float:
    try:
        return float(style.get("font-size", "16"))
    except ValueError:
        return 16.0
