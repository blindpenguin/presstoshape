"""Path commands: Object to Path, Combine and Split Path, Close / Open Path, Reverse Direction, and the Pen
continuing or joining existing paths."""

from collections.abc import Callable
from dataclasses import replace

from presstoshape.editing import containers, queries
from presstoshape.editing.operations._document import (
    map_selected,
    new_id,
    remove_shapes,
    replace_shape,
    replace_with,
)
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.geometry import affine, nodes, path_edit, transforms
from presstoshape.geometry.path_edit import Edited, Segments
from presstoshape.geometry.pen_paths import PenNode, pen_segments
from presstoshape.geometry.segments import transform_segments
from presstoshape.i18n import N_, _, ngettext
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import EllipseShape, PathShape, RectShape, Segment, Shape, TextShape
from presstoshape.render.paths import from_skia_path
from presstoshape.render.text import text_path

# A path's open end node: (path id, node index).
EndRef = tuple[int, int]


def to_path(shape: Shape) -> Shape:
    if isinstance(shape, PathShape):
        return shape
    if isinstance(shape, TextShape):
        local = from_skia_path(text_path(shape))
        segments = transform_segments(local, lambda x, y: affine.apply(shape.transform, x, y))
    else:
        segments = transforms.outline(shape) or ()
    return PathShape(shape.id, segments, shape.style)


def _can_convert(session: Session) -> bool:
    return queries.can_object_to_path(session.state)


@operation("path.object_to_path", N_("&Object to Path"), can_run=_can_convert)
def object_to_path(session: Session) -> None:
    """Turns selected rects, ellipses and text into paths with the same outline, ids and place."""
    state = session.state
    if not queries.can_object_to_path(state):
        return
    with session.edit(_("Object to Path")):
        map_selected(state, to_path)
        state.status_message = _("Converted to paths")


# --- combine and split ---------------------------------------------------------------


def _combinable(session: Session) -> list[Shape]:
    """The selected shapes bottom first, when there are at least two and all of them are paths, rectangles or
    ellipses."""
    selected = queries.selected_shapes(session.state)
    if len(selected) < 2 or not all(isinstance(shape, (PathShape, RectShape, EllipseShape)) for shape in selected):
        return []
    return selected


@operation("path.combine", N_("Co&mbine"), can_run=lambda session: bool(_combinable(session)))
def combine(session: Session) -> None:
    """One path holding the subpaths of all selected shapes, with the topmost one's id, style and place."""
    targets = _combinable(session)
    if not targets:
        return
    state = session.state
    top = targets[-1]
    segments = path_edit.combine([to_path(shape).segments for shape in targets])
    with session.edit(_("Combine")):
        # replace_with puts the result where its first target was.
        replace_with(state, [top, *targets[:-1]], [PathShape(top.id, segments, top.style)])
        state.selection = {top.id}
        state.node_selection = frozenset()
        count = len(targets)
        state.status_message = ngettext("Combined {count} object", "Combined {count} objects", count).format(
            count=count
        )


def _splittable(session: Session) -> list[tuple[PathShape, list[Segments]]]:
    out = []
    for shape in queries.selected_shapes(session.state):
        if isinstance(shape, PathShape):
            parts = path_edit.split(shape.segments)
            if len(parts) > 1:
                out.append((shape, parts))
    return out


@operation("path.split", N_("&Split Path"), can_run=lambda session: bool(_splittable(session)))
def split(session: Session) -> None:
    """Every selected compound path becomes one path per subpath, in its place and style; the first keeps its id."""
    targets = _splittable(session)
    if not targets:
        return
    state = session.state
    with session.edit(_("Split Path")):
        made: set[int] = set()
        for path, parts in targets:
            ids = [path.id, *(new_id(state) for _part in parts[1:])]
            replace_with(state, [path], [PathShape(i, part, path.style) for i, part in zip(ids, parts)])
            made.update(ids)
        state.selection = (state.selection - {path.id for path, _parts in targets}) | made
        state.node_selection = frozenset()
        count = len(made)
        state.status_message = ngettext("Split into {count} path", "Split into {count} paths", count).format(
            count=count
        )


# --- close, open, reverse ------------------------------------------------------------

# A whole-path edit, and the same edit limited to the subpaths of the given nodes.
_WholeEdit = Callable[[Segments], Edited]
_NodeEdit = Callable[[Segments, set[int]], Edited]


def _path_targets(session: Session) -> list[tuple[PathShape, set[int] | None]]:
    """Selected paths with the selected nodes to limit an edit to (Node tool), or None for the whole path."""
    state = session.state
    by_node = state.active_tool is Tool.NODE and bool(state.node_selection)
    out = []
    for shape in queries.selected_shapes(state):
        if not isinstance(shape, PathShape):
            continue
        if not by_node:
            out.append((shape, None))
            continue
        indices = {index for owner, index in state.node_selection if owner == shape.id}
        if indices:
            out.append((shape, indices))
    return out


def _has_subpath(session: Session, closed: bool) -> bool:
    for path, indices in _path_targets(session):
        for sub in path_edit.to_subs(path.segments):
            touched = indices is None or any(anchor.source in indices for anchor in sub.anchors)
            if touched and sub.closed == closed and len(sub.anchors) > 1:
                return True
    return False


