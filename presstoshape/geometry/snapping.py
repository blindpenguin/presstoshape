"""Snapping: the positions a drag can jump to, and which one is closest.

Targets are collected once per gesture into sorted tuples, so every query during the drag is a bisection.
Coordinates are document px; the tolerance is the snap distance converted from screen px by the caller.
"""

import bisect
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from presstoshape.geometry.boxes import Point, Rect

SnapTarget = Literal["grid", "guide", "artboard", "edge", "centre", "node"]


@dataclass(frozen=True)
class LineTarget:
    """A vertical line (x) or horizontal line (y) a coordinate can snap to."""

    value: float
    target: SnapTarget
    # Span along the other axis of what the line belongs to (an object's top to bottom for an x line), so the
    # feedback line can reach it; None for guides and grid lines, which are visible anyway.
    extent: tuple[float, float] | None = None


@dataclass(frozen=True)
class GridSpec:
    origin: Point
    spacing: float


@dataclass(frozen=True)
class SnapHit:
    axis: Literal["x", "y", "point"]
    value: float
    target: SnapTarget
    # Feedback segment in document coordinates, or None.
    line: tuple[Point, Point] | None
    # Where the snap happened, for the label.
    at: Point


@dataclass(frozen=True)
class SnapResult:
    """What to add to the dragged geometry, and what it snapped to."""

    offset: Point
    hits: tuple[SnapHit, ...]


NO_SNAP = SnapResult((0.0, 0.0), ())


class SnapTargets:
    def __init__(
        self,
        xs: Iterable[LineTarget] = (),
        ys: Iterable[LineTarget] = (),
        points: Iterable[Point] = (),
        grid: GridSpec | None = None,
    ) -> None:
        self.xs = tuple(sorted(xs, key=lambda line: line.value))
        self.ys = tuple(sorted(ys, key=lambda line: line.value))
        self._x_values = tuple(line.value for line in self.xs)
        self._y_values = tuple(line.value for line in self.ys)
        self.points = tuple(sorted(points))
        self._point_xs = tuple(point[0] for point in self.points)
        self.grid = grid if grid is not None and grid.spacing > 0 else None

    def with_points(self, points: Iterable[Point]) -> "SnapTargets":
        return SnapTargets(self.xs, self.ys, (*self.points, *points), self.grid)

    def __len__(self) -> int:
        return len(self.xs) + len(self.ys) + len(self.points)

    def snap_point(self, point: Point, tolerance: float) -> SnapResult:
        """A single dragged point: nodes first (both axes), else x and y independently."""
        x, y = point
        return self.snap_box((x, y, 0.0, 0.0), tolerance, (point,))

    def snap_box(self, box: Rect, tolerance: float, points: Sequence[Point] = ()) -> SnapResult:
        """A dragged box (its edges and centre) and some of its points (nodes), corrected by the nearest
        target within `tolerance`."""
        point_hit = self._nearest_point(points, tolerance)
        if point_hit is not None:
            (source, target), _distance = point_hit
            offset = (target[0] - source[0], target[1] - source[1])
            return SnapResult(offset, (SnapHit("point", 0.0, "node", None, target),))
        x, y, width, height = box
        sources_x = (x, x + width / 2, x + width) if width else (x,)
        sources_y = (y, y + height / 2, y + height) if height else (y,)
        x_snap = self._nearest_line(self.xs, self._x_values, sources_x, tolerance, 0)
        y_snap = self._nearest_line(self.ys, self._y_values, sources_y, tolerance, 1)
        dx = x_snap[0] if x_snap is not None else 0.0
        dy = y_snap[0] if y_snap is not None else 0.0
        hits = []
        # Feedback lines reach from the box where it ends up to the object it lines up with.
        if x_snap is not None:
            hits.append(self._hit("x", x_snap, (y + dy, y + height + dy)))
        if y_snap is not None:
            hits.append(self._hit("y", y_snap, (x + dx, x + width + dx)))
        if not hits:
            return NO_SNAP
        return SnapResult((dx, dy), tuple(hits))

    @staticmethod
    def _hit(
        axis: Literal["x", "y"],
        snap: tuple[float, float, SnapTarget, tuple[float, float] | None],
        own: tuple[float, float],
    ) -> SnapHit:
        """`own`: the dragged box's span along the other axis."""
        _delta, value, target, extent = snap
        line = None
        if extent is not None:
            start, end = min(extent[0], own[0]), max(extent[1], own[1])
            line = ((value, start), (value, end)) if axis == "x" else ((start, value), (end, value))
        at = (value, own[0]) if axis == "x" else (own[0], value)
        return SnapHit(axis, value, target, line, at)

    def _nearest_line(
        self,
        lines: tuple[LineTarget, ...],
        values: tuple[float, ...],
        sources: Sequence[float],
        tolerance: float,
        axis: int,
    ) -> tuple[float, float, SnapTarget, tuple[float, float] | None] | None:
        """(correction, snapped value, target, extent) for the source coordinate closest to a target."""
        best: tuple[float, float, SnapTarget, tuple[float, float] | None] | None = None
        for source in sources:
            index = bisect.bisect_left(values, source)
            for candidate in (index - 1, index):
                if 0 <= candidate < len(lines):
                    line = lines[candidate]
                    delta = line.value - source
                    if abs(delta) <= tolerance and (best is None or abs(delta) < abs(best[0])):
                        best = (delta, line.value, line.target, line.extent)
            if self.grid is not None:
                origin, spacing = self.grid.origin[axis], self.grid.spacing
                value = origin + round((source - origin) / spacing) * spacing
                delta = value - source
                # Lines win ties: a guide on a grid line should say "Guide".
                if abs(delta) <= tolerance and (best is None or abs(delta) < abs(best[0]) - 1e-9):
                    best = (delta, value, "grid", None)
        return best

    def _nearest_point(self, sources: Sequence[Point], tolerance: float) -> tuple[tuple[Point, Point], float] | None:
        best: tuple[tuple[Point, Point], float] | None = None
        for source in sources:
            low = bisect.bisect_left(self._point_xs, source[0] - tolerance)
            high = bisect.bisect_right(self._point_xs, source[0] + tolerance)
            for target in self.points[low:high]:
                distance = math.hypot(target[0] - source[0], target[1] - source[1])
                if distance <= tolerance and (best is None or distance < best[1]):
                    best = ((source, target), distance)
        return best
