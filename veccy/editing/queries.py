"""Read-only questions about an AppState, shared by operations, tools and views."""

from collections.abc import Iterator

from veccy.geometry import transforms
from veccy.models.app_state import AppState, Layer
from veccy.models.shapes import EllipseShape, RectShape, Shape, TextShape


def active_layer(state: AppState) -> Layer:
    return state.document.layers[state.selected_layer_index]


def visible_shapes(state: AppState) -> Iterator[Shape]:
    """Paint order: visible layers bottom to top."""
    for layer in state.document.layers:
        if layer.visible:
            yield from layer.shapes


def selected_shapes(state: AppState) -> list[Shape]:
    """Selected shapes in paint order, bottom first."""
    return [shape for shape in visible_shapes(state) if shape.id in state.selection]


def find_shape(state: AppState, shape_id: int) -> Shape | None:
    for layer in state.document.layers:
        for shape in layer.shapes:
            if shape.id == shape_id:
                return shape
    return None


def can_combine(state: AppState) -> bool:
    return sum(transforms.outline(shape) is not None for shape in selected_shapes(state)) >= 2


def can_object_to_path(state: AppState) -> bool:
    return any(isinstance(shape, (RectShape, EllipseShape, TextShape)) for shape in selected_shapes(state))
