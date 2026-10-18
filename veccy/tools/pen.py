"""Pen tool: click points of a smooth curve; double-click or Enter finishes, Esc cancels."""

from veccy.editing.operations import shapes
from veccy.geometry.boxes import Point
from veccy.geometry.segments import smooth_segments
from veccy.models.app_state import Tool
from veccy.render.overlay import Overlay
from veccy.tools.base import BaseTool, Mods, ToolContext

_DEDUPE_PX = 3.0


class PenTool(BaseTool):
    def __init__(self, context: ToolContext) -> None:
        super().__init__(context)
        self._points: list[Point] = []
        self._pointer: Point | None = None

    @property
    def active(self) -> bool:
        return bool(self._points)

    @property
    def overlay(self) -> Overlay:
        state = self._context.state
        preview = None
        if self._points:
            points = self._points + ([self._pointer] if self._pointer is not None else [])
            preview = (smooth_segments(self._dedupe(points)), state.tool_styles[Tool.PEN])
        return Overlay(frozenset(state.selection), preview=preview)

    def press(self, point: Point, mods: Mods) -> None:
        self._points.append(point)
        self._pointer = None

    def move(self, point: Point, mods: Mods) -> None:
        if self._points:
            self._pointer = point
            self._context.repaint()

    def double_click(self, point: Point, mods: Mods) -> None:
        self.finish()

    def key(self, name: str) -> bool:
        if name != "enter":
            return False
        self.finish()
        return True

    def finish(self) -> None:
        points = self._dedupe(self._points)
        self.cancel()
        shapes.add_path(self._context.session, points)

    def cancel(self) -> None:
        self._points = []
        self._pointer = None

    def _dedupe(self, points: list[Point]) -> list[Point]:
        # Double-click also delivers a press, so near-duplicate points (in screen px) are dropped.
        threshold = _DEDUPE_PX * self._context.pixel_size
        kept: list[Point] = []
        for point in points:
            if not kept or abs(point[0] - kept[-1][0]) + abs(point[1] - kept[-1][1]) > threshold:
                kept.append(point)
        return kept
