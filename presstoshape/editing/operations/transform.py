"""Scaling and rotating: handle gestures and the rotation field."""

from presstoshape.editing import queries
from presstoshape.editing.operations._document import map_selected, replace_shape
from presstoshape.editing.registry import register
from presstoshape.editing.session import Session
from presstoshape.geometry import affine, transforms
from presstoshape.geometry.affine import Affine
from presstoshape.i18n import N_, _, ngettext
from presstoshape.models.shapes import EllipseShape, ImageShape, RectShape, TextShape
from presstoshape.render.paths import PathCache

# Smallest width/height (doc units) a handle scale may leave; same floor as the panel's size fields.
MIN_EXTENT = 0.1


def transform_selection(session: Session, matrix: Affine) -> None:
    """Applies `matrix` (doc space) to every selected shape as one undo step."""
    state = session.state
    if not state.selection or affine.is_identity(matrix) or abs(affine.determinant(matrix)) < 1e-12:
        return
    count = len(state.selection)
    with session.edit(ngettext("Transform {count} object", "Transform {count} objects", count).format(count=count)):
        map_selected(state, lambda shape: transforms.transform_shape(shape, matrix, MIN_EXTENT))
        state.status_message = ngettext("Transformed {count} object", "Transformed {count} objects", count).format(
            count=count
        )


def set_rotation(session: Session, shape_id: int, degrees: float) -> None:
    """Rotation about the shape's own center. Consecutive edits of one shape form one undo step."""
    shape = queries.find_shape(session.state, shape_id)
    if not isinstance(shape, (RectShape, EllipseShape, TextShape, ImageShape)):
        return
    current = transforms.rotation_of(shape)
    if current is None or abs(current - degrees) < 1e-9:
        return
    with session.edit(_("Rotate"), merge_key=f"{shape_id}:rotation"):
        replace_shape(session.state, transforms.with_rotation(shape, degrees))


_BOUNDS_LABELS = {"x": N_("Change X"), "y": N_("Change Y"), "width": N_("Change width"), "height": N_("Change height")}


def set_bounds(session: Session, shape_id: int, field: str, value: float) -> None:
    """Moves or scales any shape (used for groups) so one side of its geometry bounds takes `value`: x / y move
    it, width / height scale it from its top-left corner. Consecutive edits of one field form one undo step."""
    if field not in _BOUNDS_LABELS:
        raise ValueError(f"unknown bounds field {field!r}")
    shape = queries.find_shape(session.state, shape_id)
    if shape is None:
        return
    box = PathCache().geometry_bounds(shape)
    left, top, width, height = box.left(), box.top(), box.width(), box.height()
    target = {"x": left, "y": top, "width": width, "height": height}
    target[field] = max(MIN_EXTENT, value) if field in ("width", "height") else value
    scale_x = target["width"] / width if width > 1e-9 else 1.0
    scale_y = target["height"] / height if height > 1e-9 else 1.0
    matrix = affine.compose(
        affine.translation(target["x"], target["y"]),
        affine.compose(affine.scaling(scale_x, scale_y), affine.translation(-left, -top)),
    )
    if affine.is_identity(matrix):
        return
    try:
        updated = transforms.transform_shape(shape, matrix, MIN_EXTENT)
    except ValueError:
        return
    with session.edit(_(_BOUNDS_LABELS[field]), merge_key=f"{shape_id}:{field}"):
        replace_shape(session.state, updated)


def nudge(session: Session, dx: float, dy: float) -> None:
    """Moves the selection by (dx, dy); repeated nudges (a held arrow key) form one undo step."""
    state = session.state
    if not state.selection or (dx, dy) == (0, 0):
        return
    count = len(state.selection)
    with session.edit(_("Nudge"), merge_key="nudge"):
        map_selected(state, lambda shape: transforms.translate(shape, dx, dy))
        state.status_message = ngettext("Nudged {count} object", "Nudged {count} objects", count).format(count=count)


def flip(session: Session, horizontal: bool) -> None:
    """Mirrors the selection about the centre of its bounds. Text keeps reading forwards: only its position is
    mirrored."""
    state = session.state
    selected = queries.selected_shapes(state)
    if not selected:
        return
    cache = PathCache()
    boxes = [cache.geometry_bounds(shape) for shape in selected]
    center_x = (min(box.left() for box in boxes) + max(box.right() for box in boxes)) / 2
    center_y = (min(box.top() for box in boxes) + max(box.bottom() for box in boxes)) / 2
    mirror = affine.scaling(-1, 1) if horizontal else affine.scaling(1, -1)
    matrix = affine.compose(
        affine.translation(center_x, center_y), affine.compose(mirror, affine.translation(-center_x, -center_y))
    )
    with session.edit(_("Flip horizontally") if horizontal else _("Flip vertically")):
        map_selected(state, lambda shape: transforms.transform_shape(shape, matrix, MIN_EXTENT))
        state.status_message = _("Flipped horizontally") if horizontal else _("Flipped vertically")


def _has_selection(session: Session) -> bool:
    return bool(queries.selected_shapes(session.state))


register("object.flip_horizontal", N_("Flip &Horizontal"), lambda session: flip(session, True), _has_selection)
register("object.flip_vertical", N_("Flip &Vertical"), lambda session: flip(session, False), _has_selection)
