from dataclasses import replace

import pytest

from presstoshape.editing import containers, queries, registry
from presstoshape.editing.operations import composites, edit_mode, groups, node_editing, selection, shapes, view
from presstoshape.editing.operations._document import replace_shape
from presstoshape.editing.session import Session
from presstoshape.geometry import nodes
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo, PathShape, Style
from tests.helpers import all_shapes


def _path_session():
    session = Session()
    sid = shapes.add_path(session, [(0, 0), (50, 0), (100, 50), (150, 0)])
    view.select_tool(session, Tool.NODE)
    return session, sid


def test_set_node_selection_drops_invalid_refs():
    session, sid = _path_session()
    node_editing.set_node_selection(session, {(sid, 1), (sid, 99), (12345, 0)})
    assert session.state.node_selection == {(sid, 1)}


def test_node_commands_are_one_undo_step_each():
    session, sid = _path_session()
    depth = session.undo_count
    node_editing.move_nodes(session, sid, {1}, 5, 5)
    node_editing.move_control(session, sid, (2, 1), (60, 30))
    node_editing.insert_node(session, sid, 1, 0.5)
    assert session.undo_count == depth + 3
    assert session.state.node_selection == {(sid, 1)}
    assert len(queries.find_shape(session.state, sid).segments) == 5


def test_delete_with_selected_nodes_keeps_shape():
    session, sid = _path_session()
    node_editing.set_node_selection(session, {(sid, 1)})
    selection.delete_selection(session)
    path = queries.find_shape(session.state, sid)
    assert isinstance(path, PathShape) and len(path.segments) == 3
    assert session.state.node_selection == frozenset()


def test_deleting_all_nodes_removes_shape_and_undo_restores_it():
    session, sid = _path_session()
    node_editing.set_node_selection(session, {(sid, i) for i in range(4)})
    selection.delete_selection(session)
    assert queries.find_shape(session.state, sid) is None and session.state.selection == set()
    session.undo()
    assert isinstance(queries.find_shape(session.state, sid), PathShape)


def test_undo_and_tool_change_clear_node_selection():
    session, sid = _path_session()
    node_editing.set_node_selection(session, {(sid, 1)})
    node_editing.move_nodes(session, sid, {1}, 5, 5)
    session.undo()
    assert session.state.node_selection == frozenset()
    node_editing.set_node_selection(session, {(sid, 1)})
    view.select_tool(session, Tool.SELECT)
    assert session.state.node_selection == frozenset()


def test_delete_without_node_selection_deletes_shape_under_node_tool():
    session, sid = _path_session()
    selection.delete_selection(session)
    assert queries.find_shape(session.state, sid) is None


# --- node commands ------------------------------------------------------------------

OPEN = (MoveTo(0, 0), LineTo(10, 0), LineTo(20, 10), LineTo(30, 10))
OTHER = (MoveTo(50, 0), CubicTo(55, 5, 60, 5, 60, 0))
SQUARE = (MoveTo(0, 0), LineTo(10, 0), LineTo(10, 10), LineTo(0, 10), Close())


def _paths(*segment_lists):
    """A session in the Node tool with these paths selected, bottom first; returns their ids."""
    session = Session()
    ids = [shapes.add_drawn_path(session, segments, Tool.PEN) for segments in segment_lists]
    selection.set_selection(session, set(ids))
    view.select_tool(session, Tool.NODE)
    return session, ids


def _segments(session, sid):
    return queries.find_shape(session.state, sid).segments


def _run(session, command_id):
    entry = registry.find(command_id)
    assert entry.can_run(session)
    depth = session.undo_count
    entry.invoke(session)
    assert session.undo_count == depth + 1


@pytest.mark.parametrize(
    "command_id",
    [
        "path.node_corner",
        "path.node_smooth",
        "path.node_symmetric",
        "path.make_line",
        "path.make_curve",
        "path.break_nodes",
        "path.join_nodes",
        "path.join_segment",
        "path.delete_segment",
    ],
)
def test_node_commands_need_the_node_tool_and_selected_nodes(command_id):
    session, (sid,) = _paths(OPEN)
    assert not registry.find(command_id).can_run(session)
    node_editing.set_node_selection(session, {(sid, i) for i in range(4)})
    view.select_tool(session, Tool.SELECT)
    assert not registry.find(command_id).can_run(session)


def test_smooth_and_corner_keep_the_node_selection():
    session, (sid,) = _paths(OPEN)
    node_editing.set_node_selection(session, {(sid, 1)})
    _run(session, "path.node_smooth")
    assert session.undo_label == "Make nodes smooth"
    assert nodes.nodes(_segments(session, sid))[1].smooth
    assert session.state.node_selection == {(sid, 1)}
    _run(session, "path.node_corner")
    assert not nodes.nodes(_segments(session, sid))[1].smooth
    session.undo()
    assert nodes.nodes(_segments(session, sid))[1].smooth


