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


def _image_session(reference=False):
    from presstoshape.editing.operations import images
    from tests.helpers import quadrant_picture

    session = Session()
    images.place_images(session, [("a.png", quadrant_picture(80, 40).data)], (100.0, 100.0), reference)
    model = ObjectTreeModel()
    model.set_content(session.state)
    return session, model


def _image_row(model, layer_row=0):
    layer = model.index(layer_row, 0)
    return model.index(0, 0, layer)


def test_image_rows_show_a_thumbnail_made_once_per_picture(monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon

    from presstoshape.views import object_tree_model

    QApplication.instance() or QApplication([])
    session, model = _image_session()
    made = []
    real = object_tree_model.thumbnail
    monkeypatch.setattr(object_tree_model, "thumbnail", lambda data, side: made.append(side) or real(data, side))
    assert made == []
    row = _image_row(model)
    icon = model.data(row, Qt.ItemDataRole.DecorationRole)
    assert isinstance(icon, QIcon) and not icon.isNull()
    assert icon.pixmap(48, 48).width() == 48
    model.data(row, Qt.ItemDataRole.DecorationRole)
    model.set_content(session.state)
    model.data(row, Qt.ItemDataRole.DecorationRole)
    assert made == [48]


def test_an_undecodable_picture_falls_back_to_the_type_icon():
    from PySide6.QtCore import Qt

    from presstoshape.models.shapes import ImageData, ImageShape

    QApplication.instance() or QApplication([])
    session, model = _image_session()
    layer = session.state.document.layers[0]
    shape = layer.shapes[0]
    layer.shapes[0] = ImageShape(shape.id, 0.0, 0.0, 5.0, 5.0, ImageData(b"", 2, 2, "application/x-missing", "0" * 64))
    model.set_content(session.state)
    icon = model.data(_image_row(model), Qt.ItemDataRole.DecorationRole)
    assert not icon.isNull()


def test_reference_rows_are_marked():
    from PySide6.QtCore import Qt

    QApplication.instance() or QApplication([])
    session, model = _image_session(reference=True)
    assert model.data(_image_row(model, layer_row=1), Qt.ItemDataRole.DisplayRole) == "Image (reference)"
