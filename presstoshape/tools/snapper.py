"""Snapping for one gesture: the targets around the visible area, collected when the gesture starts.

Tools build a Snapper on press and ask it for corrected points or offsets while dragging; it remembers what it
snapped to last, for the overlay. Holding Ctrl ignores snapping.
"""

from collections.abc import Iterable, Sequence

from presstoshape.editing import queries
from presstoshape.geometry import nodes, transforms, units
from presstoshape.geometry.boxes import Point, Rect
from presstoshape.geometry.snapping import NO_SNAP, GridSpec, LineTarget, SnapHit, SnapResult, SnapTargets
from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import CubicTo, GroupShape, LineTo, MoveTo, PathShape, Shape
from presstoshape.render.paths import PathCache

# Node targets beyond this many are left out (huge drawings zoomed out), so building stays quick.
_MAX_POINTS = 20_000
# Shapes this far outside the visible area (as a share of its size) still count.
_MARGIN = 0.1


def shape_points(shape: Shape) -> list[Point]:
    """Points of a shape's outline that snap: path nodes, rectangle corners, ellipse extremes; a group's from
    its children. Text has none."""
    if isinstance(shape, GroupShape):
        return [point for child in shape.children for point in shape_points(child)]
    segments = transforms.outline(shape)
    if not segments:
        return []
    return [(segment.x, segment.y) for segment in segments if isinstance(segment, (MoveTo, LineTo, CubicTo))]


def _box(cache: PathCache, shape: Shape) -> Rect:
    bounds = cache.geometry_bounds(shape)
    return bounds.left(), bounds.top(), bounds.width(), bounds.height()


def _overlaps(box: Rect, area: Rect | None) -> bool:
    if area is None:
        return True
    x, y, width, height = box
    left, top, area_width, area_height = area
    return x <= left + area_width and left <= x + width and y <= top + area_height and top <= y + height


class Snapper:
    def __init__(self, targets: SnapTargets | None, tolerance: float) -> None:
        self._targets = targets
        self._tolerance = tolerance
        self.hits: tuple[SnapHit, ...] = ()

    @classmethod
    def off(cls) -> "Snapper":
        return cls(None, 0.0)

    @classmethod
    def build(
        cls,
        state: AppState,
        cache: PathCache,
        pixel_size: float,
        visible: Rect | None = None,
        exclude: Iterable[int] = (),
        own_path: tuple[PathShape, set[int]] | None = None,
        guides: bool = True,
    ) -> "Snapper":
        """Targets from the artboard, guides, grid and the pickable shapes near the visible area, leaving out
        `exclude` (the moving shapes). `own_path`: a path whose nodes other than the given indices still snap
        (node dragging). `guides=False` when a guide itself is dragged."""
        settings = state.snapping
        if not settings.enabled:
            return cls.off()
        document = state.document
        xs: list[LineTarget] = []
        ys: list[LineTarget] = []
        points: list[Point] = []
        if settings.artboard:
            width, height = document.width, document.height
            for value in (0.0, width / 2, width):
                xs.append(LineTarget(value, "artboard", (0.0, height)))
            for value in (0.0, height / 2, height):
                ys.append(LineTarget(value, "artboard", (0.0, width)))
        if guides and settings.guides and state.view.show_guides:
            for guide in document.guides:
                (ys if guide.orientation == "horizontal" else xs).append(LineTarget(guide.position, "guide"))
        area = None
        if visible is not None:
            margin_x, margin_y = visible[2] * _MARGIN, visible[3] * _MARGIN
            area = (visible[0] - margin_x, visible[1] - margin_y, visible[2] + 2 * margin_x, visible[3] + 2 * margin_y)
        excluded = set(exclude)
        if settings.objects or settings.nodes:
            for shape in queries.pickable_shapes(state):
                if shape.id in excluded:
                    continue
                box = _box(cache, shape)
                if not _overlaps(box, area):
                    continue
                if settings.objects:
                    x, y, width, height = box
                    xs += [LineTarget(x, "edge", (y, y + height)), LineTarget(x + width, "edge", (y, y + height))]
                    xs.append(LineTarget(x + width / 2, "centre", (y, y + height)))
                    ys += [LineTarget(y, "edge", (x, x + width)), LineTarget(y + height, "edge", (x, x + width))]
                    ys.append(LineTarget(y + height / 2, "centre", (x, x + width)))
                if settings.nodes and len(points) < _MAX_POINTS:
                    points += shape_points(shape)
        if settings.nodes and own_path is not None:
            path, moving = own_path
            points += [info.point for info in nodes.nodes(path.segments) if info.index not in moving]
        grid = None
        if settings.grid and state.view.show_grid:
            grid = GridSpec((0.0, 0.0), units.grid_of(document).spacing)
        targets = SnapTargets(xs, ys, points[:_MAX_POINTS], grid)
        return cls(targets, settings.distance_px * pixel_size)

    def _use(self, result: SnapResult) -> SnapResult:
        self.hits = result.hits
        return result

    def point(self, point: Point, ignore: bool = False) -> Point:
        """`point` moved onto the nearest target, unless snapping is off or `ignore` (Ctrl held)."""
        if self._targets is None or ignore:
            self.hits = ()
            return point
        dx, dy = self._use(self._targets.snap_point(point, self._tolerance)).offset
        return point[0] + dx, point[1] + dy

    def axis(self, value: float, horizontal: bool, ignore: bool = False) -> float:
        """A guide's position: only one coordinate snaps."""
        if self._targets is None or ignore:
            self.hits = ()
            return value
        probe = (0.0, value) if horizontal else (value, 0.0)
        result = self._targets.snap_box((probe[0], probe[1], 0.0, 0.0), self._tolerance)
        hits = tuple(hit for hit in result.hits if hit.axis == ("y" if horizontal else "x"))
        self.hits = hits
        if not hits:
            return value
        return value + (result.offset[1] if horizontal else result.offset[0])

    def offset(self, box: Rect, offset: Point, points: Sequence[Point] = (), ignore: bool = False) -> Point:
        """A drag of `box` (and its `points`) by `offset`, corrected so an edge, centre or point lands on a
        target."""
        if self._targets is None or ignore:
            self.hits = ()
            return offset
        dx, dy = offset
        moved_box = (box[0] + dx, box[1] + dy, box[2], box[3])
        moved_points = [(x + dx, y + dy) for x, y in points]
        result = self._use(self._targets.snap_box(moved_box, self._tolerance, moved_points) or NO_SNAP)
        return dx + result.offset[0], dy + result.offset[1]
