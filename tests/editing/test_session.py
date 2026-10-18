import pytest

from presstoshape.editing.session import Session
from presstoshape.models.shapes import RectShape, Style


def _add_rect(session: Session, shape_id: int, label: str = "Add rectangle", merge_key: str | None = None) -> None:
    with session.edit(label, merge_key) as state:
        state.document.layers[0].shapes.append(RectShape(shape_id, 0, 0, 10, 10, Style()))


def test_edit_records_one_labelled_step_and_notifies_once(session):
    calls = []
    session.subscribe(lambda: calls.append(1))
    _add_rect(session, 1)
    assert session.undo_count == 1 and session.undo_label == "Add rectangle"
    assert session.state.dirty and calls == [1]


def test_undo_redo_swap_labels_and_restore_document(session):
    _add_rect(session, 1)
    session.undo()
    assert session.state.document.layers[0].shapes == []
    assert session.undo_label is None and session.redo_label == "Add rectangle"
    session.redo()
    assert len(session.state.document.layers[0].shapes) == 1
    assert session.undo_label == "Add rectangle" and session.redo_label is None


def test_merge_key_extends_previous_step(session):
    _add_rect(session, 1, "Change width", merge_key="1:width")
    _add_rect(session, 2, "Change width", merge_key="1:width")
    assert session.undo_count == 1
    session.end_merge()
    _add_rect(session, 3, "Change width", merge_key="1:width")
    assert session.undo_count == 2


def test_exception_inside_edit_changes_nothing(session):
    calls = []
    session.subscribe(lambda: calls.append(1))
    with pytest.raises(RuntimeError):
        with session.edit("Broken") as state:
            state.document.layers[0].shapes.append(RectShape(1, 0, 0, 10, 10, Style()))
            raise RuntimeError
    assert session.state.document.layers[0].shapes == []
    assert session.undo_count == 0 and not session.state.dirty and calls == []


def test_undo_prunes_selection_and_clears_node_selection(session):
    _add_rect(session, 1)
    session.state.selection = {1}
    session.state.node_selection = frozenset({(1, 0)})
    session.undo()
    assert session.state.selection == set()
    assert session.state.node_selection == frozenset()
    assert session.state.status_message == "Undo"


def test_new_edit_clears_redo(session):
    _add_rect(session, 1)
    session.undo()
    _add_rect(session, 2)
    assert not session.can_redo


def test_clear_history(session):
    _add_rect(session, 1)
    session.clear_history()
    assert not session.can_undo and not session.can_redo
