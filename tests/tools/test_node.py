

from presstoshape.editing import queries
from presstoshape.editing.operations import composites, node_editing, selection, shapes, view
from presstoshape.geometry import nodes
from presstoshape.models.app_state import Tool
from presstoshape.tools.base import CursorType, Mods
from tests.helpers import drag, setup_tools

NONE = Mods()


def _node_setup():
    session, g = setup_tools()
    sid = shapes.add_path(session, [(0, 0), (100, 0), (200, 100)])
    view.select_tool(session, Tool.NODE)
    g.set_tool(Tool.NODE)
    return session, g, sid


def test_node_click_selects_and_shift_toggles():
    session, g, sid = _node_setup()
    drag(g, (100, 0), (100, 0))
    assert session.state.node_selection == {(sid, 1)}
    drag(g, (200, 100), (200, 100), shift=True)
    assert session.state.node_selection == {(sid, 1), (sid, 2)}
    drag(g, (100, 0), (100, 0), shift=True)
    assert session.state.node_selection == {(sid, 2)}


def test_node_band_selects_nodes():
    session, g, sid = _node_setup()
    drag(g, (-10, -10), (150, 20))
    assert session.state.node_selection == {(sid, 0), (sid, 1)}


def test_node_drag_commits_one_move():
    session, g, sid = _node_setup()
    depth = session.undo_count
    g.press((100, 0), NONE)
    g.move((110, 20), NONE)
    (live,) = g.overlay.live
    assert (live.segments[1].x, live.segments[1].y) == (110, 20)
    assert queries.find_shape(session.state, sid).segments[1].x == 100
    g.release((110, 20), NONE)
    moved = queries.find_shape(session.state, sid).segments[1]
    assert (moved.x, moved.y) == (110, 20)
    assert session.undo_count == depth + 1


def test_control_drag_keeps_smooth_unless_alt():
    session, g, sid = _node_setup()
    drag(g, (100, 0), (100, 0))
    path = queries.find_shape(session.state, sid)
    c2 = (path.segments[1].c2x, path.segments[1].c2y)
    drag(g, c2, (c2[0] - 10, c2[1] - 30))
    smooth = queries.find_shape(session.state, sid)
    assert smooth.segments[2] != path.segments[2]
    session.undo()
    node_editing.set_node_selection(session, {(sid, 1)})
    drag(g, c2, (c2[0] - 10, c2[1] - 30), alt=True)
    assert queries.find_shape(session.state, sid).segments[2] == path.segments[2]


def test_double_click_on_segment_inserts_node():
    session, g, sid = _node_setup()
    path = queries.find_shape(session.state, sid)
    on_curve = nodes._eval(path.segments, nodes._Topology(path.segments), 2, 0.5)
    g.double_click(on_curve, NONE)
    assert len(queries.find_shape(session.state, sid).segments) == len(path.segments) + 1
    assert session.state.node_selection == {(sid, 2)}


def test_node_escape_order():
    session, g, sid = _node_setup()
    drag(g, (100, 0), (100, 0))
    g.press((100, 0), NONE)
    g.move((120, 0), NONE)
    g.escape()
    assert g.overlay.live == () and queries.find_shape(session.state, sid).segments[1].x == 100
    assert session.state.node_selection == {(sid, 1)}
    g.escape()
    assert session.state.node_selection == frozenset() and session.state.selection == {sid}
    g.escape()
    assert session.state.selection == set()


def test_node_hover_types_and_hint_for_rect():
    session, g, sid = _node_setup()
    assert g.hover((100, 0)) is CursorType.NODE
    path = queries.find_shape(session.state, sid)
    on_curve = nodes._eval(path.segments, nodes._Topology(path.segments), 2, 0.5)
    assert g.hover(on_curve) is CursorType.NODE_INSERT
    assert g.hover((500, 500)) is CursorType.ARROW
    assert g.hint is None
    rect = shapes.add_rectangle(session, (300, 300), (350, 350))
    selection.set_selection(session, {rect})
    assert "Object to Path" in g.hint


def test_node_overlay_shows_controls_of_selected_nodes():
    session, g, sid = _node_setup()
    assert g.overlay.nodes[0].controls == frozenset()
    drag(g, (100, 0), (100, 0))
    (overlay,) = g.overlay.nodes
    assert overlay.selected == {1}
    assert overlay.controls == {(1, 1), (1, 2), (2, 1), (2, 2)}


def test_node_tool_edits_a_path_part_inside_a_composite():
    session, g = setup_tools()
    path_id = shapes.add_path(session, [(0, 0), (100, 0), (200, 100)])
    rect = shapes.add_rectangle(session, (300, 300), (310, 310))
    selection.set_selection(session, {path_id, rect})
    composites.make_composite(session)
    (composite_id,) = session.state.selection
    composites.enter(session, composite_id)
    selection.set_selection(session, {path_id})
    view.select_tool(session, Tool.NODE)
    g.set_tool(Tool.NODE)
    drag(g, (100, 0), (100, 0))
    drag(g, (100, 0), (110, 20))
    part = queries.find_shape(session.state, composite_id).parts[0]
    assert (part.segments[1].x, part.segments[1].y) == (110, 20)
