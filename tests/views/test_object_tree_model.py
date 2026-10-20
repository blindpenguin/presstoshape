from PySide6.QtCore import QModelIndex
from PySide6.QtTest import QAbstractItemModelTester
from PySide6.QtWidgets import QApplication, QTreeView

from presstoshape.editing.operations import arrange, edit_mode, groups, layers, selection, shapes, visibility
from presstoshape.editing.session import Session
from presstoshape.views.object_tree_model import ObjectTreeModel


def _rows(model, index=QModelIndex()):
    rows = []
    for row in range(model.rowCount(index)):
        child = model.index(row, 0, index)
        node = model.node(child)
        flags = (node.hidden, node.locked, node.inherited_hidden, node.inherited_locked)
        rows.append((model.data(child), node.shape.id if node.shape else None, flags, _rows(model, child)))
    return rows


def test_row_by_row_updates_match_a_fresh_model():
    QApplication.instance() or QApplication([])
    session = Session()
    model = ObjectTreeModel()
    QAbstractItemModelTester(model, QAbstractItemModelTester.FailureReportingMode.Fatal, model)
    view = QTreeView()
    view.setModel(model)

    def check():
        model.set_content(session.state)
        view.expandAll()
        fresh = ObjectTreeModel()
        fresh.set_content(session.state)
        assert _rows(model) == _rows(fresh)

    first = shapes.add_rectangle(session, (0, 0), (10, 10))
    second = shapes.add_ellipse(session, (0, 0), (10, 10))
    third = shapes.add_rectangle(session, (20, 0), (30, 10))
    check()
    selection.set_selection(session, {first, second})
    groups.group(session)
    (group,) = session.state.selection
    check()
    visibility.set_hidden(session, first, True)
    visibility.set_locked(session, group, True)
    layers.set_layer_visible(session, 0, False)
    check()
    layers.set_layer_visible(session, 0, True)
    visibility.set_locked(session, group, False)
    selection.set_selection(session, {third})
    arrange.lower_to_bottom(session)
    check()
    edit_mode.enter(session, group)
    selection.set_selection(session, {second})
    selection.delete_selection(session)
    check()
    session.undo()
    layers.add_layer(session)
    shapes.add_rectangle(session, (0, 0), (5, 5))
    layers.rename_layer(session, 1, "Top")
    check()
    assert model.data(model.layer_index(1)) == "Top"
    session.undo()
    session.undo()
    session.undo()
    check()
    index = model.shape_index(first)
    assert model.node(index).shape.id == first and model.node(model.parent(index)).shape.id == group
    assert not model.shape_index(9999).isValid()
