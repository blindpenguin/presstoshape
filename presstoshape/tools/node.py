"""Node tool: select and drag path nodes and bezier controls, insert nodes by double-click, box-select nodes."""

from dataclasses import replace
from enum import Enum, auto

from presstoshape.editing import queries
from presstoshape.editing.operations import node_editing, selection
from presstoshape.geometry import nodes
from presstoshape.geometry.boxes import Point, Rect, rect_from_points
from presstoshape.i18n import N_, _
from presstoshape.models.shapes import PathShape
from presstoshape.render.handles import node_at
from presstoshape.render.overlay import NodeOverlay, Overlay
from presstoshape.tools.base import BaseTool, CursorType, Mods, ToolContext
from presstoshape.tools.snapper import Snapper

_NON_PATH_HINT = N_("Node tool edits paths. Use Path → Object to Path (Ctrl+Shift+C) first.")
# How close (screen px) a double-click must be to a segment to insert a node there.
_SEGMENT_PX = 5.0


class _Mode(Enum):
    NODES = auto()
    CONTROL = auto()
    BAND = auto()


class NodeTool(BaseTool):
    def __init__(self, context: ToolContext) -> None:
        super().__init__(context)
        self._mode: _Mode | None = None
        self._start: Point = (0.0, 0.0)
        self._end: Point = (0.0, 0.0)
        self._path: PathShape | None = None
        self._indices: set[int] = set()
        self._control: tuple[int, int] | None = None
        self._live: PathShape | None = None
        self._band_base: set[tuple[int, int]] = set()
        self._cursor = CursorType.ARROW
        self._snapper = Snapper.off()
        # Node drags: where the pressed node started, and how far the drag moves the nodes (after snapping).
        self._anchor: Point = (0.0, 0.0)
        self._delta: Point = (0.0, 0.0)

    def _nudge_by(self, dx: float, dy: float) -> bool:
        """Selected nodes move; without any, the selected paths do (as with the Select tool)."""
        if not self._context.state.node_selection:
            return super()._nudge_by(dx, dy)
        node_editing.nudge_nodes(self._context.session, dx, dy)
        return True

    @property
    def active(self) -> bool:
        return self._mode is not None

    @property
    def hint(self) -> str | None:
        if self._mode is not None:
            return None
        selected = queries.selected_shapes(self._context.state)
        return _(_NON_PATH_HINT) if any(not isinstance(shape, PathShape) for shape in selected) else None

    def _edited(self) -> list[PathShape]:
        return [shape for shape in queries.selected_shapes(self._context.state) if isinstance(shape, PathShape)]

    def _selected_nodes(self, shape_id: int) -> set[int]:
        state = self._context.state
        return {index for owner, index in state.node_selection if owner == shape_id}

    @property
    def overlay(self) -> Overlay:
        state = self._context.state
        selected_ids = frozenset(state.selection)
        overlays = []
        for path in self._edited():
            shown = self._live if self._live is not None and self._live.id == path.id else path
            selected = self._selected_nodes(path.id)
            controls = nodes.visible_controls(shown.segments, selected)
            overlays.append(NodeOverlay(shown.segments, frozenset(selected), frozenset(controls)))
        moving = frozenset({self._live.id}) if self._live is not None else frozenset()
        live = (self._live,) if self._live is not None else ()
        band = self._band() if self._mode is _Mode.BAND else None
        return Overlay(
            selected_ids, rubber_band=band, moving=moving, live=live, nodes=tuple(overlays), snap=self._snapper.hits
        )

    # --- events ---------------------------------------------------------------

    def press(self, point: Point, mods: Mods) -> None:
        state = self._context.state
        session = self._context.session
        self._start = self._end = point
        self._cursor = self.hover(point)
        for path in reversed(self._edited()):
            controls = nodes.visible_controls(path.segments, self._selected_nodes(path.id))
            pick = node_at(path.segments, point, self._context.zoom, controls)
            if pick is None:
                continue
            pick_type, target = pick
            if pick_type == "control":
                self._mode, self._path, self._control = _Mode.CONTROL, path, target
                return
            ref = (path.id, target)
            if mods.shift:
                node_editing.set_node_selection(session, set(state.node_selection) ^ {ref})
                return
            if ref not in state.node_selection:
                node_editing.set_node_selection(session, {ref})
            self._mode, self._path = _Mode.NODES, path
            self._indices = self._selected_nodes(path.id)
            # The pressed node is what snaps; the others move along by the same amount.
            self._anchor = next(info.point for info in nodes.nodes(path.segments) if info.index == target)
            self._snapper = self._context.snapper(exclude={path.id}, own_path=(path, self._indices))
            return
        if self._segment_at(point) is not None:
            return
        hit = self._context.shape_at(point)
        if hit is not None:
            if hit not in state.selection:
                selection.set_selection(session, {hit})
            return
        self._mode = _Mode.BAND
        self._band_base = set(state.node_selection) if mods.shift else set()

    def move(self, point: Point, mods: Mods) -> None:
        if self._mode is None:
            return
        self._end = point
        path = self._path
        if self._mode is _Mode.NODES and path is not None:
            wanted = (self._anchor[0] + point[0] - self._start[0], self._anchor[1] + point[1] - self._start[1])
            snapped = self._snapper.point(wanted, ignore=mods.ctrl)
            self._delta = (snapped[0] - self._anchor[0], snapped[1] - self._anchor[1])
            self._live = replace(path, segments=nodes.move_nodes(path.segments, self._indices, *self._delta))
        elif self._mode is _Mode.CONTROL and path is not None and self._control is not None:
            segments = nodes.move_control(path.segments, self._control, point, keep_smooth=not mods.alt)
            self._live = replace(path, segments=segments)
        self._context.repaint()

    def release(self, point: Point, mods: Mods) -> None:
        if self._mode is None:
            return
        self.move(point, mods)
        mode, path, control, indices, delta = self._mode, self._path, self._control, self._indices, self._delta
        band_refs = self._band_base | self._band_hits() if mode is _Mode.BAND else set()
        clicked_empty = mode is _Mode.BAND and point == self._start
        self.cancel()
        session = self._context.session
        state = self._context.state
        if mode is _Mode.NODES and path is not None:
            node_editing.move_nodes(session, path.id, indices, *delta)
        elif mode is _Mode.CONTROL and path is not None and control is not None:
            if point != self._start:
                node_editing.move_control(session, path.id, control, point, keep_smooth=not mods.alt)
        elif clicked_empty and not band_refs and state is not None and not state.node_selection:
            selection.set_selection(session, set())
        else:
            node_editing.set_node_selection(session, band_refs)
        self._context.repaint()

    def double_click(self, point: Point, mods: Mods) -> None:
        hit = self._segment_at(point)
        if hit is not None:
            path, index, t = hit
            node_editing.insert_node(self._context.session, path.id, index, t)

    def escape(self) -> None:
        """Cancels a drag, else clears the node selection, else the shape selection."""
        if self._mode is None and self._context.state.node_selection:
            node_editing.set_node_selection(self._context.session, set())
        else:
            super().escape()

    def cancel(self) -> None:
        self._mode = None
        self._path = self._control = self._live = None
        self._indices = set()
        self._band_base = set()
        self._snapper = Snapper.off()
        self._anchor = self._delta = (0.0, 0.0)

    def hover(self, point: Point) -> CursorType:
        if self._mode is not None:
            return self._cursor
        for path in self._edited():
            controls = nodes.visible_controls(path.segments, self._selected_nodes(path.id))
            if node_at(path.segments, point, self._context.zoom, controls) is not None:
                return CursorType.NODE
        return CursorType.NODE_INSERT if self._segment_at(point) is not None else CursorType.ARROW

    # --- helpers --------------------------------------------------------------

    def _segment_at(self, point: Point) -> tuple[PathShape, int, float] | None:
        reach = _SEGMENT_PX * self._context.pixel_size
        best: tuple[float, PathShape, int, float] | None = None
        for path in self._edited():
            b = self._context.cache.bounds(path).makeOutset(reach, reach)
            if not b.contains(*point):
                continue
            hit = nodes.nearest_on_path(path.segments, point)
            if hit is not None and hit[2] <= reach and (best is None or hit[2] < best[0]):
                best = (hit[2], path, hit[0], hit[1])
        return None if best is None else best[1:]

    def _band(self) -> Rect:
        return rect_from_points(self._start, self._end)

    def _band_hits(self) -> set[tuple[int, int]]:
        x, y, w, h = self._band()
        return {
            (path.id, info.index)
            for path in self._edited()
            for info in nodes.nodes(path.segments)
            if x <= info.point[0] <= x + w and y <= info.point[1] <= y + h
        }
