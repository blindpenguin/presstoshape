"""Scaling and rotating: handle gestures and the rotation field."""

from presstoshape.editing import queries
from presstoshape.editing.operations._document import map_selected, replace_shape
from presstoshape.editing.session import Session
from presstoshape.geometry import affine, transforms
from presstoshape.geometry.affine import Affine
from presstoshape.models.shapes import EllipseShape, RectShape, TextShape

# Smallest width/height (doc units) a handle scale may leave; same floor as the panel's size fields.
MIN_EXTENT = 0.1


def transform_selection(session: Session, matrix: Affine) -> None:
    """Applies `matrix` (doc space) to every selected shape as one undo step."""
    state = session.state
    if not state.selection or affine.is_identity(matrix) or abs(affine.determinant(matrix)) < 1e-12:
        return
    count = len(state.selection)
    with session.edit(f"Transform {count} object(s)"):
        map_selected(state, lambda shape: transforms.transform_shape(shape, matrix, MIN_EXTENT))
        state.status_message = f"Transformed {count} object(s)"


def set_rotation(session: Session, shape_id: int, degrees: float) -> None:
    """Rotation about the shape's own center. Consecutive edits of one shape form one undo step."""
    shape = queries.find_shape(session.state, shape_id)
    if not isinstance(shape, (RectShape, EllipseShape, TextShape)):
        return
    current = transforms.rotation_of(shape)
    if current is None or abs(current - degrees) < 1e-9:
        return
    with session.edit("Rotate", merge_key=f"{shape_id}:rotation"):
        replace_shape(session.state, transforms.with_rotation(shape, degrees))
