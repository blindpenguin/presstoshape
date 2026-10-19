import os

import pytest
from PySide6.QtWidgets import QApplication

from presstoshape.editing import queries
from presstoshape.editing.operations import documents, selection, shapes
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Document
from presstoshape.views.selection_view import SelectionOptions
from presstoshape.views.unit_fields import LengthSpinBox, font_unit

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


def test_spin_box_shows_the_unit_and_reports_pixels():
    spin = LengthSpinBox(0, 100_000)
    reported = []
    spin.px_changed.connect(reported.append)
    spin.set_unit("mm", 300)
    spin.set_px(2480.315)
    assert (spin.value(), spin.suffix(), spin.decimals()) == (210, " mm", 2)
    assert reported == []
    spin.setValue(100)
    assert reported == [pytest.approx(1181.102, abs=1e-3)]


def test_px_fields_look_as_before_and_unit_switch_keeps_the_length():
    spin = LengthSpinBox(0, 1000)
    spin.set_px(96)
    assert (spin.value(), spin.suffix()) == (96, "")
    spin.set_unit("in", 96)
    assert (spin.value(), spin.suffix(), spin.decimals()) == (1, " in", 3)


def test_font_sizes_are_points_in_physical_documents():
    assert font_unit(Document(unit="mm")) == "pt"
    assert font_unit(Document()) == "px"


def test_selection_panel_works_in_the_documents_unit():
    session = Session()
    documents.new_document(session, documents.DocumentSetup(210, 297, "mm", 300))
    document = session.state.document
    rect = shapes.add_rectangle(session, (0, 0), (document.width, document.height / 2))
    selection.set_selection(session, {rect})
    panel = SelectionOptions(session)
    panel.refresh(session.state)
    width = panel._spins["width"]
    assert (width.value(), width.suffix()) == (210, " mm")
    width.setValue(100)
    assert queries.find_shape(session.state, rect).width == pytest.approx(1181.102, abs=1e-3)
