"""SVG viewports: `viewBox`, `preserveAspectRatio` and the matrix that fits one into the other.

Stricter than svgelements: attribute grammar is case-sensitive and a malformed value is `INVALID`, which differs
from `None` (attribute absent), so the reader can count ignored values.
"""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from presstoshape.geometry.affine import Affine
from presstoshape.geometry.transforms import outline
from presstoshape.models.shapes import CubicTo, GroupShape, LineTo, MoveTo, Shape

ViewBox = tuple[float, float, float, float]


class _Invalid:
    def __repr__(self) -> str:
        return "INVALID"


INVALID: Final = _Invalid()

_NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_SEPARATOR = r"(?:\s*,\s*|\s+|(?=[-+]))"
_VIEW_BOX = re.compile(rf"\s*({_NUMBER}){_SEPARATOR}({_NUMBER}){_SEPARATOR}({_NUMBER}){_SEPARATOR}({_NUMBER})\s*")

_ALIGN_FRACTION = {"Min": 0.0, "Mid": 0.5, "Max": 1.0}
_ALIGNS = {f"x{x}Y{y}" for x in _ALIGN_FRACTION for y in _ALIGN_FRACTION}
_ESCAPE_TOLERANCE = 1e-6


@dataclass(frozen=True)
class Aspect:
    # "none" or one of xMinYMin … xMaxYMax.
    align: str
    slice: bool = False


DEFAULT = Aspect("xMidYMid")


def parse_view_box(text: str | None) -> ViewBox | None | _Invalid:
    """The four numbers; None when absent, INVALID when malformed or not finite. A width or height of zero or
    less is returned as written: the caller disables rendering for it."""
    if text is None:
        return None
    match = _VIEW_BOX.fullmatch(text)
    if match is None:
        return INVALID
    values = tuple(float(group) for group in match.groups())
    if not all(math.isfinite(value) for value in values):
        return INVALID
    return values  # type: ignore[return-value]


def parse_aspect(text: str | None) -> Aspect | None | _Invalid:
    """`[defer] <align> [meet|slice]`; None when absent, INVALID for anything else."""
    if text is None:
        return None
    tokens = text.split()
    if tokens and tokens[0] == "defer":
        tokens = tokens[1:]
    if not tokens or len(tokens) > 2:
        return INVALID
    align = tokens[0]
    if align != "none" and align not in _ALIGNS:
        return INVALID
    if len(tokens) == 1:
        return Aspect(align)
    if tokens[1] not in ("meet", "slice"):
        return INVALID
    return Aspect(align, tokens[1] == "slice")


def fit(view_box: ViewBox, width: float, height: float, aspect: Aspect) -> Affine:
    """Maps the viewBox into a viewport of `width` × `height` at the origin. Sizes must be positive; the caller
    checks the result for non-finite values."""
    min_x, min_y, box_width, box_height = view_box
    scale_x, scale_y = width / box_width, height / box_height
    if aspect.align == "none":
        offset_x = offset_y = 0.0
    else:
        scale_x = scale_y = max(scale_x, scale_y) if aspect.slice else min(scale_x, scale_y)
        offset_x = (width - box_width * scale_x) * _ALIGN_FRACTION[aspect.align[1:4]]
        offset_y = (height - box_height * scale_y) * _ALIGN_FRACTION[aspect.align[5:8]]
    return scale_x, 0.0, 0.0, scale_y, offset_x - min_x * scale_x, offset_y - min_y * scale_y


def is_finite(matrix: Affine) -> bool:
    return all(math.isfinite(value) for value in matrix)


def escapes(shapes: Sequence[Shape], x: float, y: float, width: float, height: float) -> bool:
    """Whether any shape reaches outside the rectangle. Bounds are the hull of the outline's points (control
    points included), a safe over-approximation; text has no outline and counts as inside."""
    tolerance = _ESCAPE_TOLERANCE * max(width, height)
    left, top, right, bottom = x - tolerance, y - tolerance, x + width + tolerance, y + height + tolerance
    for shape in shapes:
        if isinstance(shape, GroupShape):
            if escapes(shape.children, x, y, width, height):
                return True
            continue
        for px, py in _points(shape):
            if px < left or px > right or py < top or py > bottom:
                return True
    return False


def _points(shape: Shape):
    for segment in outline(shape) or ():
        match segment:
            case MoveTo(x=x, y=y) | LineTo(x=x, y=y):
                yield x, y
            case CubicTo(c1x=c1x, c1y=c1y, c2x=c2x, c2y=c2y, x=x, y=y):
                yield c1x, c1y
                yield c2x, c2y
                yield x, y
