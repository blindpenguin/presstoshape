from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Literal

from presstoshape.i18n import _
from presstoshape.models.shapes import PartMode, Shape, Style


class Tool(Enum):
    SELECT = auto()
    NODE = auto()
    PEN = auto()
    RECTANGLE = auto()
    ELLIPSE = auto()
    TEXT = auto()


@dataclass
class Layer:
    name: str
    visible: bool = True
    shapes: list[Shape] = field(default_factory=list)


# Units lengths are shown and entered in. Coordinates are always document pixels (1/dpi inch).
Unit = Literal["px", "mm", "cm", "in", "pt"]


def layer_name(number: int) -> str:
    """Default name of the `number`th layer, in the active language (names already in documents stay)."""
    return _("Layer {number}").format(number=number)


@dataclass
class Document:
    width: float = 600.0
    height: float = 400.0
    # Bottom-to-top paint order, same as SVG document order.
    layers: list[Layer] = field(default_factory=lambda: [Layer(layer_name(1))])
    next_id: int = 1
    # Shown/entered unit and resolution; width, height and all geometry stay in document pixels.
    unit: Unit = "px"
    dpi: float = 96.0


@dataclass
class ExportSettings:
    # Last PNG export scale, kept for the session only.
    scale: float = 1.0


def _default_tool_styles() -> dict[Tool, Style]:
    return {
        Tool.PEN: Style(fill=None),
        Tool.RECTANGLE: Style(),
        Tool.ELLIPSE: Style(),
        Tool.TEXT: Style(fill="#18181b", stroke=None),
    }


@dataclass(frozen=True)
class RecoveredFrom:
    """Where a document recovered after a crash came from; its first save asks for a file (Save As)."""

    # None for documents that were never saved.
    original_path: str | None
    # When the recovery snapshot was taken (seconds since the epoch).
    saved_at: float


@dataclass
class AppState:
    """Plain data, no Qt or app-logic imports. Owned by the Session, changed only by operations."""

    document: Document = field(default_factory=Document)
    active_tool: Tool = Tool.SELECT
    selected_layer_index: int = 0
    selection: set[int] = field(default_factory=set)
    # Node tool: selected path nodes as (shape id, segment index).
    node_selection: frozenset[tuple[int, int]] = frozenset()
    # Entered Composites, outer to inner; empty when no Composite is being edited. Not part of undo.
    edit_path: tuple[int, ...] = ()
    # Mode given to parts drawn while a Composite is being edited.
    new_part_mode: PartMode = "add"
    # Style each drawing tool gives new shapes, edited in the tool options panel.
    tool_styles: dict[Tool, Style] = field(default_factory=_default_tool_styles)
    font_size: float = 24.0
    export: ExportSettings = field(default_factory=ExportSettings)
    zoom_percent: int = 100
    status_message: str = field(default_factory=lambda: _("Ready"))
    file_path: str | None = None
    recovered: RecoveredFrom | None = None
    dirty: bool = False
    # View to show after opening a .p2s file (doc point at the viewport center); the window applies and clears it.
    restore_view_center: tuple[float, float] | None = None
    # Whether this session already said that SVG files don't keep view, tool settings and selection.
    svg_hint_shown: bool = False
