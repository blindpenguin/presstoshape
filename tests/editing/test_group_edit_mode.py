"""Entering groups: the active container machinery shared with Composites."""

from presstoshape.editing import containers, queries
from presstoshape.editing.operations import clipboard, edit_mode, selection, shapes
from presstoshape.editing.session import Session
from presstoshape.models.shapes import CompositeShape, GroupShape, RectShape, Style
from tests.helpers import all_shapes

S = Style()


def _rect(shape_id: int, x: float = 0) -> RectShape:
    return RectShape(shape_id, x, 0, 10, 10, S)


def _session() -> Session:
    """Layer: [rect 1, group 10 = [rect 2, Composite 20 = [rect 3, rect 4], group 30 = [rect 5]]]."""
    session = Session()
    composite = CompositeShape(20, (_rect(3), _rect(4, 5)), ("add", "subtract"), S)
    inner = GroupShape(30, (_rect(5, 40),))
    session.state.document.layers[0].shapes = [_rect(1, 100), GroupShape(10, (_rect(2), composite, inner))]
    session.state.document.next_id = 50
    return session


def _group(session) -> GroupShape:
    return session.state.document.layers[0].shapes[1]


def test_entering_a_group_makes_its_children_pickable():
    session = _session()
    edit_mode.enter(session, 10)
    assert containers.valid_edit_path(session.state) == (10,)
    assert [shape.id for shape in queries.pickable_shapes(session.state)] == [2, 20, 30]
    assert containers.edited_composite(session.state) is None
    assert session.state.status_message == "Editing a group: Esc or Done to leave"
    assert not session.can_undo


def test_chains_mix_groups_and_composites():
    session = _session()
    edit_mode.enter(session, 10)
    edit_mode.enter(session, 20)
    assert [shape.id for shape in containers.edit_chain(session.state)] == [10, 20]
    assert containers.part_mode(session.state, 4) == "subtract"
    edit_mode.leave(session)
    assert session.state.selection == {20}
    assert session.state.status_message == "Editing a group"
    edit_mode.enter(session, 30)
    assert [shape.id for shape in queries.pickable_shapes(session.state)] == [5]


def test_drawn_shapes_and_text_go_into_the_entered_group():
    session = _session()
    edit_mode.enter(session, 10)
    rect = shapes.add_rectangle(session, (0, 50), (20, 70))
    text = shapes.add_text(session, (0, 90), "Inside")
    assert [child.id for child in _group(session).children][-2:] == [rect, text]
    assert len(session.state.document.layers[0].shapes) == 2


def test_text_is_still_refused_inside_a_composite_in_a_group():
    session = _session()
    edit_mode.enter(session, 10)
    edit_mode.enter(session, 20)
    assert shapes.add_text(session, (0, 0), "No") is None


def test_changes_inside_rebuild_every_level():
    session = _session()
    edit_mode.enter(session, 10)
    edit_mode.enter(session, 20)
    selection.set_selection(session, {3})
    selection.delete_selection(session)
    composite = _group(session).children[1]
    assert isinstance(composite, CompositeShape) and [part.id for part in composite.parts] == [4]


def test_deleting_the_last_child_removes_the_group_and_leaves():
    session = _session()
    edit_mode.enter(session, 10)
    edit_mode.enter(session, 30)
    selection.set_selection(session, {5})
    selection.delete_selection(session)
    assert containers.valid_edit_path(session.state) == (10,)
    assert [child.id for child in _group(session).children] == [2, 20]
    selection.set_selection(session, {2, 20})
    selection.delete_selection(session)
    assert containers.valid_edit_path(session.state) == ()
    assert [shape.id for shape in all_shapes(session)] == [1]
    session.undo()
    assert [child.id for child in _group(session).children] == [2, 20]


def test_undo_past_the_group_trims_the_edit_path():
    session = Session()
    with session.edit("Make group"):
        session.state.document.layers[0].shapes = [GroupShape(1, (_rect(2),))]
    edit_mode.enter(session, 1)
    session.undo()
    assert containers.valid_edit_path(session.state) == ()


def test_pasting_a_group_into_a_composite_adds_its_shapes_as_parts():
    session = _session()
    selection.set_selection(session, {10})
    content = clipboard.copy_selection(session)
    edit_mode.enter(session, 10)
    edit_mode.enter(session, 20)
    assert clipboard.paste(session, content.native, None, None)
    parts = _group(session).children[1].parts
    # The group's rect, Composite and nested group's rect join the two existing parts.
    assert not any(isinstance(part, GroupShape) for part in parts)
    assert len(parts) == 2 + 3


def test_pasting_a_group_into_a_group_keeps_it():
    session = _session()
    selection.set_selection(session, {10})
    content = clipboard.copy_selection(session)
    edit_mode.enter(session, 10)
    assert clipboard.paste(session, content.native, None, None)
    assert isinstance(_group(session).children[-1], GroupShape)
