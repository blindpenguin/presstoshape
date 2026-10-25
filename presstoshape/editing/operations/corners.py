"""Live corners: set, remove and apply the rounding of path corner nodes (see geometry/corners.py)."""

from dataclasses import replace

from presstoshape.editing import queries
from presstoshape.editing.operations._document import replace_shape
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.geometry import corners
from presstoshape.i18n import N_, _
from presstoshape.models.app_state import AppState, Tool
from presstoshape.models.shapes import CornerKind, PathShape, Rounding, Segment

NodeRef = tuple[int, int]


def _paths(state: AppState) -> dict[int, PathShape]:
    return {shape.id: shape for shape in queries.selected_shapes(state) if isinstance(shape, PathShape)}


def _by_path(state: AppState, refs) -> dict[int, tuple[PathShape, set[int]]]:
    """The refs grouped by selected path, keeping only nodes that can carry a rounding."""
    paths = _paths(state)
    out: dict[int, tuple[PathShape, set[int]]] = {}
    for shape_id, index in refs:
        if shape_id in paths:
            out.setdefault(shape_id, (paths[shape_id], set()))[1].add(index)
    return {
        shape_id: (path, indices & corners.roundable(path.segments))
        for shape_id, (path, indices) in out.items()
        if indices & corners.roundable(path.segments)
    }


def _with_roundings(segments: tuple[Segment, ...], indices: set[int], make) -> tuple[Segment, ...]:
    out = list(segments)
    for index in indices:
        out[index] = replace(out[index], rounding=make(out[index].rounding))
    return tuple(out)


def _edit(session: Session, refs, change, label: str, merge_key: str | None = None) -> None:
    """`change(segments, indices)` on each selected path with roundable refs, in one undo step."""
    targets = _by_path(session.state, refs)
    if not targets:
        return
    state = session.state
    with session.edit(label, merge_key=merge_key):
        for path, indices in targets.values():
            replace_shape(state, replace(path, segments=change(path.segments, indices)))
        state.status_message = label


def set_radius(session: Session, refs, radius: float, merge_key: str | None = None) -> None:
    """Gives the corners `radius`, keeping each one's kind (new ones are round); 0 removes the rounding."""
    radius = max(0.0, radius)
    _edit(
        session,
        refs,
        lambda segments, indices: corners.with_radius(segments, indices, radius),
        _("Round corners"),
        merge_key,
    )


def set_corners(session: Session, refs, kind: CornerKind, radius: float, merge_key: str | None = None) -> None:
    radius = max(0.0, radius)
    rounding = Rounding(radius, kind) if radius > 0 else None
    _edit(
        session,
        refs,
        lambda segments, indices: _with_roundings(segments, indices, lambda _old: rounding),
        _("Corner rounding"),
        merge_key,
    )


def set_kind(session: Session, refs, kind: CornerKind) -> None:
    """Changes the kind of the rounded corners among `refs`, keeping their radii."""

    def change(segments: tuple[Segment, ...], indices: set[int]) -> tuple[Segment, ...]:
        rounded = {i for i in indices if segments[i].rounding is not None}
        return _with_roundings(segments, rounded, lambda old: replace(old, kind=kind))

    _edit(session, refs, change, _("Corner rounding"))


def corner_values(state: AppState, refs) -> tuple[CornerKind | None, float | None] | None:
    """Kind and radius shared by the roundable corners among `refs` (None where they differ); None when there are
    none. Unrounded corners count as round with radius 0."""
    targets = _by_path(state, refs)
    roundings = [path.segments[i].rounding for path, indices in targets.values() for i in indices]
    if not roundings:
        return None
    kinds = {r.kind if r is not None else "round" for r in roundings}
    radii = {r.radius if r is not None else 0.0 for r in roundings}
    return (next(iter(kinds)) if len(kinds) == 1 else None), (next(iter(radii)) if len(radii) == 1 else None)


def selected_corners(state: AppState) -> set[NodeRef]:
    """Selected nodes of selected paths that can be rounded (Node tool)."""
    if state.active_tool is not Tool.NODE:
        return set()
    return {(path.id, index) for path, indices in _by_path(state, state.node_selection).values() for index in indices}


def selected_corner_values(state: AppState) -> tuple[CornerKind | None, float | None] | None:
    """`corner_values` of the selected nodes (Node tool)."""
    refs = selected_corners(state)
    return corner_values(state, refs) if refs else None


def _removal_targets(state: AppState) -> set[NodeRef]:
    """Selected nodes with the Node tool, else every node of the selected paths."""
    if state.active_tool is Tool.NODE and state.node_selection:
        refs = set(state.node_selection)
    else:
        refs = {(path.id, index) for path in _paths(state).values() for index in range(len(path.segments))}
    paths = _paths(state)
    return {
        (shape_id, index)
        for shape_id, index in refs
        if shape_id in paths
        and index < len(paths[shape_id].segments)
        and getattr(paths[shape_id].segments[index], "rounding", None) is not None
    }


@operation(
    "path.remove_corners",
    N_("Remove Corner &Rounding"),
    can_run=lambda session: bool(_removal_targets(session.state)),
)
def remove_corners(session: Session) -> None:
    refs = _removal_targets(session.state)
    if not refs:
        return
    state = session.state
    paths = _paths(state)
    with session.edit(_("Remove corner rounding")):
        for shape_id in {shape_id for shape_id, _index in refs}:
            path = paths[shape_id]
            indices = {index for owner, index in refs if owner == shape_id}
            replace_shape(state, replace(path, segments=_with_roundings(path.segments, indices, lambda _old: None)))
        state.status_message = _("Removed corner rounding")


def _rounded_paths(state: AppState) -> list[PathShape]:
    return [path for path in _paths(state).values() if corners.has_rounding(path.segments)]


@operation(
    "path.apply_corners",
    N_("Appl&y Corner Rounding"),
    can_run=lambda session: bool(_rounded_paths(session.state)),
)
def apply_corners(session: Session) -> None:
    """Bakes the rounded outline into real nodes; the corners can't be changed as live corners afterwards."""
    targets = _rounded_paths(session.state)
    if not targets:
        return
    state = session.state
    with session.edit(_("Apply corner rounding")):
        for path in targets:
            replace_shape(state, replace(path, segments=corners.rounded(path.segments)))
        state.node_selection = frozenset(ref for ref in state.node_selection if ref[0] not in {p.id for p in targets})
        state.status_message = _("Applied corner rounding")
