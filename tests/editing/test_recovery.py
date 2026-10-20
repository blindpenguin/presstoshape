import json
import os

from presstoshape.editing.operations import composites, documents, edit_mode, recovery, selection, shapes, view
from presstoshape.editing.session import Session
from tests.helpers import all_shapes


def _dirty_session() -> tuple[Session, int]:
    session = Session()
    documents.new_document(session, documents.DocumentSetup(210, 297, "mm", 300))
    bottom = shapes.add_rectangle(session, (0, 0), (100, 100))
    top = shapes.add_rectangle(session, (50, 50), (150, 150))
    selection.set_selection(session, {bottom, top})
    composites.make_composite(session, "subtract")
    (composite,) = session.state.selection
    edit_mode.enter(session, composite)
    view.set_zoom(session, 40)
    return session, composite


def _never_running(run_id: str) -> bool:
    return False


def test_snapshot_round_trip_recovers_an_unsaved_marked_document(tmp_path):
    session, composite = _dirty_session()
    session.state.file_path = "/home/someone/poster.svg"
    recovery.write_snapshot(session, tmp_path, "run1", (500.0, 600.0))
    assert session.state.dirty and session.state.recovered is None

    (snapshot,) = recovery.find_snapshots(tmp_path, _never_running)
    assert (snapshot.run_id, snapshot.original_path, snapshot.name, snapshot.damaged) == (
        "run1",
        "/home/someone/poster.svg",
        "poster.svg",
        False,
    )
    other = Session()
    assert recovery.recover(other, snapshot)
    state = other.state
    assert all_shapes(other) == all_shapes(session)
    assert (state.document.unit, state.document.dpi) == ("mm", 300)
    assert state.edit_path == (composite,) and state.zoom_percent == 40
    assert state.restore_view_center == (500.0, 600.0)
    assert state.dirty and state.file_path is None
    assert state.recovered.original_path == "/home/someone/poster.svg"
    assert state.status_message.startswith("Recovered poster.svg (from ")
    assert not other.can_undo


def test_untitled_documents_and_running_runs(tmp_path):
    session, _composite = _dirty_session()
    recovery.write_snapshot(session, tmp_path, "crashed", None)
    recovery.write_snapshot(session, tmp_path, "alive", None)
    found = recovery.find_snapshots(tmp_path, lambda run_id: run_id == "alive")
    assert [snapshot.run_id for snapshot in found] == ["crashed"]
    assert found[0].name == "" and found[0].original_path is None


def test_newest_first(tmp_path):
    session, _composite = _dirty_session()
    for run_id, when in (("old", 100.0), ("new", 300.0), ("middle", 200.0)):
        recovery.write_snapshot(session, tmp_path, run_id, None)
        info = tmp_path / f"{run_id}.json"
        info.write_text(json.dumps({**json.loads(info.read_text()), "saved_at": when}))
    assert [snapshot.run_id for snapshot in recovery.find_snapshots(tmp_path, _never_running)] == [
        "new",
        "middle",
        "old",
    ]


def test_damaged_snapshots_are_marked(tmp_path):
    session, _composite = _dirty_session()
    for run_id in ("bad_info", "bad_document", "no_info"):
        recovery.write_snapshot(session, tmp_path, run_id, None)
    (tmp_path / "bad_info.json").write_text('{"original_path": 5, "saved_at": "soon"}')
    (tmp_path / "bad_document.p2s").write_bytes(b"not a zip")
    (tmp_path / "no_info.json").unlink()
    found = {snapshot.run_id: snapshot for snapshot in recovery.find_snapshots(tmp_path, _never_running)}
    assert all(snapshot.damaged for snapshot in found.values()) and len(found) == 3
    assert not recovery.recover(Session(), found["bad_document"])


def test_discard_and_adopt(tmp_path):
    session, _composite = _dirty_session()
    recovery.write_snapshot(session, tmp_path, "crashed", None)
    (snapshot,) = recovery.find_snapshots(tmp_path, _never_running)
    adopted = recovery.adopt(tmp_path, snapshot, "mine")
    assert adopted.run_id == "mine" and adopted.document == tmp_path / "mine.p2s"
    assert sorted(os.listdir(tmp_path)) == ["mine.json", "mine.p2s"]
    recovery.discard_snapshot(tmp_path, "mine")
    recovery.discard_snapshot(tmp_path, "mine")
    assert os.listdir(tmp_path) == []
    assert recovery.find_snapshots(tmp_path / "missing", _never_running) == []
