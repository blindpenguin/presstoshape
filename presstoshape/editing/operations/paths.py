"""Path construction commands: boolean combine and object to path."""

from presstoshape.editing import queries
from presstoshape.editing.operations._document import map_selected, new_id
from presstoshape.editing.registry import operation, register
from presstoshape.editing.session import Session
from presstoshape.geometry import affine, booleans, transforms
from presstoshape.geometry.segments import transform_segments
from presstoshape.models.shapes import PathShape, Shape, TextShape
from presstoshape.render.paths import from_skia_path
from presstoshape.render.text import text_path

BOOLEAN_OPS = ("union", "difference")


def combine(session: Session, op: str) -> None:
    if op not in BOOLEAN_OPS:
        raise ValueError(f"unknown boolean op {op!r}")
    state = session.state
    targets = [shape for shape in queries.selected_shapes(state) if transforms.outline(shape) is not None]
    if len(targets) < 2:
        return
    with session.edit(op.capitalize()):
        segments = booleans.boolean([transforms.outline(shape) for shape in targets], op)
        bottom = targets[0]
        consumed = {shape.id for shape in targets}
        result = PathShape(new_id(state), segments, bottom.style) if segments else None
        # The result takes the bottom shape's place in z-order (and layer), like Inkscape.
        for layer in state.document.layers:
            kept: list[Shape] = []
            for shape in layer.shapes:
                if shape.id == bottom.id and result is not None:
                    kept.append(result)
                elif shape.id not in consumed:
                    kept.append(shape)
            layer.shapes = kept
        state.selection = {result.id} if result else set()
        state.status_message = op.capitalize()


def _can_combine(session: Session) -> bool:
    return queries.can_combine(session.state)


register("path.union", "&Union", lambda session: combine(session, "union"), _can_combine)
register("path.difference", "D&ifference", lambda session: combine(session, "difference"), _can_combine)


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
