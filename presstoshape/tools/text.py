"""Text tool: click to place text typed into a prompt."""

from presstoshape.editing.operations import shapes
from presstoshape.geometry.boxes import Point
from presstoshape.tools.base import BaseTool, CursorType, Mods


class TextTool(BaseTool):
    cursor = CursorType.IBEAM

    def press(self, point: Point, mods: Mods) -> None:
        text = self._context.ask_text()
        if text is not None:
            shapes.add_text(self._context.session, point, text)
