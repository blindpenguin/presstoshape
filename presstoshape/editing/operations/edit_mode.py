"""Entering and leaving Composites and groups to work on the shapes inside them. Not undo steps."""

from presstoshape.editing import containers, queries
from presstoshape.editing.session import Session
from presstoshape.i18n import _
from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import CompositeShape, GroupShape, Shape


def _editing_message(container: Shape | None) -> str:
    if isinstance(container, GroupShape):
        return _("Editing a group")
    return _("Editing a Composite")


def enter(session: Session, shape_id: int) -> None:
    """Enters a Composite or group among the pickable shapes."""
    state = session.state
    target = next((shape for shape in queries.pickable_shapes(state) if shape.id == shape_id), None)
    if not isinstance(target, (CompositeShape, GroupShape)):
        return
    state.edit_path = (*containers.valid_edit_path(state), shape_id)
    state.selection = set()
    state.node_selection = frozenset()
    if isinstance(target, GroupShape):
        state.status_message = _("Editing a group: Esc or Done to leave")
    else:
        state.status_message = _("Editing a Composite: Esc or Done to leave")
    session.end_merge()
    session.notify()


def leave(session: Session, levels: int = 1) -> None:
    """Leaves `levels` deep and selects the Composite or group that was left."""
    state = session.state
    path = containers.valid_edit_path(state)
    if not path:
        return
    levels = max(1, min(levels, len(path)))
    left = path[len(path) - levels]
    state.edit_path = path[: len(path) - levels]
    state.selection = {left}
    state.node_selection = frozenset()
    state.status_message = _editing_message(containers.edited_container(state)) if state.edit_path else _("Ready")
    session.end_merge()
    session.notify()


def leave_all(state: AppState) -> None:
    """Silently closes edit mode, for operations that change what's around the entered shapes (layers,
    documents)."""
    if state.edit_path:
        state.edit_path = ()
        state.selection = set()
        state.node_selection = frozenset()
