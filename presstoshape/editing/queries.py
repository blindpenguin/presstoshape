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


def shown_shapes(state: AppState) -> list[Shape]:
    """Drawn shapes of the active container (locked ones included), bottom to top."""
    return containers.shown_shapes(state)


def selected_shapes(state: AppState) -> list[Shape]:
    """Selected shapes in paint order, bottom first."""
    selection = state.selection
    # Asked several times per frame: the flags are checked only for selected shapes.
    return [
        shape
        for shape in containers.active_shapes(state)
        if shape.id in selection and not shape.hidden and not shape.locked
    ]


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


class _FlagMemo:
    """Whether any shape in the document has a flag, remembered for one document content: menus ask on every
    notify, and shapes are frozen, so the same layer contents give the same answer."""

    def __init__(self, flag: str) -> None:
        self._flag = flag
        self._content: tuple[tuple[Shape, ...], ...] | None = None
        self._answer = False

    def __call__(self, state: AppState) -> bool:
        content = tuple(tuple(layer.shapes) for layer in state.document.layers)
        if not _same_content(content, self._content):
            self._content, self._answer = content, _any_flagged(content, self._flag)
        return self._answer


def _same_content(content: tuple[tuple[Shape, ...], ...], known: tuple[tuple[Shape, ...], ...] | None) -> bool:
    return (
        known is not None
        and len(content) == len(known)
        and all(
            len(shapes) == len(known_shapes) and all(a is b for a, b in zip(shapes, known_shapes))
            for shapes, known_shapes in zip(content, known)
        )
    )


def _any_flagged(content: tuple[tuple[Shape, ...], ...], flag: str) -> bool:
    pending = [shape for shapes in content for shape in shapes]
    while pending:
        shape = pending.pop()
        if getattr(shape, flag):
            return True
        pending.extend(children_of(shape))
    return False


# Whether any shape (inside containers too, in any layer) is hidden / locked.
any_hidden = _FlagMemo("hidden")
any_locked = _FlagMemo("locked")
