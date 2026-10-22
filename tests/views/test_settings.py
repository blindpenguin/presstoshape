import os

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from presstoshape.views import app_settings
from presstoshape.views.settings.canvas_page import CanvasPage
from presstoshape.views.settings.dialog import PAGES, SettingsDialog
from presstoshape.views.settings.general_page import GeneralPage
from presstoshape.views.settings.language_page import LanguagePage
from presstoshape.views.settings.pages import SettingsContext

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FRENCH = """msgid ""
msgstr ""
"Language: fr\\n"
"Plural-Forms: nplurals=2; plural=(n > 1);\\n"

msgid "&File"
msgstr "&Fichier"

msgid "Layer {number}"
msgstr "Calque {numero}"
"""


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def context(tmp_path, qapp):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    return SettingsContext(settings, "en", tmp_path / "translations")


@pytest.fixture
def messages(monkeypatch):
    """Records message boxes instead of showing them; questions are answered Yes."""
    shown = []
    for kind in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, kind, lambda parent, title, text, kind=kind: shown.append((kind, text)))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    return shown


def _choose_file(monkeypatch, path):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(path), ""))


def test_dialog_lists_every_category_and_switches_pages(context):
    dialog = SettingsDialog(context, page=2)
    assert dialog._categories.count() == len(PAGES) == 3
    assert [dialog._categories.item(row).text() for row in range(3)] == ["General", "Language", "Canvas"]
    assert dialog.page == 2 and isinstance(dialog._pages.currentWidget(), CanvasPage)
    dialog._categories.setCurrentRow(1)
    assert isinstance(dialog._pages.currentWidget(), LanguagePage)


def test_general_page_toggles_the_start_dialog(context):
    page = GeneralPage(context)
    assert page._start_dialog.isChecked()
    page._start_dialog.setChecked(False)
    assert not app_settings.show_start_dialog(context.settings)


def test_language_choice_is_saved_and_shows_the_restart_note(context):
    page = LanguagePage(context)
    page.show()
    assert page._choice.itemText(0) == "System default"
    assert [page._choice.itemData(row) for row in range(1, page._choice.count())] == ["en", "de"]
    assert [page._choice.itemText(row) for row in (1, 2)] == ["British English", "Deutsch"]
    page._choice.setCurrentIndex(2)
    assert app_settings.language(context.settings) == "de"
    assert page._note.isVisibleTo(page)
    page._choice.setCurrentIndex(1)
    assert app_settings.language(context.settings) == "en"
    assert not page._note.isVisibleTo(page)


def test_renderer_choice_is_saved_with_restart_note(context):
    page = CanvasPage(context)
    page.show()
    page._renderer.setCurrentIndex(page._renderer.findData("cpu"))
    assert app_settings.renderer(context.settings) == "cpu"
    assert page._note.isVisibleTo(page)


def test_import_copies_a_valid_file_and_reports_ignored_entries(context, tmp_path, monkeypatch, messages):
    source = tmp_path / "fr.po"
    source.write_text(FRENCH, encoding="utf-8")
    _choose_file(monkeypatch, source)
    page = LanguagePage(context)
    page._import()
    assert (context.translations_folder / "fr.po").read_text(encoding="utf-8") == FRENCH
    assert page._user_files.count() == 1
    assert page._choice.findData("fr") > 0
    ((kind, text),) = messages
    assert kind == "information" and "1 entry was ignored" in text and "numero" in text


def test_import_refuses_broken_or_unnamed_files(context, tmp_path, monkeypatch, messages):
    broken = tmp_path / "es.po"
    broken.write_text("not a translation", encoding="utf-8")
    unnamed = tmp_path / "translation.po"
    unnamed.write_text(FRENCH.replace('"Language: fr\\n"\n', ""), encoding="utf-8")
    page = LanguagePage(context)
    for path in (broken, unnamed):
        _choose_file(monkeypatch, path)
        page._import()
    assert [kind for kind, _text in messages] == ["warning", "warning"]
    assert "line 1" in messages[0][1]
    assert "fr.po" in messages[1][1]
    assert not context.translations_folder.exists()


def test_remove_deletes_the_user_file(context, messages):
    context.translations_folder.mkdir()
    (context.translations_folder / "fr.po").write_text(FRENCH, encoding="utf-8")
    page = LanguagePage(context)
    page._user_files.setCurrentRow(0)
    page._remove()
    assert not (context.translations_folder / "fr.po").exists()
    assert page._user_files.count() == 0


def test_general_page_sets_recovery_interval_and_backups(context):
    page = GeneralPage(context)
    assert page._recovery.currentData() == 5 and page._backups.isChecked()
    assert [page._recovery.itemText(row) for row in range(page._recovery.count())] == [
        "Off",
        "1 minute",
        "2 minutes",
        "5 minutes",
        "10 minutes",
    ]
    page._recovery.setCurrentIndex(page._recovery.findData(1))
    page._backups.setChecked(False)
    assert app_settings.recovery_interval(context.settings) == 1
    assert not app_settings.keep_backups(context.settings)
