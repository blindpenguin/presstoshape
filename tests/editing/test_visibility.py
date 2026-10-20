from dataclasses import replace

import pytest

from presstoshape.editing import containers, queries
from presstoshape.editing.operations import edit_mode, groups, selection, transform, visibility
from presstoshape.editing.operations.selection import delete_selection, move_selection
from presstoshape.editing.registry import find
from presstoshape.editing.session import Session
from presstoshape.models.shapes import CompositeShape, GroupShape, RectShape, Style

S = Style(fill="#ff0000", stroke=None)


def _rect(shape_id: int, x: float = 0, **flags) -> RectShape:
    return RectShape(shape_id, x, 0, 10, 10, S, **flags)


def _session(*shapes) -> Session:
    session = Session()
    session.state.document.layers[0].shapes = list(shapes)
    session.state.document.next_id = 100
    return session


def _top(session) -> list:
    return session.state.document.layers[0].shapes


def _shape(session, shape_id):
    return queries.find_shape(session.state, shape_id)


@pytest.mark.parametrize(
    "run, flag, label",
    [(visibility.hide_selection, "hidden", "Hide"), (visibility.lock_selection, "locked", "Lock")],
)
def test_hide_and_lock_flag_the_selection_in_one_step_and_clear_it(run, flag, label):
    session = _session(_rect(1), _rect(2), _rect(3))
    selection.set_selection(session, {1, 3})
    depth = session.undo_count
    run(session)
    assert [getattr(shape, flag) for shape in _top(session)] == [True, False, True]
    assert session.state.selection == set()
    assert (session.undo_count, session.undo_label) == (depth + 1, label)
    assert session.state.status_message.startswith("2 objects")
    session.undo()
    assert not any(getattr(shape, flag) for shape in _top(session))


def test_hide_and_lock_need_a_selection():
    session = _session(_rect(1))
    assert not find("object.hide").can_run(session) and not find("object.lock").can_run(session)
    visibility.hide_selection(session)
    assert session.undo_count == 0
    selection.set_selection(session, {1})
    assert find("object.hide").can_run(session) and find("object.lock").can_run(session)


def test_show_all_shows_nested_shapes_and_selects_the_pickable_ones():
    group = GroupShape(5, (_rect(2, hidden=True), _rect(3)))
    session = _session(_rect(1, hidden=True), group, _rect(4, hidden=True, locked=True))
    session.state.document.layers[0].visible = True
    assert find("object.show_all").can_run(session)
    visibility.show_all(session)
    assert not queries.any_hidden(session.state)
    assert session.undo_label == "Show all"
    # The group child isn't in the active container and 4 stays locked.
    assert session.state.selection == {1}
    assert session.state.status_message == "3 objects shown"
    assert not find("object.show_all").can_run(session)


def test_show_all_leaves_layer_visibility_alone():
    from presstoshape.editing.operations import layers

    session = _session(_rect(1, hidden=True))
    layers.set_layer_visible(session, 0, False)
    visibility.show_all(session)
    assert not session.state.document.layers[0].visible and not _top(session)[0].hidden
    assert session.state.selection == set()


def test_show_all_and_unlock_all_with_nothing_to_do():
    session = _session(_rect(1))
    visibility.show_all(session)
    assert session.state.status_message == "Nothing to show" and session.undo_count == 0
    visibility.unlock_all(session)
    assert session.state.status_message == "Nothing to unlock" and session.undo_count == 0


def test_unlock_all_unlocks_everything_and_leaves_layer_locks():
    from presstoshape.editing.operations import layers

    group = GroupShape(5, (_rect(2, locked=True), _rect(3)), locked=True)
    session = _session(_rect(1, locked=True), group)
    layers.set_layer_locked(session, 0, True)
    layers.set_layer_locked(session, 0, False)
    visibility.unlock_all(session)
    assert session.undo_label == "Unlock all"
    assert not queries.any_locked(session.state)
    assert session.state.selection == {1, 5}
    session2 = _session(_rect(1, locked=True))
    session2.state.document.layers[0].locked = True
    visibility.unlock_all(session2)
    assert session2.state.document.layers[0].locked and session2.state.selection == set()


def test_toggles_reach_nested_shapes_and_keep_the_selection():
    inner = CompositeShape(6, (_rect(3), _rect(4)), ("add", "subtract"), S)
    session = _session(_rect(1), GroupShape(5, (_rect(2), inner)))
    selection.set_selection(session, {1})
    visibility.set_hidden(session, 4, True)
    assert _shape(session, 4).hidden and session.undo_label == "Hide"
    assert _shape(session, 6).modes == ("add", "subtract")
    visibility.set_locked(session, 2, True)
    assert _shape(session, 2).locked and session.undo_label == "Lock"
    assert session.state.selection == {1}
    visibility.set_hidden(session, 4, False)
    visibility.set_locked(session, 2, False)
    assert session.undo_label == "Unlock" and not _shape(session, 4).hidden and not _shape(session, 2).locked


