"""Node tool edits on selected paths: node selection, moving nodes and handles, inserting and deleting nodes, node
types, and the structural node commands (break, join, delete segment)."""

from collections.abc import Callable
from dataclasses import replace

from presstoshape.editing import containers, queries
from presstoshape.editing.operations._document import remove_shapes, replace_shape
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.geometry import nodes, path_edit
from presstoshape.geometry.boxes import Point
from presstoshape.geometry.path_edit import Edited, NodeKind
from presstoshape.i18n import N_, _, ngettext
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import CubicTo, PathShape, Segment

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
    count = len(indices)
    message = ngettext("Moved {count} node", "Moved {count} nodes", count).format(count=count)
    _edit_path(session, path, moved, ngettext("Move node", "Move nodes", count), message)


def nudge_nodes(session: Session, dx: float, dy: float) -> None:
    """Moves the selected nodes of every edited path; repeated nudges form one undo step."""
    state = session.state
    by_path: dict[int, set[int]] = {}
    for shape_id, index in state.node_selection:
        by_path.setdefault(shape_id, set()).add(index)
    paths = [(path, indices) for shape_id, indices in by_path.items() if (path := _edited_path(session, shape_id))]
    if not paths or (dx, dy) == (0, 0):
        return
    count = sum(len(indices) for _path, indices in paths)
    with session.edit(_("Nudge nodes"), merge_key="nudge_nodes"):
        for path, indices in paths:
            replace_shape(state, replace(path, segments=nodes.move_nodes(path.segments, indices, dx, dy)))
        state.status_message = ngettext("Nudged {count} node", "Nudged {count} nodes", count).format(count=count)


def move_control(session: Session, shape_id: int, ref: tuple[int, int], point: Point, keep_smooth: bool = True) -> None:
    path = _edited_path(session, shape_id)
    if path is None or not _is_control(path.segments, ref):
        return
    moved = nodes.move_control(path.segments, ref, point, keep_smooth)
    _edit_path(session, path, moved, _("Move handle"), _("Moved a handle"))


def insert_node(session: Session, shape_id: int, segment_index: int, t: float) -> None:
    path = _edited_path(session, shape_id)
    if path is None or not 0 < segment_index < len(path.segments) or not 0 < t < 1:
        return
    segments, index = nodes.insert_node(path.segments, segment_index, t)
    _edit_path(session, path, segments, _("Insert node"), _("Inserted a node"), frozenset({(shape_id, index)}))


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
    count = sum(len(indices) for _path, indices in targets.values())
    with session.edit(ngettext("Delete node", "Delete nodes", count)):
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
        state.status_message = ngettext("Deleted {count} node", "Deleted {count} nodes", count).format(count=count)


# --- node commands (menu and Node tool buttons) -------------------------------------


def _targets(session: Session) -> list[tuple[PathShape, set[int]]]:
    """Each edited path with its selected nodes, while the Node tool is active."""
    state = session.state
    if state.active_tool is not Tool.NODE:
        return []
    by_path: dict[int, set[int]] = {}
    for shape_id, index in state.node_selection:
        by_path.setdefault(shape_id, set()).add(index)
    return [(path, indices) for shape_id, indices in by_path.items() if (path := _edited_path(session, shape_id))]


def _any_target(session: Session, test: Callable[[PathShape, set[int]], bool]) -> bool:
    return any(test(path, indices) for path, indices in _targets(session))


def _apply(
    session: Session, label: str, message: str, edit: Callable[[tuple[Segment, ...], set[int]], Edited | None]
) -> None:
    """Runs `edit` on every edited path in one undo step. The node selection becomes the nodes the edit made or
    joined, else the selected nodes where they are now; a path the edit leaves empty is deleted."""
    state = session.state
    results = [(path, indices, edit(path.segments, indices)) for path, indices in _targets(session)]
    if not results:
        return
    with session.edit(label):
        selected: set[NodeRef] = set()
        emptied: set[int] = set()
        for path, indices, edited in results:
            if edited is None:
                emptied.add(path.id)
                continue
            replace_shape(state, replace(path, segments=edited.segments))
            kept = edited.focus or {edited.index_map[i] for i in indices if i in edited.index_map}
            selected.update((path.id, index) for index in kept)
        remove_shapes(state, emptied)
        state.selection -= emptied
        state.node_selection = frozenset(selected)
        state.status_message = message


def _has_nodes(session: Session) -> bool:
    return bool(_targets(session))


def _set_type(session: Session, kind: NodeKind, label: str, message: str) -> None:
    _apply(session, label, message, lambda segments, indices: path_edit.set_node_type(segments, indices, kind))


