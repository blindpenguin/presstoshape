"""The active container: what operations and tools work on.

Outside edit mode that's the shapes in the layers, as always. Inside a Composite's edit mode it's the parts of the
innermost entered Composite. Shapes are frozen, so changing a part means rebuilding that Composite, every
Composite around it and finally the top-level one in its layer; `change_container` does that in one place.
"""

from collections.abc import Callable, Mapping
from dataclasses import replace

from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import CompositeShape, PartMode, Shape


def edit_chain(state: AppState) -> list[CompositeShape]:
    """The entered Composites, outer to inner, as far as `edit_path` still leads to existing ones."""
    chain: list[CompositeShape] = []
    candidates = [shape for layer in state.document.layers if layer.visible for shape in layer.shapes]
    for composite_id in state.edit_path:
        found = next(
            (shape for shape in candidates if shape.id == composite_id and isinstance(shape, CompositeShape)), None
        )
        if found is None:
            break
        chain.append(found)
        candidates = list(found.parts)
    return chain


def valid_edit_path(state: AppState) -> tuple[int, ...]:
    return tuple(composite.id for composite in edit_chain(state))


def edited_composite(state: AppState) -> CompositeShape | None:
    chain = edit_chain(state)
    return chain[-1] if chain else None


def part_mode(state: AppState, part_id: int) -> PartMode | None:
    """Mode of a part of the edited Composite, or None outside edit mode / for unknown ids."""
    composite = edited_composite(state)
    if composite is None:
        return None
    return dict(zip((part.id for part in composite.parts), composite.modes)).get(part_id)


def editing(state: AppState) -> bool:
    return edited_composite(state) is not None


def container_lists(state: AppState) -> list[list[Shape]]:
    """Shape lists an operation may change: every layer's (hidden ones too, as before) or the edited parts."""
    composite = edited_composite(state)
    if composite is not None:
        return [list(composite.parts)]
    return [list(layer.shapes) for layer in state.document.layers]


def pickable_shapes(state: AppState) -> list[Shape]:
    """What the user can select right now, bottom to top: visible layer shapes, or the edited parts."""
    composite = edited_composite(state)
    if composite is not None:
        return list(composite.parts)
    return [shape for layer in state.document.layers if layer.visible for shape in layer.shapes]


def change_container(
    state: AppState,
    change: Callable[[list[Shape]], list[Shape]],
    modes: Mapping[int, PartMode] | None = None,
) -> None:
    """Applies `change` to each container list and writes the results back.

    In edit mode, parts keep their mode by id; new parts get `modes[id]` if given, else `state.new_part_mode`.
    """
    chain = edit_chain(state)
    if not chain:
        for layer in state.document.layers:
            layer.shapes = change(list(layer.shapes))
        return
    innermost = chain[-1]
    updated = with_parts(innermost, change(list(innermost.parts)), state.new_part_mode, modes)
    for parent in reversed(chain[:-1]):
        updated = replace(parent, parts=tuple(updated if part.id == updated.id else part for part in parent.parts))
    for layer in state.document.layers:
        layer.shapes = [updated if shape.id == updated.id else shape for shape in layer.shapes]


def with_parts(
    composite: CompositeShape,
    parts: list[Shape],
    default_mode: PartMode,
    modes: Mapping[int, PartMode] | None = None,
) -> CompositeShape:
    """`composite` with new parts; existing parts keep their mode, new ones get `modes[id]` or `default_mode`."""
    known = dict(zip((part.id for part in composite.parts), composite.modes))
    if modes:
        known.update(modes)
    return replace(composite, parts=tuple(parts), modes=tuple(known.get(part.id, default_mode) for part in parts))
