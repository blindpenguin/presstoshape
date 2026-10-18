"""Per-tool canvas gestures: holds transient drag/preview state and commits finished gestures to the controller.

Points arrive in doc coordinates; CanvasView owns Qt events, panning and zooming.
"""

from collections.abc import Callable

from veccy.controllers import geometry
from veccy.controllers.app_controller import AppController
from veccy.controllers.geometry import Point
from veccy.models.app_state import AppState, Tool
from veccy.models.shapes import Segment, Shape, Style
from veccy.render import hit_test
from veccy.render.overlay import Overlay
from veccy.render.paths import PathCache

_HIT_TOLERANCE_PX = 3.0
_PEN_DEDUPE_PX = 3.0


class CanvasGestures:
    def __init__(
        self,
        controller: AppController,
        cache: PathCache,
        repaint: Callable[[], None],
        ask_text: Callable[[], str | None],
    ) -> None:
        self._controller = controller
        self._cache = cache
        self._repaint = repaint
        self._ask_text = ask_text
        self._state: AppState | None = None
        self._tool = Tool.SELECT
        # Doc units per screen px.
        self.pixel_size = 1.0

        self._drag_start: Point | None = None
        self._drag_end: Point | None = None
        self._moving: list[Shape] = []
        self._band_base: set[int] | None = None
        self._preview: tuple[tuple[Segment, ...], Style] | None = None
        self._pen_points: list[Point] = []

    def set_state(self, state: AppState) -> None:
        self._state = state

    def set_tool(self, tool: Tool) -> None:
        self.cancel()
        self._tool = tool

    @property
    def active(self) -> bool:
        return self._drag_start is not None or self._preview is not None

    @property
    def overlay(self) -> Overlay:
        selection = set(self._state.selection) if self._state else set()
        rubber_band = None
        moving: frozenset[int] = frozenset()
        offset = (0.0, 0.0)
        if self._band_base is not None and self._drag_start and self._drag_end:
            rubber_band = self._box(self._drag_start, self._drag_end)
            selection = self._band_base | self._band_hits()
        elif self._moving and self._drag_start and self._drag_end:
            moving = frozenset(s.id for s in self._moving)
            offset = self._delta()
        return Overlay(frozenset(selection), rubber_band, self._preview, moving, offset)

    # --- events ---------------------------------------------------------------

    def press(self, point: Point, shift: bool, ctrl: bool) -> None:
        match self._tool:
            case Tool.SELECT:
                self._press_select(point, ctrl)
            case Tool.RECTANGLE | Tool.ELLIPSE:
                self._drag_start = self._drag_end = point
                self._preview = (self._box_segments(point, point, shift), self._tool_style())
            case Tool.PEN:
                self._pen_points.append(point)
                self._preview = (geometry.smooth_segments(self._dedupe(self._pen_points)), self._tool_style())
            case Tool.TEXT:
                text = self._ask_text()
                if text is not None:
                    self._controller.add_text(point, text)
        self._repaint()

    def move(self, point: Point, shift: bool) -> None:
        if self._drag_start is not None:
            self._drag_end = point
            if self._tool in (Tool.RECTANGLE, Tool.ELLIPSE):
                self._preview = (self._box_segments(self._drag_start, point, shift), self._tool_style())
            self._repaint()
        elif self._tool is Tool.PEN and self._pen_points:
            points = self._dedupe([*self._pen_points, point])
            self._preview = (geometry.smooth_segments(points), self._tool_style())
            self._repaint()

    def release(self, point: Point, shift: bool) -> None:
        if self._drag_start is None:
            return
        self._drag_end = point
        start = self._drag_start
        if self._tool is Tool.SELECT:
            if self._band_base is not None:
                selection = self._band_base | self._band_hits()
                self.cancel()
                self._controller.set_selection(selection)
            else:
                dx, dy = self._delta()
                self.cancel()
                if dx or dy:
                    self._controller.move_selection(dx, dy)
        elif self._tool is Tool.RECTANGLE:
            self.cancel()
            self._controller.add_rectangle(start, point, shift)
        elif self._tool is Tool.ELLIPSE:
            self.cancel()
            self._controller.add_ellipse(start, point, shift)
        self._repaint()

    def double_click(self) -> None:
        if self._tool is Tool.PEN:
            self.finish_pen()

    def escape(self) -> None:
        if self.active:
            self.cancel()
            self._repaint()
        else:
            self._controller.set_selection(set())

    def finish_pen(self) -> None:
        points = self._dedupe(self._pen_points)
        self.cancel()
        self._controller.add_path(points)

    def cancel(self) -> None:
        self._drag_start = self._drag_end = None
        self._moving = []
        self._band_base = None
        self._preview = None
        self._pen_points = []

    # --- helpers --------------------------------------------------------------

    def _press_select(self, point: Point, ctrl: bool) -> None:
        state = self._state
        if state is None:
            return
        hit = hit_test.shape_at(state.document, self._cache, point, _HIT_TOLERANCE_PX * self.pixel_size)
        if hit is None:
            self._drag_start = self._drag_end = point
            self._band_base = set(state.selection) if ctrl else set()
            return
        if ctrl:
            self._controller.set_selection(state.selection ^ {hit})
            return
        if hit not in state.selection:
            self._controller.set_selection({hit})
        self._drag_start = self._drag_end = point
        self._moving = self._controller.selected_shapes()

    def _band_hits(self) -> set[int]:
        if self._state is None or self._drag_start is None or self._drag_end is None:
            return set()
        return hit_test.shapes_in_rect(self._state.document, self._cache, self._box(self._drag_start, self._drag_end))

    def _delta(self) -> Point:
        assert self._drag_start is not None and self._drag_end is not None
        return self._drag_end[0] - self._drag_start[0], self._drag_end[1] - self._drag_start[1]

    def _tool_style(self) -> Style:
        return self._state.tool_styles.get(self._tool, Style()) if self._state else Style()

    def _box_segments(self, start: Point, end: Point, square: bool) -> tuple[Segment, ...]:
        x, y, w, h = geometry.box_from_drag(start, end, square)
        if self._tool is Tool.RECTANGLE:
            return geometry.rect_segments(x, y, w, h)
        return geometry.ellipse_segments(x + w / 2, y + h / 2, w / 2, h / 2)

    def _dedupe(self, points: list[Point]) -> list[Point]:
        # Double-click also delivers a press, so near-duplicate points (in screen px) are dropped.
        threshold = _PEN_DEDUPE_PX * self.pixel_size
        out: list[Point] = []
        for p in points:
            if not out or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > threshold:
                out.append(p)
        return out

    @staticmethod
    def _box(a: Point, b: Point) -> tuple[float, float, float, float]:
        return min(a[0], b[0]), min(a[1], b[1]), abs(b[0] - a[0]), abs(b[1] - a[1])
