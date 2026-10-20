"""Adding, removing, selecting, hiding and renaming layers."""

from presstoshape.editing.operations._document import prune_selection
from presstoshape.editing.operations.edit_mode import leave_all
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.i18n import N_, _
from presstoshape.models.app_state import Layer, layer_name


@operation("layer.add", N_("Add layer"))
def add_layer(session: Session) -> None:
    state = session.state
    with session.edit(_("Add layer")):
        layers = state.document.layers
        names = {layer.name for layer in layers}
        number = len(layers) + 1
        while layer_name(number) in names:
            number += 1
        index = state.selected_layer_index + 1
        layers.insert(index, Layer(layer_name(number)))
        state.selected_layer_index = index


def remove_layer(session: Session, index: int) -> None:
    state = session.state
    layers = state.document.layers
    if len(layers) <= 1 or not 0 <= index < len(layers):
        return
    with session.edit(_("Delete layer")):
        leave_all(state)
        del layers[index]
        state.selected_layer_index = min(state.selected_layer_index, len(layers) - 1)
        prune_selection(state)


@operation("layer.remove", N_("Delete layer"), can_run=lambda session: len(session.state.document.layers) > 1)
def remove_current_layer(session: Session) -> None:
    remove_layer(session, session.state.selected_layer_index)


def select_layer(session: Session, index: int) -> None:
    state = session.state
    if index == state.selected_layer_index or not 0 <= index < len(state.document.layers):
        return
    leave_all(state)
    state.selected_layer_index = index
    session.notify()


def set_layer_visible(session: Session, index: int, visible: bool) -> None:
    state = session.state
    layer = state.document.layers[index]
    if layer.visible == visible:
        return
    with session.edit(_("Show layer") if visible else _("Hide layer")):
        leave_all(state)
        layer.visible = visible
        prune_selection(state)


def rename_layer(session: Session, index: int, name: str) -> None:
    layer = session.state.document.layers[index]
    name = name.strip()
    if name and name != layer.name:
        with session.edit(_("Rename layer")):
            layer.name = name
        return
    # Notify even when rejected so the view drops an empty/whitespace edit.
    session.notify()
