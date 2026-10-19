import os

import pytest
from PySide6.QtWidgets import QApplication

from presstoshape.models.app_state import Document
from presstoshape.views.export_dialog import ExportPngDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def dialog():
    QApplication.instance() or QApplication([])
    return ExportPngDialog(Document(2480.3, 3507.9, unit="mm", dpi=300.0), 1.0)


def test_defaults_to_the_documents_dpi(dialog):
    assert dialog._dpi.value() == 300
    assert dialog._size.text() == "2481 × 3508 px"


def test_dpi_and_scale_are_linked(dialog):
    dialog._dpi.setValue(150)
    assert dialog._scale.value() == 0.5
    assert dialog.scale == 0.5
    assert dialog._size.text() == "1241 × 1754 px"
    dialog._scale.setValue(2)
    assert dialog._dpi.value() == 600
