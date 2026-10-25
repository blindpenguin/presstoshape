"""Selection frame and handle picking for the transform gestures, sized in screen px at any zoom. Draws nothing."""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from presstoshape.geometry import affine, nodes
from presstoshape.geometry.affine import Affine
from presstoshape.geometry.boxes import Point, Rect
from presstoshape.models.shapes import (
    IDENTITY_TRANSFORM,
    CompositeShape,
    EllipseShape,
    GroupShape,
    ImageShape,
    PathShape,
    RectShape,
    Shape,
    TextShape,
)
from presstoshape.render.paths import PathCache
from presstoshape.render.text import text_path

HANDLE_PX = 8.0
# Grab radius around a handle center; a bit larger than the drawn square so it's easy to hit.
_GRAB_PX = HANDLE_PX / 2 + 2
_ROTATE_REACH_PX = 22.0
# Below this on-screen length an axis shows only its corner handles, leaving room to grab the shape.
_MIN_EDGE_HANDLES_PX = 3 * HANDLE_PX


class Handle(Enum):
    """Value: position in the frame as fractions of width/height."""

    NW = (0.0, 0.0)
    N = (0.5, 0.0)
    NE = (1.0, 0.0)
    E = (1.0, 0.5)
    SE = (1.0, 1.0)
    S = (0.5, 1.0)
    SW = (0.0, 1.0)
    W = (0.0, 0.5)
    ROTATE_NW = (0.0, 0.0, "rotate")
    ROTATE_NE = (1.0, 0.0, "rotate")
    ROTATE_SE = (1.0, 1.0, "rotate")
    ROTATE_SW = (0.0, 1.0, "rotate")

    @property
    def fraction(self) -> Point:
        return self.value[0], self.value[1]

    @property
    def is_rotate(self) -> bool:
        return len(self.value) == 3

    @property
    def opposite(self) -> "Handle":
        u, v = self.fraction
        return _BY_FRACTION[(1 - u, 1 - v)]


SCALE_HANDLES = tuple(h for h in Handle if not h.is_rotate)
_EDGE_HANDLES = {Handle.N: "x", Handle.S: "x", Handle.E: "y", Handle.W: "y"}
_BY_FRACTION = {h.fraction: h for h in SCALE_HANDLES}
_ROTATE_FOR_CORNER = {
    Handle.NW: Handle.ROTATE_NW,
    Handle.NE: Handle.ROTATE_NE,
    Handle.SE: Handle.ROTATE_SE,
    Handle.SW: Handle.ROTATE_SW,
}


@dataclass(frozen=True)
class Frame:
    """Box `rect` (x, y, w, h) in frame space; `transform` maps frame space to the document."""

    rect: Rect
    transform: Affine = IDENTITY_TRANSFORM

    def point(self, u: float, v: float) -> Point:
        x, y, w, h = self.rect
        return affine.apply(self.transform, x + u * w, y + v * h)

    def center(self) -> Point:
        return self.point(0.5, 0.5)

    def corners(self) -> list[Point]:
        return [self.point(u, v) for u, v in ((0, 0), (1, 0), (1, 1), (0, 1))]

    def transformed(self, m: Affine) -> "Frame":
        return Frame(self.rect, affine.compose(m, self.transform))

    def screen_size(self, zoom: float) -> tuple[float, float]:
        a, b, c, d = self.transform[:4]
        _, _, w, h = self.rect
        return abs(w) * math.hypot(a, b) * zoom, abs(h) * math.hypot(c, d) * zoom


def local_bounds(shape: Shape, cache: PathCache) -> Rect:
    """Geometric bounds before the shape's transform."""
    match shape:
        case RectShape(x=x, y=y, width=w, height=h) | ImageShape(x=x, y=y, width=w, height=h):
            return x, y, w, h
        case EllipseShape(cx=cx, cy=cy, rx=rx, ry=ry):
            return cx - rx, cy - ry, 2 * rx, 2 * ry
        case TextShape():
            b = text_path(shape).computeTightBounds()
        case PathShape():
            b = cache.geometry_bounds(shape)
    return b.left(), b.top(), b.width(), b.height()


