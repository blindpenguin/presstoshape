"""The tools in display order, and the toolbox that holds one instance of each for a canvas."""

from dataclasses import dataclass

from presstoshape.i18n import N_
from presstoshape.models.app_state import Tool
from presstoshape.tools.base import BaseTool, ToolContext
from presstoshape.tools.eyedropper import EyedropperTool
from presstoshape.tools.node import NodeTool
from presstoshape.tools.pen import PenTool
from presstoshape.tools.pencil import PencilTool
from presstoshape.tools.select import SelectTool
from presstoshape.tools.shapes import EllipseTool, RectangleTool
from presstoshape.tools.text import TextTool


@dataclass(frozen=True)
class ToolEntry:
    tool: Tool
    # Stable id for the keymap and menu layouts ("tool.select").
    id: str
    # Menu text with mnemonic.
    label: str
    factory: type[BaseTool]


TOOLS = (
    ToolEntry(Tool.SELECT, "tool.select", N_("&Select"), SelectTool),
    ToolEntry(Tool.NODE, "tool.node", N_("&Node"), NodeTool),
    ToolEntry(Tool.PEN, "tool.pen", N_("&Pen"), PenTool),
    ToolEntry(Tool.PENCIL, "tool.pencil", N_("Penc&il"), PencilTool),
    ToolEntry(Tool.RECTANGLE, "tool.rectangle", N_("&Rectangle"), RectangleTool),
    ToolEntry(Tool.ELLIPSE, "tool.ellipse", N_("&Ellipse"), EllipseTool),
    ToolEntry(Tool.TEXT, "tool.text", N_("&Text"), TextTool),
    ToolEntry(Tool.EYEDROPPER, "tool.eyedropper", N_("E&yedropper"), EyedropperTool),
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
            # Switched first: a tool that commits on leaving notifies, and the refresh switches here again.
            previous = self.active
            self._active_type = tool
            previous.leave()
