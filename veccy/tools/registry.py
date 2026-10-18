"""The tools in display order, and the toolbox that holds one instance of each for a canvas."""

from dataclasses import dataclass

from veccy.models.app_state import Tool
from veccy.tools.base import BaseTool, ToolContext
from veccy.tools.node import NodeTool
from veccy.tools.pen import PenTool
from veccy.tools.select import SelectTool
from veccy.tools.shapes import EllipseTool, RectangleTool
from veccy.tools.text import TextTool


@dataclass(frozen=True)
class ToolEntry:
    tool: Tool
    # Stable id for the keymap and menu layouts ("tool.select").
    id: str
    # Menu text with mnemonic.
    label: str
    factory: type[BaseTool]


TOOLS = (
    ToolEntry(Tool.SELECT, "tool.select", "&Select", SelectTool),
    ToolEntry(Tool.NODE, "tool.node", "&Node", NodeTool),
    ToolEntry(Tool.PEN, "tool.pen", "&Pen", PenTool),
    ToolEntry(Tool.RECTANGLE, "tool.rectangle", "&Rectangle", RectangleTool),
    ToolEntry(Tool.ELLIPSE, "tool.ellipse", "&Ellipse", EllipseTool),
    ToolEntry(Tool.TEXT, "tool.text", "&Text", TextTool),
)


class Toolbox:
    """One instance per tool sharing a context; switching tools cancels the old tool's gesture."""

    def __init__(self, context: ToolContext) -> None:
        self.context = context
        self._tools = {entry.tool: entry.factory(context) for entry in TOOLS}
        self._active_type = Tool.SELECT

    @property
    def active(self) -> BaseTool:
        return self._tools[self._active_type]

    def switch(self, tool: Tool) -> None:
        if tool is not self._active_type:
            self.active.cancel()
            self._active_type = tool
