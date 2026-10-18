from presstoshape.editing.operations import documents, shapes
from presstoshape.editing.session import Session
from tests.helpers import all_shapes


def test_save_and_open_roundtrip(tmp_path):
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    path = tmp_path / "a.svg"
    assert documents.save_file(session, str(path))
    assert not session.state.dirty and session.state.file_path == str(path)

    other = Session()
    assert documents.open_file(other, str(path))
    assert all_shapes(other) == all_shapes(session)
    assert not other.can_undo


def test_save_without_path_returns_false():
    assert not documents.save_file(Session())


def test_open_bad_file_reports_and_keeps_document(tmp_path):
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    bad = tmp_path / "bad.svg"
    bad.write_text("<svg")
    assert not documents.open_file(session, str(bad))
    assert "Could not open" in session.state.status_message
    assert len(all_shapes(session)) == 1
