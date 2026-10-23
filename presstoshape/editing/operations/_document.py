"""Small document edits shared by operation modules. Call them inside `session.edit()`."""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace

from presstoshape.editing import containers, queries
from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import CompositeShape, GroupShape, PartMode, Shape


def new_id(state: AppState) -> int:
    document = state.document
    document.next_id += 1
    return document.next_id - 1


def with_fresh_ids(state: AppState, shapes: Sequence[Shape]) -> list[Shape]:
    """The same shapes with new ids from the document, Composite parts and group children included (copies must
    never share ids)."""

    def renumbered(shape: Shape) -> Shape:
        if isinstance(shape, CompositeShape):
            return replace(shape, id=new_id(state), parts=tuple(renumbered(part) for part in shape.parts))
        if isinstance(shape, GroupShape):
            group_id = new_id(state)
            children = tuple(renumbered(child) for child in shape.children)
            masking = shape.masking
            if masking is not None:
                new_ids = {old.id: new.id for old, new in zip(shape.children, children)}
                masking = replace(masking, mask_ids=tuple(new_ids[i] for i in masking.mask_ids if i in new_ids))
            return replace(shape, id=group_id, children=children, masking=masking)
        return replace(shape, id=new_id(state))

    return [renumbered(shape) for shape in shapes]


def add_on_top(state: AppState, shapes: Sequence[Shape], modes: Mapping[int, PartMode] | None = None) -> None:
    """Adds `shapes` on top of the active container: the entered Composite's parts (in `modes` or the new-part
    mode), else the active layer, also when it is hidden."""
    if containers.editing(state):
        containers.change_container(state, lambda current: [*current, *shapes], modes)
    else:
        queries.active_layer(state).shapes.extend(shapes)


def insert_copies(state: AppState, copies: Mapping[int, Shape], modes: Mapping[int, PartMode] | None = None) -> None:
    """Inserts each copy (keyed by its original's id) into its original's container, all of a container's copies
    directly above its topmost original, in the originals' order."""

    def insert(shapes: list[Shape]) -> list[Shape]:
        originals = [index for index, shape in enumerate(shapes) if shape.id in copies]
        if not originals:
            return shapes
        top = originals[-1]
        return [*shapes[: top + 1], *(copies[shapes[index].id] for index in originals), *shapes[top + 1 :]]

    containers.change_container(state, insert, modes)


def delete_selected(state: AppState) -> None:
    """Removes the selected shapes and clears the selection. A group or Composite left empty goes too and its
    edit mode closes (see containers.change_container)."""
    remove_shapes(state, state.selection)
    state.selection = set()


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


def drop_unpickable(state: AppState) -> None:
    """After hiding or locking: leaves entered containers that can't be picked any more, and drops selected
    shapes and nodes that can't either."""
    state.edit_path = containers.valid_edit_path(state)
    prune_selection(state)
    state.node_selection = frozenset(ref for ref in state.node_selection if ref[0] in state.selection)


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
