"""Node tool edits on selected paths: node selection, moving nodes and handles, inserting and deleting nodes."""

from dataclasses import replace

from veccy.editing import queries
from veccy.editing.operations._document import remove_shapes, replace_shape
from veccy.editing.session import Session
from veccy.geometry import nodes
from veccy.geometry.boxes import Point
from veccy.models.shapes import CubicTo, PathShape, Segment

NodeRef = tuple[int, int]


def _edited_path(session: Session, shape_id: int) -> PathShape | None:
    shape = queries.find_shape(session.state, shape_id)
    return shape if isinstance(shape, PathShape) and shape_id in session.state.selection else None


def _is_control(segments: tuple[Segment, ...], ref: tuple[int, int]) -> bool:
    index, which = ref
    return 0 <= index < len(segments) and isinstance(segments[index], CubicTo) and which in (1, 2)


def set_node_selection(session: Session, refs: set[NodeRef]) -> None:
    """Selected nodes of selected paths; invalid refs are dropped. Not a document edit."""
    valid: set[NodeRef] = set()
    for shape_id in {ref[0] for ref in refs}:
        path = _edited_path(session, shape_id)
        if path is not None:
            indices = nodes.valid_nodes(path.segments, (index for owner, index in refs if owner == shape_id))
            valid.update((shape_id, index) for index in indices)
    if frozenset(valid) != session.state.node_selection:
        session.state.node_selection = frozenset(valid)
        session.notify()


def _edit_path(
    session: Session,
    path: PathShape,
    segments: tuple[Segment, ...],
    label: str,
    message: str,
    node_selection: frozenset[NodeRef] | None = None,
) -> None:
    state = session.state
    with session.edit(label):
        replace_shape(state, replace(path, segments=segments))
        if node_selection is not None:
            state.node_selection = node_selection
        state.status_message = message


def move_nodes(session: Session, shape_id: int, indices: set[int], dx: float, dy: float) -> None:
    path = _edited_path(session, shape_id)
    if path is None or (dx, dy) == (0, 0) or not nodes.valid_nodes(path.segments, indices):
        return
    moved = nodes.move_nodes(path.segments, indices, dx, dy)
    _edit_path(session, path, moved, "Move node(s)", f"Moved {len(indices)} node(s)")


def move_control(session: Session, shape_id: int, ref: tuple[int, int], point: Point, keep_smooth: bool = True) -> None:
    path = _edited_path(session, shape_id)
    if path is None or not _is_control(path.segments, ref):
        return
    moved = nodes.move_control(path.segments, ref, point, keep_smooth)
    _edit_path(session, path, moved, "Move handle", "Moved handle")


def insert_node(session: Session, shape_id: int, segment_index: int, t: float) -> None:
    path = _edited_path(session, shape_id)
    if path is None or not 0 < segment_index < len(path.segments) or not 0 < t < 1:
        return
    segments, index = nodes.insert_node(path.segments, segment_index, t)
    _edit_path(session, path, segments, "Insert node", "Inserted node", frozenset({(shape_id, index)}))


def delete_nodes(session: Session) -> None:
    """Deletes the selected nodes; a path left without nodes is deleted with them (same undo step)."""
    state = session.state
    by_shape: dict[int, set[int]] = {}
    for shape_id, index in state.node_selection:
        by_shape.setdefault(shape_id, set()).add(index)
    targets = {
        shape_id: (path, indices)
        for shape_id, indices in by_shape.items()
        if (path := _edited_path(session, shape_id)) is not None
    }
    if not targets:
        return
    with session.edit("Delete node(s)"):
        emptied = set()
        for shape_id, (path, indices) in targets.items():
            segments = nodes.delete_nodes(path.segments, indices)
            if segments is None:
                emptied.add(shape_id)
            else:
                replace_shape(state, replace(path, segments=segments))
        remove_shapes(state, emptied)
        state.selection -= emptied
        state.node_selection = frozenset()
        state.status_message = f"Deleted {sum(len(indices) for _, indices in targets.values())} node(s)"
