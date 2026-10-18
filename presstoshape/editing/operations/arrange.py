"""Stacking order: z-order of shapes in their layer, evaluation order of parts inside a Composite."""

from collections.abc import Callable

from presstoshape.editing import containers, queries
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.models.shapes import Shape


def _has_selection(session: Session) -> bool:
    return bool(queries.selected_shapes(session.state))


def _raise_one_step(shapes: list[Shape], selected: set[int]) -> list[Shape]:
    """Each selected shape swaps with the nearest unselected one above it; selected neighbours move together."""
    result = list(shapes)
    for index in range(len(result) - 2, -1, -1):
        if result[index].id in selected and result[index + 1].id not in selected:
            result[index], result[index + 1] = result[index + 1], result[index]
    return result


def _lower_one_step(shapes: list[Shape], selected: set[int]) -> list[Shape]:
    return list(reversed(_raise_one_step(list(reversed(shapes)), selected)))


def _to_top(shapes: list[Shape], selected: set[int]) -> list[Shape]:
    return [shape for shape in shapes if shape.id not in selected] + [shape for shape in shapes if shape.id in selected]


def _to_bottom(shapes: list[Shape], selected: set[int]) -> list[Shape]:
    return [shape for shape in shapes if shape.id in selected] + [shape for shape in shapes if shape.id not in selected]


def _arrange(session: Session, reorder: Callable[[list[Shape], set[int]], list[Shape]], label: str) -> None:
    state = session.state
    selected = {shape.id for shape in queries.selected_shapes(state)}
    if not selected:
        return
    before = [[shape.id for shape in shapes] for shapes in containers.container_lists(state)]
    after = [[shape.id for shape in reorder(shapes, selected)] for shapes in containers.container_lists(state)]
    if before == after:
        return
    with session.edit(label):
        containers.change_container(state, lambda shapes: reorder(shapes, selected))
        state.status_message = label


@operation("object.raise", "&Raise", can_run=_has_selection)
def raise_selection(session: Session) -> None:
    _arrange(session, _raise_one_step, "Raise")


@operation("object.lower", "&Lower", can_run=_has_selection)
def lower_selection(session: Session) -> None:
    _arrange(session, _lower_one_step, "Lower")


@operation("object.raise_to_top", "Raise to &Top", can_run=_has_selection)
def raise_to_top(session: Session) -> None:
    _arrange(session, _to_top, "Raise to top")


@operation("object.lower_to_bottom", "Lower to &Bottom", can_run=_has_selection)
def lower_to_bottom(session: Session) -> None:
    _arrange(session, _to_bottom, "Lower to bottom")
