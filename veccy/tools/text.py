"""Text tool: click to place text typed into a prompt."""

from veccy.editing.operations import shapes
from veccy.geometry.boxes import Point
from veccy.tools.base import BaseTool, CursorType, Mods


class TextTool(BaseTool):
    cursor = CursorType.IBEAM

    def press(self, point: Point, mods: Mods) -> None:
        text = self._context.ask_text()
        if text is not None:
            shapes.add_text(self._context.session, point, text)
