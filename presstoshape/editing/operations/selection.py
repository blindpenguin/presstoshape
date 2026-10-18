"""Selecting, moving and deleting the selected shapes."""

from presstoshape.editing import containers, queries
from presstoshape.editing.operations import node_editing
from presstoshape.editing.operations._document import map_selected, remove_shapes
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.geometry import transforms
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


@operation("edit.select_all", "Select &All")
def select_all(session: Session) -> None:
    set_selection(session, {shape.id for shape in queries.pickable_shapes(session.state)})


def move_selection(session: Session, dx: float, dy: float) -> None:
    state = session.state
    if not state.selection or (dx, dy) == (0, 0):
        return
    count = len(state.selection)
    with session.edit(f"Move {count} object(s)"):
        map_selected(state, lambda shape: transforms.translate(shape, dx, dy))
        state.status_message = f"Moved {count} object(s)"


@operation("edit.delete", "&Delete", can_run=lambda session: bool(session.state.selection))
def delete_selection(session: Session) -> None:
    """Deletes the selected shapes, or under the Node tool the selected nodes."""
    state = session.state
    if state.active_tool is Tool.NODE and state.node_selection:
        node_editing.delete_nodes(session)
        return
    selection = state.selection
    if not selection:
        return
    with session.edit(f"Delete {len(selection)} object(s)"):
        remove_shapes(state, selection)
        state.status_message = f"Deleted {len(selection)} object(s)"
        state.selection = set()
        composite = containers.edited_composite(state)
        if composite is not None and not composite.parts:
            # The last part went, so the Composite goes too and its edit mode closes.
            state.edit_path = state.edit_path[:-1]
            remove_shapes(state, {composite.id})