@operation("path.node_corner", N_("&Corner"), can_run=_has_nodes)
def make_corner(session: Session) -> None:
    _set_type(session, "corner", _("Make nodes corner"), _("Nodes are corners now"))


@operation("path.node_smooth", N_("&Smooth"), can_run=_has_nodes)
def make_smooth(session: Session) -> None:
    _set_type(session, "smooth", _("Make nodes smooth"), _("Nodes are smooth now"))


@operation("path.node_symmetric", N_("S&ymmetric"), can_run=_has_nodes)
def make_symmetric(session: Session) -> None:
    _set_type(session, "symmetric", _("Make nodes symmetric"), _("Nodes are symmetric now"))


def _can_make_lines(session: Session) -> bool:
    return _any_target(session, lambda path, indices: path_edit.has_curve_between(path.segments, indices))


@operation("path.make_line", N_("Make &Line"), can_run=_can_make_lines)
def make_lines(session: Session) -> None:
    _apply(session, _("Make segments lines"), _("Segments are straight now"), path_edit.make_lines)


def _can_make_curves(session: Session) -> bool:
    return _any_target(session, lambda path, indices: path_edit.has_line_between(path.segments, indices))


@operation("path.make_curve", N_("Make C&urve"), can_run=_can_make_curves)
def make_curves(session: Session) -> None:
    _apply(session, _("Make segments curves"), _("Segments are curves now"), path_edit.make_curves)


def _can_break(session: Session) -> bool:
    def breakable(path: PathShape, indices: set[int]) -> bool:
        return bool(indices - path_edit.end_nodes(path.segments))

    return _any_target(session, breakable)


@operation("path.break_nodes", N_("&Break at Nodes"), can_run=_can_break)
def break_nodes(session: Session) -> None:
    _apply(session, _("Break path"), _("Broke the path"), path_edit.break_at)


def _can_delete_segment(session: Session) -> bool:
    return _any_target(session, lambda path, indices: path_edit.has_edge_between(path.segments, indices))


@operation("path.delete_segment", N_("&Delete Segment"), can_run=_can_delete_segment)
def delete_segment(session: Session) -> None:
    _apply(session, _("Delete segment"), _("Deleted a segment"), path_edit.delete_segments)


def _join_pair(session: Session) -> tuple[PathShape, int, PathShape, int] | None:
    """The two selected end nodes as (higher path, node, lower path, node); the paths may be the same."""
    refs = sorted(session.state.node_selection)
    targets = {path.id: path for path, _indices in _targets(session)}
    if len(refs) != 2 or any(ref[0] not in targets for ref in refs):
        return None
    if any(index not in path_edit.end_nodes(targets[shape_id].segments) for shape_id, index in refs):
        return None
    order = {shape.id: position for position, shape in enumerate(containers.pickable_shapes(session.state))}
    (id_a, a), (id_b, b) = sorted(refs, key=lambda ref: -order.get(ref[0], -1))
    return targets[id_a], a, targets[id_b], b


def _joined(session: Session, with_segment: bool) -> tuple[PathShape, PathShape | None, Edited] | None:
    """The higher path, the lower one (None when both ends are on one path) and the joined segments."""
    pair = _join_pair(session)
    if pair is None:
        return None
    higher, a, lower, b = pair
    if higher.id == lower.id:
        edited = path_edit.join_ends(higher.segments, a, b, with_segment)
        return None if edited is None else (higher, None, edited)
    combined = path_edit.combine([higher.segments, lower.segments])
    edited = path_edit.join_ends(combined, a, len(higher.segments) + b, with_segment)
    return None if edited is None else (higher, lower, edited)


def _join(session: Session, with_segment: bool, label: str, message: str) -> None:
    joined = _joined(session, with_segment)
    if joined is None:
        return
    higher, lower, edited = joined
    state = session.state
    with session.edit(label):
        replace_shape(state, replace(higher, segments=edited.segments))
        if lower is not None:
            remove_shapes(state, {lower.id})
            state.selection -= {lower.id}
        state.node_selection = frozenset((higher.id, index) for index in edited.focus)
        state.status_message = message


@operation("path.join_nodes", N_("&Join Nodes"), can_run=lambda session: _joined(session, False) is not None)
def join_nodes(session: Session) -> None:
    _join(session, False, _("Join nodes"), _("Joined two nodes"))


@operation("path.join_segment", N_("Join with Se&gment"), can_run=lambda session: _join_pair(session) is not None)
def join_with_segment(session: Session) -> None:
    _join(session, True, _("Join with segment"), _("Joined two nodes with a segment"))
