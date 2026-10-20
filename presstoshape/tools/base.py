"""What every tool shares: modifiers, cursor types, the tool context and BaseTool. Qt-free, so tools stay testable."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

from presstoshape.editing import containers, queries
from presstoshape.editing.operations import edit_mode, selection
from presstoshape.editing.session import Session
from presstoshape.geometry.boxes import Point
from presstoshape.models.app_state import AppState
from presstoshape.render import hit_test
from presstoshape.render.overlay import Overlay
from presstoshape.render.paths import PathCache

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
    DUPLICATE = auto()


def resize_cursor_type(angle_deg: float) -> CursorType:
    """Nearest of the four resize cursors for a handle pointing at `angle_deg` on screen (y down)."""
    octant = round((angle_deg % 180) / 45) % 4
    return (CursorType.RESIZE_H, CursorType.RESIZE_FDIAG, CursorType.RESIZE_V, CursorType.RESIZE_BDIAG)[octant]


@dataclass
class ToolContext:
    """What every tool needs: the session, the shared geometry cache, view hooks and the current zoom."""

    session: Session
    cache: PathCache
    repaint: Callable[[], None]
    # The text prompt is a dialog, so the view provides it.
    ask_text: Callable[[], str | None] = lambda: None
    # Doc units per screen px.
    pixel_size: float = 1.0

    @property
    def state(self) -> AppState:
        return self.session.state

    @property
    def zoom(self) -> float:
        return 1.0 / self.pixel_size

    def shape_at(self, point: Point) -> int | None:
        """Top-most shape under `point`, with a few screen px of tolerance for thin strokes."""
        shapes = queries.pickable_shapes(self.state)
        return hit_test.shape_at(shapes, self.cache, point, HIT_TOLERANCE_PX * self.pixel_size)


class BaseTool:
    """Defaults every tool inherits: no gesture, crosshair cursor, Esc cancels or clears the selection."""

    cursor = CursorType.CROSS
    hint: str | None = None

    def __init__(self, context: ToolContext) -> None:
        self._context = context

    @property
    def active(self) -> bool:
        return False

    @property
    def overlay(self) -> Overlay:
        return Overlay(frozenset(self._context.state.selection))

    def press(self, point: Point, mods: Mods) -> None:
        pass

    def move(self, point: Point, mods: Mods) -> None:
        pass

    def release(self, point: Point, mods: Mods) -> None:
        pass

    def double_click(self, point: Point, mods: Mods) -> None:
        # Qt sends the second press of a double-click as a double-click event only.
        self.press(point, mods)

    def hover(self, point: Point) -> CursorType:
        return self.cursor

    def key(self, name: str) -> bool:
        """Tool-specific keys ("enter"); True when handled."""
        return False

    def escape(self) -> None:
        """Cancels a gesture, else clears the selection, else leaves one level of Composite edit mode."""
        state = self._context.state
        if self.active:
            self.cancel()
            self._context.repaint()
        elif state.selection or not containers.editing(state):
            selection.set_selection(self._context.session, set())
        else:
            edit_mode.leave(self._context.session)

    def cancel(self) -> None:
        pass
