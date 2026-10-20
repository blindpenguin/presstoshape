import pytest

from presstoshape.editing.operations import guides
from presstoshape.editing.registry import find
from presstoshape.editing.session import Session
from presstoshape.models.layout import GridSettings, Guide


def test_guides_are_added_moved_and_deleted_as_undo_steps():
    session = Session()
    guide_id = guides.add_guide(session, "vertical", 120)
    assert session.state.document.guides == (Guide(guide_id, "vertical", 120.0),)
    for position in (130, 140, 150):
        guides.move_guide(session, guide_id, position)
    assert session.undo_label == "Move guide"
    session.undo()
    assert session.state.document.guides[0].position == 120
    guides.delete_guide(session, guide_id)
    assert session.state.document.guides == ()
    session.undo()
    assert len(session.state.document.guides) == 1


def test_clear_guides_is_one_step_and_needs_guides():
    session = Session()
    command = find("view.clear_guides")
    assert not command.can_run(session)
    guides.add_guide(session, "horizontal", 10)
    guides.add_guide(session, "vertical", 20)
    command.invoke(session)
    assert session.state.document.guides == ()
    session.undo()
    assert len(session.state.document.guides) == 2


def test_guide_ids_come_from_the_document():
    session = Session()
    session.state.document.next_id = 40
    assert guides.add_guide(session, "horizontal", 0) == 40
    assert session.state.document.next_id == 41


def test_grid_changes_are_undoable_and_validated():
    session = Session()
    guides.set_grid(session, 25, 4)
    assert session.state.document.grid == GridSettings(25, 4)
    session.undo()
    assert session.state.document.grid is None
    with pytest.raises(ValueError):
        guides.set_grid(session, 0, 4)
    with pytest.raises(ValueError):
        guides.add_guide(session, "diagonal", 0)
