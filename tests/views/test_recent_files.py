import os

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from presstoshape.editing.operations.documents import DocumentSetup
from presstoshape.editing.session import Session
from presstoshape.views import app_settings
from presstoshape.views.app_settings import updated_recent

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_updated_recent_moves_to_top_dedupes_and_limits(tmp_path):
    paths = [str(tmp_path / f"{index}.p2s") for index in range(10)]
    assert updated_recent(paths, paths[3])[:2] == [paths[3], paths[0]]
    assert len(updated_recent(paths, paths[3])) == 10
    new = updated_recent(paths, str(tmp_path / "sub" / ".." / "new.svg"))
    assert new[0] == str(tmp_path / "new.svg") and len(new) == 10 and paths[9] not in new


def test_recent_file_accessors(settings, tmp_path):
    first, second = str(tmp_path / "a.p2s"), str(tmp_path / "b.svg")
    app_settings.add_recent_file(settings, first)
    assert app_settings.recent_files(settings) == [first]
    app_settings.add_recent_file(settings, second)
    assert app_settings.recent_files(settings) == [second, first]
    app_settings.remove_recent_file(settings, second)
    assert app_settings.recent_files(settings) == [first]
    app_settings.clear_recent_files(settings)
    assert app_settings.recent_files(settings) == []


def test_bad_stored_values_fall_back(settings):
    settings.setValue("recent_files", 42)
    settings.setValue("start/show_dialog", "false")
    settings.setValue("new_document/setup", ["wide", 1, "px", 96])
    assert app_settings.recent_files(settings) == []
    assert not app_settings.show_start_dialog(settings)
    assert app_settings.last_new_document(settings) is None


def test_last_new_document_round_trip(settings):
    assert app_settings.last_new_document(settings) is None
    setup = DocumentSetup(210, 297, "mm", 300)
    app_settings.set_last_new_document(settings, "print.a4", setup)
    assert app_settings.last_new_document(settings) == ("print.a4", setup)
    app_settings.set_last_new_document(settings, None, setup)
    assert app_settings.last_new_document(settings) == (None, setup)


def test_open_recent_menu_lists_files_or_says_there_are_none(settings, tmp_path):
    from presstoshape.views.main_window import MainWindow

    QApplication.instance() or QApplication([])
    window = MainWindow(Session(), settings, tmp_path / "recovery", tmp_path / "palettes")
    window._fill_recent_menu()
    assert [action.text() for action in window._recent_menu.actions()] == ["No recent files"]
    app_settings.add_recent_file(settings, str(tmp_path / "R&D.p2s"))
    window._fill_recent_menu()
    texts = [action.text() for action in window._recent_menu.actions()]
    assert texts == ["&1 R&&D.p2s", "", "Clear Recent Files"]
    window.close_without_prompt()
