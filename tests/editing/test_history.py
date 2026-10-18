from tests.helpers import all_shapes
from veccy.editing.operations import selection, shapes
from veccy.editing.session import Session


def test_undo_redo_add_and_move():
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    selection.move_selection(session, 5, 0)
    assert all_shapes(session)[0].x == 5
    session.undo()
    assert all_shapes(session)[0].x == 0
    session.undo()
    assert all_shapes(session) == [] and session.state.selection == set()
    session.redo()
    session.redo()
    assert all_shapes(session)[0].x == 5
    assert not session.can_redo


def test_new_edit_clears_redo():
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    session.undo()
    shapes.add_ellipse(session, (0, 0), (10, 10))
    assert not session.can_redo
