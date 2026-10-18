import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path

from veccy.controllers import affine, geometry, nodes, svg_io
from veccy.controllers.affine import Affine
from veccy.controllers.geometry import Point
from veccy.models.app_state import AppState, Document, Layer, Tool
from veccy.models.shapes import CubicTo, EllipseShape, PathShape, RectShape, Shape, TextShape
from veccy.render import export
from veccy.render.paths import from_skia_path
from veccy.render.text import text_path

_UNDO_LIMIT = 200
_MIN_ZOOM, _MAX_ZOOM = 10, 800
_ZOOM_STEP = 1.25
_BOOLEAN_OPS = ("union", "difference")
# Smallest width/height (doc units) a handle scale may leave; same floor as the panel's size fields.
_MIN_EXTENT = 0.1
# Shape fields the selection panel may edit directly, with their minimum value (None = unbounded).
_EDITABLE_FIELDS: dict[type, dict[str, float | None]] = {
    RectShape: {"x": None, "y": None, "width": 0.1, "height": 0.1},
    EllipseShape: {"cx": None, "cy": None, "rx": 0.1, "ry": 0.1},
    TextShape: {"x": None, "y": None, "font_size": 1.0, "text": None},
}


@dataclass
class _Snapshot:
    document: Document
    selected_layer_index: int


def _copy_document(doc: Document) -> Document:
    # Shapes are frozen, so copying the layer lists is enough to isolate a snapshot.
    layers = [Layer(layer.name, layer.visible, list(layer.shapes)) for layer in doc.layers]
    return Document(doc.width, doc.height, layers, doc.next_id)


def _to_path(shape: Shape) -> Shape:
    if isinstance(shape, PathShape):
        return shape
    if isinstance(shape, TextShape):
        local = from_skia_path(text_path(shape))
        segments = geometry.transform_segments(local, lambda x, y: affine.apply(shape.transform, x, y))
    else:
        segments = geometry.outline(shape) or ()
    return PathShape(shape.id, segments, shape.style)


