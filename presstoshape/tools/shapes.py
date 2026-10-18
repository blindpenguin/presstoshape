"""Rectangle and ellipse tools: drag a box, Shift for a square or circle."""

from presstoshape.editing.operations import shapes
from presstoshape.geometry.boxes import Point, box_from_drag
from presstoshape.geometry.segments import ellipse_segments, rect_segments
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import Segment
from presstoshape.render.overlay import Overlay
from presstoshape.tools.base import BaseTool, Mods, ToolContext


class _BoxTool(BaseTool):
    tool_type: Tool

    def __init__(self, context: ToolContext) -> None:
        super().__init__(context)
        self._start: Point | None = None
        self._end: Point = (0.0, 0.0)
        self._square = False

    @property
    def active(self) -> bool:
        return self._start is not None

    @property
    def overlay(self) -> Overlay:
        state = self._context.state
        preview = None
        if self._start is not None:
            preview = (self._segments(self._start, self._end, self._square), state.tool_styles[self.tool_type])
        return Overlay(frozenset(state.selection), preview=preview)

    def press(self, point: Point, mods: Mods) -> None:
        self._start = self._end = point
        self._square = mods.shift

    def move(self, point: Point, mods: Mods) -> None:
        if self._start is None:
            return
        self._end, self._square = point, mods.shift
        self._context.repaint()

    def release(self, point: Point, mods: Mods) -> None:
        if self._start is None:
            return
        start = self._start
        self.cancel()
        self._commit(start, point, mods.shift)

    def cancel(self) -> None:
        self._start = None

    def _segments(self, start: Point, end: Point, square: bool) -> tuple[Segment, ...]:
        raise NotImplementedError

    def _commit(self, start: Point, end: Point, square: bool) -> None:
        raise NotImplementedError


class RectangleTool(_BoxTool):
    tool_type = Tool.RECTANGLE

    def _segments(self, start: Point, end: Point, square: bool) -> tuple[Segment, ...]:
        return rect_segments(*box_from_drag(start, end, square))

    def _commit(self, start: Point, end: Point, square: bool) -> None:
        shapes.add_rectangle(self._context.session, start, end, square)


class EllipseTool(_BoxTool):
    tool_type = Tool.ELLIPSE

    def _segments(self, start: Point, end: Point, square: bool) -> tuple[Segment, ...]:
        x, y, w, h = box_from_drag(start, end, square)
        return ellipse_segments(x + w / 2, y + h / 2, w / 2, h / 2)

    def _commit(self, start: Point, end: Point, square: bool) -> None:
        shapes.add_ellipse(self._context.session, start, end, square)
