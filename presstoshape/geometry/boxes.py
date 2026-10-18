"""Points and axis-aligned boxes: the 2D basics shared by every layer."""

import math

Point = tuple[float, float]
# x, y, width, height.
Rect = tuple[float, float, float, float]


def rect_from_points(a: Point, b: Point) -> Rect:
    """Box spanned by two corners in any order (rubber bands, drag boxes)."""
    return min(a[0], b[0]), min(a[1], b[1]), abs(b[0] - a[0]), abs(b[1] - a[1])


def box_from_drag(start: Point, end: Point, square: bool = False) -> Rect:
    w, h = end[0] - start[0], end[1] - start[1]
    if square:
        side = max(abs(w), abs(h))
        w, h = math.copysign(side, w), math.copysign(side, h)
    return min(start[0], start[0] + w), min(start[1], start[1] + h), abs(w), abs(h)
