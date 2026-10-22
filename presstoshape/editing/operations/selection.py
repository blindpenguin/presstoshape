"""Selecting, moving and deleting the selected shapes."""

from presstoshape.editing import queries
from presstoshape.editing.operations import node_editing
from presstoshape.editing.operations._document import delete_selected, map_selected
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.geometry import transforms
from presstoshape.i18n import N_, ngettext
from presstoshape.models.app_state import Tool


def set_selection(session: Session, ids: set[int]) -> None:
    state = session.state
    selection = {shape.id for shape in queries.pickable_shapes(state)} & set(ids)
    if selection == state.selection:
        return
    state.selection = selection
    state.node_selection = frozenset()
    session.end_merge()
    session.notify()


@operation("edit.select_all", N_("Select &All"))
def select_all(session: Session) -> None:
    set_selection(session, {shape.id for shape in queries.pickable_shapes(session.state)})


def move_selection(session: Session, dx: float, dy: float) -> None:
    state = session.state
    if not state.selection or (dx, dy) == (0, 0):
        return
    count = len(state.selection)
    with session.edit(ngettext("Move {count} object", "Move {count} objects", count).format(count=count)):
        map_selected(state, lambda shape: transforms.translate(shape, dx, dy))
        state.status_message = ngettext("Moved {count} object", "Moved {count} objects", count).format(count=count)


@operation("edit.delete", N_("&Delete"), can_run=lambda session: bool(session.state.selection))
def delete_selection(session: Session) -> None:
    """Deletes the selected shapes, or under the Node tool the selected nodes."""
    state = session.state
    if state.active_tool is Tool.NODE and state.node_selection:
        node_editing.delete_nodes(session)
        return
    selection = state.selection
    if not selection:
        return
    count = len(selection)
    with session.edit(ngettext("Delete {count} object", "Delete {count} objects", count).format(count=count)):
        delete_selected(state)
        state.status_message = ngettext("Deleted {count} object", "Deleted {count} objects", count).format(count=count)
