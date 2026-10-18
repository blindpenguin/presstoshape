"""Object to Path: turn rects, ellipses and text into editable paths."""

from presstoshape.editing import queries
from presstoshape.editing.operations._document import map_selected
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.geometry import affine, transforms
from presstoshape.geometry.segments import transform_segments
from presstoshape.models.shapes import PathShape, Shape, TextShape
from presstoshape.render.paths import from_skia_path
from presstoshape.render.text import text_path


def _to_path(shape: Shape) -> Shape:
    if isinstance(shape, PathShape):
        return shape
    if isinstance(shape, TextShape):
        local = from_skia_path(text_path(shape))
        segments = transform_segments(local, lambda x, y: affine.apply(shape.transform, x, y))
    else:
        segments = transforms.outline(shape) or ()
    return PathShape(shape.id, segments, shape.style)


@operation("path.object_to_path", "&Object to Path", can_run=lambda session: queries.can_object_to_path(session.state))
def object_to_path(session: Session) -> None:
    """Turns selected rects, ellipses and text into paths with the same outline, ids and place."""
    state = session.state
    if not queries.can_object_to_path(state):
        return
    with session.edit("Object to path"):
        map_selected(state, _to_path)
        state.status_message = "Object to path"
