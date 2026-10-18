import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path

from veccy.controllers import geometry, svg_io
from veccy.controllers.geometry import Point
from veccy.models.app_state import AppState, Document, Layer, Tool
from veccy.models.shapes import EllipseShape, PathShape, RectShape, Shape, TextShape

_UNDO_LIMIT = 200
_MIN_ZOOM, _MAX_ZOOM = 10, 800
_ZOOM_STEP = 1.25
_BOOLEAN_OPS = ("union", "difference")


@dataclass
class _Snapshot:
    document: Document
    selected_layer_index: int


def _copy_document(doc: Document) -> Document:
    # Shapes are frozen, so copying the layer lists is enough to isolate a snapshot.
    layers = [Layer(layer.name, layer.visible, list(layer.shapes)) for layer in doc.layers]
    return Document(doc.width, doc.height, layers, doc.next_id)


class AppController:
    """Mutates AppState and notifies subscribers after every change. No Qt imports — views call these on input."""

    def __init__(self, state: AppState) -> None:
        self.state = state
        self._undo_stack: list[_Snapshot] = []
        self._redo_stack: list[_Snapshot] = []
        self._merge_key: str | None = None
        self._listeners: list[Callable[[], None]] = []

    def subscribe(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # --- undo ---------------------------------------------------------------

    def _snapshot(self) -> _Snapshot:
        return _Snapshot(_copy_document(self.state.document), self.state.selected_layer_index)

    def _checkpoint(self, merge_key: str | None = None) -> None:
        """Call before mutating the document. Back-to-back calls with the same merge_key form one undo step."""
        if merge_key is None or merge_key != self._merge_key:
            self._undo_stack.append(self._snapshot())
            del self._undo_stack[:-_UNDO_LIMIT]
        self._merge_key = merge_key
        self._redo_stack.clear()
        self.state.dirty = True

    def _restore(self, snapshot: _Snapshot) -> None:
        self.state.document = snapshot.document
        self.state.selected_layer_index = min(snapshot.selected_layer_index, len(snapshot.document.layers) - 1)
        self._merge_key = None
        self.state.dirty = True
        self._prune_selection()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self._snapshot())
        self._restore(self._undo_stack.pop())
        self.state.status_message = "Undo"
        self._notify()

    def redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self._snapshot())
        self._restore(self._redo_stack.pop())
        self.state.status_message = "Redo"
        self._notify()

    # --- queries ------------------------------------------------------------

    @property
    def active_layer(self) -> Layer:
        return self.state.document.layers[self.state.selected_layer_index]

    def _visible_shapes(self) -> Iterator[Shape]:
        for layer in self.state.document.layers:
            if layer.visible:
                yield from layer.shapes

    def selected_shapes(self) -> list[Shape]:
        """Selected shapes in paint order, bottom first."""
        return [s for s in self._visible_shapes() if s.id in self.state.selection]

    def can_combine(self) -> bool:
        return sum(geometry.outline(s) is not None for s in self.selected_shapes()) >= 2

    def _prune_selection(self) -> None:
        self.state.selection = {s.id for s in self._visible_shapes()} & self.state.selection

    def _new_id(self) -> int:
        doc = self.state.document
        doc.next_id += 1
        return doc.next_id - 1

    def _map_selected(self, fn: Callable[[Shape], Shape]) -> None:
        selection = self.state.selection
        for layer in self.state.document.layers:
            layer.shapes = [fn(s) if s.id in selection else s for s in layer.shapes]

    # --- tools & view -------------------------------------------------------

    def select_tool(self, tool: Tool) -> None:
        self.state.active_tool = tool
        self.state.status_message = f"Tool: {tool.name.title()}"
        self._notify()

    def set_zoom(self, zoom_percent: float) -> None:
        zoom = max(_MIN_ZOOM, min(_MAX_ZOOM, round(zoom_percent)))
        if zoom == self.state.zoom_percent:
            return
        self.state.zoom_percent = zoom
        self._notify()

    def zoom_in(self) -> None:
        self.set_zoom(self.state.zoom_percent * _ZOOM_STEP)

    def zoom_out(self) -> None:
        self.set_zoom(self.state.zoom_percent / _ZOOM_STEP)

    # --- shape creation -----------------------------------------------------

    def _add(self, make: Callable[[int], Shape], label: str) -> int | None:
        if not self.active_layer.visible:
            self.state.status_message = f"Layer '{self.active_layer.name}' is hidden"
            self._notify()
            return None
        self._checkpoint()
        shape = make(self._new_id())
        self.active_layer.shapes.append(shape)
        self.state.selection = {shape.id}
        self.state.status_message = f"Added {label}"
        self._notify()
        return shape.id

    def add_rectangle(self, start: Point, end: Point, square: bool = False) -> int | None:
        x, y, w, h = geometry.box_from_drag(start, end, square)
        if w < 1 or h < 1:
            return None
        style = self.state.default_style
        return self._add(lambda id_: RectShape(id_, x, y, w, h, style), "rectangle")

    def add_ellipse(self, start: Point, end: Point, circle: bool = False) -> int | None:
        x, y, w, h = geometry.box_from_drag(start, end, circle)
        if w < 1 or h < 1:
            return None
        style = self.state.default_style
        return self._add(lambda id_: EllipseShape(id_, x + w / 2, y + h / 2, w / 2, h / 2, style), "ellipse")

    def add_path(self, points: list[Point]) -> int | None:
        if len(points) < 2:
            return None
        segments = geometry.smooth_segments(points)
        style = replace(self.state.default_style, fill=None)
        return self._add(lambda id_: PathShape(id_, segments, style), "path")

    def add_text(self, position: Point, text: str) -> int | None:
        if not text.strip():
            return None
        default = self.state.default_style
        style = replace(default, fill=default.fill or default.stroke or "#000000", stroke=None)
        size = self.state.font_size
        return self._add(lambda id_: TextShape(id_, position[0], position[1], text, size, style), "text")

    # --- selection & editing ------------------------------------------------

    def set_selection(self, ids: set[int]) -> None:
        selection = {s.id for s in self._visible_shapes()} & set(ids)
        if selection == self.state.selection:
            return
        self.state.selection = selection
        self._merge_key = None
        self._notify()

    def select_all(self) -> None:
        self.set_selection({s.id for s in self._visible_shapes()})

    def move_selection(self, dx: float, dy: float) -> None:
        if not self.state.selection or (dx, dy) == (0, 0):
            return
        self._checkpoint()
        self._map_selected(lambda s: geometry.translate(s, dx, dy))
        self.state.status_message = f"Moved {len(self.state.selection)} object(s)"
        self._notify()

    def delete_selection(self) -> None:
        selection = self.state.selection
        if not selection:
            return
        self._checkpoint()
        for layer in self.state.document.layers:
            layer.shapes = [s for s in layer.shapes if s.id not in selection]
        self.state.status_message = f"Deleted {len(selection)} object(s)"
        self.state.selection = set()
        self._notify()

    def combine(self, op: str) -> None:
        if op not in _BOOLEAN_OPS:
            raise ValueError(f"unknown boolean op {op!r}")
        targets = [s for s in self.selected_shapes() if geometry.outline(s) is not None]
        if len(targets) < 2:
            return
        self._checkpoint()
        segments = geometry.boolean([geometry.outline(s) for s in targets], op)
        bottom = targets[0]
        consumed = {s.id for s in targets}
        result = PathShape(self._new_id(), segments, bottom.style) if segments else None
        # The result takes the bottom shape's place in z-order (and layer), like Inkscape.
        for layer in self.state.document.layers:
            shapes: list[Shape] = []
            for s in layer.shapes:
                if s.id == bottom.id and result is not None:
                    shapes.append(result)
                elif s.id not in consumed:
                    shapes.append(s)
            layer.shapes = shapes
        self.state.selection = {result.id} if result else set()
        self.state.status_message = op.capitalize()
        self._notify()

    # --- style --------------------------------------------------------------

    def set_fill(self, color: str | None) -> None:
        self._restyle(fill=color)

    def set_stroke(self, color: str | None) -> None:
        self._restyle(stroke=color)

    def set_stroke_width(self, width: float) -> None:
        self._restyle(merge_key="stroke_width", stroke_width=max(0.0, width))

    def _restyle(self, merge_key: str | None = None, **changes) -> None:
        """Applies to the selection and to the defaults for new shapes (last-used style)."""
        self.state.default_style = replace(self.state.default_style, **changes)
        if self.state.selection:
            self._checkpoint(merge_key)
            self._map_selected(lambda s: replace(s, style=replace(s.style, **changes)))
        self._notify()

    # --- layers -------------------------------------------------------------

    def add_layer(self) -> None:
        self._checkpoint()
        layers = self.state.document.layers
        names = {layer.name for layer in layers}
        n = len(layers) + 1
        while f"Layer {n}" in names:
            n += 1
        index = self.state.selected_layer_index + 1
        layers.insert(index, Layer(f"Layer {n}"))
        self.state.selected_layer_index = index
        self._notify()

    def remove_layer(self, index: int) -> None:
        layers = self.state.document.layers
        if len(layers) <= 1 or not 0 <= index < len(layers):
            return
        self._checkpoint()
        del layers[index]
        self.state.selected_layer_index = min(self.state.selected_layer_index, len(layers) - 1)
        self._prune_selection()
        self._notify()

    def select_layer(self, index: int) -> None:
        if index == self.state.selected_layer_index or not 0 <= index < len(self.state.document.layers):
            return
        self.state.selected_layer_index = index
        self._notify()

    def set_layer_visible(self, index: int, visible: bool) -> None:
        layer = self.state.document.layers[index]
        if layer.visible == visible:
            return
        self._checkpoint()
        layer.visible = visible
        self._prune_selection()
        self._notify()

    def rename_layer(self, index: int, name: str) -> None:
        layer = self.state.document.layers[index]
        name = name.strip()
        if name and name != layer.name:
            self._checkpoint()
            layer.name = name
        # Notify even when rejected so the view drops an empty/whitespace edit.
        self._notify()

    # --- files --------------------------------------------------------------

    def new_document(self) -> None:
        self._reset(Document(), None, "New document")

    def open_file(self, path: str) -> bool:
        try:
            doc = svg_io.read_svg(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError, ET.ParseError) as e:
            self.state.status_message = f"Could not open {Path(path).name}: {e}"
            self._notify()
            return False
        self._reset(doc, path, f"Opened {Path(path).name}")
        return True

    def save_file(self, path: str | None = None) -> bool:
        """Saves to `path`, or the current file. Returns False if there's no target or writing failed."""
        target = path or self.state.file_path
        if target is None:
            return False
        try:
            Path(target).write_text(svg_io.write_svg(self.state.document), encoding="utf-8")
        except OSError as e:
            self.state.status_message = f"Could not save {Path(target).name}: {e}"
            self._notify()
            return False
        self.state.file_path = target
        self.state.dirty = False
        self.state.status_message = f"Saved {Path(target).name}"
        self._notify()
        return True

    def _reset(self, doc: Document, path: str | None, message: str) -> None:
        self.state.document = doc
        self.state.file_path = path
        self.state.dirty = False
        self.state.selection = set()
        self.state.selected_layer_index = len(doc.layers) - 1
        self.state.status_message = message
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._merge_key = None
        self._notify()