def _edit_paths(session: Session, label: str, whole: _WholeEdit, by_nodes: _NodeEdit) -> None:
    targets = _path_targets(session)
    if not targets:
        return
    state = session.state
    with session.edit(label):
        selected = set()
        for path, indices in targets:
            edited = whole(path.segments) if indices is None else by_nodes(path.segments, indices)
            replace_shape(state, replace(path, segments=edited.segments))
            if indices is not None:
                kept = {edited.index_map[i] for i in indices if i in edited.index_map} | edited.focus
                selected.update((path.id, index) for index in kept)
        state.node_selection = frozenset(selected)
        state.status_message = label


@operation("path.close", N_("C&lose Path"), can_run=lambda session: _has_subpath(session, closed=False))
def close_paths(session: Session) -> None:
    _edit_paths(session, _("Close Path"), path_edit.close_subpaths, path_edit.close_subpaths)


@operation("path.open", N_("O&pen Path"), can_run=lambda session: _has_subpath(session, closed=True))
def open_paths(session: Session) -> None:
    _edit_paths(session, _("Open Path"), path_edit.open_subpaths, path_edit.break_at)


@operation("path.reverse", N_("Rev&erse Direction"), can_run=lambda session: bool(_path_targets(session)))
def reverse_paths(session: Session) -> None:
    _edit_paths(session, _("Reverse Direction"), path_edit.reverse, path_edit.reverse)


# --- the Pen continuing and joining paths -----------------------------------------------


def open_ends(session: Session) -> list[tuple[EndRef, tuple[float, float]]]:
    """End nodes of open subpaths on the paths the user can pick right now, topmost path first, with their points."""
    out = []
    for shape in reversed(containers.pickable_shapes(session.state)):
        if isinstance(shape, PathShape):
            points = {info.index: info.point for info in nodes.nodes(shape.segments)}
            out.extend(((shape.id, index), points[index]) for index in sorted(path_edit.end_nodes(shape.segments)))
    return out


def _pickable_path(session: Session, shape_id: int) -> PathShape | None:
    return next(
        (s for s in containers.pickable_shapes(session.state) if s.id == shape_id and isinstance(s, PathShape)), None
    )


def _with_end_handle(segments: Segments, index: int, handle: tuple[float, float] | None) -> Segments:
    """`segments` with the handle on the segment at end node `index` moved to `handle` (if that segment has one)."""
    controls = nodes.Topology(segments).controls(index)
    if handle is None or not controls:
        return segments
    out: list[Segment] = list(segments)
    ref = controls[0]
    s = out[ref[0]]
    out[ref[0]] = replace(s, c1x=handle[0], c1y=handle[1]) if ref[1] == 1 else replace(s, c2x=handle[0], c2y=handle[1])
    return tuple(out)


def continue_path(session: Session, pen_nodes: list[PenNode], start: EndRef | None, end: EndRef | None) -> None:
    """Commits a Pen path that starts on the open end `start` and/or finishes on the open end `end` of existing
    paths: the drawn nodes are joined into them. The result keeps the id, style and place of the higher of the
    paths it joins; the other one goes. Ending on the other end of the subpath it started from closes it."""
    first = _pickable_path(session, start[0]) if start is not None else None
    last = _pickable_path(session, end[0]) if end is not None else None
    if len(pen_nodes) < 2 or (first is None and last is None):
        return
    tail = pen_segments(pen_nodes)
    tail_end = len(tail) - 1
    if first is not None:
        assert start is not None
        own = _with_end_handle(first.segments, start[1], pen_nodes[0].handle_in)
        edited = path_edit.join_ends(path_edit.combine([own, tail]), start[1], len(own), with_segment=False)
        if edited is None:
            return
        segments, tail_end = edited.segments, edited.index_map[len(own) + tail_end]
        if last is not None and last.id == first.id:
            assert end is not None
            target = edited.index_map.get(end[1])
            closed = None if target is None else path_edit.join_ends(segments, target, tail_end, with_segment=False)
            if closed is not None:
                segments = closed.segments
            last = None
    else:
        segments = tail
    if last is not None:
        assert end is not None
        edited = path_edit.join_ends(
            path_edit.combine([last.segments, segments]), end[1], len(last.segments) + tail_end, with_segment=False
        )
        if edited is None:
            return
        segments = edited.segments
    kept = _higher(session, [p for p in (first, last) if p is not None])
    state = session.state
    joining = first is not None and last is not None
    with session.edit(_("Join paths") if joining else _("Continue path")):
        replace_shape(state, replace(kept, segments=segments))
        gone = {p.id for p in (first, last) if p is not None and p.id != kept.id}
        remove_shapes(state, gone)
        state.selection = {kept.id}
        state.node_selection = frozenset()
        state.status_message = _("Joined paths") if joining else _("Continued a path")


def _higher(session: Session, paths: list[PathShape]) -> PathShape:
    order = {shape.id: position for position, shape in enumerate(containers.pickable_shapes(session.state))}
    return max(paths, key=lambda path: order.get(path.id, -1))
