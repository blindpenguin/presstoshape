"""Aligning and distributing the selected objects, by their geometric bounds (the selection frame's box)."""

from collections.abc import Callable

from presstoshape.editing import queries
from presstoshape.editing.operations._document import map_selected
from presstoshape.editing.registry import register
from presstoshape.editing.session import Session
from presstoshape.geometry import align as layout
from presstoshape.geometry import transforms
from presstoshape.geometry.boxes import Point, Rect
from presstoshape.i18n import N_, _
from presstoshape.models.layout import AlignReference
from presstoshape.models.shapes import Shape
from presstoshape.render.paths import PathCache

# Edge -> (command id, menu label, undo label).
ALIGN_COMMANDS: dict[layout.AlignEdge, tuple[str, str, str]] = {
    "left": ("object.align_left", N_("&Left"), N_("Align left")),
    "hcenter": ("object.align_hcenter", N_("Centre &Horizontally"), N_("Align centres horizontally")),
    "right": ("object.align_right", N_("&Right"), N_("Align right")),
    "top": ("object.align_top", N_("&Top"), N_("Align top")),
    "vcenter": ("object.align_vcenter", N_("Centre &Vertically"), N_("Align centres vertically")),
    "bottom": ("object.align_bottom", N_("&Bottom"), N_("Align bottom")),
}
DISTRIBUTE_COMMANDS: dict[layout.DistributeMode, tuple[str, str, str]] = {
    "gaps_x": ("object.distribute_x", N_("Distribute &Horizontally"), N_("Distribute horizontally")),
    "gaps_y": ("object.distribute_y", N_("Distribute &Vertically"), N_("Distribute vertically")),
    "centers_x": (
        "object.distribute_centers_x",
        N_("Distribute &Centres Horizontally"),
        N_("Distribute centres horizontally"),
    ),
    "centers_y": (
        "object.distribute_centers_y",
        N_("Distribute C&entres Vertically"),
        N_("Distribute centres vertically"),
    ),
}


def _box(shape: Shape, cache: PathCache) -> Rect:
    bounds = cache.geometry_bounds(shape)
    return bounds.left(), bounds.top(), bounds.width(), bounds.height()


def _apply(session: Session, selected: list[Shape], offsets: list[Point], label: str) -> None:
    moves = {shape.id: offset for shape, offset in zip(selected, offsets) if offset != (0.0, 0.0)}
    if not moves:
        return

    def moved(shape: Shape) -> Shape:
        if shape.id not in moves:
            return shape
        return transforms.translate(shape, *moves[shape.id])

    with session.edit(label):
        map_selected(session.state, moved)
        session.state.status_message = label


def align(session: Session, edge: layout.AlignEdge) -> None:
    """Lines up the selected objects' edge or centre with the selection's bounds, or with the artboard (always so
    for a single object)."""
    state = session.state
    selected = queries.selected_shapes(state)
    if not selected:
        return
    cache = PathCache()
    boxes = [_box(shape, cache) for shape in selected]
    if state.align_reference == "artboard" or len(selected) == 1:
        reference: Rect = (0.0, 0.0, state.document.width, state.document.height)
    else:
        reference = layout.union(boxes)
    _apply(session, selected, layout.align_offsets(boxes, edge, reference), _(ALIGN_COMMANDS[edge][2]))


def distribute(session: Session, mode: layout.DistributeMode) -> None:
    """Spaces three or more selected objects evenly; the outermost two stay."""
    selected = queries.selected_shapes(session.state)
    if len(selected) < 3:
        return
    cache = PathCache()
    boxes = [_box(shape, cache) for shape in selected]
    _apply(session, selected, layout.distribute_offsets(boxes, mode), _(DISTRIBUTE_COMMANDS[mode][2]))


def set_align_reference(session: Session, reference: AlignReference) -> None:
    """What single-step alignment lines up with. View state, not a document edit."""
    if reference not in ("selection", "artboard"):
        raise ValueError(f"unknown align reference {reference!r}")
    session.state.align_reference = reference
    session.notify()


def _can_align(session: Session) -> bool:
    return bool(queries.selected_shapes(session.state))


def _can_distribute(session: Session) -> bool:
    return len(queries.selected_shapes(session.state)) >= 3


def _runner(fn: Callable[..., None], value: str) -> Callable[[Session], None]:
    return lambda session: fn(session, value)


for _edge, (_id, _label, _undo) in ALIGN_COMMANDS.items():
    register(_id, _label, _runner(align, _edge), _can_align)
for _mode, (_id, _label, _undo) in DISTRIBUTE_COMMANDS.items():
    register(_id, _label, _runner(distribute, _mode), _can_distribute)
