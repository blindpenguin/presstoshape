"""Types shared by the per-tool gesture modules. Qt-free, so gestures and cursor choice stay unit-testable."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

from veccy.controllers.app_controller import AppController
from veccy.models.app_state import AppState
from veccy.render.paths import PathCache

HIT_TOLERANCE_PX = 3.0


@dataclass(frozen=True)
class Mods:
    shift: bool = False
    ctrl: bool = False
    alt: bool = False


class CursorType(Enum):
    """What a press would do here; CanvasView maps these to Qt cursors."""

    ARROW = auto()
    MOVE = auto()
    RESIZE_H = auto()
    RESIZE_V = auto()
    # Diagonals as on screen (y down): FDIAG runs top-left to bottom-right, BDIAG bottom-left to top-right.
    RESIZE_FDIAG = auto()
    RESIZE_BDIAG = auto()
    ROTATE = auto()
    CROSS = auto()
    IBEAM = auto()
    NODE = auto()
    NODE_INSERT = auto()


def resize_cursor_type(angle_deg: float) -> CursorType:
    """Nearest of the four resize cursors for a handle pointing at `angle_deg` on screen (y down)."""
    octant = round((angle_deg % 180) / 45) % 4
    return (CursorType.RESIZE_H, CursorType.RESIZE_FDIAG, CursorType.RESIZE_V, CursorType.RESIZE_BDIAG)[octant]


@dataclass
class GestureContext:
    """What every gesture needs: the controller, shared geometry cache, a repaint hook and the current view."""

    controller: AppController
    cache: PathCache
    repaint: Callable[[], None]
    state: AppState | None = None
    # Doc units per screen px.
    pixel_size: float = 1.0

    @property
    def zoom(self) -> float:
        return 1.0 / self.pixel_size
