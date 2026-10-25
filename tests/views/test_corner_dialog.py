from PySide6.QtWidgets import QApplication

from presstoshape.views.corner_dialog import CornerDialog


def test_dialog_shows_and_returns_values_in_the_document_unit():
    QApplication.instance() or QApplication([])
    dialog = CornerDialog("chamfer", 96.0, "in", 96.0)
    assert dialog._kind.currentData() == "chamfer"
    assert dialog._radius.value() == 1.0
    dialog._kind.setCurrentIndex(2)
    dialog._radius.setValue(0.5)
    dialog._accept()
    assert dialog.kind == "chamfer" and dialog.radius == 48.0
    dialog = CornerDialog("round", 10.0, "px", 96.0)
    dialog._kind.setCurrentIndex(1)
    dialog._accept()
    assert (dialog.kind, dialog.radius) == ("inverted", 10.0)
