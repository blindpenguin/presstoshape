"""The active container: what operations and tools work on.

Outside edit mode that's the shapes in the layers, as always. Inside an entered Composite or group it's the parts
or children of the innermost entered one. Shapes are frozen, so changing a shape inside means rebuilding that
container, every container around it and finally the top-level one in its layer; `change_container` does that in
one place.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace

from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import CompositeShape, ContainerShape, GroupShape, PartMode, Shape, children_of


def edit_chain(state: AppState) -> list[ContainerShape]:
    """The entered Composites and groups, outer to inner, as far as `edit_path` still leads to existing ones that
    could be picked: a container that got hidden or locked, or whose layer did, ends the chain."""
    chain: list[ContainerShape] = []
    candidates: Iterable[Shape] = (
        shape for layer in state.document.layers if layer.visible and not layer.locked for shape in layer.shapes
    )
    for container_id in state.edit_path:
        found = next(
            (
                shape
                for shape in candidates
                if shape.id == container_id
                and isinstance(shape, (CompositeShape, GroupShape))
                and not shape.hidden
                and not shape.locked
            ),
            None,
        )
        if found is None:
            break
        chain.append(found)
        candidates = children_of(found)
    return chain


def valid_edit_path(state: AppState) -> tuple[int, ...]:
    return tuple(container.id for container in edit_chain(state))


def edited_container(state: AppState) -> ContainerShape | None:
    chain = edit_chain(state)
    return chain[-1] if chain else None


def edited_composite(state: AppState) -> CompositeShape | None:
    """The innermost entered container when it is a Composite (part modes and outline-only rules apply)."""
    container = edited_container(state)
    return container if isinstance(container, CompositeShape) else None


def part_mode(state: AppState, part_id: int) -> PartMode | None:
    """Mode of a part of the edited Composite, or None outside a Composite / for unknown ids."""
    composite = edited_composite(state)
    if composite is None:
        return None
    return dict(zip((part.id for part in composite.parts), composite.modes)).get(part_id)


def editing(state: AppState) -> bool:
    """Whether a Composite or group is entered."""
    return edited_container(state) is not None


def container_lists(state: AppState) -> list[list[Shape]]:
    """Shape lists an operation may change: every layer's (hidden ones too, as before) or the entered shapes."""
    container = edited_container(state)
    if container is not None:
        return [list(children_of(container))]
    return [list(layer.shapes) for layer in state.document.layers]


def shown_shapes(state: AppState) -> list[Shape]:
    """Drawn shapes of the active container, bottom to top: visible layers' shapes or the entered shapes, without
    hidden ones; locked ones included (they stay snap targets)."""
    container = edited_container(state)
    if container is not None:
        return [shape for shape in children_of(container) if not shape.hidden]
    return [shape for layer in state.document.layers if layer.visible for shape in layer.shapes if not shape.hidden]


def pickable_shapes(state: AppState) -> list[Shape]:
    """What the user can select right now, bottom to top: `shown_shapes` without locked ones and without the
    shapes of locked layers."""
    return [shape for shape in active_shapes(state) if not shape.hidden and not shape.locked]


def active_shapes(state: AppState) -> Sequence[Shape]:
    """The entered shapes, or the shapes of visible, unlocked layers, hidden and locked ones included. For hot
    paths that check the flags of only the few shapes they keep (see queries.selected_shapes)."""
    container = edited_container(state)
    if container is not None:
        return children_of(container)
    return [shape for layer in state.document.layers if layer.visible and not layer.locked for shape in layer.shapes]


def map_shapes(state: AppState, change: Callable[[Shape], Shape]) -> list[Shape]:
    """Applies `change` to every shape in the document, containers' insides included (a container before its
    children), rebuilding only the containers whose contents changed, so unchanged shapes keep their identity.
    Returns the shapes `change` replaced, in their final versions."""
    replaced: list[Shape] = []
    for layer in state.document.layers:
        mapped = [_mapped(shape, change, replaced) for shape in layer.shapes]
        if any(new is not old for new, old in zip(mapped, layer.shapes)):
            layer.shapes = mapped
    return replaced


def _mapped(shape: Shape, change: Callable[[Shape], Shape], replaced: list[Shape]) -> Shape:
    changed = change(shape)
    result = changed
    children = children_of(changed)
    if children:
        mapped = [_mapped(child, change, replaced) for child in children]
        if any(new is not old for new, old in zip(mapped, children)):
            # Every part keeps its id, so the mode fallback is never used.
            result = with_children(changed, mapped, "add")
    if changed is not shape:
        replaced.append(result)
    return result


def change_container(
    state: AppState,
    change: Callable[[list[Shape]], list[Shape]],
    modes: Mapping[int, PartMode] | None = None,
) -> None:
    """Applies `change` to each container list and writes the results back.

    In a Composite, parts keep their mode by id; new parts get `modes[id]` if given, else `state.new_part_mode`.
    An entered container left empty is removed, and so is every container around it that becomes empty; edit
    mode then closes to the level above them.
    """
    chain = edit_chain(state)
    if not chain:
        for layer in state.document.layers:
            layer.shapes = change(list(layer.shapes))
        return
    updated: Shape | None = with_children(chain[-1], change(list(children_of(chain[-1]))), state.new_part_mode, modes)
    depth = len(chain) - 1
    if not children_of(updated):
        updated, state.edit_path = None, state.edit_path[:depth]
    for depth in range(len(chain) - 2, -1, -1):
        parent, child_id = chain[depth], chain[depth + 1].id
        siblings = [shape for shape in children_of(parent) if shape.id != child_id or updated is not None]
        siblings = [updated if shape.id == child_id else shape for shape in siblings]
        updated = with_children(parent, siblings, state.new_part_mode) if siblings else None
        if updated is None:
            state.edit_path = state.edit_path[:depth]
    top_id = chain[0].id
    for layer in state.document.layers:
        layer.shapes = [
            updated if shape.id == top_id else shape
            for shape in layer.shapes
            if shape.id != top_id or updated is not None
        ]


def with_children(
    container: ContainerShape,
    children: list[Shape],
    default_mode: PartMode,
    modes: Mapping[int, PartMode] | None = None,
) -> ContainerShape:
    """`container` with new children; in a Composite, existing parts keep their mode and new ones get `modes[id]`
    or `default_mode`."""
    if isinstance(container, GroupShape):
        return replace(container, children=tuple(children))
    known = dict(zip((part.id for part in container.parts), container.modes))
    if modes:
        known.update(modes)
    return replace(container, parts=tuple(children), modes=tuple(known.get(part.id, default_mode) for part in children))
