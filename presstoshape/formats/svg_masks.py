"""Pure helpers for reading `clip-path` and `mask`: the reference value, the box that bounding-box units refer
to, and the mask rectangle. The reader (`svg_reader`) does the walking."""

import re
from dataclasses import dataclass
from typing import Literal

from presstoshape.geometry.affine import Affine, apply, compose, invert
from presstoshape.geometry.segments import segments_bounds, transform_segments
from presstoshape.geometry.transforms import outline
from presstoshape.models.shapes import GroupShape, Shape, TextShape

MAX_REFERENCE_DEPTH = 16
MAX_CLIP_CHILDREN = 4096

Box = tuple[float, float, float, float]
_URL = re.compile(r"url\(\s*(['\"]?)#([^'\")\s]+)\1\s*\)")
# A rough width per character for text, where no font is at hand to measure with.
_TEXT_WIDTH_PER_SIZE = 0.55
_TEXT_ASCENT = 0.8


@dataclass(frozen=True)
class Reference:
    """`type` is "none" (absent or `none`), "url" (a reference to `target`), or "unsupported" (a basic shape
    such as `circle()` or anything else that is not a reference)."""

    type: Literal["none", "url", "unsupported"]
    target: str | None = None


def parse_reference(value: str | None) -> Reference:
    if value is None or value.strip() in ("", "none"):
        return Reference("none")
    match = _URL.match(value.strip())
    if match is not None:
        return Reference("url", match.group(2))
    return Reference("unsupported")


def bbox_matrix(box: Box) -> Affine:
    """Maps the unit square onto `box`, for units of `objectBoundingBox`."""
    x, y, width, height = box
    return (width, 0.0, 0.0, height, x, y)


def unit_value(text: str | None, default: float) -> float:
    """A bounding-box fraction: a number, or a percentage as its fraction."""
    if text is None:
        return default
    text = text.strip()
    try:
        value = float(text[:-1]) / 100 if text.endswith("%") else float(text)
    except ValueError:
        return default
    return value if value == value and abs(value) != float("inf") else default


def shapes_box(shapes: list[Shape], to_user: Affine) -> Box | None:
    """Bounding box (x, y, width, height) of `shapes` in the user space `to_user` leads back to, without strokes
    (the bounding box of SVG). None when nothing has any extent to measure. Text is estimated."""
    try:
        back = invert(to_user)
    except ValueError:
        return None
    boxes = [box for shape in shapes if (box := _box(shape, back)) is not None]
    if not boxes:
        return None
    left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
    right, bottom = max(b[0] + b[2] for b in boxes), max(b[1] + b[3] for b in boxes)
    return left, top, right - left, bottom - top


def _box(shape: Shape, back: Affine) -> Box | None:
    if shape.hidden:
        return None
    if isinstance(shape, GroupShape):
        return shapes_box(list(shape.children), invert(back))
    if isinstance(shape, TextShape):
        width = len(shape.text) * shape.font_size * _TEXT_WIDTH_PER_SIZE
        left = shape.x - {"start": 0.0, "middle": width / 2, "end": width}[shape.anchor]
        corners = [
            (left, shape.y - shape.font_size * _TEXT_ASCENT),
            (left + width, shape.y + shape.font_size * (1 - _TEXT_ASCENT)),
        ]
        placed = compose(back, shape.transform)
        points = [apply(placed, *corner) for corner in corners]
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    segments = outline(shape)
    if not segments:
        return None
    return segments_bounds(transform_segments(segments, lambda x, y: apply(back, x, y)))


def covers(region: Box, box: Box | None) -> bool:
    """Whether `region` contains all of `box`; unknown boxes are not covered."""
    if box is None:
        return False
    return (
        region[0] <= box[0]
        and region[1] <= box[1]
        and region[0] + region[2] >= box[0] + box[2]
        and region[1] + region[3] >= box[1] + box[3]
    )


def region_in_group_space(region: Box, user_to_group: Affine) -> Box:
    """The box around `region` after the matrix (the mask region follows the element's transform)."""
    x, y, width, height = region
    corners = [
        apply(user_to_group, px, py) for px, py in ((x, y), (x + width, y), (x, y + height), (x + width, y + height))
    ]
    left, right = min(c[0] for c in corners), max(c[0] for c in corners)
    top, bottom = min(c[1] for c in corners), max(c[1] for c in corners)
    return left, top, right - left, bottom - top
