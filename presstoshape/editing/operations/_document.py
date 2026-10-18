"""Small document edits shared by operation modules. Call them inside `session.edit()`."""

from collections.abc import Callable, Iterable, Mapping, Sequence

from presstoshape.editing import containers, queries
from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import PartMode, Shape


def new_id(state: AppState) -> int:
    document = state.document
    document.next_id += 1
    return document.next_id - 1


def replace_shape(state: AppState, updated: Shape) -> None:
    containers.change_container(
        state, lambda shapes: [updated if shape.id == updated.id else shape for shape in shapes]
    )


def remove_shapes(state: AppState, ids: Iterable[int]) -> None:
    doomed = set(ids)
    containers.change_container(state, lambda shapes: [shape for shape in shapes if shape.id not in doomed])


def map_selected(state: AppState, change: Callable[[Shape], Shape]) -> None:
    selection = state.selection
    containers.change_container(
        state, lambda shapes: [change(shape) if shape.id in selection else shape for shape in shapes]
    )


def prune_selection(state: AppState) -> None:
    state.selection = {shape.id for shape in queries.pickable_shapes(state)} & state.selection


def replace_with(
    state: AppState,
    targets: Sequence[Shape],
    new_shapes: Sequence[Shape],
    modes: Mapping[int, PartMode] | None = None,
) -> None:
    """Removes `targets` and puts `new_shapes` where the bottom-most target was (its layer and z-order, or its place
    among a Composite's parts; `modes` sets the new shapes' part modes there)."""
    bottom = targets[0]
    consumed = {shape.id for shape in targets}
    if modes is None and (inherited := containers.part_mode(state, bottom.id)) is not None:
        modes = {shape.id: inherited for shape in new_shapes}

    def replace_in(shapes: list[Shape]) -> list[Shape]:
        kept: list[Shape] = []
        for shape in shapes:
            if shape.id == bottom.id:
                kept.extend(new_shapes)
            elif shape.id not in consumed:
                kept.append(shape)
        return kept

    containers.change_container(state, replace_in, modes)
