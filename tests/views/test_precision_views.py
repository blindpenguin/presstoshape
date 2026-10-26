import os

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from presstoshape.editing.operations import selection, shapes, view
from presstoshape.editing.session import Session
from presstoshape.models.layout import SnapSettings
from presstoshape.views import app_settings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def window(settings, tmp_path):
    from presstoshape.views.main_window import MainWindow

    QApplication.instance() or QApplication([])
    window = MainWindow(Session(), settings, tmp_path / "recovery", tmp_path / "swatches.json")
    yield window
    window.close_without_prompt()


def test_snap_settings_round_trip_and_survive_garbage(settings):
    assert app_settings.snap_settings(settings) == SnapSettings()
    changed = SnapSettings(enabled=False, grid=True, nodes=False, distance_px=12.0)
    app_settings.set_snap_settings(settings, changed)
    assert app_settings.snap_settings(settings) == changed
    settings.setValue("snapping/distance_px", "far")
    assert app_settings.snap_settings(settings).distance_px == 8.0


def test_toggles_show_check_marks_and_are_remembered(window, settings):
    session = window._session
    action = window._actions["view.snapping"]
    assert action.isCheckable() and action.isChecked()
    action.trigger()
    assert not session.state.snapping.enabled and not action.isChecked()
    window._actions["view.show_rulers"].trigger()
    assert not app_settings.show_rulers(settings)
    assert not app_settings.snap_settings(settings).enabled


def test_a_new_window_starts_with_the_remembered_toggles(settings, tmp_path):
    from presstoshape.views.main_window import MainWindow

    QApplication.instance() or QApplication([])
    app_settings.set_show_rulers(settings, False)
    app_settings.set_snap_settings(settings, SnapSettings(objects=False))
    window = MainWindow(Session(), settings, tmp_path / "recovery", tmp_path / "swatches.json")
    assert not window._session.state.view.show_rulers
    assert not window._session.state.snapping.objects
    window.close_without_prompt()


def test_align_panel_buttons_follow_the_selection(window):
    session = window._session
    align_left = window._actions["object.align_left"]
    distribute = window._actions["object.distribute_x"]
    assert not align_left.isEnabled()
    ids = [shapes.add_rectangle(session, (x, 0), (x + 10, 10)) for x in (0, 30, 90)]
    selection.set_selection(session, set(ids[:2]))
    assert align_left.isEnabled() and not distribute.isEnabled()
    selection.set_selection(session, set(ids))
    assert distribute.isEnabled()
    window._align._reference.activated.emit(1)
    assert session.state.align_reference == "artboard"
    view.set_snap_distance(session, 5)


def test_grid_settings_dialog_changes_the_grid(window, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from presstoshape.views.grid_dialog import GridDialog

    def fake_exec(dialog):
        dialog._spacing.set_px(25)
        dialog._major.setValue(4)
        dialog._accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(GridDialog, "exec", fake_exec)
    window.open_grid_settings()
    grid = window._session.state.document.grid
    assert (grid.spacing, grid.major_every) == (25, 4)
    assert window._session.undo_label == "Change grid"
