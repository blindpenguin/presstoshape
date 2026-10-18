"""Creating shapes and editing one shape's geometry or text."""

from collections.abc import Callable
from dataclasses import replace

from veccy.editing import queries
from veccy.editing.operations._document import new_id, replace_shape
from veccy.editing.session import Session
from veccy.geometry import transforms
from veccy.geometry.boxes import Point, box_from_drag
from veccy.geometry.segments import smooth_segments
from veccy.models.app_state import Tool
from veccy.models.shapes import EllipseShape, PathShape, RectShape, Shape, TextShape

# Shape fields the selection panel may edit directly, with their minimum value (None = unbounded).
EDITABLE_FIELDS: dict[type, dict[str, float | None]] = {
    RectShape: {"x": None, "y": None, "width": 0.1, "height": 0.1},
    EllipseShape: {"cx": None, "cy": None, "rx": 0.1, "ry": 0.1},
    TextShape: {"x": None, "y": None, "font_size": 1.0, "text": None},
}


def _add(session: Session, make: Callable[[int], Shape], name: str) -> int | None:
    state = session.state
    layer = queries.active_layer(state)
    if not layer.visible:
        state.status_message = f"Layer '{layer.name}' is hidden"
        session.notify()
        return None
    with session.edit(f"Add {name}"):
        shape = make(new_id(state))
        layer.shapes.append(shape)
        state.selection = {shape.id}
        state.status_message = f"Added {name}"
    return shape.id


def add_rectangle(session: Session, start: Point, end: Point, square: bool = False) -> int | None:
    x, y, w, h = box_from_drag(start, end, square)
    if w < 1 or h < 1:
        return None
    style = session.state.tool_styles[Tool.RECTANGLE]
    return _add(session, lambda shape_id: RectShape(shape_id, x, y, w, h, style), "rectangle")


def add_ellipse(session: Session, start: Point, end: Point, circle: bool = False) -> int | None:
    x, y, w, h = box_from_drag(start, end, circle)
    if w < 1 or h < 1:
        return None
    style = session.state.tool_styles[Tool.ELLIPSE]
    return _add(session, lambda shape_id: EllipseShape(shape_id, x + w / 2, y + h / 2, w / 2, h / 2, style), "ellipse")


def add_path(session: Session, points: list[Point]) -> int | None:
    if len(points) < 2:
        return None
    segments = smooth_segments(points)
    style = session.state.tool_styles[Tool.PEN]
    return _add(session, lambda shape_id: PathShape(shape_id, segments, style), "path")


def add_text(session: Session, position: Point, text: str) -> int | None:
    if not text.strip():
        return None
    style = session.state.tool_styles[Tool.TEXT]
    size = session.state.font_size
    return _add(session, lambda shape_id: TextShape(shape_id, position[0], position[1], text, size, style), "text")


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
    with session.edit(f"Change {field.replace('_', ' ')}", merge_key=f"{shape_id}:{field}"):
        updated = replace(shape, **{field: value})
        rotation = transforms.rotation_of(shape)
        if rotation:
            # The rotation is about the center; keep the angle while the center moves with the new geometry.
            updated = transforms.with_rotation(updated, rotation)
        replace_shape(state, updated)
