"""`preserveAspectRatio` math shared by SVG viewports and images: align, meet and slice."""

import math
from typing import Final

from presstoshape.geometry.affine import Affine
from presstoshape.models.shapes import Aspect, ImageShape

ViewBox = tuple[float, float, float, float]
Rect = tuple[float, float, float, float]


class Invalid:
    def __repr__(self) -> str:
        return "INVALID"


INVALID: Final = Invalid()

_ALIGN_FRACTION = {"Min": 0.0, "Mid": 0.5, "Max": 1.0}
_ALIGNS = {f"x{x}Y{y}" for x in _ALIGN_FRACTION for y in _ALIGN_FRACTION}

DEFAULT = Aspect("xMidYMid")


def parse_aspect(text: str | None) -> Aspect | None | Invalid:
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


def fitted_rect(
    source_width: float, source_height: float, x: float, y: float, width: float, height: float, aspect: Aspect
) -> tuple[Rect, bool]:
    """Where a source of the given size lands in the viewport rectangle, and whether it must be clipped to the
    viewport (slice). Empty or non-finite sizes give an empty rectangle at the viewport origin."""
    values = (source_width, source_height, x, y, width, height)
    if not all(math.isfinite(value) for value in values) or min(source_width, source_height, width, height) <= 0:
        return (x if math.isfinite(x) else 0.0, y if math.isfinite(y) else 0.0, 0.0, 0.0), False
    scale_x, _, _, scale_y, offset_x, offset_y = fit((0.0, 0.0, source_width, source_height), width, height, aspect)
    rect = (x + offset_x, y + offset_y, source_width * scale_x, source_height * scale_y)
    return rect, aspect.slice and aspect.align != "none"


def visible_box(shape: ImageShape) -> Rect:
    """The area an image covers: the fitted rectangle (meet), the viewport otherwise (slice is clipped to it)."""
    rect, clipped = fitted_rect(
        shape.data.width, shape.data.height, shape.x, shape.y, shape.width, shape.height, shape.aspect
    )
    if clipped or rect[2] <= 0 or rect[3] <= 0:
        return shape.x, shape.y, max(0.0, shape.width), max(0.0, shape.height)
    return rect