def test_toggles_ignore_unknown_ids_and_unchanged_flags():
    session = _session(_rect(1))
    visibility.set_hidden(session, 99, True)
    visibility.set_locked(session, 1, False)
    assert session.undo_count == 0


def test_toggling_a_selected_shape_drops_it_from_the_selection():
    session = _session(_rect(1), _rect(2))
    selection.set_selection(session, {1, 2})
    visibility.set_locked(session, 1, True)
    assert session.state.selection == {2}


@pytest.mark.parametrize("toggle", [visibility.set_hidden, visibility.set_locked])
def test_hiding_or_locking_the_entered_group_leaves_edit_mode(toggle):
    session = _session(GroupShape(5, (_rect(1), _rect(2))))
    edit_mode.enter(session, 5)
    selection.set_selection(session, {1})
    toggle(session, 5, True)
    assert session.state.edit_path == () and session.state.selection == set()


def test_commands_inside_an_entered_group_work_on_its_children():
    session = _session(GroupShape(5, (_rect(1), _rect(2))))
    edit_mode.enter(session, 5)
    selection.set_selection(session, {1})
    visibility.hide_selection(session)
    assert session.state.edit_path == (5,)
    assert _shape(session, 1).hidden
    assert [shape.id for shape in queries.pickable_shapes(session.state)] == [2]
    visibility.show_all(session)
    assert session.state.selection == {1}


def test_moving_and_deleting_a_group_takes_its_hidden_and_locked_children_along():
    session = _session(GroupShape(5, (_rect(1, hidden=True), _rect(2, locked=True), _rect(3))))
    selection.set_selection(session, {5})
    move_selection(session, 10, 0)
    group = _top(session)[0]
    assert [child.x for child in group.children] == [10, 10, 10]
    assert group.children[0].hidden and group.children[1].locked
    transform.flip(session, True)
    assert _top(session)[0].children[0].hidden
    delete_selection(session)
    assert _top(session) == []


def test_ungroup_keeps_the_childrens_flags():
    session = _session(GroupShape(5, (_rect(1, hidden=True), _rect(2))))
    selection.set_selection(session, {5})
    groups.ungroup(session)
    assert [(shape.id, shape.hidden) for shape in _top(session)] == [(1, True), (2, False)]
    assert session.state.selection == {2}


def test_any_hidden_follows_undo():
    session = _session(_rect(1))
    selection.set_selection(session, {1})
    visibility.hide_selection(session)
    assert queries.any_hidden(session.state)
    session.undo()
    assert not queries.any_hidden(session.state)
    assert containers.pickable_shapes(session.state) == [replace(_rect(1))]


def test_releasing_a_composite_doesnt_select_its_hidden_or_locked_parts():
    from presstoshape.editing.operations import composites

    composite = CompositeShape(5, (_rect(1), _rect(2, hidden=True), _rect(3, locked=True)), ("add",) * 3, S)
    session = _session(composite)
    selection.set_selection(session, {5})
    composites.release_composite(session)
    assert session.state.selection == {1}


# --- select_object ---------------------------------------------------------------------------


def _tree_session():
    from presstoshape.models.app_state import Layer

    session = Session()
    composite = CompositeShape(20, (_rect(3), _rect(4)), ("add", "subtract"), S)
    other = GroupShape(30, (_rect(5), _rect(6)))
    session.state.document.layers = [
        Layer("Bottom", True, [_rect(1), other]),
        Layer("Top", True, [GroupShape(10, (_rect(2), composite))]),
    ]
    session.state.document.next_id = 100
    return session


def test_select_object_enters_the_containers_around_it():
    session = _tree_session()
    depth = session.undo_count
    visibility.select_object(session, 4)
    assert session.state.selected_layer_index == 1
    assert session.state.edit_path == (10, 20) and session.state.selection == {4}
    assert session.undo_count == depth


def test_select_object_moves_from_one_entered_container_to_another():
    session = _tree_session()
    edit_mode.enter(session, 30)
    visibility.select_object(session, 3)
    assert session.state.edit_path == (10, 20) and session.state.selection == {3}
    visibility.select_object(session, 1)
    assert session.state.edit_path == () and session.state.selection == {1}
    assert session.state.selected_layer_index == 0


def test_select_object_extends_only_within_the_same_container():
    session = _tree_session()
    visibility.select_object(session, 3)
    visibility.select_object(session, 4, extend=True)
    assert session.state.selection == {3, 4}
    visibility.select_object(session, 2, extend=True)
    assert session.state.edit_path == (10,) and session.state.selection == {2}
    visibility.select_object(session, 1)
    visibility.select_object(session, 10, extend=True)
    assert session.state.selection == {1, 10}


def test_select_object_refuses_hidden_locked_and_inherited_and_unknown():
    session = _tree_session()
    visibility.set_hidden(session, 4, True)
    visibility.set_locked(session, 30, True)
    selection.set_selection(session, {1})
    for shape_id in (4, 30, 5, 99):
        visibility.select_object(session, shape_id)
        assert session.state.selection == {1} and session.state.edit_path == ()
    session.state.document.layers[1].locked = True
    visibility.select_object(session, 2)
    assert session.state.selection == {1}
