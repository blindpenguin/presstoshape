"""Boolean commands on the selection: union, difference, intersection, exclude and divide. All destructive."""


import pathops

from presstoshape.editing import queries
from presstoshape.editing.operations._document import new_id, replace_with
from presstoshape.editing.registry import register
from presstoshape.editing.session import Session
from presstoshape.geometry import booleans, transforms
from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import PathShape, Shape

# Command -> (mode applied to every shape above the bottom one, name shown in undo and status).
OPERATIONS: dict[str, tuple[booleans.Mode, str]] = {
    "union": ("add", "Union"),
    "difference": ("subtract", "Difference"),
    "intersection": ("intersect", "Intersection"),
    "exclude": ("exclude", "Exclude"),
}


def _targets(state: AppState) -> list[Shape]:
    """Selected shapes with a vector outline, bottom to top."""
    return [shape for shape in queries.selected_shapes(state) if transforms.outline(shape) is not None]


def combine(session: Session, op: str) -> None:
    if op not in OPERATIONS:
        raise ValueError(f"unknown boolean op {op!r}")
    mode, name = OPERATIONS[op]
    state = session.state
    targets = _targets(state)
    if len(targets) < 2:
        return
    try:
        segments = booleans.combine_parts([(transforms.outline(shape), mode) for shape in targets])
    except pathops.PathOpsError:
        _report_failure(session, name)
        return
    with session.edit(name):
        result = [PathShape(new_id(state), segments, targets[0].style)] if segments else []
        replace_with(state, targets, result)
        state.selection = {shape.id for shape in result}
        state.status_message = name if result else f"{name} is empty"


def divide_selection(session: Session) -> None:
    """Splits the selected shapes along all their edges; each piece keeps the style it showed before."""
    state = session.state
    targets = _targets(state)
    if len(targets) < 2:
        return
    try:
        pieces = booleans.divide([transforms.outline(shape) for shape in targets])
    except pathops.PathOpsError:
        _report_failure(session, "Divide")
        return
    # Pieces of higher shapes stay above pieces of lower ones.
    pieces.sort(key=lambda piece: piece[1])
    with session.edit("Divide"):
        result = [PathShape(new_id(state), segments, targets[top].style) for segments, top in pieces]
        replace_with(state, targets, result)
        state.selection = {shape.id for shape in result}
        state.status_message = f"Divided into {len(result)} pieces"


def _report_failure(session: Session, name: str) -> None:
    session.state.status_message = f"{name} failed"
    session.notify()


def _can_combine(session: Session) -> bool:
    return queries.can_combine(session.state)


register("path.union", "&Union", lambda session: combine(session, "union"), _can_combine)
register("path.difference", "D&ifference", lambda session: combine(session, "difference"), _can_combine)
register("path.intersection", "&Intersection", lambda session: combine(session, "intersection"), _can_combine)
register("path.exclude", "E&xclude", lambda session: combine(session, "exclude"), _can_combine)
register("path.divide", "Di&vide", divide_selection, _can_combine)
