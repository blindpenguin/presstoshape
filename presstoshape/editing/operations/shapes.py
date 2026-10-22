"""Creating shapes and editing one shape's geometry or text."""

from collections.abc import Callable
from dataclasses import replace
from typing import get_args

from presstoshape.editing import containers, queries
from presstoshape.editing.operations._document import map_selected, new_id, replace_shape
from presstoshape.editing.session import Session
from presstoshape.geometry import transforms
from presstoshape.geometry.boxes import Point, box_from_drag
from presstoshape.geometry.segments import smooth_segments
from presstoshape.i18n import _
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import EllipseShape, PathShape, RectShape, Segment, Shape, TextAnchor, TextShape

# Shape fields the selection panel may edit directly, with their minimum value (None = unbounded).
EDITABLE_FIELDS: dict[type, dict[str, float | None]] = {
    RectShape: {"x": None, "y": None, "width": 0.1, "height": 0.1},
    EllipseShape: {"cx": None, "cy": None, "rx": 0.1, "ry": 0.1},
    TextShape: {"x": None, "y": None, "font_size": 1.0, "text": None},
}


def _field_label(field: str) -> str:
    """Undo label for editing one field in the selection panel."""
    labels = {
        "x": _("Change X"),
        "y": _("Change Y"),
        "cx": _("Change X"),
        "cy": _("Change Y"),
        "width": _("Change width"),
        "height": _("Change height"),
        "rx": _("Change horizontal radius"),
        "ry": _("Change vertical radius"),
        "font_size": _("Change font size"),
        "text": _("Change text"),
    }
    return labels[field]


def _add(session: Session, make: Callable[[int], Shape], label: str, message: str) -> int | None:
    """Adds to the active layer, or on top of the entered group or Composite (in the new-part mode)."""
    state = session.state
    inside = containers.editing(state)
    layer = queries.active_layer(state)
    if not inside and not layer.visible:
        state.status_message = _("Layer '{name}' is hidden").format(name=layer.name)
        session.notify()
        return None
    if not inside and layer.locked:
        state.status_message = _("Layer '{name}' is locked").format(name=layer.name)
        session.notify()
        return None
    with session.edit(label):
        shape = make(new_id(state))
        if inside:
            containers.change_container(state, lambda shapes: [*shapes, shape])
        else:
            layer.shapes.append(shape)
        state.selection = {shape.id}
        state.status_message = message
    return shape.id


def add_rectangle(session: Session, start: Point, end: Point, square: bool = False) -> int | None:
    x, y, w, h = box_from_drag(start, end, square)
    if w < 1 or h < 1:
        return None
    style = session.state.tool_styles[Tool.RECTANGLE]

    def make(shape_id: int) -> Shape:
        return RectShape(shape_id, x, y, w, h, style)

    return _add(session, make, _("Add rectangle"), _("Added a rectangle"))


def add_ellipse(session: Session, start: Point, end: Point, circle: bool = False) -> int | None:
    x, y, w, h = box_from_drag(start, end, circle)
    if w < 1 or h < 1:
        return None
    style = session.state.tool_styles[Tool.ELLIPSE]

    def make(shape_id: int) -> Shape:
        return EllipseShape(shape_id, x + w / 2, y + h / 2, w / 2, h / 2, style)

    return _add(session, make, _("Add ellipse"), _("Added an ellipse"))


def add_path(session: Session, points: list[Point]) -> int | None:
    if len(points) < 2:
        return None
    segments = smooth_segments(points)
    style = session.state.tool_styles[Tool.PEN]

    def make(shape_id: int) -> Shape:
        return PathShape(shape_id, segments, style)

    return _add(session, make, _("Add path"), _("Added a path"))


def add_drawn_path(session: Session, segments: tuple[Segment, ...], tool: Tool) -> int | None:
    """A path drawn by `tool` (e.g. the Pencil), in that tool's style."""
    style = session.state.tool_styles[tool]

    def make(shape_id: int) -> Shape:
        return PathShape(shape_id, segments, style)

    return _add(session, make, _("Add path"), _("Added a path"))


def add_text(session: Session, position: Point, text: str) -> int | None:
    if not text.strip():
        return None
    if containers.edited_composite(session.state) is not None:
        session.state.status_message = _("Text can't be a Composite part: add it outside, then use Object to Path")
        session.notify()
        return None
    style = session.state.tool_styles[Tool.TEXT]
    size = session.state.font_size

    def make(shape_id: int) -> Shape:
        return TextShape(shape_id, position[0], position[1], text, size, style)

    return _add(session, make, _("Add text"), _("Added text"))


def set_shape_field(session: Session, shape_id: int, field: str, value: float | str) -> None:
    """Edits one geometry/content field. Consecutive edits of the same field form one undo step."""
    state = session.state
    shape = queries.find_shape(state, shape_id)
    if shape is None:
        return
    fields = EDITABLE_FIELDS.get(type(shape), {})
    if field not in fields:
        raise ValueError(f"{type(shape).__name__}.{field} is not editable")
    if field == "text":
        value = str(value)
        if not value.strip():
            # Notify anyway so the view drops the rejected empty text.
            session.notify()
            return
    else:
        minimum = fields[field]
        value = float(value) if minimum is None else max(minimum, float(value))
    if getattr(shape, field) == value:
        return
    with session.edit(_field_label(field), merge_key=f"{shape_id}:{field}"):
        updated = replace(shape, **{field: value})
        rotation = transforms.rotation_of(shape)
        if rotation:
            # The rotation is about the center; keep the angle while the center moves with the new geometry.
            updated = transforms.with_rotation(updated, rotation)
        replace_shape(state, updated)


def set_corner_radius(session: Session, radius: float) -> None:
    """Rounds the corners of every selected rectangle (both radii); other shapes are left alone."""
    radius = max(0.0, float(radius))
    rects = [shape for shape in queries.selected_shapes(session.state) if isinstance(shape, RectShape)]
    if all(rect.rx == radius and rect.ry == radius for rect in rects):
        return
    with session.edit(_("Change corner radius"), merge_key="corner_radius"):
        map_selected(
            session.state,
            lambda shape: replace(shape, rx=radius, ry=radius) if isinstance(shape, RectShape) else shape,
        )


def set_text_anchor(session: Session, anchor: TextAnchor) -> None:
    """Which point of the selected text lines sits at their position; the position stays, the text moves."""
    if anchor not in get_args(TextAnchor):
        raise ValueError(f"unknown text anchor {anchor!r}")
    texts = [shape for shape in queries.selected_shapes(session.state) if isinstance(shape, TextShape)]
    if all(text.anchor == anchor for text in texts):
        return
    with session.edit(_("Change text alignment")):
        map_selected(
            session.state,
            lambda shape: replace(shape, anchor=anchor) if isinstance(shape, TextShape) else shape,
        )
