"""Composites: make, release and flatten them, enter and leave their edit mode, and set part modes."""

from presstoshape.editing import containers, queries
from presstoshape.editing.operations._document import map_selected, new_id, prune_selection, replace_with
from presstoshape.editing.registry import operation, register
from presstoshape.editing.session import Session
from presstoshape.geometry import transforms
from presstoshape.i18n import N_, _, pgettext
from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import CompositeShape, PartMode, PathShape, Shape

PART_MODES: tuple[PartMode, ...] = ("add", "subtract", "intersect", "exclude")


def mode_label(mode: PartMode) -> str:
    labels = {
        "add": pgettext("part mode", "Add"),
        "subtract": pgettext("part mode", "Subtract"),
        "intersect": pgettext("part mode", "Intersect"),
        "exclude": pgettext("part mode", "Exclude"),
    }
    return labels[mode]


def _selected_composites(state: AppState) -> list[CompositeShape]:
    return [shape for shape in queries.selected_shapes(state) if isinstance(shape, CompositeShape)]


def _can_make(session: Session) -> bool:
    return queries.can_combine(session.state)


def _has_composite(session: Session) -> bool:
    return bool(_selected_composites(session.state))


# --- make / release / flatten ---------------------------------------------------------


def make_composite(session: Session, mode: PartMode = "add") -> None:
    """Turns the selected outlines into a Composite: bottom one as base, every other part in `mode`. Inside edit
    mode the new Composite is nested in place and takes the bottom part's mode there."""
    state = session.state
    if queries.selection_has_image(state):
        state.status_message = _("Images cannot be part of a Composite")
        session.notify()
        return
    targets = queries.combinable_shapes(state)
    if len(targets) < 2:
        return
    with session.edit(_("Make Composite")):
        modes = ("add",) + (mode,) * (len(targets) - 1)
        composite = CompositeShape(new_id(state), tuple(targets), modes, targets[0].style)
        replace_with(state, targets, [composite])
        state.selection = {composite.id}
        state.status_message = _("Made a Composite (double-click to edit it)")


register("path.make_composite", N_("Make &Composite"), make_composite, _can_make)
# Menu entries of the Make Composite As submenu.
_MAKE_AS_LABELS: dict[PartMode, str] = {
    "add": N_("&Add"),
    "subtract": N_("&Subtract"),
    "intersect": N_("&Intersect"),
    "exclude": N_("&Exclude"),
}
for _mode, _label in _MAKE_AS_LABELS.items():
    register(
        f"path.make_composite_{_mode}",
        _label,
        lambda session, mode=_mode: make_composite(session, mode),
        _can_make,
    )


@operation("path.release_composite", N_("&Release Composite"), can_run=_has_composite)
def release_composite(session: Session) -> None:
    """Replaces each selected Composite by its parts, in place and with their own styles."""
    state = session.state
    composites = _selected_composites(state)
    if not composites:
        return
    with session.edit(_("Release Composite")):
        released: dict[int, CompositeShape] = {composite.id: composite for composite in composites}
        modes: dict[int, PartMode] = {}
        for composite in composites:
            # Inside a parent Composite the base inherits the released Composite's mode there; others keep theirs.
            outer_mode = containers.part_mode(state, composite.id)
            modes.update(zip((part.id for part in composite.parts[1:]), composite.modes[1:]))
            if outer_mode is not None:
                modes[composite.parts[0].id] = outer_mode

        def unpack(shapes: list[Shape]) -> list[Shape]:
            result: list[Shape] = []
            for shape in shapes:
                result.extend(released[shape.id].parts if shape.id in released else [shape])
            return result

        containers.change_container(state, unpack, modes if containers.edited_composite(state) else None)
        state.selection = {part.id for composite in composites for part in composite.parts}
        prune_selection(state)
        state.status_message = _("Released the Composite")


def _flatten(shape: Shape) -> Shape:
    if isinstance(shape, CompositeShape):
        return PathShape(shape.id, transforms.outline(shape) or (), shape.style)
    return shape


@operation("path.flatten_composite", N_("&Flatten Composite"), can_run=_has_composite)
def flatten_composite(session: Session) -> None:
    """Bakes each selected Composite into a plain path with its result outline and style."""
    state = session.state
    if not _selected_composites(state):
        return
    with session.edit(_("Flatten Composite")):
        map_selected(state, _flatten)
        state.status_message = _("Flattened the Composite")


# --- edit mode ---------------------------------------------------------------------------


def set_part_mode(session: Session, mode: PartMode) -> None:
    """Changes the mode of the selected parts of the edited Composite; the base part is skipped."""
    state = session.state
    composite = containers.edited_composite(state)
    if composite is None:
        return
    base_id = composite.parts[0].id
    targets = [
        part.id
        for part, current in zip(composite.parts, composite.modes)
        if part.id in state.selection and part.id != base_id and current != mode
    ]
    if not targets:
        return
    with session.edit(_("Change mode")):
        containers.change_container(state, lambda parts: parts, {part_id: mode for part_id in targets})
        state.status_message = _("Mode: {mode}").format(mode=mode_label(mode))


def set_new_part_mode(session: Session, mode: PartMode) -> None:
    """Mode for parts drawn in edit mode. Not a document edit."""
    session.state.new_part_mode = mode
    session.notify()
