"""Pen tool: click for corner nodes joined by straight lines, click + drag for smooth nodes with handles.

Clicking the first node closes the path; double-click or Enter finishes it open, Backspace removes the last
node, Esc discards it. Shift keeps lines and handles at 45° steps, Alt while dragging breaks the handles.
"""

import math

from presstoshape.editing.operations import shapes
from presstoshape.geometry.boxes import Point, constrain_angle
from presstoshape.geometry.pen_paths import PenNode, mirrored, pen_segments, with_drag
from presstoshape.models.app_state import Tool
from presstoshape.render.overlay import NodeOverlay, Overlay
from presstoshape.tools.base import BaseTool, CursorType, Mods, ToolContext
from presstoshape.tools.snapper import Snapper

# Screen px: a press that moves less than this is a click; the pointer this close to a node is on it.
_DRAG_PX = 3.0
_NODE_PX = 5.0


class PenTool(BaseTool):
    def __init__(self, context: ToolContext) -> None:
        super().__init__(context)
        self._nodes: list[PenNode] = []
        # Where the button went down, while it is down.
        self._pressed: Point | None = None
        self._dragging = False
        self._closing = False
        self._pointer: Point | None = None
        self._snapper: Snapper | None = None

    @property
    def active(self) -> bool:
        return bool(self._nodes)

    @property
    def overlay(self) -> Overlay:
        state = self._context.state
        selection = frozenset(state.selection)
        if not self._nodes:
            return Overlay(selection)
        on_first = self._closing or (self._pressed is None and self._over_first(self._pointer))
        if on_first:
            preview = pen_segments(self._nodes, closed=True)
        elif self._pressed is not None or self._pointer is None:
            preview = pen_segments(self._nodes)
        else:
            preview = pen_segments([*self._nodes, PenNode(self._pointer)])
        segments = pen_segments(self._nodes)
        node = self._nodes[0] if self._closing else self._nodes[-1]
        handles = tuple((node.point, handle) for handle in (node.handle_in, node.handle_out) if handle is not None)
        nodes = NodeOverlay(segments, frozenset({0}) if on_first else frozenset(), handles=handles)
        snap = self._snapper.hits if self._snapper is not None and not self._dragging else ()
        return Overlay(
            selection,
            preview=(preview, state.tool_styles[Tool.PEN]) if len(preview) > 1 else None,
            nodes=(nodes,),
            snap=snap,
        )

    def press(self, point: Point, mods: Mods) -> None:
        # Targets stay put while a path is being clicked together, so they are collected once.
        if self._snapper is None:
            self._snapper = self._context.snapper()
        self._dragging = False
        self._closing = False
        self._pressed = None
        if self._over_first(point):
            self._closing = True
            self._pressed = point
            return
        if self._nodes and self._near(point, self._nodes[-1].point):
            return
        position = self._position(point, mods)
        self._nodes.append(PenNode(position))
        self._snapper = self._snapper.with_points([position])
        self._pressed = position
        self._pointer = None

    def move(self, point: Point, mods: Mods) -> None:
        if not self._nodes:
            return
        if self._pressed is None:
            self._pointer = point if self._over_first(point) else self._position(point, mods)
        else:
            if not self._dragging and self._distance_px(point, self._pressed) < _DRAG_PX:
                return
            self._dragging = True
            self._drag_handles(point, mods)
        self._context.repaint()

    def release(self, point: Point, mods: Mods) -> None:
        if self._pressed is None:
            return
        if self._closing:
            self._commit(closed=True)
            return
        self._pressed = None
        self._dragging = False
        self._pointer = point

    def double_click(self, point: Point, mods: Mods) -> None:
        # The first click of the double-click already placed the node (or closed the path).
        if self._nodes:
            self._commit(closed=False)

    def hover(self, point: Point) -> CursorType:
        if not self._nodes:
            return CursorType.CROSS
        return CursorType.PEN_CLOSE if self._over_first(point) else CursorType.PEN_ADD

    def key(self, name: str) -> bool:
        if not self._nodes or self._pressed is not None:
            return False
        if name == "enter":
            self._commit(closed=False)
            return True
        if name == "backspace":
            self._nodes.pop()
            if not self._nodes:
                self.cancel()
            return True
        return False

    def leave(self) -> None:
        self._commit(closed=False)

    def cancel(self) -> None:
        self._nodes = []
        self._pressed = None
        self._dragging = False
        self._closing = False
        self._pointer = None
        self._snapper = None

    def _commit(self, closed: bool) -> None:
        nodes = self._nodes
        self.cancel()
        if len(nodes) >= 2:
            shapes.add_drawn_path(self._context.session, pen_segments(nodes, closed), Tool.PEN)

    def _drag_handles(self, point: Point, mods: Mods) -> None:
        index = 0 if self._closing else len(self._nodes) - 1
        node = self._nodes[index]
        target = constrain_angle(node.point, point) if mods.shift else point
        if self._closing and mods.alt:
            # The first segment keeps its handle; only the closing segment's end changes.
            self._nodes[index] = PenNode(node.point, mirrored(node.point, target), node.handle_out)
        else:
            self._nodes[index] = with_drag(node, target, mirror=not mods.alt)

    def _position(self, point: Point, mods: Mods) -> Point:
        assert self._snapper is not None
        if mods.shift and self._nodes:
            self._snapper.hits = ()
            return constrain_angle(self._nodes[-1].point, point)
        return self._snapper.point(point, ignore=mods.ctrl)

    def _over_first(self, point: Point | None) -> bool:
        return point is not None and len(self._nodes) >= 2 and self._near(point, self._nodes[0].point)

    def _near(self, a: Point, b: Point) -> bool:
        return self._distance_px(a, b) <= _NODE_PX

    def _distance_px(self, a: Point, b: Point) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1]) / self._context.pixel_size
