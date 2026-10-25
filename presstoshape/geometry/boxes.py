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


def constrain_angle(origin: Point, point: Point, step_deg: float = 45.0) -> Point:
    """`point` projected onto the nearest ray from `origin` at a multiple of `step_deg` (Shift-drawing)."""
    dx, dy = point[0] - origin[0], point[1] - origin[1]
    step = math.radians(step_deg)
    angle = round(math.atan2(dy, dx) / step) * step
    ux, uy = math.cos(angle), math.sin(angle)
    length = dx * ux + dy * uy
    return origin[0] + length * ux, origin[1] + length * uy
