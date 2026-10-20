"""Select tool: click/box selection, moving, and scaling/rotating through the selection frame's handles."""

import math
from enum import Enum, auto

from presstoshape.editing import containers, queries
from presstoshape.editing.operations import clipboard, edit_mode, guides, selection, transform
from presstoshape.geometry import affine, transforms
from presstoshape.geometry.affine import Affine
from presstoshape.geometry.align import union
from presstoshape.geometry.boxes import Point, Rect, rect_from_points
from presstoshape.i18n import _
from presstoshape.models.layout import Guide
from presstoshape.models.shapes import CompositeShape, GroupShape, Shape
from presstoshape.render import hit_test
from presstoshape.render.guides import guide_at
from presstoshape.render.handles import Frame, Handle, handle_at, handle_direction, selection_frame
from presstoshape.render.overlay import Overlay
from presstoshape.tools.base import HIT_TOLERANCE_PX, BaseTool, CursorType, Mods, ToolContext, resize_cursor_type
from presstoshape.tools.snapper import Snapper, shape_points

# Above this many shapes a scale preview replays the recorded shapes under the matrix (strokes scale too until
# release) instead of rebuilding each shape per mouse move.
_EXACT_PREVIEW_LIMIT = 200
_ROTATE_SNAP_DEG = 15.0
# Moving more shapes than this snaps by their bounding box only, not their nodes too.
_SNAP_POINTS_LIMIT = 200


class _Mode(Enum):
    BAND = auto()
    MOVE = auto()
    SCALE = auto()
    ROTATE = auto()
    GUIDE = auto()


