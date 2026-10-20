from presstoshape.editing.operations import layers, selection, shapes
from presstoshape.editing.session import Session


def test_hidden_layer_shapes_drop_out_of_selection_and_block_drawing():
    session = Session()
    sid = shapes.add_rectangle(session, (0, 0), (10, 10))
    layers.set_layer_visible(session, 0, False)
    assert session.state.selection == set()
    selection.set_selection(session, {sid})
    assert session.state.selection == set()
    assert shapes.add_rectangle(session, (0, 0), (10, 10)) is None


def test_layers_add_remove_rename():
    session = Session()
    layers.add_layer(session)
    assert [layer.name for layer in session.state.document.layers] == ["Layer 1", "Layer 2"]
    assert session.state.selected_layer_index == 1
    layers.rename_layer(session, 1, "  Top ")
    layers.rename_layer(session, 1, "   ")
    assert session.state.document.layers[1].name == "Top"
    layers.remove_layer(session, 1)
    layers.remove_layer(session, 0)
    assert len(session.state.document.layers) == 1
    assert session.state.selected_layer_index == 0


def test_undo_layer_removal_restores_selected_index():
    session = Session()
    layers.add_layer(session)
    layers.remove_layer(session, 1)
    session.undo()
    assert len(session.state.document.layers) == 2


def test_locked_layer_keeps_shapes_but_drops_them_from_selection_and_blocks_drawing():
    session = Session()
    sid = shapes.add_rectangle(session, (0, 0), (10, 10))
    layers.set_layer_locked(session, 0, True)
    assert session.undo_label == "Lock layer"
    assert session.state.selection == set()
    selection.set_selection(session, {sid})
    assert session.state.selection == set()
    assert shapes.add_rectangle(session, (0, 0), (10, 10)) is None
    assert session.state.status_message == "Layer 'Layer 1' is locked"
    layers.set_layer_locked(session, 0, False)
    assert session.undo_label == "Unlock layer"
    assert len(session.state.document.layers[0].shapes) == 1


def test_locking_the_layer_of_the_entered_group_leaves_edit_mode():
    from presstoshape.editing.operations import edit_mode, groups

    session = Session()
    first = shapes.add_rectangle(session, (0, 0), (10, 10))
    second = shapes.add_rectangle(session, (20, 0), (30, 10))
    selection.set_selection(session, {first, second})
    groups.group(session)
    (group_id,) = session.state.selection
    edit_mode.enter(session, group_id)
    selection.set_selection(session, {first})
    layers.set_layer_locked(session, 0, True)
    assert session.state.edit_path == () and session.state.selection == set()
