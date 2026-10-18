"""Per-tool canvas gestures: holds transient drag/preview state and commits finished gestures to the controller.

Points arrive in doc coordinates; CanvasView owns Qt events, panning and zooming. The Select tool lives in
SelectGesture; the drawing tools are short enough to stay here.
"""

from collections.abc import Callable

from veccy.controllers import geometry
from veccy.controllers.app_controller import AppController
from veccy.controllers.geometry import Point
from veccy.models.app_state import AppState, Tool
from veccy.models.shapes import Segment, Style
from veccy.render.overlay import Overlay
from veccy.render.paths import PathCache
from veccy.views.gesture_types import CursorType, GestureContext, Mods
from veccy.views.node_gesture import NodeGesture
from veccy.views.select_gesture import SelectGesture

_PEN_DEDUPE_PX = 3.0

_TOOL_CURSORS = {Tool.TEXT: CursorType.IBEAM}


class CanvasGestures:
    def __init__(
        self,
        controller: AppController,
        cache: PathCache,
        repaint: Callable[[], None],
        ask_text: Callable[[], str | None],
    ) -> None:
        self._ctx = GestureContext(controller, cache, repaint)
        self._controller = controller
        self._repaint = repaint
        self._ask_text = ask_text
        self._tool = Tool.SELECT
        self._select = SelectGesture(self._ctx)
        self._node = NodeGesture(self._ctx)

        self._drag_start: Point | None = None
        self._preview: tuple[tuple[Segment, ...], Style] | None = None
        self._pen_points: list[Point] = []

    @property
    def pixel_size(self) -> float:
        """Doc units per screen px."""
        return self._ctx.pixel_size

    @pixel_size.setter
    def pixel_size(self, value: float) -> None:
        self._ctx.pixel_size = value

    def set_state(self, state: AppState) -> None:
        self._ctx.state = state

    def set_tool(self, tool: Tool) -> None:
        self.cancel()
        self._tool = tool

    @property
    def active(self) -> bool:
        return self._select.active or self._node.active or self._drag_start is not None or self._preview is not None

    @property
    def overlay(self) -> Overlay:
        if self._tool is Tool.SELECT:
            return self._select.overlay
        if self._tool is Tool.NODE:
            return self._node.overlay
        selection = frozenset(self._ctx.state.selection) if self._ctx.state else frozenset()
        return Overlay(selection, preview=self._preview)

    @property
    def hint(self) -> str | None:
        """Transient status text for the gesture in progress (e.g. rotation angle)."""
        if self._tool is Tool.SELECT:
            return self._select.hint
        return self._node.hint if self._tool is Tool.NODE else None

    def hover(self, point: Point) -> CursorType:
        if self._tool is Tool.SELECT:
            return self._select.hover(point)
        if self._tool is Tool.NODE:
            return self._node.hover(point)
        return _TOOL_CURSORS.get(self._tool, CursorType.CROSS)

    # --- events ---------------------------------------------------------------

    def press(self, point: Point, mods: Mods) -> None:
        match self._tool:
            case Tool.SELECT:
                self._select.press(point, mods)
            case Tool.NODE:
                self._node.press(point, mods)
            case Tool.RECTANGLE | Tool.ELLIPSE:
                self._drag_start = point
                self._preview = (self._box_segments(point, point, mods.shift), self._tool_style())
            case Tool.PEN:
                self._pen_points.append(point)
                self._preview = (geometry.smooth_segments(self._dedupe(self._pen_points)), self._tool_style())
            case Tool.TEXT:
                text = self._ask_text()
                if text is not None:
                    self._controller.add_text(point, text)
        self._repaint()

    def move(self, point: Point, mods: Mods) -> None:
        if self._tool is Tool.SELECT:
            self._select.move(point, mods)
        elif self._tool is Tool.NODE:
            self._node.move(point, mods)
        elif self._drag_start is not None:
            self._preview = (self._box_segments(self._drag_start, point, mods.shift), self._tool_style())
            self._repaint()
        elif self._tool is Tool.PEN and self._pen_points:
            points = self._dedupe([*self._pen_points, point])
            self._preview = (geometry.smooth_segments(points), self._tool_style())
            self._repaint()

    def release(self, point: Point, mods: Mods) -> None:
        if self._tool is Tool.SELECT:
            self._select.release(point, mods)
            return
        if self._tool is Tool.NODE:
            self._node.release(point, mods)
            return
        if self._drag_start is None:
            return
        start = self._drag_start
        self.cancel()
        if self._tool is Tool.RECTANGLE:
            self._controller.add_rectangle(start, point, mods.shift)
        elif self._tool is Tool.ELLIPSE:
            self._controller.add_ellipse(start, point, mods.shift)
        self._repaint()

    def double_click(self, point: Point, mods: Mods) -> None:
        if self._tool is Tool.PEN:
            self.finish_pen()
        elif self._tool is Tool.NODE:
            self._node.double_click(point)
        else:
            # Qt sends the second press of a double-click as a double-click event only.
            self.press(point, mods)

    def escape(self) -> None:
        if self._tool is Tool.NODE and self._node.escape():
            return
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
        self._select.cancel()
        self._node.cancel()
        self._drag_start = None
        self._preview = None
        self._pen_points = []

    # --- helpers --------------------------------------------------------------

    def _tool_style(self) -> Style:
        state = self._ctx.state
        return state.tool_styles.get(self._tool, Style()) if state else Style()

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
