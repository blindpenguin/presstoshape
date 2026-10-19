import os

import pytest
from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import QApplication

from presstoshape.editing.operations.documents import DocumentSetup
from presstoshape.views.new_document_dialog import OPEN, NewDocumentDialog, StartChoices

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def qapp():
    QLocale.setDefault(QLocale("en_GB"))
    return QApplication.instance() or QApplication([])


def _select(dialog, preset_id):
    tree = dialog._presets
    for category in range(tree.topLevelItemCount()):
        parent = tree.topLevelItem(category)
        for row in range(parent.childCount()):
            if parent.child(row).data(0, Qt.ItemDataRole.UserRole) == preset_id:
                tree.setCurrentItem(parent.child(row))
                return
    raise AssertionError(preset_id)


def test_default_without_history_is_the_built_in_size():
    dialog = NewDocumentDialog()
    assert dialog.setup == DocumentSetup(600, 400, "px", 96)
    assert dialog.preset_id is None
    assert dialog._hint.text() == "158.75 × 105.83 mm"


def test_preset_fills_the_fields_and_editing_makes_it_custom():
    dialog = NewDocumentDialog()
    _select(dialog, "print.a4")
    assert dialog.setup == DocumentSetup(210, 297, "mm", 300)
    assert dialog.preset_id == "print.a4"
    assert dialog._hint.text() == "2480 × 3508 px"
    assert dialog._portrait.isChecked() and not dialog._landscape.isChecked()
    dialog._width.setValue(200)
    assert dialog.preset_id is None and not dialog._presets.selectedItems()


def test_unit_change_keeps_the_physical_size_and_dpi_change_keeps_the_values():
    dialog = NewDocumentDialog()
    _select(dialog, "print.a4")
    dialog._unit.setCurrentIndex(dialog._unit.findData("in"))
    assert (dialog._width.value(), dialog._height.value()) == (8.268, 11.693)
    dialog._dpi.setValue(150)
    assert (dialog._width.value(), dialog._dpi.value()) == (8.268, 150)
    assert dialog._hint.text() == "1240 × 1754 px"


def test_px_documents_keep_their_pixels_when_the_dpi_changes():
    dialog = NewDocumentDialog()
    _select(dialog, "screen.full_hd")
    dialog._dpi.setValue(300)
    assert (dialog._width.value(), dialog._height.value()) == (1920, 1080)


def test_orientation_buttons_swap_width_and_height():
    dialog = NewDocumentDialog()
    _select(dialog, "print.a5")
    dialog._set_orientation(portrait=False)
    assert (dialog._width.value(), dialog._height.value()) == (210, 148)
    assert dialog._landscape.isChecked() and not dialog._portrait.isChecked()
    dialog._set_orientation(portrait=False)
    assert dialog._width.value() == 210


def test_invalid_sizes_disable_create_with_a_reason():
    dialog = NewDocumentDialog()
    dialog._width.setValue(0)
    assert not dialog._create.isEnabled()
    assert "at least 1 px" in dialog._problem.text()
    dialog._width.setValue(100)
    assert dialog._create.isEnabled()


def test_last_setup_is_preselected_custom_or_preset():
    custom = NewDocumentDialog((None, DocumentSetup(12, 34, "cm", 200)))
    assert custom.setup == DocumentSetup(12, 34, "cm", 200) and custom.preset_id is None
    landscape_a4 = NewDocumentDialog(("print.a4", DocumentSetup(297, 210, "mm", 300)))
    assert landscape_a4.preset_id == "print.a4"
    assert landscape_a4.setup == DocumentSetup(297, 210, "mm", 300)


def test_startup_parts_only_at_startup(tmp_path):
    assert NewDocumentDialog().show_at_startup is None
    recent = tmp_path / "drawing.p2s"
    recent.write_bytes(b"")
    dialog = NewDocumentDialog(start=StartChoices([str(recent)], show_at_startup=False, error="It broke"))
    assert dialog.show_at_startup is False
    assert dialog._recent.count() == 1
    dialog._on_recent_activated(dialog._recent.item(0))
    assert dialog.open_path == str(recent)
    other = NewDocumentDialog(start=StartChoices([], show_at_startup=True))
    other._choose_open(OPEN)
    assert other.open_path == OPEN
