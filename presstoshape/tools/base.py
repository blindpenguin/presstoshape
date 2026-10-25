"""What every tool shares: modifiers, cursor types, the tool context and BaseTool. Qt-free, so tools stay testable."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum, auto

from presstoshape.editing import containers
from presstoshape.editing.operations import edit_mode, selection, transform
from presstoshape.editing.session import Session
from presstoshape.geometry import units
from presstoshape.geometry.boxes import Point, Rect
from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import PathShape
from presstoshape.render import hit_test
from presstoshape.render.overlay import Overlay
from presstoshape.render.paths import PathCache
from presstoshape.tools.snapper import Snapper

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
    # Dragging a horizontal guide moves it up and down; a vertical one left and right.
    GUIDE_HORIZONTAL = auto()
    GUIDE_VERTICAL = auto()
    # Pen: a click adds a node to the open path / closes it on its first node.
    PEN_ADD = auto()
    PEN_CLOSE = auto()


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
    # The document area the canvas shows (x, y, w, h), so snapping can ignore what's off-screen; None = all.
    visible_rect: Rect | None = None
    # Set by the canvas while the pointer is outside the canvas (over a ruler): a guide released there goes.
    pointer_off_canvas: bool = False
    # Opens the guide position dialog; a dialog, so the view provides it.
    edit_guide: Callable[[int], None] = lambda guide_id: None

    @property
    def state(self) -> AppState:
        return self.session.state

    @property
    def zoom(self) -> float:
        return 1.0 / self.pixel_size

    def snapper(
        self, exclude: Iterable[int] = (), own_path: tuple[PathShape, set[int]] | None = None, guides: bool = True
    ) -> Snapper:
        """Snap targets for a gesture starting now."""
        return Snapper.build(self.state, self.cache, self.pixel_size, self.visible_rect, exclude, own_path, guides)

    def shape_at(self, point: Point) -> int | None:
        """Top-most shape under `point`, with a few screen px of tolerance for thin strokes."""
        # Asked on every hover; hit_test passes over hidden and locked shapes itself.
        shapes = containers.active_shapes(self.state)
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

    def nudge(self, x: int, y: int, mods: Mods) -> bool:
        """Arrow key in direction (x, y): moves what this tool works on by one step (Shift: ten steps, Alt: one
        screen pixel). False when there is nothing to move, so the view can scroll instead."""
        if self.active:
            return True
        document = self._context.state.document
        step = self._context.pixel_size if mods.alt else units.nudge_px(document.unit, document.dpi)
        if mods.shift:
            step *= 10
        return self._nudge_by(x * step, y * step)

    def _nudge_by(self, dx: float, dy: float) -> bool:
        if not self._context.state.selection:
            return False
        transform.nudge(self._context.session, dx, dy)
        return True

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

    def leave(self) -> None:
        """Another tool was chosen; by default the running gesture is dropped."""
        self.cancel()
