import pytest
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from presstoshape.editing.operations import documents, recovery, shapes
from presstoshape.editing.session import Session
from presstoshape.views import app_settings, recovery_keeper
from presstoshape.views.recovery_keeper import RecoveryKeeper


@pytest.fixture
def setup(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    # One "minute" of recovery interval lasts 20 ms in these tests.
    monkeypatch.setattr(recovery_keeper, "MINUTE_MS", 20)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    app_settings.set_recovery_interval(settings, 1)
    session = Session()
    keeper = RecoveryKeeper(session, tmp_path / "recovery", lambda: (0.0, 0.0), settings)
    session.subscribe(keeper.refresh)
    yield session, keeper, settings, tmp_path / "recovery"
    keeper.finish()


def _snapshot(folder, keeper):
    return folder / f"{keeper.run_id}.p2s"


def test_dirty_document_gets_a_snapshot_after_the_interval(setup):
    session, keeper, _settings, folder = setup
    shapes.add_rectangle(session, (0, 0), (10, 10))
    assert not _snapshot(folder, keeper).exists()
    QTest.qWait(80)
    assert _snapshot(folder, keeper).exists()
    written = _snapshot(folder, keeper).stat().st_mtime_ns
    keeper.refresh()
    QTest.qWait(80)
    assert _snapshot(folder, keeper).stat().st_mtime_ns == written


def test_saving_or_turning_off_removes_the_snapshot(setup, tmp_path):
    session, keeper, settings, folder = setup
    shapes.add_rectangle(session, (0, 0), (10, 10))
    QTest.qWait(80)
    assert _snapshot(folder, keeper).exists()
    documents.save_file(session, str(tmp_path / "saved.p2s"))
    assert not _snapshot(folder, keeper).exists()
    shapes.add_rectangle(session, (20, 0), (30, 10))
    QTest.qWait(80)
    assert _snapshot(folder, keeper).exists()
    app_settings.set_recovery_interval(settings, 0)
    keeper.refresh()
    assert not _snapshot(folder, keeper).exists()


def test_finish_removes_snapshot_and_lock(setup):
    session, keeper, _settings, folder = setup
    shapes.add_rectangle(session, (0, 0), (10, 10))
    QTest.qWait(80)
    keeper.finish()
    assert list(folder.iterdir()) == []


def test_other_live_runs_count_as_running_and_their_snapshots_are_not_offered(setup, tmp_path):
    session, keeper, settings, folder = setup
    other = RecoveryKeeper(Session(), folder, lambda: (0.0, 0.0), settings)
    shapes.add_rectangle(session, (0, 0), (10, 10))
    QTest.qWait(80)
    assert other.is_running(keeper.run_id) and keeper.is_running(other.run_id)
    assert recovery.find_snapshots(folder, other.is_running) == []
    assert not keeper.is_running("crashed-run-without-lock")
    other.finish()


def test_unwritable_folder_disables_recovery_with_a_message(tmp_path):
    QApplication.instance() or QApplication([])
    blocker = tmp_path / "file"
    blocker.write_text("")
    session = Session()
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    keeper = RecoveryKeeper(session, blocker / "recovery", lambda: (0.0, 0.0), settings)
    assert "recovery data" in session.state.status_message
    shapes.add_rectangle(session, (0, 0), (10, 10))
    keeper.refresh()
    keeper.finish()
