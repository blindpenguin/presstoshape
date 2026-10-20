"""Read-only questions about an AppState, shared by operations, tools and views."""

from collections.abc import Iterator

from presstoshape.editing import containers
from presstoshape.geometry import transforms
from presstoshape.models.app_state import AppState, Layer
from presstoshape.models.shapes import CompositeShape, EllipseShape, RectShape, Shape, TextShape, children_of


def active_layer(state: AppState) -> Layer:
    return state.document.layers[state.selected_layer_index]


def visible_shapes(state: AppState) -> Iterator[Shape]:
    """Paint order: visible layers bottom to top (document level; parts of Composites are not listed)."""
    for layer in state.document.layers:
        if layer.visible:
            yield from layer.shapes


def pickable_shapes(state: AppState) -> list[Shape]:
    """What the user can select right now, bottom to top: visible layer shapes, or the edited Composite's parts."""
    return containers.pickable_shapes(state)


def selected_shapes(state: AppState) -> list[Shape]:
    """Selected shapes in paint order, bottom first."""
    return [shape for shape in pickable_shapes(state) if shape.id in state.selection]


def find_shape(state: AppState, shape_id: int) -> Shape | None:
    """Any shape by id, including parts of Composites and children of groups."""
    pending = [shape for layer in state.document.layers for shape in layer.shapes]
    while pending:
        shape = pending.pop()
        if shape.id == shape_id:
            return shape
        pending.extend(children_of(shape))
    return None


def can_combine(state: AppState) -> bool:
    return sum(transforms.outline(shape) is not None for shape in selected_shapes(state)) >= 2


def can_object_to_path(state: AppState) -> bool:
    return any(
        isinstance(shape, (RectShape, EllipseShape, TextShape, CompositeShape)) for shape in selected_shapes(state)
    )
