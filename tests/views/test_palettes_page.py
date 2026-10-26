import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from presstoshape.editing.operations import palettes
from presstoshape.editing.session import Session
from presstoshape.models.colours import Palette, Swatch
from presstoshape.views.settings.pages import SettingsContext
from presstoshape.views.settings.palettes_page import PalettesPage

SWATCHES = (Swatch(1, "Black", "#000000"), Swatch(2, "", "#ff004d"), Swatch(3, "", "#29adff"))


@pytest.fixture
def page(tmp_path):
    QApplication.instance() or QApplication([])
    session = Session()
    palettes.set_palettes(session, (Palette(1, "PICO-8", SWATCHES), Palette(2, "Mine"), Palette(3, "Third")))
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    context = SettingsContext(settings, "en", tmp_path / "translations", session, tmp_path / "palettes")
    return PalettesPage(context), session


def select(page, *rows):
    page._list.clearSelection()
    for row in rows:
        page._list.item(row).setSelected(True)


def names(session):
    return [p.name for p in session.state.colours.palettes]


def test_list_counts_and_buttons_follow_the_selection(page):
    widget, _session = page
    assert widget._list.item(0).text() == "PICO-8 (3 colours)"
    select(widget, 0)
    assert widget._buttons["rename"].isEnabled() and widget._buttons["duplicate"].isEnabled()
    assert len(widget._preview.cells) == 3
    assert widget._preview_title.text() == "PICO-8: 3 colours"
    select(widget, 0, 2)
    assert not widget._buttons["rename"].isEnabled() and widget._buttons["delete"].isEnabled()
    assert widget._preview.cells == ()


def test_new_rename_duplicate(page, monkeypatch):
    widget, session = page
    answers = iter([("Warm", True), ("Hot", True)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: next(answers))
    widget._new()
    assert names(session)[-1] == "Warm" and widget.selected_ids() == [session.state.colours.palettes[-1].id]
    widget._rename()
    assert names(session)[-1] == "Hot"
    select(widget, 0)
    widget._duplicate()
    assert names(session) == ["PICO-8", "PICO-8 copy", "Mine", "Third", "Hot"]


def test_delete_asks_first(page, monkeypatch):
    widget, session = page
    answers = iter([QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes])
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: asked.append(args[2]) or next(answers))
    select(widget, 1, 2)
    widget._delete()
    assert names(session) == ["PICO-8", "Mine", "Third"]
    widget._delete()
    assert names(session) == ["PICO-8"]
    assert "Mine" in asked[0] and "Third" in asked[0]


def test_drag_reorder_reaches_the_session(page):
    widget, session = page
    widget._list.insertItem(0, widget._list.takeItem(2))
    widget._list._on_reordered([widget._list.item(row).data(256) for row in range(widget._list.count())])
    assert names(session) == ["Third", "PICO-8", "Mine"]


def test_preview_swatch_menu_edits_that_palette(page):
    widget, session = page
    palettes.set_current_palette(session, 2)
    select(widget, 0)
    menu = widget.swatch_menu(2)
    menu.actions()[-1].trigger()
    widget.refresh()
    assert [s.color for s in palettes.find_palette(session.state, 1).swatches] == ["#000000", "#29adff"]
    assert palettes.find_palette(session.state, 2).swatches == ()
    assert widget._list.item(0).text() == "PICO-8 (2 colours)"


def test_page_without_session_explains_itself(tmp_path):
    QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    widget = PalettesPage(SettingsContext(settings, "en", tmp_path / "translations"))
    assert not hasattr(widget, "_list")
