"""Hiding, showing, locking and unlocking objects, and picking one from the object tree."""

from collections.abc import Callable
from dataclasses import replace

from presstoshape.editing import containers, object_tree, queries
from presstoshape.editing.operations._document import drop_unpickable, map_selected
from presstoshape.editing.operations.edit_mode import enter_path
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.i18n import N_, _, ngettext
from presstoshape.models.shapes import ImageShape, Shape


def _has_selection(session: Session) -> bool:
    return bool(session.state.selection)


def _flag_selection(session: Session, label: str, flag: str, message: Callable[[int], str]) -> None:
    state = session.state
    count = len(state.selection)
    if not count:
        return
    with session.edit(label):
        map_selected(state, lambda shape: replace(shape, **{flag: True}))
        state.selection = set()
        drop_unpickable(state)
        state.status_message = message(count)


def _clear_everywhere(session: Session, label: str, flag: str, message: Callable[[int], str]) -> None:
    """Clears `flag` on every shape in the document; those now pickable become the selection."""
    state = session.state
    with session.edit(label):
        cleared = containers.map_shapes(
            state, lambda shape: replace(shape, **{flag: False}) if getattr(shape, flag) else shape
        )
        drop_unpickable(state)
        pickable = {shape.id for shape in queries.pickable_shapes(state)}
        state.selection = {shape.id for shape in cleared} & pickable
        state.node_selection = frozenset()
        state.status_message = message(len(cleared))


def _nothing_to(session: Session, message: str) -> None:
    session.state.status_message = message
    session.notify()


@operation("object.hide", N_("H&ide Selection"), can_run=_has_selection)
def hide_selection(session: Session) -> None:
    _flag_selection(
        session,
        _("Hide"),
        "hidden",
        lambda count: ngettext(
            "{count} object hidden. Object → Show All brings it back",
            "{count} objects hidden. Object → Show All brings them back",
            count,
        ).format(count=count),
    )


@operation("object.show_all", N_("&Show All"), can_run=lambda session: queries.any_hidden(session.state))
def show_all(session: Session) -> None:
    if not queries.any_hidden(session.state):
        _nothing_to(session, _("Nothing to show"))
        return
    _clear_everywhere(
        session,
        _("Show all"),
        "hidden",
        lambda count: ngettext("{count} object shown", "{count} objects shown", count).format(count=count),
    )


@operation("object.lock", N_("L&ock Selection"), can_run=_has_selection)
def lock_selection(session: Session) -> None:
    _flag_selection(
        session,
        _("Lock"),
        "locked",
        lambda count: ngettext(
            "{count} object locked. Object → Unlock All unlocks it",
            "{count} objects locked. Object → Unlock All unlocks them",
            count,
        ).format(count=count),
    )


@operation("object.unlock_all", N_("U&nlock All"), can_run=lambda session: queries.any_locked(session.state))
def unlock_all(session: Session) -> None:
    if not queries.any_locked(session.state):
        _nothing_to(session, _("Nothing to unlock"))
        return
    _clear_everywhere(
        session,
        _("Unlock all"),
        "locked",
        lambda count: ngettext("{count} object unlocked", "{count} objects unlocked", count).format(count=count),
    )


def _set_flag(session: Session, shape_id: int, label: str, change: Callable[[Shape], Shape]) -> None:
    state = session.state
    with session.edit(label):
        containers.map_shapes(state, lambda shape: change(shape) if shape.id == shape_id else shape)
        drop_unpickable(state)


def set_hidden(session: Session, shape_id: int, hidden: bool) -> None:
    """Hides or shows one object anywhere in the document (the tree's eye). Unknown ids do nothing."""
    shape = queries.find_shape(session.state, shape_id)
    if shape is None or shape.hidden == hidden:
        return
    _set_flag(session, shape_id, _("Hide") if hidden else _("Show"), lambda shape: replace(shape, hidden=hidden))


def set_locked(session: Session, shape_id: int, locked: bool) -> None:
    """Locks or unlocks one object anywhere in the document (the tree's lock). Unknown ids do nothing."""
    shape = queries.find_shape(session.state, shape_id)
    if shape is None or shape.locked == locked:
        return
    _set_flag(session, shape_id, _("Lock") if locked else _("Unlock"), lambda shape: replace(shape, locked=locked))


def select_object(session: Session, shape_id: int, extend: bool = False) -> None:
    """Selects an object from the tree: activates its layer, enters the containers around it and selects it.
    `extend` adds it to the selection when it is in the active container. Objects hidden or locked themselves or
    by their layer or containers, and ids that are gone, do nothing. Not an undo step."""
    state = session.state
    location = object_tree.locate(state, shape_id)
    if location is None:
        return
    shape = queries.find_shape(state, shape_id)
    # A reference image is locked by design; the tree can still select it to make it artwork again.
    held = not (isinstance(shape, ImageShape) and shape.reference)
    if shape.hidden or (held and (shape.locked or any(object_tree.inherited_flags(state, location)))):
        return
    state.selected_layer_index = location.layer_index
    same_container = containers.valid_edit_path(state) == location.containers
    if not same_container:
        enter_path(state, location.containers)
    state.selection = {*state.selection, shape_id} if extend and same_container else {shape_id}
    state.node_selection = frozenset()
    session.end_merge()
    session.notify()
