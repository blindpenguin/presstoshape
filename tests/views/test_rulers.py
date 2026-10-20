import os

from PySide6.QtWidgets import QApplication, QDialog

from presstoshape.editing.operations import guides, view
from presstoshape.editing.session import Session
from presstoshape.models.layout import Guide
from presstoshape.views.canvas_view import CanvasView
from presstoshape.views.guide_dialog import GuideDialog
from presstoshape.views.ruler_view import RULER_SIZE

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _canvas():
    QApplication.instance() or QApplication([])
    session = Session()
    canvas = CanvasView(session, "cpu")
    session.subscribe(lambda: canvas.refresh(session.state))
    canvas.resize(400, 300)
    canvas.refresh(session.state)
    canvas.show()
    QApplication.processEvents()
    return session, canvas


def test_rulers_take_margins_and_follow_the_setting():
    session, canvas = _canvas()
    assert canvas._rulers["horizontal"].isVisible()
    assert canvas.viewport().geometry().y() >= RULER_SIZE
    view.toggle_rulers(session)
    QApplication.processEvents()
    assert not canvas._rulers["horizontal"].isVisible()
    assert canvas.viewport().geometry().y() < RULER_SIZE
    canvas.deleteLater()


def test_rulers_know_the_view():
    session, canvas = _canvas()
    ruler = canvas._rulers["horizontal"]
    assert ruler._zoom == canvas._vp.zoom
    assert ruler._start_doc == canvas._vp.to_doc((0.0, 0.0))[0]
    canvas.deleteLater()


def test_dragging_out_of_a_ruler_adds_a_guide_and_back_cancels():
    session, canvas = _canvas()
    viewport = canvas.viewport()
    canvas._begin_new_guide("vertical")
    canvas._drag_new_guide(viewport.mapToGlobal(viewport.rect().center()))
    assert canvas._new_guide is not None
    canvas._release_new_guide(viewport.mapToGlobal(viewport.rect().center()))
    assert len(session.state.document.guides) == 1
    canvas._begin_new_guide("horizontal")
    outside = viewport.mapToGlobal(viewport.rect().topLeft()) - viewport.rect().center()
    canvas._drag_new_guide(outside)
    canvas._release_new_guide(outside)
    assert len(session.state.document.guides) == 1
    canvas.deleteLater()


def test_guide_dialog_reports_position_in_document_px_or_deletion():
    QApplication.instance() or QApplication([])
    dialog = GuideDialog(Guide(1, "horizontal", 96.0), "in", 96.0)
    assert dialog._position.value() == 1.0
    dialog._position.setValue(2.0)
    dialog._accept()
    assert dialog.result() == QDialog.DialogCode.Accepted and dialog.position == 192.0
    dialog = GuideDialog(Guide(1, "vertical", 10.0), "px", 96.0)
    dialog._delete()
    assert dialog.deleted


def test_editing_a_guide_through_the_canvas_dialog(monkeypatch):
    session, canvas = _canvas()
    guide_id = guides.add_guide(session, "vertical", 40)

    def fake_exec(dialog):
        dialog._position.setValue(55)
        dialog._accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(GuideDialog, "exec", fake_exec)
    canvas._edit_guide(guide_id)
    assert session.state.document.guides[0].position == 55
    canvas.deleteLater()
