from veccy.editing.operations import layers, selection, shapes
from veccy.editing.session import Session


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
