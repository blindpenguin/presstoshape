from veccy.editing import queries
from veccy.editing.operations import node_editing, selection, shapes, view
from veccy.editing.session import Session
from veccy.models.app_state import Tool
from veccy.models.shapes import PathShape


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
