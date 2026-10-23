import os

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QColor, QDropEvent, QImage
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from presstoshape.editing.operations import documents
from presstoshape.editing.session import Session
from presstoshape.models.shapes import ImageShape
from presstoshape.views import clipboard
from presstoshape.views.main_window import MainWindow
from tests.helpers import all_shapes, quadrant_picture

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PICTURE = quadrant_picture(100, 50)


@pytest.fixture
def window(tmp_path):
    QApplication.instance() or QApplication([])
    session = Session()
    documents.new_document(session, documents.DocumentSetup(400, 300, "px", 96))
    window = MainWindow(session)
    window.resize(900, 700)
    window.show()
    QApplication.processEvents()
    yield window
    window.close_without_prompt()


@pytest.fixture
def messages(monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: shown.append(text))
    return shown


def pictures(window):
    return [shape for shape in all_shapes(window._session) if isinstance(shape, ImageShape)]


def write(tmp_path, name="a.png", data=PICTURE.data):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_place_image_reads_the_chosen_files_into_the_view_center(window, tmp_path, monkeypatch, messages):
    first, second = write(tmp_path, "a.png"), write(tmp_path, "b.png")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args, **kwargs: ([str(first), str(second)], ""))
    window.place_image()
    one, two = pictures(window)
    assert one.data is two.data and not one.reference
    center_x, center_y = window.canvas.view_center()
    assert one.x + one.width / 2 == pytest.approx(center_x) and one.y + one.height / 2 == pytest.approx(center_y)
    assert window._state.selection == {one.id, two.id} and messages == []


def test_a_cancelled_dialog_places_nothing(window, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args, **kwargs: ([], ""))
    window.place_image()
    assert pictures(window) == []


def test_place_as_reference_makes_dimmed_locked_images_in_a_reference_layer(window, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args, **kwargs: ([str(write(tmp_path))], ""))
    window.place_reference()
    (shape,) = pictures(window)
    assert shape.reference and shape.locked
    assert window._state.document.layers[0].name == "Reference"


def test_unusable_and_unreadable_files_are_listed_in_one_message(window, tmp_path, monkeypatch, messages):
    good, bad = write(tmp_path, "good.png"), write(tmp_path, "bad.png", b"junk")
    gone = tmp_path / "gone.png"
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a, **k: ([str(good), str(bad), str(gone)], ""))
    window.place_image()
    assert len(pictures(window)) == 1
    (text,) = messages
    assert "bad.png" in text and "gone.png" in text and "good.png" not in text


def test_replace_image_swaps_the_selected_picture(window, tmp_path, monkeypatch):
    window.place_files([write(tmp_path)], (200.0, 150.0))
    tall = quadrant_picture(50, 100)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(write(tmp_path, "t.png", tall.data)), ""))
    window.replace_image()
    (shape,) = pictures(window)
    assert shape.data == tall


def test_replace_is_only_enabled_for_exactly_one_selected_image(window, tmp_path):
    assert not window._actions["image.replace"].isEnabled()
    window.place_files([write(tmp_path)], (200.0, 150.0))
    assert window._actions["image.replace"].isEnabled()
    window.place_files([write(tmp_path, "a.png"), write(tmp_path, "b.png")], (200.0, 150.0))
    assert not window._actions["image.replace"].isEnabled()


def drop(window, mime, x=300, y=300):
    event = QDropEvent(
        QPointF(x, y), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    window.dropEvent(event)
    return event


def test_dropping_image_files_places_them_where_they_landed(window, tmp_path):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(write(tmp_path)))])
    event = drop(window, mime, 300, 300)
    (shape,) = pictures(window)
    spot = window.canvas.viewport().mapFrom(window, QPoint(300, 300))
    expected = window.canvas.to_doc(spot.x(), spot.y())
    assert event.isAccepted()
    assert (shape.x + shape.width / 2, shape.y + shape.height / 2) == pytest.approx(expected)


def test_dropping_other_files_is_ignored_with_a_message(window, tmp_path):
    other = tmp_path / "notes.txt"
    other.write_text("hello")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(other))])
    drop(window, mime)
    assert pictures(window) == []
    assert "dropped" in window._state.status_message


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_the_window_accepts_drags_of_files_and_images_only(window):
    from PySide6.QtGui import QDragEnterEvent

    def enter(mime):
        event = QDragEnterEvent(
            window.rect().center(),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        event.ignore()
        window.dragEnterEvent(event)
        return event.isAccepted()

    files = QMimeData()
    files.setUrls([QUrl.fromLocalFile("/tmp/x.png")])
    assert enter(files)
    assert not enter(QMimeData())


def bitmap_mime(width=8, height=6):
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("red"))
    mime = QMimeData()
    mime.setImageData(image)
    return mime


def test_a_bitmap_on_the_clipboard_becomes_a_png_and_is_offered_for_paste():
    QApplication.instance() or QApplication([])
    mime = bitmap_mime()
    assert clipboard.offers_paste(mime)
    png = clipboard.png_of(mime)
    assert png is not None and png.startswith(b"\x89PNG")
    assert clipboard.png_of(QMimeData()) is None


def test_pasting_a_bitmap_places_an_image_in_the_view_center(window):
    QApplication.clipboard().setMimeData(bitmap_mime(80, 60))
    window.paste()
    (shape,) = pictures(window)
    assert (shape.width, shape.height) == (80, 60)
    assert window._state.selection == {shape.id}


def test_shapes_on_the_clipboard_win_over_a_bitmap(window, tmp_path):
    window.place_files([write(tmp_path)], (200.0, 150.0))
    window.copy()
    mime = QApplication.clipboard().mimeData()
    assert mime is not None and mime.hasFormat("application/x-presstoshape-shapes")
    window.paste()
    assert len(pictures(window)) == 2


def test_a_dropped_bitmap_is_placed(window):
    mime = bitmap_mime(40, 30)
    drop(window, mime)
    (shape,) = pictures(window)
    assert (shape.width, shape.height) == (40, 30)


def test_menus_offer_the_image_commands_without_shortcuts(window):
    from presstoshape.views.keymap import KEYMAP

    for command in ("file.place_image", "file.place_reference", "image.replace", "image.reset_size", "image.fit_page"):
        assert not window._actions[command].shortcuts()
        assert command not in KEYMAP or KEYMAP[command].shortcut is None
    titles = [action.text() for action in window.menuBar().actions()]
    assert titles == ["&File", "&Edit", "&Path", "&Object", "&View", "&Tools", "&Help"]
    show = window._actions["view.show_references"]
    assert show.isCheckable() and show.isChecked()
    show.trigger()
    assert not window._state.view.show_references
    assert show.isChecked() is False
