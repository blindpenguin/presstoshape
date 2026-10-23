"""Clipping and opacity masks for the SVG writer: a masked group becomes a `<g>` of its content that points at a
`<clipPath>` or `<mask>` holding the mask objects."""

import xml.etree.ElementTree as ET
from collections.abc import Callable

from presstoshape.formats.svg_names import q
from presstoshape.formats.svg_page import number_text
from presstoshape.formats.svg_paint import PaintDefs
from presstoshape.geometry import booleans
from presstoshape.geometry.boxes import Rect
from presstoshape.geometry.masks import visible_outline
from presstoshape.geometry.segments import segments_bounds
from presstoshape.geometry.transforms import area_outline
from presstoshape.geometry.transforms import outline as shape_outline
from presstoshape.models.shapes import (
    Close,
    GroupShape,
    ImageShape,
    LineTo,
    Masking,
    MoveTo,
    Segment,
    Shape,
    TextShape,
    content_children,
    mask_children,
)

WriteShape = Callable[[Shape, PaintDefs], ET.Element]
PathData = Callable[[tuple[Segment, ...]], str]

# Paint and stroke attributes a clip child doesn't need: only its fill area counts.
_PAINT_ATTRIBUTES = (
    "fill",
    "stroke",
    "stroke-width",
    "opacity",
    "fill-opacity",
    "stroke-opacity",
    "stroke-miterlimit",
    "stroke-dashoffset",
    "stroke-dasharray",
    "stroke-linecap",
    "stroke-linejoin",
    "fill-rule",
)
# Inverted clips are written as a huge rectangle with the clip cut out of it.
_EVERYWHERE = ((-1e5, -1e5), (1e5, -1e5), (1e5, 1e5), (-1e5, 1e5))
_REGION_MARGIN = 0.1
_PAGE_FALLBACK_SCALE = 3


def _num(value: float) -> str:
    return number_text(value, 6)


def masked_group_element(
    group: GroupShape, defs: PaintDefs, write_shape: WriteShape, path_data: PathData
) -> ET.Element:
    masking = group.masking
    attrs: dict[str, str] = {}
    if masking.type == "clip":
        attrs["clip-path"] = f"url(#{_clip_path(group, defs, write_shape, path_data)})"
    else:
        attrs["mask"] = f"url(#{_mask(group, defs, write_shape)})"
    if group.opacity != 1:
        attrs["opacity"] = _num(group.opacity)
    element = ET.Element(q("g"), attrs)
    for child in content_children(group):
        element.append(write_shape(child, defs))
    return element


def _clip_path(group: GroupShape, defs: PaintDefs, write_shape: WriteShape, path_data: PathData) -> str:
    clip_id = defs.new_id("clip")
    clip = ET.Element(q("clipPath"), {"id": clip_id})
    if group.masking.inverted:
        _append_inverted(clip, group, path_data)
    else:
        for child in mask_children(group):
            clip.extend(_clip_elements(child, defs, write_shape, path_data))
    defs.add_definition(clip)
    return clip_id


def _append_inverted(clip: ET.Element, group: GroupShape, path_data: PathData) -> None:
    hole = visible_outline(GroupShape(0, mask_children(group), masking=None))
    everywhere = (MoveTo(*_EVERYWHERE[0]), *(LineTo(*point) for point in _EVERYWHERE[1:]), Close())
    outline = booleans.combine_parts([(everywhere, "add"), (hole, "subtract")]) if hole else everywhere
    clip.append(ET.Element(q("path"), {"d": path_data(outline)}))


def _clip_elements(shape: Shape, defs: PaintDefs, write_shape: WriteShape, path_data: PathData) -> list[ET.Element]:
    """Elements that stand for `shape` inside a `<clipPath>`: its geometry, never its paint. A group may not
    appear there, so plain groups are flattened and masked ones written as the area they show."""
    if shape.hidden:
        return []
    if isinstance(shape, GroupShape):
        if shape.masking is None:
            return [
                element for child in shape.children for element in _clip_elements(child, defs, write_shape, path_data)
            ]
        outline = visible_outline(shape)
        return [ET.Element(q("path"), {"d": path_data(outline)})] if outline else []
    if isinstance(shape, ImageShape):
        return [ET.Element(q("path"), {"d": path_data(shape_outline(shape) or ())})]
    element = write_shape(shape, defs)
    for attribute in _PAINT_ATTRIBUTES:
        element.attrib.pop(attribute, None)
    if shape.style.fill_rule == "evenodd":
        element.set("clip-rule", "evenodd")
    return [element]


def _mask(group: GroupShape, defs: PaintDefs, write_shape: WriteShape) -> str:
    masking = group.masking
    mask_id = defs.new_id("mask")
    x, y, width, height = _region(group, masking, defs)
    attrs = {
        "id": mask_id,
        "maskUnits": "userSpaceOnUse",
        "x": _num(x),
        "y": _num(y),
        "width": _num(width),
        "height": _num(height),
    }
    if masking.type == "alpha":
        attrs["mask-type"] = "alpha"
    mask = ET.Element(q("mask"), attrs)
    for child in mask_children(group):
        if not child.hidden:
            mask.append(write_shape(child, defs))
    defs.add_definition(mask)
    return mask_id


def _region(group: GroupShape, masking: Masking, defs: PaintDefs) -> Rect:
    """The mask rectangle: the stored region, else a box around everything the group shows, else (text has no
    outline here) the page, made generous."""
    if masking.region is not None:
        return masking.region
    boxes = []
    for shape in group.children:
        box = _box(shape)
        if box is None:
            return defs.fallback_region(_PAGE_FALLBACK_SCALE)
        boxes.append(box)
    if not boxes:
        return defs.fallback_region(_PAGE_FALLBACK_SCALE)
    left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
    right, bottom = max(b[2] for b in boxes), max(b[3] for b in boxes)
    margin_x, margin_y = (right - left) * _REGION_MARGIN, (bottom - top) * _REGION_MARGIN
    return left - margin_x, top - margin_y, right - left + 2 * margin_x, bottom - top + 2 * margin_y


def _box(shape: Shape) -> tuple[float, float, float, float] | None:
    """left, top, right, bottom including the stroke, None when the shape has no vector outline."""
    if isinstance(shape, TextShape):
        return None
    if isinstance(shape, GroupShape):
        boxes = [_box(child) for child in shape.children if not child.hidden]
        if any(box is None for box in boxes) or not boxes:
            return None
        return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    outline = area_outline(shape)
    bounds = segments_bounds(outline) if outline else None
    if bounds is None:
        return None
    half = 0.0 if isinstance(shape, ImageShape) else shape.style.stroke_width / 2 * 1.5 if shape.style.stroke else 0.0
    x, y, width, height = bounds
    return x - half, y - half, x + width + half, y + height + half
