import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from presstoshape.editing.operations import selection, shapes, swatches, view
from presstoshape.editing.session import Session
from presstoshape.formats.swatch_library import read_library
from presstoshape.models.app_state import Tool
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
    window = MainWindow(session, settings, tmp_path / "recovery", tmp_path / "swatches.json")
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
    again = MainWindow(Session(), settings, tmp_path / "recovery", tmp_path / "swatches.json")
    assert again._state.colours.recent[0] == "#123456"
    assert again._state.colours.numbers == "rgb"


def test_library_is_saved_and_loaded(tmp_path, window, settings):
    window_, session = window
    swatches.add_swatch(session, "library", "#abcdef", name="Mine")
    (saved,) = read_library((tmp_path / "swatches.json").read_text(encoding="utf-8"))
    assert (saved.name, saved.color) == ("Mine", "#abcdef")
    again = MainWindow(Session(), settings, tmp_path / "recovery", tmp_path / "swatches.json")
    assert [s.color for s in again._state.colours.library] == ["#abcdef"]


def test_unreadable_library_starts_empty_and_is_kept_as_backup(tmp_path, settings):
    QApplication.instance() or QApplication([])
    library = tmp_path / "swatches.json"
    library.write_text("{broken", encoding="utf-8")
    session = Session()
    MainWindow(session, settings, tmp_path / "recovery", library)
    assert session.state.colours.library == ()
    assert library.read_text(encoding="utf-8") == "{broken"
    swatches.add_swatch(session, "library", "#000000")
    assert (tmp_path / "swatches.backup.json").read_text(encoding="utf-8") == "{broken"
    assert len(read_library(library.read_text(encoding="utf-8"))) == 1


def test_window_without_settings_writes_no_library(tmp_path):
    QApplication.instance() or QApplication([])
    session = Session()
    MainWindow(session, None, tmp_path / "recovery", tmp_path / "swatches.json")
    swatches.add_swatch(session, "library", "#000000")
    assert not (tmp_path / "swatches.json").exists()


def test_document_swatch_click_applies_colour_and_opacity(window):
    window_, session = window
    selected_rect(session)
    swatches.add_swatch(session, "document", "#ff0000", 0.5)
    swatch = session.state.document.swatches[0]
    window_._colour._apply_swatch("document", swatch.id)
    style = all_shapes(session)[0].style
    assert (style.fill, style.fill_opacity) == ("#ff0000", 0.5)


def test_palette_images_and_files_import(tmp_path):
    from PySide6.QtGui import QColor, QImage

    from presstoshape.views.colour_panel import _read_palette_file

    QApplication.instance() or QApplication([])
    image = QImage(16, 8, QImage.Format.Format_RGBA8888)
    image.fill(QColor("#1d2b53"))
    for x in range(8, 16):
        for y in range(8):
            image.setPixelColor(x, y, QColor("#ffccaa"))
    image.save(str(tmp_path / "palette-8x.png"))
    assert [color for _n, color, _o in _read_palette_file(tmp_path / "palette-8x.png")] == ["#1d2b53", "#ffccaa"]
    (tmp_path / "p.hex").write_text("000000\r\n", encoding="utf-8")
    assert _read_palette_file(tmp_path / "p.hex") == [("", "#000000", 1.0)]
    (tmp_path / "notes.doc").write_bytes(b"nothing")
    with pytest.raises(ValueError):
        _read_palette_file(tmp_path / "notes.doc")
