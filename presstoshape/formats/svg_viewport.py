"""SVG viewports: `viewBox`, `preserveAspectRatio` and the matrix that fits one into the other.

Stricter than svgelements: attribute grammar is case-sensitive and a malformed value is `INVALID`, which differs
from `None` (attribute absent), so the reader can count ignored values.
"""

import math
import re
from collections.abc import Sequence

from presstoshape.geometry.affine import Affine
from presstoshape.geometry.aspect import DEFAULT, INVALID, Aspect, Invalid, fit, parse_aspect
from presstoshape.geometry.transforms import outline
from presstoshape.models.shapes import CubicTo, GroupShape, LineTo, MoveTo, Shape

__all__ = ["DEFAULT", "INVALID", "Aspect", "fit", "parse_aspect"]

ViewBox = tuple[float, float, float, float]


_NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_SEPARATOR = r"(?:\s*,\s*|\s+|(?=[-+]))"
_VIEW_BOX = re.compile(rf"\s*({_NUMBER}){_SEPARATOR}({_NUMBER}){_SEPARATOR}({_NUMBER}){_SEPARATOR}({_NUMBER})\s*")

_ESCAPE_TOLERANCE = 1e-6


def parse_view_box(text: str | None) -> ViewBox | None | Invalid:
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