def test_make_curve_and_line_need_matching_segments():
    session, (sid,) = _paths(OPEN)
    node_editing.set_node_selection(session, {(sid, 0), (sid, 1)})
    assert not registry.find("path.make_line").can_run(session)
    _run(session, "path.make_curve")
    assert isinstance(_segments(session, sid)[1], CubicTo)
    assert not registry.find("path.make_curve").can_run(session)
    _run(session, "path.make_line")
    assert _segments(session, sid) == OPEN


def test_break_selects_both_new_ends_and_ignores_end_nodes():
    session, (sid,) = _paths(SQUARE)
    node_editing.set_node_selection(session, {(sid, 2)})
    _run(session, "path.break_nodes")
    assert session.undo_label == "Break path"
    assert session.state.node_selection == {(sid, 0), (sid, 4)}
    assert not isinstance(_segments(session, sid)[-1], Close)
    node_editing.set_node_selection(session, {(sid, 0)})
    assert not registry.find("path.break_nodes").can_run(session)


def test_delete_segment_removes_a_path_left_empty():
    session, (sid,) = _paths(OPEN[:2])
    node_editing.set_node_selection(session, {(sid, 0), (sid, 1)})
    _run(session, "path.delete_segment")
    assert queries.find_shape(session.state, sid) is None
    assert session.state.selection == set() and session.state.node_selection == frozenset()


def test_join_two_ends_of_one_path_closes_it():
    session, (sid,) = _paths(OPEN)
    node_editing.set_node_selection(session, {(sid, 0), (sid, 3)})
    _run(session, "path.join_segment")
    assert isinstance(_segments(session, sid)[-1], Close)
    assert session.state.node_selection == {(sid, 0), (sid, 3)}


def test_join_two_paths_keeps_the_higher_one():
    session, (low, high) = _paths(OPEN, OTHER)
    restyled = replace(queries.find_shape(session.state, high), style=Style(fill="#ff0000"))
    with session.edit("restyle"):
        replace_shape(session.state, restyled)
    node_editing.set_node_selection(session, {(low, 3), (high, 0)})
    _run(session, "path.join_nodes")
    assert session.undo_label == "Join nodes"
    assert queries.find_shape(session.state, low) is None
    joined = queries.find_shape(session.state, high)
    assert joined.style == restyled.style
    assert [n.point for n in nodes.nodes(joined.segments)] == [(60, 0), (40, 5), (20, 10), (10, 0), (0, 0)]
    assert session.state.selection == {high}
    assert session.state.node_selection == {(high, 1)}
    assert all_shapes(session) == [joined]
    session.undo()
    assert len(all_shapes(session)) == 2


def test_join_needs_exactly_two_end_nodes():
    session, (low, high) = _paths(OPEN, OTHER)
    node_editing.set_node_selection(session, {(low, 3), (high, 0), (low, 0)})
    assert not registry.find("path.join_segment").can_run(session)
    node_editing.set_node_selection(session, {(low, 2), (high, 0)})
    assert not registry.find("path.join_segment").can_run(session)
    node_editing.set_node_selection(session, {(low, 0), (low, 1)})
    assert not registry.find("path.join_nodes").can_run(session)
    short, (sid,) = _paths(OPEN[:2])
    node_editing.set_node_selection(short, {(sid, 0), (sid, 1)})
    assert not registry.find("path.join_nodes").can_run(short)
    assert registry.find("path.join_segment").can_run(short)


def test_node_commands_inside_an_entered_group():
    session, ids = _paths(OPEN, OTHER)
    groups.group(session)
    [group_id] = session.state.selection
    edit_mode.enter(session, group_id)
    selection.set_selection(session, set(ids))
    view.select_tool(session, Tool.NODE)
    node_editing.set_node_selection(session, {(ids[0], 3), (ids[1], 0)})
    _run(session, "path.join_segment")
    group = queries.find_shape(session.state, group_id)
    assert [child.id for child in group.children] == [ids[1]]


def test_node_commands_on_composite_parts_keep_their_mode():
    session, ids = _paths(SQUARE, OPEN)
    composites.make_composite(session, "subtract")
    [composite_id] = session.state.selection
    edit_mode.enter(session, composite_id)
    selection.set_selection(session, {ids[1]})
    view.select_tool(session, Tool.NODE)
    node_editing.set_node_selection(session, {(ids[1], 1)})
    mode = containers.part_mode(session.state, ids[1])
    _run(session, "path.break_nodes")
    assert containers.part_mode(session.state, ids[1]) == mode
