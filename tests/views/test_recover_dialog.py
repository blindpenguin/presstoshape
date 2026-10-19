import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from presstoshape.editing.operations import recovery, shapes
from presstoshape.editing.session import Session
from presstoshape.views.recover_dialog import RecoverDialog


@pytest.fixture
def snapshots(tmp_path):
    QApplication.instance() or QApplication([])
    session = Session()
    shapes.add_rectangle(session, (0, 0), (100, 100))
    session.state.file_path = str(tmp_path / "poster.p2s")
    recovery.write_snapshot(session, tmp_path, "good", None)
    session.state.file_path = None
    recovery.write_snapshot(session, tmp_path, "broken", None)
    (tmp_path / "broken.p2s").write_bytes(b"junk")
    return recovery.find_snapshots(tmp_path, lambda run_id: False), tmp_path


def test_lists_snapshots_with_previews_and_damaged_ones(snapshots):
    found, folder = snapshots
    dialog = RecoverDialog(found, folder)
    texts = [dialog._list.item(row).text() for row in range(dialog._list.count())]
    assert any(text.startswith("poster.p2s\n") for text in texts)
    assert any("Untitled (damaged" in text for text in texts)
    good_row = next(row for row, text in enumerate(texts) if text.startswith("poster.p2s"))
    assert not dialog._list.item(good_row).icon().isNull()
    dialog._list.setCurrentRow(good_row)
    assert dialog._recover_button.isEnabled()
    dialog._list.setCurrentRow(1 - good_row)
    assert not dialog._recover_button.isEnabled() and dialog._discard_button.isEnabled()


def test_recover_returns_the_choice(snapshots):
    found, folder = snapshots
    dialog = RecoverDialog(found, folder)
    texts = [dialog._list.item(row).text() for row in range(dialog._list.count())]
    dialog._list.setCurrentRow(next(row for row, text in enumerate(texts) if text.startswith("poster.p2s")))
    dialog._recover()
    assert dialog.chosen.run_id == "good"


def test_discard_asks_then_deletes(snapshots, monkeypatch):
    found, folder = snapshots
    dialog = RecoverDialog(found, folder)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    dialog._discard()
    assert dialog._list.count() == 2
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    dialog._discard()
    dialog._discard()
    assert sorted(path.suffix for path in folder.iterdir()) == []
    assert dialog.chosen is None
