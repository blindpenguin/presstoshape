"""Node tool: select and drag path nodes and bezier controls, insert nodes by double-click, box-select nodes."""

from dataclasses import replace
from enum import Enum, auto

from veccy.controllers import nodes
from veccy.controllers.geometry import Point
from veccy.models.shapes import PathShape
from veccy.render import hit_test
from veccy.render.handles import node_at
from veccy.render.overlay import NodeOverlay, Overlay, Rect
from veccy.views.gesture_types import HIT_TOLERANCE_PX, CursorType, GestureContext, Mods

# How close (screen px) a double-click must be to a segment to insert a node there.
_SEGMENT_PX = 5.0

_NON_PATH_HINT = "Node tool edits paths. Use Path → Object to Path (Ctrl+Shift+C) first."


class _Mode(Enum):
    NODES = auto()
    CONTROL = auto()
    BAND = auto()


class NodeGesture:
    def __init__(self, ctx: GestureContext) -> None:
        self._ctx = ctx
        self._mode: _Mode | None = None
        self._start: Point = (0.0, 0.0)
        self._end: Point = (0.0, 0.0)
        self._path: PathShape | None = None
        self._indices: set[int] = set()
        self._control: tuple[int, int] | None = None
        self._live: PathShape | None = None
        self._band_base: set[tuple[int, int]] = set()
        self._cursor = CursorType.ARROW

    @property
    def active(self) -> bool:
        return self._mode is not None

    @property
    def hint(self) -> str | None:
        state = self._ctx.state
        if state is None or self._mode is not None:
            return None
        selected = self._ctx.controller.selected_shapes()
        return _NON_PATH_HINT if any(not isinstance(s, PathShape) for s in selected) else None

    def _edited(self) -> list[PathShape]:
        return [s for s in self._ctx.controller.selected_shapes() if isinstance(s, PathShape)]

    def _selected_nodes(self, shape_id: int) -> set[int]:
        state = self._ctx.state
        return {i for sid, i in state.node_selection if sid == shape_id} if state else set()

    @property
    def overlay(self) -> Overlay:
        state = self._ctx.state
        selection = frozenset(state.selection) if state else frozenset()
        overlays = []
        for path in self._edited():
            shown = self._live if self._live is not None and self._live.id == path.id else path
            selected = self._selected_nodes(path.id)
            controls = nodes.visible_controls(shown.segments, selected)
            overlays.append(NodeOverlay(shown.segments, frozenset(selected), frozenset(controls)))
        moving = frozenset({self._live.id}) if self._live is not None else frozenset()
        live = (self._live,) if self._live is not None else ()
        band = self._band() if self._mode is _Mode.BAND else None
        return Overlay(selection, rubber_band=band, moving=moving, live=live, nodes=tuple(overlays))

    # --- events ---------------------------------------------------------------

    def press(self, point: Point, mods: Mods) -> None:
        state = self._ctx.state
        if state is None:
            return
        controller = self._ctx.controller
        self._start = self._end = point
        self._cursor = self.hover(point)
        for path in reversed(self._edited()):
            controls = nodes.visible_controls(path.segments, self._selected_nodes(path.id))
            pick = node_at(path.segments, point, self._ctx.zoom, controls)
            if pick is None:
                continue
            pick_type, target = pick
            if pick_type == "control":
                self._mode, self._path, self._control = _Mode.CONTROL, path, target
                return
            ref = (path.id, target)
            if mods.shift:
                controller.set_node_selection(set(state.node_selection) ^ {ref})
                return
            if ref not in state.node_selection:
                controller.set_node_selection({ref})
            self._mode, self._path = _Mode.NODES, path
            self._indices = self._selected_nodes(path.id)
            return
        if self._segment_at(point) is not None:
            return
        hit = hit_test.shape_at(state.document, self._ctx.cache, point, HIT_TOLERANCE_PX * self._ctx.pixel_size)
        if hit is not None:
            if hit not in state.selection:
                controller.set_selection({hit})
            return
        self._mode = _Mode.BAND
        self._band_base = set(state.node_selection) if mods.shift else set()

    def move(self, point: Point, mods: Mods) -> None:
        if self._mode is None:
            return
        self._end = point
        path = self._path
        if self._mode is _Mode.NODES and path is not None:
            dx, dy = point[0] - self._start[0], point[1] - self._start[1]
            self._live = replace(path, segments=nodes.move_nodes(path.segments, self._indices, dx, dy))
        elif self._mode is _Mode.CONTROL and path is not None and self._control is not None:
            segments = nodes.move_control(path.segments, self._control, point, keep_smooth=not mods.alt)
            self._live = replace(path, segments=segments)
        self._ctx.repaint()

    def release(self, point: Point, mods: Mods) -> None:
        if self._mode is None:
            return
        self.move(point, mods)
        mode, path, control, indices = self._mode, self._path, self._control, self._indices
        band_refs = self._band_base | self._band_hits() if mode is _Mode.BAND else set()
        clicked_empty = mode is _Mode.BAND and point == self._start
        self.cancel()
        controller = self._ctx.controller
        state = self._ctx.state
        if mode is _Mode.NODES and path is not None:
            dx, dy = point[0] - self._start[0], point[1] - self._start[1]
            controller.move_nodes(path.id, indices, dx, dy)
        elif mode is _Mode.CONTROL and path is not None and control is not None:
            if point != self._start:
                controller.move_control(path.id, control, point, keep_smooth=not mods.alt)
        elif clicked_empty and not band_refs and state is not None and not state.node_selection:
            controller.set_selection(set())
        else:
            controller.set_node_selection(band_refs)
        self._ctx.repaint()

    def double_click(self, point: Point) -> None:
        hit = self._segment_at(point)
        if hit is not None:
            path, index, t = hit
            self._ctx.controller.insert_node(path.id, index, t)

    def escape(self) -> bool:
        """Cancels a drag, else clears the node selection; False when there was nothing to clear."""
        state = self._ctx.state
        if self._mode is not None:
            self.cancel()
            self._ctx.repaint()
            return True
        if state is not None and state.node_selection:
            self._ctx.controller.set_node_selection(set())
            return True
        return False

    def cancel(self) -> None:
        self._mode = None
        self._path = self._control = self._live = None
        self._indices = set()
        self._band_base = set()

    def hover(self, point: Point) -> CursorType:
        if self._mode is not None:
            return self._cursor
        for path in self._edited():
            controls = nodes.visible_controls(path.segments, self._selected_nodes(path.id))
            if node_at(path.segments, point, self._ctx.zoom, controls) is not None:
                return CursorType.NODE
        return CursorType.NODE_INSERT if self._segment_at(point) is not None else CursorType.ARROW

    # --- helpers --------------------------------------------------------------

    def _segment_at(self, point: Point) -> tuple[PathShape, int, float] | None:
        reach = _SEGMENT_PX * self._ctx.pixel_size
        best: tuple[float, PathShape, int, float] | None = None
        for path in self._edited():
            b = self._ctx.cache.bounds(path).makeOutset(reach, reach)
            if not b.contains(*point):
                continue
            hit = nodes.nearest_on_path(path.segments, point)
            if hit is not None and hit[2] <= reach and (best is None or hit[2] < best[0]):
                best = (hit[2], path, hit[0], hit[1])
        return None if best is None else best[1:]

    def _band(self) -> Rect:
        (x0, y0), (x1, y1) = self._start, self._end
        return min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)

    def _band_hits(self) -> set[tuple[int, int]]:
        x, y, w, h = self._band()
        return {
            (path.id, info.index)
            for path in self._edited()
            for info in nodes.nodes(path.segments)
            if x <= info.point[0] <= x + w and y <= info.point[1] <= y + h
        }
