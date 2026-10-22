import os
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from presstoshape.editing.session import Session
from presstoshape.views.import_report_dialog import ImportReportDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SAMPLES = Path(__file__).resolve().parent.parent / "formats" / "samples" / "svg"


@pytest.fixture
def window(tmp_path):
    from presstoshape.views.main_window import MainWindow

    QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(Session(), settings, tmp_path / "recovery")
    window.reports = []
    window.show_import_report = lambda name, notes: window.reports.append((name, notes))
    yield window
    window.close_without_prompt()


def test_opening_a_lossy_file_shows_its_notes_once(window):
    assert window.open_path(str(SAMPLES / "figma_frame.svg"))
    assert window.reports == [
        (
            "figma_frame.svg",
            ["1 clip path was ignored, its content is shown unclipped"],
        )
    ]
    assert window._session.state.import_notes == []


def test_clean_files_show_no_report(window):
    assert window.open_path(str(SAMPLES / "illustrator_classes.svg"))
    assert window.reports == []


def test_dialog_lists_every_note():
    QApplication.instance() or QApplication([])
    dialog = ImportReportDialog("a.svg", ["one", "two"])
    assert [dialog.notes.item(index).text() for index in range(dialog.notes.count())] == ["one", "two"]
    dialog.deleteLater()
