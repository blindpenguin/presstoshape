"""Select tool: click/box selection, moving, and scaling/rotating through the selection frame's handles."""

import math
from enum import Enum, auto

from presstoshape.editing import queries
from presstoshape.editing.operations import selection, transform
from presstoshape.geometry import affine, transforms
from presstoshape.geometry.affine import Affine
from presstoshape.geometry.boxes import Point, Rect, rect_from_points
from presstoshape.models.shapes import Shape
from presstoshape.render import hit_test
from presstoshape.render.handles import Frame, Handle, handle_at, handle_direction, selection_frame
from presstoshape.render.overlay import Overlay
from presstoshape.tools.base import BaseTool, CursorType, Mods, ToolContext, resize_cursor_type

# Above this many shapes a scale preview replays the recorded shapes under the matrix (strokes scale too until
# release) instead of rebuilding each shape per mouse move.
_EXACT_PREVIEW_LIMIT = 200
_ROTATE_SNAP_DEG = 15.0


class _Mode(Enum):
    BAND = auto()
    MOVE = auto()
    SCALE = auto()
    ROTATE = auto()


class SelectTool(BaseTool):
    def __init__(self, context: ToolContext) -> None:
        super().__init__(context)
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
        frame = self.frame()
        if self._mode is None or frame is None:
            return Overlay(selected_ids, frame=frame)
        moving = frozenset(shape.id for shape in self._moving)
        return Overlay(
            selected_ids, moving=moving, matrix=self._matrix, live=self._live, frame=frame.transformed(self._matrix)
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
            return
        hit = self._context.shape_at(point)
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
        self._cursor = CursorType.MOVE
        self._moving = queries.selected_shapes(self._context.state)

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
        self._context.repaint()

    def release(self, point: Point, mods: Mods) -> None:
        if self._mode is None:
            return
        self.move(point, mods)
        mode, matrix = self._mode, self._matrix
        chosen = self._band_base | self._band_hits() if mode is _Mode.BAND else set()
        self.cancel()
        session = self._context.session
        match mode:
            case _Mode.BAND:
                selection.set_selection(session, chosen)
            case _Mode.MOVE:
                if matrix[4] or matrix[5]:
                    selection.move_selection(session, matrix[4], matrix[5])
            case _Mode.SCALE | _Mode.ROTATE:
                transform.transform_selection(session, matrix)
        self._context.repaint()

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
        handle = handle_at(frame, point, self._context.zoom) if frame is not None else None
        if handle is not None:
            return CursorType.ROTATE if handle.is_rotate else resize_cursor_type(handle_direction(frame, handle))
        return CursorType.MOVE if self._context.shape_at(point) is not None else CursorType.ARROW

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
        self.hint = f"Rotate {result:.1f}°"
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
        return hit_test.shapes_in_rect(self._context.state.document, self._context.cache, self._band())
