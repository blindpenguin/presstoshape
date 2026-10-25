import os

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from presstoshape.editing.operations import view
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Tool
from presstoshape.views.canvas_view import CanvasView

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _canvas_with_delete_action():
    QApplication.instance() or QApplication([])
    session = Session()
    canvas = CanvasView(session, "cpu")
    session.subscribe(lambda: canvas.refresh(session.state))
    triggered = []
    action = QAction(canvas)
    action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
    action.triggered.connect(lambda: triggered.append(True))
    canvas.addAction(action)
    canvas.resize(600, 400)
    canvas.refresh(session.state)
    canvas.show()
    canvas.activateWindow()
    canvas.setFocus()
    QTest.qWaitForWindowExposed(canvas)
    view.select_tool(session, Tool.PEN)
    return session, canvas, triggered


def _click(canvas, x, y):
    sx, sy = canvas._vp.to_screen((x, y))
    QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(sx, sy))


def test_delete_mid_path_removes_the_pens_last_node_not_the_selection():
    session, canvas, triggered = _canvas_with_delete_action()
    _click(canvas, 50, 50)
    _click(canvas, 150, 50)
    pen = canvas._toolbox.active
    QTest.keyClick(canvas, Qt.Key.Key_Delete)
    assert triggered == [] and len(pen._nodes) == 1
    QTest.keyClick(canvas, Qt.Key.Key_Backspace)
    assert not pen.active
    QTest.keyClick(canvas, Qt.Key.Key_Delete)
    assert triggered == [True]
    canvas.deleteLater()
