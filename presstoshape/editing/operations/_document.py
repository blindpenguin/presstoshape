"""Small document edits shared by operation modules. Call them inside `session.edit()`."""

from collections.abc import Callable, Iterable

from presstoshape.editing import queries
from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import Shape


def new_id(state: AppState) -> int:
    document = state.document
    document.next_id += 1
    return document.next_id - 1


def replace_shape(state: AppState, updated: Shape) -> None:
    for layer in state.document.layers:
        layer.shapes = [updated if shape.id == updated.id else shape for shape in layer.shapes]


def remove_shapes(state: AppState, ids: Iterable[int]) -> None:
    doomed = set(ids)
    for layer in state.document.layers:
        layer.shapes = [shape for shape in layer.shapes if shape.id not in doomed]


def map_selected(state: AppState, change: Callable[[Shape], Shape]) -> None:
    selection = state.selection
    for layer in state.document.layers:
        layer.shapes = [change(shape) if shape.id in selection else shape for shape in layer.shapes]


def prune_selection(state: AppState) -> None:
    state.selection = {shape.id for shape in queries.visible_shapes(state)} & state.selection