def _is_control(segments: tuple, ref: tuple[int, int]) -> bool:
    index, which = ref
    return 0 <= index < len(segments) and isinstance(segments[index], CubicTo) and which in (1, 2)


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
        self.state.node_selection = frozenset()

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

    def can_object_to_path(self) -> bool:
        return any(isinstance(s, (RectShape, EllipseShape, TextShape)) for s in self.selected_shapes())

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
        self.state.node_selection = frozenset()
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
        style = self.state.tool_styles[Tool.RECTANGLE]
        return self._add(lambda id_: RectShape(id_, x, y, w, h, style), "rectangle")

    def add_ellipse(self, start: Point, end: Point, circle: bool = False) -> int | None:
        x, y, w, h = geometry.box_from_drag(start, end, circle)
        if w < 1 or h < 1:
            return None
        style = self.state.tool_styles[Tool.ELLIPSE]
        return self._add(lambda id_: EllipseShape(id_, x + w / 2, y + h / 2, w / 2, h / 2, style), "ellipse")

    def add_path(self, points: list[Point]) -> int | None:
        if len(points) < 2:
            return None
        segments = geometry.smooth_segments(points)
        style = self.state.tool_styles[Tool.PEN]
        return self._add(lambda id_: PathShape(id_, segments, style), "path")

    def add_text(self, position: Point, text: str) -> int | None:
        if not text.strip():
            return None
        style = self.state.tool_styles[Tool.TEXT]
        size = self.state.font_size
        return self._add(lambda id_: TextShape(id_, position[0], position[1], text, size, style), "text")

    # --- selection & editing ------------------------------------------------

    def set_selection(self, ids: set[int]) -> None:
        selection = {s.id for s in self._visible_shapes()} & set(ids)
        if selection == self.state.selection:
            return
        self.state.selection = selection
        self.state.node_selection = frozenset()
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

    def transform_selection(self, m: Affine) -> None:
        """Applies `m` (doc space) to every selected shape as one undo step: handle scaling and rotation."""
        if not self.state.selection or affine.is_identity(m) or abs(affine.determinant(m)) < 1e-12:
            return
        self._checkpoint()
        self._map_selected(lambda s: geometry.transform_shape(s, m, _MIN_EXTENT))
        self.state.status_message = f"Transformed {len(self.state.selection)} object(s)"
        self._notify()

    def set_rotation(self, shape_id: int, degrees: float) -> None:
        """Rotation about the shape's own center. Consecutive edits of one shape form one undo step."""
        shape = self.find_shape(shape_id)
        if not isinstance(shape, (RectShape, EllipseShape, TextShape)):
            return
        current = geometry.rotation_of(shape)
        if current is None or abs(current - degrees) < 1e-9:
            return
        self._checkpoint(merge_key=f"{shape_id}:rotation")
        self._replace_shape(geometry.with_rotation(shape, degrees))
        self._notify()

    def _replace_shape(self, updated: Shape) -> None:
        for layer in self.state.document.layers:
            layer.shapes = [updated if s.id == updated.id else s for s in layer.shapes]

    def object_to_path(self) -> None:
        """Turns selected rects, ellipses and text into paths with the same outline, ids and place."""
        if not self.can_object_to_path():
            return
        self._checkpoint()
        self._map_selected(_to_path)
        self.state.status_message = "Object to path"
        self._notify()

    # --- node editing -------------------------------------------------------

    def _edited_path(self, shape_id: int) -> PathShape | None:
        shape = self.find_shape(shape_id)
        return shape if isinstance(shape, PathShape) and shape_id in self.state.selection else None

    def set_node_selection(self, refs: set[tuple[int, int]]) -> None:
        """Selected nodes of selected paths; invalid refs are dropped. Not a document edit."""
        valid: set[tuple[int, int]] = set()
        for shape_id in {ref[0] for ref in refs}:
            path = self._edited_path(shape_id)
            if path is not None:
                indices = nodes.valid_nodes(path.segments, (i for sid, i in refs if sid == shape_id))
                valid.update((shape_id, i) for i in indices)
        if frozenset(valid) != self.state.node_selection:
            self.state.node_selection = frozenset(valid)
            self._notify()

    def _edit_path(
        self, path: PathShape, segments: tuple, message: str, node_selection: frozenset | None = None
    ) -> None:
        self._checkpoint()
        self._replace_shape(replace(path, segments=segments))
        if node_selection is not None:
            self.state.node_selection = node_selection
        self.state.status_message = message
        self._notify()

    def move_nodes(self, shape_id: int, indices: set[int], dx: float, dy: float) -> None:
        path = self._edited_path(shape_id)
        if path is None or (dx, dy) == (0, 0) or not nodes.valid_nodes(path.segments, indices):
            return
        self._edit_path(path, nodes.move_nodes(path.segments, indices, dx, dy), f"Moved {len(indices)} node(s)")

    def move_control(self, shape_id: int, ref: tuple[int, int], point: Point, keep_smooth: bool = True) -> None:
        path = self._edited_path(shape_id)
        if path is None or not _is_control(path.segments, ref):
            return
        self._edit_path(path, nodes.move_control(path.segments, ref, point, keep_smooth), "Moved handle")

    def insert_node(self, shape_id: int, segment_index: int, t: float) -> None:
        path = self._edited_path(shape_id)
        if path is None or not 0 < segment_index < len(path.segments) or not 0 < t < 1:
            return
        segments, index = nodes.insert_node(path.segments, segment_index, t)
        self._edit_path(path, segments, "Inserted node", frozenset({(shape_id, index)}))

    def delete_nodes(self) -> None:
        """Deletes the selected nodes; a path left without nodes is deleted with them (same undo step)."""
        by_shape: dict[int, set[int]] = {}
        for shape_id, index in self.state.node_selection:
            by_shape.setdefault(shape_id, set()).add(index)
        targets = {sid: (p, idx) for sid, idx in by_shape.items() if (p := self._edited_path(sid)) is not None}
        if not targets:
            return
        self._checkpoint()
        emptied = set()
        for shape_id, (path, indices) in targets.items():
            segments = nodes.delete_nodes(path.segments, indices)
            if segments is None:
                emptied.add(shape_id)
            else:
                self._replace_shape(replace(path, segments=segments))
        for layer in self.state.document.layers:
            layer.shapes = [s for s in layer.shapes if s.id not in emptied]
        self.state.selection -= emptied
        self.state.node_selection = frozenset()
        self.state.status_message = f"Deleted {sum(len(i) for _, i in targets.values())} node(s)"
        self._notify()

    def find_shape(self, shape_id: int) -> Shape | None:
        for layer in self.state.document.layers:
            for s in layer.shapes:
                if s.id == shape_id:
                    return s
        return None

    def set_shape_field(self, shape_id: int, field: str, value: float | str) -> None:
        """Edits one geometry/content field. Consecutive edits of the same field form one undo step."""
        shape = self.find_shape(shape_id)
        if shape is None:
            return
        fields = _EDITABLE_FIELDS.get(type(shape), {})
        if field not in fields:
            raise ValueError(f"{type(shape).__name__}.{field} is not editable")
        if field == "text":
            value = str(value)
            if not value.strip():
                # Notify anyway so the view drops the rejected empty text.
                self._notify()
                return
        else:
            minimum = fields[field]
            value = float(value) if minimum is None else max(minimum, float(value))
        if getattr(shape, field) == value:
            return
        self._checkpoint(merge_key=f"{shape_id}:{field}")
        updated = replace(shape, **{field: value})
        rotation = geometry.rotation_of(shape)
        if rotation:
            # The rotation is about the center; keep the angle while the center moves with the new geometry.
            updated = geometry.with_rotation(updated, rotation)
        self._replace_shape(updated)
        self._notify()

    def delete_selection(self) -> None:
        if self.state.active_tool is Tool.NODE and self.state.node_selection:
            self.delete_nodes()
            return
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
        """Restyles the selection only; tool defaults are separate (set_tool_style)."""
        if not self.state.selection:
            return
        self._checkpoint(merge_key)
        self._map_selected(lambda s: replace(s, style=replace(s.style, **changes)))
        self._notify()

    def set_tool_style(self, tool: Tool, **changes) -> None:
        """Changes the style `tool` gives new shapes. Not a document edit, so no undo step."""
        if "stroke_width" in changes:
            changes["stroke_width"] = max(0.0, changes["stroke_width"])
        self.state.tool_styles[tool] = replace(self.state.tool_styles[tool], **changes)
        self._notify()

    def set_font_size(self, size: float) -> None:
        self.state.font_size = max(1.0, size)
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

    def export_png(self, path: str, scale: float) -> bool:
        """Writes the artboard as PNG. Not an edit: undo history and the dirty flag are untouched."""
        self.state.export.scale = scale
        name = Path(path).name
        data = export.render_png(self.state.document, scale)
        try:
            if data is None:
                raise ValueError("image too large to render")
            Path(path).write_bytes(data)
        except (OSError, ValueError) as e:
            self.state.status_message = f"Export failed: {e}"
            self._notify()
            return False
        width, height = export.export_size(self.state.document, scale)
        self.state.status_message = f"Exported {name} ({width} × {height} px)"
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