class SelectTool(BaseTool):
    def __init__(self, context: ToolContext) -> None:
        super().__init__(context)
        self._mode: _Mode | None = None
        self._start: Point = (0.0, 0.0)
        self._end: Point = (0.0, 0.0)
        self._band_base: set[int] = set()
        self._moving: list[Shape] = []
        # Alt+drag: the move leaves the originals and places copies.
        self._duplicating = False
        self._handle: Handle | None = None
        self._frame0: Frame | None = None
        self._matrix: Affine = affine.IDENTITY
        self._live: tuple[Shape, ...] = ()
        self._cursor = CursorType.ARROW
        self.hint: str | None = None
        self._frame_key: tuple[Shape, ...] | None = None
        self._frame: Frame | None = None
        self._snapper = Snapper.off()
        # Moving: the moving shapes' box and nodes, as they were when the drag started.
        self._move_box: Rect = (0.0, 0.0, 0.0, 0.0)
        self._move_points: list[Point] = []
        self._guide: Guide | None = None

    @property
    def active(self) -> bool:
        return self._mode is not None

    def frame(self) -> Frame | None:
        """Frame of the committed selection, cached until the selected shapes change."""
        shapes = tuple(queries.selected_shapes(self._context.state))
        if shapes != self._frame_key:
            self._frame_key = shapes
            self._frame = selection_frame(shapes, self._context.cache)
        return self._frame

    @property
    def overlay(self) -> Overlay:
        state = self._context.state
        selected_ids = frozenset(state.selection)
        if self._mode is _Mode.BAND:
            return Overlay(frozenset(self._band_base | self._band_hits()), rubber_band=self._band())
        if self._mode is _Mode.GUIDE:
            return Overlay(selected_ids, frame=self.frame(), snap=self._snapper.hits, guide_preview=self._guide)
        frame = self.frame()
        if self._mode is None or frame is None:
            return Overlay(selected_ids, frame=frame)
        snap = self._snapper.hits
        if self._duplicating:
            return Overlay(
                selected_ids,
                matrix=self._matrix,
                copies=tuple(self._moving),
                frame=frame.transformed(self._matrix),
                snap=snap,
            )
        moving = frozenset(shape.id for shape in self._moving)
        return Overlay(
            selected_ids,
            moving=moving,
            matrix=self._matrix,
            live=self._live,
            frame=frame.transformed(self._matrix),
            snap=snap,
        )

    # --- events ---------------------------------------------------------------

    def press(self, point: Point, mods: Mods) -> None:
        state = self._context.state
        self._start = self._end = point
        self._cursor = self.hover(point)
        frame = self.frame()
        handle = handle_at(frame, point, self._context.zoom) if frame is not None and not mods.ctrl else None
        if handle is not None:
            self._mode = _Mode.ROTATE if handle.is_rotate else _Mode.SCALE
            self._handle, self._frame0 = handle, frame
            self._moving = queries.selected_shapes(self._context.state)
            if self._mode is _Mode.SCALE:
                self._snapper = self._context.snapper(exclude=(shape.id for shape in self._moving))
            return
        hit = self._context.shape_at(point)
        guide = self._guide_at(point) if hit is None else None
        if guide is not None:
            self._mode, self._guide = _Mode.GUIDE, guide
            self._cursor = self._guide_cursor(guide)
            self._snapper = self._context.snapper(guides=False)
            return
        if hit is None:
            self._mode = _Mode.BAND
            self._band_base = set(state.selection) if mods.ctrl else set()
            return
        if mods.ctrl:
            selection.set_selection(self._context.session, state.selection ^ {hit})
            return
        if hit not in state.selection:
            selection.set_selection(self._context.session, {hit})
        self._mode = _Mode.MOVE
        self._duplicating = mods.alt
        self._cursor = CursorType.DUPLICATE if mods.alt else CursorType.MOVE
        self._moving = queries.selected_shapes(self._context.state)
        self._start_move_snapping()

    def move(self, point: Point, mods: Mods) -> None:
        if self._mode is None:
            return
        self._end = point
        match self._mode:
            case _Mode.MOVE:
                offset = (point[0] - self._start[0], point[1] - self._start[1])
                dx, dy = self._snapper.offset(self._move_box, offset, self._move_points, ignore=mods.ctrl)
                self._matrix = affine.translation(dx, dy)
            case _Mode.SCALE:
                self._matrix = self._scale_matrix(self._snapper.point(point, ignore=mods.ctrl), mods)
                self._live = self._exact_preview()
            case _Mode.GUIDE if self._guide is not None:
                horizontal = self._guide.orientation == "horizontal"
                position = self._snapper.axis(point[1] if horizontal else point[0], horizontal, ignore=mods.ctrl)
                self._guide = Guide(self._guide.id, self._guide.orientation, position)
            case _Mode.ROTATE:
                self._matrix = self._rotate_matrix(point, mods)
        self._context.repaint()

    def release(self, point: Point, mods: Mods) -> None:
        if self._mode is None:
            return
        self.move(point, mods)
        mode, matrix, duplicating, guide = self._mode, self._matrix, self._duplicating, self._guide
        chosen = self._band_base | self._band_hits() if mode is _Mode.BAND else set()
        self.cancel()
        session = self._context.session
        match mode:
            case _Mode.BAND:
                selection.set_selection(session, chosen)
            case _Mode.MOVE if duplicating:
                if matrix[4] or matrix[5]:
                    clipboard.duplicate_and_move(session, matrix[4], matrix[5])
            case _Mode.MOVE:
                if matrix[4] or matrix[5]:
                    selection.move_selection(session, matrix[4], matrix[5])
            case _Mode.SCALE | _Mode.ROTATE:
                transform.transform_selection(session, matrix)
            case _Mode.GUIDE if guide is not None:
                if self._context.pointer_off_canvas:
                    guides.delete_guide(session, guide.id)
                else:
                    guides.move_guide(session, guide.id, guide.position)
        self._context.repaint()

    def cancel(self) -> None:
        self._mode = None
        self._moving = []
        self._duplicating = False
        self._band_base = set()
        self._handle = self._frame0 = None
        self._matrix = affine.IDENTITY
        self._live = ()
        self._snapper = Snapper.off()
        self._move_points = []
        self._guide = None
        self.hint = None

    def double_click(self, point: Point, mods: Mods) -> None:
        """Enters a Composite or group; inside one, a double-click on nothing leaves one level."""
        state = self._context.state
        hit = self._context.shape_at(point)
        shape = queries.find_shape(state, hit) if hit is not None else None
        guide = self._guide_at(point) if hit is None else None
        if guide is not None:
            self.cancel()
            self._context.edit_guide(guide.id)
        elif isinstance(shape, (CompositeShape, GroupShape)):
            self.cancel()
            edit_mode.enter(self._context.session, shape.id)
        elif hit is None and containers.editing(state):
            self.cancel()
            edit_mode.leave(self._context.session)
        else:
            self.press(point, mods)

    def key(self, name: str) -> bool:
        if name != "enter":
            return False
        selected = queries.selected_shapes(self._context.state)
        if len(selected) == 1 and isinstance(selected[0], (CompositeShape, GroupShape)):
            edit_mode.enter(self._context.session, selected[0].id)
            return True
        return False

    def hover(self, point: Point) -> CursorType:
        if self._mode is not None:
            return self._cursor
        frame = self.frame()
        handle = handle_at(frame, point, self._context.zoom) if frame is not None else None
        if handle is not None:
            return CursorType.ROTATE if handle.is_rotate else resize_cursor_type(handle_direction(frame, handle))
        if self._context.shape_at(point) is not None:
            return CursorType.MOVE
        guide = self._guide_at(point)
        return self._guide_cursor(guide) if guide is not None else CursorType.ARROW

    # --- snapping and guides --------------------------------------------------

    def _start_move_snapping(self) -> None:
        cache = self._context.cache
        boxes = []
        for shape in self._moving:
            bounds = cache.geometry_bounds(shape)
            boxes.append((bounds.left(), bounds.top(), bounds.width(), bounds.height()))
        self._move_box = union(boxes) if boxes else (0.0, 0.0, 0.0, 0.0)
        snap_nodes = self._context.state.snapping.nodes and len(self._moving) <= _SNAP_POINTS_LIMIT
        self._move_points = [point for shape in self._moving for point in shape_points(shape)] if snap_nodes else []
        self._snapper = self._context.snapper(exclude=(shape.id for shape in self._moving))

    def _guide_at(self, point: Point) -> Guide | None:
        state = self._context.state
        if not state.view.show_guides or state.view.lock_guides:
            return None
        return guide_at(state.document.guides, point, HIT_TOLERANCE_PX * self._context.pixel_size)

    @staticmethod
    def _guide_cursor(guide: Guide) -> CursorType:
        return CursorType.GUIDE_HORIZONTAL if guide.orientation == "horizontal" else CursorType.GUIDE_VERTICAL

    # --- transform math -------------------------------------------------------

    def _scale_matrix(self, point: Point, mods: Mods) -> Affine:
        frame, handle = self._frame0, self._handle
        assert frame is not None and handle is not None
        to_frame = affine.invert(frame.transform)
        px, py = affine.apply(to_frame, *point)
        sx0, sy0 = affine.apply(to_frame, *self._start)
        x, y, w, h = frame.rect
        u, v = handle.fraction
        au, av = (0.5, 0.5) if mods.alt else (1 - u, 1 - v)
        ax, ay = x + au * w, y + av * h
        hx, hy = x + u * w, y + v * h
        fx = self._factor(hx + px - sx0 - ax, hx - ax) if u != 0.5 else 1.0
        fy = self._factor(hy + py - sy0 - ay, hy - ay) if v != 0.5 else 1.0
        if mods.shift:
            if u != 0.5 and v != 0.5:
                uniform = max(abs(fx), abs(fy))
                fx, fy = math.copysign(uniform, fx), math.copysign(uniform, fy)
            elif u != 0.5:
                fy = abs(fx)
            else:
                fx = abs(fy)
        a, b, c, d = frame.transform[:4]
        fx = self._clamped(fx, w * math.hypot(a, b))
        fy = self._clamped(fy, h * math.hypot(c, d))
        return affine.compose(frame.transform, affine.compose(affine.scaling(fx, fy, ax, ay), to_frame))

    @staticmethod
    def _factor(new: float, old: float) -> float:
        return new / old if abs(old) > 1e-12 else 1.0

    def _clamped(self, factor: float, extent: float) -> float:
        """Keeps the scaled extent at least one screen px; the sign survives so dragging across flips."""
        if extent <= 0:
            return 1.0
        minimum = self._context.pixel_size / extent
        return factor if abs(factor) >= minimum else math.copysign(minimum, factor)

    def _rotate_matrix(self, point: Point, mods: Mods) -> Affine:
        assert self._frame0 is not None
        if point == self._start:
            return affine.IDENTITY
        cx, cy = self._frame0.center()
        sweep = math.degrees(
            math.atan2(point[1] - cy, point[0] - cx) - math.atan2(self._start[1] - cy, self._start[0] - cx)
        )
        base = (transforms.rotation_of(self._moving[0]) or 0.0) if len(self._moving) == 1 else 0.0
        result = base + sweep
        if mods.shift:
            result = round(result / _ROTATE_SNAP_DEG) * _ROTATE_SNAP_DEG
        result = math.remainder(result, 360)
        self.hint = _("Rotate {angle:.1f}°").format(angle=result)
        return affine.rotation(math.radians(result - base), cx, cy)

    def _exact_preview(self) -> tuple[Shape, ...]:
        if len(self._moving) > _EXACT_PREVIEW_LIMIT:
            return ()
        return tuple(transforms.transform_shape(shape, self._matrix) for shape in self._moving)

    # --- helpers --------------------------------------------------------------

    def _band(self) -> Rect:
        return rect_from_points(self._start, self._end)

    def _band_hits(self) -> set[int]:
        if self._mode is not _Mode.BAND:
            return set()
        shapes = queries.pickable_shapes(self._context.state)
        return hit_test.shapes_in_rect(shapes, self._context.cache, self._band())
