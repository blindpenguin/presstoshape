from dataclasses import dataclass, field
from enum import Enum, auto

from veccy.models.shapes import Shape, Style


class Tool(Enum):
    SELECT = auto()
    PEN = auto()
    RECTANGLE = auto()
    ELLIPSE = auto()
    TEXT = auto()


@dataclass
class Layer:
    name: str
    visible: bool = True
    shapes: list[Shape] = field(default_factory=list)


@dataclass
class Document:
    width: float = 600.0
    height: float = 400.0
    # Bottom-to-top paint order, same as SVG document order.
    layers: list[Layer] = field(default_factory=lambda: [Layer("Layer 1")])
    next_id: int = 1


def _default_tool_styles() -> dict[Tool, Style]:
    return {
        Tool.PEN: Style(fill=None),
        Tool.RECTANGLE: Style(),
        Tool.ELLIPSE: Style(),
        Tool.TEXT: Style(fill="#18181b", stroke=None),
    }


@dataclass
class AppState:
    """Plain data, no Qt/view/controller imports. Owned by App, read by views, mutated only by controllers."""

    document: Document = field(default_factory=Document)
    active_tool: Tool = Tool.SELECT
    selected_layer_index: int = 0
    selection: set[int] = field(default_factory=set)
    # Style each drawing tool gives new shapes, edited in the tool options panel.
    tool_styles: dict[Tool, Style] = field(default_factory=_default_tool_styles)
    font_size: float = 24.0
    zoom_percent: int = 100
    status_message: str = "Ready"
    file_path: str | None = None
    dirty: bool = False
