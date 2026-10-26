import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from presstoshape.editing.operations import palettes, selection, shapes, swatches, view
from presstoshape.editing.session import Session
from presstoshape.formats.swatch_library import write_library
from presstoshape.models.app_state import Tool
from presstoshape.models.colours import Swatch
from presstoshape.views import app_settings
from presstoshape.views.main_window import MainWindow
from tests.helpers import all_shapes


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def window(tmp_path, settings):
    QApplication.instance() or QApplication([])
    session = Session()
    window = MainWindow(session, settings, tmp_path / "recovery", tmp_path / "palettes")
    return window, session


def selected_rect(session):
    shapes.add_rectangle(session, (0, 0), (10, 10))
    selection.set_selection(session, {all_shapes(session)[0].id})


def drag_picker(panel, start, end):
    picker = panel._picker
    picker.resize(200, 130)
    QTest.mousePress(picker, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(picker, end)
    QTest.mouseRelease(picker, Qt.MouseButton.LeftButton, pos=end)


def test_picker_drag_previews_then_commits_one_undo_step(window):
    window_, session = window
    panel = window_._colour
    selected_rect(session)
    previews = []
    panel.preview_changed.connect(previews.append)
    count = session.undo_count
    drag_picker(panel, QPoint(5, 5), QPoint(150, 20))
    assert previews and previews[-1] is None
    assert any(isinstance(item, dict) and "fill" in item for item in previews)
    assert session.undo_count == count + 1
    assert session.undo_label == "Change fill"
    assert all_shapes(session)[0].style.fill == session.state.colours.recent[0]


def test_preview_does_not_change_the_document(window):
    window_, session = window
    selected_rect(session)
    before = all_shapes(session)[0]
    window_.canvas.set_style_preview({"fill": "#00ff00"})
    assert window_.canvas._style_preview[0].style.fill == "#00ff00"
    assert all_shapes(session)[0] is before
    window_.canvas.set_style_preview(None)
    assert window_.canvas._style_preview == ()


def test_panel_follows_the_tool_target(window):
    window_, session = window
    view.select_tool(session, Tool.ELLIPSE)
    panel = window_._colour
    panel._hex.setText("#00ff00")
    panel._hex.editingFinished.emit()
    assert session.state.tool_styles[Tool.ELLIPSE].fill == "#00ff00"
    assert not session.can_undo


def test_number_steps_merge_and_end_on_finish(window):
    window_, session = window
    selected_rect(session)
    panel = window_._colour
    count = session.undo_count
    for value in (10, 20, 30):
        panel._numbers[0].setValue(value)
    assert session.undo_count == count + 1
    panel._numbers[0].editingFinished.emit()
    panel._numbers[0].setValue(40)
    assert session.undo_count == count + 2


def test_invalid_hex_reverts(window):
    window_, session = window
    selected_rect(session)
    panel = window_._colour
    fill = all_shapes(session)[0].style.fill
    panel._hex.setText("not a colour")
    panel._hex.editingFinished.emit()
    assert panel._hex.text() == fill
    assert all_shapes(session)[0].style.fill == fill


def test_hex_accepts_colour_names(window):
    window_, session = window
    selected_rect(session)
    panel = window_._colour
    panel._hex.setText("teal")
    panel._hex.editingFinished.emit()
    assert all_shapes(session)[0].style.fill == "#008080"


def test_recent_colours_and_number_mode_are_remembered(tmp_path, window, settings):
    window_, session = window
    selected_rect(session)
    panel = window_._colour
    panel._hex.setText("#123456")
    panel._hex.editingFinished.emit()
    panel._mode.click()
    assert app_settings.recent_colours(settings)[0] == "#123456"
    assert app_settings.colour_numbers(settings) == "rgb"
    again = MainWindow(Session(), settings, tmp_path / "recovery", tmp_path / "palettes")
    assert again._state.colours.recent[0] == "#123456"
    assert again._state.colours.numbers == "rgb"


def test_palettes_and_current_palette_are_saved_and_loaded(tmp_path, window, settings):
    window_, session = window
    swatches.add_swatch(session, "library", "#abcdef", name="Mine")
    second = palettes.new_palette(session, "Second")
    palettes.set_current_palette(session, second)
    assert (tmp_path / "palettes" / "my-swatches.json").is_file()
    again = MainWindow(Session(), settings, tmp_path / "recovery", tmp_path / "palettes")
    loaded = again._state.colours.palettes
    assert [p.name for p in loaded] == ["My swatches", "Second"]
    assert [s.color for s in loaded[0].swatches] == ["#abcdef"]
    assert palettes.current_palette(again._state).name == "Second"


def test_old_library_is_migrated(tmp_path, settings):
    QApplication.instance() or QApplication([])
    (tmp_path / "swatches.json").write_text(write_library((Swatch(1, "", "#123456"),)), encoding="utf-8")
    session = Session()
    MainWindow(session, settings, tmp_path / "recovery", tmp_path / "palettes")
    assert [p.name for p in session.state.colours.palettes] == ["My swatches"]
    assert (tmp_path / "swatches.migrated.json").is_file()


def test_unreadable_palette_files_are_reported_and_kept(tmp_path, settings):
    QApplication.instance() or QApplication([])
    folder = tmp_path / "palettes"
    folder.mkdir()
    (folder / "bad.json").write_text("{broken", encoding="utf-8")
    session = Session()
    MainWindow(session, settings, tmp_path / "recovery", folder)
    assert session.state.colours.palettes == ()
    assert "bad.json" in session.state.status_message
    swatches.add_swatch(session, "library", "#000000")
    assert (folder / "bad.json").read_text(encoding="utf-8") == "{broken"


def test_window_without_settings_writes_no_palettes(tmp_path):
    QApplication.instance() or QApplication([])
    session = Session()
    MainWindow(session, None, tmp_path / "recovery", tmp_path / "palettes")
    swatches.add_swatch(session, "library", "#000000")
    assert not (tmp_path / "palettes").exists()


def test_library_tab_follows_palettes(window):
    window_, session = window
    panel = window_._colour
    assert panel._library_stack.currentIndex() == 1
    first = palettes.new_palette(session, "First")
    palettes.new_palette(session, "Second")
    assert [panel._palette_box.itemText(i) for i in range(panel._palette_box.count())] == ["First", "Second"]
    assert panel._palette_box.currentText() == "Second"
    assert panel._library_stack.currentIndex() == 0
    panel._palette_box.activated.emit(0)
    assert session.state.colours.current_palette == first


def test_manage_palettes_opens_settings_on_the_palettes_page(window, monkeypatch):
    from presstoshape.views.settings.dialog import PAGES, SettingsDialog
    from presstoshape.views.settings.palettes_page import PalettesPage

    window_, _session = window
    opened = []
    monkeypatch.setattr(SettingsDialog, "exec", lambda dialog: opened.append(dialog.page) or 0)
    window_._colour.manage_palettes.emit()
    assert opened == [PAGES.index(PalettesPage)]


def test_document_swatch_click_applies_colour_and_opacity(window):
    window_, session = window
    selected_rect(session)
    swatches.add_swatch(session, "document", "#ff0000", 0.5)
    swatch = session.state.document.swatches[0]
    window_._colour._apply_swatch("document", swatch.id)
    style = all_shapes(session)[0].style
    assert (style.fill, style.fill_opacity) == ("#ff0000", 0.5)