def selection_frame(shapes: Iterable[Shape], cache: PathCache) -> Frame | None:
    """One shape: its own (possibly rotated) box. Several: the axis-aligned box around all of them."""
    shapes = list(shapes)
    if not shapes:
        return None
    if len(shapes) == 1 and not isinstance(shapes[0], (PathShape, CompositeShape, GroupShape)):
        return Frame(local_bounds(shapes[0], cache), shapes[0].transform)
    boxes = [cache.geometry_bounds(s) for s in shapes]
    left, top = min(b.left() for b in boxes), min(b.top() for b in boxes)
    right, bottom = max(b.right() for b in boxes), max(b.bottom() for b in boxes)
    return Frame((left, top, right - left, bottom - top))


def handle_points(frame: Frame, zoom: float) -> dict[Handle, Point]:
    """Doc positions of the scale handles shown at this zoom."""
    width_px, height_px = frame.screen_size(zoom)
    hidden = {"x": width_px < _MIN_EDGE_HANDLES_PX, "y": height_px < _MIN_EDGE_HANDLES_PX}
    return {h: frame.point(*h.fraction) for h in SCALE_HANDLES if not hidden.get(_EDGE_HANDLES.get(h, ""), False)}


def handle_at(frame: Frame, point: Point, zoom: float) -> Handle | None:
    """Scale handle within grab distance, else a rotation zone just outside a corner, else None."""
    best: tuple[float, Handle] | None = None
    for handle, p in handle_points(frame, zoom).items():
        dist = max(abs(point[0] - p[0]), abs(point[1] - p[1])) * zoom
        if dist <= _GRAB_PX and (best is None or dist < best[0]):
            best = (dist, handle)
    if best is not None:
        return best[1]
    if _inside(frame, point):
        return None
    for corner, rotate in _ROTATE_FOR_CORNER.items():
        p = frame.point(*corner.fraction)
        if math.hypot(point[0] - p[0], point[1] - p[1]) * zoom <= _ROTATE_REACH_PX:
            return rotate
    return None


def handle_direction(frame: Frame, handle: Handle) -> float:
    """On-screen angle (degrees, y down) of the handle's outward direction; picks the resize cursor."""
    u, v = handle.fraction
    du, dv = 2 * u - 1, 2 * v - 1
    a, b, c, d = frame.transform[:4]
    # Unit axes, so a long thin frame still gives 45° corners.
    nu, nv = math.hypot(a, b) or 1.0, math.hypot(c, d) or 1.0
    return math.degrees(math.atan2(b / nu * du + d / nv * dv, a / nu * du + c / nv * dv))


NODE_PX = 7.0
# How much larger a subpath's start node is drawn.
START_EXTRA_PX = 4.0
CONTROL_PX = 6.0
_NODE_GRAB_PX = 6.0


def node_at(segments, point: Point, zoom: float, controls=()) -> tuple[str, object] | None:
    """("control", ref) for a visible control or ("node", index) for an anchor within grab distance, else None.

    Controls win over anchors, since a control often sits right on top of its anchor.
    """
    reach = _NODE_GRAB_PX / zoom
    best: tuple[float, tuple[str, object]] | None = None
    for ref in controls:
        cx, cy = nodes.control_point(segments, ref)
        dist = math.hypot(point[0] - cx, point[1] - cy)
        if dist <= reach and (best is None or dist < best[0]):
            best = (dist, ("control", ref))
    if best is not None:
        return best[1]
    for info in nodes.nodes(segments):
        dist = math.hypot(point[0] - info.point[0], point[1] - info.point[1])
        if dist <= reach and (best is None or dist < best[0]):
            best = (dist, ("node", info.index))
    return None if best is None else best[1]


WIDGET_PX = 7.0
_WIDGET_GRAB_PX = 5.0


def widget_at(widgets, point: Point, zoom: float) -> int | None:
    """The node index of the live-corner widget under `point`, nearest first."""
    reach = _WIDGET_GRAB_PX / zoom
    best: tuple[float, int] | None = None
    for index, (x, y) in widgets:
        dist = math.hypot(point[0] - x, point[1] - y)
        if dist <= reach and (best is None or dist < best[0]):
            best = (dist, index)
    return None if best is None else best[1]


def _inside(frame: Frame, point: Point) -> bool:
    try:
        lx, ly = affine.apply(affine.invert(frame.transform), *point)
    except ValueError:
        return False
    x, y, w, h = frame.rect
    return min(x, x + w) <= lx <= max(x, x + w) and min(y, y + h) <= ly <= max(y, y + h)
