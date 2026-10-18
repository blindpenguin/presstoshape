"""Select tool: click/box selection, moving, and scaling/rotating through the selection frame's handles."""

import math
from enum import Enum, auto

from veccy.controllers import affine, geometry
from veccy.controllers.affine import Affine
from veccy.controllers.geometry import Point
from veccy.models.shapes import Shape
from veccy.render import hit_test
from veccy.render.handles import Frame, Handle, handle_at, handle_direction, selection_frame
from veccy.render.overlay import Overlay, Rect
from veccy.views.gesture_types import HIT_TOLERANCE_PX, CursorType, GestureContext, Mods, resize_cursor_type

# Above this many shapes a scale preview replays the recorded shapes under the matrix (strokes scale too until
# release) instead of rebuilding each shape per mouse move.
_EXACT_PREVIEW_LIMIT = 200
_ROTATE_SNAP_DEG = 15.0


class _Mode(Enum):
    BAND = auto()
    MOVE = auto()
    SCALE = auto()
    ROTATE = auto()


class SelectGesture:
    def __init__(self, ctx: GestureContext) -> None:
        self._ctx = ctx
        self._mode: _Mode | None = None
        self._start: Point = (0.0, 0.0)
        self._end: Point = (0.0, 0.0)
        self._band_base: set[int] = set()
        self._moving: list[Shape] = []
        self._handle: Handle | None = None
        self._frame0: Frame | None = None
        self._matrix: Affine = affine.IDENTITY
        self._live: tuple[Shape, ...] = ()
        self._cursor = CursorType.ARROW
        self.hint: str | None = None
        self._frame_key: tuple[Shape, ...] | None = None
        self._frame: Frame | None = None

    @property
    def active(self) -> bool:
        return self._mode is not None

    def frame(self) -> Frame | None:
        """Frame of the committed selection, cached until the selected shapes change."""
        shapes = tuple(self._ctx.controller.selected_shapes()) if self._ctx.state else ()
        if shapes != self._frame_key:
            self._frame_key = shapes
            self._frame = selection_frame(shapes, self._ctx.cache)
        return self._frame

    @property
    def overlay(self) -> Overlay:
        state = self._ctx.state
        selection = frozenset(state.selection) if state else frozenset()
        if self._mode is _Mode.BAND:
            return Overlay(frozenset(self._band_base | self._band_hits()), rubber_band=self._band())
        frame = self.frame()
        if self._mode is None or frame is None:
            return Overlay(selection, frame=frame)
        moving = frozenset(s.id for s in self._moving)
        return Overlay(selection, moving=moving, matrix=self._matrix, live=self._live, frame=frame.transformed(self._matrix))

    # --- events ---------------------------------------------------------------

    def press(self, point: Point, mods: Mods) -> None:
        state = self._ctx.state
        if state is None:
            return
        self._start = self._end = point
        self._cursor = self.hover(point)
        frame = self.frame()
        handle = handle_at(frame, point, self._ctx.zoom) if frame is not None and not mods.ctrl else None
        if handle is not None:
            self._mode = _Mode.ROTATE if handle.is_rotate else _Mode.SCALE
            self._handle, self._frame0 = handle, frame
            self._moving = self._ctx.controller.selected_shapes()
            return
        hit = self._shape_at(point)
        if hit is None:
            self._mode = _Mode.BAND
            self._band_base = set(state.selection) if mods.ctrl else set()
            return
        if mods.ctrl:
            self._ctx.controller.set_selection(state.selection ^ {hit})
            return
        if hit not in state.selection:
            self._ctx.controller.set_selection({hit})
        self._mode = _Mode.MOVE
        self._cursor = CursorType.MOVE
        self._moving = self._ctx.controller.selected_shapes()

    def move(self, point: Point, mods: Mods) -> None:
        if self._mode is None:
            return
        self._end = point
        match self._mode:
            case _Mode.MOVE:
                self._matrix = affine.translation(point[0] - self._start[0], point[1] - self._start[1])
            case _Mode.SCALE:
                self._matrix = self._scale_matrix(point, mods)
                self._live = self._exact_preview()
            case _Mode.ROTATE:
                self._matrix = self._rotate_matrix(point, mods)
        self._ctx.repaint()

    def release(self, point: Point, mods: Mods) -> None:
        if self._mode is None:
            return
        self.move(point, mods)
        mode, matrix = self._mode, self._matrix
        selection = self._band_base | self._band_hits() if mode is _Mode.BAND else None
        self.cancel()
        controller = self._ctx.controller
        match mode:
            case _Mode.BAND:
                controller.set_selection(selection)
            case _Mode.MOVE:
                if matrix[4] or matrix[5]:
                    controller.move_selection(matrix[4], matrix[5])
            case _Mode.SCALE | _Mode.ROTATE:
                controller.transform_selection(matrix)
        self._ctx.repaint()

    def cancel(self) -> None:
        self._mode = None
        self._moving = []
        self._band_base = set()
        self._handle = self._frame0 = None
        self._matrix = affine.IDENTITY
        self._live = ()
        self.hint = None

    def hover(self, point: Point) -> CursorType:
        if self._mode is not None:
            return self._cursor
        frame = self.frame()
        handle = handle_at(frame, point, self._ctx.zoom) if frame is not None else None
        if handle is not None:
            return CursorType.ROTATE if handle.is_rotate else resize_cursor_type(handle_direction(frame, handle))
        return CursorType.MOVE if self._shape_at(point) is not None else CursorType.ARROW

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
        minimum = self._ctx.pixel_size / extent
        return factor if abs(factor) >= minimum else math.copysign(minimum, factor)

    def _rotate_matrix(self, point: Point, mods: Mods) -> Affine:
        assert self._frame0 is not None
        if point == self._start:
            return affine.IDENTITY
        cx, cy = self._frame0.center()
        sweep = math.degrees(
            math.atan2(point[1] - cy, point[0] - cx) - math.atan2(self._start[1] - cy, self._start[0] - cx)
        )
        base = (geometry.rotation_of(self._moving[0]) or 0.0) if len(self._moving) == 1 else 0.0
        result = base + sweep
        if mods.shift:
            result = round(result / _ROTATE_SNAP_DEG) * _ROTATE_SNAP_DEG
        result = math.remainder(result, 360)
        self.hint = f"Rotate {result:.1f}°"
        return affine.rotation(math.radians(result - base), cx, cy)

    def _exact_preview(self) -> tuple[Shape, ...]:
        if len(self._moving) > _EXACT_PREVIEW_LIMIT:
            return ()
        return tuple(geometry.transform_shape(s, self._matrix) for s in self._moving)

    # --- helpers --------------------------------------------------------------

    def _shape_at(self, point: Point) -> int | None:
        state = self._ctx.state
        if state is None:
            return None
        return hit_test.shape_at(state.document, self._ctx.cache, point, HIT_TOLERANCE_PX * self._ctx.pixel_size)

    def _band(self) -> Rect:
        (x0, y0), (x1, y1) = self._start, self._end
        return min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)

    def _band_hits(self) -> set[int]:
        if self._mode is not _Mode.BAND or self._ctx.state is None:
            return set()
        return hit_test.shapes_in_rect(self._ctx.state.document, self._ctx.cache, self._band())
